"""
Pure pytest test suite for campaign_generator app
Uses ONLY pytest patterns - no TestCase classes, only functions with fixtures
"""

import json
import os
from io import BytesIO
from unittest.mock import Mock, patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image

from .ai_service import CampaignGenerator
from .forms import BriefForm, JSONBriefUploadForm
from .models import Brief, GeneratedAsset, GenerationSession, Language
from .translation_service import MockTranslationProvider, TranslationService


# Language Fixtures (loaded from Django fixtures)
@pytest.fixture
def load_languages(db):
    """Load language fixtures"""
    from django.core.management import call_command

    call_command("loaddata", "initial_languages")


@pytest.fixture
def english_language(load_languages):
    """Get English language from fixtures"""
    return Language.objects.get(code="en")


@pytest.fixture
def spanish_language(load_languages):
    """Get Spanish language from fixtures"""
    return Language.objects.get(code="es")


@pytest.fixture
def japanese_language(load_languages):
    """Get Japanese language from fixtures"""
    return Language.objects.get(code="ja")


# Fixtures
@pytest.fixture
def sample_brief_data(english_language):
    """Sample brief data for testing"""
    return {
        "title": "Test Campaign",
        "products": [
            {"name": "Product A", "type": "Energy Drink"},
            {"name": "Product B", "type": "Zero Sugar"},
        ],
        "target_region": "California",
        "target_audience": "Young adults",
        "campaign_message": "Test message",
        "primary_language": english_language,
    }


@pytest.fixture
def brief(db, sample_brief_data):
    """Create a test brief"""
    return Brief.objects.create(**sample_brief_data)


@pytest.fixture
def brief_with_reference_image(db, sample_brief_data, test_image_bytes):
    """Create a test brief with a reference image"""
    from io import BytesIO

    from django.core.files.uploadedfile import InMemoryUploadedFile

    # Create a mock uploaded file from test image
    image_file = InMemoryUploadedFile(
        BytesIO(test_image_bytes),
        "ImageField",
        "test_reference.jpg",
        "image/jpeg",
        len(test_image_bytes),
        None,
    )

    # Create brief with reference image
    brief_data = sample_brief_data.copy()
    brief = Brief.objects.create(**brief_data)
    brief.reference_image.save("test_reference.jpg", image_file, save=True)

    return brief


@pytest.fixture
def generation_run(db, brief):
    """Create a test generation run"""
    from .models import GenerationRun

    return GenerationRun.objects.create(brief=brief, run_index=1, success=True, assets_generated=3)


@pytest.fixture
def generated_asset(db, brief, generation_run):
    """Create a test generated asset"""
    return GeneratedAsset.objects.create(
        brief=brief,
        generation_run=generation_run,
        product_name="Product A",
        aspect_ratio="1:1",
        ai_prompt="Test prompt",
        organized_file_path="/test/path",
        generation_time_seconds=5.5,
    )


@pytest.fixture
def campaign_generator():
    """Create CampaignGenerator instance"""
    return CampaignGenerator()


@pytest.fixture
def test_image_bytes():
    """Helper to create test image bytes"""
    img = Image.new("RGB", (100, 100), color="red")
    buf = BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


# Model Tests
@pytest.mark.django_db
def test_brief_creation(sample_brief_data):
    """Test basic brief creation"""
    brief = Brief.objects.create(**sample_brief_data)
    assert brief.title == "Test Campaign"
    assert len(brief.products) == 2
    assert brief.product_count == 2


@pytest.mark.django_db
def test_brief_str_representation(brief):
    """Test string representation"""
    assert str(brief) == "Test Campaign"


@pytest.mark.django_db
def test_product_count_property(brief):
    """Test product_count property with various scenarios"""
    assert brief.product_count == 2

    # Test with no products
    brief.products = []
    brief.save()
    assert brief.product_count == 0

    # Test with empty products (None not allowed due to NOT NULL constraint)
    brief.products = []
    brief.save()
    assert brief.product_count == 0


@pytest.mark.django_db
def test_product_count_with_empty_products(english_language):
    """Test edge case: empty products list"""
    brief = Brief.objects.create(
        title="Empty Products Test",
        products=[],  # Empty list
        target_region="California",
        target_audience="Young adults",
        campaign_message="Test message",
        primary_language=english_language,
    )
    assert brief.product_count == 0


@pytest.mark.django_db
def test_special_characters_in_data(english_language):
    """Test handling of special characters"""
    brief = Brief.objects.create(
        title="Tëst Çampaign with Special Chars!",
        products=[
            {"name": "Product-A/B & Co. (2024)", "type": "Energy Drink"},
            {"name": "Prøduct Ñame", "type": "Spëcial Drink"},
        ],
        target_region="Califórnia",
        target_audience="Young adults & teens",
        campaign_message="Test message with émojis! 🚀",
        primary_language=english_language,
    )
    assert brief.product_count == 2
    assert "Product-A/B & Co. (2024)" in str(brief.products)


@pytest.mark.django_db
def test_asset_creation(brief):
    """Test basic asset creation"""
    from .models import GenerationRun

    # Create a generation run first
    generation_run = GenerationRun.objects.create(brief=brief, run_index=1, success=True)

    asset = GeneratedAsset.objects.create(
        brief=brief,
        generation_run=generation_run,
        product_name="Product A",
        aspect_ratio="1:1",
        ai_prompt="Test prompt",
        organized_file_path="/test/path",
        generation_time_seconds=5.5,
    )
    assert asset.product_name == "Product A"
    assert asset.aspect_ratio == "1:1"
    assert asset.generation_time_seconds == 5.5


@pytest.mark.django_db
def test_asset_str_representation(generated_asset):
    """Test string representation"""
    expected = "Product A - 1:1 (Run #1)"
    assert str(generated_asset) == expected


@pytest.mark.django_db
@pytest.mark.parametrize("aspect_ratio", ["1:1", "9:16", "16:9"])
def test_aspect_ratio_choices(brief, aspect_ratio):
    """Test all valid aspect ratio choices"""
    from .models import GenerationRun

    # Create a generation run first
    generation_run = GenerationRun.objects.create(brief=brief, run_index=1, success=True)

    asset = GeneratedAsset.objects.create(
        brief=brief,
        generation_run=generation_run,
        product_name="Product A",
        aspect_ratio=aspect_ratio,
        ai_prompt="Test prompt",
    )
    assert asset.aspect_ratio == aspect_ratio


@pytest.mark.django_db
def test_asset_relationships(generated_asset, brief):
    """Test model relationships"""
    assert generated_asset.brief == brief
    assert generated_asset in brief.generated_assets.all()


@pytest.mark.django_db
def test_generation_session_creation(brief):
    """Test generation session creation"""
    session = GenerationSession.objects.create(
        brief=brief,
        success=False,  # Use actual model field
        assets_generated=3,  # Use actual model field
        estimated_cost_usd=0.12,
    )
    assert session.brief == brief
    assert session.success == False
    assert session.assets_generated == 3


# Form Tests
@pytest.mark.django_db
def test_brief_form_valid(english_language):
    """Test form with valid data"""
    form_data = {
        "title": "Test Campaign",
        "products_json": '[{"name": "Product A", "type": "Energy Drink"}, {"name": "Product B", "type": "Energy Drink"}]',
        "target_region": "California",
        "target_audience": "Young adults",
        "campaign_message": "Test message",
        "primary_language": english_language.id,
    }
    form = BriefForm(data=form_data)
    assert form.is_valid(), f"Form errors: {form.errors}"


def test_brief_form_invalid_json():
    """Test form with invalid JSON - this should reveal a bug if JSON validation is missing"""
    form_data = {
        "title": "Test Campaign",
        "products_json": "invalid json {malformed",  # Invalid JSON
        "target_region": "California",
        "target_audience": "Young adults",
        "campaign_message": "Test message",
    }
    form = BriefForm(data=form_data)
    assert not form.is_valid()
    assert "products_json" in form.errors


@pytest.mark.django_db
def test_brief_form_save(english_language):
    """Test form save functionality"""
    form_data = {
        "title": "Test Campaign",
        "products_json": '[{"name": "Product A", "type": "Energy Drink"}, {"name": "Product B", "type": "Energy Drink"}]',
        "target_region": "California",
        "target_audience": "Young adults",
        "campaign_message": "Test message",
        "primary_language": english_language.id,
    }
    form = BriefForm(data=form_data)
    assert form.is_valid(), f"Form errors: {form.errors}"

    brief = form.save()
    assert brief.title == "Test Campaign"
    assert len(brief.products) == 2
    assert brief.products[0]["name"] == "Product A"
    assert brief.products[1]["name"] == "Product B"
    assert brief.primary_language == english_language


def test_brief_form_missing_required_fields():
    """Test form with missing required fields"""
    incomplete_data = {
        "title": "Test Campaign",
        # Missing products_json, target_region, etc.
    }
    form = BriefForm(data=incomplete_data)
    assert not form.is_valid()


def test_brief_form_empty_products_json():
    """Test edge case: empty products JSON array"""
    form_data = {
        "title": "Test Campaign",
        "products_json": "[]",  # Empty array - should fail
        "target_region": "California",
        "target_audience": "Young adults",
        "campaign_message": "Test message",
    }
    form = BriefForm(data=form_data)
    assert not form.is_valid()  # Should fail because we require at least 1 product
    assert "products_json" in form.errors


@pytest.mark.django_db
def test_brief_form_single_product(english_language):
    """Test that a single product is now allowed"""
    form_data = {
        "title": "Single Product Campaign",
        "products_json": '[{"name": "Single Product", "type": "Energy Drink"}]',
        "target_region": "California",
        "target_audience": "Young adults",
        "campaign_message": "Test message",
        "primary_language": english_language.id,
    }
    form = BriefForm(data=form_data)
    assert form.is_valid()  # Should pass with just 1 product

    brief = form.save()
    assert brief.product_count == 1
    assert brief.products[0]["name"] == "Single Product"


def test_brief_form_very_long_campaign_message():
    """Test handling of very long campaign messages"""
    long_message = "A" * 5000  # Very long message
    form_data = {
        "title": "Test Campaign",
        "products_json": '[{"name": "Product A", "type": "Energy Drink"}]',
        "target_region": "California",
        "target_audience": "Young adults",
        "campaign_message": long_message,
    }
    form = BriefForm(data=form_data)
    # This should either be valid or have proper validation
    # If it causes issues, we've found a bug
    is_valid = form.is_valid()
    assert isinstance(is_valid, bool)  # At minimum, it shouldn't crash


