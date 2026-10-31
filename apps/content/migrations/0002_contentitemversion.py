from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ("content", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ContentItemVersion",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("file_id", models.UUIDField(blank=True, null=True)),
                ("external_url", models.URLField(blank=True)),
                ("file_name", models.CharField(blank=True, max_length=255)),
                ("file_size_bytes", models.BigIntegerField(blank=True, null=True)),
                ("version_number", models.PositiveIntegerField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("content_item", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="versions", to="content.contentitem")),
                ("created_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="content_item_versions_created", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-version_number"]},
        ),
        migrations.AddConstraint(
            model_name="contentitemversion",
            constraint=models.UniqueConstraint(fields=("content_item", "version_number"), name="uniq_content_item_version"),
        ),
    ]
