"""
Main CLI module for Omelet
"""

import click
import requests
from pathlib import Path
from .markdown_processor import MarkdownProcessor
from .image_uploader import ImageUploader
from .gcs_uploader import GCSUploader
from .gcloud_auth import GCloudAuth
from .config import Config
from .image_metadata import strip_image_metadata, scrub_watermark as scrub_image


@click.group()
def cli():
    """Omelet CLI - Process markdown files with ease"""
    pass


def convert_plantuml_to_image(puml_content: str, output_path: Path) -> bool:
    """Convert PlantUML content to PNG image via puml.omelet.tech"""
    content = puml_content.strip()
    if not content.startswith("@startuml"):
        content = "@startuml\n" + content
    if not content.endswith("@enduml"):
        content = content + "\n@enduml"

    url = "https://puml.omelet.tech/png"
    headers = {"Content-Type": "text/plain; charset=utf-8"}

    response = requests.post(url, data=content.encode("utf-8"), headers=headers, timeout=60)
    response.raise_for_status()

    output_path.write_bytes(response.content)
    return True


@cli.command()
@click.argument("file", type=click.Path(exists=True))
@click.option("--folder", "-f", help="Folder name for organizing uploads (defaults to parent folder)")
@click.option("--no-plantuml", is_flag=True, help="Skip PlantUML processing")
def buildmarkdown(file, folder, no_plantuml):
    """Process a markdown file and upload local images"""
    file_path = Path(file)

    if not file_path.suffix.lower() == ".md":
        click.echo(f"Error: {file} is not a markdown file", err=True)
        raise click.Abort()

    # Use provided folder or default to parent folder name
    if folder is None:
        folder = file_path.parent.name

    click.echo(f"Processing markdown file: {file}")

    # Initialize components
    config = Config()
    processor = MarkdownProcessor()

    # Choose uploader based on configuration
    if config.use_gcs:
        # Use Google Cloud Storage
        auth = GCloudAuth()
        if not auth.is_authenticated():
            click.echo("Error: Not authenticated with Google Cloud.", err=True)
            click.echo("Please run: gcloud auth application-default login", err=True)
            raise click.Abort()
        uploader = GCSUploader(config.gcs_bucket, auth)
        click.echo(f"Using Google Cloud Storage (bucket: {config.gcs_bucket})")
    else:
        # Use API backend
        uploader = ImageUploader(config)
        click.echo(f"Using API backend: {config.backend_url}")

    try:
        # Read the markdown file
        content = file_path.read_text(encoding="utf-8")

        # Process PlantUML blocks first
        if not no_plantuml:
            puml_blocks = processor.find_plantuml_blocks(content)
            if puml_blocks:
                click.echo(f"Found {len(puml_blocks)} PlantUML block(s) to convert")

                for block in puml_blocks:
                    try:
                        image_filename = f"{block['diagram_name']}-{block['hash']}.png"
                        image_path = file_path.parent / image_filename

                        click.echo(f"Converting PlantUML: {block['diagram_name']}...")
                        convert_plantuml_to_image(block['content'], image_path)
                        click.echo(f"✓ Generated: {image_filename}")

                        content = processor.replace_plantuml_with_image(content, block, image_filename)
                        file_path.write_text(content, encoding="utf-8")

                    except requests.exceptions.RequestException as e:
                        error_msg = str(e)
                        if hasattr(e, "response") and e.response is not None:
                            if "x-plantuml-diagram-error" in e.response.headers:
                                error_msg = e.response.headers["x-plantuml-diagram-error"]
                        click.echo(f"✗ Failed to convert {block['diagram_name']}: {error_msg}", err=True)
            else:
                click.echo("No PlantUML blocks found")

        # Re-read content after PlantUML processing
        content = file_path.read_text(encoding="utf-8")

        # Find all local images
        images = processor.find_local_images(content, file_path)

        if not images:
            click.echo("No local images found in the markdown file")
            return

        click.echo(f"Found {len(images)} local image(s) to upload")

        # Upload images and replace URLs one by one
        total_updated = 0

        with click.progressbar(images, label="Uploading images") as bar:
            for image_info in bar:
                try:
                    if strip_image_metadata(image_info["path"]):
                        click.echo(f"\n✓ Stripped metadata: {image_info['path'].name}")
                    public_url = uploader.upload_image(image_info["path"], folder)
                    click.echo(f"\n✓ Uploaded: {image_info['path'].name} -> {public_url}")

                    # Replace URL in content immediately after successful upload
                    url_mapping = {image_info["original"]: public_url}
                    content = processor.replace_urls(content, url_mapping)

                    # Save the updated content to file
                    file_path.write_text(content, encoding="utf-8")
                    total_updated += 1
                    click.echo(f"✓ Updated markdown file with new URL")

                except Exception as e:
                    click.echo(f"\n✗ Failed to upload {image_info['path'].name}: {str(e)}", err=True)

        if total_updated > 0:
            click.echo(f"\n✓ Successfully updated {total_updated} image URL(s) in {file}")

    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        raise click.Abort()


