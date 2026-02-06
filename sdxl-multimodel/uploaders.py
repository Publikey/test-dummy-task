import logging
import uuid
from io import BytesIO
from PIL import Image

logger = logging.getLogger(__name__)


class UploadError(Exception):
    """Raised when all upload providers fail."""
    pass


class AzureProvider:
    name = "azure"

    def __init__(self, connection_string: str, container: str):
        from azure.storage.blob import BlobServiceClient, ContentSettings
        self.blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        self.container = container
        self.ContentSettings = ContentSettings

    def upload(self, image: Image.Image) -> str:
        buffered = BytesIO()
        image.save(buffered, format="JPEG", quality=95)
        image_bytes = buffered.getvalue()

        blob_name = f"{uuid.uuid4()}.jpg"
        blob_client = self.blob_service_client.get_blob_client(
            container=self.container, blob=blob_name
        )
        blob_client.upload_blob(
            image_bytes,
            blob_type="BlockBlob",
            overwrite=True,
            content_settings=self.ContentSettings(content_type="image/jpeg")
        )
        return blob_client.url


# To add a new provider, create a class with:
#   - name: str
#   - upload(image) -> str (returns URL)
#
# Example:
#
# class S3Provider:
#     name = "s3"
#     def __init__(self, bucket, region, ...): ...
#     def upload(self, image) -> str: ...


class ImageUploader:
    """Chain of upload providers. First success wins."""

    def __init__(self):
        self.providers = []

    def add_provider(self, provider):
        self.providers.append(provider)
        logger.info(f"Upload provider registered: {provider.name}")

    def upload(self, image: Image.Image) -> str:
        if not self.providers:
            raise UploadError("No upload providers configured")

        errors = []
        for provider in self.providers:
            try:
                url = provider.upload(image)
                logger.info(f"Uploaded via {provider.name}: {url}")
                return url
            except Exception as e:
                logger.warning(f"Upload failed with {provider.name}: {e}")
                errors.append(f"{provider.name}: {e}")

        raise UploadError(f"All upload providers failed: {'; '.join(errors)}")
