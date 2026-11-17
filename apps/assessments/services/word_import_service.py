import re
from dataclasses import dataclass
from datetime import timedelta
from difflib import SequenceMatcher

from docx import Document
from docx.oxml.ns import qn
from django.db import transaction
from django.utils import timezone

from apps.assessments.models import Question, QuestionBank, QuestionOption, QuestionType


QUESTION_RE = re.compile(r"^(?:question\s*)?(\d+)[\s.)-]+(.+)$", re.IGNORECASE)
OPTION_RE = re.compile(r"^([A-H])[\s.)\-:]+(.+)$", re.IGNORECASE)
ANSWER_RE = re.compile(
    r"^(?:answer|correct\s+answer|correct)\s*[:\-]\s*([A-H](?:\s*[,/&]\s*[A-H])?)$",
    re.IGNORECASE,
)
# A literal typed label like "A." or "1)" — only then is the raw text authoritative.
LITERAL_LABEL_RE = re.compile(r"^(?:[A-Ha-h]|\d+)\s*[.)]", re.IGNORECASE)

# A heading line that starts the answer key section: "Answer Key", "Keys:",
# "Correct Answers", "ANSWERS"...
KEY_SECTION_RE = re.compile(
    r"^\s*(?:answer\s*keys?|answers?|correct\s+answers?|keys?)\s*[:\-]?\s*$",
    re.IGNORECASE,
)
# Key entries anywhere on a line: "1. B", "10-A", "3) C", "1-B, 2-C".
KEY_ENTRY_RE = re.compile(r"(\d+)\s*[-.)\s]+\s*([A-H])\b", re.IGNORECASE)

# Table-based key formats: answer grids ("Q1..Q10" header row with letters in
# the cells below) and detail rows ("1 | Topic | B) text"), plus "Q1 | B" pairs.
Q_HEADER_RE = re.compile(r"^\s*Q\s*(\d+)\s*$", re.IGNORECASE)
NUM_CELL_RE = re.compile(r"^\s*(\d+)\s*$")
LETTER_CELL_RE = re.compile(r"^\s*([A-H])\s*$", re.IGNORECASE)
LETTER_PREFIX_RE = re.compile(r"^\s*([A-H])\s*[).:]", re.IGNORECASE)
CELL_KEY_RE = re.compile(r"^\s*(\d+)\s*[-.)\s]+\s*([A-H])\b", re.IGNORECASE)
# Bare "Q3" or "B" cells from an answer grid that has no "Keys:" heading.
BARE_KEY_CELL_RE = re.compile(r"^\s*(?:Q\s*\d+|[A-H])\s*$", re.IGNORECASE)


@dataclass
class ParsedQuestion:
    text: str
    options: list[str]
    correct_labels: set[str]


def _numbering_levels(document: Document) -> dict[int, dict[int, tuple[str, int]]]:
    """Map numId -> {ilvl: (numFmt, start)} from the document's numbering part."""
    try:
        numbering = document.part.numbering_part.element
    except (AttributeError, NotImplementedError):
        return {}

    abstracts: dict[str, dict[int, tuple[str, int]]] = {}
    for abstract in numbering.findall(qn("w:abstractNum")):
        abstract_id = abstract.get(qn("w:abstractNumId"))
        levels: dict[int, tuple[str, int]] = {}
        for lvl in abstract.findall(qn("w:lvl")):
            ilvl = int(lvl.get(qn("w:ilvl")))
            fmt = lvl.find(qn("w:numFmt"))
            start = lvl.find(qn("w:start"))
            levels[ilvl] = (
                fmt.get(qn("w:val")) if fmt is not None else "decimal",
                int(start.get(qn("w:val"))) if start is not None else 1,
            )
        abstracts[abstract_id] = levels

    num_map: dict[int, dict[int, tuple[str, int]]] = {}
    for num in numbering.findall(qn("w:num")):
        ref = num.find(qn("w:abstractNumId"))
        abstract_id = ref.get(qn("w:val")) if ref is not None else None
        if abstract_id in abstracts:
            num_map[int(num.get(qn("w:numId")))] = abstracts[abstract_id]
    return num_map


def _list_prefix(paragraph, num_map, counters) -> str | None:
    """Reconstruct "1." / "A." for paragraphs using Word list numbering."""
    pPr = paragraph._p.pPr
    if pPr is None or pPr.numPr is None:
        return None
    num_pr = pPr.numPr
    try:
        num_id = int(num_pr.numId.val)
        ilvl = int(num_pr.ilvl.val) if num_pr.ilvl is not None else 0
    except (TypeError, ValueError):
        return None
    levels = num_map.get(num_id)
    if not levels or ilvl not in levels:
        return None

    for key in [k for k in counters if k[0] == num_id and k[1] > ilvl]:
        counters.pop(key)
    key = (num_id, ilvl)
    counters[key] = counters.get(key, levels[ilvl][1] - 1) + 1
    number = counters[key]
    return f"{number}." if ilvl == 0 else f"{chr(64 + number)}."