class _GhostFallbackUploader:
    """Fallback uploader that pushes images straight to Ghost's native image API.

    Used as last-resort when neither GCS nor a configured backend_url is available,
    so a `publish` invocation never silently leaves local image paths in the post body.
    """

    def __init__(self, ghost_client):
        self._ghost = ghost_client

    def upload_image(self, image_path: Path, folder: str) -> str:  # noqa: ARG002 - folder ignored by Ghost
        return self._ghost.upload_image(str(image_path))


def _pick_uploader(config: Config):
    """Return (uploader, label) using a fallback chain so we never silently skip upload.

    Priority:
      1. GCS (when ``use_gcs=True`` AND gcloud auth works)
      2. ImageUploader (when ``backend_url`` is configured)
      3. Ghost native image API (always available once Ghost credentials are set)

    Returns ``(None, None)`` only if no uploader is usable, in which case the caller
    should abort rather than proceed with local paths in the body.
    """
    if config.use_gcs:
        auth = GCloudAuth()
        if auth.is_authenticated():
            return GCSUploader(config.gcs_bucket, auth), f"Google Cloud Storage (bucket: {config.gcs_bucket})"
        click.echo(
            "⚠ GCS configured but gcloud auth missing - run `gcloud auth application-default login`. "
            "Falling back to next available uploader.",
            err=True,
        )

    if getattr(config, "backend_url", None):
        return ImageUploader(config), f"ImageUploader backend ({config.backend_url})"

    if config.ghost_api_url and config.ghost_admin_api_key:
        from .ghost_client import GhostClient

        ghost = GhostClient(config.ghost_api_url, config.ghost_admin_api_key)
        return _GhostFallbackUploader(ghost), "Ghost native image storage (fallback)"

    return None, None


def process_markdown_images(file_path: Path, config: Config, processor: MarkdownProcessor, skip_plantuml: bool = False, scrub: bool = False):
    """Process PlantUML blocks and upload local images, return updated content."""
    content = file_path.read_text(encoding="utf-8")
    folder = file_path.parent.name

    uploader, uploader_label = _pick_uploader(config)
    if uploader is not None:
        click.echo(f"Using {uploader_label}")

    # Process PlantUML blocks first
    if not skip_plantuml:
        puml_blocks = processor.find_plantuml_blocks(content)
        if puml_blocks:
            click.echo(f"Found {len(puml_blocks)} PlantUML block(s) to convert")
            for block in puml_blocks:
                try:
                    image_filename = f"{block['diagram_name']}-{block['hash']}.png"
                    image_path = file_path.parent / image_filename

                    click.echo(f"Converting PlantUML: {block['diagram_name']}...")
                    convert_plantuml_to_image(block['content'], image_path)
                    click.echo(f"✓ Generated: {image_filename}")

                    content = processor.replace_plantuml_with_image(content, block, image_filename)
                    file_path.write_text(content, encoding="utf-8")
                except requests.exceptions.RequestException as e:
                    error_msg = str(e)
                    if hasattr(e, "response") and e.response is not None:
                        if "x-plantuml-diagram-error" in e.response.headers:
                            error_msg = e.response.headers["x-plantuml-diagram-error"]
                    click.echo(f"✗ Failed to convert {block['diagram_name']}: {error_msg}", err=True)

    # Re-read content after PlantUML processing
    content = file_path.read_text(encoding="utf-8")

    images = processor.find_local_images(content, file_path)

    # Fail loud when there are images to upload but no uploader is available.
    # Silent skipping here used to produce Ghost drafts with broken `./foo.png` paths.
    if images and uploader is None:
        click.echo(
            f"✗ Found {len(images)} local image(s) but no uploader is configured. "
            "Configure one of: GCS auth (`gcloud auth application-default login`), "
            "`backend_url` in ~/.omelet.json, or Ghost admin credentials.",
            err=True,
        )
        raise click.Abort()

    if uploader and images:
        click.echo(f"Found {len(images)} local image(s) to upload")
        for image_info in images:
            try:
                if scrub and scrub_image(image_info["path"]):
                    click.echo(f"✓ Scrubbed watermark: {image_info['path'].name}")
                if strip_image_metadata(image_info["path"]):
                    click.echo(f"✓ Stripped metadata: {image_info['path'].name}")
                public_url = uploader.upload_image(image_info["path"], folder)
                click.echo(f"✓ Uploaded: {image_info['path'].name}")
                url_mapping = {image_info["original"]: public_url}
                content = processor.replace_urls(content, url_mapping)
                file_path.write_text(content, encoding="utf-8")
            except Exception as e:
                click.echo(f"✗ Failed to upload {image_info['path'].name}: {str(e)}", err=True)

    return content


