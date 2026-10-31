from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("files", "0002_file_playback_file_id")]

    operations = [migrations.RemoveField(model_name="file", name="playback_file_id")]
