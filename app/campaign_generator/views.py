import os
import tempfile
import zipfile

from django.conf import settings
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from .ai_service import CampaignGenerator
from .forms import BriefForm, JSONBriefUploadForm
from .models import Brief, GeneratedAsset, Language


def home(request):
    """Home page with brief creation and asset gallery"""
    recent_briefs = Brief.objects.all().order_by("-created_at")[:5]
    recent_assets = GeneratedAsset.objects.all().order_by("-created_at")[:12]

    context = {
        "recent_briefs": recent_briefs,
        "recent_assets": recent_assets,
        "total_briefs": Brief.objects.count(),
        "total_assets": GeneratedAsset.objects.count(),
    }

    return render(request, "campaign_generator/home.html", context)


def create_brief(request):
    """Create new campaign brief"""
    if request.method == "POST":
        form = BriefForm(request.POST, request.FILES)

        if form.is_valid():
            brief = form.save()
            messages.success(request, f'Campaign brief "{brief.title}" created successfully!')
            return redirect("brief_detail", brief_id=brief.id)
        else:
            # Add form errors to messages for debugging
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = BriefForm()

    # Systematically prepare all example data in view layer
    # This completely decouples data logic from template presentation
    context = {
        "form": form,
        "example_data": _prepare_example_data(),
    }
    
    # Add demo briefs for "Copy to Form" functionality
    from .models import DemoBrief
    context['demo_briefs'] = DemoBrief.objects.filter(is_active=True)

    return render(request, "campaign_generator/create_brief.html", context)


def _prepare_example_data():
    """
    Prepare all example data for template.
    This function encapsulates all business logic for example data preparation,
    ensuring complete separation between view logic and template presentation.
    """
    # Get selected example languages (German and French)
    example_languages = Language.objects.filter(
        code__in=['de', 'fr'], is_active=True
    ).order_by('name')
    
    # Base example data (static content)
    base_data = {
        'title': 'Pacific Pulse Energy Drink Launch',
        'target_region': 'Pacific Coast US/Mexico border cities',
        'campaign_message': 'Natural energy that connects you to the coastal lifestyle',
        'primary_language': 'English',
        'products_json': '''[
  {
    "name": "Pacific Pulse Original",
    "type": "Energy Drink"
  },
  {
    "name": "Pacific Pulse Zero", 
    "type": "Zero-Sugar Energy Drink"
  }
]'''
    }
    
    # Dynamic language-dependent data
    if example_languages.exists():
        language_codes = '/'.join([lang.code.upper() for lang in example_languages])
        language_names = ', '.join([lang.name for lang in example_languages])
        language_ids = ','.join([str(lang.id) for lang in example_languages])
        language_codes_csv = ','.join([lang.code for lang in example_languages])  # For template use
        
        # Build complete target audience string
        target_audience = f"18-30, urban, multilingual (EN/{language_codes}), health-conscious but fun-seeking"
        
        # Build tip text
        language_list = ' + '.join(['English'] + [lang.name for lang in example_languages])
        tip_text = f"({language_list})"
    else:
        # Fallback if no additional languages
        language_names = "None"
        language_ids = ""
        language_codes_csv = ""  # Empty for no additional languages
        target_audience = "18-30, urban, multilingual, health-conscious but fun-seeking"
        tip_text = "(English only)"
    
    # Combine all prepared data
    return {
        **base_data,
        'target_audience': target_audience,
        'language_names': language_names,
        'language_ids': language_ids,
        'language_codes_csv': language_codes_csv,
        'tip_text': tip_text,
    }


def upload_brief(request):
    """Upload brief from JSON/YAML file"""
    if request.method == "POST":
        form = JSONBriefUploadForm(request.POST, request.FILES)

        if form.is_valid():
            brief = form.save()
            messages.success(request, f'Campaign brief "{brief.title}" uploaded successfully!')
            return redirect("brief_detail", brief_id=brief.id)
    else:
        form = JSONBriefUploadForm()

    return render(request, "campaign_generator/upload_brief.html", {"form": form})


