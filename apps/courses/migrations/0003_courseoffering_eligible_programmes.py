from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("courses", "0002_courseoffering_courseinstructor_courseenrollment_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="courseoffering",
            name="eligible_programmes",
            field=models.ManyToManyField(
                blank=True,
                help_text="Additional programmes approved for this offering.",
                related_name="eligible_course_offerings",
                to="university.programme",
            ),
        ),
    ]
