# Omelet CLI

Automatically upload local images in Markdown files to a server and replace local paths with public URLs.

## Features

- 🔍 Automatically detects local images in Markdown files
- 📤 Uploads images to a configured server endpoint or Google Cloud Storage
- 🔄 Replaces local paths with public URLs
- ⚡ Supports concurrent uploads with progress display
- 🔐 Basic authentication support for API backend
- ☁️ Direct Google Cloud Storage integration
- 🎯 Configurable via JSON file or environment variables

## Installation

```bash
pip install .
```

Or install in development mode:

```bash
pip install -e .
```

## Usage

Basic usage:

```bash
omelet buildmarkdown ./readme.md
```

This will:
1. Scan the markdown file for local images (e.g., `![](./image.png)`)
2. Upload each image to the configured server
3. Replace local paths with the returned public URLs
4. Update the original markdown file

## Configuration

Omelet can be configured via:

### 1. Configuration File

Create `.omelet.json` in your home directory or current working directory:

```json
{
  "backend_url": "https://n8n.omelet.tech/webhook-test/3a4e5b1a-1cd3-459b-adb0-803753a95943",
  "username": "your-username",
  "password": "your-password",
  "use_gcs": false,
  "gcs_bucket": "omelet-f0b89.appspot.com"
}
```

### 2. Environment Variables

```bash
export OMELET_USERNAME="your-username"
export OMELET_PASSWORD="your-password"
export OMELET_USE_GCS="true"  # Set to "true" to use Google Cloud Storage
export OMELET_GCS_BUCKET="your-bucket-name"
```

## Google Cloud Storage Setup

To use Google Cloud Storage instead of the API backend:

### 1. Authenticate with Google Cloud

Omelet uses your existing gcloud CLI authentication. Make sure you're authenticated:

```bash
# Authenticate with gcloud CLI
gcloud auth application-default login
```

### 2. Enable Google Cloud Storage mode

Set in configuration file:
```json
{
  "use_gcs": true,
  "gcs_bucket": "your-bucket-name"
}
```

Or use environment variable:
```bash
export OMELET_USE_GCS="true"
export OMELET_GCS_BUCKET="your-bucket-name"
```

### 3. Verify setup

Run omelet on a markdown file:
```bash
omelet buildmarkdown ./readme.md
```

The tool will upload images to: `gs://your-bucket-name/public/blog/{folder}/{filename}`

## Server API Requirements

The upload endpoint should:
- Accept POST requests with `multipart/form-data`
- Expect fields:
  - `data`: The image file (binary)
  - `folder`: The folder name (taken from the markdown file's parent directory)
- Support Basic Authentication (if configured)
- Return JSON response:
  ```json
  {
    "public_url": "https://example.com/path/to/uploaded-image.png"
  }
  ```

## Example

**Before:**
```markdown
# My Article

![](./images/diagram.png)

Some content here...

![Screenshot](../assets/screenshot.jpg)
```

**After:**
```markdown
# My Article

![](https://cdn.example.com/blog/images/diagram.png)

Some content here...

![Screenshot](https://cdn.example.com/blog/assets/screenshot.jpg)
```

## Supported Image Formats

- PNG
- JPG/JPEG
- GIF
- SVG
- WebP
- BMP
- ICO

## Error Handling

- Non-existent image files are reported but don't stop processing
- Failed uploads are logged with error messages
- Original paths are preserved if upload fails
- The tool continues processing remaining images even if some fail

## Development

Install development dependencies:

```bash
pip install -e ".[dev]"
```

Run tests:

```bash
pytest
```

## Author

**Nguyen Anh Binh**  
Email: socrat.nguyeannhbinh@gmail.com  
Website: [omelet.tech](https://omelet.tech)

## License

MIT License - see [LICENSE](LICENSE) file for details