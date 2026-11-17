from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0004_remove_staffprofile_department_id_and_more"),
        ("files", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="avatar_file",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="avatar_users",
                to="files.file",
                verbose_name="avatar file",
            ),
        ),
    ]