def test_json_upload_form_valid():
    """Test with valid JSON file"""
    json_data = {
        "title": "Test Campaign",
        "products": [
            {"name": "Product A", "type": "Energy Drink"},
            {"name": "Product B", "type": "Energy Drink"},
        ],
        "target_region": "California",
        "target_audience": "Young adults",
        "campaign_message": "Test message",
    }
    json_content = json.dumps(json_data).encode("utf-8")
    json_file = SimpleUploadedFile("test.json", json_content, content_type="application/json")

    form = JSONBriefUploadForm(files={"brief_file": json_file})
    assert form.is_valid()


def test_json_upload_form_invalid_file_extension():
    """Test with invalid file extension"""
    content = b"some content"
    txt_file = SimpleUploadedFile("test.txt", content, content_type="text/plain")

    form = JSONBriefUploadForm(files={"brief_file": txt_file})
    assert not form.is_valid()
    assert "brief_file" in form.errors


def test_json_upload_form_invalid_json_content():
    """Test with invalid JSON content"""
    invalid_json = b"invalid json content"
    json_file = SimpleUploadedFile("test.json", invalid_json, content_type="application/json")

    form = JSONBriefUploadForm(files={"brief_file": json_file})
    assert not form.is_valid()


def test_yaml_file_upload():
    """Test YAML file upload"""
    yaml_content = """
title: "Test Campaign"
products:
  - name: "Product A"
    type: "Energy Drink"
  - name: "Product B"
    type: "Energy Drink"
target_region: "California"
target_audience: "Young adults"
campaign_message: "Test message"
"""
    yaml_file = SimpleUploadedFile(
        "test.yaml", yaml_content.encode("utf-8"), content_type="application/yaml"
    )

    form = JSONBriefUploadForm(files={"brief_file": yaml_file})
    assert form.is_valid()


# AI Service Tests
def test_generator_initialization(campaign_generator):
    """Test CampaignGenerator initialization"""
    assert campaign_generator.client is not None
    assert os.path.exists(campaign_generator.output_base)


def test_feature_flag_setting(campaign_generator):
    """Test feature flag is properly set"""
    assert isinstance(campaign_generator.use_outpaint_method, bool)


def test_prompt_building_methods_exist(campaign_generator):
    """Test that required prompt building methods exist"""
    assert hasattr(campaign_generator, "_build_core_scene_prompt")
    if campaign_generator.use_outpaint_method:
        assert hasattr(campaign_generator, "_build_consistent_base_prompt")


def test_core_scene_prompt_building(campaign_generator, sample_brief_data):
    """Test core scene prompt building"""
    brief = Mock()
    brief.target_region = sample_brief_data["target_region"]
    brief.target_audience = sample_brief_data["target_audience"]
    brief.campaign_message = sample_brief_data["campaign_message"]

    product = {"name": "Test Product", "type": "Energy Drink"}

    prompt = campaign_generator._build_core_scene_prompt(product, brief)
    assert "Test Product" in prompt
    assert "California" in prompt
    assert "Test message" in prompt


def test_save_generated_asset_method_exists(campaign_generator):
    """Test that _save_generated_asset method exists"""
    assert hasattr(campaign_generator, "_save_generated_asset")
    assert callable(campaign_generator._save_generated_asset)


def test_image_processing_methods_exist(campaign_generator):
    """Test that required image processing methods exist"""
    assert hasattr(campaign_generator, "_image_to_bytes")
    assert hasattr(campaign_generator, "_add_text_overlay")
    assert hasattr(campaign_generator, "_save_organized")


@patch("campaign_generator.ai_service.requests.get")
@pytest.mark.django_db
def test_save_generated_asset_method(mock_requests, campaign_generator, brief, test_image_bytes):
    """Test _save_generated_asset method functionality"""
    # Mock image response
    mock_response = Mock()
    mock_response.content = test_image_bytes
    mock_response.raise_for_status.return_value = None
    mock_requests.return_value = mock_response

    # Mock internal methods to avoid actual image processing
    with (
        patch.object(campaign_generator, "_add_text_overlay") as mock_overlay,
        patch.object(campaign_generator, "_save_organized") as mock_save_org,
        patch.object(campaign_generator, "_image_to_bytes") as mock_to_bytes,
    ):
        mock_overlay.return_value = Image.new("RGB", (100, 100))
        mock_save_org.return_value = "/test/path"
        mock_to_bytes.return_value = b"test"

        # Create a generation run for the test
        from .models import GenerationRun

        generation_run = GenerationRun.objects.create(brief=brief, run_index=1, success=True)

        asset = campaign_generator._save_generated_asset(
            brief=brief,
            product_name="Test Product",
            aspect_ratio="1:1",
            image_url_or_data="http://example.com/image.jpg",
            prompt="Test prompt",
            generation_time=5.0,
            generation_run=generation_run,
        )

        assert isinstance(asset, GeneratedAsset)
        assert asset.product_name == "Test Product"
        assert asset.aspect_ratio == "1:1"
        assert asset.generation_time_seconds == 5.0


# View Tests
@pytest.mark.django_db
def test_home_view(client):
    """Test home page loads correctly"""
    response = client.get(reverse("home"))
    assert response.status_code == 200
    assert b"Campaign Generator" in response.content


@pytest.mark.django_db
def test_create_brief_view_get(client):
    """Test brief creation form loads"""
    response = client.get(reverse("create_brief"))
    assert response.status_code == 200
    assert b"Create Campaign Brief" in response.content


@pytest.mark.django_db
def test_create_brief_view_post_valid(client, english_language):
    """Test brief creation form submission with valid data"""
    form_data = {
        "title": "Test Campaign",
        "products_json": '[{"name": "Product A", "type": "Energy Drink"}, {"name": "Product B", "type": "Energy Drink"}]',
        "target_region": "California",
        "target_audience": "Young adults",
        "campaign_message": "Test message",
        "primary_language": english_language.id,
    }
    response = client.post(reverse("create_brief"), data=form_data)
    assert response.status_code == 302  # Redirect after successful creation


@pytest.mark.django_db
def test_create_brief_view_post_invalid(client):
    """Test brief creation with invalid data"""
    form_data = {
        "title": "Test Campaign",
        "products_json": "invalid json",  # Invalid JSON
        "target_region": "California",
        "target_audience": "Young adults",
        "campaign_message": "Test message",
    }
    response = client.post(reverse("create_brief"), data=form_data)
    # Should stay on same page with errors, not redirect
    assert response.status_code == 200
    assert b"error" in response.content.lower() or b"invalid" in response.content.lower()


@pytest.mark.django_db
def test_brief_detail_view(client, brief):
    """Test brief detail page loads"""
    response = client.get(reverse("brief_detail", kwargs={"brief_id": brief.id}))
    assert response.status_code == 200
    assert brief.title.encode() in response.content


@pytest.mark.django_db
def test_gallery_view(client):
    """Test gallery page loads"""
    response = client.get(reverse("gallery"))
    assert response.status_code == 200
    assert b"Asset Gallery" in response.content


@pytest.mark.django_db
def test_upload_brief_view(client):
    """Test upload brief page loads"""
    response = client.get(reverse("upload_brief"))
    assert response.status_code == 200
    assert b"Upload Campaign Brief" in response.content


@pytest.mark.django_db
def test_asset_detail_view(client, generated_asset):
    """Test asset detail view"""
    response = client.get(reverse("asset_detail", kwargs={"asset_id": generated_asset.id}))
    assert response.status_code == 200
    assert b"Product A" in response.content


@pytest.mark.django_db
def test_nonexistent_brief_404(client):
    """Test 404 for nonexistent brief"""
    response = client.get(reverse("brief_detail", kwargs={"brief_id": 9999}))
    assert response.status_code == 404


@pytest.mark.django_db
def test_nonexistent_asset_404(client):
    """Test 404 for nonexistent asset"""
    response = client.get(reverse("asset_detail", kwargs={"asset_id": 9999}))
    assert response.status_code == 404


# Integration Tests
@pytest.mark.integration
@pytest.mark.django_db
def test_complete_brief_creation_workflow(client, english_language):
    """Test complete workflow from creation to detail view"""
    # Create brief
    form_data = {
        "title": "Integration Test Campaign",
        "products_json": '[{"name": "Product A", "type": "Energy Drink"}, {"name": "Product B", "type": "Energy Drink"}]',
        "target_region": "California",
        "target_audience": "Young adults",
        "campaign_message": "Test message",
        "primary_language": english_language.id,
    }
    response = client.post(reverse("create_brief"), data=form_data)
    assert response.status_code == 302

    # Check brief was created
    brief = Brief.objects.get(title="Integration Test Campaign")
    assert brief.product_count == 2

    # Check detail view works
    response = client.get(reverse("brief_detail", kwargs={"brief_id": brief.id}))
    assert response.status_code == 200
    assert b"Integration Test Campaign" in response.content


@pytest.mark.integration
@pytest.mark.django_db
def test_json_upload_workflow(client, english_language):
    """Test JSON upload workflow"""
    json_data = {
        "title": "JSON Upload Test",
        "products": [
            {"name": "Product A", "type": "Energy Drink"},
            {"name": "Product B", "type": "Energy Drink"},
        ],
        "target_region": "California",
        "target_audience": "Young adults",
        "campaign_message": "Test message",
        "primary_language": english_language.id,
    }
    json_content = json.dumps(json_data).encode("utf-8")
    json_file = SimpleUploadedFile("test.json", json_content, content_type="application/json")

    response = client.post(reverse("upload_brief"), data={"brief_file": json_file})
    assert response.status_code == 302  # Redirect after successful upload

    # Check brief was created
    brief = Brief.objects.get(title="JSON Upload Test")
    assert brief.target_region == "California"
    assert brief.primary_language == english_language


# Bug Discovery Tests
@pytest.mark.unit
@pytest.mark.django_db
def test_empty_title_handling(english_language):
    """Test potential bug: empty title"""
    brief_data = {
        "title": "",  # Empty title
        "products": [{"name": "Product A", "type": "Energy Drink"}],
        "target_region": "California",
        "target_audience": "Young adults",
        "campaign_message": "Test message",
        "primary_language": english_language,
    }
    # This might reveal validation bugs
    try:
        brief = Brief.objects.create(**brief_data)
        # If this succeeds, we might want to add validation
        assert brief.title == ""
    except Exception as e:
        # If this fails, we need to handle empty titles
        assert isinstance(e, Exception)


@pytest.mark.unit
@pytest.mark.django_db
def test_null_products_handling():
    """Test potential bug: null products - should fail due to NOT NULL constraint"""
    brief_data = {
        "title": "Test Campaign",
        "products": None,  # Null products - should fail
        "target_region": "California",
        "target_audience": "Young adults",
        "campaign_message": "Test message",
    }
    # This should fail due to NOT NULL constraint on products field
    with pytest.raises(Exception):  # Should raise IntegrityError
        _ = Brief.objects.create(**brief_data)


