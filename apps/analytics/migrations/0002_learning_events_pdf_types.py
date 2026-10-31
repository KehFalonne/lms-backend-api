from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("analytics", "0001_initial")]

    operations = [
        migrations.AlterField(
            model_name="learningevent",
            name="event_type",
            field=models.CharField(
                choices=[
                    ("COURSE_VIEWED", "Course viewed"),
                    ("MODULE_VIEWED", "Module viewed"),
                    ("CONTENT_VIEWED", "Content viewed"),
                    ("CONTENT_COMPLETED", "Content completed"),
                    ("PDF_OPENED", "PDF opened"),
                    ("PDF_DOWNLOADED", "PDF downloaded"),
                    ("ASSIGNMENT_OPENED", "Assignment opened"),
                    ("ASSIGNMENT_SUBMITTED", "Assignment submitted"),
                    ("ASSESSMENT_STARTED", "Assessment started"),
                    ("ASSESSMENT_SUBMITTED", "Assessment submitted"),
                    ("DISCUSSION_VIEWED", "Discussion viewed"),
                    ("LOGIN", "Login"),
                ],
                db_index=True,
                max_length=40,
                verbose_name="event type",
            ),
        )
    ]
