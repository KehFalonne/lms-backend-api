from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("assessments", "0004_assessment_proctoring_mode_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="assessment",
            name="proctoring_enforcement",
            field=models.CharField(
                choices=[
                    ("REVIEW_ONLY", "Review only"),
                    ("AUTO_SUBMIT", "Automatically submit"),
                ],
                default="REVIEW_ONLY",
                help_text=(
                    "REVIEW_ONLY records violations for lecturer review. "
                    "AUTO_SUBMIT submits the attempt when the threshold is reached."
                ),
                max_length=20,
                verbose_name="proctoring enforcement",
            ),
        ),
    ]
