"""
Seed 30 diverse questions into CSC301 Midterm Quiz and configure it as a
randomized CA exam.

Usage:
    python manage.py seed_ca_exam_30
    python manage.py seed_ca_exam_30 --duration-hours 4 --last-entry-minutes 180
"""

from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.assessments.models import (
    Assessment,
    AssessmentAttempt,
    AssessmentCodeAttempt,
    AssessmentQuestion,
    Question,
    QuestionBank,
    QuestionOption,
)
from apps.assessments.services.access_service import AssessmentAccessService

# ── 30 questions (mix of MCQ, True/False, Short Answer, Numeric) ──

MCQ = [
    {
        "text": "What does SQL stand for?",
        "options": [
            ("Structured Query Language", True),
            ("Simple Query Language", False),
            ("Standard Query Language", False),
            ("Sequential Query Language", False),
        ],
    },
    {
        "text": "Which of these is a DDL command?",
        "options": [
            ("CREATE", True),
            ("SELECT", False),
            ("INSERT", False),
            ("UPDATE", False),
        ],
    },
    {
        "text": "What is the primary purpose of a primary key?",
        "options": [
            ("Uniquely identify each row", True),
            ("Speed up sorting", False),
            ("Store metadata", False),
            ("Encrypt data", False),
        ],
    },
    {
        "text": "What does a foreign key do?",
        "options": [
            ("Links to another table's primary key", True),
            ("Encrypts the row", False),
            ("Indexes every column", False),
            ("Deletes the row on insert", False),
        ],
    },
    {
        "text": "Which join returns all rows from both tables, matching where possible?",
        "options": [
            ("FULL OUTER JOIN", True),
            ("INNER JOIN", False),
            ("LEFT JOIN", False),
            ("CROSS JOIN", False),
        ],
    },
    {
        "text": "What does ACID stand for in database transactions?",
        "options": [
            ("Atomicity, Consistency, Isolation, Durability", True),
            ("Access, Create, Index, Delete", False),
            ("Atomic, Compact, Integrated, Distributed", False),
            ("Alter, Commit, Insert, Delete", False),
        ],
    },
    {
        "text": "Which normal form eliminates transitive dependencies?",
        "options": [
            ("Third Normal Form (3NF)", True),
            ("First Normal Form (1NF)", False),
            ("Second Normal Form (2NF)", False),
            ("Boyce-Codd Normal Form (BCNF)", False),
        ],
    },
    {
        "text": "What is an index primarily used for?",
        "options": [
            ("Speeding up read queries", True),
            ("Encrypting rows", False),
            ("Validating data types", False),
            ("Auto-generating IDs", False),
        ],
    },
    {
        "text": "Which SQL command permanently removes a table from the database?",
        "options": [
            ("DROP TABLE", True),
            ("DELETE TABLE", False),
            ("REMOVE TABLE", False),
            ("CLEAR TABLE", False),
        ],
    },
    {
        "text": "What does NULL represent in SQL?",
        "options": [
            ("An unknown or missing value", True),
            ("The number zero", False),
            ("An empty string", False),
            ("A boolean false", False),
        ],
    },
]

TRUE_FALSE = [
    ("A primary key can be NULL.", False),
    ("A foreign key can be NULL.", True),
    ("DELETE removes the entire table structure.", False),
    ("A UNIQUE constraint can allow multiple NULLs.", True),
    ("Every table must have a primary key.", False),
    ("ORDER BY is used for filtering rows.", False),
    ("A view physically stores its own copy of the data.", False),
    ("Transactions can be rolled back.", True),
]

SHORT_ANSWER = [
    ("Which SQL keyword removes duplicate rows?", ["DISTINCT", "distinct"]),
    ("Which SQL clause filters rows?", ["WHERE", "where"]),
    ("Which SQL clause sorts results?", ["ORDER BY", "order by"]),
    ("Which SQL keyword adds a new row?", ["INSERT", "insert"]),
    ("Which SQL command modifies existing rows?", ["UPDATE", "update"]),
    ("Which SQL keyword creates an alias?", ["AS", "as"]),
    (
        "Which type of key uniquely identifies a row in a table?",
        ["PRIMARY KEY", "primary key"],
    ),
    (
        "What does GROUP BY typically accompany in aggregation?",
        ["AGGREGATE", "aggregate function", "aggregate functions"],
    ),
]

NUMERIC = [
    ("What is the maximum value of a signed TINYINT?", Decimal("127")),
    (
        "What is the minimum number of tables required to demonstrate a JOIN?",
        Decimal("2"),
    ),
    (
        "If a table has a PRIMARY KEY column and 3 other columns, how many total columns does it have?",
        Decimal("4"),
    ),
    ("What does SELECT COUNT(*) return for an empty table?", Decimal("0")),
]


