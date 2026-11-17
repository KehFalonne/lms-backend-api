import pytest
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APIClient

from apps.academics.models import AcademicYear, Semester
from apps.accounts.models import StaffProfile
from apps.assessments.models import (
    Assessment,
    AssessmentAttempt,
    AssessmentProctoringEvent,
    AssessmentQuestion,
    AssessmentStatus,
    AttemptStatus,
    Question,
    QuestionBank,
    QuestionOption,
    QuestionType,
    StudentAnswer,
)
from apps.courses.models import (
    Course,
    CourseEnrollment,
    CourseInstructor,
    CourseOffering,
    EnrollmentStatus,
    TeachingRole,
)
from apps.university.models import Department, Faculty, Programme

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def lecturer():
    return User.objects.create_user(
        email="lec@x.y",
        university_id="GU2",
        password="p",
        first_name="J",
        last_name="L",
        status="ACTIVE",
    )


@pytest.fixture
def student():
    return User.objects.create_user(
        email="stu@x.y",
        university_id="GU3",
        password="p",
        first_name="S",
        last_name="S",
        status="ACTIVE",
    )


@pytest.fixture
def staff():
    return User.objects.create_user(
        email="staff@x.y",
        university_id="GU4",
        password="p",
        first_name="St",
        last_name="Aff",
        status="ACTIVE",
        is_staff=True,
    )


@pytest.fixture
def setup(lecturer, student):
    f = Faculty.objects.create(code="FOC", name="Computing")
    d = Department.objects.create(faculty=f, code="CS", name="CS")
    p = Programme.objects.create(department=d, code="BSC-CS", name="BSc")
    c = Course.objects.create(
        department=d, code="CSC101", title="Intro", credits=3, level=100
    )
    y = AcademicYear.objects.create(
        name="2026/2027", start_date="2026-09-01", end_date="2027-07-31"
    )
    s = Semester.objects.create(
        academic_year=y,
        name="S1",
        code="S1",
        sequence=1,
        start_date="2026-09-01",
        end_date="2027-01-31",
    )
    o = CourseOffering.objects.create(course=c, semester=s, programme=p, section="A")
    CourseInstructor.objects.create(
        course_offering=o,
        user=lecturer,
        teaching_role=TeachingRole.PRIMARY_INSTRUCTOR,
        can_manage_content=True,
        can_grade=True,
        can_manage_assessments=True,
    )
    CourseEnrollment.objects.create(
        course_offering=o,
        student=student,
        status=EnrollmentStatus.ACTIVE,
    )
    return {"offering": o, "lecturer": lecturer, "student": student}


def _make_mcq(bank, text="What is 2+2?", correct_index=0):
    q = Question.objects.create(
        question_bank=bank,
        question_type=QuestionType.MULTIPLE_CHOICE,
        text=text,
        default_points=Decimal("2.00"),
        created_by=bank.owner,
    )
    options = ["4", "3", "5", "22"]
    for idx, opt in enumerate(options):
        QuestionOption.objects.create(
            question=q,
            text=opt,
            is_correct=(idx == correct_index),
            position=idx + 1,
        )
    return q