@cli.command()
@click.argument("file", type=click.Path(exists=True))
@click.option("--no-plantuml", is_flag=True, help="Skip PlantUML processing")
@click.option("--no-images", is_flag=True, help="Skip image processing")
@click.option("--featured-image", "-i", type=click.Path(exists=True), help="Featured image path")
@click.option("--scrub-watermark", is_flag=True, help="Disrupt SynthID/AI watermark via downscale+noise+upscale before upload")
def publish(file, no_plantuml, no_images, featured_image, scrub_watermark):
    """Build and publish a markdown file to Ghost CMS"""
    file_path = Path(file)

    if file_path.suffix.lower() not in (".md", ".mdx"):
        click.echo(f"Error: {file} is not a .md or .mdx file", err=True)
        raise click.Abort()

    config = Config()

    if not config.ghost_api_url or not config.ghost_admin_api_key:
        click.echo("Error: Ghost API not configured.", err=True)
        click.echo("Please add 'ghost_api_url' and 'ghost_admin_api_key' to your ~/.omelet.json file", err=True)
        click.echo("Or set GHOST_API_URL and GHOST_ADMIN_API_KEY environment variables", err=True)
        raise click.Abort()

    try:
        click.echo(f"Publishing: {file}")

        processor = MarkdownProcessor()

        with open(file_path, 'r', encoding='utf-8') as f:
            original = f.read()
        normalized = processor.normalize_punctuation(original)
        if normalized != original:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(normalized)
            click.echo("✓ Normalized punctuation (em-dash → hyphen, removed body `---` dividers)")

        # Step 1: Process images (PlantUML + upload)
        if not no_images:
            process_markdown_images(file_path, config, processor, skip_plantuml=no_plantuml, scrub=scrub_watermark)

        # Safety net: refuse to push a post that still contains local image paths.
        # Without this, an upload failure (or misconfiguration that slips past step 1)
        # would publish a broken Ghost draft with `./image.png` references.
        post_image_content = file_path.read_text(encoding="utf-8")
        leftover_images = processor.find_local_images(post_image_content, file_path)
        if leftover_images:
            click.echo(
                f"✗ Refusing to publish: {len(leftover_images)} local image path(s) still in body:",
                err=True,
            )
            for img in leftover_images[:5]:
                click.echo(f"    - {img['original']}", err=True)
            if len(leftover_images) > 5:
                click.echo(f"    ... and {len(leftover_images) - 5} more", err=True)
            click.echo("Fix the uploader configuration above and re-run.", err=True)
            raise click.Abort()

        # Step 2: Publish to Ghost
        from .ghost_client import GhostClient
        click.echo("Publishing to Ghost CMS...")
        ghost = GhostClient(config.ghost_api_url, config.ghost_admin_api_key)
        post = ghost.publish_markdown(str(file_path))

        click.echo(f"✓ Created post: {post['title']}")
        click.echo(f"  ID: {post['id']}")
        click.echo(f"  Slug: {post['slug']}")

        # Step 3: Set featured image if provided
        if featured_image:
            if scrub_watermark and scrub_image(featured_image):
                click.echo(f"✓ Scrubbed watermark: {Path(featured_image).name}")
            if strip_image_metadata(featured_image):
                click.echo(f"✓ Stripped metadata: {Path(featured_image).name}")
            click.echo(f"Uploading featured image: {featured_image}")
            ghost.set_featured_image(post['id'], featured_image)
            click.echo("✓ Featured image set")

        edit_url = f"{config.ghost_api_url}/ghost/#/editor/post/{post['id']}"
        click.echo(click.style(f"\nEdit URL: {edit_url}", fg="green", bold=True))

    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        raise click.Abort()


@cli.command()
@click.option("--file", "-f", type=click.Path(exists=True), help="Path to the .puml file")
@click.option("--string", "-s", help="PlantUML string content")
@click.option("--output", "-o", required=True, type=click.Path(), help="Output image path (e.g., diagram.png)")
@click.option(
    "--format",
    "output_format",
    default="png",
    type=click.Choice(["png", "svg", "txt"]),
    help="Output format (default: png)",
)
def puml(file, string, output, output_format):
    """Convert PlantUML to image via puml.omelet.tech"""
    if not file and not string:
        click.echo("Error: Either --file or --string is required", err=True)
        raise click.Abort()

    if file and string:
        click.echo("Error: Cannot use both --file and --string", err=True)
        raise click.Abort()

    # Get content from file or string
    if file:
        try:
            content = Path(file).read_text(encoding="utf-8")
        except Exception as e:
            click.echo(f"Error reading file: {e}", err=True)
            raise click.Abort()
    else:
        content = string

    # Ensure content has @startuml and @enduml tags
    content = content.strip()
    if not content.startswith("@startuml"):
        content = "@startuml\n" + content
    if not content.endswith("@enduml"):
        content = content + "\n@enduml"

    # Send to PlantUML service
    url = f"https://puml.omelet.tech/{output_format}"
    headers = {"Content-Type": "text/plain; charset=utf-8"}

    try:
        click.echo(f"Converting PlantUML to {output_format}...")
        response = requests.post(url, data=content.encode("utf-8"), headers=headers, timeout=30)
        response.raise_for_status()

        output_path = Path(output)
        output_path.write_bytes(response.content)
        click.echo(f"✓ Successfully saved image to {output}")

    except requests.exceptions.RequestException as e:
        click.echo(f"Error communicating with PlantUML service: {e}", err=True)
        if hasattr(e, "response") and e.response is not None:
            if "x-plantuml-diagram-error" in e.response.headers:
                click.echo(f"PlantUML Error: {e.response.headers['x-plantuml-diagram-error']}", err=True)
        raise click.Abort()


