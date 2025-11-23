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


@cli.command()
@click.argument("file", type=click.Path(exists=True))
@click.option("--folder", "-f", help="Folder name for organizing uploads (defaults to parent folder)")
def buildmarkdown(file, folder):
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


def main():
    """Entry point for the CLI"""
    cli()


if __name__ == "__main__":
    main()