class TestQuestionBank:
    url = "/api/v1/question-banks/"

    def test_create_bank(self, api, lecturer):
        api.force_authenticate(user=lecturer)
        res = api.post(
            self.url, {"title": "Q1 Bank", "visibility": "PRIVATE"}, format="json"
        )
        assert res.status_code == 201
        assert res.json()["data"]["title"] == "Q1 Bank"

    def test_create_question(self, api, lecturer):
        api.force_authenticate(user=lecturer)
        bank = QuestionBank.objects.create(title="B", owner=lecturer)

        res = api.post(
            f"{self.url}{bank.id}/questions/",
            {
                "questionType": "MULTIPLE_CHOICE",
                "text": "What is 2+2?",
                "defaultPoints": "2.00",
                "options": [
                    {"text": "4", "isCorrect": True, "position": 1},
                    {"text": "3", "isCorrect": False, "position": 2},
                    {"text": "5", "isCorrect": False, "position": 3},
                ],
            },
            format="json",
        )
        assert res.status_code == 201
        assert res.json()["data"]["options"][0]["isCorrect"] is True

    def test_import_word_and_set_correct_answer(self, api, lecturer, setup):
        import io

        from docx import Document
        from django.core.files.uploadedfile import SimpleUploadedFile

        api.force_authenticate(user=lecturer)
        bank = QuestionBank.objects.create(
            title="B", owner=lecturer, course=setup["offering"].course
        )

        doc = Document()
        for line in [
            "1. What is the capital of Nigeria?",
            "A. Lagos",
            "B. Abuja",
            "C. Kano",
            "D. Ibadan",
            "Answer: B",
            "2. Which of these is a prime number?",
            "A. 4",
            "B. 6",
            "C. 7",
            "D. 9",
            "Correct Answer: C",
        ]:
            doc.add_paragraph(line)
        buffer = io.BytesIO()
        doc.save(buffer)

        upload = SimpleUploadedFile(
            "questions.docx",
            buffer.getvalue(),
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ),
        )
        res = api.post(
            f"{self.url}{bank.id}/questions/import-word/",
            {"file": upload},
            format="multipart",
        )
        assert res.status_code == 201
        data = res.json()["data"]
        assert len(data) == 2
        assert all(q["status"] == "DRAFT" for q in data)
        imported = data[0]
        assert imported["options"][1]["isCorrect"] is True  # Answer: B

        # Lecturer picks the correct answer after import.
        res = api.patch(
            f"/api/v1/questions/{imported['id']}/",
            {
                "options": [
                    {"text": "Lagos", "position": 1, "isCorrect": False},
                    {"text": "Abuja", "position": 2, "isCorrect": True},
                    {"text": "Kano", "position": 3, "isCorrect": False},
                    {"text": "Ibadan", "position": 4, "isCorrect": False},
                ]
            },
            format="json",
        )
        assert res.status_code == 200
        updated = res.json()["data"]["options"]
        assert [o["isCorrect"] for o in updated] == [False, True, False, False]

    def test_import_word_list_numbered_document(self, api, lecturer, setup):
        """Documents using Word's list numbering (no literal 1./A. text) import."""
        import io

        from docx import Document
        from docx.oxml import OxmlElement, parse_xml
        from docx.oxml.ns import nsdecls, qn
        from django.core.files.uploadedfile import SimpleUploadedFile

        api.force_authenticate(user=lecturer)
        bank = QuestionBank.objects.create(
            title="B", owner=lecturer, course=setup["offering"].course
        )

        doc = Document()

        def add_list_paragraph(text, ilvl):
            p = doc.add_paragraph(text)
            pPr = p._p.get_or_add_pPr()
            numPr = OxmlElement("w:numPr")
            ilvl_el = OxmlElement("w:ilvl")
            ilvl_el.set(qn("w:val"), str(ilvl))
            numId_el = OxmlElement("w:numId")
            numId_el.set(qn("w:val"), "1")
            numPr.append(ilvl_el)
            numPr.append(numId_el)
            pPr.append(numPr)
            return p

        for line, ilvl in [
            ("What is 2+2?", 0),
            ("3", 1),
            ("4", 1),
            ("5", 1),
            ("22", 1),
            ("A set with 3 elements has how many subsets?", 0),
            ("4", 1),
            ("6", 1),
            ("8", 1),
            ("9", 1),
        ]:
            add_list_paragraph(line, ilvl)

        numbering = doc.part.numbering_part.element
        ns = nsdecls("w")
        numbering.append(
            parse_xml(
                f'<w:abstractNum {ns} w:abstractNumId="0">'
                '<w:multiLevelType w:val="hybridMultilevel"/>'
                '<w:lvl w:ilvl="0"><w:start w:val="1"/>'
                '<w:numFmt w:val="decimal"/><w:lvlText w:val="%1."/></w:lvl>'
                '<w:lvl w:ilvl="1"><w:start w:val="1"/>'
                '<w:numFmt w:val="lowerLetter"/><w:lvlText w:val="%2."/></w:lvl>'
                "</w:abstractNum>"
            )
        )
        numbering.append(
            parse_xml(
                f'<w:num {ns} w:numId="1"><w:abstractNumId w:val="0"/></w:num>'
            )
        )

        buffer = io.BytesIO()
        doc.save(buffer)
        upload = SimpleUploadedFile(
            "list-numbered.docx",
            buffer.getvalue(),
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ),
        )
        res = api.post(
            f"{self.url}{bank.id}/questions/import-word/",
            {"file": upload},
            format="multipart",
        )
        assert res.status_code == 201
        data = res.json()["data"]
        assert len(data) == 2
        first, second = data
        assert first["options"][1]["text"] == "4"
        assert second["text"].startswith("A set with 3 elements")
        assert len(second["options"]) == 4

    def test_import_word_with_answer_key_section(self, api, lecturer, setup):
        """An "Answer Key" section at the end of the file sets correct options."""
        import io

        from docx import Document
        from django.core.files.uploadedfile import SimpleUploadedFile

        api.force_authenticate(user=lecturer)
        bank = QuestionBank.objects.create(
            title="B", owner=lecturer, course=setup["offering"].course
        )

        doc = Document()
        for line in [
            "1. What is the capital of Nigeria?",
            "A. Lagos",
            "B. Abuja",
            "C. Kano",
            "D. Ibadan",
            "2. Which of these is a prime number?",
            "A. 4",
            "B. 6",
            "C. 7",
            "D. 9",
            "ANSWER KEY",
            "1. B",
            "2-C",
        ]:
            doc.add_paragraph(line)
        buffer = io.BytesIO()
        doc.save(buffer)

        upload = SimpleUploadedFile(
            "questions-with-key.docx",
            buffer.getvalue(),
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ),
        )
        res = api.post(
            f"{self.url}{bank.id}/questions/import-word/",
            {"file": upload},
            format="multipart",
        )
        assert res.status_code == 201
        data = res.json()["data"]
        assert len(data) == 2
        assert [o["isCorrect"] for o in data[0]["options"]] == [False, True, False, False]
        assert [o["isCorrect"] for o in data[1]["options"]] == [False, False, True, False]

    def test_import_word_with_keys_heading_and_grid_table(self, api, lecturer, setup):
        """A "Keys:" heading followed by a Q-number grid table sets correct
        options and must not leak key cells into the last question."""
        import io

        from docx import Document
        from django.core.files.uploadedfile import SimpleUploadedFile

        api.force_authenticate(user=lecturer)
        bank = QuestionBank.objects.create(
            title="B", owner=lecturer, course=setup["offering"].course
        )

        doc = Document()
        for line in [
            "1. What is the capital of Nigeria?",
            "A. Lagos",
            "B. Abuja",
            "C. Kano",
            "D. Ibadan",
            "2. Which of these is a prime number?",
            "A. 4",
            "B. 6",
            "C. 7",
            "D. 9",
            "3. What is 2 + 2?",
            "A. 3",
            "B. 4",
            "C. 5",
            "D. 6",
        ]:
            doc.add_paragraph(line)
        doc.add_heading("Keys:", level=1)
        table = doc.add_table(rows=2, cols=3)
        for col, value in enumerate(["Q1", "Q2", "Q3"]):
            table.rows[0].cells[col].text = value
        for col, value in enumerate(["B", "C", "B"]):
            table.rows[1].cells[col].text = value

        buffer = io.BytesIO()
        doc.save(buffer)
        upload = SimpleUploadedFile(
            "questions-with-key-grid.docx",
            buffer.getvalue(),
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ),
        )
        res = api.post(
            f"{self.url}{bank.id}/questions/import-word/",
            {"file": upload},
            format="multipart",
        )
        assert res.status_code == 201
        data = res.json()["data"]
        assert len(data) == 3
        assert [o["isCorrect"] for o in data[0]["options"]] == [False, True, False, False]
        assert [o["isCorrect"] for o in data[1]["options"]] == [False, False, True, False]
        assert [o["isCorrect"] for o in data[2]["options"]] == [False, True, False, False]
        last_option_texts = [o["text"] for o in data[2]["options"]]
        assert last_option_texts == ["3", "4", "5", "6"]

    def test_import_word_with_headingless_key_grid_table(self, api, lecturer, setup):
        """An answer grid table with no "Keys:" heading still applies."""
        import io

        from docx import Document
        from django.core.files.uploadedfile import SimpleUploadedFile

        api.force_authenticate(user=lecturer)
        bank = QuestionBank.objects.create(
            title="B", owner=lecturer, course=setup["offering"].course
        )

        doc = Document()
        for line in [
            "1. What is the capital of Nigeria?",
            "A. Lagos",
            "B. Abuja",
            "C. Kano",
            "D. Ibadan",
            "2. Which of these is a prime number?",
            "A. 4",
            "B. 6",
            "C. 7",
            "D. 9",
        ]:
            doc.add_paragraph(line)
        table = doc.add_table(rows=2, cols=2)
        for col, value in enumerate(["Q1", "Q2"]):
            table.rows[0].cells[col].text = value
        for col, value in enumerate(["B", "C"]):
            table.rows[1].cells[col].text = value

        buffer = io.BytesIO()
        doc.save(buffer)
        upload = SimpleUploadedFile(
            "questions-with-bare-grid.docx",
            buffer.getvalue(),
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ),
        )
        res = api.post(
            f"{self.url}{bank.id}/questions/import-word/",
            {"file": upload},
            format="multipart",
        )
        assert res.status_code == 201
        data = res.json()["data"]
        assert len(data) == 2
        assert [o["isCorrect"] for o in data[0]["options"]] == [False, True, False, False]
        assert [o["isCorrect"] for o in data[1]["options"]] == [False, False, True, False]
        assert [o["text"] for o in data[1]["options"]] == ["4", "6", "7", "9"]

    def test_import_word_with_key_section_between_questions(self, api, lecturer, setup):
        """The key section may sit in the middle; questions after it still parse."""
        import io

        from docx import Document
        from django.core.files.uploadedfile import SimpleUploadedFile

        api.force_authenticate(user=lecturer)
        bank = QuestionBank.objects.create(
            title="B", owner=lecturer, course=setup["offering"].course
        )

        doc = Document()
        for line in [
            "1. What is the capital of Nigeria?",
            "A. Lagos",
            "B. Abuja",
            "C. Kano",
            "D. Ibadan",
            "2. Which of these is a prime number?",
            "A. 4",
            "B. 6",
            "C. 7",
            "D. 9",
            "ANSWER KEY",
            "1. B",
            "2. C",
            "3. B",
            "3. What is 2 + 2?",
            "A. 3",
            "B. 4",
            "C. 5",
            "D. 6",
        ]:
            doc.add_paragraph(line)
        buffer = io.BytesIO()
        doc.save(buffer)

        upload = SimpleUploadedFile(
            "questions-with-mid-key.docx",
            buffer.getvalue(),
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ),
        )
        res = api.post(
            f"{self.url}{bank.id}/questions/import-word/",
            {"file": upload},
            format="multipart",
        )
        assert res.status_code == 201
        data = res.json()["data"]
        assert len(data) == 3
        by_text = {q["text"]: q for q in data}
        capital = by_text["What is the capital of Nigeria?"]
        prime = by_text["Which of these is a prime number?"]
        sum_q = by_text["What is 2 + 2?"]
        assert [o["isCorrect"] for o in capital["options"]] == [False, True, False, False]
        assert [o["isCorrect"] for o in prime["options"]] == [False, False, True, False]
        assert [o["isCorrect"] for o in sum_q["options"]] == [False, True, False, False]

    def test_import_answer_key_file(self, api, lecturer, setup):
        """A separate .txt key file applies correct answers to bank questions."""
        import io

        from docx import Document
        from django.core.files.uploadedfile import SimpleUploadedFile

        api.force_authenticate(user=lecturer)
        bank = QuestionBank.objects.create(
            title="B", owner=lecturer, course=setup["offering"].course
        )

        doc = Document()
        for line in [
            "1. What is the capital of Nigeria?",
            "A. Lagos",
            "B. Abuja",
            "C. Kano",
            "D. Ibadan",
            "2. Which of these is a prime number?",
            "A. 4",
            "B. 6",
            "C. 7",
            "D. 9",
        ]:
            doc.add_paragraph(line)
        buffer = io.BytesIO()
        doc.save(buffer)
        upload = SimpleUploadedFile(
            "questions.docx",
            buffer.getvalue(),
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ),
        )
        res = api.post(
            f"{self.url}{bank.id}/questions/import-word/",
            {"file": upload},
            format="multipart",
        )
        assert res.status_code == 201
        imported = res.json()["data"]
        assert all(
            not any(o["isCorrect"] for o in q["options"]) for q in imported
        )

        key_upload = SimpleUploadedFile(
            "answer-key.txt",
            b"Answer Key\n1. B\n2-C\n3) A\n",
            content_type="text/plain",
        )
        res = api.post(
            f"{self.url}{bank.id}/questions/import-answer-key/",
            {"file": key_upload},
            format="multipart",
        )
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["applied"] == 2
        assert data["totalQuestions"] == 2

        res = api.get(f"{self.url}{bank.id}/questions/")
        questions = res.json()["data"]
        by_text = {q["text"]: q for q in questions}
        capital = by_text["What is the capital of Nigeria?"]
        prime = by_text["Which of these is a prime number?"]
        assert [o["isCorrect"] for o in capital["options"]] == [False, True, False, False]
        assert [o["isCorrect"] for o in prime["options"]] == [False, False, True, False]

        # Garbage file -> 400
        garbage = SimpleUploadedFile("bad.txt", b"hello world", content_type="text/plain")
        res = api.post(
            f"{self.url}{bank.id}/questions/import-answer-key/",
            {"file": garbage},
            format="multipart",
        )
        assert res.status_code == 400

    def test_import_answer_key_file_from_tables(self, api, lecturer, setup):
        """A .docx key file with an answer grid and a detail table applies keys."""
        import io

        from docx import Document
        from django.core.files.uploadedfile import SimpleUploadedFile

        api.force_authenticate(user=lecturer)
        bank = QuestionBank.objects.create(
            title="B", owner=lecturer, course=setup["offering"].course
        )

        doc = Document()
        for line in [
            "1. What is the capital of Nigeria?",
            "A. Lagos",
            "B. Abuja",
            "C. Kano",
            "D. Ibadan",
            "2. Which of these is a prime number?",
            "A. 4",
            "B. 6",
            "C. 7",
            "D. 9",
            "3. What is 2 + 2?",
            "A. 3",
            "B. 4",
            "C. 5",
            "D. 6",
        ]:
            doc.add_paragraph(line)
        buffer = io.BytesIO()
        doc.save(buffer)
        upload = SimpleUploadedFile(
            "questions.docx",
            buffer.getvalue(),
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ),
        )
        res = api.post(
            f"{self.url}{bank.id}/questions/import-word/",
            {"file": upload},
            format="multipart",
        )
        assert res.status_code == 201

        key_doc = Document()
        key_doc.add_paragraph("Assessment — Answer Key")
        grid = key_doc.add_table(rows=2, cols=3)
        grid.rows[0].cells[0].text = "Q1"
        grid.rows[0].cells[1].text = "Q2"
        grid.rows[0].cells[2].text = "Q3"
        grid.rows[1].cells[0].text = "B"
        grid.rows[1].cells[1].text = "C"
        grid.rows[1].cells[2].text = "B"
        detail = key_doc.add_table(rows=2, cols=3)
        detail.rows[0].cells[0].text = "#"
        detail.rows[0].cells[1].text = "Topic"
        detail.rows[0].cells[2].text = "Correct Answer"
        detail.rows[1].cells[0].text = "1"
        detail.rows[1].cells[1].text = "Capitals"
        detail.rows[1].cells[2].text = "B) Abuja"
        buffer = io.BytesIO()
        key_doc.save(buffer)
        key_upload = SimpleUploadedFile(
            "answer-key.docx",
            buffer.getvalue(),
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ),
        )
        res = api.post(
            f"{self.url}{bank.id}/questions/import-answer-key/",
            {"file": key_upload},
            format="multipart",
        )
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["applied"] == 3
        assert data["totalQuestions"] == 3

        res = api.get(f"{self.url}{bank.id}/questions/")
        questions = res.json()["data"]
        by_text = {q["text"]: q for q in questions}
        capital = by_text["What is the capital of Nigeria?"]
        prime = by_text["Which of these is a prime number?"]
        sum_q = by_text["What is 2 + 2?"]
        assert [o["isCorrect"] for o in capital["options"]] == [False, True, False, False]
        assert [o["isCorrect"] for o in prime["options"]] == [False, False, True, False]
        assert [o["isCorrect"] for o in sum_q["options"]] == [False, True, False, False]

    def test_import_answer_key_matches_by_text_when_order_differs(self, api, lecturer, setup):
        """Key entries with answer text map to the right questions even when
        the bank order does not match the key numbering."""
        import io

        from docx import Document
        from django.core.files.uploadedfile import SimpleUploadedFile

        api.force_authenticate(user=lecturer)
        bank = QuestionBank.objects.create(
            title="B", owner=lecturer, course=setup["offering"].course
        )

        doc = Document()
        for line in [
            "1. What is the capital of Nigeria?",
            "A. Lagos",
            "B. Abuja",
            "C. Kano",
            "D. Ibadan",
            "2. Which of these is a prime number?",
            "A. 4",
            "B. 6",
            "C. 7",
            "D. 9",
            "3. What is 2 + 2?",
            "A. 3",
            "B. 4",
            "C. 5",
            "D. 6",
        ]:
            doc.add_paragraph(line)
        buffer = io.BytesIO()
        doc.save(buffer)
        upload = SimpleUploadedFile(
            "questions.docx",
            buffer.getvalue(),
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ),
        )
        res = api.post(
            f"{self.url}{bank.id}/questions/import-word/",
            {"file": upload},
            format="multipart",
        )
        assert res.status_code == 201

        # Key numbering disagrees with bank order (bank is capital, prime, sum;
        # key numbers sum=1, capital=2, prime=3) — answer texts must win.
        key_doc = Document()
        detail = key_doc.add_table(rows=4, cols=3)
        detail.rows[0].cells[0].text = "#"
        detail.rows[0].cells[1].text = "Topic"
        detail.rows[0].cells[2].text = "Correct Answer"
        for row, (num, topic, answer) in enumerate(
            [
                ("1", "Arithmetic", "B) 4"),
                ("2", "Capitals", "B) Abuja"),
                ("3", "Primes", "C) 7"),
            ],
            start=1,
        ):
            detail.rows[row].cells[0].text = num
            detail.rows[row].cells[1].text = topic
            detail.rows[row].cells[2].text = answer
        buffer = io.BytesIO()
        key_doc.save(buffer)
        key_upload = SimpleUploadedFile(
            "answer-key.docx",
            buffer.getvalue(),
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ),
        )
        res = api.post(
            f"{self.url}{bank.id}/questions/import-answer-key/",
            {"file": key_upload},
            format="multipart",
        )
        assert res.status_code == 200
        assert res.json()["data"]["applied"] == 3

        res = api.get(f"{self.url}{bank.id}/questions/")
        questions = res.json()["data"]
        by_text = {q["text"]: q for q in questions}
        capital = by_text["What is the capital of Nigeria?"]
        prime = by_text["Which of these is a prime number?"]
        sum_q = by_text["What is 2 + 2?"]
        assert [o["isCorrect"] for o in capital["options"]] == [False, True, False, False]
        assert [o["isCorrect"] for o in prime["options"]] == [False, False, True, False]
        assert [o["isCorrect"] for o in sum_q["options"]] == [False, True, False, False]

    def test_import_answer_key_targets_selected_questions(self, api, lecturer, setup):
        """Key upload with questionIds only marks the selected questions."""
        import io

        from docx import Document
        from django.core.files.uploadedfile import SimpleUploadedFile

        api.force_authenticate(user=lecturer)
        bank = QuestionBank.objects.create(
            title="B", owner=lecturer, course=setup["offering"].course
        )

        def import_docx(lines, name):
            doc = Document()
            for line in lines:
                doc.add_paragraph(line)
            buffer = io.BytesIO()
            doc.save(buffer)
            upload = SimpleUploadedFile(
                name,
                buffer.getvalue(),
                content_type=(
                    "application/vnd.openxmlformats-officedocument."
                    "wordprocessingml.document"
                ),
            )
            return api.post(
                f"{self.url}{bank.id}/questions/import-word/",
                {"file": upload},
                format="multipart",
            )

        res = import_docx(
            [
                "1. Batch one A?",
                "A. one",
                "B. two",
                "2. Batch one B?",
                "A. one",
                "B. two",
            ],
            "batch1.docx",
        )
        assert res.status_code == 201
        batch1_ids = {q["id"] for q in res.json()["data"]}

        res = import_docx(
            [
                "1. Batch two A?",
                "A. one",
                "B. two",
                "2. Batch two B?",
                "A. one",
                "B. two",
            ],
            "batch2.docx",
        )
        assert res.status_code == 201
        batch2_ids = [q["id"] for q in res.json()["data"]]

        key_upload = SimpleUploadedFile(
            "answer-key.txt",
            b"1. A\n2. A\n",
            content_type="text/plain",
        )
        res = api.post(
            f"{self.url}{bank.id}/questions/import-answer-key/",
            {"file": key_upload, "questionIds": batch2_ids},
            format="multipart",
        )
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["applied"] == 2
        assert data["totalQuestions"] == 2

        res = api.get(f"{self.url}{bank.id}/questions/")
        by_id = {q["id"]: q for q in res.json()["data"]}
        for qid in batch2_ids:
            assert [o["isCorrect"] for o in by_id[qid]["options"]] == [True, False]
        for qid in batch1_ids:
            assert all(not o["isCorrect"] for o in by_id[qid]["options"])