@cli.command()
@click.argument("file", required=False, type=click.Path(exists=True))
@click.option("--token", "-t", help="QuillBot Firebase JWT token (useridtoken)")
@click.option("--text", help="Direct text to check instead of a file")
@click.option("--section", help="Check only a specific section (for LaTeX files)")
@click.option("--language", default=None, help="Language code (auto-detected if not specified)")
@click.option("--no-explain", is_flag=True, help="Disable explanation categories")
@click.option("--raw", is_flag=True, help="Output raw JSON response")
@click.option("--all-sections", is_flag=True, help="Check each LaTeX section individually")
def aicheck(file, token, text, section, language, no_explain, raw, all_sections):
    """Check text or LaTeX files for AI-generated content using QuillBot.

    \b
    Examples:
      omelet aicheck paper.tex
      omelet aicheck --text "Some text to check"
      omelet aicheck --section introduction paper.tex
      omelet aicheck --all-sections paper.tex

    \b
    Token can be set via:
      - --token flag
      - QUILLBOT_TOKEN env var
      - quillbot_token in ~/.omelet.json
    """
    import json as json_mod
    import time
    from .ai_check import (
        strip_latex,
        extract_sections,
        detect_language,
        check_ai_score,
        display_results,
        is_auth_error,
        TEXT_LOWER_LIMIT,
    )

    if not file and not text:
        click.echo("Error: Provide a file or use --text", err=True)
        raise click.Abort()

    # Resolve token: flag -> config -> env -> prompt
    config = Config()
    if not token:
        token = config.quillbot_token
    if not token:
        token = click.prompt("QuillBot token (useridtoken)", hide_input=True)
        config.save("quillbot_token", token)
        click.echo("Token saved to ~/.omelet.json")

    def refresh_token() -> str:
        """Prompt for a new token and save it."""
        click.echo(click.style("Token expired or invalid.", fg="yellow"))
        new_token = click.prompt("Enter new QuillBot token", hide_input=True)
        config.save("quillbot_token", new_token)
        click.echo("New token saved to ~/.omelet.json")
        return new_token

    explain = not no_explain

    if text:
        check_text = text
        label = "Direct Text"
    else:
        file_path = Path(file)
        content = file_path.read_text(encoding="utf-8")
        is_latex = file_path.suffix.lower() in (".tex", ".latex")

        if is_latex and all_sections:
            sections = extract_sections(content)
            if not sections:
                click.echo("No sections found in file", err=True)
                raise click.Abort()

            click.echo(f"Found {len(sections)} sections: {', '.join(sections.keys())}")

            lang_code = language
            if not lang_code:
                first_text = next(iter(sections.values()))
                lang_code, lang_name = detect_language(first_text, token)
                click.echo(f"Detected language: {lang_name} ({lang_code})")

            for sec_name, sec_text in sections.items():
                if len(sec_text) < TEXT_LOWER_LIMIT:
                    click.echo(f"\nSkipping '{sec_name}' (too short)")
                    continue
                click.echo(f"\nChecking section: {sec_name} ({len(sec_text)} chars)...")
                result = check_ai_score(sec_text, token, lang_code, explain)
                if is_auth_error(result):
                    token = refresh_token()
                    result = check_ai_score(sec_text, token, lang_code, explain)
                if raw:
                    click.echo(json_mod.dumps(result, indent=2))
                else:
                    display_results(result, label=sec_name.title())
                time.sleep(1)
            return

        if is_latex and section:
            sections = extract_sections(content)
            match = section.lower()
            found = None
            for name, body in sections.items():
                if match in name.lower():
                    found = (name, body)
                    break
            if not found:
                click.echo(
                    f"Section '{section}' not found. Available: {', '.join(sections.keys())}",
                    err=True,
                )
                raise click.Abort()
            check_text = found[1]
            label = found[0].title()
        elif is_latex:
            check_text = strip_latex(content)
            label = file_path.name
        else:
            # Plain text / markdown / any other file
            check_text = content
            label = file_path.name

    # Detect language
    lang_code = language
    if not lang_code:
        click.echo("Detecting language...")
        lang_code, lang_name = detect_language(check_text, token)
        click.echo(f"Detected language: {lang_name} ({lang_code})")

    click.echo(f"Text length: {len(check_text)} characters")
    click.echo("Checking AI content...")

    result = check_ai_score(check_text, token, lang_code, explain)

    if is_auth_error(result):
        token = refresh_token()
        result = check_ai_score(check_text, token, lang_code, explain)

    if raw:
        click.echo(json_mod.dumps(result, indent=2))
    else:
        display_results(result, label=label)


