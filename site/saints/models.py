import uuid
from datetime import date

from django.db import models
from django.db.models import DateTimeField


class UUIDModel(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class CreatableModel(models.Model):
    created = DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True


class UpdatableModel(models.Model):
    updated = DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class BaseModel(UUIDModel, CreatableModel, UpdatableModel):
    class Meta:
        abstract = True


class Saint(BaseModel):
    month = models.IntegerField(help_text="Month the saint is commemorated on the calendar as an integer from 1 to 12")
    day = models.IntegerField(
        help_text="Day of the month the saint is commemorated on the calendar as an integer from 1 to 31"
    )
    name = models.CharField(max_length=2500, help_text="Name of the saint")
    canonization_status = models.CharField(
        null=True,
        blank=True,
        max_length=2500,
        help_text="Title of the saint, such as Saint (St), Saints (SS), Blessed (Bd), Blesseds (BB), Venerable, etc.",
    )
    category = models.CharField(
        null=True,
        blank=True,
        max_length=2500,
        help_text="Category or categories of the saint such as Martyr, Confessor, Virgin, King, Queen, Penitent, Bishop, Archbishop, etc.",
    )
    biography_or_hagiography = models.TextField(help_text="Biography or Hagiography of the saint")
    footnotes = models.TextField(
        null=True,
        blank=True,
        help_text="Footnotes to the biography of the saint, if provided",
    )
    reflection = models.TextField(
        null=True,
        blank=True,
        help_text="A reflection or meditation on the life of the saint, if provided",
    )
    volume = models.IntegerField(null=True, blank=True, help_text="Volume number of the book, from 1 to 4")
    page_number = models.IntegerField(null=True, blank=True, help_text="Page number of the book, from 1 to 3000")
    year_of_death = models.CharField(
        null=True,
        blank=True,
        max_length=2500,
        help_text="Year of death often in the format 'A.D. 700', but can also be more generic such as 'Seventh Century' or a range",
    )


class SaintTitleEnum(models.TextChoices):
    SAINT = "Saint", "Saint"
    SAINTS = "Saints", "Saints"
    BLESSED = "Blessed", "Blessed"
    BLESSEDS = "Blesseds", "Blesseds"
    VENERABLE = "Venerable", "Venerable"


class Rank(models.TextChoices):
    # 1954
    DOUBLE_OF_I_CLASS = "Double of the I Class", "Double of the I Class"
    DOUBLE_OF_II_CLASS = "Double of the II Class", "Double of the II Class"
    MAJOR_DOUBLE = "Major Double (Greater Double)", "Major Double (Greater Double)"
    DOUBLE = "Double", "Double"
    SEMIDOUBLE = "Semidouble", "Semidouble"
    SIMPLE = "Simple", "Simple"
    GREATER_PRIVILEGED_FERIA = "Greater Privileged Feria", "Greater Privileged Feria"
    GREATER_NON_PRIVILEGED_FERIA = "Greater Non-Privileged Feria", "Greater Non-Privileged Feria"
    LESSER_FERIA = "Lesser Feria", "Lesser Feria"
    PRIV_OCTAVE_FIRST_ORDER = "Privileged Octave of the First Order", "Privileged Octave of the First Order"
    PRIV_OCTAVE_SECOND_ORDER = "Privileged Octave of the Second Order", "Privileged Octave of the Second Order"
    PRIV_OCTAVE_THIRD_ORDER = "Privileged Octave of the Third Order", "Privileged Octave of the Third Order"
    COMMON_OCTAVE = "Common Octave", "Common Octave"
    SIMPLE_OCTAVE = "Simple Octave", "Simple Octave"
    PRIVILEGED_VIGIL = "Privileged Vigil", "Privileged Vigil"
    COMMON_VIGIL = "Common Vigil", "Common Vigil"
    COMMEMORATION = "Commemoration", "Commemoration"

    # 1960
    FEAST_OF_THE_FIRST_CLASS = "Feast of the First Class", "Feast of the First Class"
    FEAST_OF_THE_SECOND_CLASS = "Feast of the Second Class", "Feast of the Second Class"
    FEAST_OF_THE_THIRD_CLASS = "Feast of the Third Class", "Feast of the Third Class"
    FERIA_OF_THE_FIRST_CLASS = "Feria of the First Class", "Feria of the First Class"
    FERIA_OF_THE_SECOND_CLASS = "Feria of the Second Class", "Feria of the Second Class"
    FERIA_OF_THE_THIRD_CLASS = "Feria of the Third Class", "Feria of the Third Class"
    FERIA_OF_THE_FOURTH_CLASS = "Feria of the Fourth Class", "Feria of the Fourth Class"
    OCTAVE_DAY = "Octave Day", "Octave Day"
    # COMMEMORATION = "Commemoration", "Commemoration" # This is already defined in 1954 section

    # 1969 / Current Roman Rite
    SOLEMNITY = "Solemnity", "Solemnity"
    FEAST = "Feast", "Feast"
    MEMORIAL = "Memorial", "Memorial"
    OPTIONAL_MEMORIAL = "Optional Memorial", "Optional Memorial"
    SEASONAL_WEEKDAY = "Seasonal Weekday", "Seasonal Weekday"
    FERIA = "Feria", "Feria"


class CalendarEnum(models.TextChoices):
    ROMAN_RITE_1954 = "Roman Rite (1954)", "Roman Rite (1954)"
    ROMAN_RITE_1962 = "Roman Rite (1962)", "Roman Rite (1962)"
    CURRENT_ROMAN_RITE = "Roman Rite (Current)", "Roman Rite (Current)"
    ORDINARIATE_ROMAN_RITE = "Roman Rite (Ordinariate)", "Roman Rite (Ordinariate)"


class SubcalendarEnum(models.TextChoices):
    GENERAL = "General", "General"
    USA = "USA", "USA"
    FSSP = "FSSP", "FSSP"
    ICKSP = "ICKSP", "ICKSP"
    SSPX = "SSPX", "SSPX"
    IN_SOME_PLACES = "In Some Places", "In Some Places"


class FeastTypeEnum(models.TextChoices):
    EVENT_IN_LIFE_OF_CHRIST = "Event in the life of Christ", "Event in the life of Christ"
    DAY_WITHIN_OCTAVE = "Day within the Octave", "Day within the Octave"
    OTHER_EVENT = "Other Event", "Other Event"
    BVM_FEAST = (
        "Title, Apparition, or Feast of the Blessed Virgin Mary",
        "Title, Apparition, or Feast of the Blessed Virgin Mary",
    )
    SAINT = "Saint", "Saint"
    OTHER = "Other", "Other"


class CalendarEvent(models.Model):
    date = models.DateField(blank=True, null=True)
    month = models.PositiveSmallIntegerField()
    day = models.PositiveSmallIntegerField()
    year = models.PositiveSmallIntegerField()
    latin_name = models.CharField(max_length=2500, blank=True, null=True)
    english_name = models.CharField(max_length=2500, blank=True, null=True)
    english_translation = models.CharField(max_length=2500, blank=True, null=True)
    color = models.CharField(max_length=255, blank=True, null=True)
    latin_notes = models.CharField(max_length=255, blank=True, null=True)
    english_notes = models.CharField(max_length=255, blank=True, null=True)
    order = models.PositiveSmallIntegerField(default=0)
    is_primary_for_day = models.BooleanField(default=False)
    temporale_or_sanctorale = models.CharField(max_length=255, blank=True, null=True)
    latin_rank = models.CharField(max_length=255, blank=True, null=True)
    english_rank = models.CharField(max_length=255, blank=True, null=True)
    is_person = models.BooleanField(default=False)
    saint_name = models.CharField(max_length=2500, blank=True, null=True)
    saint_category = models.CharField(max_length=2500, blank=True, null=True)
    saint_categories = models.JSONField(blank=True, null=True)
    saint_singular_or_plural = models.CharField(
        max_length=255, blank=True, null=True, choices=[("singular", "Singular"), ("plural", "Plural")]
    )
    calendar = models.CharField(max_length=255, blank=True, null=True)
    subcalendar = models.CharField(max_length=255, blank=True, null=True)
    season = models.CharField(max_length=255, blank=True, null=True)
    biography = models.ForeignKey(
        "Biography", null=True, blank=True, on_delete=models.SET_NULL, related_name="calendar_events"
    )

    def save(self, *args, **kwargs):
        if self.year and self.month and self.day and not self.date:
            self.date = date(self.year, self.month, self.day)
        if self.date:
            self.year = self.date.year
            self.month = self.date.month
            self.day = self.date.day
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.english_name} ({self.english_rank }) - {self.month}/{self.day}/{self.year} ({self.calendar})"


