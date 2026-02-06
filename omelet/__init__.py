"""
Omelet - Markdown image upload automation tool
"""

__version__ = "0.1.0"

from .cli import cli
from .markdown_processor import MarkdownProcessor
from .gcs_uploader import GCSUploader
from .config import Config
from .ghost_client import GhostClient
from .gemini_image import GeminiImageGenerator

__all__ = ['cli', 'MarkdownProcessor', 'GCSUploader', 'Config', 'GhostClient', 'GeminiImageGenerator']