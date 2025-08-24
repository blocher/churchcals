import nested_admin
from django.contrib import admin

from .models import FeastDescriptionModel  # Added import
from .models import (
    BibleVerseModel,
    Biography,
    BulletPoint,
    BulletPointsModel,
    FoodModel,
    HagiographyCitationModel,
    HagiographyModel,
    ImageModel,
    LegendModel,
    Podcast,
    PodcastEpisode,
    PodcastListenLog,
    QuoteModel,
    ShortDescriptionsModel,
    TraditionModel,
    WritingModel,
)


class ShortDescriptionsInline(nested_admin.NestedStackedInline):
    model = ShortDescriptionsModel
    can_delete = False
    extra = 0


class QuoteInline(nested_admin.NestedStackedInline):
    model = QuoteModel
    can_delete = False
    extra = 0


class BibleVerseInline(nested_admin.NestedStackedInline):
    model = BibleVerseModel
    can_delete = False
    extra = 0


class HagiographyInline(nested_admin.NestedStackedInline):
    model = HagiographyModel
    can_delete = False
    extra = 0
    filter_horizontal = ("citations",)


class LegendInline(nested_admin.NestedStackedInline):
    model = LegendModel
    can_delete = False
    extra = 0
    filter_horizontal = ("citations",)


class BulletPointNestedInline(nested_admin.NestedTabularInline):
    model = BulletPoint
    extra = 0
    ordering = ["order"]


class BulletPointsNestedInline(nested_admin.NestedStackedInline):
    model = BulletPointsModel
    can_delete = False
    extra = 0
    filter_horizontal = ("citations",)
    show_change_link = True
    inlines = [BulletPointNestedInline]


class TraditionInline(nested_admin.NestedTabularInline):
    model = TraditionModel
    extra = 0
    ordering = ["order"]


class FoodInline(nested_admin.NestedTabularInline):
    model = FoodModel
    extra = 0
    ordering = ["order"]


class WritingInline(nested_admin.NestedTabularInline):
    model = WritingModel
    extra = 0
    ordering = ["order"]


class ImageInline(nested_admin.NestedTabularInline):
    model = ImageModel
    extra = 0
    ordering = ["order"]


class FeastDescriptionInline(nested_admin.NestedStackedInline):
    model = FeastDescriptionModel
    can_delete = False
    extra = 0
    filter_horizontal = ("citations",)


class BiographyAdmin(nested_admin.NestedModelAdmin):
    inlines = [
        ShortDescriptionsInline,
        QuoteInline,
        BibleVerseInline,
        HagiographyInline,
        LegendInline,
        BulletPointsNestedInline,
        TraditionInline,
        FoodInline,
        WritingInline,
        ImageInline,
        FeastDescriptionInline,
    ]


admin.site.register(Biography, BiographyAdmin)
admin.site.register(FeastDescriptionModel)


class PodcastEpisodeInline(nested_admin.NestedTabularInline):
    model = PodcastEpisode
    extra = 0
    ordering = ["-date"]


class PodcastAdmin(nested_admin.NestedModelAdmin):
    class ListenLogInline(nested_admin.NestedTabularInline):
        model = PodcastListenLog
        extra = 0
        readonly_fields = (
            "created",
            "episode",
            "ip_address",
            "geo_country",
            "geo_region",
            "geo_city",
            "user_agent",
            "bytes_served",
            "is_partial",
            "is_seek",
            "request_index",
            "playback_id",
            "status_code",
        )
        fields = (
            "created",
            "episode",
            "ip_address",
            "geo_country",
            "geo_region",
            "geo_city",
            "user_agent",
            "bytes_served",
            "is_partial",
            "is_seek",
            "request_index",
            "playback_id",
            "status_code",
        )
        can_delete = False
        ordering = ["-created"]

    inlines = [PodcastEpisodeInline, ListenLogInline]


@admin.register(PodcastEpisode)
class PodcastEpisodeAdmin(admin.ModelAdmin):
    list_filter = ["date"]
    ordering = ["-date"]
    class ListenLogInline(nested_admin.NestedTabularInline):
        model = PodcastListenLog
        extra = 0
        readonly_fields = (
            "created",
            "ip_address",
            "geo_country",
            "geo_region",
            "geo_city",
            "user_agent",
            "bytes_served",
            "is_partial",
            "is_seek",
            "request_index",
            "playback_id",
            "status_code",
        )
        fields = (
            "created",
            "ip_address",
            "geo_country",
            "geo_region",
            "geo_city",
            "user_agent",
            "bytes_served",
            "is_partial",
            "is_seek",
            "request_index",
            "playback_id",
            "status_code",
        )
        can_delete = False
        ordering = ["-created"]

    inlines = [ListenLogInline]


admin.site.register(Podcast, PodcastAdmin)


@admin.register(PodcastListenLog)
class PodcastListenLogAdmin(admin.ModelAdmin):
    list_display = (
        "created",
        "podcast",
        "episode",
        "ip_address",
        "geo_country",
        "geo_region",
        "geo_city",
        "bytes_served",
        "status_code",
        "is_partial",
        "is_seek",
        "request_index",
        "playback_id",
    )
    list_filter = (
        "podcast",
        "episode",
        "is_partial",
        "is_seek",
        "geo_country",
        "status_code",
    )
    search_fields = (
        "episode__episode_title",
        "podcast__title",
        "ip_address",
        "user_agent",
        "fingerprint_sha256",
        "playback_id",
        "x_forwarded_for",
    )
    raw_id_fields = ("podcast", "episode", "user")
    date_hierarchy = "created"
    ordering = ("-created",)
    readonly_fields = (
        "created",
        "updated",
        "podcast",
        "episode",
        "method",
        "path",
        "referrer",
        "user_agent",
        "ip_address",
        "x_forwarded_for",
        "session_key",
        "user",
        "range_header",
        "range_start",
        "range_end",
        "total_size",
        "bytes_served",
        "is_partial",
        "status_code",
        "response_time_ms",
        "geo_country",
        "geo_region",
        "geo_city",
        "geo_latitude",
        "geo_longitude",
        "fingerprint_sha256",
        "playback_id",
        "is_seek",
        "request_index",
    )
