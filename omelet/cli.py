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


@cli.command()
@click.argument("file", type=click.Path(exists=True))
def publish(file):
    """Publish a markdown file to the configured webhook URL"""
    file_path = Path(file)

    if not file_path.suffix.lower() == ".md":
        click.echo(f"Error: {file} is not a markdown file", err=True)
        raise click.Abort()

    # Load configuration
    config = Config()

    if not config.public_webhook_url:
        click.echo("Error: No public webhook URL configured.", err=True)
        click.echo("Please add 'public_webhook_url' to your ~/.omelet.json file", err=True)
        raise click.Abort()

    try:
        # Read the markdown file
        content = file_path.read_text(encoding="utf-8")

        click.echo(f"Publishing markdown file: {file}")
        click.echo(f"Webhook URL: {config.public_webhook_url}")

        # Send POST request with markdown content in 'data' field
        response = requests.post(
            config.public_webhook_url, json={"data": content}, headers={"Content-Type": "application/json"}, timeout=30
        )

        if response.status_code == 200:
            click.echo("✓ Successfully published markdown file")
            if response.text:
                click.echo(f"Response: {response.text}")
                data = response.json()
                post_id = data.get("id")
                title = data.get("title")
                if post_id:
                    click.echo(f"Post ID: {post_id}")
                    click.echo(f"Title: {title}")
                    draft_url = f"https://omelet.ghost.io/ghost/#/editor/post/{post_id}"
                    click.echo(click.style(f"Draft URL: {draft_url}", fg="green", bold=True))
                else:
                    click.echo("No post ID found in response")
        else:
            click.echo(f"✗ Failed to publish: HTTP {response.status_code}", err=True)
            if response.text:
                click.echo(f"Response: {response.text}", err=True)
            raise click.Abort()

    except requests.exceptions.RequestException as e:
        click.echo(f"Error: Network request failed - {str(e)}", err=True)
        raise click.Abort()
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


def main():
    """Entry point for the CLI"""
    cli()


if __name__ == "__main__":
    main()