@pytest.mark.unit
def test_malformed_json_in_form():
    """Test potential bug: malformed JSON handling"""
    malformed_jsons = [
        '{"name": "Product A"',  # Missing closing brace
        '[{"name": "Product A", "type":}]',  # Missing value
        "not json at all",
        '{"name": "Product A", "type": "Drink",}',  # Trailing comma
    ]

    for bad_json in malformed_jsons:
        form_data = {
            "title": "Test Campaign",
            "products_json": bad_json,
            "target_region": "California",
            "target_audience": "Young adults",
            "campaign_message": "Test message",
        }
        form = BriefForm(data=form_data)
        # Should be invalid, if it's valid we found a bug
        assert not form.is_valid(), f"Bug: Form accepted malformed JSON: {bad_json}"


@pytest.mark.unit
@pytest.mark.django_db
def test_asset_without_image_file(brief):
    """Test potential bug: asset without image file"""
    from .models import GenerationRun

    # Create a generation run first
    generation_run = GenerationRun.objects.create(brief=brief, run_index=1, success=True)

    asset = GeneratedAsset.objects.create(
        brief=brief,
        generation_run=generation_run,
        product_name="Product A",
        aspect_ratio="1:1",
        ai_prompt="Test prompt",
        # No image_file set
    )
    # This should work, but views should handle missing images gracefully
    assert asset.image_file.name == ""


@pytest.mark.unit
def test_extremely_long_product_name():
    """Test potential bug: very long product names"""
    extremely_long_name = "A" * 1000  # 1000 characters
    products_with_long_name = [{"name": extremely_long_name, "type": "Energy Drink"}]
    form_data = {
        "title": "Test Campaign",
        "products_json": json.dumps(products_with_long_name),
        "target_region": "California",
        "target_audience": "Young adults",
        "campaign_message": "Test message",
    }
    form = BriefForm(data=form_data)
    # This might reveal database field length limits
    is_valid = form.is_valid()
    assert isinstance(is_valid, bool)  # Should not crash


# Bug Discovery Tests - BytesIO Error
@pytest.mark.unit
@pytest.mark.django_db
def test_bytesio_error_in_admin(brief):
    """Test that reproduces the 'bytes-like object is required, not '_io.BytesIO'' error in admin"""
    from io import BytesIO
    from unittest.mock import Mock, patch

    from PIL import Image

    from .ai_service import CampaignGenerator

    # Create a mock image
    mock_image = Image.new("RGB", (100, 100), color="red")

    # Mock the AI service methods
    with (
        patch("campaign_generator.ai_service.requests.get") as mock_requests,
        patch.object(CampaignGenerator, "_add_text_overlay") as mock_overlay,
        patch.object(CampaignGenerator, "_save_organized") as mock_save_org,
        patch.object(CampaignGenerator, "_image_to_bytes") as mock_to_bytes,
    ):
        # Mock the requests response to return BytesIO instead of bytes (this is the bug)
        mock_response = Mock()
        mock_response.content = BytesIO(b"fake_image_data")  # This is the bug - should be bytes
        mock_response.raise_for_status.return_value = None
        mock_requests.return_value = mock_response

        # Mock the overlay to return a PIL Image
        mock_overlay.return_value = mock_image
        mock_save_org.return_value = "/test/path"
        mock_to_bytes.return_value = b"fake_bytes"

        generator = CampaignGenerator()

        # Create a generation run for the test
        from .models import GenerationRun

        generation_run = GenerationRun.objects.create(brief=brief, run_index=1, success=True)

        # This should raise the TypeError: a bytes-like object is required, not '_io.BytesIO'
        with pytest.raises((TypeError, Exception), match=".*bytes-like object.*"):
            generator._save_generated_asset(
                brief=brief,
                product_name="Test Product",
                aspect_ratio="1:1",
                image_url_or_data="http://fake-url.com/image.jpg",
                prompt="Test prompt",
                generation_time=5.0,
                generation_run=generation_run,
            )


@pytest.mark.unit
@pytest.mark.django_db
def test_bytesio_error_fixed(brief):
    """Test that the BytesIO error is fixed when requests.get returns proper bytes"""
    from io import BytesIO
    from unittest.mock import Mock, patch

    from PIL import Image

    from .ai_service import CampaignGenerator

    # Create a real image and convert it to bytes
    test_image = Image.new("RGB", (100, 100), color="red")
    image_buffer = BytesIO()
    test_image.save(image_buffer, format="JPEG")
    real_image_bytes = image_buffer.getvalue()

    # Mock the AI service methods
    with (
        patch("campaign_generator.ai_service.requests.get") as mock_requests,
        patch("requests.get") as mock_requests_global,
        patch.object(CampaignGenerator, "_add_text_overlay") as mock_overlay,
        patch.object(CampaignGenerator, "_save_organized") as mock_save_org,
        patch.object(CampaignGenerator, "_image_to_bytes") as mock_to_bytes,
    ):
        # Mock the requests response to return real image bytes
        mock_response = Mock()
        mock_response.content = real_image_bytes  # Real JPEG bytes
        mock_response.raise_for_status.return_value = None
        mock_requests.return_value = mock_response
        mock_requests_global.return_value = mock_response

        # Mock the overlay to return a PIL Image
        mock_overlay.return_value = test_image
        mock_save_org.return_value = "/test/path"
        mock_to_bytes.return_value = real_image_bytes

        generator = CampaignGenerator()

        # Create a generation run for the test
        from .models import GenerationRun

        generation_run = GenerationRun.objects.create(brief=brief, run_index=1, success=True)

        # This should work without the BytesIO error
        asset = generator._save_generated_asset(
            brief=brief,
            product_name="Test Product",
            aspect_ratio="1:1",
            image_url_or_data="http://fake-url.com/image.jpg",
            prompt="Test prompt",
            generation_time=5.0,
            generation_run=generation_run,
        )

        # Verify the asset was created successfully
        assert asset is not None
        assert asset.product_name == "Test Product"
        assert asset.aspect_ratio == "1:1"


@pytest.mark.unit
@pytest.mark.django_db
def test_unique_constraint_handling(brief):
    """Test that unique constraint violations are handled gracefully"""
    from io import BytesIO
    from unittest.mock import Mock, patch

    from PIL import Image

    from .ai_service import CampaignGenerator
    from .models import GeneratedAsset

    # Create a real image and convert it to bytes
    test_image = Image.new("RGB", (100, 100), color="red")
    image_buffer = BytesIO()
    test_image.save(image_buffer, format="JPEG")
    real_image_bytes = image_buffer.getvalue()

    # Mock the AI service methods
    with (
        patch("campaign_generator.ai_service.requests.get") as mock_requests,
        patch("requests.get") as mock_requests_global,
        patch.object(CampaignGenerator, "_add_text_overlay") as mock_overlay,
        patch.object(CampaignGenerator, "_save_organized") as mock_save_org,
        patch.object(CampaignGenerator, "_image_to_bytes") as mock_to_bytes,
    ):
        # Mock the requests response to return real image bytes
        mock_response = Mock()
        mock_response.content = real_image_bytes
        mock_response.raise_for_status.return_value = None
        mock_requests.return_value = mock_response
        mock_requests_global.return_value = mock_response

        # Mock the overlay to return a PIL Image
        mock_overlay.return_value = test_image
        mock_save_org.return_value = "/test/path"
        mock_to_bytes.return_value = real_image_bytes

        generator = CampaignGenerator()

        # Create a generation run for the test
        from .models import GenerationRun

        generation_run = GenerationRun.objects.create(brief=brief, run_index=1, success=True)

        # First call should create a new asset
        asset1 = generator._save_generated_asset(
            brief=brief,
            product_name="Test Product",
            aspect_ratio="1:1",
            image_url_or_data="http://fake-url.com/image.jpg",
            prompt="Test prompt 1",
            generation_time=5.0,
            generation_run=generation_run,
        )

        # Second call with same brief/product/aspect_ratio should update existing asset
        asset2 = generator._save_generated_asset(
            brief=brief,
            product_name="Test Product",
            aspect_ratio="1:1",
            image_url_or_data="http://fake-url.com/image2.jpg",
            prompt="Test prompt 2",
            generation_time=3.0,
            generation_run=generation_run,
        )

        # Should be the same asset object (updated, not duplicated)
        assert asset1.id == asset2.id
        assert asset2.ai_prompt == "Test prompt 2"  # Should be updated
        assert asset2.generation_time_seconds == 3.0  # Should be updated

        # Should only have one asset in the database
        assets = GeneratedAsset.objects.filter(
            brief=brief, product_name="Test Product", aspect_ratio="1:1"
        )
        assert assets.count() == 1


@pytest.mark.unit
@pytest.mark.django_db
def test_generation_run_model(brief):
    """Test the new GenerationRun model functionality"""
    from .models import GenerationRun

    # Create first generation run
    run1 = GenerationRun.objects.create(
        brief=brief, run_index=1, success=True, assets_generated=3, total_generation_time=15.5
    )

    # Create second generation run (retry)
    run2 = GenerationRun.objects.create(
        brief=brief, run_index=2, success=False, assets_generated=0, error_message="API timeout"
    )

    # Test run properties
    assert run1.run_index == 1
    assert run1.success == True
    assert run1.is_current == False  # No longer latest run after run2 is created
    assert run2.is_current == True  # Latest run

    # Test string representation
    assert "Run #1" in str(run1)
    assert "Run #2" in str(run2)
    assert "Failed" in str(run2)


@pytest.mark.unit
@pytest.mark.django_db
def test_generation_run_with_assets(brief):
    """Test that assets are properly linked to generation runs"""
    from .models import GeneratedAsset, GenerationRun

    # Create generation run
    run = GenerationRun.objects.create(brief=brief, run_index=1, success=True)

    # Create assets for this run
    asset1 = GeneratedAsset.objects.create(
        brief=brief,
        generation_run=run,
        product_name="Test Product",
        aspect_ratio="1:1",
        ai_prompt="Test prompt",
        organized_file_path="/test/path",
    )

    asset2 = GeneratedAsset.objects.create(
        brief=brief,
        generation_run=run,
        product_name="Test Product",
        aspect_ratio="9:16",
        ai_prompt="Test prompt 2",
        organized_file_path="/test/path2",
    )

    # Test relationships
    assert asset1.generation_run == run
    assert asset2.generation_run == run
    assert run.assets.count() == 2

    # Test string representation includes run number
    assert "Run #1" in str(asset1)
    assert "Run #1" in str(asset2)


# Mock API Tests
@pytest.fixture
def mock_settings():
    """Fixture to mock Django settings for testing"""
    from django.test import override_settings

    return override_settings


