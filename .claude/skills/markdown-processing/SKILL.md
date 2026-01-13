---
name: markdown-processing
description: Work with Markdown files and image processing. Use when the user needs to analyze, modify, or process Markdown content with images.
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
---

# Markdown Processing Skill

This skill helps work with Markdown files and image handling in the Omelet CLI context.

## Capabilities

### 1. Analyze Markdown Images
Find all local image references in a Markdown file:
```python
import re
pattern = r'!\[([^\]]*)\]\(([^)]+)\)'
matches = re.findall(pattern, content)
```

### 2. Validate Image Paths
Supported extensions: PNG, JPG, JPEG, GIF, SVG, WebP, BMP, ICO

Check if image exists:
```bash
test -f "path/to/image.png" && echo "exists" || echo "missing"
```

### 3. Convert Relative Paths
```python
from pathlib import Path

def resolve_path(md_file: str, img_path: str) -> str:
    md_dir = Path(md_file).parent
    if img_path.startswith('./'):
        img_path = img_path[2:]
    return str(md_dir / img_path)
```

### 4. Preview Markdown
Convert to HTML for preview:
```bash
python -m markdown file.md > preview.html
```

## Common Tasks

- List all images: Search for `!\[` pattern
- Find broken images: Check each path exists
- Batch rename: Update paths in content
- Extract alt text: Parse the `[alt]` portion

## Project Integration

The `MarkdownProcessor` class in `omelet/markdown_processor.py` handles:
- `find_local_images()` - Detect local image references
- `replace_image_paths()` - Update paths with URL mappings
