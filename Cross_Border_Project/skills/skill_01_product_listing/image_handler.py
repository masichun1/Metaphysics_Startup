import logging
from core.logger import get_logger
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import httpx

from core.shopify_client import ShopifyClient

logger = get_logger("metaphysics.skill_01")


class ImageHandler:
    """
    Download product images from URLs and upload them to Shopify.

    Handles: download -> temp storage -> Shopify upload -> temp cleanup.
    """

    def __init__(
        self,
        shopify_client: ShopifyClient,
        download_timeout: int = 30,
        max_dimensions: tuple[int, int] = (2048, 2048),
    ):
        self.shopify = shopify_client
        self.download_timeout = download_timeout
        self.max_dimensions = max_dimensions
        self._http = httpx.Client(timeout=httpx.Timeout(download_timeout))

    def close(self) -> None:
        self._http.close()

    def process_images(
        self, product_id: int, image_urls: list[str]
    ) -> list[dict]:
        """
        Download images from URLs and upload to a Shopify product.

        Returns list of uploaded image objects from Shopify.
        """
        uploaded: list[dict] = []
        temp_dir = Path(tempfile.mkdtemp(prefix="shopify_img_"))

        try:
            for idx, url in enumerate(image_urls):
                try:
                    image_result = self._download_and_upload(
                        product_id, url, idx, temp_dir
                    )
                    if image_result:
                        uploaded.append(image_result)
                except Exception as e:
                    logger.warning(
                        "image_upload_failed",
                        product_id=product_id,
                        url=url[:100],
                        error=str(e),
                    )
        finally:
            # Cleanup temp files
            for f in temp_dir.glob("*"):
                try:
                    f.unlink()
                except OSError:
                    pass
            try:
                temp_dir.rmdir()
            except OSError:
                pass

        return uploaded

    def _download_and_upload(
        self, product_id: int, url: str, index: int, temp_dir: Path
    ) -> dict | None:
        """Download a single image and upload to Shopify."""
        parsed = urlparse(url)
        filename = Path(parsed.path).name or f"image_{index}.jpg"

        # Basic extension validation
        ext = Path(filename).suffix.lower()
        if ext not in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
            filename = f"{filename}.jpg"

        temp_path = temp_dir / filename

        # Download
        response = self._http.get(url, follow_redirects=True)
        response.raise_for_status()
        temp_path.write_bytes(response.content)

        # Upload to Shopify
        return self.shopify.upload_product_image(product_id, temp_path)