class Command(BaseCommand):
    help = "Seed 30 diverse questions into the CSC301 Midterm Quiz CA exam."

    def add_arguments(self, parser):
        parser.add_argument("--duration-hours", type=float, default=4.0)
        parser.add_argument("--last-entry-minutes", type=int, default=180)

    @transaction.atomic
    def handle(self, *args, **opts):
        now = timezone.now()

        # Find the assessment
        a = Assessment.objects.filter(title__icontains="Midterm").first()
        if not a:
            a = Assessment.objects.filter(assessment_type="QUIZ").first()
        if not a:
            self.stderr.write(
                self.style.ERROR(
                    "No assessment found. Run `python manage.py seed_all` first."
                )
            )
            return

        # Get or create the question bank
        bank = a.assessment_questions.first()
        bank = bank.question.question_bank if bank else None
        if not bank:
            bank = QuestionBank.objects.filter(title__icontains="CSC301").first()
        if not bank:
            bank = QuestionBank.objects.create(
                course=a.course_offering.course,
                title="CSC301 — CA Question Bank",
                description="Auto-generated CA question bank.",
                owner=a.created_by,
                visibility="PRIVATE",
            )

        # Clear existing attempts + code audit trail first
        # (otherwise student can't re-enter after the question set changes)
        n_attempts = AssessmentAttempt.objects.filter(assessment=a).delete()[0]
        AssessmentCodeAttempt.objects.filter(assessment=a).delete()
        if n_attempts:
            self.stdout.write(f"  Cleared {n_attempts} existing attempt(s)")

        # Clear existing assessment-question links (keep bank questions)
        AssessmentQuestion.objects.filter(assessment=a).delete()

        # ── Create 30 questions and attach them ──────────────────
        created = []

        for q_data in MCQ:
            q = Question.objects.create(
                question_bank=bank,
                question_type="MULTIPLE_CHOICE",
                text=q_data["text"],
                default_points=Decimal("2.00"),
                difficulty="MEDIUM",
                created_by=a.created_by,
            )
            for i, (opt_text, is_correct) in enumerate(q_data["options"], start=1):
                QuestionOption.objects.create(
                    question=q,
                    text=opt_text,
                    is_correct=is_correct,
                    position=i,
                )
            created.append(q)

        for q_text, correct in TRUE_FALSE:
            q = Question.objects.create(
                question_bank=bank,
                question_type="TRUE_FALSE",
                text=q_text,
                default_points=Decimal("1.00"),
                difficulty="EASY",
                created_by=a.created_by,
            )
            QuestionOption.objects.create(
                question=q,
                text="True",
                is_correct=correct,
                position=1,
            )
            QuestionOption.objects.create(
                question=q,
                text="False",
                is_correct=not correct,
                position=2,
            )
            created.append(q)

        for q_text, answer_key in SHORT_ANSWER:
            q = Question.objects.create(
                question_bank=bank,
                question_type="SHORT_ANSWER",
                text=q_text,
                default_points=Decimal("2.00"),
                difficulty="MEDIUM",
                answer_key=answer_key,
                created_by=a.created_by,
            )
            created.append(q)

        for q_text, numeric in NUMERIC:
            q = Question.objects.create(
                question_bank=bank,
                question_type="NUMERIC",
                text=q_text,
                default_points=Decimal("1.00"),
                difficulty="EASY",
                numeric_answer=numeric,
                numeric_tolerance=Decimal("0"),
                created_by=a.created_by,
            )
            created.append(q)

        # Attach all to the assessment
        for pos, q in enumerate(created, start=1):
            AssessmentQuestion.objects.create(
                assessment=a,
                question=q,
                position=pos,
                points=q.default_points,
            )

        a.recompute_total_points()

        # ── Configure CA exam ────────────────────────────────────
        a.status = "PUBLISHED"
        a.is_code_gated = True
        a.ca_opens_at = now - timedelta(minutes=5)
        a.ca_last_entry_at = now + timedelta(minutes=opts["last_entry_minutes"])
        a.available_from = now - timedelta(minutes=5)
        a.available_until = now + timedelta(hours=opts["duration_hours"])
        a.serve_question_count = None  # serve ALL questions
        a.randomize_question_order = True  # shuffle questions per student
        a.shuffle_options = True  # shuffle options per student
        a.save()

        code = AssessmentAccessService.generate_and_set_code(a)

        # ── Print ────────────────────────────────────────────────
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(self.style.SUCCESS("CA EXAM READY — 30 questions"))
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(f"Assessment:      {a.title}")
        self.stdout.write(f"Total questions: {a.assessment_questions.count()}")
        self.stdout.write(f"Total points:    {a.total_points}")
        self.stdout.write(
            f"Randomize order: YES (each student gets a different sequence)"
        )
        self.stdout.write(
            f"Shuffle options: YES (each student sees options in a different order)"
        )
        self.stdout.write(f"URL:             http://localhost:3000/assessments/{a.id}")
        self.stdout.write("")
        self.stdout.write(
            self.style.WARNING("ACCESS CODE (copy now, never shown again):")
        )
        self.stdout.write(self.style.SUCCESS(f"    {code}"))
        self.stdout.write("")
        self.stdout.write(
            f"Window: {a.ca_opens_at.strftime('%H:%M')} – "
            f"{a.ca_last_entry_at.strftime('%H:%M')} (last entry) · "
            f"Hard close: {a.available_until.strftime('%H:%M')}"
        )
        self.stdout.write(self.style.SUCCESS("=" * 60))