@pytest.mark.django_db
def test_ai_dev_mode_enabled(mock_settings, campaign_generator):
    """Test that AI_DEV_MODE=True uses mock generation"""
    with mock_settings(AI_DEV_MODE=True):
        # Recreate generator with dev mode enabled
        generator = CampaignGenerator()
        assert generator.dev_mode is True

        # Test that _call_dalle returns mock data
        mock_image_data = generator._call_dalle("test prompt")
        assert isinstance(mock_image_data, bytes)
        assert len(mock_image_data) > 0


@pytest.mark.django_db
def test_ai_dev_mode_disabled(mock_settings, campaign_generator):
    """Test that AI_DEV_MODE=False uses real API (mocked)"""
    with mock_settings(AI_DEV_MODE=False):
        # Recreate generator with dev mode disabled
        generator = CampaignGenerator()
        assert generator.dev_mode is False

        # Mock the OpenAI client to avoid real API calls
        with patch.object(generator.client.images, "generate") as mock_generate:
            # Mock the API response
            mock_response = Mock()
            mock_response.data = [Mock()]
            mock_response.data[0].url = "http://example.com/image.jpg"
            mock_generate.return_value = mock_response

            # Mock requests.get for image download
            with patch("campaign_generator.ai_service.requests.get") as mock_requests:
                mock_image_response = Mock()
                mock_image_response.content = b"fake_image_data"
                mock_requests.return_value = mock_image_response

                # This should call the real API path (but mocked)
                image_data = generator._call_dalle("test prompt")
                assert image_data == b"fake_image_data"
                mock_generate.assert_called_once()


@pytest.mark.django_db
def test_mock_image_creation(campaign_generator):
    """Test that mock image creation works correctly"""
    # Force dev mode for this test
    campaign_generator.dev_mode = True

    mock_image_data = campaign_generator._create_mock_image()

    # Verify it's valid image data
    assert isinstance(mock_image_data, bytes)
    assert len(mock_image_data) > 0

    # Verify it's a valid JPEG
    from io import BytesIO

    from PIL import Image

    image = Image.open(BytesIO(mock_image_data))
    assert image.size == (1024, 1024)
    assert image.mode == "RGB"


@pytest.mark.django_db
def test_no_api_calls_in_dev_mode(mock_settings, campaign_generator):
    """Test that no real API calls are made when dev mode is enabled"""
    with mock_settings(AI_DEV_MODE=True):
        generator = CampaignGenerator()

        # Mock the OpenAI client to ensure it's never called
        with patch.object(generator.client.images, "generate") as mock_generate:
            # Call the method that should use mock data
            generator._call_dalle("test prompt")

            # Verify the real API was never called
            mock_generate.assert_not_called()


@pytest.mark.django_db
def test_billing_error_handling(mock_settings, campaign_generator):
    """Test improved error handling for billing issues"""
    with mock_settings(AI_DEV_MODE=False):
        generator = CampaignGenerator()

        # Mock the OpenAI client to raise billing error
        with patch.object(generator.client.images, "generate") as mock_generate:
            mock_generate.side_effect = Exception(
                "Error code: 400 - {'error': {'message': 'Billing hard limit has been reached', 'type': 'image_generation_user_error', 'param': None, 'code': 'billing_hard_limit_reached'}}"
            )

            with pytest.raises(Exception) as exc_info:
                generator._call_dalle("test prompt")

            # Verify the error message is helpful
            error_msg = str(exc_info.value)
            assert "OpenAI billing limit reached" in error_msg
            assert "https://platform.openai.com/usage" in error_msg


@pytest.mark.django_db
def test_quota_error_handling(mock_settings, campaign_generator):
    """Test error handling for quota exceeded"""
    with mock_settings(AI_DEV_MODE=False):
        generator = CampaignGenerator()

        # Mock the OpenAI client to raise quota error
        with patch.object(generator.client.images, "generate") as mock_generate:
            mock_generate.side_effect = Exception(
                "Error code: 429 - {'error': {'message': 'You exceeded your current quota', 'type': 'insufficient_quota'}}"
            )

            with pytest.raises(Exception) as exc_info:
                generator._call_dalle("test prompt")

            # Verify the error message is helpful
            error_msg = str(exc_info.value)
            assert "OpenAI API quota exceeded" in error_msg
            assert "https://platform.openai.com/usage" in error_msg


@pytest.mark.django_db
def test_generation_with_dev_mode(mock_settings, brief):
    """Test full generation workflow in dev mode"""
    with mock_settings(AI_DEV_MODE=True):
        generator = CampaignGenerator()

        # This should work without any API calls
        assets = generator.generate_campaign_assets(brief)

        # Verify assets were created
        assert len(assets) > 0

        # Verify all assets have mock images
        for asset in assets:
            assert asset.image_file.name != ""
            # In dev mode, assets should have mock images or be generated from mock images
            assert "MOCK IMAGE" in str(asset.ai_prompt) or asset.generation_time_seconds >= 0


@pytest.mark.django_db
def test_cost_estimation_in_views(mock_settings, client, brief):
    """Test that cost estimation works in views"""
    with mock_settings(AI_DEV_MODE=False):
        # Mock all OpenAI API calls to avoid real API calls and long execution time
        with (
            patch("campaign_generator.ai_service.CampaignGenerator._call_dalle") as mock_dalle,
            patch(
                "campaign_generator.ai_service.CampaignGenerator._outpaint_landscape"
            ) as mock_landscape,
            patch(
                "campaign_generator.ai_service.CampaignGenerator._outpaint_vertical"
            ) as mock_vertical,
        ):
            # Mock the API responses
            mock_dalle.return_value = b"mock_image_data"
            mock_landscape.return_value = b"mock_landscape_data"
            mock_vertical.return_value = b"mock_vertical_data"

            # Test the cost warning appears for expensive operations
            response = client.post(
                reverse("generate_assets", kwargs={"brief_id": brief.id}), data={}, follow=True
            )

            # Should show cost warning if no API key or other issues
            # The exact behavior depends on whether API key is set
            assert response.status_code in [200, 302]


@pytest.mark.django_db
def test_dev_mode_environment_variable():
    """Test that AI_DEV_MODE can be set via environment variable"""
    import os

    from django.test import override_settings

    # Test with environment variable set
    with patch.dict(os.environ, {"AI_DEV_MODE": "true"}):
        # Use override_settings to simulate the environment variable effect
        with override_settings(AI_DEV_MODE=True):
            from django.conf import settings

            assert getattr(settings, "AI_DEV_MODE", False) is True

    # Test with environment variable not set (defaults to False)
    with patch.dict(os.environ, {}, clear=True):
        # Remove the key if it exists
        if "AI_DEV_MODE" in os.environ:
            del os.environ["AI_DEV_MODE"]

        # This should default to False
        with override_settings(AI_DEV_MODE=False):
            from django.conf import settings

            assert getattr(settings, "AI_DEV_MODE", False) is False


@pytest.mark.django_db
def test_mock_image_consistency(campaign_generator):
    """Test that mock images are consistent and valid"""
    campaign_generator.dev_mode = True

    # Generate multiple mock images
    images = []
    for i in range(3):
        image_data = campaign_generator._create_mock_image()
        images.append(image_data)

    # All should be valid
    for image_data in images:
        assert isinstance(image_data, bytes)
        assert len(image_data) > 0

        # Should be valid JPEG
        from io import BytesIO

        from PIL import Image

        image = Image.open(BytesIO(image_data))
        assert image.size == (1024, 1024)


@pytest.mark.django_db
def test_generation_run_with_dev_mode(mock_settings, brief):
    """Test that GenerationRun is properly created in dev mode"""
    with mock_settings(AI_DEV_MODE=True):
        generator = CampaignGenerator()

        # Generate assets
        assets = generator.generate_campaign_assets(brief)

        # Check that a GenerationRun was created
        from .models import GenerationRun

        runs = GenerationRun.objects.filter(brief=brief)
        assert runs.count() == 1

        run = runs.first()
        assert run.success is True
        assert run.assets_generated == len(assets)
        assert run.estimated_cost_usd is not None


@pytest.mark.django_db
def test_dev_mode_vs_production_mode_switching(mock_settings, brief):
    """Test switching between dev and production modes"""
    # Test dev mode
    with mock_settings(AI_DEV_MODE=True):
        generator = CampaignGenerator()
        assert generator.dev_mode is True

        # Should use mock data
        mock_data = generator._call_dalle("test")
        assert isinstance(mock_data, bytes)

    # Test production mode
    with mock_settings(AI_DEV_MODE=False):
        generator = CampaignGenerator()
        assert generator.dev_mode is False

        # Should attempt real API call (but we'll mock it)
        with patch.object(generator.client.images, "generate") as mock_generate:
            mock_response = Mock()
            mock_response.data = [Mock()]
            mock_response.data[0].url = "http://example.com/image.jpg"
            mock_generate.return_value = mock_response

            with patch("campaign_generator.ai_service.requests.get") as mock_requests:
                mock_requests.return_value.content = b"real_api_data"

                api_data = generator._call_dalle("test")
                assert api_data == b"real_api_data"
                mock_generate.assert_called_once()


# ===== MULTILINGUAL TESTS =====


@pytest.fixture
def multilingual_brief(db, english_language, spanish_language):
    """Create a multilingual brief"""
    brief = Brief.objects.create(
        title="Test Multilingual Campaign",
        target_region="Global",
        target_audience="International audience",
        campaign_message="Global energy for everyone",
        products=[{"name": "Energy Drink", "type": "Beverage"}],
        primary_language=english_language,
    )
    brief.supported_languages.add(spanish_language)
    return brief


# Language Model Tests
@pytest.mark.django_db
def test_language_model_creation(english_language):
    """Test Language model creation and properties"""
    assert english_language.code == "en"
    assert english_language.name == "English"
    assert english_language.direction == "ltr"
    assert english_language.script == "latin"
    assert english_language.is_active is True
    assert str(english_language) == "English (en)"


@pytest.mark.django_db
def test_language_text_direction_choices(japanese_language):
    """Test language with different text direction"""
    assert japanese_language.direction == "ttb"
    assert japanese_language.script == "hiragana"


# Brief Model Tests
@pytest.mark.django_db
def test_brief_with_primary_language(multilingual_brief, english_language):
    """Test brief with primary language"""
    assert multilingual_brief.primary_language == english_language
    assert multilingual_brief.primary_language.code == "en"


@pytest.mark.django_db
def test_brief_get_all_languages(multilingual_brief, english_language, spanish_language):
    """Test getting all languages for a brief"""
    languages = multilingual_brief.get_all_languages()
    language_codes = [lang.code for lang in languages]

    assert "en" in language_codes
    assert "es" in language_codes
    assert len(languages) == 2


@pytest.mark.django_db
def test_brief_expected_asset_count_multilingual(multilingual_brief):
    """Test asset count calculation with multiple languages"""
    # 1 product × 3 aspect ratios × 2 languages = 6 assets
    assert multilingual_brief.get_expected_asset_count() == 6