PROVIDER_DEFAULT_MODEL = {
    "openai": "gpt-image-2",
    "gemini": "gemini-3-pro-image-preview",
}


@cli.command("generate-image")
@click.argument("prompt", required=False)
@click.argument("output", required=False)
@click.option("--blog", "-b", help="Generate featured image for a blog topic")
@click.option(
    "--style",
    "-s",
    default="minimal",
    type=click.Choice([
        "academic",
        "tech",
        "minimal",
        "colorful",
        "constructivism",
        "socialist-realism",
    ]),
    help="Image style preset (default: minimal)",
)
@click.option("--output", "-o", "output_opt", type=click.Path(), help="Output file path")
@click.option(
    "--provider",
    "-p",
    default="gemini",
    type=click.Choice(["openai", "gemini"]),
    help="Image generation provider (default: gemini)",
)
@click.option("--model", "-m", default=None, help="Model to use (defaults per provider)")
@click.option(
    "--size",
    default="1536x1024",
    help="Image size for OpenAI (1024x1024, 1536x1024, 1024x1536)",
)
@click.option(
    "--quality",
    default="high",
    type=click.Choice(["auto", "low", "medium", "high"]),
    help="Image quality for OpenAI (default: high)",
)
def generate_image(prompt, output, blog, style, output_opt, provider, model, size, quality):
    """Generate images using OpenAI or Google Gemini.

    \b
    Examples:
      omelet generate-image "A futuristic city" city.png
      omelet generate-image --blog "Binary Search Trees" -o bst/featured.png
      omelet generate-image --blog "YOLO26" --style constructivism -o yolo/featured.png
      omelet generate-image -p openai --blog "Python Tips" --style tech -o py/feat.png

    \b
    Providers:
      gemini  - gemini-3-pro-image-preview (default)
      openai  - gpt-image-2

    \b
    Styles:
      minimal            - Clean white background, simple line art (default)
      academic           - Black & white textbook diagrams
      tech               - Dark gradient with neon elements
      colorful           - Vibrant gradients, bold colors
      constructivism     - Russian Constructivism poster (red/black/cream, El Lissitzky)
      socialist-realism  - Soviet Socialist Realism poster (heroic figure, painterly)
    """
    output_path = output_opt or output

    config = Config()
    resolved_model = model or PROVIDER_DEFAULT_MODEL[provider]

    if provider == "openai":
        from .openai_image import OpenAIImageGenerator

        api_key = config.openai_api_key
        if not api_key:
            api_key = click.prompt("OpenAI API key (OPENAI_API_KEY)", hide_input=True)
            config.save("openai_api_key", api_key)

        generator = OpenAIImageGenerator(api_key=api_key, model=resolved_model)
        gen_kwargs = {"size": size, "quality": quality}
    else:
        from .gemini_image import GeminiImageGenerator

        api_key = config.google_api_key
        if not api_key:
            api_key = click.prompt("Google API key (GOOGLE_API_KEY)", hide_input=True)

        generator = GeminiImageGenerator(api_key=api_key, model=resolved_model)
        gen_kwargs = {}

    click.echo(f"Provider: {provider} ({resolved_model})")

    if blog:
        if not output_path:
            output_path = "featured-image.png"
        click.echo(f"Generating blog featured image for: {blog}")
        click.echo(f"Style: {style}")
        try:
            if provider == "openai":
                saved = generator.generate_blog_featured_image(
                    blog, output_path, style, size=size, quality=quality
                )
            else:
                saved = generator.generate_blog_featured_image(blog, output_path, style)
            click.echo(f"Image saved: {saved}")
        except RuntimeError as e:
            click.echo(f"Error: {e}", err=True)
            raise click.Abort()
    elif prompt and output_path:
        click.echo(f"Generating image...")
        click.echo(f"Prompt: {prompt[:100]}{'...' if len(prompt) > 100 else ''}")
        try:
            saved = generator.generate_image(prompt, output_path, **gen_kwargs)
            click.echo(f"Image saved: {saved}")
        except RuntimeError as e:
            click.echo(f"Error: {e}", err=True)
            raise click.Abort()
    else:
        click.echo("Error: Provide a prompt + output path, or use --blog.", err=True)
        raise click.Abort()


# Alias: omelet genimg
cli.add_command(generate_image, "genimg")


