"""
Configuration module for Omelet
"""
import os
from pathlib import Path
import json
from typing import Optional


class Config:
    """Configuration manager for Omelet"""
    
    def __init__(self, config_file: Optional[Path] = None):
        self.config_file = config_file or self._get_default_config_path()
        self.config = self._load_config()
        
        # Set up properties for easy access
        self.backend_url = self.get('backend_url', 'https://n8n.omelet.tech/webhook-test/3a4e5b1a-1cd3-459b-adb0-803753a95943')
        self.username = self.get('username', os.environ.get('OMELET_USERNAME'))
        self.password = self.get('password', os.environ.get('OMELET_PASSWORD'))
        
        # Google Cloud Storage settings
        self.gcs_bucket = self.get('gcs_bucket', os.environ.get('OMELET_GCS_BUCKET', 'omelet-f0b89.appspot.com'))
        self.use_gcs = self.get('use_gcs', os.environ.get('OMELET_USE_GCS', 'false').lower() == 'true')
        
        # Public webhook URL for publishing markdown
        self.public_webhook_url = self.get('public_webhook_url', os.environ.get('OMELET_PUBLIC_WEBHOOK_URL'))

        # Ghost CMS settings
        self.ghost_api_url = self.get('ghost_api_url', os.environ.get('GHOST_API_URL'))
        self.ghost_admin_api_key = self.get('ghost_admin_api_key', os.environ.get('GHOST_ADMIN_API_KEY'))
    
    def _get_default_config_path(self) -> Path:
        """Get the default configuration file path"""
        # Look for config in these locations (in order):
        # 1. Current directory
        # 2. User's home directory
        
        config_locations = [
            Path.cwd() / '.omelet.json',
            Path.home() / '.omelet.json',
        ]
        
        for location in config_locations:
            if location.exists():
                return location
        
        # If no config exists, use home directory as default
        return Path.home() / '.omelet.json'
    
    def _load_config(self) -> dict:
        """Load configuration from file"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        
        # Return empty config (will use defaults)
        return {}
    
    def get(self, key: str, default=None):
        """Get a configuration value"""
        return self.config.get(key, default)
    
    def save_example_config(self):
        """Save an example configuration file"""
        example_config = {
            "backend_url": "https://n8n.omelet.tech/webhook-test/3a4e5b1a-1cd3-459b-adb0-803753a95943",
            "public_webhook_url": "https://your-webhook-url.com/webhook",
            "username": "your-username",
            "password": "your-password",
            "use_gcs": False,
            "gcs_bucket": "omelet-f0b89.appspot.com",
            "ghost_api_url": "https://your-site.ghost.io",
            "ghost_admin_api_key": "your-key-id:your-secret"
        }
        
        config_path = Path.home() / '.omelet.json.example'
        with open(config_path, 'w') as f:
            json.dump(example_config, f, indent=2)
        
        return config_path