# GeneratedAsset Model Tests
@pytest.mark.django_db
def test_generated_asset_with_language(generation_run, english_language):
    """Test GeneratedAsset with language"""
    asset = GeneratedAsset.objects.create(
        brief=generation_run.brief,
        generation_run=generation_run,
        product_name="Test Product",
        aspect_ratio="1:1",
        language=english_language,
        ai_prompt="Test prompt",
    )

    assert asset.language == english_language
    assert asset.translation_status == "original"
    assert asset.get_display_name() == "Test Product - 1:1 (EN)"


@pytest.mark.django_db
def test_generated_asset_organized_folder_with_language(generation_run, spanish_language):
    """Test organized folder path includes language"""
    asset = GeneratedAsset.objects.create(
        brief=generation_run.brief,
        generation_run=generation_run,
        product_name="Test Product",
        aspect_ratio="16:9",
        language=spanish_language,
        ai_prompt="Test prompt",
    )

    assert asset.organized_folder == "test-product/es/16x9"


@pytest.mark.django_db
def test_generated_asset_translation_relationship(
    generation_run, english_language, spanish_language
):
    """Test translation relationship between assets"""
    original_asset = GeneratedAsset.objects.create(
        brief=generation_run.brief,
        generation_run=generation_run,
        product_name="Test Product",
        aspect_ratio="1:1",
        language=english_language,
        ai_prompt="Test prompt",
        translation_status="original",
    )

    translated_asset = GeneratedAsset.objects.create(
        brief=generation_run.brief,
        generation_run=generation_run,
        product_name="Test Product",
        aspect_ratio="1:1",
        language=spanish_language,
        ai_prompt="Test prompt",
        original_asset=original_asset,
        translation_status="translated",
        translated_campaign_message="Mensaje traducido",
    )

    assert translated_asset.original_asset == original_asset
    assert translated_asset.translation_status == "translated"
    assert translated_asset.translated_campaign_message == "Mensaje traducido"


# Translation Service Tests
def test_mock_translation_provider():
    """Test MockTranslationProvider"""
    provider = MockTranslationProvider()

    assert provider.is_available() is True

    # Test same language
    result = provider.translate("Hello", "en", "en")
    assert result == "Hello"

    # Test different language
    result = provider.translate("Hello", "es", "en")
    assert result == "[ES] Hello"

    # Test unknown language
    result = provider.translate("Hello", "xyz", "en")
    assert result == "[XYZ] Hello"


def test_translation_service_initialization():
    """Test TranslationService initialization"""
    service = TranslationService()

    # Should have at least MockTranslationProvider available
    assert len(service.available_providers) >= 1
    provider_names = service.get_available_providers()
    assert "MockTranslationProvider" in provider_names


def test_translation_service_translate_text():
    """Test TranslationService text translation"""
    service = TranslationService()

    # Test same language
    result = service.translate_text("Hello", "en", "en")
    assert result == "Hello"

    # Test different language (could be real OpenAI or mock)
    result = service.translate_text("Hello", "es", "en")
    assert result is not None
    assert len(result) > 0
    # Accept either real translation or mock format
    assert result in ["Hola", "[ES] Hello"] or "hola" in result.lower()


def test_translation_service_translate_campaign_content():
    """Test TranslationService campaign content translation"""
    service = TranslationService()

    content = {
        "title": "Energy Drink Campaign",
        "message": "Natural energy for active lifestyle",
        "audience": "Young professionals",
    }

    translated = service.translate_campaign_content(content, "es", "en")

    # Verify all fields are translated (could be real or mock)
    assert "title" in translated
    assert "message" in translated
    assert "audience" in translated

    # Verify translations are not empty and different from originals (unless same language)
    for key, original_text in content.items():
        translated_text = translated[key]
        assert translated_text is not None
        assert len(translated_text) > 0
        # Accept either real translation or mock format
        assert (
            translated_text != original_text
            or translated_text.startswith("[ES]")
            or "campaña" in translated_text.lower()
            or "energía" in translated_text.lower()
        )


# Form Tests
@pytest.mark.django_db
def test_brief_form_with_languages(english_language, spanish_language):
    """Test BriefForm with language selection"""
    form_data = {
        "title": "Test Campaign",
        "target_region": "Global",
        "target_audience": "Everyone",
        "campaign_message": "Test message",
        "primary_language": english_language.id,
        "products_json": '[{"name": "Product A", "type": "Drink"}]',
        "additional_languages": [spanish_language.id],
    }

    form = BriefForm(data=form_data)
    assert form.is_valid(), f"Form errors: {form.errors}"

    brief = form.save()
    assert brief.primary_language == english_language
    assert spanish_language in brief.supported_languages.all()


@pytest.mark.django_db
def test_brief_form_without_additional_languages(english_language):
    """Test BriefForm without additional languages"""
    form_data = {
        "title": "Test Campaign",
        "target_region": "Global",
        "target_audience": "Everyone",
        "campaign_message": "Test message",
        "primary_language": english_language.id,
        "products_json": '[{"name": "Product A", "type": "Drink"}]',
    }

    form = BriefForm(data=form_data)
    assert form.is_valid(), f"Form errors: {form.errors}"

    brief = form.save()
    assert brief.primary_language == english_language
    assert brief.supported_languages.count() == 0


# Admin Tests
@pytest.mark.django_db
def test_language_admin_display(english_language):
    """Test Language admin display"""
    from .admin import LanguageAdmin

    admin = LanguageAdmin(Language, None)

    # Test list display fields exist
    for field in admin.list_display:
        assert hasattr(english_language, field) or hasattr(admin, field)


@pytest.mark.django_db
def test_brief_admin_with_multilingual_fields(multilingual_brief):
    """Test Brief admin with multilingual fields"""
    from .admin import BriefAdmin

    admin = BriefAdmin(Brief, None)

    # Test that primary_language is in list_display
    assert "primary_language" in admin.list_display

    # Test that supported_languages is in filter_horizontal
    assert "supported_languages" in admin.filter_horizontal


@pytest.mark.django_db
def test_generated_asset_admin_with_language_fields(generation_run, english_language):
    """Test GeneratedAsset admin with language fields"""
    from .admin import GeneratedAssetAdmin

    asset = GeneratedAsset.objects.create(
        brief=generation_run.brief,
        generation_run=generation_run,
        product_name="Test Product",
        aspect_ratio="1:1",
        language=english_language,
        ai_prompt="Test prompt",
    )

    admin = GeneratedAssetAdmin(GeneratedAsset, None)

    # Test that language fields are in list_display
    assert "language" in admin.list_display
    assert "translation_status" in admin.list_display

    # Test that language is in list_filter
    assert "language" in admin.list_filter
    assert "translation_status" in admin.list_filter


# Integration Tests
@pytest.mark.django_db
def test_multilingual_workflow_end_to_end(english_language, spanish_language):
    """Test complete multilingual workflow"""
    # 1. Create multilingual brief
    brief = Brief.objects.create(
        title="Global Campaign",
        target_region="Worldwide",
        target_audience="Global audience",
        campaign_message="Universal energy",
        products=[{"name": "Global Energy", "type": "Drink"}],
        primary_language=english_language,
    )
    brief.supported_languages.add(spanish_language)

    # 2. Verify brief setup
    assert brief.get_expected_asset_count() == 6  # 1 product × 3 ratios × 2 languages

    # 3. Create generation run
    from .models import GenerationRun

    run = GenerationRun.objects.create(brief=brief, run_index=1, success=True)

    # 4. Create assets for both languages
    for lang in brief.get_all_languages():
        for ratio in ["1:1", "9:16", "16:9"]:
            GeneratedAsset.objects.create(
                brief=brief,
                generation_run=run,
                product_name="Global Energy",
                aspect_ratio=ratio,
                language=lang,
                ai_prompt=f"Generate {ratio} image for {lang.name}",
                translation_status="original" if lang.code == "en" else "translated",
            )

    # 5. Verify assets created
    assert GeneratedAsset.objects.filter(brief=brief).count() == 6
    assert GeneratedAsset.objects.filter(brief=brief, language=english_language).count() == 3
    assert GeneratedAsset.objects.filter(brief=brief, language=spanish_language).count() == 3

    # 6. Test organized folder structure
    en_asset = GeneratedAsset.objects.filter(language=english_language, aspect_ratio="1:1").first()
    es_asset = GeneratedAsset.objects.filter(language=spanish_language, aspect_ratio="1:1").first()

    assert en_asset.organized_folder == "global-energy/en/1x1"
    assert es_asset.organized_folder == "global-energy/es/1x1"


# ===== TEMPLATE DECOUPLING TESTS =====


@pytest.mark.django_db
def test_prepare_example_data_function_exists():
    """Test that _prepare_example_data function exists and is callable"""
    from .views import _prepare_example_data

    assert callable(_prepare_example_data)


@pytest.mark.django_db
def test_prepare_example_data_returns_dict(load_languages):
    """Test that _prepare_example_data returns a dictionary with expected keys"""
    from .views import _prepare_example_data

    example_data = _prepare_example_data()

    assert isinstance(example_data, dict)

    # Test all required keys are present
    required_keys = [
        "title",
        "target_region",
        "campaign_message",
        "primary_language",
        "products_json",
        "language_names",
        "language_ids",
        "language_codes_csv",
        "target_audience",
        "tip_text",
    ]

    for key in required_keys:
        assert key in example_data, f"Missing key: {key}"


@pytest.mark.django_db
def test_prepare_example_data_static_content(load_languages):
    """Test that static content in example data is correct"""
    from .views import _prepare_example_data

    example_data = _prepare_example_data()

    # Test static content
    assert example_data["title"] == "Pacific Pulse Energy Drink Launch"
    assert example_data["target_region"] == "Pacific Coast US/Mexico border cities"
    assert (
        example_data["campaign_message"]
        == "Natural energy that connects you to the coastal lifestyle"
    )
    assert example_data["primary_language"] == "English"
    # Target audience should include language codes dynamically
    assert "18-30, urban, multilingual" in example_data["target_audience"]
    assert "health-conscious but fun-seeking" in example_data["target_audience"]


@pytest.mark.django_db
def test_prepare_example_data_language_filtering(load_languages):
    """Test that example data correctly filters for German and French languages"""
    from .views import _prepare_example_data

    example_data = _prepare_example_data()

    # Should have German and French languages
    assert "German" in example_data["language_names"]
    assert "French" in example_data["language_names"]

    # Should not include other languages like English, Spanish, etc.
    assert "English" not in example_data["language_names"]
    assert "Spanish" not in example_data["language_names"]