def _prepare_brief_detail_context(brief, assets, sessions):
    """
    Transform brief detail model data into UI-ready context according to DECOUPLE.md patterns.
    
    Templates should know NOTHING about model structure - only UI state.
    """
    from django.urls import reverse
    
    # Transform brief data into UI-ready format
    brief_data = {
        'brief_id': str(brief.id),
        'brief_title': brief.title,
        'brief_message': brief.campaign_message,
        'target_region': brief.target_region,
        'target_audience': brief.target_audience,
        'primary_language': brief.primary_language.name,
        'additional_languages': [lang.name for lang in brief.supported_languages.all()],
        'products': brief.products,
        'expected_asset_count': brief.get_expected_asset_count(),
        'actual_asset_count': assets.count(),
        'created_date': brief.created_at.strftime("%Y-%m-%d"),
        'generate_url': reverse('generate_assets', kwargs={'brief_id': brief.id}),
        'download_url': reverse('download_assets', kwargs={'brief_id': brief.id}),
        'can_generate': True,  # Business logic for generate permission
        'can_download': assets.exists(),  # Business logic for download availability
    }
    
    # Transform assets into UI-ready format
    ui_assets = []
    for asset in assets:
        ui_asset = {
            'asset_id': str(asset.id),
            'title': asset.product_name,
            'aspect_ratio': asset.aspect_ratio,
            'language_name': asset.language.name,
            'language_code': asset.language.code.upper(),
            'thumbnail_url': asset.image_file.url if asset.image_file else '',
            'detail_url': reverse('asset_detail', kwargs={'asset_id': asset.id}),
            'download_url': asset.image_file.url if asset.image_file else '',
            'download_filename': f"{asset.product_name}_{asset.aspect_ratio}.jpg",
            'created_date': asset.created_at.strftime("%Y-%m-%d %H:%M"),
            'time_ago': asset.created_at,  # Will use timesince filter in template
            'has_image': bool(asset.image_file),
            'generation_time_seconds': asset.generation_time_seconds,
        }
        ui_assets.append(ui_asset)
    
    # Group assets by product for display
    ui_assets_by_product = {}
    for asset_data in ui_assets:
        product = asset_data['title']
        if product not in ui_assets_by_product:
            ui_assets_by_product[product] = {}
        lang_code = asset_data['language_code'].lower()
        if lang_code not in ui_assets_by_product[product]:
            ui_assets_by_product[product][lang_code] = {}
        ui_assets_by_product[product][lang_code][asset_data['aspect_ratio']] = asset_data
    
    # Transform sessions into UI-ready format
    ui_sessions = []
    for session in sessions:
        ui_session = {
            'session_id': str(session.id),
            'started_date': session.started_at.strftime("%Y-%m-%d %H:%M"),
            'completed_date': session.completed_at.strftime("%Y-%m-%d %H:%M") if session.completed_at else None,
            'status': session.status,
            'is_completed': session.status == 'completed',
            'is_failed': session.status == 'failed',
            'is_running': session.status == 'running',
            'progress_text': f"{session.completed_assets}/{session.total_assets}" if session.total_assets else "Starting...",
        }
        ui_sessions.append(ui_session)
    
    return {
        **brief_data,
        'assets': ui_assets,
        'assets_by_product': ui_assets_by_product,
        'sessions': ui_sessions,
    }


def brief_detail(request, brief_id):
    """Display brief details and generated assets"""
    brief = get_object_or_404(Brief, id=brief_id)
    assets = brief.generated_assets.all().order_by("product_name", "language__name", "aspect_ratio")
    sessions = brief.generation_sessions.all().order_by("-started_at")

    # Use helper function to transform model data into UI-ready context
    context = _prepare_brief_detail_context(brief, assets, sessions)

    return render(request, "campaign_generator/brief_detail.html", context)


def generate_assets(request, brief_id):
    """Generate campaign assets for a brief"""
    brief = get_object_or_404(Brief, id=brief_id)

    if request.method == "POST":
        try:
            # Check if OpenAI API key is configured
            if not getattr(settings, "OPENAI_API_KEY", None):
                messages.error(
                    request,
                    "OpenAI API key not configured. Please set OPENAI_API_KEY environment variable.",
                )
                return redirect("brief_detail", brief_id=brief.id)

            # Estimate cost and warn user
            expected_assets = brief.get_expected_asset_count()
            estimated_cost = expected_assets * 0.040  # DALL-E 3 cost estimate
            if estimated_cost > 1.0:  # Warn if cost > $1
                messages.warning(
                    request,
                    f"Estimated cost for this generation: ${estimated_cost:.2f}. "
                    f"Make sure you have sufficient OpenAI credits.",
                )

            # Generate assets
            generator = CampaignGenerator()
            assets = generator.generate_campaign_assets(brief)

            messages.success(request, f"Generated {len(assets)} campaign assets successfully!")

            # Return JSON for AJAX requests
            if request.headers.get("Content-Type") == "application/json":
                return JsonResponse(
                    {
                        "success": True,
                        "message": f"Generated {len(assets)} assets",
                        "asset_count": len(assets),
                    }
                )

        except Exception as e:
            error_msg = f"Generation failed: {str(e)}"
            messages.error(request, error_msg)

            if request.headers.get("Content-Type") == "application/json":
                return JsonResponse({"success": False, "error": error_msg})

    return redirect("brief_detail", brief_id=brief.id)


