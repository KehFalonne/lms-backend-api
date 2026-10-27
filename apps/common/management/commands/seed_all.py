"""
Populates the full GU-LMS database with a realistic, deterministic dataset
for local development and frontend work.

Idempotent: safe to run repeatedly.

Usage:
    python manage.py seed_all
    python manage.py seed_all --reset     # wipe seeded data first
"""

from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.academics.models import (
    AcademicYear,
    AcademicYearStatus,
    Semester,
    SemesterStatus,
)
from apps.accounts.models import (
    Role,
    RoleScope,
    StudentProfile,
    StaffProfile,
    UserRole,
    UserStatus,
)
from apps.announcements.models import Announcement, AnnouncementStatus
from apps.assessments.models import (
    Assessment,
    AssessmentQuestion,
    AssessmentStatus,
    AssessmentType,
    Question,
    QuestionBank,
    QuestionOption,
    QuestionType,
)
from apps.assignments.models import (
    Assignment,
    AssignmentStatus,
    SubmissionType,
)
from apps.content.models import ContentItem, ContentType, CourseModule
from apps.courses.models import (
    Course,
    CourseEnrollment,
    CourseInstructor,
    CourseOffering,
    EnrollmentStatus,
    OfferingStatus,
    TeachingRole,
)
from apps.discussions.models import DiscussionForum, DiscussionPost, DiscussionTopic
from apps.grading.models import GradeCategory, GradeItem, GradeSourceType
from apps.university.models import (
    DegreeType,
    Department,
    Faculty,
    Programme,
)

User = get_user_model()


