"""
Utility functions for the campaign generator app.
"""
import os
from PIL import Image
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from io import BytesIO


def normalize_reference_image(image_file, target_size=(1024, 1024)):
    """
    Normalize an uploaded image to exactly 1024x1024 pixels using FILL strategy.
    
    This function:
    1. Opens the uploaded image
    2. Scales to FILL the entire 1024x1024 area (crops excess, no padding)
    3. Saves it as a high-quality JPEG
    4. Returns a Django File object ready for storage
    
    Args:
        image_file: Uploaded file object (Django UploadedFile)
        target_size: Tuple of (width, height) for the output size
        
    Returns:
        ContentFile: Django file object with normalized image data
        
    Raises:
        PIL.UnidentifiedImageError: If the file is not a valid image
        ValueError: If the image cannot be processed
    """
    try:
        # Open the image
        with Image.open(image_file) as img:
            # Convert to RGB if necessary (handles RGBA, grayscale, etc.)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Use FILL strategy: scale to fill entire target size, then crop excess
            original_width, original_height = img.size
            target_width, target_height = target_size
            
            # Calculate the scale factor to FILL the target size (crop excess)
            scale_factor = max(target_width / original_width, target_height / original_height)
            
            # Calculate new dimensions (will be >= target size)
            new_width = int(original_width * scale_factor)
            new_height = int(original_height * scale_factor)
            
            # Resize the image to fill the target area
            img_resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Calculate crop position to center the image
            left = (new_width - target_width) // 2
            top = (new_height - target_height) // 2
            right = left + target_width
            bottom = top + target_height
            
            # Crop to exact target size
            normalized_img = img_resized.crop((left, top, right, bottom))
            
            # Save to BytesIO buffer as high-quality JPEG
            buffer = BytesIO()
            normalized_img.save(buffer, format='JPEG', quality=95, optimize=True)
            buffer.seek(0)
            
            # Generate filename
            original_name = getattr(image_file, 'name', 'reference_image.jpg')
            name_without_ext = os.path.splitext(original_name)[0]
            normalized_filename = f"{name_without_ext}_normalized_1024x1024.jpg"
            
            # Return as ContentFile
            return ContentFile(buffer.getvalue(), name=normalized_filename)
            
    except Exception as e:
        raise ValueError(f"Failed to process reference image: {str(e)}")


def get_reference_image_metadata(original_file):
    """
    Generate metadata about a reference image for display purposes.
    
    Args:
        original_file: The original uploaded file
        
    Returns:
        dict: Metadata about the processing
    """
    try:
        with Image.open(original_file) as img:
            original_size = img.size
            file_size = original_file.size if hasattr(original_file, 'size') else 0
            
            return {
                'original_dimensions': f"{original_size[0]}x{original_size[1]}",
                'normalized_dimensions': "1024x1024",
                'original_format': img.format or 'Unknown',
                'normalized_format': 'JPEG',
                'original_file_size': file_size,
                'processing_note': f"Normalized from {original_size[0]}x{original_size[1]} to 1024x1024 pixels"
            }
    except Exception:
        return {
            'original_dimensions': 'Unknown',
            'normalized_dimensions': "1024x1024", 
            'original_format': 'Unknown',
            'normalized_format': 'JPEG', 
            'original_file_size': 0,
            'processing_note': "Normalized to 1024x1024 pixels"
        }
