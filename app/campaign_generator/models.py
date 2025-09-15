from django.db import models
from django.utils.text import slugify
from versatileimagefield.fields import VersatileImageField


class Language(models.Model):
    """Language support for multilingual campaigns"""

    TEXT_DIRECTIONS = [
        ("ltr", "Left-to-Right"),
        ("rtl", "Right-to-Left"),
        ("ttb", "Top-to-Bottom"),
    ]

    SCRIPT_TYPES = [
        ("latin", "Latin"),
        ("hiragana", "Hiragana"),
        ("katakana", "Katakana"),
        ("han", "Han (Chinese/Japanese)"),
        ("hangul", "Hangul"),
        ("arabic", "Arabic"),
        ("hebrew", "Hebrew"),
        ("cyrillic", "Cyrillic"),
    ]

    code = models.CharField(
        max_length=5, unique=True, help_text="ISO 639-1 language code (e.g., 'en', 'es', 'ja')"
    )
    name = models.CharField(
        max_length=50, help_text="Language name in English (e.g., 'English', 'Spanish', 'Japanese')"
    )
    native_name = models.CharField(
        max_length=50, blank=True, help_text="Language name in native script (e.g., '日本語')"
    )
    direction = models.CharField(
        max_length=10,
        choices=TEXT_DIRECTIONS,
        default="ltr",
        help_text="Text direction for this language",
    )
    script = models.CharField(
        max_length=20,
        choices=SCRIPT_TYPES,
        default="latin",
        help_text="Primary script type for this language",
    )
    is_active = models.BooleanField(
        default=True, help_text="Whether this language is available for campaigns"
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.code})"

    class Meta:
        ordering = ["name"]