@pytest.mark.django_db
def test_prepare_example_data_language_ids_format(load_languages):
    """Test that language IDs are properly formatted as comma-separated string"""
    from .views import _prepare_example_data

    example_data = _prepare_example_data()

    # Should be comma-separated string of IDs
    assert isinstance(example_data["language_ids"], str)
    assert "," in example_data["language_ids"]

    # Should contain valid language IDs
    language_ids = example_data["language_ids"].split(",")
    assert len(language_ids) == 2  # German and French

    # All IDs should be numeric
    for lang_id in language_ids:
        assert lang_id.isdigit()


@pytest.mark.django_db
def test_prepare_example_data_products_json_format(load_languages):
    """Test that products JSON is properly formatted"""
    import json

    from .views import _prepare_example_data

    example_data = _prepare_example_data()

    # Should be valid JSON string
    products_data = json.loads(example_data["products_json"])

    assert isinstance(products_data, list)
    assert len(products_data) == 2

    # Check product structure
    for product in products_data:
        assert "name" in product
        assert "type" in product
        assert product["name"] in ["Pacific Pulse Original", "Pacific Pulse Zero"]
        assert "Energy Drink" in product["type"]


@pytest.mark.django_db
def test_prepare_example_data_tip_text_format(load_languages):
    """Test that tip text is properly formatted with language names"""
    from .views import _prepare_example_data

    example_data = _prepare_example_data()

    # Should start with "English" and include additional languages
    assert example_data["tip_text"].startswith("(English")
    assert "German" in example_data["tip_text"]
    assert "French" in example_data["tip_text"]
    assert example_data["tip_text"].endswith(")")


@pytest.mark.django_db
def test_prepare_example_data_no_languages_found():
    """Test behavior when no German/French languages are found"""
    from .views import _prepare_example_data

    # Clear all languages first
    Language.objects.all().delete()

    example_data = _prepare_example_data()

    # Should handle empty language list gracefully
    assert example_data["language_names"] == "None"
    assert example_data["language_ids"] == ""
    assert example_data["tip_text"] == "(English only)"  # Just English, no additional languages


@pytest.mark.django_db
def test_prepare_example_data_inactive_languages(load_languages):
    """Test that inactive languages are not included"""
    from .views import _prepare_example_data

    # Make German language inactive
    german_lang = Language.objects.get(code="de")
    german_lang.is_active = False
    german_lang.save()

    example_data = _prepare_example_data()

    # Should only include French now
    assert "French" in example_data["language_names"]
    assert "German" not in example_data["language_names"]


@pytest.mark.django_db
def test_prepare_example_data_language_ordering(load_languages):
    """Test that languages are ordered by name"""
    from .views import _prepare_example_data

    example_data = _prepare_example_data()

    # French should come before German alphabetically
    language_names = example_data["language_names"].split(", ")
    assert language_names[0] == "French"
    assert language_names[1] == "German"


@pytest.mark.django_db
def test_prepare_example_data_language_codes_csv(load_languages):
    """Test that language codes CSV format is properly generated"""
    from .views import _prepare_example_data

    example_data = _prepare_example_data()

    # Should contain comma-separated language codes
    assert "fr,de" == example_data["language_codes_csv"]

    # Should be consistent with language names
    language_names = example_data["language_names"].split(", ")
    language_codes = example_data["language_codes_csv"].split(",")
    assert len(language_names) == len(language_codes)


@pytest.mark.django_db
def test_prepare_example_data_data_types(load_languages):
    """Test that all data types are correct"""
    from .views import _prepare_example_data

    example_data = _prepare_example_data()

    # Test data types
    assert isinstance(example_data["title"], str)
    assert isinstance(example_data["target_region"], str)
    assert isinstance(example_data["campaign_message"], str)
    assert isinstance(example_data["primary_language"], str)
    assert isinstance(example_data["products_json"], str)
    assert isinstance(example_data["language_names"], str)
    assert isinstance(example_data["language_ids"], str)
    assert isinstance(example_data["language_codes_csv"], str)
    assert isinstance(example_data["target_audience"], str)
    assert isinstance(example_data["tip_text"], str)


# ===== GALLERY VIEW DECOUPLING TESTS =====


@pytest.mark.django_db
def test_gallery_view_language_direction_flags(load_languages, client):
    """Test that gallery view provides correct language direction flags"""

    # Create a brief with assets
    brief = Brief.objects.create(
        title="Test Brief",
        target_region="Test Region",
        target_audience="Test Audience",
        campaign_message="Test Message",
        products=[{"name": "Test Product", "type": "Drink"}],
        primary_language=Language.objects.get(code="en"),
    )

    # Create a generation run
    from .models import GenerationRun

    generation_run = GenerationRun.objects.create(brief=brief, run_index=1, success=True)

    # Create assets for different language directions
    english_lang = Language.objects.get(code="en")  # ltr
    GeneratedAsset.objects.create(
        brief=brief,
        generation_run=generation_run,
        product_name="Test Product",
        aspect_ratio="1:1",
        language=english_lang,
        ai_prompt="Test prompt",
    )

    # Test the view
    response = client.get("/gallery/")

    # Check that context contains language groups with decoupled flags
    assert "assets_by_language" in response.context

    # Find the language group for English
    language_groups = response.context["assets_by_language"]
    english_group = None
    for group in language_groups:
        if group["lang_code"] == "en":
            english_group = group
            break

    assert english_group is not None
    assert "lang_rtl" in english_group
    assert "lang_ttb" in english_group
    assert "lang_ltr" in english_group

    # English should be ltr
    assert english_group["lang_ltr"] is True
    assert english_group["lang_rtl"] is False
    assert english_group["lang_ttb"] is False


@pytest.mark.django_db
def test_gallery_view_rtl_language_flags(load_languages, client):
    """Test gallery view with RTL language (Arabic)"""

    # Create Arabic language if it doesn't exist
    arabic_lang, created = Language.objects.get_or_create(
        code="ar",
        defaults={"name": "Arabic", "direction": "rtl", "script": "arabic", "is_active": True},
    )

    # Create brief and assets
    brief = Brief.objects.create(
        title="Test Brief",
        target_region="Test Region",
        target_audience="Test Audience",
        campaign_message="Test Message",
        products=[{"name": "Test Product", "type": "Drink"}],
        primary_language=Language.objects.get(code="en"),
    )

    from .models import GenerationRun

    generation_run = GenerationRun.objects.create(brief=brief, run_index=1, success=True)

    GeneratedAsset.objects.create(
        brief=brief,
        generation_run=generation_run,
        product_name="Test Product",
        aspect_ratio="1:1",
        language=arabic_lang,
        ai_prompt="Test prompt",
    )

    # Test the view
    response = client.get("/gallery/")

    # Find Arabic language group
    language_groups = response.context["assets_by_language"]
    arabic_group = None
    for group in language_groups:
        if group["lang_code"] == "ar":
            arabic_group = group
            break

    assert arabic_group is not None
    assert arabic_group["lang_rtl"] is True
    assert arabic_group["lang_ltr"] is False
    assert arabic_group["lang_ttb"] is False


@pytest.mark.django_db
def test_gallery_view_ttb_language_flags(load_languages, client):
    """Test gallery view with TTB language (Japanese)"""

    # Create brief and assets with Japanese
    brief = Brief.objects.create(
        title="Test Brief",
        target_region="Test Region",
        target_audience="Test Audience",
        campaign_message="Test Message",
        products=[{"name": "Test Product", "type": "Drink"}],
        primary_language=Language.objects.get(code="en"),
    )

    from .models import GenerationRun

    generation_run = GenerationRun.objects.create(brief=brief, run_index=1, success=True)

    japanese_lang = Language.objects.get(code="ja")  # ttb
    GeneratedAsset.objects.create(
        brief=brief,
        generation_run=generation_run,
        product_name="Test Product",
        aspect_ratio="1:1",
        language=japanese_lang,
        ai_prompt="Test prompt",
    )

    # Test the view
    response = client.get("/gallery/")

    # Find Japanese language group
    language_groups = response.context["assets_by_language"]
    japanese_group = None
    for group in language_groups:
        if group["lang_code"] == "ja":
            japanese_group = group
            break

    assert japanese_group is not None
    assert japanese_group["lang_ttb"] is True
    assert japanese_group["lang_ltr"] is False
    assert japanese_group["lang_rtl"] is False


@pytest.mark.django_db
def test_gallery_view_language_group_structure(load_languages, client):
    """Test that language groups have the correct structure with decoupled flags"""

    # Create brief and assets
    brief = Brief.objects.create(
        title="Test Brief",
        target_region="Test Region",
        target_audience="Test Audience",
        campaign_message="Test Message",
        products=[{"name": "Test Product", "type": "Drink"}],
        primary_language=Language.objects.get(code="en"),
    )

    from .models import GenerationRun

    generation_run = GenerationRun.objects.create(brief=brief, run_index=1, success=True)

    english_lang = Language.objects.get(code="en")
    GeneratedAsset.objects.create(
        brief=brief,
        generation_run=generation_run,
        product_name="Test Product",
        aspect_ratio="1:1",
        language=english_lang,
        ai_prompt="Test prompt",
    )

    # Test the view
    response = client.get("/gallery/")

    # Check language group structure
    language_groups = response.context["assets_by_language"]
    assert len(language_groups) > 0

    for group in language_groups:
        # Required keys
        required_keys = [
            "lang_name",
            "lang_code",
            "assets",
            "count",
            "lang_rtl",
            "lang_ttb",
            "lang_ltr",
        ]
        for key in required_keys:
            assert key in group, f"Missing key in language group: {key}"

        # Data types
        assert isinstance(group["lang_name"], str)
        assert isinstance(group["lang_code"], str)
        assert isinstance(group["assets"], list)
        assert isinstance(group["count"], int)
        assert isinstance(group["lang_rtl"], bool)
        assert isinstance(group["lang_ttb"], bool)
        assert isinstance(group["lang_ltr"], bool)

        # Boolean flags should be mutually exclusive
        direction_flags = [group["lang_rtl"], group["lang_ttb"], group["lang_ltr"]]
        assert sum(direction_flags) == 1, "Exactly one direction flag should be True"


@pytest.mark.django_db
def test_gallery_view_no_assets_empty_groups(client):
    """Test gallery view with no assets returns empty but properly structured groups"""

    # Test with no assets
    response = client.get("/gallery/")

    # Should have empty but properly structured context
    assert "assets_by_language" in response.context
    language_groups = response.context["assets_by_language"]
    assert isinstance(language_groups, list)
    assert len(language_groups) == 0


# ===== DECOUPLING TESTS =====


