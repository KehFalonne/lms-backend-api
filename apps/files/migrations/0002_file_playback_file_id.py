from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("files", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="file",
            name="playback_file_id",
            field=models.UUIDField(
                blank=True,
                editable=False,
                help_text="Optional browser-compatible playback copy.",
                null=True,
            ),
        )
    ]
