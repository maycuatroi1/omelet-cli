"""
Module for processing markdown files
"""
from pathlib import Path
import re
from typing import List, Dict, Any


class MarkdownProcessor:
    """Processor for markdown files"""
    
    def __init__(self):
        self.image_pattern = r'!\[([^\]]*)\]\(([^)]+)\)'
    
    def find_local_images(self, content: str, markdown_path: Path) -> List[Dict[str, Any]]:
        """
        Find all local images in markdown content
        
        Args:
            content: The markdown content
            markdown_path: Path to the markdown file
            
        Returns:
            List of dictionaries containing image information
        """
        images = []
        
        # Find all image references
        matches = re.finditer(self.image_pattern, content)
        
        for match in matches:
            alt_text = match.group(1)
            image_path = match.group(2)
            
            # Check if it's a local image
            if self._is_local_image(image_path):
                # Resolve the absolute path
                if image_path.startswith('./'):
                    absolute_path = markdown_path.parent / image_path[2:]
                elif image_path.startswith('../'):
                    absolute_path = markdown_path.parent / image_path
                else:
                    absolute_path = markdown_path.parent / image_path
                
                absolute_path = absolute_path.resolve()
                
                # Check if file exists
                if absolute_path.exists() and absolute_path.is_file():
                    images.append({
                        'alt_text': alt_text,
                        'original': image_path,
                        'path': absolute_path,
                        'match_start': match.start(),
                        'match_end': match.end()
                    })
        
        return images
    
    def _is_local_image(self, path: str) -> bool:
        """Check if an image path is local"""
        # Not a URL
        if path.startswith(('http://', 'https://', 'ftp://', '//')):
            return False
        
        # Check for common image extensions
        image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.bmp', '.ico'}
        path_lower = path.lower()
        
        return any(path_lower.endswith(ext) for ext in image_extensions)
    
    def replace_urls(self, content: str, url_mappings: Dict[str, str]) -> str:
        """
        Replace local image paths with public URLs
        
        Args:
            content: The markdown content
            url_mappings: Dictionary mapping original paths to public URLs
            
        Returns:
            Updated markdown content
        """
        # Sort mappings by length (descending) to handle nested paths correctly
        sorted_mappings = sorted(url_mappings.items(), key=lambda x: len(x[0]), reverse=True)
        
        for original_path, public_url in sorted_mappings:
            # Create the pattern to match the exact image reference
            pattern = re.escape(f']({original_path})')
            replacement = f']({public_url})'
            content = content.replace(pattern[1:], replacement)  # Remove the escaping of ']'
        
        return content