class Biography(BaseModel):
    name = models.CharField(max_length=2500)
    religion = models.CharField(max_length=64)
    calendar = models.CharField(max_length=64)

    def __str__(self):
        return f"{self.name} ({self.religion})"


class ShortDescriptionsModel(models.Model):
    biography = models.OneToOneField(Biography, on_delete=models.CASCADE, related_name="short_descriptions")
    one_sentence_description = models.TextField()
    one_paragraph_description = models.TextField()


class QuoteModel(models.Model):
    biography = models.OneToOneField(Biography, on_delete=models.CASCADE, related_name="quote")
    quote = models.TextField()
    person = models.CharField(max_length=2500)
    date = models.CharField(max_length=2500)


class BibleVerseModel(models.Model):
    biography = models.OneToOneField(Biography, on_delete=models.CASCADE, related_name="bible_verse")
    citation = models.CharField(max_length=2500)
    text = models.TextField()
    bible_version_abbreviation = models.CharField(max_length=32)
    bible_version = models.CharField(max_length=2500)
    bible_version_year = models.CharField(max_length=8)


class HagiographyCitationModel(models.Model):
    citation = models.TextField()
    url = models.URLField(max_length=2500, null=True, blank=True)
    date_accessed = models.CharField(max_length=64, null=True, blank=True)
    title = models.CharField(max_length=2500, null=True, blank=True)

    def __str__(self):
        url_part = f" - { self.url }" if self.url else ""
        return f"{self.title or 'Citation'}{url_part}"


