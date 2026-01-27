"""
Module for processing markdown files
"""
from pathlib import Path
import re
import hashlib
from typing import List, Dict, Any, Tuple


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
            # Use regex to find and replace the image path in markdown syntax
            # This pattern matches ![alt text](original_path)
            pattern = r'(\!\[[^\]]*\]\()' + re.escape(original_path) + r'(\))'
            replacement = r'\1' + public_url + r'\2'
            content = re.sub(pattern, replacement, content)
        
        return content

    def find_plantuml_blocks(self, content: str) -> List[Dict[str, Any]]:
        """
        Find all PlantUML code blocks in markdown content

        Args:
            content: The markdown content

        Returns:
            List of dictionaries containing PlantUML block information
        """
        blocks = []
        pattern = r'```plantuml\s*\n(.*?)```'

        for match in re.finditer(pattern, content, re.DOTALL):
            puml_content = match.group(1).strip()
            diagram_name = self._extract_diagram_name(puml_content)
            content_hash = hashlib.md5(puml_content.encode()).hexdigest()[:8]

            blocks.append({
                'content': puml_content,
                'full_match': match.group(0),
                'match_start': match.start(),
                'match_end': match.end(),
                'diagram_name': diagram_name,
                'hash': content_hash
            })

        return blocks

    def _extract_diagram_name(self, puml_content: str) -> str:
        """Extract diagram name from @startuml directive"""
        match = re.search(r'@startuml\s+(\S+)', puml_content)
        if match:
            return match.group(1)
        return "diagram"

    def replace_plantuml_with_image(self, content: str, block: Dict[str, Any], image_path: str) -> str:
        """
        Replace a PlantUML code block with an image reference

        Args:
            content: The markdown content
            block: PlantUML block info from find_plantuml_blocks
            image_path: Path or URL to the generated image

        Returns:
            Updated markdown content
        """
        image_markdown = f'![{block["diagram_name"]}]({image_path})'
        return content.replace(block['full_match'], image_markdown)