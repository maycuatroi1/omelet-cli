"""
Google Cloud authentication module for Omelet
"""
from typing import Optional, Tuple
from google.auth import default
from google.auth.credentials import Credentials
import click


class GCloudAuth:
    """Handle Google Cloud authentication using gcloud CLI credentials"""
    
    def __init__(self):
        self.credentials = None
        self.project_id = None
    
    def is_authenticated(self) -> bool:
        """Check if user is authenticated via gcloud CLI"""
        try:
            self.credentials, self.project_id = default()
            return self.credentials is not None
        except Exception:
            return False
    
    def get_credentials(self) -> Tuple[Optional[Credentials], Optional[str]]:
        """
        Get current credentials from gcloud CLI
        
        Returns:
            Tuple of (credentials, project_id)
        """
        try:
            if not self.credentials:
                self.credentials, self.project_id = default()
            return self.credentials, self.project_id
        except Exception as e:
            click.echo(f"Failed to get gcloud credentials: {str(e)}", err=True)
            click.echo("Make sure you have authenticated with: gcloud auth application-default login", err=True)
            return None, None