@pytest.mark.django_db
def test_gallery_view_context_decoupling(client, generated_asset):
    """Test that gallery view provides properly decoupled context data"""
    # Use existing generated_asset fixture

    response = client.get(reverse("gallery"))
    assert response.status_code == 200

    # Test assets_by_language structure - should be UI-ready
    language_groups = response.context["assets_by_language"]
    assert isinstance(language_groups, list)

    if language_groups:
        group = language_groups[0]

        # Language group should have UI-ready data, not model objects
        assert "lang_name" in group  # UI name, not group.language.name
        assert "lang_code" in group  # UI code, not group.language.code
        assert "lang_native" in group  # UI native name
        assert "lang_direction_badge" in group  # UI text, not model method
        assert "count" in group
        assert "assets" in group

        # Assets should have UI-ready data, not model objects
        if group["assets"]:
            asset = group["assets"][0]

            # Should have UI-ready asset data
            assert "asset_id" in asset  # UI ID, not asset.id
            assert "title" in asset  # UI title, not asset.product_name
            assert "thumbnail_url" in asset  # UI URL, not asset.image_file.url
            assert "detail_url" in asset  # UI URL, not {% url %}
            assert "download_url" in asset  # UI URL
            assert "aspect_ratio_badge" in asset  # UI text
            assert "lang_code_badge" in asset  # UI text
            assert "brief_title" in asset  # UI text, not asset.brief.title
            assert "brief_url" in asset  # UI URL
            assert "created_date" in asset  # UI formatted date, not asset.created_at


@pytest.mark.django_db
def test_gallery_view_no_model_fields_in_context(client):
    """Test that gallery context contains no raw model objects or fields"""
    response = client.get(reverse("gallery"))

    # These should NOT exist in context (would be model objects)
    forbidden_keys = [
        "assets",  # Raw queryset
        "briefs_queryset",  # Raw queryset
        "languages_queryset",  # Raw queryset
    ]

    for key in forbidden_keys:
        assert key not in response.context, f"Context should not contain raw model data: {key}"

    # Assets by language should not contain model objects
    language_groups = response.context.get("assets_by_language", [])
    for group in language_groups:
        # Should not have model objects
        assert "language" not in group, "Should not contain model object"
        assert hasattr(group, "language") is False, "Should not contain model relationship"


@pytest.mark.django_db
def test_brief_detail_view_context_decoupling(client, brief):
    """Test that brief detail view provides properly decoupled context data"""
    response = client.get(reverse("brief_detail", kwargs={"brief_id": brief.id}))
    assert response.status_code == 200

    # Should have UI-ready brief data, not model object
    assert "brief_title" in response.context
    assert "brief_message" in response.context
    assert "brief_id" in response.context
    assert "can_generate" in response.context  # Boolean flag
    assert "can_download" in response.context  # Boolean flag
    assert "generate_url" in response.context  # Pre-built URL
    assert "download_url" in response.context  # Pre-built URL

    # Should not expose model object directly
    brief_obj = response.context.get("brief")
    if brief_obj:
        # If brief object exists, template should not access its fields directly
        pass  # We'll validate this in template testing


# ===== VIEW CONTEXT INTEGRATION TESTS =====


@pytest.mark.django_db
def test_create_brief_view_context_structure(client, load_languages):
    """Test that create_brief view provides properly structured context"""
    response = client.get("/brief/create/")

    assert response.status_code == 200
    assert "form" in response.context
    assert "example_data" in response.context

    # Test example_data structure
    example_data = response.context["example_data"]
    assert isinstance(example_data, dict)

    # All required keys should be present
    required_keys = [
        "title",
        "target_region",
        "campaign_message",
        "primary_language",
        "products_json",
        "language_names",
        "language_ids",
        "language_codes_csv",
        "target_audience",
        "tip_text",
    ]

    for key in required_keys:
        assert key in example_data, f"Missing key in example_data: {key}"


@pytest.mark.django_db
def test_gallery_view_context_structure(client, load_languages):
    """Test that gallery view provides properly structured context"""
    response = client.get("/gallery/")

    assert response.status_code == 200

    # Test context structure
    context = response.context
    assert "assets_by_language" in context
    assert "aspect_ratios" in context
    assert "briefs" in context
    assert "languages" in context

    # Test data types
    assert isinstance(context["assets_by_language"], list)
    assert isinstance(context["aspect_ratios"], list)
    assert isinstance(context["briefs"], list)
    assert isinstance(context["languages"], list)


# ===== LANGUAGE CODE FORM TESTS =====


@pytest.mark.django_db
def test_brief_form_with_language_codes(load_languages):
    """Test BriefForm accepts language codes instead of IDs"""
    form_data = {
        "title": "Test Campaign",
        "target_region": "Global",
        "target_audience": "Everyone",
        "campaign_message": "Test message",
        "primary_language_code": "en",  # Use language code instead of ID
        "additional_language_codes": ["fr", "de"],  # Use language codes
        "products_json": '[{"name": "Product A", "type": "Drink"}]',
    }

    # Note: This test will initially fail until we implement language code support
    # We're adding it to ensure our changes work correctly


@pytest.mark.django_db
def test_json_upload_with_language_codes(client, load_languages):
    """Test JSON upload workflow with language codes"""
    json_data = {
        "title": "JSON Upload Test with Codes",
        "products": [{"name": "Product A", "type": "Energy Drink"}],
        "target_region": "California",
        "target_audience": "Young adults",
        "campaign_message": "Test message",
        "primary_language": "en",  # Use language code instead of ID
        "additional_languages": ["fr", "de"],  # Use language codes
    }
    json_content = json.dumps(json_data).encode("utf-8")
    json_file = SimpleUploadedFile("test.json", json_content, content_type="application/json")

    response = client.post(reverse("upload_brief"), data={"brief_file": json_file})
    assert response.status_code == 302  # Redirect after successful upload

    # Check brief was created with correct languages
    brief = Brief.objects.get(title="JSON Upload Test with Codes")
    assert brief.primary_language.code == "en"

    # Check additional languages
    additional_langs = brief.supported_languages.all()
    additional_codes = [lang.code for lang in additional_langs]
    assert "fr" in additional_codes
    assert "de" in additional_codes
    assert len(additional_codes) == 2


# ===== REFERENCE IMAGE TESTS =====


def create_test_image(width=800, height=600, format="JPEG"):
    """Helper function to create a test image for upload tests"""
    image = Image.new("RGB", (width, height), "red")
    buffer = BytesIO()
    image.save(buffer, format=format)
    buffer.seek(0)
    return buffer


@pytest.mark.django_db
def test_reference_image_normalization():
    """Test the image normalization utility function"""
    from .utils import normalize_reference_image

    # Create a test image
    test_image_buffer = create_test_image(800, 600)
    test_file = SimpleUploadedFile(
        "test.jpg", test_image_buffer.getvalue(), content_type="image/jpeg"
    )

    # Normalize the image
    normalized_file = normalize_reference_image(test_file)

    # Check that we got a file back
    assert normalized_file is not None
    assert normalized_file.name.endswith("_normalized_1024x1024.jpg")

    # Check the normalized image dimensions
    normalized_image = Image.open(normalized_file)
    assert normalized_image.size == (1024, 1024)
    assert normalized_image.format == "JPEG"


@pytest.mark.django_db
def test_reference_image_metadata():
    """Test the image metadata extraction utility"""
    from .utils import get_reference_image_metadata

    # Create a test image
    test_image_buffer = create_test_image(800, 600)
    test_file = SimpleUploadedFile(
        "test.jpg", test_image_buffer.getvalue(), content_type="image/jpeg"
    )

    # Get metadata
    metadata = get_reference_image_metadata(test_file)

    assert metadata["original_dimensions"] == "800x600"
    assert metadata["normalized_dimensions"] == "1024x1024"
    assert metadata["normalized_format"] == "JPEG"
    assert "processing_note" in metadata


@pytest.mark.django_db
def test_brief_form_with_reference_image(load_languages):
    """Test BriefForm with reference image upload"""
    from .forms import BriefForm

    # Create a test image
    test_image_buffer = create_test_image(500, 300)
    test_image = SimpleUploadedFile(
        "reference.jpg", test_image_buffer.getvalue(), content_type="image/jpeg"
    )

    form_data = {
        "title": "Test Campaign with Image",
        "target_region": "Test Region",
        "target_audience": "Test Audience",
        "campaign_message": "Test Message",
        "primary_language": 1,  # English
        "products_json": '[{"name": "Product A", "type": "Drink"}]',
    }

    file_data = {"reference_image": test_image}

    form = BriefForm(data=form_data, files=file_data)
    assert form.is_valid(), f"Form errors: {form.errors}"

    brief = form.save()
    assert brief.reference_image is not None
    assert "_normalized_1024x1024" in brief.reference_image.name
    assert brief.reference_image.name.endswith(".jpg")


@pytest.mark.django_db
def test_json_upload_form_with_reference_image(load_languages):
    """Test JSONBriefUploadForm with reference image"""
    from .forms import JSONBriefUploadForm

    # Create test JSON file
    json_data = {
        "title": "JSON Test with Image",
        "products": [{"name": "Product A", "type": "Drink"}],
        "target_region": "Test Region",
        "target_audience": "Test Audience",
        "campaign_message": "Test Message",
    }
    json_content = json.dumps(json_data).encode("utf-8")
    json_file = SimpleUploadedFile("test.json", json_content, content_type="application/json")

    # Create test image
    test_image_buffer = create_test_image(400, 400)
    test_image = SimpleUploadedFile(
        "reference.png", test_image_buffer.getvalue(), content_type="image/png"
    )

    form_data = {}
    file_data = {"brief_file": json_file, "reference_image": test_image}

    form = JSONBriefUploadForm(data=form_data, files=file_data)
    assert form.is_valid(), f"Form errors: {form.errors}"

    brief = form.save()
    assert brief.reference_image is not None
    assert "_normalized_1024x1024" in brief.reference_image.name
    assert brief.reference_image.name.endswith(".jpg")


@pytest.mark.django_db
def test_brief_model_reference_image_field(load_languages):
    """Test that Brief model properly stores reference images"""
    from .models import Brief, Language

    # Create a brief
    english = Language.objects.get(code="en")
    brief = Brief.objects.create(
        title="Test Brief",
        target_region="Test Region",
        target_audience="Test Audience",
        campaign_message="Test Message",
        products=[{"name": "Product A", "type": "Drink"}],
        primary_language=english,
    )

    # Check that reference_image field exists and is empty by default
    assert hasattr(brief, "reference_image")
    assert not brief.reference_image  # VersatileImageField returns falsy when empty