class Command(BaseCommand):
    help = "Seed the entire GU-LMS database for development."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset", action="store_true", help="Delete seeded data before re-seeding."
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["reset"]:
            self._reset()
            self.stdout.write(self.style.WARNING("Existing seed data deleted."))

        self._seed_roles()
        self._seed_users()
        self._seed_university()
        self._seed_academic_year()
        self._seed_courses()
        self._seed_offering()
        self._seed_instructors_and_enrollments()
        self._seed_course_content()
        self._seed_assignments()
        self._seed_assessment()
        self._seed_gradebook()
        self._seed_announcements()
        self._seed_discussions()

        self._print_summary()

    # ────────────────────────────────────────────────────────────────

    def _reset(self):
        from apps.assignments.models import AssignmentSubmission
        from apps.assessments.models import AssessmentAttempt
        from apps.courses.models import CoursePrerequisite
        from apps.grading.models import Grade, GradeHistory

        # Content / interactions
        AssignmentSubmission.objects.all().delete()
        AssessmentAttempt.objects.all().delete()
        GradeHistory.objects.all().delete()
        Grade.objects.all().delete()
        GradeItem.objects.all().delete()
        GradeCategory.objects.all().delete()
        Announcement.objects.all().delete()
        DiscussionPost.objects.all().delete()
        DiscussionTopic.objects.all().delete()
        DiscussionForum.objects.all().delete()
        Assignment.objects.all().delete()

        # Assessments
        AssessmentQuestion.objects.all().delete()
        Assessment.objects.all().delete()
        QuestionOption.objects.all().delete()
        Question.objects.all().delete()
        QuestionBank.objects.all().delete()

        # Content
        ContentItem.objects.all().delete()
        CourseModule.objects.all().delete()

        # Course relationships (delete before Course — PROTECT FKs)
        CourseEnrollment.objects.all().delete()
        CourseInstructor.objects.all().delete()
        CoursePrerequisite.objects.all().delete()  # ← FIX
        CourseOffering.objects.all().delete()
        Course.objects.all().delete()

        # University structure
        Programme.objects.all().delete()
        Department.objects.all().delete()
        Faculty.objects.all().delete()
        AcademicYear.objects.all().delete()

        # Users (profiles cascade)
        User.objects.filter(
            email__in=[
                "admin@graciousuniversity.edu",
                "lecturer@graciousuniversity.edu",
                "lecturer2@graciousuniversity.edu",
                "student@graciousuniversity.edu",
                "student2@graciousuniversity.edu",
                "student3@graciousuniversity.edu",
            ]
        ).delete()

    # ── RBAC ────────────────────────────────────────────────────────

    def _seed_roles(self):
        from django.core.management import call_command

        call_command("seed_rbac", verbosity=0)
        self.stdout.write(self.style.SUCCESS("  ✓ RBAC roles & permissions"))

    # ── Users ───────────────────────────────────────────────────────

    def _seed_users(self):
        self._admin = User.objects.create_user(
            email="admin@graciousuniversity.edu",
            university_id="GU0001",
            password="Admin1234!",
            first_name="Super",
            last_name="Admin",
            status=UserStatus.ACTIVE,
        )
        self._admin.is_staff = True
        self._admin.is_superuser = True
        self._admin.save(update_fields=["is_staff", "is_superuser"])

        self._lecturer = self._make_user(
            email="lecturer@graciousuniversity.edu",
            university_id="GU0002",
            password="Lecturer1234!",
            first_name="Jane",
            last_name="Smith",
            staff_number="GU-STAFF-0001",
            job_title="Senior Lecturer",
        )
        self._lecturer2 = self._make_user(
            email="lecturer2@graciousuniversity.edu",
            university_id="GU0003",
            password="Lecturer1234!",
            first_name="David",
            last_name="Okafor",
            staff_number="GU-STAFF-0002",
            job_title="Lecturer",
        )

        self._student = self._make_student(
            email="student@graciousuniversity.edu",
            university_id="GU2026001",
            matricule="GU-2026-001234",
            first_name="John",
            last_name="Doe",
        )
        self._student2 = self._make_student(
            email="student2@graciousuniversity.edu",
            university_id="GU2026002",
            matricule="GU-2026-001235",
            first_name="Mary",
            last_name="Learner",
        )
        self._student3 = self._make_student(
            email="student3@graciousuniversity.edu",
            university_id="GU2026003",
            matricule="GU-2026-001236",
            first_name="Peter",
            last_name="Njoya",
        )

        self.stdout.write(
            self.style.SUCCESS("  ✓ Users (1 admin, 2 lecturers, 3 students)")
        )

    def _make_user(
        self,
        *,
        email,
        university_id,
        password,
        first_name,
        last_name,
        staff_number,
        job_title,
    ):
        u = User.objects.create_user(
            email=email,
            university_id=university_id,
            password=password,
            first_name=first_name,
            last_name=last_name,
            status=UserStatus.ACTIVE,
        )
        StaffProfile.objects.create(
            user=u, staff_number=staff_number, job_title=job_title
        )
        for code in ("LECTURER",):
            role = Role.objects.filter(code=code).first()
            if role:
                UserRole.objects.get_or_create(
                    user=u,
                    role=role,
                    scope_type=RoleScope.GLOBAL,
                    faculty=None,
                    department=None,
                    course_offering_id=None,
                )
        return u

    def _make_student(self, *, email, university_id, matricule, first_name, last_name):
        u = User.objects.create_user(
            email=email,
            university_id=university_id,
            password="Student1234!",
            first_name=first_name,
            last_name=last_name,
            status=UserStatus.ACTIVE,
        )
        StudentProfile.objects.create(
            user=u,
            matricule_number=matricule,
            current_level=300,
            admission_year=2024,
        )
        role = Role.objects.filter(code="STUDENT").first()
        if role:
            UserRole.objects.get_or_create(
                user=u,
                role=role,
                scope_type=RoleScope.GLOBAL,
                faculty=None,
                department=None,
                course_offering_id=None,
            )
        return u

    # ── University ──────────────────────────────────────────────────

    def _seed_university(self):
        self._faculty = Faculty.objects.create(
            code="FOC",
            name="Faculty of Computing",
            status="ACTIVE",
        )
        self._dept = Department.objects.create(
            faculty=self._faculty,
            code="CS",
            name="Computer Science",
            status="ACTIVE",
        )
        self._dept_se = Department.objects.create(
            faculty=self._faculty,
            code="SE",
            name="Software Engineering",
            status="ACTIVE",
        )
        self._programme = Programme.objects.create(
            department=self._dept,
            code="BSC-CS",
            name="BSc Computer Science",
            degree_type=DegreeType.BSC,
            duration_years=4,
            status="ACTIVE",
        )
        self._programme_se = Programme.objects.create(
            department=self._dept_se,
            code="BSC-SE",
            name="BSc Software Engineering",
            degree_type=DegreeType.BSC,
            duration_years=4,
            status="ACTIVE",
        )
        self.stdout.write(self.style.SUCCESS("  ✓ University structure"))

    # ── Academic year ───────────────────────────────────────────────

    def _seed_academic_year(self):
        self._year = AcademicYear.objects.create(
            name="2026/2027",
            start_date=date(2026, 9, 1),
            end_date=date(2027, 7, 31),
            status=AcademicYearStatus.ACTIVE,
            is_current=True,
        )
        self._semester = Semester.objects.create(
            academic_year=self._year,
            name="Semester 1",
            code="S1",
            sequence=1,
            start_date=date(2026, 9, 1),
            end_date=date(2027, 1, 31),
            status=SemesterStatus.ACTIVE,
            is_current=True,
        )
        self.stdout.write(
            self.style.SUCCESS("  ✓ Academic year 2026/2027 + Semester 1")
        )

    # ── Courses ─────────────────────────────────────────────────────

    def _seed_courses(self):
        self._courses = {}
        for code, title, level, credits in [
            ("CSC101", "Introduction to Computing", 100, 3),
            ("CSC201", "Data Structures", 200, 3),
            ("CSC301", "Database Systems", 300, 3),
            ("CSC401", "Advanced Database Systems", 400, 3),
        ]:
            self._courses[code] = Course.objects.create(
                department=self._dept,
                code=code,
                title=title,
                credits=credits,
                level=level,
                status="ACTIVE",
            )
        self.stdout.write(self.style.SUCCESS("  ✓ Courses (4)"))

    # ── Course offering ─────────────────────────────────────────────

    def _seed_offering(self):
        self._offering = CourseOffering.objects.create(
            course=self._courses["CSC301"],
            semester=self._semester,
            programme=self._programme,
            section="A",
            capacity=50,
            status=OfferingStatus.ACTIVE,
            published_at=timezone.now(),
        )
        self.stdout.write(
            self.style.SUCCESS("  ✓ Course offering: CSC301 (Semester 1)")
        )

    # ── Instructors & enrollments ───────────────────────────────────

    def _seed_instructors_and_enrollments(self):
        CourseInstructor.objects.create(
            course_offering=self._offering,
            user=self._lecturer,
            teaching_role=TeachingRole.PRIMARY_INSTRUCTOR,
            can_manage_content=True,
            can_grade=True,
            can_manage_assessments=True,
            can_manage_students=True,
            assigned_by=self._admin,
        )
        for student in (self._student, self._student2, self._student3):
            CourseEnrollment.objects.create(
                course_offering=self._offering,
                student=student,
                status=EnrollmentStatus.ACTIVE,
            )
        self.stdout.write(
            self.style.SUCCESS("  ✓ 1 primary instructor + 3 enrollments")
        )

    # ── Content ─────────────────────────────────────────────────────

    def _seed_course_content(self):
        modules = [
            (
                "Introduction to Databases",
                [
                    (
                        "Welcome and Syllabus",
                        ContentType.TEXT,
                        "Introduction to CSC301.",
                    ),
                    ("Database Fundamentals", ContentType.TEXT, "What is a database?"),
                    ("Week 1 Slides", ContentType.PDF, ""),
                ],
            ),
            (
                "Relational Model",
                [
                    ("Tables and Relations", ContentType.TEXT, "How relations work."),
                    ("Normalization", ContentType.VIDEO, ""),
                ],
            ),
            (
                "SQL",
                [
                    ("SELECT Basics", ContentType.TEXT, "SELECT queries."),
                    ("Joins", ContentType.TEXT, "INNER, LEFT, RIGHT, FULL."),
                ],
            ),
        ]
        for pos, (title, items) in enumerate(modules, start=1):
            module = CourseModule.objects.create(
                course_offering=self._offering,
                title=title,
                description=f"Module {pos}",
                position=pos,
                is_published=True,
                created_by=self._lecturer,
            )
            for ipos, (i_title, i_type, i_body) in enumerate(items, start=1):
                ContentItem.objects.create(
                    course_module=module,
                    title=i_title,
                    content_type=i_type,
                    body=i_body,
                    position=ipos,
                    is_required=(ipos == 1),
                    is_published=True,
                    created_by=self._lecturer,
                )
        self.stdout.write(self.style.SUCCESS("  ✓ Course content (3 modules, 7 items)"))

    # ── Assignments ─────────────────────────────────────────────────

    def _seed_assignments(self):
        Assignment.objects.create(
            course_offering=self._offering,
            title="ER Diagram Design",
            description="Design an ER diagram for a library system.",
            instructions="Submit a PDF of your ER diagram.",
            max_score=20,
            due_at=timezone.now() + timedelta(days=7),
            submission_type=SubmissionType.FILE_UPLOAD,
            status=AssignmentStatus.PUBLISHED,
            created_by=self._lecturer,
            published_at=timezone.now(),
        )
        Assignment.objects.create(
            course_offering=self._offering,
            title="SQL Query Practice",
            description="Write 10 SQL queries.",
            instructions="Text submission with your queries.",
            max_score=10,
            due_at=timezone.now() + timedelta(days=14),
            submission_type=SubmissionType.TEXT_ENTRY,
            status=AssignmentStatus.PUBLISHED,
            created_by=self._lecturer,
            published_at=timezone.now(),
        )
        self.stdout.write(self.style.SUCCESS("  ✓ Assignments (2)"))

    # ── Assessment ──────────────────────────────────────────────────

    def _seed_assessment(self):
        bank = QuestionBank.objects.create(
            course=self._courses["CSC301"],
            title="CSC301 — Question Bank",
            description="Bank for database systems quizzes.",
            owner=self._lecturer,
            visibility="PRIVATE",
        )

        # MCQ
        q1 = Question.objects.create(
            question_bank=bank,
            question_type=QuestionType.MULTIPLE_CHOICE,
            text="What does SQL stand for?",
            default_points=Decimal("2.00"),
            difficulty="EASY",
            created_by=self._lecturer,
        )
        for i, (t, ok) in enumerate(
            [
                ("Structured Query Language", True),
                ("Simple Query Language", False),
                ("Standard Query Language", False),
                ("None of the above", False),
            ],
            start=1,
        ):
            QuestionOption.objects.create(
                question=q1, text=t, is_correct=ok, position=i
            )

        # True/False
        q2 = Question.objects.create(
            question_bank=bank,
            question_type=QuestionType.TRUE_FALSE,
            text="A primary key can be NULL.",
            default_points=Decimal("2.00"),
            difficulty="EASY",
            created_by=self._lecturer,
        )
        QuestionOption.objects.create(
            question=q2, text="True", is_correct=False, position=1
        )
        QuestionOption.objects.create(
            question=q2, text="False", is_correct=True, position=2
        )

        # Short answer
        q3 = Question.objects.create(
            question_bank=bank,
            question_type=QuestionType.SHORT_ANSWER,
            text="Which SQL keyword removes duplicate rows?",
            default_points=Decimal("2.00"),
            difficulty="MEDIUM",
            answer_key=["DISTINCT", "distinct"],
            created_by=self._lecturer,
        )

        # Assessment
        self._assessment = Assessment.objects.create(
            course_offering=self._offering,
            title="CSC301 Midterm Quiz",
            description="Covers Modules 1 and 2.",
            instructions="Answer all questions. Time limit 30 minutes.",
            assessment_type=AssessmentType.QUIZ,
            available_from=timezone.now() - timedelta(hours=1),
            available_until=timezone.now() + timedelta(days=7),
            time_limit_minutes=30,
            max_attempts=1,
            passing_score=Decimal("50.00"),
            status=AssessmentStatus.PUBLISHED,
            created_by=self._lecturer,
            published_at=timezone.now(),
        )
        for pos, q in enumerate([q1, q2, q3], start=1):
            AssessmentQuestion.objects.create(
                assessment=self._assessment,
                question=q,
                position=pos,
                points=q.default_points,
            )
        self._assessment.recompute_total_points()

        self.stdout.write(
            self.style.SUCCESS("  ✓ Assessment: CSC301 Midterm Quiz (3 questions)")
        )

    # ── Gradebook ───────────────────────────────────────────────────

    def _seed_gradebook(self):
        cat_a = GradeCategory.objects.create(
            course_offering=self._offering,
            name="Assignments",
            weight=Decimal("40.00"),
            position=1,
        )
        cat_q = GradeCategory.objects.create(
            course_offering=self._offering,
            name="Quizzes",
            weight=Decimal("20.00"),
            position=2,
        )
        cat_f = GradeCategory.objects.create(
            course_offering=self._offering,
            name="Final Exam",
            weight=Decimal("40.00"),
            position=3,
        )
        GradeItem.objects.create(
            course_offering=self._offering,
            category=cat_a,
            name="ER Diagram Design",
            max_score=20,
            position=1,
            source_type=GradeSourceType.MANUAL,
        )
        GradeItem.objects.create(
            course_offering=self._offering,
            category=cat_a,
            name="SQL Query Practice",
            max_score=10,
            position=2,
            source_type=GradeSourceType.MANUAL,
        )
        GradeItem.objects.create(
            course_offering=self._offering,
            category=cat_q,
            name="Midterm Quiz",
            max_score=6,
            position=1,
            source_type=GradeSourceType.ASSESSMENT,
            source_id=self._assessment.id,
        )
        GradeItem.objects.create(
            course_offering=self._offering,
            category=cat_f,
            name="Final Exam",
            max_score=100,
            position=1,
            source_type=GradeSourceType.MANUAL,
        )
        self.stdout.write(
            self.style.SUCCESS(
                "  ✓ Gradebook (3 categories, 4 items — weights sum to 100%)"
            )
        )

    # ── Announcements ───────────────────────────────────────────────

    def _seed_announcements(self):
        Announcement.objects.create(
            course_offering=self._offering,
            title="Welcome to CSC301",
            body="Please review the syllabus and complete the intro assignment.",
            is_pinned=True,
            status=AnnouncementStatus.PUBLISHED,
            publish_at=timezone.now(),
            created_by=self._lecturer,
        )
        Announcement.objects.create(
            course_offering=self._offering,
            title="Midterm Quiz opens Monday",
            body="The midterm quiz will be available on Monday. Read Modules 1 and 2.",
            status=AnnouncementStatus.PUBLISHED,
            publish_at=timezone.now(),
            created_by=self._lecturer,
        )
        self.stdout.write(self.style.SUCCESS("  ✓ Announcements (2)"))

    # ── Discussions ─────────────────────────────────────────────────

    def _seed_discussions(self):
        forum = DiscussionForum.objects.create(
            course_offering=self._offering,
            title="General Q&A",
            description="Ask anything about the course.",
            created_by=self._lecturer,
        )
        topic = DiscussionTopic.objects.create(
            forum=forum,
            title="Welcome thread",
            body="Introduce yourself!",
            is_pinned=True,
            created_by=self._lecturer,
        )
        DiscussionPost.objects.create(
            topic=topic,
            author=self._student,
            body="Hi everyone, I'm John. Excited for this course.",
        )
        DiscussionPost.objects.create(
            topic=topic,
            author=self._student2,
            body="Hello! Mary here, looking forward to learning SQL.",
        )
        self.stdout.write(
            self.style.SUCCESS("  ✓ Discussion forum with welcome thread")
        )

    # ── Summary ─────────────────────────────────────────────────────

    def _print_summary(self):
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Seed complete. Credentials:"))
        self.stdout.write("")
        self.stdout.write("  SUPERUSER  admin@graciousuniversity.edu       Admin1234!")
        self.stdout.write(
            "  LECTURER   lecturer@graciousuniversity.edu    Lecturer1234!"
        )
        self.stdout.write(
            "  LECTURER   lecturer2@graciousuniversity.edu   Lecturer1234!"
        )
        self.stdout.write(
            "  STUDENT    student@graciousuniversity.edu     Student1234!"
        )
        self.stdout.write(
            "  STUDENT    student2@graciousuniversity.edu    Student1234!"
        )
        self.stdout.write(
            "  STUDENT    student3@graciousuniversity.edu    Student1234!"
        )
        self.stdout.write("")
