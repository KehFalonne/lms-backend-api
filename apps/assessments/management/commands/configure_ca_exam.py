"""
Configure an assessment as a live CA exam with a generated access code.

Usage:
    python manage.py configure_ca_exam
    python manage.py configure_ca_exam --assessment-id <uuid>
    python manage.py configure_ca_exam --title "Midterm"
    python manage.py configure_ca_exam --duration-hours 4
    python manage.py configure_ca_exam --serve 2 --randomize
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.assessments.models import Assessment
from apps.assessments.services.access_service import AssessmentAccessService


class Command(BaseCommand):
    help = "Configure a CA exam and generate a fresh access code."

    def add_arguments(self, parser):
        parser.add_argument(
            "--assessment-id",
            type=str,
            default=None,
            help="Exact assessment UUID. Otherwise the first published quiz is picked.",
        )
        parser.add_argument(
            "--title",
            type=str,
            default=None,
            help="Substring to match the assessment title (case-insensitive).",
        )
        parser.add_argument(
            "--duration-hours",
            type=float,
            default=4.0,
            help="Total window length from now (default 4 hours).",
        )
        parser.add_argument(
            "--entry-grace-minutes",
            type=int,
            default=180,
            help="Minutes from now that late entry is allowed (default 180).",
        )
        parser.add_argument(
            "--serve",
            type=int,
            default=None,
            help="Number of questions to serve per student (optional).",
        )
        parser.add_argument(
            "--randomize",
            action="store_true",
            help="Randomize question order per student.",
        )

    def handle(self, *args, **opts):
        now = timezone.now()

        # Find the assessment
        a = None
        if opts["assessment_id"]:
            a = Assessment.objects.filter(pk=opts["assessment_id"]).first()
        elif opts["title"]:
            a = (
                Assessment.objects.filter(title__icontains=opts["title"])
                .order_by("-created_at")
                .first()
            )
        else:
            a = (
                Assessment.objects.filter(
                    assessment_type="QUIZ",
                    assessment_questions__isnull=False,
                )
                .distinct()
                .order_by("-created_at")
                .first()
            )
            if not a:
                a = Assessment.objects.filter(
                    assessment_questions__isnull=False
                ).first()

        if not a:
            self.stderr.write(
                self.style.ERROR(
                    "No assessment with questions found. Create one first."
                )
            )
            return

        q_count = a.assessment_questions.count()

        # Configure the window
        a.status = "PUBLISHED"
        a.is_code_gated = True
        a.ca_opens_at = now - timedelta(minutes=5)
        a.ca_last_entry_at = now + timedelta(minutes=opts["entry_grace_minutes"])
        a.available_from = now - timedelta(minutes=5)
        a.available_until = now + timedelta(hours=opts["duration_hours"])
        if opts["serve"] is not None:
            a.serve_question_count = opts["serve"]
        if opts["randomize"]:
            a.randomize_question_order = True
        a.save()

        # Generate code
        code = AssessmentAccessService.generate_and_set_code(a)

        # Print
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(self.style.SUCCESS("CA EXAM IS LIVE"))
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(f"Assessment:   {a.title}")
        self.stdout.write(f"Questions:    {q_count}")
        self.stdout.write(f"URL:          http://localhost:3000/assessments/{a.id}")
        self.stdout.write("")
        self.stdout.write(
            self.style.WARNING("ACCESS CODE (copy now, never shown again):")
        )
        self.stdout.write(self.style.SUCCESS(f"    {code}"))
        self.stdout.write("")
        self.stdout.write("Window:")
        self.stdout.write(f"  Opens:      {a.ca_opens_at.strftime('%Y-%m-%d %H:%M')}")
        self.stdout.write(
            f"  Last entry: {a.ca_last_entry_at.strftime('%Y-%m-%d %H:%M')}"
        )
        self.stdout.write(
            f"  Hard close: {a.available_until.strftime('%Y-%m-%d %H:%M')}"
        )
        if opts["serve"]:
            self.stdout.write(f"  Serve:      {opts['serve']} questions per student")
        if opts["randomize"]:
            self.stdout.write("  Randomize:  yes")
        self.stdout.write(self.style.SUCCESS("=" * 60))
