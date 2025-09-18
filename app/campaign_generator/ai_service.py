import base64
import os
import time
from io import BytesIO

import openai
import requests
from django.conf import settings
from django.utils import timezone
from django.utils.text import slugify
from PIL import Image, ImageDraw, ImageFont


class CampaignGenerator:
    """Generate campaign assets with aspect-ratio specific prompts"""

    def __init__(self):
        self.client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        self.output_base = os.path.join(settings.MEDIA_ROOT, "outputs")
        os.makedirs(self.output_base, exist_ok=True)

        # Feature flag for outpainting approach (configurable via settings)
        self.use_outpaint_method = getattr(settings, "USE_OUTPAINT_METHOD", True)

        # Development mode flag - when True, uses mock generation instead of real API calls
        self.dev_mode = getattr(settings, "AI_DEV_MODE", False)

    def generate_campaign_assets(self, brief):
        """Generate images for each product x aspect ratio using selected method

        Each generation creates a new GenerationRun. If it fails, just create another run.
        This ensures visual consistency within each run and easy retry capability.
        """
        from .models import GenerationRun

        # Get next run index for this brief
        latest_run = GenerationRun.objects.filter(brief=brief).order_by("-run_index").first()
        next_run_index = (latest_run.run_index + 1) if latest_run else 1

        # Create new generation run
        generation_run = GenerationRun.objects.create(brief=brief, run_index=next_run_index)

        assets = []
        total_time = 0

        try:
            # First, create reference image assets if a reference image was uploaded
            if brief.reference_image:
                print("📸 Creating reference image assets...")
                reference_assets = self._create_reference_image_assets(brief, generation_run)
                assets.extend(reference_assets)
                # Reference images have 0 generation time

            else:
                # Generate all AI assets for this run (products × languages × aspect ratios)
                for language in brief.get_all_languages():
                    for product in brief.products:
                        if self.use_outpaint_method:
                            # NEW METHOD: Generate consistent base image, then outpaint for different aspect ratios
                            product_assets = self._generate_assets_with_outpainting(
                                product, brief, generation_run, language
                            )
                        else:
                            # ORIGINAL METHOD: Generate 3 DIFFERENT images, each optimized for its aspect ratio
                            square_asset = self.generate_square_image(
                                product, brief, generation_run, language
                            )
                            story_asset = self.generate_story_image(
                                product, brief, generation_run, language
                            )
                            landscape_asset = self.generate_landscape_image(
                                product, brief, generation_run, language
                            )
                            product_assets = [square_asset, story_asset, landscape_asset]

                        assets.extend(product_assets)
                        for asset in product_assets:
                            total_time += asset.generation_time_seconds or 0

            # Mark run as successful
            generation_run.assets_generated = len(assets)
            generation_run.total_generation_time = total_time
            generation_run.success = True
            generation_run.completed_at = timezone.now()
            generation_run.estimated_cost_usd = len(assets) * 0.040  # DALL-E 3 cost estimate
            generation_run.save()

            return assets

        except Exception as e:
            # Mark run as failed
            generation_run.error_message = str(e)
            generation_run.completed_at = timezone.now()
            generation_run.save()
            raise

    def generate_square_image(self, product, brief, generation_run, language=None):
        """1:1 - Square crop of core scene for Instagram feed"""
        core_prompt = self._build_core_scene_prompt(product, brief, language)
        aspect_prompt = f"""
        {core_prompt}
        Composed for square format (1:1). Center the product prominently.
        Frame tightly for social media feed engagement.
        Leave clear space at bottom 20% for text overlay.
        """
        return self._generate_and_save(
            aspect_prompt, product, brief, "1:1", generation_run, language
        )

    def generate_story_image(self, product, brief, generation_run, language=None):
        """9:16 - Vertical crop of same scene for Stories/TikTok"""
        core_prompt = self._build_core_scene_prompt(product, brief, language)
        aspect_prompt = f"""
        {core_prompt}
        Composed for vertical story format (9:16). Full-height composition.
        Show more vertical context around the same core scene.
        Leave clear space at bottom 15% for text overlay.
        """
        return self._generate_and_save(
            aspect_prompt, product, brief, "9:16", generation_run, language
        )

    def generate_landscape_image(self, product, brief, generation_run, language=None):
        """16:9 - Horizontal crop of same scene for YouTube/video"""
        core_prompt = self._build_core_scene_prompt(product, brief, language)
        aspect_prompt = f"""
        {core_prompt}
        Composed for landscape format (16:9). Wide cinematic framing.
        Show more horizontal context of the same core scene.
        Leave clear space at bottom 15% for text overlay.
        """
        return self._generate_and_save(
            aspect_prompt, product, brief, "16:9", generation_run, language
        )

    def _build_core_scene_prompt(self, product, brief, language=None):
        """Build the core scene description that stays consistent across aspect ratios"""
        if language is None:
            language = brief.primary_language

        return f"""
        Professional product photography of {product["name"]} ({product.get("type", "product")}).
        Setting: {brief.target_region} environment suitable for {brief.target_audience}.
        Brand message: {brief.campaign_message}.
        Language context: {language.name}
        
        Core scene: Product prominently featured with premium lighting and styling.
        Color palette: Bright, energetic, modern.
        Style: High-end commercial photography, clean and engaging.
        Mood: Aspirational and authentic.
        
        The SAME core composition and lighting setup, but optimized framing for different aspect ratios.
        """

    def _generate_and_save(
        self, prompt, product, brief, aspect_ratio, generation_run, language=None
    ):
        """Generate single asset with specific prompt and composition"""
        start_time = time.time()

        # Call DALL-E 3 with optimized prompt
        image_data = self._call_dalle(prompt)

        generation_time = time.time() - start_time

        # Use the unified _save_generated_asset method
        asset = self._save_generated_asset(
            brief=brief,
            product_name=product["name"],
            aspect_ratio=aspect_ratio,
            image_url_or_data=image_data,
            prompt=prompt,
            generation_time=generation_time,
            generation_run=generation_run,
            language=language or brief.primary_language,
        )

        return asset

    def _call_dalle(self, prompt):
        """Call DALL-E 3 API or return mock data in dev mode"""
        if self.dev_mode:
            # Return a mock image in development mode
            return self._create_mock_image()

        try:
            response = self.client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size="1024x1024",  # DALL-E 3 standard size
                quality="standard",
                n=1,
            )

            # Download image data
            import requests

            image_url = response.data[0].url
            image_response = requests.get(image_url)

            return image_response.content

        except Exception as e:
            error_msg = str(e)
            # Provide more helpful error messages for common issues
            if "billing_hard_limit_reached" in error_msg:
                raise Exception(
                    "OpenAI billing limit reached. Please check your OpenAI account billing "
                    "at https://platform.openai.com/usage and add credits or increase your spending limit."
                )
            elif "insufficient_quota" in error_msg:
                raise Exception(
                    "OpenAI API quota exceeded. Please check your usage limits at "
                    "https://platform.openai.com/usage"
                )
            else:
                raise Exception(f"DALL-E generation failed: {error_msg}")

    def _create_mock_image(self):
        """Create a mock image for development/testing purposes"""
        from PIL import Image, ImageDraw, ImageFont

        # Create a simple mock image
        img = Image.new("RGB", (1024, 1024), color="lightblue")
        draw = ImageDraw.Draw(img)

        # Add some text to indicate it's a mock
        try:
            # Try to use a default font
            font = ImageFont.load_default()
        except:
            font = None

        text = "MOCK IMAGE\n(Dev Mode)"
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        x = (1024 - text_width) // 2
        y = (1024 - text_height) // 2

        draw.text((x, y), text, fill="darkblue", font=font)

        # Convert to bytes
        img_bytes = BytesIO()
        img.save(img_bytes, format="JPEG")
        img_bytes.seek(0)
        return img_bytes.getvalue()

    def _add_text_overlay(self, image, campaign_message, aspect_ratio):
        """Add campaign message overlay optimized for aspect ratio"""
        img = image

        # Convert to target aspect ratio first
        img = self._resize_to_aspect_ratio(img, aspect_ratio)

        # Create overlay with semi-transparent background
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # Aspect ratio specific positioning and sizing
        text_config = self._get_text_config(img.size, aspect_ratio)

        # Draw semi-transparent background rectangle
        draw.rectangle(
            [
                (text_config["x"] - 20, text_config["y"] - 15),
                (
                    text_config["x"] + text_config["width"] + 20,
                    text_config["y"] + text_config["height"] + 15,
                ),
            ],
            fill=(0, 0, 0, 180),
        )  # Black with transparency

        # Add campaign message text
        try:
            font = ImageFont.truetype("Arial.ttf", text_config["font_size"])
        except:
            font = ImageFont.load_default()

        # Wrap text if needed
        wrapped_text = self._wrap_text(campaign_message, font, text_config["width"])

        draw.multiline_text(
            (text_config["x"], text_config["y"]),
            wrapped_text,
            font=font,
            fill=(255, 255, 255, 255),  # White text
            align="center",
        )

        # Composite images
        final_img = Image.alpha_composite(img.convert("RGBA"), overlay)
        return final_img.convert("RGB")

    def _resize_to_aspect_ratio(self, img, aspect_ratio):
        """Resize image to target aspect ratio"""
        target_ratios = {
            "1:1": (1024, 1024),
            "9:16": (576, 1024),  # Vertical
            "16:9": (1024, 576),  # Horizontal
        }

        target_size = target_ratios.get(aspect_ratio, (1024, 1024))
        return img.resize(target_size, Image.Resampling.LANCZOS)

    def _get_text_config(self, img_size, aspect_ratio):
        """Get text positioning config for each aspect ratio"""
        width, height = img_size

        configs = {
            "1:1": {
                "x": width // 10,
                "y": height - 120,
                "width": width - (width // 5),
                "height": 80,
                "font_size": 28,
            },
            "9:16": {
                "x": width // 20,
                "y": height - 150,
                "width": width - (width // 10),
                "height": 100,
                "font_size": 24,
            },
            "16:9": {
                "x": width // 8,
                "y": height - 100,
                "width": width - (width // 4),
                "height": 70,
                "font_size": 32,
            },
        }

        return configs.get(aspect_ratio, configs["1:1"])

    def _get_original_square_image_data(self, square_asset, product, brief, base_prompt):
        """Get the original square image data without banner text for outpainting"""

        # If we have the original image data stored, use it
        if hasattr(square_asset, "original_image_data") and square_asset.original_image_data:
            return square_asset.original_image_data

        # Fallback: if for some reason we don't have the original data,
        # we need to regenerate the square image without banner text
        print(
            f"⚠️  Original image data not found, regenerating for {product.get('name', 'Product')}..."
        )

        # Generate the square image using DALL-E (or mock in dev mode)
        square_prompt = self._create_square_prompt(product, brief)

        # Call DALL-E to get the original image
        image_data = self._call_dalle(square_prompt)

        return image_data

    def _convert_to_png_bytes(self, image_data):
        """Convert image data to PNG format for OpenAI API compatibility"""
        from PIL import Image

        # Load the image from bytes
        image = Image.open(BytesIO(image_data))

        # Convert to RGB if necessary (PNG doesn't support all modes)
        if image.mode in ("RGBA", "LA"):
            # Keep transparency for PNG
            pass
        elif image.mode != "RGB":
            image = image.convert("RGB")

        # Convert to PNG bytes
        png_buffer = BytesIO()
        image.save(png_buffer, format="PNG")
        return png_buffer.getvalue()

    def _build_context_and_mask(self, base_1024, direction, step_px=384):
        """
        Build a 1024x1024 RGBA image and a matching mask where:
          - opaque (white) mask = keep content
          - transparent mask = let model paint
        For efficiency we keep (1024 - step_px) px of context and reveal 'step_px' for generation.
        """
        from PIL import Image

        if base_1024.size != (1024, 1024):
            raise ValueError("Context builder expects a 1024x1024 image.")

        ctx_keep = 1024 - step_px
        canvas = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
        mask = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))  # transparent = paint
        opaque = Image.new("RGBA", (ctx_keep, 1024), (255, 255, 255, 255))

        if direction == "right":
            # keep left ctx_keep, paint right step_px
            canvas.paste(base_1024.crop((0, 0, ctx_keep, 1024)), (0, 0))
            mask.paste(opaque, (0, 0))
        elif direction == "left":
            canvas.paste(base_1024.crop((1024 - ctx_keep, 0, 1024, 1024)), (step_px, 0))
            mask.paste(opaque, (step_px, 0))
        elif direction == "down":
            canvas.paste(base_1024.crop((0, 0, 1024, ctx_keep)), (0, 0))
            mask.paste(opaque.resize((1024, ctx_keep)), (0, 0))
        elif direction == "up":
            canvas.paste(base_1024.crop((0, 1024 - ctx_keep, 1024, 1024)), (0, step_px))
            mask.paste(opaque.resize((1024, ctx_keep)), (0, step_px))
        else:
            raise ValueError("Invalid direction")

        return canvas, mask

    def _alpha_ramp(self, width, height, horizontal=True):
        """
        Create a 0..255 alpha ramp (black=0, white=255).
        horizontal=True -> left (0) to right (255)
        """
        from PIL import Image

        ramp = Image.new("L", (width, height))
        # Build gradient using a single-row/column and resize (fast and smooth)
        if horizontal:
            row = Image.linear_gradient("L").resize((width, 1))
            ramp = row.resize((width, height))
        else:
            col = Image.linear_gradient("L").resize((1, height))
            ramp = col.resize((width, height))
        return ramp

    def _blend_strip(self, base, new_strip, overlap_px, direction):
        """
        Alpha-blend the new strip into the base along the seam using an overlap region.
        The overlap is linear to reduce visible seams.
        """
        from PIL import Image, ImageChops

        base = base.convert("RGBA") if base.mode != "RGBA" else base
        new_strip = new_strip.convert("RGBA") if new_strip.mode != "RGBA" else new_strip

        bw, bh = base.size
        sw, sh = new_strip.size
        assert bh == sh or bw == sw, "Strip and base must align on non-extension axis."

        out = base.copy()
        if direction in ("right", "left"):
            # Horizontal seam
            if direction == "right":
                # Overlap on base's right edge
                x_overlap_base = max(0, bw - overlap_px)
                # Overlap on strip's left edge
                overlap_new = new_strip.crop((0, 0, overlap_px, sh))
                overlap_old = out.crop((x_overlap_base, 0, bw, bh))

                ramp = self._alpha_ramp(overlap_px, bh, horizontal=True)  # 0..255 left->right
                # blend: old * (1 - a) + new * a
                overlap_new_mask = ramp
                overlap_old_mask = ImageChops.invert(ramp)

                tmp = Image.new("RGBA", (overlap_px, bh))
                tmp.paste(overlap_old, (0, 0), overlap_old_mask)
                tmp.paste(overlap_new, (0, 0), overlap_new_mask)

                out.paste(tmp, (x_overlap_base, 0))
                # Paste remainder of strip (beyond overlap)
                if sw > overlap_px:
                    remainder = new_strip.crop((overlap_px, 0, sw, sh))
                    out = Image.new("RGBA", (bw + (sw - overlap_px), bh)).convert("RGBA")
                    out.paste(base.crop((0, 0, bw, bh)), (0, 0))
                    out.paste(remainder, (bw, 0))
            else:  # left
                # Overlap on base's left edge
                x_overlap_base = 0
                # Overlap on strip's right edge
                overlap_new = new_strip.crop((sw - overlap_px, 0, sw, sh))
                overlap_old = out.crop((0, 0, overlap_px, bh))

                # Horizontal ramp but reversed (we want 0 at right, 255 at left for new)
                ramp = self._alpha_ramp(overlap_px, bh, horizontal=True).transpose(
                    Image.FLIP_LEFT_RIGHT
                )
                overlap_new_mask = ramp
                overlap_old_mask = ImageChops.invert(ramp)

                tmp = Image.new("RGBA", (overlap_px, bh))
                tmp.paste(overlap_old, (0, 0), overlap_old_mask)
                tmp.paste(overlap_new, (0, 0), overlap_new_mask)

                out.paste(tmp, (0, 0))
                # Paste remainder of strip (beyond overlap) on the left
                if sw > overlap_px:
                    remainder = new_strip.crop((0, 0, sw - overlap_px, sh))
                    expanded = Image.new("RGBA", (bw + (sw - overlap_px), bh))
                    expanded.paste(remainder, (0, 0))
                    expanded.paste(out, (sw - overlap_px, 0))
                    out = expanded

        else:
            # Vertical seam
            if direction == "down":
                y_overlap_base = max(0, bh - overlap_px)
                overlap_new = new_strip.crop((0, 0, sw, overlap_px))
                overlap_old = out.crop((0, y_overlap_base, bw, bh))

                ramp = self._alpha_ramp(sw, overlap_px, horizontal=False)  # top->bottom
                overlap_new_mask = ramp
                overlap_old_mask = ImageChops.invert(ramp)

                tmp = Image.new("RGBA", (bw, overlap_px))
                tmp.paste(overlap_old, (0, 0), overlap_old_mask)
                tmp.paste(overlap_new, (0, 0), overlap_new_mask)

                out.paste(tmp, (0, y_overlap_base))
                if sh > overlap_px:
                    remainder = new_strip.crop((0, overlap_px, sw, sh))
                    out = Image.new("RGBA", (bw, bh + (sh - overlap_px)))
                    out.paste(base.crop((0, 0, bw, bh)), (0, 0))
                    out.paste(remainder, (0, bh))
            else:  # up
                y_overlap_base = 0
                overlap_new = new_strip.crop((0, sh - overlap_px, sw, sh))
                overlap_old = out.crop((0, 0, bw, overlap_px))

                ramp = self._alpha_ramp(sw, overlap_px, horizontal=False).transpose(
                    Image.FLIP_TOP_BOTTOM
                )
                overlap_new_mask = ramp
                overlap_old_mask = ImageChops.invert(ramp)

                tmp = Image.new("RGBA", (bw, overlap_px))
                tmp.paste(overlap_old, (0, 0), overlap_old_mask)
                tmp.paste(overlap_new, (0, 0), overlap_new_mask)

                out.paste(tmp, (0, 0))
                if sh > overlap_px:
                    remainder = new_strip.crop((0, 0, sw, sh - overlap_px))
                    expanded = Image.new("RGBA", (bw, bh + (sh - overlap_px)))
                    expanded.paste(remainder, (0, 0))
                    expanded.paste(out, (0, sh - overlap_px))
                    out = expanded

        return out

    def _extend_once(self, current, direction, step_px=384, overlap_px=192, prompt=""):
        """
        Perform one extension step by creating a 1024x1024 'context+mask' and
        blending the generated strip back into the full canvas.
        """
        from PIL import Image

        if direction in ("right", "left"):
            assert current.height == 1024, "Height must be 1024 for horizontal extension."
            # Build a 1024x1024 context image by sampling edge area of 'current'
            # For robustness when current.width != 1024, we take an aligned crop of width 1024.
            if current.width < 1024:
                # Pad to 1024 (rare if starting exactly 1024)
                padded = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
                padded.paste(current, ((1024 - current.width) // 2, 0))
                base_for_ctx = padded
            else:
                # Use the last 1024 region touching the edge we're extending
                if direction == "right":
                    # For right extension, use the rightmost 1024px as context
                    base_for_ctx = current.crop((current.width - 1024, 0, current.width, 1024))
                else:  # left
                    # For left extension, also use the rightmost 1024px as context
                    # This ensures we extend from the newly generated content, not repeat the original
                    base_for_ctx = current.crop((current.width - 1024, 0, current.width, 1024))

            canvas, mask = self._build_context_and_mask(base_for_ctx, direction, step_px)
            tile = self._call_images_edit(canvas, mask, prompt)
            # Extract the newly painted strip from the tile
            if direction == "right":
                new_strip = tile.crop((1024 - step_px, 0, 1024, 1024))
                # Prepend the retained context part so seam aligns during blend
                new_strip_full = Image.new("RGBA", (step_px + overlap_px, 1024))
                # overlap comes from the tile too (left side of the new strip region)
                overlap_from_tile = tile.crop(
                    (1024 - step_px - overlap_px, 0, 1024 - step_px, 1024)
                )
                new_strip_full.paste(overlap_from_tile, (0, 0))
                new_strip_full.paste(new_strip, (overlap_px, 0))
                return self._blend_strip(current, new_strip_full, overlap_px, "right")
            else:  # left
                new_strip = tile.crop((0, 0, step_px, 1024))
                overlap_from_tile = tile.crop((step_px, 0, step_px + overlap_px, 1024))
                new_strip_full = Image.new("RGBA", (step_px + overlap_px, 1024))
                new_strip_full.paste(new_strip, (0, 0))
                new_strip_full.paste(overlap_from_tile, (step_px, 0))
                return self._blend_strip(current, new_strip_full, overlap_px, "left")

        else:
            assert current.width == 1024, "Width must be 1024 for vertical extension."
            if current.height < 1024:
                padded = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
                padded.paste(current, (0, (1024 - current.height) // 2))
                base_for_ctx = padded
            else:
                if direction == "down":
                    base_for_ctx = current.crop((0, current.height - 1024, 1024, current.height))
                else:  # up
                    base_for_ctx = current.crop((0, 0, 1024, 1024))

            canvas, mask = self._build_context_and_mask(base_for_ctx, direction, step_px)
            tile = self._call_images_edit(canvas, mask, prompt)
            if direction == "down":
                new_strip = tile.crop((0, 1024 - step_px, 1024, 1024))
                overlap_from_tile = tile.crop(
                    (0, 1024 - step_px - overlap_px, 1024, 1024 - step_px)
                )
                new_strip_full = Image.new("RGBA", (1024, step_px + overlap_px))
                new_strip_full.paste(overlap_from_tile, (0, 0))
                new_strip_full.paste(new_strip, (0, overlap_px))
                return self._blend_strip(current, new_strip_full, overlap_px, "down")
            else:  # up
                new_strip = tile.crop((0, 0, 1024, step_px))
                overlap_from_tile = tile.crop((0, step_px, 1024, step_px + overlap_px))
                new_strip_full = Image.new("RGBA", (1024, step_px + overlap_px))
                new_strip_full.paste(new_strip, (0, 0))
                new_strip_full.paste(overlap_from_tile, (0, step_px))
                return self._blend_strip(current, new_strip_full, overlap_px, "up")

    def _call_images_edit(self, canvas_rgba, mask_rgba, prompt):
        """Call OpenAI images.edit API with proper file handling"""
        from PIL import Image

        # Truncate prompt to fit API limit (1000 characters)
        truncated_prompt = prompt[:997] + "..." if len(prompt) > 1000 else prompt

        buf_img = BytesIO()
        buf_mask = BytesIO()
        canvas_rgba.save(buf_img, format="PNG")
        mask_rgba.save(buf_mask, format="PNG")
        buf_img.seek(0)
        buf_mask.seek(0)

        # Set filenames for proper MIME type detection
        buf_img.name = "image.png"
        buf_mask.name = "mask.png"

        resp = self.client.images.edit(
            image=buf_img,
            mask=buf_mask,
            prompt=truncated_prompt,
            size="1024x1024",
            n=1,
            response_format="b64_json",
        )

        # Convert base64 to PIL Image
        image_b64 = resp.data[0].b64_json
        image_bytes = base64.b64decode(image_b64)
        return Image.open(BytesIO(image_bytes)).convert("RGBA")

    def _extend_direction(self, original_image, direction, step_px, prompt):
        """
        Extend in one direction using the correct process:
        1. Create mask covering the entire 1024x1024 image
        2. Slide image+mask to create gap
        3. Send to DALL-E to fill gap
        4. Extract and return the new strip
        """
        from PIL import Image

        # Step 1: Create mask covering entire 1024x1024 image
        mask = Image.new("RGBA", (1024, 1024), (255, 255, 255, 255))  # Opaque = keep

        # Step 2: Create 1024x1024 canvas and slide image+mask
        canvas = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
        canvas_mask = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))

        if direction == "right":
            # Slide image+mask 384px to the left, leaving 384px gap on right
            canvas.paste(original_image, (-step_px, 0))
            canvas_mask.paste(mask, (-step_px, 0))
            # The right 384px of canvas and canvas_mask are now transparent (gap)

        elif direction == "left":
            # Slide image+mask 384px to the right, leaving 384px gap on left
            canvas.paste(original_image, (step_px, 0))
            canvas_mask.paste(mask, (step_px, 0))
            # The left 384px of canvas and canvas_mask are now transparent (gap)

        elif direction == "down":
            # Slide image+mask 384px up, leaving 384px gap on bottom
            canvas.paste(original_image, (0, -step_px))
            canvas_mask.paste(mask, (0, -step_px))
            # The bottom 384px of canvas and canvas_mask are now transparent (gap)

        elif direction == "up":
            # Slide image+mask 384px down, leaving 384px gap on top
            canvas.paste(original_image, (0, step_px))
            canvas_mask.paste(mask, (0, step_px))
            # The top 384px of canvas and canvas_mask are now transparent (gap)

        # Step 3: Send to DALL-E to fill the gap
        tile = self._call_images_edit(canvas, canvas_mask, prompt)

        # Step 4: Extract the new strip
        if direction == "right":
            # Extract the right 384px (the filled gap)
            new_strip = tile.crop((1024 - step_px, 0, 1024, 1024))
        elif direction == "left":
            # Extract the left 384px (the filled gap)
            new_strip = tile.crop((0, 0, step_px, 1024))
        elif direction == "down":
            # Extract the bottom 384px (the filled gap)
            new_strip = tile.crop((0, 1024 - step_px, 1024, 1024))
        elif direction == "up":
            # Extract the top 384px (the filled gap)
            new_strip = tile.crop((0, 0, 1024, step_px))

        return new_strip


    def _create_mock_landscape_image(self):
        """Create a mock landscape image for dev mode"""
        from PIL import Image, ImageDraw, ImageFont

        # Create 1792x1024 landscape image
        img = Image.new("RGB", (1792, 1024), color="lightblue")
        draw = ImageDraw.Draw(img)

        try:
            font = ImageFont.load_default()
        except:
            font = None

        text = "MOCK LANDSCAPE\n(Dev Mode)"
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        x = (1792 - text_width) // 2
        y = (1024 - text_height) // 2

        draw.text((x, y), text, fill="darkblue", font=font)

        # Convert to bytes
        img_bytes = BytesIO()
        img.save(img_bytes, format="JPEG")
        img_bytes.seek(0)
        return img_bytes.getvalue()

    def _create_mock_vertical_image(self):
        """Create a mock vertical image for dev mode"""
        from PIL import Image, ImageDraw, ImageFont

        # Create 1024x1792 portrait image
        img = Image.new("RGB", (1024, 1792), color="lightgreen")
        draw = ImageDraw.Draw(img)

        try:
            font = ImageFont.load_default()
        except:
            font = None

        text = "MOCK VERTICAL\n(Dev Mode)"
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        x = (1024 - text_width) // 2
        y = (1792 - text_height) // 2

        draw.text((x, y), text, fill="darkgreen", font=font)

        # Convert to bytes
        img_bytes = BytesIO()
        img.save(img_bytes, format="JPEG")
        img_bytes.seek(0)
        return img_bytes.getvalue()

    def _extend_image_horizontally_fallback(self, square_image_data, target_aspect_ratio):
        """Fallback PIL-based horizontal extension (original method)"""
        from PIL import Image, ImageFilter

        # Load the square image
        square_image = Image.open(BytesIO(square_image_data))

        # Calculate target dimensions for 16:9 aspect ratio
        original_size = square_image.size[0]  # Assuming square image
        # Use the same dimensions as the incremental method: 1792x1024
        target_width = 1792
        target_height = 1024

        # Create new landscape canvas
        landscape_image = Image.new("RGB", (target_width, target_height), color="white")

        # Calculate position to center the square image
        x_offset = (target_width - original_size) // 2

        # Paste the square image in the center
        landscape_image.paste(square_image, (x_offset, 0))

        # Extend the background by copying and blurring edges
        left_extension = square_image.crop((0, 0, original_size // 4, original_size))
        right_extension = square_image.crop(
            (3 * original_size // 4, 0, original_size, original_size)
        )

        # Blur the extensions to create seamless background
        left_extension = left_extension.filter(ImageFilter.GaussianBlur(radius=2))
        right_extension = right_extension.filter(ImageFilter.GaussianBlur(radius=2))

        # Fill the left and right areas
        for x in range(x_offset):
            landscape_image.paste(left_extension, (x, 0))
        for x in range(x_offset + original_size, target_width):
            landscape_image.paste(right_extension, (x, 0))

        # Convert back to bytes
        output_buffer = BytesIO()
        landscape_image.save(output_buffer, format="JPEG", quality=90)
        return output_buffer.getvalue()

    def _extend_image_vertically_fallback(self, square_image_data, target_aspect_ratio):
        """Fallback PIL-based vertical extension (original method)"""
        from PIL import Image, ImageFilter

        # Load the square image
        square_image = Image.open(BytesIO(square_image_data))

        # Calculate target dimensions for 9:16 aspect ratio
        original_size = square_image.size[0]  # Assuming square image
        # Use the same dimensions as the incremental method: 1024x1792
        target_width = 1024
        target_height = 1792

        # Create new portrait canvas
        portrait_image = Image.new("RGB", (target_width, target_height), color="white")

        # Calculate position to center the square image
        y_offset = (target_height - original_size) // 2

        # Paste the square image in the center
        portrait_image.paste(square_image, (0, y_offset))

        # Extend the background by copying and blurring edges
        top_extension = square_image.crop((0, 0, original_size, original_size // 4))
        bottom_extension = square_image.crop(
            (0, 3 * original_size // 4, original_size, original_size)
        )

        # Blur the extensions to create seamless background
        top_extension = top_extension.filter(ImageFilter.GaussianBlur(radius=2))
        bottom_extension = bottom_extension.filter(ImageFilter.GaussianBlur(radius=2))

        # Fill the top and bottom areas
        for y in range(y_offset):
            portrait_image.paste(top_extension, (0, y))
        for y in range(y_offset + original_size, target_height):
            portrait_image.paste(bottom_extension, (0, y))

        # Convert back to bytes
        output_buffer = BytesIO()
        portrait_image.save(output_buffer, format="JPEG", quality=90)
        return output_buffer.getvalue()

    def _wrap_text(self, text, font, max_width):
        """Wrap text to fit within specified width"""
        words = text.split()
        lines = []
        current_line = []

        for word in words:
            test_line = " ".join(current_line + [word])
            bbox = font.getbbox(test_line)
            if bbox[2] <= max_width:  # width fits
                current_line.append(word)
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                    current_line = [word]
                else:
                    lines.append(word)  # Single word too long

        if current_line:
            lines.append(" ".join(current_line))

        return "\n".join(lines)

    def _save_organized(self, image, product_name, aspect_ratio):
        """Save to organized folder structure as required by FDE brief"""
        # Create folder: outputs/product_name/aspect_ratio/
        folder_name = f"{slugify(product_name)}/{aspect_ratio.replace(':', 'x')}"
        folder_path = os.path.join(self.output_base, folder_name)
        os.makedirs(folder_path, exist_ok=True)

        # Generate filename with timestamp
        timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
        filename = f"campaign_{timestamp}.jpg"
        file_path = os.path.join(folder_path, filename)

        # Save image
        image.save(file_path, "JPEG", quality=90)

        return file_path

    def _image_to_bytes(self, image):
        """Convert PIL Image to bytes for Django FileField"""
        buffer = BytesIO()
        image.save(buffer, format="JPEG", quality=90)
        buffer.seek(0)
        return buffer.getvalue()

    def _get_translated_message(self, brief, language):
        """Get translated campaign message for the specified language, with database caching"""
        if language.code == "en" or language.code == brief.primary_language.code:
            return brief.campaign_message

        # First check if we already have a translation cached for this brief+language combination
        from .models import GeneratedAsset

        existing_asset = (
            GeneratedAsset.objects.filter(brief=brief, language=language)
            .exclude(translated_campaign_message="")
            .first()
        )

        if existing_asset and existing_asset.translated_campaign_message:
            return existing_asset.translated_campaign_message

        # If no cached translation, generate one using TranslationService
        try:
            from .translation_service import TranslationService

            translator = TranslationService()
            translated_message = translator.translate_text(
                text=brief.campaign_message,
                target_language=language.code,
                source_language=brief.primary_language.code,
            )
            return translated_message
        except Exception as e:
            print(f"Translation failed for {language.code}: {e}")
            return brief.campaign_message  # Fallback to original

    def _generate_assets_with_outpainting(self, product, brief, session, language=None):
        """
        NEW METHOD: Generate consistent images using base square + outpainting

        1. Generate a square (1:1) base image with consistent composition
        2. Create landscape (16:9) by extending horizontally (outpainting)
        3. Create vertical (9:16) by extending vertically (outpainting)

        This ensures all images have the same core content and are truly comparable.
        """

        assets = []
        product_name = product.get("name", "Product")

        # Step 1: Generate base square image (1:1) - this will be our reference
        print(f"🎨 Generating base square image for {product_name}...")
        base_prompt = self._build_consistent_base_prompt(product, brief)

        start_time = time.time()
        base_image_data = self._call_dalle(base_prompt)
        generation_time = time.time() - start_time

        # Save base square asset (with text overlay)
        base_url = "mock://base_image.jpg"  # Mock URL for dev mode
        square_asset = self._save_generated_asset(
            brief=brief,
            product_name=product_name,
            aspect_ratio="1:1",
            image_url_or_data=base_image_data,
            prompt=base_prompt,
            generation_time=generation_time,
            generation_run=session,
            language=language or brief.primary_language,
        )
        assets.append(square_asset)

        # Store the original image data (without banner) for outpainting
        square_asset.original_image_data = base_image_data

        # Step 2: Create landscape version using image editing (simulated outpainting)
        print(f"🎨 Creating landscape version for {product_name}...")
        landscape_asset = self._create_landscape_from_square(
            square_asset, product, brief, base_prompt, language
        )
        assets.append(landscape_asset)

        # Step 3: Create vertical version using image editing (simulated outpainting)
        print(f"🎨 Creating vertical version for {product_name}...")
        vertical_asset = self._create_vertical_from_square(
            square_asset, product, brief, base_prompt, language
        )
        assets.append(vertical_asset)

        return assets


    def _build_consistent_base_prompt(self, product, brief):
        """Build a prompt optimized for square format that will work well when extended"""
        product_name = product.get("name", "Product")
        product_type = product.get("type", "product")

        return f"""
        Professional product photography of {product_name} ({product_type}) for social media campaign.
        
        COMPOSITION FOR SQUARE FORMAT (will be extended for other ratios):
        - Product prominently centered in scene
        - Clean, balanced composition with breathing room on all sides
        - Background elements arranged symmetrically
        - Avoid important details near edges (will be extended)
        
        SETTING & STYLE:
        - Location: {brief.target_region} environment 
        - Target audience: {brief.target_audience}
        - Campaign message: {brief.campaign_message}
        - Professional commercial photography
        - High-end lighting and styling
        - Modern, aspirational mood
        
        TECHNICAL REQUIREMENTS:
        - Square composition (1:1 ratio)
        - Central focus with extendable background
        - Consistent lighting across frame
        - Premium visual quality
        - Leave 20% margin at bottom for text overlay
        
        Background should be photographically realistic and easily extendable in both horizontal and vertical directions.
        """.strip()

    def _create_landscape_from_square(
        self, square_asset, product, brief, base_prompt, language=None
    ):
        """Create 16:9 landscape version by extending the square image horizontally"""

        # Get the original square image data (without banner text) for outpainting
        # We need to regenerate the square image without banner text for clean extension
        square_image_data = self._get_original_square_image_data(
            square_asset, product, brief, base_prompt
        )

        # Create outpainting prompt that references the existing image
        landscape_prompt = f"""
        {base_prompt}
        
        LANDSCAPE EXTENSION (16:9):
        - Extend the existing square image horizontally to create a 16:9 landscape
        - Maintain the exact same central composition, lighting, and product positioning
        - Add complementary background elements on left and right sides
        - Keep the same color palette and style as the original square image
        - The central area should be identical to the square version
        """.strip()

        # Create landscape version using OpenAI outpainting
        start_time = time.time()
        landscape_image_data = self._outpaint_landscape(square_image_data, landscape_prompt)
        generation_time = time.time() - start_time

        # Save the extended image (with text overlay)
        landscape_asset = self._save_generated_asset(
            brief=square_asset.brief,
            product_name=square_asset.product_name,
            aspect_ratio="16:9",
            image_url_or_data=landscape_image_data,
            prompt=landscape_prompt,
            generation_time=generation_time,
            generation_run=square_asset.generation_run,
            language=language or square_asset.language,
        )

        return landscape_asset

    def _create_vertical_from_square(
        self, square_asset, product, brief, base_prompt, language=None
    ):
        """Create 9:16 vertical version by extending the square image vertically"""

        # Get the original square image data (without banner text) for outpainting
        # We need to regenerate the square image without banner text for clean extension
        square_image_data = self._get_original_square_image_data(
            square_asset, product, brief, base_prompt
        )

        # Create outpainting prompt that references the existing image
        vertical_prompt = f"""
        {base_prompt}
        
        VERTICAL EXTENSION (9:16):
        - Extend the existing square image vertically to create a 9:16 portrait
        - Maintain the exact same central composition, lighting, and product positioning
        - Add complementary background elements above and below
        - Keep the same color palette and style as the original square image
        - The central area should be identical to the square version
        - Perfect for mobile/story format
        """.strip()

        # Create vertical version using OpenAI outpainting
        start_time = time.time()
        vertical_image_data = self._outpaint_vertical(square_image_data, vertical_prompt)
        generation_time = time.time() - start_time

        # Save the extended image (with text overlay)
        vertical_asset = self._save_generated_asset(
            brief=square_asset.brief,
            product_name=square_asset.product_name,
            aspect_ratio="9:16",
            image_url_or_data=vertical_image_data,
            prompt=vertical_prompt,
            generation_time=generation_time,
            generation_run=square_asset.generation_run,
            language=language or square_asset.language,
        )

        return vertical_asset

    def _outpaint_landscape(self, square_image_data, prompt):
        """Use correct outpainting process to extend a square image horizontally to create a landscape version"""
        if self.dev_mode:
            # In dev mode, use the fallback method that properly extends the input image
            return self._extend_image_horizontally_fallback(square_image_data, "16:9")

        try:
            from PIL import Image

            # Convert image data to PIL Image
            original_image = Image.open(BytesIO(square_image_data)).convert("RGBA")
            if original_image.size != (1024, 1024):
                raise ValueError(f"Expected 1024x1024 image, got {original_image.size}")

            print("🎨 Starting landscape outpainting: 1024x1024 → 1792x1024")

            # Step 1: Extend 384px to the right
            print("🎨 Step 1: Extending right 384px")
            right_strip = self._extend_direction(original_image, "right", 384, prompt)

            # Step 2: Extend 384px to the left
            print("🎨 Step 2: Extending left 384px")
            left_strip = self._extend_direction(original_image, "left", 384, prompt)

            # Step 3: Assemble final image
            print("🎨 Step 3: Assembling final image")
            final_image = Image.new("RGBA", (1792, 1024))

            # Paste left strip (0, 0)
            final_image.paste(left_strip, (0, 0))
            # Paste original image (384, 0)
            final_image.paste(original_image, (384, 0))
            # Paste right strip (1408, 0)
            final_image.paste(right_strip, (1408, 0))

            print(f"✅ Final landscape dimensions: {final_image.size}")

            # Convert back to bytes
            result_buffer = BytesIO()
            final_image.save(result_buffer, format="PNG")
            return result_buffer.getvalue()

        except Exception as e:
            print(f"❌ OpenAI outpainting failed: {e}")
            # Fallback to PIL-based extension
            return self._extend_image_horizontally_fallback(square_image_data, "16:9")

    def _outpaint_vertical(self, square_image_data, prompt):
        """Use correct outpainting process to extend a square image vertically to create a portrait version"""
        if self.dev_mode:
            # In dev mode, use the fallback method that properly extends the input image
            return self._extend_image_vertically_fallback(square_image_data, "9:16")

        try:
            from PIL import Image

            # Convert image data to PIL Image
            original_image = Image.open(BytesIO(square_image_data)).convert("RGBA")
            if original_image.size != (1024, 1024):
                raise ValueError(f"Expected 1024x1024 image, got {original_image.size}")

            print("🎨 Starting portrait outpainting: 1024x1024 → 1024x1792")

            # Step 1: Extend 384px downward
            print("🎨 Step 1: Extending down 384px")
            bottom_strip = self._extend_direction(original_image, "down", 384, prompt)

            # Step 2: Extend 384px upward
            print("🎨 Step 2: Extending up 384px")
            top_strip = self._extend_direction(original_image, "up", 384, prompt)

            # Step 3: Assemble final image
            print("🎨 Step 3: Assembling final image")
            final_image = Image.new("RGBA", (1024, 1792))

            # Paste top strip (0, 0)
            final_image.paste(top_strip, (0, 0))
            # Paste original image (0, 384)
            final_image.paste(original_image, (0, 384))
            # Paste bottom strip (0, 1408)
            final_image.paste(bottom_strip, (0, 1408))

            print(f"✅ Final portrait dimensions: {final_image.size}")

            # Convert back to bytes
            result_buffer = BytesIO()
            final_image.save(result_buffer, format="PNG")
            return result_buffer.getvalue()

        except Exception as e:
            print(f"❌ OpenAI outpainting failed: {e}")
            # Fallback to PIL-based extension
            return self._extend_image_vertically_fallback(square_image_data, "9:16")

    def _save_generated_asset(
        self,
        brief,
        product_name,
        aspect_ratio,
        image_url_or_data,
        prompt,
        generation_time,
        generation_run,
        language=None,
    ):
        """Save generated asset from URL or direct image data to database and organized folder"""
        from .models import GeneratedAsset

        # Handle both URL and direct image data
        if isinstance(image_url_or_data, str) and image_url_or_data.startswith(
            ("http://", "https://")
        ):
            # Download image from DALL-E URL
            response = requests.get(image_url_or_data)
            response.raise_for_status()
            image_data = response.content
        else:
            # Direct image data (for dev mode or mock data)
            image_data = image_url_or_data

        # Convert to PIL Image for processing
        image = Image.open(BytesIO(image_data))

        # Get translated campaign message for this language
        campaign_message = self._get_translated_message(brief, language or brief.primary_language)

        # Add text overlay optimized for this aspect ratio
        final_image = self._add_text_overlay(image, campaign_message, aspect_ratio)

        # Save to organized folder structure
        organized_path = self._save_organized(final_image, product_name, aspect_ratio)

        # Create or update database record (handle unique constraint)
        asset_language = language or brief.primary_language
        asset, created = GeneratedAsset.objects.get_or_create(
            generation_run=generation_run,
            product_name=product_name,
            aspect_ratio=aspect_ratio,
            language=asset_language,
            defaults={
                "brief": brief,
                "ai_prompt": prompt,
                "organized_file_path": organized_path,
                "generation_time_seconds": generation_time,
                "translated_campaign_message": campaign_message
                if asset_language.code != brief.primary_language.code
                else "",
                "translation_status": "translated"
                if asset_language.code != brief.primary_language.code
                else "original",
            },
        )

        # If asset already existed, update it with new data
        if not created:
            asset.ai_prompt = prompt
            asset.organized_file_path = organized_path
            asset.generation_time_seconds = generation_time
            # Update translation if this is a non-primary language and we don't have a translation yet
            if (
                asset_language.code != brief.primary_language.code
                and not asset.translated_campaign_message
            ):
                asset.translated_campaign_message = campaign_message
                asset.translation_status = "translated"
            asset.save()

        # Also save to Django media field for web display
        filename = (
            f"{slugify(product_name)}_{aspect_ratio.replace(':', 'x')}_{int(time.time())}.jpg"
        )
        asset.image_file.save(filename, BytesIO(self._image_to_bytes(final_image)), save=True)

        return asset

    def _create_reference_image_assets(self, brief, generation_run):
        """
        Create assets from the uploaded reference image for all products and languages.

        The reference image is treated as the first asset with 0 generation time.
        """
        from .models import GeneratedAsset
        from .utils import get_reference_image_metadata

        assets = []

        # Get metadata about the reference image processing
        metadata = get_reference_image_metadata(brief.reference_image)

        # Load the reference image
        reference_image = Image.open(brief.reference_image.path)

        # Create reference assets for each product and language
        for language in brief.get_all_languages():
            for product in brief.products:
                product_name = product.get("name", "Product")

                # Convert reference image to bytes for processing
                reference_buffer = BytesIO()
                reference_image.save(reference_buffer, format="JPEG", quality=90)
                reference_image_data = reference_buffer.getvalue()

                # Create reference assets for all aspect ratios using the same high-quality extension as AI images
                aspect_ratios = [
                    ("1:1", reference_image_data),  # Original square - no extension needed
                    (
                        "16:9",
                        self._outpaint_landscape(
                            reference_image_data,
                            f"Professional background for {product_name} product campaign",
                        ),
                    ),  # Landscape
                    (
                        "9:16",
                        self._outpaint_vertical(
                            reference_image_data,
                            f"Professional background for {product_name} product campaign",
                        ),
                    ),  # Portrait
                ]

                for aspect_ratio, extended_image_data in aspect_ratios:
                    # Get translated campaign message for this language
                    campaign_message = self._get_translated_message(brief, language)

                    # Convert extended image data back to PIL Image for text overlay
                    extended_image = Image.open(BytesIO(extended_image_data))

                    # Add text overlay to the extended reference image for this aspect ratio
                    final_image = self._add_text_overlay(
                        extended_image, campaign_message, aspect_ratio
                    )

                    # Save to organized folder structure
                    organized_path = self._save_organized(final_image, product_name, aspect_ratio)

                    # Create database record for reference asset
                    asset = GeneratedAsset.objects.create(
                        brief=brief,
                        generation_run=generation_run,
                        product_name=product_name,
                        aspect_ratio=aspect_ratio,
                        language=language,
                        ai_prompt=f"Reference image: {metadata['processing_note']}",
                        generation_time_seconds=0.0,  # Reference images have 0 generation time
                        organized_file_path=organized_path,
                        translated_campaign_message=campaign_message
                        if language.code != brief.primary_language.code
                        else "",
                        translation_status="translated"
                        if language.code != brief.primary_language.code
                        else "original",
                        is_reference_image=True,
                        reference_image_note=metadata["processing_note"],
                    )

                    # Also save to Django media field for web display
                    filename = f"ref_{slugify(product_name)}_{aspect_ratio.replace(':', 'x')}_{int(time.time())}.jpg"
                    asset.image_file.save(
                        filename, BytesIO(self._image_to_bytes(final_image)), save=True
                    )

                    assets.append(asset)
                    print(
                        f"✅ Created reference asset: {product_name} ({aspect_ratio}) in {language.name}"
                    )

        return assets