def _paragraphs(document: Document) -> list[str]:
    num_map = _numbering_levels(document)
    counters: dict[tuple[int, int], int] = {}
    values: list[str] = []

    def add(paragraph) -> None:
        text = paragraph.text.strip()
        if not text:
            return
        if (
            QUESTION_RE.match(text)
            or ANSWER_RE.match(text)
            or LITERAL_LABEL_RE.match(text)
        ):
            values.append(text)
            return
        prefix = _list_prefix(paragraph, num_map, counters)
        if prefix:
            text = f"{prefix} {text}"
        values.append(text)

    for paragraph in document.paragraphs:
        add(paragraph)
    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    add(paragraph)
    return values


def parse_answer_key(lines: list[str]) -> dict[int, str]:
    """Extract question-number -> letter entries from answer key lines."""
    entries: dict[int, str] = {}
    for line in lines:
        for match in KEY_ENTRY_RE.finditer(line):
            entries[int(match.group(1))] = match.group(2).upper()
    return entries


def parse_answer_key_tables(document: Document) -> dict[int, str]:
    """Extract key entries from table layouts (answer grids, detail rows)."""
    entries: dict[int, str] = {}
    for table in document.tables:
        rows = [[cell.text.strip() for cell in row.cells] for row in table.rows]
        for r, row in enumerate(rows):
            if not row:
                continue
            # "1 | B" / "Q7 | B) text" — number first, letter beside it.
            first = Q_HEADER_RE.match(row[0]) or NUM_CELL_RE.match(row[0])
            if first:
                num = int(first.group(1))
                for cell in row[1:]:
                    letter = LETTER_CELL_RE.match(cell) or LETTER_PREFIX_RE.match(cell)
                    if letter:
                        entries[num] = letter.group(1).upper()
                        break
            # "1. B" inside a single cell.
            for cell in row:
                cell_match = CELL_KEY_RE.match(cell)
                if cell_match:
                    entries[int(cell_match.group(1))] = cell_match.group(2).upper()
            # Grid: "Q1..Q10" header row, letters in the same column below.
            for c, cell in enumerate(row):
                header = Q_HEADER_RE.match(cell)
                if not header:
                    continue
                num = int(header.group(1))
                for below in rows[r + 1 :]:
                    if c < len(below):
                        letter = LETTER_CELL_RE.match(below[c])
                        if letter:
                            entries[num] = letter.group(1).upper()
                            break
    return entries


def parse_answer_key_document(document: Document) -> dict[int, str]:
    entries = parse_answer_key(_paragraphs(document))
    entries.update(parse_answer_key_tables(document))
    return entries


def parse_answer_key_texts(document: Document) -> dict[int, tuple[str, str]]:
    """Extract number -> (letter, answer text) from detail rows like "1 | Topic | B) text"."""
    entries: dict[int, tuple[str, str]] = {}
    for table in document.tables:
        rows = [[cell.text.strip() for cell in row.cells] for row in table.rows]
        for row in rows:
            if not row:
                continue
            first = Q_HEADER_RE.match(row[0]) or NUM_CELL_RE.match(row[0])
            if not first:
                continue
            num = int(first.group(1))
            for cell in row[1:]:
                letter_match = LETTER_PREFIX_RE.match(cell)
                if letter_match:
                    text = cell[letter_match.end() :].strip()
                    if text:
                        entries[num] = (letter_match.group(1).upper(), text)
                    break
    return entries


def _apply_key_entries(parsed: list[ParsedQuestion], entries: dict[int, str]) -> None:
    """Set correct_labels on parsed questions from key entries."""
    numbers = sorted(entries)
    if not numbers or not parsed:
        return
    # Numbers within range map directly; otherwise (e.g. numbering continued
    # past the question count) map entries in ascending order to question order.
    if all(1 <= n <= len(parsed) for n in numbers):
        for num, label in entries.items():
            parsed[num - 1].correct_labels = {label}
    else:
        for idx, num in enumerate(numbers):
            if idx < len(parsed):
                parsed[idx].correct_labels = {entries[num]}


def _is_key_line(line: str) -> bool:
    """True when a line is nothing but answer-key entries ("1. B", "1-B, 2-C").
    Used to tell key entries apart from questions inside a key section, so the
    section may sit anywhere in the document instead of only at the end."""
    if not KEY_ENTRY_RE.search(line):
        return False
    return not KEY_ENTRY_RE.sub("", line).strip(" ,;")


