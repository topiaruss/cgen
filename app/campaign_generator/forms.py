import json

import yaml
from django import forms

from .models import Brief, Language
from .utils import normalize_reference_image, get_reference_image_metadata


class BriefForm(forms.ModelForm):
    """Simple form for creating campaign briefs"""

    products_json = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "rows": 6,
                "class": "form-control",
                "placeholder": """[
  {
    "name": "Pacific Pulse Original",
    "type": "Energy Drink"
  },
  {
    "name": "Pacific Pulse Zero", 
    "type": "Zero-Sugar Energy Drink"
  }
]""",
            }
        ),
        help_text="JSON array of products with name and type fields",
        label="Products (JSON)",
    )
    
    additional_languages = forms.ModelMultipleChoiceField(
        queryset=Language.objects.filter(is_active=True).exclude(code='en'),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        help_text="Select additional languages for this campaign (English is included by default)",
        label="Additional Languages"
    )
    
    reference_image = forms.ImageField(
        required=False,
        help_text="Optional reference image that will be normalized to 1024x1024 pixels and used as the first generated asset",
        label="Reference Image",
        widget=forms.ClearableFileInput(attrs={"class": "form-control", "accept": "image/*"})
    )

    class Meta:
        model = Brief
        fields = ["title", "target_region", "target_audience", "campaign_message", "primary_language", "reference_image"]
        widgets = {
            "title": forms.TextInput(
                attrs={"placeholder": "Pacific Pulse Energy Drink Launch", "class": "form-control"}
            ),
            "target_region": forms.TextInput(
                attrs={
                    "placeholder": "Pacific Coast US/Mexico border cities",
                    "class": "form-control",
                }
            ),
            "target_audience": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "18-30, urban, bilingual EN/ES, health-conscious but fun-seeking",
                    "class": "form-control",
                }
            ),
            "campaign_message": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Natural energy that connects you to the coastal lifestyle",
                    "class": "form-control",
                }
            ),
            "primary_language": forms.Select(attrs={"class": "form-control"}),
        }

    def clean_products_json(self):
        """Validate and parse products JSON"""
        products_json = self.cleaned_data["products_json"]

        try:
            products = json.loads(products_json)
        except json.JSONDecodeError as e:
            raise forms.ValidationError(f"Invalid JSON format: {e}")

        if not isinstance(products, list):
            raise forms.ValidationError("Products must be a JSON array")

        if len(products) < 1:
            raise forms.ValidationError("At least 1 product is required")

        for i, product in enumerate(products):
            if not isinstance(product, dict):
                raise forms.ValidationError(f"Product {i + 1} must be an object")

            if "name" not in product:
                raise forms.ValidationError(f"Product {i + 1} missing 'name' field")

            if not product["name"].strip():
                raise forms.ValidationError(f"Product {i + 1} name cannot be empty")

        return products

    def save(self, commit=True):
        """Save brief with parsed products JSON, languages, and normalized reference image"""
        brief = super().save(commit=False)
        brief.products = self.cleaned_data["products_json"]
        
        # Process reference image if provided
        reference_image = self.cleaned_data.get("reference_image")
        if reference_image:
            try:
                # Normalize the image to 1024x1024
                normalized_image = normalize_reference_image(reference_image)
                brief.reference_image = normalized_image
            except Exception as e:
                # If image processing fails, add a form error
                raise forms.ValidationError(f"Failed to process reference image: {str(e)}")

        if commit:
            brief.save()
            # Save many-to-many relationships after the instance is saved
            if self.cleaned_data.get("additional_languages"):
                brief.supported_languages.set(self.cleaned_data["additional_languages"])

        return brief


