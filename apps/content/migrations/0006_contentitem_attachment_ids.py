from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("content", "0005_contentitem_chapters")]

    operations = [
        migrations.AddField(
            model_name="contentitem",
            name="attachment_ids",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Ready file IDs attached to the lesson.",
                verbose_name="attachment files",
            ),
        )
    ]
