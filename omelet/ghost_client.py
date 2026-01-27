"""
Ghost CMS client for publishing blog posts
"""
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any

import jwt
import markdown
import requests
from markdown.extensions.tables import TableExtension
from markdown.extensions.fenced_code import FencedCodeExtension
from markdown.extensions.codehilite import CodeHiliteExtension


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """Parse YAML frontmatter from markdown."""
    frontmatter = {}

    match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
    if match:
        fm_text = match.group(1)
        body = content[match.end():]

        for line in fm_text.split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()

                if value.startswith('[') and value.endswith(']'):
                    value = json.loads(value.replace("'", '"'))
                elif value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]

                frontmatter[key] = value

        return frontmatter, body

    return {}, content


def markdown_to_html(md_content: str) -> str:
    """Convert markdown to HTML."""
    html = markdown.markdown(
        md_content,
        extensions=[
            TableExtension(),
            FencedCodeExtension(),
            CodeHiliteExtension(css_class='highlight', guess_lang=False),
            'nl2br'
        ]
    )
    return html


class GhostClient:
    """Client for interacting with Ghost Admin API."""

    def __init__(self, api_url: str, admin_api_key: str):
        self.api_url = api_url.rstrip('/')
        self.admin_api_key = admin_api_key
        self.token = self._create_jwt_token()
        self.headers = {
            "Authorization": f"Ghost {self.token}",
            "Content-Type": "application/json"
        }

    def _create_jwt_token(self) -> str:
        """Create JWT token for Ghost Admin API authentication."""
        key_parts = self.admin_api_key.split(':')
        key_id = key_parts[0]
        secret = bytes.fromhex(key_parts[1])

        iat = int(datetime.now(timezone.utc).timestamp())
        header = {'alg': 'HS256', 'typ': 'JWT', 'kid': key_id}
        payload = {
            'iat': iat,
            'exp': iat + 5 * 60,
            'aud': '/admin/'
        }

        return jwt.encode(payload, secret, algorithm='HS256', headers=header)

    def get_post(self, post_id: str) -> dict:
        """Get a post by ID."""
        url = f"{self.api_url}/ghost/api/admin/posts/{post_id}/?formats=html"
        response = requests.get(url, headers=self.headers)

        if response.status_code != 200:
            raise Exception(f"Error getting post: {response.status_code} - {response.text}")

        return response.json()["posts"][0]

    def create_post(self, title: str, html: str, tags: List[str] = None,
                   excerpt: str = None, meta_title: str = None,
                   meta_description: str = None, feature_image: str = None,
                   slug: str = None) -> dict:
        """Create a new post."""
        post_data = {
            'posts': [{
                'title': title,
                'html': html,
                'status': 'draft',
                'tags': [{'name': tag} for tag in (tags or [])],
                'custom_excerpt': excerpt or '',
                'meta_title': meta_title or title,
                'meta_description': meta_description or excerpt or '',
            }]
        }

        if feature_image:
            post_data['posts'][0]['feature_image'] = feature_image
        if slug:
            post_data['posts'][0]['slug'] = slug

        url = f"{self.api_url}/ghost/api/admin/posts/?source=html"
        response = requests.post(url, json=post_data, headers=self.headers)

        if response.status_code == 201:
            return response.json()['posts'][0]
        else:
            raise Exception(f"Error creating post: {response.status_code} - {response.text}")

    def update_post(self, post_id: str, updates: dict) -> dict:
        """Update a post with the given data."""
        current = self.get_post(post_id)
        updates["updated_at"] = current["updated_at"]

        url = f"{self.api_url}/ghost/api/admin/posts/{post_id}/?source=html"
        response = requests.put(url, headers=self.headers, json={"posts": [updates]})

        if response.status_code != 200:
            raise Exception(f"Error updating post: {response.status_code} - {response.text}")

        return response.json()["posts"][0]

    def upload_image(self, image_path: str) -> str:
        """Upload an image to Ghost and return its URL."""
        url = f"{self.api_url}/ghost/api/admin/images/upload/"
        headers = {"Authorization": f"Ghost {self.token}"}

        with open(image_path, 'rb') as f:
            ext = Path(image_path).suffix.lower()
            mime_types = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.gif': 'image/gif', '.webp': 'image/webp'}
            mime_type = mime_types.get(ext, 'image/png')
            filename = Path(image_path).name
            files = {'file': (filename, f, mime_type)}
            data = {'purpose': 'image', 'ref': image_path}
            response = requests.post(url, headers=headers, files=files, data=data)

        if response.status_code != 201:
            raise Exception(f"Error uploading image: {response.status_code} - {response.text}")

        return response.json()['images'][0]['url']

    def set_featured_image(self, post_id: str, image_path: str,
                          alt: str = None, caption: str = None) -> dict:
        """Upload and set featured image for a post."""
        image_url = self.upload_image(image_path)

        updates = {"feature_image": image_url}
        if alt:
            updates["feature_image_alt"] = alt
        if caption:
            updates["feature_image_caption"] = caption

        return self.update_post(post_id, updates)

    def publish_markdown(self, markdown_path: str, slug: str = None) -> dict:
        """Create a new Ghost post from markdown file."""
        with open(markdown_path, 'r', encoding='utf-8') as f:
            content = f.read()

        frontmatter, body = parse_frontmatter(content)
        html_content = markdown_to_html(body)

        tags = frontmatter.get('tags', frontmatter.get('keywords', []))
        if isinstance(tags, str):
            tags = [tags]

        if slug is None:
            slug = Path(markdown_path).parent.name
            if slug == '.':
                slug = None

        post = self.create_post(
            title=frontmatter.get('title', 'Untitled'),
            html=html_content,
            tags=tags,
            excerpt=frontmatter.get('description', ''),
            meta_title=frontmatter.get('title', ''),
            meta_description=frontmatter.get('description', ''),
            feature_image=frontmatter.get('image'),
            slug=slug
        )

        return post
