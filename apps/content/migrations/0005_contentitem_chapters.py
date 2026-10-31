from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("content", "0004_contentitem_allow_download"),
    ]

    operations = [
        migrations.AddField(
            model_name="contentitem",
            name="chapters",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Ordered audio chapters with title and startSeconds.",
                verbose_name="audio chapters",
            ),
        ),
    ]
