from django.contrib import admin

from .models import Brief, DemoBrief, GeneratedAsset, GenerationRun, GenerationSession, Language


@admin.register(Language)
class LanguageAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "native_name", "direction", "script", "is_active"]
    list_filter = ["direction", "script", "is_active"]
    search_fields = ["name", "code", "native_name"]
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        ("Basic Info", {"fields": ("code", "name", "native_name", "is_active")}),
        ("Text Properties", {"fields": ("direction", "script")}),
        ("Metadata", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )


@admin.register(Brief)
class BriefAdmin(admin.ModelAdmin):
    list_display = ["title", "target_region", "primary_language", "product_count", "created_at"]
    list_filter = ["target_region", "primary_language", "created_at"]
    search_fields = ["title", "target_region", "campaign_message"]
    readonly_fields = ["created_at", "updated_at"]
    filter_horizontal = ["supported_languages"]

    fieldsets = (
        ("Campaign Details", {"fields": ("title", "campaign_message")}),
        ("Target Information", {"fields": ("target_region", "target_audience")}),
        (
            "Languages",
            {"fields": ("primary_language", "supported_languages", "translation_config")},
        ),
        (
            "Products",
            {
                "fields": ("products",),
                "description": 'JSON array of products: [{"name": "Product A", "type": "Energy Drink"}]',
            },
        ),
        ("Reference Image", {"fields": ("reference_image",), "classes": ("collapse",)}),
        ("Metadata", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def product_count(self, obj):
        """Return the number of products in this brief"""
        return len(obj.products) if obj.products else 0

    product_count.short_description = "Products"


@admin.register(GeneratedAsset)
class GeneratedAssetAdmin(admin.ModelAdmin):
    list_display = [
        "get_display_name",
        "language",
        "translation_status",
        "brief",
        "generation_run",
        "is_reference_image",
        "file_size_mb",
        "generation_time_seconds",
        "created_at",
    ]
    list_filter = [
        "aspect_ratio",
        "language",
        "translation_status",
        "brief",
        "generation_run",
        "is_reference_image",
        "created_at",
    ]
    search_fields = ["product_name", "brief__title", "ai_prompt", "translated_campaign_message"]
    readonly_fields = ["created_at", "file_size_mb", "organized_folder", "get_display_name"]

    fieldsets = (
        (
            "Asset Details",
            {"fields": ("brief", "generation_run", "product_name", "aspect_ratio", "image_file")},
        ),
        (
            "Language & Translation",
            {
                "fields": (
                    "language",
                    "translation_status",
                    "original_asset",
                    "translated_campaign_message",
                )
            },
        ),
        (
            "Generation Info",
            {
                "fields": (
                    "ai_prompt",
                    "generation_time_seconds",
                    "is_reference_image",
                    "reference_image_note",
                )
            },
        ),
        (
            "File Organization",
            {"fields": ("organized_file_path", "organized_folder"), "classes": ("collapse",)},
        ),
        (
            "Metadata",
            {
                "fields": ("created_at", "file_size_mb", "get_display_name"),
                "classes": ("collapse",),
            },
        ),
    )


@admin.register(GenerationRun)
class GenerationRunAdmin(admin.ModelAdmin):
    list_display = [
        "brief",
        "run_index",
        "success",
        "assets_generated",
        "total_generation_time",
        "estimated_cost_usd",
        "started_at",
    ]
    list_filter = ["success", "started_at", "run_index"]
    search_fields = ["brief__title", "error_message"]
    readonly_fields = ["started_at", "duration_seconds", "is_current"]

    fieldsets = (
        ("Run Info", {"fields": ("brief", "run_index", "started_at", "completed_at")}),
        (
            "Results",
            {
                "fields": (
                    "success",
                    "assets_generated",
                    "total_generation_time",
                    "estimated_cost_usd",
                )
            },
        ),
        (
            "Performance",
            {"fields": ("duration_seconds", "is_current"), "classes": ("collapse",)},
        ),
        ("Errors", {"fields": ("error_message",), "classes": ("collapse",)}),
    )


@admin.register(GenerationSession)
class GenerationSessionAdmin(admin.ModelAdmin):
    list_display = [
        "brief",
        "success",
        "assets_generated",
        "total_generation_time",
        "estimated_cost_usd",
        "started_at",
    ]
    list_filter = ["success", "started_at"]
    search_fields = ["brief__title", "error_message"]
    readonly_fields = ["started_at"]

    fieldsets = (
        ("Session Info", {"fields": ("brief", "started_at", "completed_at")}),
        (
            "Results",
            {
                "fields": (
                    "success",
                    "assets_generated",
                    "total_generation_time",
                    "estimated_cost_usd",
                )
            },
        ),
        ("Errors", {"fields": ("error_message",), "classes": ("collapse",)}),
    )


@admin.register(DemoBrief)
class DemoBriefAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "target_region",
        "primary_language",
        "product_count",
        "is_active",
        "created_at",
    ]
    list_filter = ["target_region", "primary_language", "is_active", "created_at"]
    search_fields = ["title", "target_region", "campaign_message", "description"]
    readonly_fields = ["created_at", "updated_at"]
    filter_horizontal = ["supported_languages"]

    fieldsets = (
        ("Demo Brief Details", {"fields": ("title", "description", "is_active")}),
        ("Campaign Details", {"fields": ("campaign_message",)}),
        ("Target Information", {"fields": ("target_region", "target_audience")}),
        (
            "Languages",
            {"fields": ("primary_language", "supported_languages", "translation_config")},
        ),
        (
            "Products",
            {
                "fields": ("products",),
                "description": 'JSON array of products: [{"name": "Product A", "type": "Energy Drink"}]',
            },
        ),
        ("Metadata", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def product_count(self, obj):
        """Return the number of products in this demo brief"""
        return len(obj.products) if obj.products else 0

    product_count.short_description = "Products"
