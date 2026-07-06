"""
Gemini image generation module for Omelet.

Uses Google Gemini API to generate images from text prompts,
with special support for blog featured images.
"""

from pathlib import Path

from google import genai
from google.genai import types

from .image_metadata import strip_image_metadata


STYLE_PROMPTS = {
    "academic": (
        "Black and white line art, textbook figure style, clean white or light gray background, "
        "simple geometric shapes and icons, hand-drawn sketch aesthetic, academic labels, "
        "like a figure from O'Reilly book or IEEE paper. Include a 'Figure 1:' caption at bottom"
    ),
    "tech": (
        "Dark blue/purple gradient background, modern minimalist tech illustration style, "
        "glowing geometric elements, professional quality"
    ),
    "minimal": (
        "Clean white background, simple line art, minimalist design, elegant and professional"
    ),
    "colorful": (
        "Vibrant gradient background, modern flat design, bold colors, eye-catching composition"
    ),
    "constructivism": (
        "Russian Constructivism poster style merged with modern minimalism. "
        "Asymmetric composition with strong 45-degree diagonal energy. "
        "Color palette strictly limited: deep red (#C8102E), pure black, off-white cream (#F5F1E8), "
        "single accent of deep navy blue. Flat colors only, NO gradients. "
        "Bold geometric shapes overlapping (rectangles, circles, triangles). "
        "Heavy sans-serif block typography for any text elements. "
        "Diagonal red wedge composition reminiscent of El Lissitzky's 'Beat the Whites with the Red Wedge' (1919). "
        "Generous negative space. High contrast, propaganda-poster boldness, machine-aesthetic. "
        "Reference: Rodchenko, El Lissitzky, Mayakovsky 1919-1925 designs. "
        "NOT generic flat design, NOT Bauhaus pastel — must have aggressive constructivist energy."
    ),
    "socialist-realism": (
        "Soviet Socialist Realism propaganda poster style merged with modern minimalism. "
        "Monumental, heroic, optimistic composition with one central idealized figure "
        "(scientist, engineer, or worker) in a confident heroic three-quarter pose, "
        "looking forward with determination. Slightly low camera angle for monumental feel. "
        "Painterly brush strokes, NOT photorealistic. Idealized realism. "
        "Dramatic chiaroscuro lighting from upper left, casting confident shadow. "
        "Color palette: dominant deep crimson red (#A8121E), warm cream/parchment background (#E8DCC4), "
        "strong black outlines, golden ochre highlights (#C4923A), muted teal accents. "
        "Limited to 5 colors max. Bright optimistic palette. "
        "Background elements (minimalist): rising sun with red rays, abstracted industrial silhouettes, "
        "stylized wheat-stalks or banner motifs. Generous negative space. "
        "Reference: Aleksandr Deyneka, Vera Mukhina, Vasily Yefanov, Soviet 1940s scientific posters. "
        "Modern minimalist execution with socialist realism DNA — heroic, painterly, propagandistic."
    ),
}


# Models that support high-resolution output (2K/4K) and aspect_ratio via
# ImageConfig. Nano Banana Pro (gemini-3-pro-image) and Nano Banana 2
# (gemini-3.1-flash-image family) all accept image_size up to "4K".
HIGH_RES_MODEL_PREFIXES = ("gemini-3-pro-image", "gemini-3.1-flash-image", "gemini-3.1-flash-lite-image")


class GeminiImageGenerator:
    """Generate images using Google Gemini API."""

    def __init__(self, api_key: str, model: str = "gemini-3-pro-image"):
        self.client = genai.Client(api_key=api_key)
        self.model = model

    def _supports_high_res(self) -> bool:
        return any(self.model.startswith(prefix) for prefix in HIGH_RES_MODEL_PREFIXES)

    def _build_image_config(self, image_size, aspect_ratio):
        """Build an ImageConfig, defaulting Pro/Nano-Banana-2 models to 2K output."""
        if image_size is None and self._supports_high_res():
            image_size = "2K"
        if not image_size and not aspect_ratio:
            return None
        return types.ImageConfig(image_size=image_size, aspect_ratio=aspect_ratio)

    @staticmethod
    def _extract_image_bytes(response):
        """Pull the first inline image blob out of a response, if any.

        Nano Banana Pro is a "thinking" image model: an occasional candidate
        comes back with only reasoning parts (or ``content.parts is None``)
        before the image turn. Walk every candidate/part defensively instead of
        assuming ``candidates[0].content.parts`` is a non-empty list.
        """
        for candidate in getattr(response, "candidates", None) or []:
            content = getattr(candidate, "content", None)
            for part in getattr(content, "parts", None) or []:
                inline = getattr(part, "inline_data", None)
                if inline and inline.data:
                    return inline.data
        return None

    def generate_image(
        self,
        prompt: str,
        output_path: str,
        image_size: str = None,
        aspect_ratio: str = None,
        max_retries: int = 3,
    ) -> str:
        """
        Generate an image from a text prompt and save it.

        Args:
            prompt: Text description of the image to generate.
            output_path: Path where the image will be saved.
            image_size: Output resolution ("1K", "2K", "4K"). Only honored by
                high-res models; defaults to "2K" for those, None otherwise.
            aspect_ratio: Output aspect ratio (e.g. "16:9", "1:1", "4:3").
            max_retries: Attempts before giving up when a response comes back
                without an image (thinking models do this occasionally).

        Returns:
            Path to the saved image file.

        Raises:
            RuntimeError: If no image was generated after ``max_retries``.
        """
        config = types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
            image_config=self._build_image_config(image_size, aspect_ratio),
        )

        last_reason = None
        for _ in range(max_retries):
            response = self.client.models.generate_content(
                model=self.model, contents=prompt, config=config
            )
            data = self._extract_image_bytes(response)
            if data:
                output_file = Path(output_path)
                output_file.parent.mkdir(parents=True, exist_ok=True)
                with open(output_file, "wb") as f:
                    f.write(data)
                strip_image_metadata(output_file)
                return str(output_file)

            candidates = getattr(response, "candidates", None) or []
            last_reason = candidates[0].finish_reason if candidates else "no candidates"

        raise RuntimeError(
            f"No image was generated by Gemini after {max_retries} attempts "
            f"(model={self.model}, last finish_reason={last_reason})"
        )

    def generate_blog_featured_image(
        self,
        topic: str,
        output_path: str,
        style: str = "academic",
        image_size: str = None,
    ) -> str:
        """
        Generate a featured image for a blog post.

        Args:
            topic: The blog topic/title.
            output_path: Path where the image will be saved.
            style: Image style preset (academic, tech, minimal, colorful).
            image_size: Output resolution ("1K", "2K", "4K") for high-res models.

        Returns:
            Path to the saved image file.
        """
        style_desc = STYLE_PROMPTS.get(style, STYLE_PROMPTS["academic"])

        prompt = (
            f"Create a featured image for a programming blog about: {topic}\n\n"
            f"Requirements:\n"
            f"- {style_desc}\n"
            f"- Professional quality suitable as blog hero image\n"
            f"- 16:9 aspect ratio composition\n"
            f"- Clean, educational aesthetic suitable for tech blog"
        )

        return self.generate_image(
            prompt, output_path, image_size=image_size, aspect_ratio="16:9"
        )