# ============================================================================
# Ghost CMS admin (bulk operations)
# ============================================================================

@cli.group()
def ghost():
    """Ghost CMS admin operations (bulk noindex, tag cleanup, AI scan)."""
    pass


def _ghost_admin():
    """Build a GhostAdmin client from Config."""
    from .ghost_admin import GhostAdmin
    config = Config()
    if not config.ghost_api_url or not config.ghost_admin_api_key:
        click.echo("Error: Ghost API not configured.", err=True)
        click.echo("Add 'ghost_api_url' and 'ghost_admin_api_key' to ~/.omelet.json", err=True)
        raise click.Abort()
    return GhostAdmin(config.ghost_api_url, config.ghost_admin_api_key)


@ghost.command()
@click.argument("slug")
@click.option("--undo", is_flag=True, help="Remove noindex instead of adding")
def noindex(slug, undo):
    """Add (or --undo remove) noindex meta on post or page by slug."""
    from .ghost_admin import add_noindex
    admin = _ghost_admin()
    status, msg = add_noindex(admin, slug, undo=undo)
    color = {'OK': 'green', 'SKIP': 'yellow', 'NOT_FOUND': 'red', 'FAIL': 'red'}.get(status, 'white')
    click.echo(click.style(f'{status}: {msg}', fg=color))


@ghost.command()
@click.argument("slug")
def unpublish(slug):
    """Set post or page to draft status by slug."""
    from .ghost_admin import set_status
    admin = _ghost_admin()
    status, msg = set_status(admin, slug, 'draft')
    color = {'OK': 'green', 'SKIP': 'yellow', 'NOT_FOUND': 'red', 'FAIL': 'red'}.get(status, 'white')
    click.echo(click.style(f'{status}: {msg}', fg=color))


@ghost.command()
@click.argument("slug")
def publish_again(slug):
    """Republish a draft post or page by slug."""
    from .ghost_admin import set_status
    admin = _ghost_admin()
    status, msg = set_status(admin, slug, 'published')
    color = {'OK': 'green', 'SKIP': 'yellow', 'NOT_FOUND': 'red', 'FAIL': 'red'}.get(status, 'white')
    click.echo(click.style(f'{status}: {msg}', fg=color))


@ghost.command("cleanup-tags")
@click.option(
    "--strategy",
    type=click.Choice(["safe", "aggressive"]),
    default="safe",
    help="safe = delete orphans only. aggressive = also set thin tags to internal.",
)
@click.option("--threshold", default=2, type=int,
              help="Tags with <threshold posts are 'thin'. Default 2 (i.e. 1-post tags).")
@click.option("--dry-run", is_flag=True, help="Show counts only, don't apply.")
def cleanup_tags(strategy, threshold, dry_run):
    """Cleanup tag pollution: delete orphans, optionally internalize thin tags."""
    from .ghost_admin import cleanup_tags as do_cleanup
    admin = _ghost_admin()
    summary = do_cleanup(admin, strategy=strategy, threshold=threshold, dry_run=True)
    click.echo(f'Total tags: {summary["total_tags"]}')
    click.echo(f'Orphans (will DELETE): {summary["orphans"]}')
    if strategy == 'aggressive':
        click.echo(f'Thin tags <{threshold} posts (will INTERNALIZE): {summary["thin"]}')

    if dry_run:
        click.echo('--dry-run: stopping here.')
        return
    if not click.confirm('Apply?', default=False):
        click.echo('Aborted.')
        return

    summary = do_cleanup(admin, strategy=strategy, threshold=threshold, dry_run=False)
    click.echo(click.style(f'Deleted: {summary["deleted"]} orphans', fg='green'))
    if strategy == 'aggressive':
        click.echo(click.style(f'Internalized: {summary["internalized"]} thin tags', fg='green'))
    if summary['errors']:
        click.echo(click.style(f'Errors: {len(summary["errors"])}', fg='red'))
        for e in summary['errors'][:5]:
            click.echo(f'  - {e}')


@ghost.command("scan-ai-endings")
@click.option("--fix", is_flag=True, help="Auto-remove confirmed AI endings (with confirmation).")
@click.option("--include-drafts", is_flag=True, help="Also scan draft posts.")
def scan_ai_endings(fix, include_drafts):
    """Scan posts for AI-template closings (Tóm lại / Hy vọng / Chúc vui vẻ / Kết luận)."""
    from .ghost_admin import find_ai_endings, remove_ai_ending
    admin = _ghost_admin()
    candidates = find_ai_endings(admin, include_drafts=include_drafts)
    click.echo(f'Found {len(candidates)} posts with AI ending\n')
    for c in candidates:
        click.echo(click.style(f'  [{c["ending_kind"]}] {c["slug"]}', bold=True))
        preview = c['last_para'][:150].replace('\n', ' ')
        click.echo(f'    {preview}{"..." if len(c["last_para"]) > 150 else ""}\n')

    if not fix or not candidates:
        return
    if not click.confirm(f'Remove AI ending from {len(candidates)} posts?', default=False):
        click.echo('Aborted.')
        return

    ok = fail = skip = 0
    for c in candidates:
        status, msg = remove_ai_ending(admin, c)
        if status == 'OK':
            ok += 1
            click.echo(click.style(f'  OK: {msg}', fg='green'))
        elif status == 'SKIP':
            skip += 1
            click.echo(click.style(f'  SKIP {c["slug"]}: {msg}', fg='yellow'))
        else:
            fail += 1
            click.echo(click.style(f'  FAIL {c["slug"]}: {msg}', fg='red'))
    click.echo(f'\nDone. OK={ok}, SKIP={skip}, FAIL={fail}')


