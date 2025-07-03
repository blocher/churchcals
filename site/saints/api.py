"""REST API endpoints for the saints project."""

from datetime import timedelta

from rest_framework import serializers, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from saints.models import (
    BibleVerseModel,
    Biography,
    BulletPoint,
    BulletPointsModel,
    CalendarEvent,
    FeastDescriptionModel,
    FoodModel,
    HagiographyCitationModel,
    HagiographyModel,
    ImageModel,
    LegendModel,
    QuoteModel,
    ShortDescriptionsModel,
    TraditionModel,
    WritingModel,
)
from saints.views import first_sunday_of_advent


class HagiographyCitationSerializer(serializers.ModelSerializer):
    class Meta:
        model = HagiographyCitationModel
        fields = ["citation", "url", "date_accessed", "title"]


class ShortDescriptionsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShortDescriptionsModel
        fields = ["one_sentence_description", "one_paragraph_description"]


class QuoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuoteModel
        fields = ["quote", "person", "date"]


class BibleVerseSerializer(serializers.ModelSerializer):
    class Meta:
        model = BibleVerseModel
        fields = [
            "citation",
            "text",
            "bible_version_abbreviation",
            "bible_version",
            "bible_version_year",
        ]


class HagiographySerializer(serializers.ModelSerializer):
    citations = HagiographyCitationSerializer(many=True, read_only=True)

    class Meta:
        model = HagiographyModel
        fields = ["hagiography", "citations"]


class LegendSerializer(serializers.ModelSerializer):
    citations = HagiographyCitationSerializer(many=True, read_only=True)

    class Meta:
        model = LegendModel
        fields = ["title", "legend", "citations"]


class BulletPointSerializer(serializers.ModelSerializer):
    class Meta:
        model = BulletPoint
        fields = ["text", "order"]


class BulletPointsSerializer(serializers.ModelSerializer):
    bullet_points = BulletPointSerializer(many=True, read_only=True)
    citations = HagiographyCitationSerializer(many=True, read_only=True)

    class Meta:
        model = BulletPointsModel
        fields = ["bullet_points", "citations"]


class TraditionSerializer(serializers.ModelSerializer):
    class Meta:
        model = TraditionModel
        fields = ["tradition", "country_of_origin", "reason_associated_with_saint", "order"]


class FoodSerializer(serializers.ModelSerializer):
    class Meta:
        model = FoodModel
        fields = [
            "food_name",
            "description",
            "country_of_origin",
            "reason_associated_with_saint",
            "order",
        ]


class WritingSerializer(serializers.ModelSerializer):
    class Meta:
        model = WritingModel
        fields = ["writing", "date", "title", "url", "author", "type", "order"]


class ImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImageModel
        fields = ["url", "title", "author", "date", "order"]


class FeastDescriptionSerializer(serializers.ModelSerializer):
    citations = HagiographyCitationSerializer(many=True, read_only=True)

    class Meta:
        model = FeastDescriptionModel
        fields = ["feast_description", "citations"]


class BiographySerializer(serializers.ModelSerializer):
    short_descriptions = ShortDescriptionsSerializer(read_only=True)
    quote = QuoteSerializer(read_only=True)
    bible_verse = BibleVerseSerializer(read_only=True)
    hagiography = HagiographySerializer(read_only=True)
    legend = LegendSerializer(read_only=True)
    bullet_points = BulletPointsSerializer(read_only=True)
    traditions = TraditionSerializer(many=True, read_only=True)
    foods = FoodSerializer(many=True, read_only=True)
    writings = WritingSerializer(many=True, read_only=True)
    images = ImageSerializer(many=True, read_only=True)
    feast_description = FeastDescriptionSerializer(read_only=True)

    class Meta:
        model = Biography
        fields = [
            "uuid",
            "name",
            "religion",
            "calendar",
            "short_descriptions",
            "quote",
            "bible_verse",
            "hagiography",
            "legend",
            "bullet_points",
            "traditions",
            "foods",
            "writings",
            "images",
            "feast_description",
        ]


class CalendarEventSerializer(serializers.ModelSerializer):
    biography = BiographySerializer(read_only=True)

    class Meta:
        model = CalendarEvent
        fields = [
            "id",
            "date",
            "month",
            "day",
            "year",
            "latin_name",
            "english_name",
            "english_translation",
            "color",
            "latin_notes",
            "english_notes",
            "order",
            "is_primary_for_day",
            "temporale_or_sanctorale",
            "latin_rank",
            "english_rank",
            "is_person",
            "saint_name",
            "saint_category",
            "saint_categories",
            "saint_singular_or_plural",
            "calendar",
            "subcalendar",
            "season",
            "biography",
        ]


class BiographyViewSet(viewsets.ReadOnlyModelViewSet):
    """Retrieve biographies with all related data."""

    queryset = Biography.objects.all()
    serializer_class = BiographySerializer


class LiturgicalYearView(APIView):
    """Return all events for a liturgical year on a specific calendar."""

    calendar_filters = {
        "catholic_1954": {"calendar__icontains": "1954"},
        "catholic_1962": {"calendar__icontains": "1960"},
        "current": {"calendar__icontains": "catholic"},
        "ordinariate": {"calendar__icontains": "ordinariate"},
        "acna": {"calendar__icontains": "acna"},
        "tec": {"calendar__icontains": "tec"},
    }

    def get(self, request, year: int, calendar: str) -> Response:
        start = first_sunday_of_advent(year)
        end = first_sunday_of_advent(year + 1) - timedelta(days=1)
        filters = self.calendar_filters.get(calendar, self.calendar_filters["current"])
        events = CalendarEvent.objects.filter(date__range=(start, end), **filters).order_by(
            "date",
            "order",
            "english_name",
        )
        serializer = CalendarEventSerializer(events, many=True)
        return Response({"calendar": calendar, "year": year, "events": serializer.data})


class DayView(APIView):
    """Return all events for a single day grouped by calendar."""

    calendar_filters = LiturgicalYearView.calendar_filters

    def get(self, request, date):
        events_by_calendar = {}
        for key, flt in self.calendar_filters.items():
            day_events = CalendarEvent.objects.filter(date=date, **flt).order_by("order", "english_name")
            events_by_calendar[key] = CalendarEventSerializer(day_events, many=True).data
        return Response({"date": date, "calendars": events_by_calendar})


class CalendarListView(APIView):
    """List available calendars."""

    def get(self, request):
        calendars = list(LiturgicalYearView.calendar_filters.keys())
        return Response({"calendars": calendars})

