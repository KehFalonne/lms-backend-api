from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("assessments", "0006_alter_proctoring_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="assessment",
            name="ca_invigilator",
            field=models.ForeignKey(
                blank=True,
                limit_choices_to={"is_staff": True, "is_active": True},
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="ca_sessions_invigilated",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.CreateModel(
            name="CAInvigilatorAction",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("action", models.CharField(
                    choices=[
                        ("MESSAGE", "Message student"),
                        ("PAUSE", "Pause attempt"),
                        ("RESUME", "Resume attempt"),
                        ("FORCE_SUBMIT", "Force submit"),
                        ("TERMINATE", "Terminate attempt"),
                        ("RESET_LOCKDOWN", "Reset lockdown"),
                    ],
                    max_length=30,
                )),
                ("detail", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "actor",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="ca_invigilator_actions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "attempt",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="invigilator_actions",
                        to="assessments.assessmentattempt",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["attempt", "-created_at"], name="assessments_ca_attempt_idx")
                ],
            },
        ),
    ]