class HagiographyModel(models.Model):
    biography = models.OneToOneField(Biography, on_delete=models.CASCADE, related_name="hagiography")
    hagiography = models.TextField()
    citations = models.ManyToManyField(HagiographyCitationModel, blank=True, related_name="hagiographies")


class LegendModel(models.Model):
    biography = models.OneToOneField(Biography, on_delete=models.CASCADE, related_name="legend")
    legend = models.TextField()
    title = models.CharField(max_length=2500)
    citations = models.ManyToManyField(HagiographyCitationModel, blank=True, related_name="legends")


class BulletPointsModel(models.Model):
    biography = models.OneToOneField(Biography, on_delete=models.CASCADE, related_name="bullet_points")
    citations = models.ManyToManyField(HagiographyCitationModel, blank=True, related_name="bullet_points")


class BulletPoint(models.Model):
    bullet_points_model = models.ForeignKey(BulletPointsModel, on_delete=models.CASCADE, related_name="bullet_points")
    text = models.TextField()
    order = models.PositiveIntegerField(default=0)


class TraditionModel(models.Model):
    biography = models.ForeignKey(Biography, on_delete=models.CASCADE, related_name="traditions")
    tradition = models.TextField()
    country_of_origin = models.CharField(max_length=2500, null=True, blank=True)
    reason_associated_with_saint = models.TextField(null=True, blank=True)
    order = models.PositiveIntegerField(default=0)


class FoodModel(models.Model):
    biography = models.ForeignKey(Biography, on_delete=models.CASCADE, related_name="foods")
    food_name = models.CharField(max_length=2500)
    description = models.TextField()
    country_of_origin = models.CharField(max_length=2500, null=True, blank=True)
    reason_associated_with_saint = models.TextField(null=True, blank=True)
    order = models.PositiveIntegerField(default=0)


class WritingModel(models.Model):
    biography = models.ForeignKey(Biography, on_delete=models.CASCADE, related_name="writings")
    writing = models.TextField()
    date = models.CharField(max_length=2500)
    title = models.CharField(max_length=2500)
    url = models.URLField(max_length=2500, null=True, blank=True)
    author = models.CharField(max_length=2500, null=True, blank=True)
    type = models.CharField(max_length=32, choices=[("by", "By Saint"), ("about", "About Saint")])
    order = models.PositiveIntegerField(default=0)


class ImageModel(models.Model):
    biography = models.ForeignKey(Biography, on_delete=models.CASCADE, related_name="images")
    url = models.URLField(max_length=2500, )
    title = models.CharField(max_length=2500)
    author = models.CharField(max_length=2500, null=True, blank=True)
    date = models.CharField(max_length=2500, null=True, blank=True)
    order = models.PositiveIntegerField(default=0)


class FeastDescriptionModel(models.Model):
    biography = models.OneToOneField(Biography, on_delete=models.CASCADE, related_name="feast_description")
    feast_description = models.TextField()
    citations = models.ManyToManyField(HagiographyCitationModel, blank=True, related_name="feast_descriptions")


class Podcast(BaseModel):
    slug = models.SlugField(unique=True, max_length=500)
    religion = models.CharField(max_length=64)
    title = models.CharField(max_length=2500)
    image = models.ImageField(upload_to="podcast_images/", null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    link = models.URLField(max_length=2500, default="https://saints.benlocher.com")

    def __str__(self):
        return self.title


class PodcastEpisode(BaseModel):
    slug = models.SlugField(unique=True, max_length=500)
    date = models.DateField(help_text="Date this episode is for")
    published_date = models.DateTimeField(null=True, blank=True)
    podcast = models.ForeignKey(Podcast, on_delete=models.CASCADE, related_name="episodes")
    file_name = models.CharField(max_length=2500)
    episode_title = models.CharField(max_length=2500)
    episode_subtitle = models.CharField(max_length=2500)
    episode_short_description = models.TextField()
    episode_long_description = models.TextField()
    episode_full_text = models.TextField()
    duration = models.IntegerField(null=True, blank=True, help_text="Duration of the episode in seconds")
    episode_number = models.PositiveIntegerField(null=True, blank=True, help_text="Episode number within the podcast")

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return self.episode_title
