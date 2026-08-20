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
  "backend_url": "https://your-backend-url.com/webhook",
  "username": "your-username",
  "password": "your-password",
  "use_gcs": false,
  "gcs_bucket": "your-bucket-name"
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

![Screenshot](./assets/screenshot.jpg)
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

## Raw HTML and SVG in MDX

Ghost's HTML-to-lexical converter rewrites markup it recognises: every `<figure>`
becomes its own image card, which collapses a multi-image grid to the first image
and concatenates the captions. Wrapping a block in `<!--kg-card-begin: html-->` and
`<!--kg-card-end: html-->` is the documented way to hand Ghost that block untouched.

Whatever sits between those markers skips the bleach allowlist too, so inline SVG,
`style` attributes and anything else survive to the published post. Script tags,
`on*` event handlers and `javascript:` URLs still fail the build. An `<svg>` written
*outside* the markers is an error rather than a silent strip, because the allowlist
has no SVG vocabulary and would leave only the text nodes behind.

`<Diagram>` writes the markers for you:

```mdx
<Diagram src="./diagrams/01-architecture.svg" caption="Hình 1. Ba khối `KDA` rồi một khối **MLA**." />

<Diagram caption="Inline works too">
<svg viewBox="0 0 200 40" role="img" aria-label="...">...</svg>
</Diagram>
```

- `src` inlines an `.svg` or `.html` file at compile time, resolved next to the post.
- Children are raw markup, never parsed as markdown. `caption` is inline markdown.
- `class` appends to the emitted `omelet-diagram` class.
- `<img src="./local.png">` inside the block is uploaded and rewritten like any other
  local image, so screenshots can carry a real `<figcaption>`.

## Interactive Widgets in MDX

`<Widget>` is the one slot in a post that is allowed to carry a `<script>`. It reads
an `.html` file sitting next to the post, drops the file in verbatim, and marks the
block with `<!--omelet:widget-->` right after `<!--kg-card-begin: html-->`. Sanitize
recognises that sentinel and skips the executable-markup check for that block only.

```mdx
<Widget src="./widgets/bpe-demo.html" caption="Hình 3. Gõ một từ và xem `BPE` cắt nó." />
```

- `src` is required, must end in `.html`, and is resolved inside the post's own
  directory. Anything else fails the build.
- `caption` is optional and parsed as inline markdown. `class` is optional and
  appends to the emitted `omelet-widget` class.
- The tag must sit at the top level of the post. Nesting it inside another component
  raises a `ComponentError`, because a nested block never gets its own marker and its
  script would be stripped anyway.
- omelet-cli ships no CSS for `.omelet-widget`. The widget file carries its own
  inline styles.

Only the compiler writes that sentinel, and only around a file read from the post's
directory. Every other `kg-card` block - including one you type by hand - still fails
the build with a `SanitizeError` the moment it holds a `<script>` tag, an `on*`
attribute, or a `javascript:` URL.

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