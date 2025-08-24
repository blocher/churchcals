from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("saints", "0003_podcastlistenlog"),
    ]

    operations = [
        migrations.AddField(
            model_name="podcastlistenlog",
            name="playback_id",
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.AddField(
            model_name="podcastlistenlog",
            name="is_seek",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="podcastlistenlog",
            name="request_index",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddIndex(
            model_name="podcastlistenlog",
            index=models.Index(fields=["playback_id"], name="saints_podcastlisten_playback_idx"),
        ),
    ]