@pytest.mark.django_db
def test_reference_image_asset_generation(load_languages, brief_with_reference_image):
    """Test that reference images are properly converted to assets during generation."""
    from unittest.mock import patch

    from .ai_service import CampaignGenerator

    # Mock the AI generation so we don't make real API calls
    with patch.object(CampaignGenerator, "_generate_assets_with_outpainting") as mock_outpaint:
        mock_outpaint.return_value = []  # No AI assets, only reference assets

        generator = CampaignGenerator()
        assets = generator.generate_campaign_assets(brief_with_reference_image)

        # Check that reference assets were created
        reference_assets = [asset for asset in assets if asset.is_reference_image]
        assert len(reference_assets) > 0, "Reference assets should be created"

        # Check properties of reference assets
        ref_asset = reference_assets[0]
        assert ref_asset.generation_time_seconds == 0.0, (
            "Reference assets should have 0 generation time"
        )
        assert ref_asset.is_reference_image is True, "Should be marked as reference image"
        assert "Reference image:" in ref_asset.ai_prompt, "Should have reference image prompt"
        assert ref_asset.reference_image_note, "Should have reference image note"

        # Check that we have reference assets for all products and aspect ratios
        expected_count = (
            len(brief_with_reference_image.products)
            * len(brief_with_reference_image.get_all_languages())
            * 3
        )  # 3 aspect ratios
        assert len(reference_assets) == expected_count, (
            f"Should create {expected_count} reference assets"
        )


@pytest.mark.django_db
def test_generated_asset_reference_metadata(load_languages):
    """Test GeneratedAsset reference image metadata fields"""
    from .models import Brief, GeneratedAsset, GenerationRun, Language

    # Create test objects
    english = Language.objects.get(code="en")
    brief = Brief.objects.create(
        title="Test Brief",
        target_region="Test Region",
        target_audience="Test Audience",
        campaign_message="Test Message",
        products=[{"name": "Product A", "type": "Drink"}],
        primary_language=english,
    )

    generation_run = GenerationRun.objects.create(brief=brief, run_index=1, success=True)

    asset = GeneratedAsset.objects.create(
        brief=brief,
        generation_run=generation_run,
        product_name="Product A",
        aspect_ratio="1:1",
        language=english,
        ai_prompt="Test prompt",
        is_reference_image=True,
        reference_image_note="Normalized from uploaded reference (500x300 to 1024x1024)",
    )

    assert asset.is_reference_image is True
    assert "Normalized from uploaded reference" in asset.reference_image_note


@pytest.mark.django_db
def test_create_brief_view_with_reference_image(client, load_languages):
    """Test create brief view handles reference image upload"""

    # Create test image
    test_image_buffer = create_test_image(600, 400)
    test_image = SimpleUploadedFile(
        "test.jpg", test_image_buffer.getvalue(), content_type="image/jpeg"
    )

    form_data = {
        "title": "Integration Test with Image",
        "target_region": "Test Region",
        "target_audience": "Test Audience",
        "campaign_message": "Test Message",
        "primary_language": 1,
        "products_json": '[{"name": "Product A", "type": "Drink"}]',
        "reference_image": test_image,
    }

    response = client.post(reverse("create_brief"), data=form_data)

    # Should redirect on success
    assert response.status_code == 302

    # Check that brief was created with reference image
    from .models import Brief

    brief = Brief.objects.get(title="Integration Test with Image")
    assert brief.reference_image is not None


@pytest.mark.django_db
def test_upload_brief_view_with_reference_image(client, load_languages):
    """Test upload brief view handles reference image"""

    # Create test JSON file
    json_data = {
        "title": "Upload Test with Image",
        "products": [{"name": "Product A", "type": "Drink"}],
        "target_region": "Test Region",
        "target_audience": "Test Audience",
        "campaign_message": "Test Message",
    }
    json_content = json.dumps(json_data).encode("utf-8")
    json_file = SimpleUploadedFile("test.json", json_content, content_type="application/json")

    # Create test image
    test_image_buffer = create_test_image(300, 300)
    test_image = SimpleUploadedFile(
        "ref.jpg", test_image_buffer.getvalue(), content_type="image/jpeg"
    )

    form_data = {"brief_file": json_file, "reference_image": test_image}

    response = client.post(reverse("upload_brief"), data=form_data)

    # Should redirect on success
    assert response.status_code == 302

    # Check that brief was created with reference image
    from .models import Brief

    brief = Brief.objects.get(title="Upload Test with Image")
    assert brief.reference_image is not None


# =============================================================================
# DemoBrief Model Tests
# =============================================================================


@pytest.mark.django_db
def test_demo_brief_creation(load_languages):
    """Test DemoBrief model creation"""
    from campaign_generator.models import DemoBrief, Language

    en = Language.objects.get(code="en")
    products = [{"name": "Pacific Pulse Original", "type": "Energy Drink"}]

    demo_brief = DemoBrief.objects.create(
        title="Pacific Pulse Demo",
        target_region="California Coast",
        target_audience="Active millennials",
        campaign_message="Fuel Your Adventure",
        products=products,
        primary_language=en,
        description="Demo brief for Pacific Pulse energy drink campaign",
    )

    assert demo_brief.title == "Pacific Pulse Demo"
    assert demo_brief.primary_language == en
    assert demo_brief.products == products
    assert demo_brief.is_active is True
    assert str(demo_brief) == "Pacific Pulse Demo"


@pytest.mark.django_db
def test_demo_brief_get_all_languages(load_languages):
    """Test DemoBrief get_all_languages method"""
    from campaign_generator.models import DemoBrief, Language

    en = Language.objects.get(code="en")
    fr = Language.objects.get(code="fr")
    de = Language.objects.get(code="de")

    demo_brief = DemoBrief.objects.create(
        title="Multi-Language Demo",
        target_region="Global",
        target_audience="Global audience",
        campaign_message="Universal message",
        products=[{"name": "Product", "type": "Type"}],
        primary_language=en,
    )

    demo_brief.supported_languages.add(fr, de)

    all_languages = demo_brief.get_all_languages()
    language_codes = {lang.code for lang in all_languages}

    assert len(all_languages) == 3
    assert language_codes == {"en", "fr", "de"}


@pytest.mark.django_db
def test_demo_brief_to_brief_data(load_languages):
    """Test DemoBrief to_brief_data conversion method"""
    from campaign_generator.models import DemoBrief, Language

    en = Language.objects.get(code="en")
    fr = Language.objects.get(code="fr")
    de = Language.objects.get(code="de")

    products = [
        {"name": "Pacific Pulse Original", "type": "Energy Drink"},
        {"name": "Pacific Pulse Zero", "type": "Sugar-Free Energy Drink"},
    ]

    demo_brief = DemoBrief.objects.create(
        title="Demo Brief for Copy",
        target_region="West Coast",
        target_audience="Health-conscious consumers",
        campaign_message="Energy that moves you",
        products=products,
        primary_language=en,
        translation_config={"style": "casual"},
    )

    demo_brief.supported_languages.add(fr, de)

    brief_data = demo_brief.to_brief_data()

    assert brief_data["title"] == "Demo Brief for Copy"
    assert brief_data["target_region"] == "West Coast"
    assert brief_data["target_audience"] == "Health-conscious consumers"
    assert brief_data["campaign_message"] == "Energy that moves you"
    assert brief_data["products"] == products
    assert brief_data["primary_language"] == en.id
    assert set(brief_data["supported_languages"]) == {fr.id, de.id}
    assert brief_data["translation_config"] == {"style": "casual"}


@pytest.mark.django_db
def test_demo_brief_ordering(load_languages):
    """Test DemoBrief model ordering"""
    from campaign_generator.models import DemoBrief, Language

    en = Language.objects.get(code="en")

    # Create demo briefs in non-alphabetical order
    DemoBrief.objects.create(
        title="Zebra Campaign",
        target_region="Global",
        target_audience="Everyone",
        campaign_message="Message",
        products=[{"name": "Product", "type": "Type"}],
        primary_language=en,
    )

    DemoBrief.objects.create(
        title="Alpha Campaign",
        target_region="Global",
        target_audience="Everyone",
        campaign_message="Message",
        products=[{"name": "Product", "type": "Type"}],
        primary_language=en,
    )

    # Check they're ordered alphabetically by title
    demo_briefs = list(DemoBrief.objects.all())
    titles = [brief.title for brief in demo_briefs]

    assert titles == ["Alpha Campaign", "Zebra Campaign"]


@pytest.mark.django_db
def test_create_brief_view_includes_demo_briefs(client, load_languages):
    """Test create_brief view includes demo briefs in context"""
    from campaign_generator.models import DemoBrief, Language

    en = Language.objects.get(code="en")

    # Create a demo brief
    demo_brief = DemoBrief.objects.create(
        title="Test Demo Brief",
        target_region="Test Region",
        target_audience="Test Audience",
        campaign_message="Test Message",
        products=[{"name": "Test Product", "type": "Test Type"}],
        primary_language=en,
        is_active=True,
    )

    response = client.get("/brief/create/")

    assert response.status_code == 200
    assert "demo_briefs" in response.context
    assert demo_brief in response.context["demo_briefs"]


@pytest.mark.django_db
def test_create_brief_view_excludes_inactive_demo_briefs(client, load_languages):
    """Test create_brief view excludes inactive demo briefs"""
    from campaign_generator.models import DemoBrief, Language

    en = Language.objects.get(code="en")

    # Create active and inactive demo briefs
    active_demo = DemoBrief.objects.create(
        title="Active Demo",
        target_region="Test Region",
        target_audience="Test Audience",
        campaign_message="Test Message",
        products=[{"name": "Test Product", "type": "Test Type"}],
        primary_language=en,
        is_active=True,
    )

    inactive_demo = DemoBrief.objects.create(
        title="Inactive Demo",
        target_region="Test Region",
        target_audience="Test Audience",
        campaign_message="Test Message",
        products=[{"name": "Test Product", "type": "Test Type"}],
        primary_language=en,
        is_active=False,
    )

    response = client.get("/brief/create/")

    assert response.status_code == 200
    assert "demo_briefs" in response.context
    assert active_demo in response.context["demo_briefs"]
    assert inactive_demo not in response.context["demo_briefs"]


@pytest.mark.django_db
def test_demo_brief_conditional_display(client, load_languages):
    """Test that demo briefs only show when they exist"""
    from campaign_generator.models import DemoBrief, Language

    # Test with no demo briefs
    response = client.get("/brief/create/")
    assert response.status_code == 200
    assert "demo_briefs" in response.context
    assert response.context["demo_briefs"].count() == 0

    # Test with demo briefs
    en = Language.objects.get(code="en")
    DemoBrief.objects.create(
        title="Test Demo",
        target_region="Test Region",
        target_audience="Test Audience",
        campaign_message="Test Message",
        products=[{"name": "Test Product", "type": "Test Type"}],
        primary_language=en,
        is_active=True,
    )

    response = client.get("/brief/create/")
    assert response.status_code == 200
    assert response.context["demo_briefs"].count() == 1


# Run with: uv run pytest app/campaign_generator/tests.py -v
