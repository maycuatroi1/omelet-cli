"""
Main CLI module for Omelet
"""
import click
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
@click.argument('file', type=click.Path(exists=True))
def buildmarkdown(file):
    """Process a markdown file and upload local images"""
    file_path = Path(file)
    
    if not file_path.suffix.lower() == '.md':
        click.echo(f"Error: {file} is not a markdown file", err=True)
        raise click.Abort()
    
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
        content = file_path.read_text(encoding='utf-8')
        
        # Find all local images
        images = processor.find_local_images(content, file_path)
        
        if not images:
            click.echo("No local images found in the markdown file")
            return
        
        click.echo(f"Found {len(images)} local image(s) to upload")
        
        # Upload images and get URL mappings
        url_mappings = {}
        folder_name = file_path.parent.name
        
        with click.progressbar(images, label='Uploading images') as bar:
            for image_info in bar:
                try:
                    public_url = uploader.upload_image(image_info['path'], folder_name)
                    url_mappings[image_info['original']] = public_url
                    click.echo(f"\n✓ Uploaded: {image_info['path'].name} -> {public_url}")
                except Exception as e:
                    click.echo(f"\n✗ Failed to upload {image_info['path'].name}: {str(e)}", err=True)
        
        # Replace URLs in content
        if url_mappings:
            updated_content = processor.replace_urls(content, url_mappings)
            
            # Save the updated content back to the original file
            file_path.write_text(updated_content, encoding='utf-8')
            click.echo(f"\n✓ Updated {len(url_mappings)} image URL(s) in {file}")
        
    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        raise click.Abort()


def main():
    """Entry point for the CLI"""
    cli()


if __name__ == "__main__":
    main()