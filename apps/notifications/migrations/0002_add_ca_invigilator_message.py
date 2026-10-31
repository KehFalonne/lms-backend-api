from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="notification",
            name="type",
            field=models.CharField(
                choices=[
                    ("ANNOUNCEMENT", "Announcement"),
                    ("ASSIGNMENT", "Assignment"),
                    ("ASSESSMENT", "Assessment"),
                    ("GRADE", "Grade"),
                    ("DISCUSSION", "Discussion"),
                    ("CA_INVIGILATOR_MESSAGE", "CA invigilator message"),
                    ("SYSTEM", "System"),
                ],
                db_index=True,
                default="SYSTEM",
                max_length=30,
                verbose_name="type",
            ),
        ),
    ]