@ghost.command("set-seo")
@click.argument("identifier")
@click.option("--title", "-t", help="Post title (also used as meta_title default).")
@click.option("--slug", help="URL slug.")
@click.option("--description", "-d", "meta_description",
              help="Meta description (~140-160 chars).")
@click.option("--excerpt", "custom_excerpt", help="Ghost custom_excerpt.")
@click.option("--excerpt-from-meta", is_flag=True,
              help="Use --description as custom_excerpt if --excerpt not given.")
@click.option("--feature-image", help="Public URL of feature image.")
@click.option("--feature-image-alt", help="Alt text for feature image.")
@click.option("--meta-title", help="SEO title override (default: --title).")
@click.option("--tags", help="Comma-separated tag names (replaces existing).")
@click.option("--og-title")
@click.option("--og-description")
@click.option("--og-image")
@click.option("--twitter-title")
@click.option("--twitter-description")
@click.option("--twitter-image")
@click.option("--og-mirror", is_flag=True,
              help="Auto-fill og_*/twitter_* from title + description + feature_image.")
@click.option("--from-frontmatter", type=click.Path(exists=True, path_type=Path),
              help="Read missing fields from markdown YAML frontmatter (title, slug, description, tags, feature_image).")
@click.option("--show", is_flag=True, help="Print current SEO fields and exit.")
def set_seo_cmd(identifier, show, from_frontmatter, og_mirror, excerpt_from_meta, tags, **kwargs):
    """Set SEO metadata on a Ghost post/page (title, meta, OG, Twitter, tags, feature image) in one PUT.

    IDENTIFIER is either a 24-hex post id or a slug.
    """
    from .ghost_admin import set_seo, show_seo, parse_frontmatter

    admin = _ghost_admin()

    if show:
        current = show_seo(admin, identifier)
        if current is None:
            click.echo(click.style(f'NOT_FOUND: no post/page with id/slug {identifier!r}', fg='red'))
            raise click.Abort()
        click.echo(click.style(f'Status: {current.pop("_status")}', bold=True))
        click.echo(f'URL:    {current.pop("_url")}')
        for k, v in current.items():
            if v in (None, '', []):
                continue
            preview = str(v)
            if len(preview) > 100:
                preview = preview[:97] + '...'
            click.echo(f'  {k:25s} = {preview}')
        return

    fields = {k: v for k, v in kwargs.items() if v is not None}
    tag_list = [t.strip() for t in tags.split(',')] if tags else None

    # Merge in frontmatter (only fills missing keys, doesn't override CLI args)
    if from_frontmatter:
        fm = parse_frontmatter(from_frontmatter)
        fm_map = {
            'title': 'title',
            'slug': 'slug',
            'description': 'meta_description',
            'meta_description': 'meta_description',
            'excerpt': 'custom_excerpt',
            'feature_image': 'feature_image',
            'feature_image_alt': 'feature_image_alt',
        }
        for fm_key, field_key in fm_map.items():
            if field_key not in fields and fm.get(fm_key):
                fields[field_key] = fm[fm_key]
        if tag_list is None and fm.get('tags'):
            fm_tags = fm['tags']
            tag_list = fm_tags if isinstance(fm_tags, list) else [t.strip() for t in str(fm_tags).split(',')]

    # If --title given but no --meta-title, default meta_title to title (Ghost convention)
    if fields.get('title') and not fields.get('meta_title'):
        fields['meta_title'] = fields['title']

    if not fields and not tag_list:
        click.echo('No fields provided. Use --show to inspect, or pass field options.', err=True)
        raise click.Abort()

    status, msg, applied = set_seo(
        admin, identifier,
        fields=fields,
        tags=tag_list,
        og_mirror=og_mirror,
        excerpt_from_meta=excerpt_from_meta,
    )
    color = {'OK': 'green', 'SKIP': 'yellow', 'NOT_FOUND': 'red', 'FAIL': 'red'}.get(status, 'white')
    click.echo(click.style(f'{status}: {msg}', fg=color))
    if status == 'OK':
        for k, v in applied.items():
            preview = str(v)
            if len(preview) > 100:
                preview = preview[:97] + '...'
            click.echo(f'  {k:25s} = {preview}')