def asset_detail(request, asset_id):
    """Display individual asset details"""
    asset = get_object_or_404(GeneratedAsset, id=asset_id)

    # Get related assets (same brief, different aspect ratios)
    related_assets = GeneratedAsset.objects.filter(
        brief=asset.brief, product_name=asset.product_name
    ).exclude(id=asset.id)

    context = {
        "asset": asset,
        "related_assets": related_assets,
    }

    return render(request, "campaign_generator/asset_detail.html", context)


def download_assets(request, brief_id):
    """Download all assets for a brief as organized ZIP file"""
    brief = get_object_or_404(Brief, id=brief_id)
    assets = brief.generated_assets.all()

    if not assets.exists():
        messages.error(request, "No assets found for this brief.")
        return redirect("brief_detail", brief_id=brief.id)

    # Create temporary ZIP file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as temp_zip:
        with zipfile.ZipFile(temp_zip, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for asset in assets:
                if asset.image_file and os.path.exists(asset.image_file.path):
                    # Use organized folder structure in ZIP
                    folder_path = f"{asset.organized_folder}/"
                    filename = f"campaign_{asset.id}.jpg"
                    zip_path = folder_path + filename

                    zip_file.write(asset.image_file.path, zip_path)

            # Add brief info as JSON
            import json

            brief_info = {
                "title": brief.title,
                "target_region": brief.target_region,
                "target_audience": brief.target_audience,
                "campaign_message": brief.campaign_message,
                "products": brief.products,
                "generated_assets": len(assets),
                "created_at": brief.created_at.isoformat(),
            }

            zip_file.writestr("brief_info.json", json.dumps(brief_info, indent=2))

    # Serve ZIP file
    with open(temp_zip.name, "rb") as zip_data:
        response = HttpResponse(zip_data.read(), content_type="application/zip")
        response["Content-Disposition"] = f'attachment; filename="{brief.title}_assets.zip"'

    # Clean up temp file
    os.unlink(temp_zip.name)

    return response


def _prepare_gallery_context(assets, ordered_languages, aspect_ratio_filter, brief_filter, language_filter):
    """
    Transform model data into UI-ready context according to DECOUPLE.md patterns.
    
    Templates should know NOTHING about model structure - only UI state.
    """
    from django.urls import reverse
    
    # Group assets by language for display
    assets_by_language = {}
    for asset in assets:
        lang_code = asset.language.code
        if lang_code not in assets_by_language:
            assets_by_language[lang_code] = {
                'language': asset.language,
                'assets': []
            }
        assets_by_language[lang_code]['assets'].append(asset)

    # Transform to UI-ready data structure
    ui_language_groups = []
    for lang in ordered_languages:
        if lang.code in assets_by_language:
            # Transform assets into UI-ready format
            ui_assets = []
            for asset in assets_by_language[lang.code]['assets']:
                ui_asset = {
                    'asset_id': str(asset.id),  # Ensure string for URL building
                    'title': asset.product_name,
                    'thumbnail_url': asset.image_file.url if asset.image_file else '',
                    'detail_url': reverse('asset_detail', kwargs={'asset_id': asset.id}) if asset.id else '',
                    'download_url': asset.image_file.url if asset.image_file else '',
                    'download_filename': f"{asset.product_name}_{asset.aspect_ratio}.jpg",
                    'aspect_ratio_badge': asset.aspect_ratio,
                    'lang_code_badge': asset.language.code.upper(),
                    'brief_title': asset.brief.title,
                    'brief_url': reverse('brief_detail', kwargs={'brief_id': asset.brief.id}) if asset.brief.id else '',
                    'created_date': asset.created_at.strftime("%Y-%m-%d %H:%M"),
                    'time_ago': asset.created_at,  # Will use timesince filter in template
                    'has_image': bool(asset.image_file),
                }
                ui_assets.append(ui_asset)
            
            # Transform language group into UI-ready format
            ui_group = {
                'lang_name': lang.name,
                'lang_code': lang.code,
                'lang_native': lang.native_name,
                'lang_direction_badge': lang.get_direction_display() if lang.direction != 'ltr' else '',
                'show_direction_badge': lang.direction != 'ltr',
                'show_native_name': lang.native_name != lang.name,
                'count': len(ui_assets),
                'assets': ui_assets,
                # Direction flags for styling
                'lang_rtl': lang.direction == 'rtl',
                'lang_ttb': lang.direction == 'ttb', 
                'lang_ltr': lang.direction == 'ltr',
            }
            ui_language_groups.append(ui_group)
    
    # Prepare filter data as UI-ready lists
    aspect_ratios = []
    for ratio_value, ratio_label in GeneratedAsset.ASPECT_RATIOS:
        aspect_ratios.append({
            'value': ratio_value,
            'label': ratio_label,
            'is_selected': aspect_ratio_filter == ratio_value
        })
    
    briefs = []
    for brief in Brief.objects.all().order_by("-created_at"):
        briefs.append({
            'id': brief.id,
            'title': brief.title,
            'is_selected': brief_filter == str(brief.id)
        })
    
    languages = []
    for lang in ordered_languages:
        languages.append({
            'code': lang.code,
            'name': lang.name,
            'is_selected': language_filter == lang.code
        })
    
    return {
        'assets_by_language': ui_language_groups,
        'aspect_ratios': aspect_ratios,
        'briefs': briefs,
        'languages': languages,
        'selected_aspect_ratio': aspect_ratio_filter,
        'selected_brief': brief_filter,
        'selected_language': language_filter,
    }


def gallery(request):
    """Gallery view of all generated assets with dynamic language grouping"""
    assets = GeneratedAsset.objects.select_related('language', 'brief').all().order_by("-created_at")

    # Filter by aspect ratio if requested
    aspect_ratio_filter = request.GET.get("aspect_ratio")
    if aspect_ratio_filter:
        assets = assets.filter(aspect_ratio=aspect_ratio_filter)

    # Filter by brief if requested
    brief_filter = request.GET.get("brief")
    if brief_filter:
        assets = assets.filter(brief_id=brief_filter)

    # Filter by language if requested
    language_filter = request.GET.get("language")
    if language_filter:
        assets = assets.filter(language__code=language_filter)

    # Get all languages that have assets, ordered with English first
    languages_with_assets = Language.objects.filter(
        generatedasset__in=assets
    ).distinct().order_by('code')
    
    # Ensure English is first if it exists
    english_lang = None
    other_langs = []
    
    for lang in languages_with_assets:
        if lang.code == 'en':
            english_lang = lang
        else:
            other_langs.append(lang)
    
    # Build the ordered language list
    ordered_languages = []
    if english_lang:
        ordered_languages.append(english_lang)
    ordered_languages.extend(sorted(other_langs, key=lambda x: x.name))

    # Use helper function to transform model data into UI-ready context
    context = _prepare_gallery_context(
        assets=assets,
        ordered_languages=ordered_languages,
        aspect_ratio_filter=aspect_ratio_filter,
        brief_filter=brief_filter,
        language_filter=language_filter
    )

    return render(request, "campaign_generator/gallery.html", context)


def api_brief_status(request, brief_id):
    """API endpoint for checking brief generation status (for real-time updates)"""
    brief = get_object_or_404(Brief, id=brief_id)

    latest_session = brief.generation_sessions.order_by("-started_at").first()

    data = {
        "brief_id": brief.id,
        "title": brief.title,
        "expected_assets": brief.get_expected_asset_count(),
        "generated_assets": brief.generated_assets.count(),
        "is_generating": latest_session and not latest_session.completed_at
        if latest_session
        else False,
        "last_generation": {
            "success": latest_session.success,
            "started_at": latest_session.started_at.isoformat(),
            "completed_at": latest_session.completed_at.isoformat()
            if latest_session.completed_at
            else None,
            "assets_generated": latest_session.assets_generated,
            "total_time": latest_session.total_generation_time,
            "estimated_cost": float(latest_session.estimated_cost_usd)
            if latest_session.estimated_cost_usd
            else None,
        }
        if latest_session
        else None,
    }

    return JsonResponse(data)
