from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("content", "0003_contentitem_transcript"),
    ]

    operations = [
        migrations.AddField(
            model_name="contentitem",
            name="allow_download",
            field=models.BooleanField(
                default=True,
                help_text="Allow students to download attached audio files.",
                verbose_name="allow download",
            ),
        ),
    ]
