from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("content", "0002_contentitemversion"),
    ]

    operations = [
        migrations.AddField(
            model_name="contentitem",
            name="transcript",
            field=models.TextField(blank=True, verbose_name="audio transcript"),
        ),
    ]