class TestAssessmentLifecycle:
    def test_create_assessment(self, api, lecturer, setup):
        api.force_authenticate(user=lecturer)
        res = api.post(
            f"/api/v1/course-offerings/{setup['offering'].id}/assessments/",
            {
                "courseOfferingId": str(setup["offering"].id),
                "title": "Quiz 1",
                "assessmentType": "QUIZ",
                "maxAttempts": 1,
                "timeLimitMinutes": 30,
            },
            format="json",
        )
        assert res.status_code == 201
        assert res.json()["data"]["status"] == "DRAFT"

    def test_lecturer_sees_own_draft_student_does_not(self, api, lecturer, student, setup):
        api.force_authenticate(user=lecturer)
        Assessment.objects.create(
            course_offering=setup["offering"],
            title="Draft Quiz",
            created_by=lecturer,
        )
        Assessment.objects.create(
            course_offering=setup["offering"],
            title="Published Quiz",
            created_by=lecturer,
            status=AssessmentStatus.PUBLISHED,
        )
        res = api.get(f"/api/v1/course-offerings/{setup['offering'].id}/assessments/")
        titles = [a["title"] for a in res.json()["data"]]
        assert "Draft Quiz" in titles
        assert "Published Quiz" in titles

        api.force_authenticate(user=student)
        res = api.get(f"/api/v1/course-offerings/{setup['offering'].id}/assessments/")
        titles = [a["title"] for a in res.json()["data"]]
        assert "Published Quiz" in titles
        assert "Draft Quiz" not in titles

    def test_detail_manage_shape_for_lecturer_student_shape_for_student(
        self, api, lecturer, student, setup
    ):
        a = Assessment.objects.create(
            course_offering=setup["offering"],
            title="Detail Quiz",
            created_by=lecturer,
        )
        api.force_authenticate(user=lecturer)
        res = api.get(f"/api/v1/assessments/{a.id}/")
        assert res.status_code == 200
        assert res.json()["data"]["status"] == AssessmentStatus.DRAFT

        api.force_authenticate(user=student)
        res = api.get(f"/api/v1/assessments/{a.id}/")
        assert res.status_code == 200
        assert "status" not in res.json()["data"]

    def test_publish_requires_questions(self, api, staff, setup):
        api.force_authenticate(user=staff)
        a = Assessment.objects.create(
            course_offering=setup["offering"],
            title="Empty",
            created_by=staff,
        )
        res = api.post(f"/api/v1/assessments/{a.id}/publish/")
        assert res.status_code == 400

    def test_add_question_lecturer_cannot_publish_staff_can(
        self, api, lecturer, staff, setup
    ):
        api.force_authenticate(user=lecturer)
        a = Assessment.objects.create(
            course_offering=setup["offering"],
            title="Quiz",
            created_by=lecturer,
            available_from=timezone.now() - timedelta(hours=1),
            available_until=timezone.now() + timedelta(days=1),
        )
        bank = QuestionBank.objects.create(
            title="B", owner=lecturer, course=setup["offering"].course
        )
        q = _make_mcq(bank)

        res = api.post(
            f"/api/v1/assessments/{a.id}/questions/",
            {"questionId": str(q.id), "position": 1, "points": "2.00"},
            format="json",
        )
        assert res.status_code == 201

        res = api.post(f"/api/v1/assessments/{a.id}/publish/")
        assert res.status_code == 403

        api.force_authenticate(user=staff)
        res = api.post(f"/api/v1/assessments/{a.id}/publish/")
        assert res.status_code == 200
        assert res.json()["data"]["status"] == "PUBLISHED"

    def test_bulk_attach_questions(self, api, lecturer, setup):
        api.force_authenticate(user=lecturer)
        a = Assessment.objects.create(
            course_offering=setup["offering"],
            title="Quiz",
            created_by=lecturer,
        )
        bank = QuestionBank.objects.create(
            title="B", owner=lecturer, course=setup["offering"].course
        )
        q1 = _make_mcq(bank, text="Q1")
        q2 = _make_mcq(bank, text="Q2")
        q3 = _make_mcq(bank, text="Q3")

        res = api.post(
            f"/api/v1/assessments/{a.id}/questions/",
            {"questionIds": [str(q1.id), str(q2.id), str(q3.id)]},
            format="json",
        )
        assert res.status_code == 201
        assert len(res.json()["data"]) == 3
        assert "3 questions added" in res.json()["message"]

        res = api.get(f"/api/v1/assessments/{a.id}/questions/")
        rows = res.json()["data"]
        assert [r["position"] for r in rows] == [1, 2, 3]

        # Re-attaching the same questions is skipped, not duplicated.
        res = api.post(
            f"/api/v1/assessments/{a.id}/questions/",
            {"questionIds": [str(q1.id), str(q2.id)]},
            format="json",
        )
        assert res.status_code == 201
        assert res.json()["data"] == []
        assert AssessmentQuestion.objects.filter(assessment=a).count() == 3

        # Questions from a bank of another course are skipped.
        other_bank = QuestionBank.objects.create(title="X", owner=lecturer)
        qx = _make_mcq(other_bank, text="QX")
        res = api.post(
            f"/api/v1/assessments/{a.id}/questions/",
            {"questionIds": [str(qx.id)]},
            format="json",
        )
        assert res.status_code == 201
        assert res.json()["data"] == []
        assert AssessmentQuestion.objects.filter(assessment=a).count() == 3


