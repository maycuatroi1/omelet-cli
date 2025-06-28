"""
Google Cloud Storage uploader module
"""
from pathlib import Path
from google.cloud import storage
from .gcloud_auth import GCloudAuth


class GCSUploader:
    """Handler for uploading images to Google Cloud Storage"""
    
    def __init__(self, bucket_name: str, auth: GCloudAuth):
        """
        Initialize GCS uploader
        
        Args:
            bucket_name: Name of the GCS bucket
            auth: GCloudAuth instance
        """
        self.bucket_name = bucket_name
        self.auth = auth
        self.client = None
        self.bucket = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize GCS client and bucket"""
        credentials, project_id = self.auth.get_credentials()
        if not credentials:
            raise Exception("Failed to get Google Cloud credentials")
        
        self.client = storage.Client(
            credentials=credentials,
            project=project_id
        )
        self.bucket = self.client.bucket(self.bucket_name)
    
    def upload_image(self, image_path: Path, folder: str) -> str:
        """
        Upload a single image to Google Cloud Storage
        
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
        
        # Construct the blob name (path in GCS)
        blob_name = f"public/blog/{folder}/{image_path.name}"
        
        # Create a blob
        blob = self.bucket.blob(blob_name)
        
        # Set content type based on file extension
        content_type = self._get_mime_type(image_path)
        
        # Upload the file
        with open(image_path, 'rb') as f:
            blob.upload_from_file(f, content_type=content_type)
        
        # Make the blob publicly accessible
        blob.make_public()
        
        # Return the public URL
        return f"https://storage.googleapis.com/{self.bucket_name}/{blob_name}"
    
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