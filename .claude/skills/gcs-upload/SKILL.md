---
name: gcs-upload
description: Work with Google Cloud Storage for image uploads. Use when the user needs help with GCS configuration, authentication, or upload issues.
allowed-tools: Read, Bash, Grep
---

# Google Cloud Storage Upload Skill

This skill helps configure and troubleshoot GCS uploads in Omelet CLI.

## Authentication Setup

### 1. Install gcloud CLI
```bash
# macOS
brew install google-cloud-sdk

# Verify installation
gcloud --version
```

### 2. Authenticate
```bash
# Application default credentials (required for omelet)
gcloud auth application-default login

# Check current auth
gcloud auth list
```

### 3. Configure Project
```bash
# Set project
gcloud config set project YOUR_PROJECT_ID

# View config
gcloud config list
```

## Bucket Configuration

### In `.omelet.json`:
```json
{
  "use_gcs": true,
  "gcs_bucket": "your-bucket-name"
}
```

### Or Environment Variables:
```bash
export OMELET_USE_GCS=true
export OMELET_GCS_BUCKET=your-bucket-name
```

## Troubleshooting

### Permission Denied
```bash
# Check bucket access
gsutil ls gs://bucket-name/

# Grant access (if you're bucket admin)
gsutil iam ch user:email@example.com:objectCreator gs://bucket-name
```

### Authentication Expired
```bash
# Re-authenticate
gcloud auth application-default login
```

### Wrong Project
```bash
# List projects
gcloud projects list

# Switch project
gcloud config set project correct-project-id
```

## Upload Path Structure

Files are uploaded to:
```
gs://bucket-name/public/blog/{folder}/{filename}
```

Public URL format:
```
https://storage.googleapis.com/{bucket}/public/blog/{folder}/{filename}
```

## Testing GCS Upload
```python
from omelet.gcs_uploader import GCSUploader

uploader = GCSUploader("bucket-name")
url = uploader.upload("image.png", "test-folder")
print(url)
```