class TestStaffAssessmentAccess:
    """Administrators and school staff manage assessments even without an
    instructor link on the offering."""

    def test_staff_can_create_assessment(self, api, staff, setup):
        api.force_authenticate(user=staff)
        assert not CourseInstructor.objects.filter(user=staff).exists()

        res = api.post(
            f"/api/v1/course-offerings/{setup['offering'].id}/assessments/",
            {
                "courseOfferingId": str(setup["offering"].id),
                "title": "Staff Quiz",
                "assessmentType": "QUIZ",
                "maxAttempts": 1,
                "timeLimitMinutes": 30,
            },
            format="json",
        )
        assert res.status_code == 201
        assert res.json()["data"]["status"] == "DRAFT"

    def test_staff_can_add_question_and_publish(self, api, staff, setup):
        api.force_authenticate(user=staff)
        a = Assessment.objects.create(
            course_offering=setup["offering"],
            title="Staff Quiz",
            created_by=staff,
            available_from=timezone.now() - timedelta(hours=1),
            available_until=timezone.now() + timedelta(days=1),
        )
        bank = QuestionBank.objects.create(
            title="B", owner=staff, course=setup["offering"].course
        )
        q = _make_mcq(bank)

        res = api.post(
            f"/api/v1/assessments/{a.id}/questions/",
            {"questionId": str(q.id), "position": 1, "points": "2.00"},
            format="json",
        )
        assert res.status_code == 201

        res = api.post(f"/api/v1/assessments/{a.id}/publish/")
        assert res.status_code == 200
        assert res.json()["data"]["status"] == "PUBLISHED"

    def test_superuser_can_create_assessment(self, api, setup):
        admin = User.objects.create_superuser(
            email="root@x.y", university_id="GU0001", password="p"
        )
        api.force_authenticate(user=admin)
        res = api.post(
            f"/api/v1/course-offerings/{setup['offering'].id}/assessments/",
            {
                "courseOfferingId": str(setup["offering"].id),
                "title": "Admin Quiz",
                "assessmentType": "QUIZ",
            },
            format="json",
        )
        assert res.status_code == 201