def parse_word_questions(document: Document) -> list[ParsedQuestion]:
    parsed: list[ParsedQuestion] = []
    current: ParsedQuestion | None = None
    key_lines: list[str] = []
    in_key_section = False

    for line in _paragraphs(document):
        if in_key_section:
            question_match = QUESTION_RE.match(line)
            if question_match and not _is_key_line(line):
                in_key_section = False
            else:
                key_lines.append(line)
                continue
        if KEY_SECTION_RE.match(line):
            in_key_section = True
            continue

        question_match = QUESTION_RE.match(line)
        option_match = OPTION_RE.match(line)
        answer_match = ANSWER_RE.match(line)

        if question_match:
            if current:
                parsed.append(current)
            current = ParsedQuestion(
                text=question_match.group(2).strip(),
                options=[],
                correct_labels=set(),
            )
        elif current and option_match:
            current.options.append(option_match.group(2).strip())
        elif current and answer_match:
            current.correct_labels = {
                label.strip().upper()
                for label in re.split(r"[,/&]", answer_match.group(1))
            }
        elif current and BARE_KEY_CELL_RE.match(line):
            in_key_section = True
            key_lines.append(line)
        elif current:
            if current.options:
                current.options[-1] = f"{current.options[-1]} {line}".strip()
            else:
                current.text = f"{current.text} {line}".strip()

    if current:
        parsed.append(current)
    parsed = [question for question in parsed if question.text and len(question.options) >= 2]
    entries = parse_answer_key(key_lines)
    if key_lines or in_key_section:
        entries.update(parse_answer_key_tables(document))
    _apply_key_entries(parsed, entries)
    return parsed


@transaction.atomic
def import_word_questions(bank: QuestionBank, document: Document, user) -> list[Question]:
    questions = parse_word_questions(document)
    created: list[Question] = []

    for item in questions:
        question = Question.objects.create(
            question_bank=bank,
            question_type=QuestionType.MULTIPLE_CHOICE,
            text=item.text,
            created_by=user,
        )
        for position, option_text in enumerate(item.options, start=1):
            label = chr(64 + position)
            QuestionOption.objects.create(
                question=question,
                text=option_text,
                position=position,
                is_correct=label in item.correct_labels,
            )
        created.append(question)

    # The clock has millisecond resolution, so a fast import gives many
    # questions identical created_at values and UUID tiebreaking scrambles the
    # order answer keys rely on. Pin a strictly increasing timestamp instead.
    base = timezone.now()
    for idx, question in enumerate(created):
        Question.objects.filter(pk=question.pk).update(
            created_at=base + timedelta(microseconds=idx)
        )
    return created


def _normalize_key_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).casefold().rstrip(".")


def _match_by_answer(questions, position_texts, entry: tuple[str, str]):
    """Find the question whose option at the key's letter position matches the
    answer text (exact, then close match). Returns None when ambiguous."""
    letter, text = entry
    position = ord(letter) - 64
    norm = _normalize_key_text(text)
    if not norm:
        return None

    exact = [
        q
        for q in questions
        if _normalize_key_text(position_texts[q.id].get(position, "")) == norm
    ]
    if len(exact) == 1:
        return exact[0]

    best = None
    best_ratio = 0.0
    second_ratio = 0.0
    for q in questions:
        option_text = _normalize_key_text(position_texts[q.id].get(position, ""))
        if not option_text:
            continue
        ratio = SequenceMatcher(None, norm, option_text).ratio()
        if ratio > best_ratio:
            second_ratio, best_ratio, best = best_ratio, ratio, q
        elif ratio > second_ratio:
            second_ratio = ratio
    if best is not None and best_ratio >= 0.9 and best_ratio - second_ratio >= 0.05:
        return best
    return None


def apply_answer_key_to_questions(
    questions, entries: dict[int, str], answer_texts: dict[int, tuple[str, str]] | None = None
) -> int:
    """Set each question's correct option from key entries; returns count applied.

    When the key file carries answer texts (e.g. "B) p ∧ ¬q"), questions are
    matched by that text so reordered banks still get correct answers;
    otherwise entries map by question number/position."""
    numbers = sorted(entries)
    if not numbers or not questions:
        return 0

    position_texts = {
        q.id: {o.position: o.text for o in q.options.all()} for q in questions
    }
    applied = 0
    for num, label in entries.items():
        target = None
        if answer_texts and num in answer_texts:
            target = _match_by_answer(questions, position_texts, answer_texts[num])
        if target is None:
            if all(1 <= n <= len(questions) for n in numbers):
                target = questions[num - 1]
            else:
                idx = numbers.index(num)
                target = questions[idx] if idx < len(questions) else None
        if target is None:
            continue
        position = ord(label) - 64
        if position not in position_texts[target.id]:
            continue
        target.options.update(is_correct=False)
        target.options.filter(position=position).update(is_correct=True)
        applied += 1
    return applied
