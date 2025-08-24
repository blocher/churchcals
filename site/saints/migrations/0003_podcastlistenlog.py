from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("saints", "0002_alter_podcast_slug_alter_podcastepisode_slug"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PodcastListenLog",
            fields=[
                ("uuid", models.UUIDField(primary_key=True, serialize=False, editable=False)),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                (
                    "podcast",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.SET_NULL,
                        blank=True,
                        null=True,
                        related_name="listen_logs",
                        to="saints.podcast",
                    ),
                ),
                (
                    "episode",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.SET_NULL,
                        blank=True,
                        null=True,
                        related_name="listen_logs",
                        to="saints.podcastepisode",
                    ),
                ),
                ("method", models.CharField(max_length=8, blank=True, null=True)),
                ("path", models.CharField(max_length=2048, blank=True, null=True)),
                ("referrer", models.CharField(max_length=2048, blank=True, null=True)),
                ("user_agent", models.TextField(blank=True, null=True)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("x_forwarded_for", models.CharField(max_length=1024, blank=True, null=True)),
                ("session_key", models.CharField(max_length=128, blank=True, null=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.SET_NULL,
                        blank=True,
                        null=True,
                        related_name="podcast_listens",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                ("range_header", models.CharField(max_length=255, blank=True, null=True)),
                ("range_start", models.BigIntegerField(blank=True, null=True)),
                ("range_end", models.BigIntegerField(blank=True, null=True)),
                ("total_size", models.BigIntegerField(blank=True, null=True)),
                ("bytes_served", models.BigIntegerField(blank=True, null=True)),
                ("is_partial", models.BooleanField(default=False)),
                ("status_code", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("response_time_ms", models.PositiveIntegerField(blank=True, null=True)),
                ("geo_country", models.CharField(max_length=128, blank=True, null=True)),
                ("geo_region", models.CharField(max_length=128, blank=True, null=True)),
                ("geo_city", models.CharField(max_length=128, blank=True, null=True)),
                ("geo_latitude", models.FloatField(blank=True, null=True)),
                ("geo_longitude", models.FloatField(blank=True, null=True)),
                ("fingerprint_sha256", models.CharField(max_length=64, blank=True, null=True)),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.AddIndex(
            model_name="podcastlistenlog",
            index=models.Index(fields=["created"], name="saints_podcastlisten_created_idx"),
        ),
        migrations.AddIndex(
            model_name="podcastlistenlog",
            index=models.Index(fields=["podcast", "episode"], name="saints_podcastlisten_pod_ep_idx"),
        ),
        migrations.AddIndex(
            model_name="podcastlistenlog",
            index=models.Index(fields=["ip_address"], name="saints_podcastlisten_ip_idx"),
        ),
        migrations.AddIndex(
            model_name="podcastlistenlog",
            index=models.Index(fields=["fingerprint_sha256"], name="saints_podcastlisten_fp_idx"),
        ),
    ]