class TestCAAccessControl:
    """CA code issuance and CA config are admin/staff/invigilator-only."""

    def _assessment(self, setup, created_by):
        return Assessment.objects.create(
            course_offering=setup["offering"],
            title="CA",
            created_by=created_by,
        )

    def test_lecturer_cannot_generate_code(self, api, lecturer, setup):
        a = self._assessment(setup, lecturer)
        api.force_authenticate(user=lecturer)
        res = api.post(f"/api/v1/assessments/{a.id}/generate-code/")
        assert res.status_code == 403

    def test_staff_can_generate_code(self, api, staff, setup):
        a = self._assessment(setup, staff)
        api.force_authenticate(user=staff)
        res = api.post(f"/api/v1/assessments/{a.id}/generate-code/")
        assert res.status_code == 200
        assert res.json()["data"]["code"]
        a.refresh_from_db()
        assert a.access_code_hash

    def test_invigilator_can_generate_code(self, api, setup):
        invigilator = User.objects.create_user(
            email="inv@x.y",
            university_id="GU9",
            password="p",
            status="ACTIVE",
        )
        StaffProfile.objects.create(user=invigilator, staff_number="INV-1")
        a = self._assessment(setup, setup["lecturer"])
        a.ca_invigilator = invigilator
        a.save(update_fields=["ca_invigilator", "updated_at"])

        api.force_authenticate(user=invigilator)
        res = api.post(f"/api/v1/assessments/{a.id}/generate-code/")
        assert res.status_code == 200
        assert res.json()["data"]["code"]

    def test_lecturer_cannot_set_ca_fields(self, api, lecturer, setup):
        api.force_authenticate(user=lecturer)
        res = api.post(
            f"/api/v1/course-offerings/{setup['offering'].id}/assessments/",
            {
                "title": "CA Quiz",
                "assessmentType": "QUIZ",
                "caOpensAt": timezone.now().isoformat(),
            },
            format="json",
        )
        assert res.status_code == 403

        a = self._assessment(setup, lecturer)
        res = api.patch(
            f"/api/v1/assessments/{a.id}/",
            {"proctoringEnabled": True},
            format="json",
        )
        assert res.status_code == 403

    def test_staff_can_set_ca_fields(self, api, staff, setup):
        api.force_authenticate(user=staff)
        a = self._assessment(setup, staff)
        res = api.patch(
            f"/api/v1/assessments/{a.id}/",
            {
                "caOpensAt": timezone.now().isoformat(),
                "proctoringEnabled": True,
            },
            format="json",
        )
        assert res.status_code == 200
        assert res.json()["data"]["proctoringEnabled"] is True