@ghost.command("migrate-images")
@click.argument("identifier")
@click.option("--source-base", help="Base URL to resolve relative img src (e.g. https://kimi.page/).")
@click.option("--folder", help="GCS subfolder under public/blog/ (default: post slug).")
@click.option("--mirror-external", is_flag=True,
              help="Also mirror absolute external URLs (not just relative paths).")
@click.option("--bucket", help="Override gcs_bucket from ~/.omelet.json.")
@click.option("--strip-watermark", is_flag=True,
              help="Run scrub_watermark in addition to strip_image_metadata.")
@click.option("--dry-run", is_flag=True, help="Show what would migrate, don't apply.")
def migrate_images_cmd(identifier, source_base, folder, mirror_external, bucket, strip_watermark, dry_run):
    """Download all <img> in a post, strip metadata, upload to GCS, replace src.

    IDENTIFIER is either a 24-hex post id or a slug.

    Examples:
      omelet ghost migrate-images my-post-slug --source-base https://kimi.page/
      omelet ghost migrate-images 6a0bad59... --mirror-external --dry-run
    """
    from .ghost_admin import migrate_images
    admin = _ghost_admin()
    result = migrate_images(
        admin, identifier,
        source_base=source_base,
        folder=folder,
        mirror_external=mirror_external,
        bucket=bucket,
        strip_watermark=strip_watermark,
        dry_run=dry_run,
    )

    status = result.get('status', 'UNKNOWN')
    color = {'OK': 'green', 'DRY_RUN': 'cyan', 'NOOP': 'yellow',
             'NOT_FOUND': 'red', 'FAIL': 'red'}.get(status, 'white')
    click.echo(click.style(f'\n{status}: post={result.get("post_slug", "?")}', fg=color, bold=True))

    if status in ('NOT_FOUND', 'FAIL'):
        click.echo(click.style(f'  error: {result.get("error", "?")}', fg='red'))
        raise click.Abort()

    if status == 'DRY_RUN':
        for src, url in result.get('would_migrate', []):
            click.echo(f'  WOULD: {src}')
            click.echo(f'         ← {url}')
    else:
        for old, new in result.get('mapping', {}).items():
            click.echo(click.style(f'  ✓ {old}', fg='green'))
            click.echo(f'    → {new}')

    for src, reason in result.get('skipped', []) or []:
        click.echo(click.style(f'  SKIP: {src}  ({reason})', fg='yellow'))
    for src, err in result.get('errors', []) or []:
        click.echo(click.style(f'  FAIL: {src}  ({err})', fg='red'))


# ============================================================================
# SEO audit
# ============================================================================

@cli.group()
def seo():
    """SEO audit and recovery tools."""
    pass


@seo.command()
@click.option("--ga4-csv", type=click.Path(exists=True),
              help="GA4 'Queries' export CSV for click/impression analysis.")
@click.option("--out", "-o", default="seo-audit.md", type=click.Path(),
              help="Output markdown report path.")
@click.option("--site-url", default="https://www.omelet.tech",
              help="Public site URL (for sitemap fetch).")
def audit(ga4_csv, out, site_url):
    """Run full SEO health audit and write a markdown report."""
    from .seo import build_audit_report
    admin = _ghost_admin()
    click.echo("Building audit report...")
    report = build_audit_report(admin, base_url=site_url, ga4_csv=ga4_csv)
    Path(out).write_text(report, encoding='utf-8')
    click.echo(click.style(f'Report saved: {out}', fg='green'))


@cli.command()
@click.argument("file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--port", "-p", default=4321, type=int, help="Port (auto-pick next free if busy)")
@click.option("--host", "-h", default="0.0.0.0", help="Bind host (0.0.0.0 = accept from any IP)")
@click.option(
    "--theme",
    "-t",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Path to Ghost theme screen.css for WYSIWYG preview",
)
@click.option("--no-browser", is_flag=True, help="Do not auto-open browser")
@click.option("--no-watch-components", is_flag=True, help="Do not watch omelet/mdx/components/*.py")
def preview(file: Path, port: int, host: str, theme, no_browser: bool, no_watch_components: bool):
    """Live preview a .mdx or .md file in the browser with hot reload."""
    from .preview import start_server

    theme_path = theme
    if theme_path is None:
        candidates = [
            Path.home() / "git" / "omelet.tech-template" / "assets" / "built" / "screen.css",
            Path.home() / "git" / "omelet.tech-template" / "assets" / "css" / "screen.css",
        ]
        for c in candidates:
            if c.exists():
                theme_path = c
                break

    start_server(
        file_path=file,
        host=host,
        port=port,
        theme_css_path=theme_path,
        open_browser=not no_browser,
        watch_components=not no_watch_components,
    )


def main():
    """Entry point for the CLI"""
    cli()


if __name__ == "__main__":
    main()
