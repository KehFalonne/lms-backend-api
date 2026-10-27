"""
Deterministic academic structure for development (database doc §75).

Creates:
    Faculty of Computing (FOC)
        → Computer Science (CS)
            → BSc Computer Science (BSC-CS)
            → BSc Software Engineering (BSC-SE)
    Faculty of Science (FOS)
        → Mathematics (MATH)
            → BSc Mathematics (BSC-MATH)

    Academic Year 2026/2027 (current)
        → Semester 1 (current)
        → Semester 2

    Courses: CSC101, CSC201, CSC301, CSC401

Usage:
    python manage.py seed_academic_structure
    python manage.py seed_academic_structure --reset
"""

from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.academics.models import (
    AcademicYear,
    AcademicYearStatus,
    Semester,
    SemesterStatus,
)
from apps.courses.models import Course
from apps.university.models import Department, DegreeType, Faculty, Programme

FACULTIES = [
    {"code": "FOC", "name": "Faculty of Computing", "description": "Computing & IT."},
    {"code": "FOS", "name": "Faculty of Science", "description": "Natural sciences."},
]

DEPARTMENTS = [
    {"faculty": "FOC", "code": "CS", "name": "Computer Science"},
    {"faculty": "FOC", "code": "SE", "name": "Software Engineering"},
    {"faculty": "FOS", "code": "MATH", "name": "Mathematics"},
]

PROGRAMMES = [
    {
        "dept": "CS",
        "code": "BSC-CS",
        "name": "BSc Computer Science",
        "degree": DegreeType.BSC,
        "years": 4,
    },
    {
        "dept": "SE",
        "code": "BSC-SE",
        "name": "BSc Software Engineering",
        "degree": DegreeType.BSC,
        "years": 4,
    },
    {
        "dept": "MATH",
        "code": "BSC-MATH",
        "name": "BSc Mathematics",
        "degree": DegreeType.BSC,
        "years": 4,
    },
]

COURSES = [
    {
        "dept": "CS",
        "code": "CSC101",
        "title": "Introduction to Computing",
        "credits": 3,
        "level": 100,
    },
    {
        "dept": "CS",
        "code": "CSC201",
        "title": "Data Structures",
        "credits": 3,
        "level": 200,
    },
    {
        "dept": "CS",
        "code": "CSC301",
        "title": "Database Systems",
        "credits": 3,
        "level": 300,
    },
    {
        "dept": "CS",
        "code": "CSC401",
        "title": "Advanced Database Systems",
        "credits": 3,
        "level": 400,
    },
]


class Command(BaseCommand):
    help = "Seed academic structure: faculties, departments, programmes, years, semesters, courses."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing seeded academic structure first.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["reset"]:
            Course.objects.filter(code__in=[c["code"] for c in COURSES]).delete()
            Programme.objects.filter(code__in=[p["code"] for p in PROGRAMMES]).delete()
            Department.objects.filter(
                code__in=[d["code"] for d in DEPARTMENTS]
            ).delete()
            Faculty.objects.filter(code__in=[f["code"] for f in FACULTIES]).delete()
            AcademicYear.objects.filter(name="2026/2027").delete()
            self.stdout.write(self.style.WARNING("Existing seed data deleted."))

        # Faculties
        faculty_map = {}
        for f in FACULTIES:
            obj, _ = Faculty.objects.update_or_create(
                code=f["code"],
                defaults={
                    "name": f["name"],
                    "description": f.get("description", ""),
                },
            )
            faculty_map[obj.code] = obj
        self.stdout.write(self.style.SUCCESS(f"  ✓ Faculties: {len(faculty_map)}"))

        # Departments
        dept_map = {}
        for d in DEPARTMENTS:
            obj, _ = Department.objects.update_or_create(
                faculty=faculty_map[d["faculty"]],
                code=d["code"],
                defaults={"name": d["name"]},
            )
            dept_map[obj.code] = obj
        self.stdout.write(self.style.SUCCESS(f"  ✓ Departments: {len(dept_map)}"))

        # Programmes
        prog_map = {}
        for p in PROGRAMMES:
            obj, _ = Programme.objects.update_or_create(
                department=dept_map[p["dept"]],
                code=p["code"],
                defaults={
                    "name": p["name"],
                    "degree_type": p["degree"],
                    "duration_years": p["years"],
                },
            )
            prog_map[obj.code] = obj
        self.stdout.write(self.style.SUCCESS(f"  ✓ Programmes: {len(prog_map)}"))

        # Academic Year 2026/2027
        year, _ = AcademicYear.objects.update_or_create(
            name="2026/2027",
            defaults={
                "start_date": date(2026, 9, 1),
                "end_date": date(2027, 7, 31),
                "status": AcademicYearStatus.ACTIVE,
                "is_current": True,
            },
        )
        self.stdout.write(self.style.SUCCESS(f"  ✓ Academic year: {year.name}"))

        # Semesters
        s1, _ = Semester.objects.update_or_create(
            academic_year=year,
            code="S1",
            defaults={
                "name": "Semester 1",
                "sequence": 1,
                "start_date": date(2026, 9, 1),
                "end_date": date(2027, 1, 31),
                "status": SemesterStatus.ACTIVE,
                "is_current": True,
            },
        )
        s2, _ = Semester.objects.update_or_create(
            academic_year=year,
            code="S2",
            defaults={
                "name": "Semester 2",
                "sequence": 2,
                "start_date": date(2027, 2, 1),
                "end_date": date(2027, 7, 31),
                "status": SemesterStatus.UPCOMING,
                "is_current": False,
            },
        )
        self.stdout.write(self.style.SUCCESS(f"  ✓ Semesters: {s1.name}, {s2.name}"))

        # Courses
        for c in COURSES:
            Course.objects.update_or_create(
                department=dept_map[c["dept"]],
                code=c["code"],
                defaults={
                    "title": c["title"],
                    "credits": c["credits"],
                    "level": c["level"],
                },
            )
        self.stdout.write(self.style.SUCCESS(f"  ✓ Courses: {len(COURSES)}"))

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Academic structure seeded."))