class TestAttemptFlow:
    def _make_assessment(self, setup, lecturer, *, time_limit=30):
        a = Assessment.objects.create(
            course_offering=setup["offering"],
            title="Quiz",
            assessment_type="QUIZ",
            created_by=lecturer,
            max_attempts=1,
            time_limit_minutes=time_limit,
            available_from=timezone.now() - timedelta(hours=1),
            available_until=timezone.now() + timedelta(days=1),
            status=AssessmentStatus.PUBLISHED,
            total_points=Decimal("2.00"),
        )
        bank = QuestionBank.objects.create(title="B", owner=lecturer)
        q = _make_mcq(bank)
        aq = AssessmentQuestion.objects.create(
            assessment=a, question=q, position=1, points=Decimal("2.00")
        )
        return a, aq, q

    def test_student_starts_and_submits(self, api, student, lecturer, setup):
        a, aq, q = self._make_assessment(setup, lecturer)

        api.force_authenticate(user=student)
        res = api.post(f"/api/v1/assessments/{a.id}/attempts/start/")
        assert res.status_code == 201
        attempt_id = res.json()["data"]["id"]

        # Save correct answer
        correct = q.options.filter(is_correct=True).first()
        res = api.put(
            f"/api/v1/assessment-attempts/{attempt_id}/answers/{aq.id}/",
            {"selectedOptionIds": [str(correct.id)]},
            format="json",
        )
        assert res.status_code == 200

        # Submit
        res = api.post(f"/api/v1/assessment-attempts/{attempt_id}/submit/")
        assert res.status_code == 200
        body = res.json()["data"]
        assert body["status"] == "AUTO_GRADED"
        assert Decimal(body["totalScore"]) == Decimal("2.00")
        assert Decimal(body["percentage"]) == Decimal("100.00")
        assert body["passed"] is True
        assert Decimal(body["passingScore"]) == Decimal("50.00")
        assert Decimal(body["totalPoints"]) == Decimal("2.00")

    def test_wrong_answer_scores_zero(self, api, student, lecturer, setup):
        a, aq, q = self._make_assessment(setup, lecturer)

        api.force_authenticate(user=student)
        attempt_id = api.post(f"/api/v1/assessments/{a.id}/attempts/start/").json()[
            "data"
        ]["id"]
        wrong = q.options.filter(is_correct=False).first()
        api.put(
            f"/api/v1/assessment-attempts/{attempt_id}/answers/{aq.id}/",
            {"selectedOptionIds": [str(wrong.id)]},
            format="json",
        )
        body = api.post(f"/api/v1/assessment-attempts/{attempt_id}/submit/").json()[
            "data"
        ]
        assert Decimal(body["totalScore"]) == Decimal("0.00")
        assert body["passed"] is False

    def test_max_attempts_enforced(self, api, student, lecturer, setup):
        a, aq, q = self._make_assessment(setup, lecturer)

        api.force_authenticate(user=student)
        api.post(f"/api/v1/assessments/{a.id}/attempts/start/")
        res = api.post(f"/api/v1/assessments/{a.id}/attempts/start/")
        assert res.status_code == 400

    def test_student_cannot_see_other_attempt(self, api, student, lecturer, setup):
        # Create an attempt owned by the lecturer (not student)
        a, aq, q = self._make_assessment(setup, lecturer)
        from apps.assessments.services.attempt_service import AttemptService

        CourseEnrollment.objects.get_or_create(
            course_offering=setup["offering"],
            student=lecturer,
            defaults={"status": EnrollmentStatus.ACTIVE},
        )
        attempt = AttemptService.start_attempt(assessment=a, student=lecturer)

        api.force_authenticate(user=student)
        res = api.get(f"/api/v1/assessment-attempts/{attempt.id}/")
        assert res.status_code == 403

    def test_proctoring_review_only_counts_events_without_submitting(
        self, api, student, lecturer, setup
    ):
        a, _, _ = self._make_assessment(setup, lecturer)
        a.proctoring_enabled = True
        a.proctoring_max_violations = 1
        a.proctoring_enforcement = "REVIEW_ONLY"
        a.save(update_fields=[
            "proctoring_enabled",
            "proctoring_max_violations",
            "proctoring_enforcement",
        ])

        api.force_authenticate(user=student)
        attempt_id = api.post(f"/api/v1/assessments/{a.id}/attempts/start/").json()[
            "data"
        ]["id"]
        response = api.post(
            f"/api/v1/assessment-attempts/{attempt_id}/proctoring-events/",
            {"eventType": "TAB_SWITCH"},
            format="json",
        )

        assert response.status_code == 200
        assert response.json()["data"]["violationCount"] == 1
        assert response.json()["data"]["autoSubmitted"] is False
        assert AssessmentAttempt.objects.get(id=attempt_id).status == AttemptStatus.IN_PROGRESS

    def test_proctoring_auto_submit_is_server_enforced(
        self, api, student, lecturer, setup
    ):
        a, _, _ = self._make_assessment(setup, lecturer)
        a.proctoring_enabled = True
        a.proctoring_max_violations = 1
        a.proctoring_enforcement = "AUTO_SUBMIT"
        a.save(update_fields=[
            "proctoring_enabled",
            "proctoring_max_violations",
            "proctoring_enforcement",
        ])

        api.force_authenticate(user=student)
        attempt_id = api.post(f"/api/v1/assessments/{a.id}/attempts/start/").json()[
            "data"
        ]["id"]
        response = api.post(
            f"/api/v1/assessment-attempts/{attempt_id}/proctoring-events/",
            {"eventType": "TAB_SWITCH"},
            format="json",
        )

        assert response.status_code == 200
        assert response.json()["data"]["autoSubmitted"] is True
        assert AssessmentProctoringEvent.objects.filter(attempt_id=attempt_id).count() == 1
        assert AssessmentAttempt.objects.get(id=attempt_id).status != AttemptStatus.IN_PROGRESS


