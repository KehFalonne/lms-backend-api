"""
Seed a broad course catalog and active programme offerings for development.

The command is idempotent: running it repeatedly updates the same deterministic
courses and offerings instead of creating duplicates.

Usage:
    python manage.py seed_course_catalog
    python manage.py seed_course_catalog --courses-per-department 20
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.academics.models import Semester
from apps.courses.models import Course, CourseOffering, OfferingStatus
from apps.university.models import Department, Programme


REAL_COURSES = {
    "CS": [
        ("CSC101", "Introduction to Computer Science", 100, 3),
        ("CSC102", "Computer Programming I", 100, 3),
        ("CSC103", "Discrete Mathematics", 100, 3),
        ("CSC104", "Computer Systems Fundamentals", 100, 3),
        ("CSC201", "Data Structures and Algorithms", 200, 3),
        ("CSC202", "Object-Oriented Programming", 200, 3),
        ("CSC203", "Computer Organization", 200, 3),
        ("CSC204", "Database Systems", 200, 3),
        ("CSC301", "Operating Systems", 300, 3),
        ("CSC302", "Computer Networks", 300, 3),
        ("CSC303", "Software Engineering", 300, 3),
        ("CSC304", "Web Application Development", 300, 3),
        ("CSC401", "Artificial Intelligence", 400, 3),
        ("CSC402", "Compiler Construction", 400, 3),
        ("CSC403", "Information Security", 400, 3),
        ("CSC404", "Distributed Systems", 400, 3),
        ("CSC501", "Machine Learning", 500, 3),
        ("CSC502", "Data Mining", 500, 3),
        ("CSC503", "Cloud Computing", 500, 3),
        ("CSC504", "Computer Science Project", 500, 6),
    ],
    "SE": [
        ("SWE101", "Introduction to Software Engineering", 100, 3),
        ("SWE102", "Programming Fundamentals", 100, 3),
        ("SWE103", "Discrete Structures for Computing", 100, 3),
        ("SWE104", "Human-Computer Interaction", 100, 3),
        ("SWE201", "Data Structures for Software Engineers", 200, 3),
        ("SWE202", "Object-Oriented Design", 200, 3),
        ("SWE203", "Requirements Engineering", 200, 3),
        ("SWE204", "Software Construction", 200, 3),
        ("SWE301", "Software Architecture", 300, 3),
        ("SWE302", "Database Application Development", 300, 3),
        ("SWE303", "Software Testing and Quality Assurance", 300, 3),
        ("SWE304", "Agile Methods and DevOps", 300, 3),
        ("SWE401", "Secure Software Engineering", 400, 3),
        ("SWE402", "Distributed Software Systems", 400, 3),
        ("SWE403", "Mobile Application Development", 400, 3),
        ("SWE404", "Software Project Management", 400, 3),
        ("SWE501", "Cloud-Native Application Engineering", 500, 3),
        ("SWE502", "Software Maintenance and Evolution", 500, 3),
        ("SWE503", "Enterprise Systems Engineering", 500, 3),
        ("SWE504", "Software Engineering Project", 500, 6),
    ],
    "MATH": [
        ("MTH101", "Algebra and Trigonometry", 100, 3),
        ("MTH102", "Calculus I", 100, 3),
        ("MTH103", "Analytic Geometry", 100, 3),
        ("MTH104", "Introduction to Probability", 100, 3),
        ("MTH201", "Calculus II", 200, 3),
        ("MTH202", "Linear Algebra", 200, 3),
        ("MTH203", "Differential Equations", 200, 3),
        ("MTH204", "Numerical Methods", 200, 3),
        ("MTH301", "Real Analysis", 300, 3),
        ("MTH302", "Abstract Algebra", 300, 3),
        ("MTH303", "Mathematical Statistics", 300, 3),
        ("MTH304", "Operations Research", 300, 3),
        ("MTH401", "Complex Analysis", 400, 3),
        ("MTH402", "Topology", 400, 3),
        ("MTH403", "Measure and Integration", 400, 3),
        ("MTH404", "Stochastic Processes", 400, 3),
        ("MTH501", "Functional Analysis", 500, 3),
        ("MTH502", "Advanced Mathematical Statistics", 500, 3),
        ("MTH503", "Mathematical Modelling", 500, 3),
        ("MTH504", "Mathematics Project", 500, 6),
    ],
}


class Command(BaseCommand):
    help = "Seed 20 courses per department and active offerings for every programme."

    def add_arguments(self, parser):
        parser.add_argument(
            "--courses-per-department",
            type=int,
            default=20,
            help="Number of deterministic courses to create per department.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        count = options["courses_per_department"]
        if count < 1:
            self.stderr.write(self.style.ERROR("The course count must be at least 1."))
            return

        try:
            semester = Semester.objects.get(is_current=True)
        except Semester.DoesNotExist:
            self.stderr.write(
                self.style.ERROR(
                    "No current semester found. Run seed_academic_structure first."
                )
            )
            return

        departments = list(
            Department.objects.filter(
                status="ACTIVE", deleted_at__isnull=True
            ).order_by("code")
        )
        programmes = list(
            Programme.objects.filter(
                status="ACTIVE", deleted_at__isnull=True
            ).select_related("department")
        )

        if not departments:
            self.stderr.write(
                self.style.ERROR("No active departments found. Seed the academic structure first.")
            )
            return
        if not programmes:
            self.stderr.write(
                self.style.ERROR("No active programmes found. Seed the academic structure first.")
            )
            return

        courses_by_department = {}
        total_courses = 0
        total_offerings = 0
        archived_legacy_offerings = 0

        for department in departments:
            subject = department.name.removeprefix("Department of ").strip()
            prefix = "".join(
                character for character in department.code.upper() if character.isalnum()
            )[:8]
            courses = []

            for index in range(count):
                catalog = REAL_COURSES.get(department.code.upper())
                if catalog and index < len(catalog):
                    code, title, level, credits = catalog[index]
                else:
                    level = 100 + ((index // 4) * 100)
                    credits = 3
                    title = f"Specialized {subject} Course {index + 1}"
                    code = f"{prefix}{index + 1:03d}"

                course, _ = Course.objects.update_or_create(
                    department=department,
                    code=code,
                    defaults={
                        "title": title,
                        "description": f"{title} for {department.name}.",
                        "credits": credits,
                        "level": min(level, 700),
                        "course_type": "CORE" if index % 4 else "ELECTIVE",
                        "status": "ACTIVE",
                        "deleted_at": None,
                    },
                )
                courses.append(course)
                total_courses += 1

            courses_by_department[department.id] = courses

            # The initial version of this command generated placeholder codes
            # such as CS001 and SE001. Keep their history, but remove them
            # from student registration after the real catalog is seeded.
            if department.code.upper() in REAL_COURSES:
                legacy_codes = [
                    f"{prefix}{index:03d}" for index in range(1, count + 1)
                ]
                archived_legacy_offerings += CourseOffering.objects.filter(
                    course__department=department,
                    course__code__in=legacy_codes,
                ).exclude(status=OfferingStatus.ARCHIVED).update(
                    status=OfferingStatus.ARCHIVED
                )
                Course.objects.filter(
                    department=department, code__in=legacy_codes
                ).exclude(code__in=[course[0] for course in REAL_COURSES[department.code.upper()]]).update(
                    status="ARCHIVED"
                )

        for programme in programmes:
            for course in courses_by_department.get(programme.department_id, []):
                offering, created = CourseOffering.objects.update_or_create(
                    course=course,
                    semester=semester,
                    programme=programme,
                    section="A",
                    defaults={
                        "capacity": 100,
                        "status": OfferingStatus.ACTIVE,
                        "published_at": timezone.now(),
                    },
                )
                if created:
                    total_offerings += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {total_courses} courses across {len(departments)} departments."
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Created {total_offerings} new active offerings across "
                f"{len(programmes)} programmes for {semester.name}."
            )
        )
        if archived_legacy_offerings:
            self.stdout.write(
                self.style.WARNING(
                    f"Archived {archived_legacy_offerings} placeholder offerings."
                )
            )