class Brief(models.Model):
    """Campaign brief - matches FDE requirements exactly"""

    title = models.CharField(max_length=200)
    target_region = models.CharField(max_length=200)
    target_audience = models.TextField()
    campaign_message = models.TextField()
    products = models.JSONField(
        help_text="Array of products: [{'name': 'Product A', 'type': 'Energy Drink'}]"
    )

    # Multilingual fields
    primary_language = models.ForeignKey(
        Language,
        on_delete=models.PROTECT,
        related_name="primary_briefs",
        default=1,  # English by default
        help_text="Primary language for this campaign",
    )
    supported_languages = models.ManyToManyField(
        Language,
        related_name="supported_briefs",
        blank=True,
        help_text="Additional languages to generate assets for",
    )
    translation_config = models.JSONField(
        default=dict, blank=True, help_text="Translation settings and overrides"
    )

    # Reference image for asset generation
    reference_image = VersatileImageField(
        upload_to="reference_images/",
        blank=True,
        null=True,
        help_text="Optional reference image that will be normalized to 1024x1024 and used as the first generated asset",
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    @property
    def product_count(self):
        return len(self.products) if self.products else 0

    def get_all_languages(self):
        """Get all languages for this brief (primary + supported)"""
        languages = [self.primary_language]
        languages.extend(self.supported_languages.all())
        return list(set(languages))  # Remove duplicates

    def get_expected_asset_count(self):
        """Calculate expected number of generated assets (products × 3 aspect ratios × languages)"""
        language_count = len(self.get_all_languages())
        return self.product_count * 3 * language_count

    class Meta:
        ordering = ["-created_at"]


class DemoBrief(models.Model):
    """Demo brief templates - identical structure to Brief for easy copying"""

    title = models.CharField(max_length=200)
    target_region = models.CharField(max_length=200)
    target_audience = models.TextField()
    campaign_message = models.TextField()
    products = models.JSONField(
        help_text="Array of products: [{'name': 'Product A', 'type': 'Energy Drink'}]"
    )

    # Multilingual fields - same as Brief
    primary_language = models.ForeignKey(
        Language,
        on_delete=models.PROTECT,
        related_name="primary_demo_briefs",
        default=1,  # English by default
        help_text="Primary language for this campaign",
    )
    supported_languages = models.ManyToManyField(
        Language,
        related_name="supported_demo_briefs",
        blank=True,
        help_text="Additional languages to generate assets for",
    )
    translation_config = models.JSONField(
        default=dict, blank=True, help_text="Translation settings and overrides"
    )

    # Demo-specific fields
    description = models.TextField(
        blank=True, help_text="Description of this demo brief for selection UI"
    )
    is_active = models.BooleanField(
        default=True, help_text="Whether this demo brief appears in the selection UI"
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    def get_all_languages(self):
        """Get all languages (primary + supported) for this demo brief"""
        all_languages = [self.primary_language]
        all_languages.extend(self.supported_languages.all())
        return list(set(all_languages))  # Remove duplicates

    def to_brief_data(self):
        """Convert to dict format for copying to Brief form"""
        return {
            "title": self.title,
            "target_region": self.target_region,
            "target_audience": self.target_audience,
            "campaign_message": self.campaign_message,
            "products": self.products,
            "primary_language": self.primary_language.id,
            "supported_languages": [lang.id for lang in self.supported_languages.all()],
            "translation_config": self.translation_config,
        }

    class Meta:
        ordering = ["title"]


class GeneratedAsset(models.Model):
    """Track generated campaign assets"""

    ASPECT_RATIOS = [
        ("1:1", "Square (1:1)"),
        ("9:16", "Vertical Story (9:16)"),
        ("16:9", "Horizontal Video (16:9)"),
    ]

    TRANSLATION_STATUS_CHOICES = [
        ("original", "Original"),
        ("translated", "Translated"),
        ("failed", "Translation Failed"),
        ("pending", "Translation Pending"),
    ]

    brief = models.ForeignKey(Brief, on_delete=models.CASCADE, related_name="generated_assets")
    generation_run = models.ForeignKey(
        "GenerationRun", on_delete=models.CASCADE, related_name="assets"
    )
    product_name = models.CharField(max_length=200)
    aspect_ratio = models.CharField(max_length=10, choices=ASPECT_RATIOS)

    # Multilingual fields
    language = models.ForeignKey(
        Language,
        on_delete=models.PROTECT,
        default=1,  # English by default
        help_text="Language for this asset",
    )
    original_asset = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        help_text="Link to original asset if this is a translation",
    )
    translation_status = models.CharField(
        max_length=20,
        choices=TRANSLATION_STATUS_CHOICES,
        default="original",
        help_text="Translation status of this asset",
    )
    translated_campaign_message = models.TextField(
        blank=True, help_text="Translated campaign message for this language"
    )

    # AI generation details
    ai_prompt = models.TextField()
    generation_time_seconds = models.FloatField(null=True, blank=True)

    # File storage - Simple ImageField for MVP (no VersatileImageField needed)
    image_file = models.ImageField(upload_to="generated/", blank=True)
    organized_file_path = models.CharField(
        max_length=500, help_text="Path in organized output structure"
    )

    # Reference image metadata
    is_reference_image = models.BooleanField(
        default=False, help_text="True if this asset was created from an uploaded reference image"
    )
    reference_image_note = models.CharField(
        max_length=200,
        blank=True,
        help_text="Note about the reference image processing (e.g., 'Normalized from uploaded reference')",
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.product_name} - {self.aspect_ratio} (Run #{self.generation_run.run_index})"

    @property
    def file_size_mb(self):
        """Get file size in MB for display"""
        if self.image_file:
            return round(self.image_file.size / (1024 * 1024), 2)
        return 0

    @property
    def organized_folder(self):
        """Get the organized folder name for this asset"""
        return f"{slugify(self.product_name)}/{self.language.code}/{self.aspect_ratio.replace(':', 'x')}"

    def get_display_name(self):
        """Get display name including language"""
        return f"{self.product_name} - {self.aspect_ratio} ({self.language.code.upper()})"

    class Meta:
        ordering = ["-created_at"]
        unique_together = ["generation_run", "product_name", "aspect_ratio", "language"]
        indexes = [
            models.Index(fields=["language", "aspect_ratio"]),
            models.Index(fields=["brief", "language"]),
            models.Index(fields=["translation_status"]),
        ]


class GenerationRun(models.Model):
    """Track generation runs - each run is independent and can be retried"""

    brief = models.ForeignKey(Brief, on_delete=models.CASCADE, related_name="generation_runs")

    # Simple run identification
    run_index = models.IntegerField(help_text="Sequential run number for this brief")
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Results
    success = models.BooleanField(default=False)
    error_message = models.TextField(blank=True)
    assets_generated = models.IntegerField(default=0)
    total_generation_time = models.FloatField(default=0.0)
    estimated_cost_usd = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)

    def __str__(self):
        status = "✅ Success" if self.success else "❌ Failed"
        return f"Run #{self.run_index} - {status} - {self.brief.title}"

    @property
    def is_current(self):
        """Is this the most recent run for this brief?"""
        latest_run = GenerationRun.objects.filter(brief=self.brief).order_by("-run_index").first()
        return latest_run and self.run_index == latest_run.run_index

    @property
    def duration_seconds(self):
        """Calculate run duration"""
        if self.completed_at and self.started_at:
            return (self.completed_at - self.started_at).total_seconds()
        return 0

    class Meta:
        ordering = ["-started_at"]
        unique_together = ["brief", "run_index"]


class GenerationSession(models.Model):
    """Track generation sessions for logging/reporting - DEPRECATED, use GenerationRun"""

    brief = models.ForeignKey(Brief, on_delete=models.CASCADE, related_name="generation_sessions")
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    assets_generated = models.IntegerField(default=0)
    total_generation_time = models.FloatField(default=0.0)
    success = models.BooleanField(default=False)
    error_message = models.TextField(blank=True)
    estimated_cost_usd = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)

    def __str__(self):
        status = "✅ Success" if self.success else "❌ Failed"
        return f"{status} - {self.brief.title} ({self.assets_generated} assets)"

    class Meta:
        ordering = ["-started_at"]
