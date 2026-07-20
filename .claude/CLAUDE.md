# Omelet CLI

The toolchain behind omelet.tech: compile MDX posts, preview them live, publish to Ghost,
generate images, and lint the writing itself.

## Who depends on this

`~/github/blog` (the omelet.tech content repo) cannot build, preview, or publish a single post
without this CLI. Its docs instruct agents to run `omelet preview`, `omelet publish`,
`omelet lint`. **Renaming or removing a command breaks that repo silently.**

Before changing the command surface, run `cd ~/github/blog && python3 tools/check.py`. It compares
what the blog docs tell agents to run against what `omelet --help` actually offers. It was
written the day the two drifted apart and nobody noticed.

## Boot

`./init.sh` - installs editable (so the code on disk is the code that runs) and runs the tests.
An `omelet` installed non-editable from a stale branch is how the blog repo ended up
documenting a `preview` command that the binary did not have.

## Project Structure

```
omelet/
├── cli.py                # CLI entry point, all top-level commands
├── config.py             # Configuration (.omelet.json / env)
├── markdown_processor.py # Image discovery + URL replacement
├── gcs_uploader.py       # Google Cloud Storage uploader
├── ghost_admin.py        # Ghost Admin API (noindex, tags, SEO)
├── ai_check.py           # QuillBot AI-detector wrapper (statistical, English-leaning)
├── seo.py                # SEO audit / recovery
├── mdx/                  # MDX compiler: parser, jsx_tokenizer, citations, components/
├── preview/              # Live preview server (hot reload)
└── lint/                 # Content linter: AI slop + depth proxies. See below.
```

## The content linter (`omelet lint`)

`omelet/lint/` mechanizes the writing rules that used to live only as prose in the blog repo.
A rule that lives only in a document is a rule a future agent violates silently.

- `doc.py` - masks code, math, and URLs before any rule sees the text, so an em-dash inside a
  code sample is not mistaken for prose.
- `rules.py` - SLOP-* (em-dash, marketing filler, AI closings, choppy rhythm), DEPTH-* (numbers
  with no source, dead citation keys, primary-source ratio, no original artifact), VOICE-*, FMT-*.
  Every rule carries a `fix` line: the message lands in an agent's context, which makes it the
  cheapest prompt you will ever write.
- Reports only by default. `--strict` exits 1.

**`lint` is not `aicheck`.** `aicheck` asks QuillBot whether a text is statistically
machine-generated. `lint` asks whether the post breaks omelet.tech's own rules. Different
questions, and the second one is the one that catches slop written by a human in a hurry.

The blacklist in `rules.py` is a hand-copy of the one in `~/github/blog/.claude/rules/PERSONAL_VOICE.md`.
Change one, change the other. Nothing enforces this yet, and it will rot.

## Commands

```bash
# Install in development mode
./init.sh                     # or: pip install -e ".[dev]"

# Process markdown and upload images
omelet buildmarkdown <file.md> --folder <folder-name>

# Publish to Ghost
omelet publish <file.mdx>

# Live preview with hot reload
omelet preview <file.mdx>

# Lint a post: AI slop + depth
omelet lint <file.mdx> [--strict]

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
