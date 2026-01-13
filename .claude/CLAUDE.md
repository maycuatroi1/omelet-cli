# Omelet CLI

A command-line tool for uploading local images in Markdown files to cloud storage and replacing paths with public URLs.

## Tech Stack

- **Language:** Python 3.8+
- **CLI Framework:** Click 8.0+
- **HTTP Client:** Requests
- **Cloud Storage:** Google Cloud Storage (optional)

## Project Structure

```
omelet/
├── cli.py                # CLI entry point and commands
├── config.py             # Configuration management
├── markdown_processor.py # Markdown parsing & URL replacement
├── image_uploader.py     # API backend uploader
├── gcs_uploader.py       # Google Cloud Storage uploader
└── gcloud_auth.py        # GCS authentication handler
```

## Commands

```bash
# Install in development mode
pip install -e .

# Process markdown and upload images
omelet buildmarkdown <file.md> --folder <folder-name>

# Publish markdown to webhook
omelet public <file.md>

# Run tests
pytest

# Format code
black omelet/

# Type check
mypy omelet/

# Lint
flake8 omelet/
```

## Code Style

- Use **Black** formatter (88 char line length)
- Use **type hints** for all function parameters and returns
- Use **Click** decorators for CLI commands
- Follow PEP 8 naming conventions

## Configuration

Config loaded from `.omelet.json` or environment variables:
- `OMELET_USERNAME` / `OMELET_PASSWORD` - API auth
- `OMELET_USE_GCS` - Enable GCS mode
- `OMELET_GCS_BUCKET` - GCS bucket name
- `OMELET_PUBLIC_WEBHOOK_URL` - Publishing webhook

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=omelet --cov-report=html
```

## Key Patterns

- **MarkdownProcessor**: Uses regex `!\[([^\]]*)\]\(([^)]+)\)` to find images
- **ImageUploader**: POST multipart/form-data with Basic Auth
- **GCSUploader**: Uses `google.cloud.storage` with public blob access
- **Config**: Singleton pattern with property-based access

## Image Formats Supported

PNG, JPG, JPEG, GIF, SVG, WebP, BMP, ICO