class JSONBriefUploadForm(forms.Form):
    """Alternative form for uploading JSON/YAML brief files"""

    brief_file = forms.FileField(
        help_text="Upload a JSON or YAML file containing campaign brief",
        widget=forms.FileInput(attrs={"accept": ".json,.yaml,.yml", "class": "form-control"}),
    )
    
    reference_image = forms.ImageField(
        required=False,
        help_text="Optional reference image that will be normalized to 1024x1024 pixels and used as the first generated asset",
        label="Reference Image",
        widget=forms.ClearableFileInput(attrs={"class": "form-control", "accept": "image/*"})
    )

    def clean_brief_file(self):
        """Validate and parse uploaded brief file"""
        brief_file = self.cleaned_data["brief_file"]

        if not brief_file.name.lower().endswith((".json", ".yaml", ".yml")):
            raise forms.ValidationError("File must be JSON or YAML format")

        try:
            content = brief_file.read().decode("utf-8")
            brief_file.seek(0)  # Reset file pointer

            if brief_file.name.lower().endswith(".json"):
                data = json.loads(content)
            else:
                data = yaml.safe_load(content)

            # Validate required fields
            required_fields = [
                "title",
                "target_region",
                "target_audience",
                "campaign_message",
                "products",
            ]
            missing_fields = [field for field in required_fields if field not in data]

            if missing_fields:
                raise forms.ValidationError(f"Missing required fields: {', '.join(missing_fields)}")

            # Validate products
            if not isinstance(data["products"], list) or len(data["products"]) < 1:
                raise forms.ValidationError("Must include at least 1 product")

            return data

        except (json.JSONDecodeError, yaml.YAMLError) as e:
            raise forms.ValidationError(f"Invalid file format: {e}")
        except UnicodeDecodeError:
            raise forms.ValidationError("File encoding not supported")

    def save(self):
        """Create Brief instance from uploaded file data"""
        data = self.cleaned_data["brief_file"]
        
        # Handle primary language - can be ID or code
        primary_language = None
        if "primary_language" in data:
            primary_lang_value = data["primary_language"]
            if isinstance(primary_lang_value, str):
                # Language code provided
                try:
                    primary_language = Language.objects.get(code=primary_lang_value, is_active=True)
                except Language.DoesNotExist:
                    # Fallback to English if code not found
                    primary_language = Language.objects.get(code='en')
            else:
                # Language ID provided (backward compatibility)
                try:
                    primary_language = Language.objects.get(id=primary_lang_value, is_active=True)
                except Language.DoesNotExist:
                    primary_language = Language.objects.get(code='en')
        else:
            # Default to English
            primary_language = Language.objects.get(code='en')

        brief = Brief.objects.create(
            title=data["title"],
            target_region=data["target_region"],
            target_audience=data["target_audience"],
            campaign_message=data["campaign_message"],
            products=data["products"],
            primary_language=primary_language
        )
        
        # Process reference image if provided
        reference_image = self.cleaned_data.get("reference_image")
        if reference_image:
            try:
                # Normalize the image to 1024x1024
                normalized_image = normalize_reference_image(reference_image)
                brief.reference_image = normalized_image
                brief.save()  # Save the brief with the reference image
            except Exception as e:
                # If image processing fails, delete the brief and raise error
                brief.delete()
                raise forms.ValidationError(f"Failed to process reference image: {str(e)}")
        
        # Handle additional languages - can be IDs or codes
        if "additional_languages" in data and data["additional_languages"]:
            additional_langs = []
            for lang_value in data["additional_languages"]:
                if isinstance(lang_value, str):
                    # Language code provided
                    try:
                        lang = Language.objects.get(code=lang_value, is_active=True)
                        additional_langs.append(lang)
                    except Language.DoesNotExist:
                        pass  # Skip invalid codes
                else:
                    # Language ID provided (backward compatibility)
                    try:
                        lang = Language.objects.get(id=lang_value, is_active=True)
                        additional_langs.append(lang)
                    except Language.DoesNotExist:
                        pass  # Skip invalid IDs
            
            if additional_langs:
                brief.supported_languages.set(additional_langs)

        return brief
