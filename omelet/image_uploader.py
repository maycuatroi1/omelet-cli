"""
Module for uploading images
"""
from pathlib import Path
import requests
from typing import Optional


class ImageUploader:
    """Handler for uploading images"""

    def __init__(self, config):
        self.config = config
        self.session = requests.Session()

        # Set up basic auth if configured
        if config.username and config.password:
            self.session.auth = (config.username, config.password)

    def upload_image(self, image_path: Path, folder: str) -> str:
        """
        Upload a single image to the server

        Args:
            image_path: Path to the image file
            folder: Folder name (from parent directory)

        Returns:
            Public URL of the uploaded image

        Raises:
            Exception: If upload fails
        """
        if not image_path.exists():
            raise FileNotFoundError(f"Image file not found: {image_path}")

        # Prepare the multipart form data
        with open(image_path, 'rb') as f:
            files = {
                'data': (image_path.name, f, self._get_mime_type(image_path))
            }
            data = {
                'folder': folder
            }

            # Make the upload request
            response = self.session.post(
                self.config.backend_url,
                files=files,
                data=data,
                timeout=30
            )

        # Check for successful upload
        if response.status_code != 200:
            raise Exception(f"Upload failed with status {response.status_code}: {response.text}")

        # Parse the response
        try:
            result = response.json()
            public_url = result.get('public_url')
            if not public_url:
                raise Exception("No public_url in response")
            return public_url
        except (ValueError, KeyError) as e:
            raise Exception(f"Invalid response from server: {str(e)}")

    def _get_mime_type(self, file_path: Path) -> str:
        """Get MIME type for an image file"""
        mime_types = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.svg': 'image/svg+xml',
            '.webp': 'image/webp',
            '.bmp': 'image/bmp',
            '.ico': 'image/x-icon'
        }
        return mime_types.get(file_path.suffix.lower(), 'application/octet-stream')
