from django.contrib import admin
import nested_admin
from .models import (
    Biography,
    ShortDescriptionsModel,
    QuoteModel,
    BibleVerseModel,
    HagiographyModel,
    HagiographyCitationModel,
    LegendModel,
    BulletPointsModel,
    BulletPoint,
    TraditionModel,
    FoodModel,
    WritingModel,
    ImageModel,
    FeastDescriptionModel,  # Added import
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
    filter_horizontal = ('citations',)

class LegendInline(nested_admin.NestedStackedInline):
    model = LegendModel
    can_delete = False
    extra = 0
    filter_horizontal = ('citations',)

class BulletPointNestedInline(nested_admin.NestedTabularInline):
    model = BulletPoint
    extra = 0
    ordering = ["order"]

class BulletPointsNestedInline(nested_admin.NestedStackedInline):
    model = BulletPointsModel
    can_delete = False
    extra = 0
    filter_horizontal = ('citations',)
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
    filter_horizontal = ('citations',)

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