class TestMyAssessments:
    def test_list(self, api, student, lecturer, setup):
        a, aq, q = self._make_assessment_for_test(setup, lecturer)
        api.force_authenticate(user=student)
        res = api.get("/api/v1/my/assessments/")
        assert res.status_code == 200
        assert len(res.json()["data"]) == 1

    def _make_assessment_for_test(self, setup, lecturer):
        a = Assessment.objects.create(
            course_offering=setup["offering"],
            title="Quiz",
            created_by=lecturer,
            status=AssessmentStatus.PUBLISHED,
            available_from=timezone.now() - timedelta(hours=1),
            available_until=timezone.now() + timedelta(days=1),
        )
        return a, None, None


class TestAdminBankAccess:
    """Administrators and staff can open and use any course bank, while
    lecturers stay owner-scoped."""

    url = "/api/v1/question-banks/"

    def _other_bank(self, setup, lecturer):
        return QuestionBank.objects.create(
            title="Lecturer Bank",
            owner=lecturer,
            course=setup["offering"].course,
            department=setup["offering"].course.department,
        )

    def test_admin_lists_other_owners_banks_for_course(self, api, staff, setup, lecturer):
        bank = self._other_bank(setup, lecturer)
        api.force_authenticate(user=staff)
        res = api.get(
            f"{self.url}?courseOfferingId={setup['offering'].id}", format="json"
        )
        assert res.status_code == 200
        rows = res.json()["data"]
        assert any(r["id"] == str(bank.id) for r in rows)
        row = next(r for r in rows if r["id"] == str(bank.id))
        assert row["owner"]["id"] == str(lecturer.id)

    def test_lecturer_still_sees_only_own_banks(self, api, setup):
        other = User.objects.create_user(
            email="other@x.y",
            university_id="GU5",
            password="p",
            status="ACTIVE",
        )
        bank = self._other_bank(setup, other)
        api.force_authenticate(user=setup["lecturer"])
        res = api.get(
            f"{self.url}?courseOfferingId={setup['offering'].id}", format="json"
        )
        assert res.status_code == 200
        rows = res.json()["data"]
        assert all(r["id"] != str(bank.id) for r in rows)

    def test_admin_opens_and_imports_into_other_owners_bank(self, api, staff, setup, lecturer):
        import io

        from docx import Document
        from django.core.files.uploadedfile import SimpleUploadedFile

        bank = self._other_bank(setup, lecturer)
        doc = Document()
        for line in [
            "1. What is 2+2?",
            "A. 3",
            "B. 4",
            "C. 5",
            "D. 6",
        ]:
            doc.add_paragraph(line)
        buffer = io.BytesIO()
        doc.save(buffer)
        upload = SimpleUploadedFile(
            "questions.docx",
            buffer.getvalue(),
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ),
        )
        api.force_authenticate(user=staff)
        res = api.get(f"{self.url}{bank.id}/")
        assert res.status_code == 200
        res = api.post(
            f"{self.url}{bank.id}/questions/import-word/",
            {"file": upload},
            format="multipart",
        )
        assert res.status_code == 201
        assert bank.questions.filter(deleted_at__isnull=True).count() == 1

    def test_lecturer_cannot_open_other_owners_bank(self, api, setup):
        other = User.objects.create_user(
            email="other2@x.y",
            university_id="GU6",
            password="p",
            status="ACTIVE",
        )
        bank = self._other_bank(setup, other)
        api.force_authenticate(user=setup["lecturer"])
        res = api.get(f"{self.url}{bank.id}/")
        assert res.status_code == 404
