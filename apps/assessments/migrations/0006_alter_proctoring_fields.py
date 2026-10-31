from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("assessments", "0005_assessment_proctoring_enforcement"),
    ]

    operations = [
        migrations.AlterField(
            model_name="assessment",
            name="proctoring_max_violations",
            field=models.PositiveSmallIntegerField(
                default=0,
                help_text=(
                    "Apply the configured enforcement policy after this many "
                    "violations. 0 = log only, never enforce."
                ),
                verbose_name="max proctoring violations",
            ),
        ),
        migrations.AlterField(
            model_name="assessmentproctoringevent",
            name="event_type",
            field=models.CharField(
                choices=[
                    ("TAB_SWITCH", "Tab switch"),
                    ("WINDOW_BLUR", "Window blur"),
                    ("FULLSCREEN_EXIT", "Fullscreen exit"),
                    ("CONTEXT_MENU", "Context menu"),
                    ("COPY", "Copy"),
                    ("PASTE", "Paste"),
                    ("HEARTBEAT_GAP", "Heartbeat gap"),
                    ("OTHER", "Other"),
                ],
                db_index=True,
                max_length=30,
                verbose_name="event type",
            ),
        ),
    ]
