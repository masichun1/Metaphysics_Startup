import hashlib
import hmac
import json
import time
from base64 import b64encode
from pathlib import Path
from typing import Any

import httpx

from core.config_loader import AppConfig, ShopifyConfig
from core.exceptions import (
    ShopifyAuthError,
    ShopifyError,
    ShopifyNotFoundError,
    ShopifyRateLimitError,
    ShopifyValidationError,
)
from core.retry import retry_on_failure

# Shopify leaky bucket: default 40 requests per second, 2 replenished per second.
# We use a token bucket with burst=40, refill_rate=2/s.
_TOKEN_BUCKET_MAX = 40
_TOKEN_REFILL_RATE = 2.0  # tokens per second


class TokenBucket:
    """Simple token bucket for Shopify rate limiting."""

    def __init__(self, max_tokens: int = _TOKEN_BUCKET_MAX, refill_rate: float = _TOKEN_REFILL_RATE):
        self.max_tokens = max_tokens
        self.refill_rate = refill_rate
        self._tokens = float(max_tokens)
        self._last_refill = time.monotonic()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self.max_tokens, self._tokens + elapsed * self.refill_rate)
        self._last_refill = now

    def acquire(self) -> bool:
        """Try to acquire a token. Returns True if acquired, False if must wait."""
        self._refill()
        if self._tokens >= 1.0:
            self._tokens -= 1.0
            return True
        return False

    def wait_for_token(self) -> None:
        """Block until a token is available."""
        while not self.acquire():
            time.sleep(0.05)


class ShopifyClient:
    """
    Unified Shopify Admin API client supporting both REST and GraphQL.

    Features:
    - Token bucket rate limiting
    - Automatic retry on 429/5xx
    - HMAC webhook verification
    """

    def __init__(self, config: ShopifyConfig):
        self.config = config
        self.base_url = f"https://{config.domain}/admin/api/{config.api_version}"
        self._bucket = TokenBucket()
        self._client = httpx.Client(
            headers={
                "X-Shopify-Access-Token": config.access_token,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=httpx.Timeout(30.0, connect=10.0),
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "ShopifyClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    # --- REST helpers ---

    def _url(self, endpoint: str) -> str:
        return f"{self.base_url}/{endpoint.lstrip('/')}"

    def _update_rate_limit(self, response: httpx.Response) -> None:
        """Update token bucket from response headers."""
        header = response.headers.get("X-Shopify-Shop-Api-Call-Limit", "")
        if header:
            parts = header.split("/")
            if len(parts) == 2:
                used = int(parts[0])
                limit = int(parts[1])
                # Adjust available tokens based on server-side usage
                remaining = limit - used
                self._bucket._tokens = min(
                    float(self._bucket.max_tokens),
                    max(0, float(remaining)),
                )

    def _handle_response(self, response: httpx.Response) -> dict | list:
        self._update_rate_limit(response)
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After", "2")
            raise ShopifyRateLimitError(f"Rate limited. Retry after {retry_after}s")
        if response.status_code == 401:
            raise ShopifyAuthError("Invalid Shopify access token")
        if response.status_code == 404:
            raise ShopifyNotFoundError(f"Resource not found: {response.request.url}")
        if response.status_code == 422:
            errors = response.json() if response.text else {}
            raise ShopifyValidationError(f"Validation error: {errors}")
        if response.status_code >= 500:
            raise ShopifyError(f"Shopify server error {response.status_code}: {response.text[:500]}")
        if response.text:
            return response.json()
        return {}

    @retry_on_failure(
        max_attempts=3,
        retryable_exceptions=(ShopifyRateLimitError, ShopifyError),
    )
    def rest_get(self, endpoint: str, params: dict | None = None) -> dict | list:
        self._bucket.wait_for_token()
        response = self._client.get(self._url(endpoint), params=params)
        return self._handle_response(response)

    @retry_on_failure(
        max_attempts=3,
        retryable_exceptions=(ShopifyRateLimitError, ShopifyError),
    )
    def rest_post(self, endpoint: str, data: dict) -> dict:
        self._bucket.wait_for_token()
        response = self._client.post(self._url(endpoint), json=data)
        return self._handle_response(response)

    @retry_on_failure(
        max_attempts=3,
        retryable_exceptions=(ShopifyRateLimitError, ShopifyError),
    )
    def rest_put(self, endpoint: str, data: dict) -> dict:
        self._bucket.wait_for_token()
        response = self._client.put(self._url(endpoint), json=data)
        return self._handle_response(response)

    @retry_on_failure(
        max_attempts=3,
        retryable_exceptions=(ShopifyRateLimitError, ShopifyError),
    )
    def rest_delete(self, endpoint: str) -> dict:
        self._bucket.wait_for_token()
        response = self._client.delete(self._url(endpoint))
        return self._handle_response(response)

    # --- GraphQL ---

    def graphql_url(self) -> str:
        return f"https://{self.config.domain}/admin/api/{self.config.api_version}/graphql.json"

    @retry_on_failure(
        max_attempts=3,
        retryable_exceptions=(ShopifyRateLimitError, ShopifyError),
    )
    def graphql(self, query: str, variables: dict | None = None) -> dict:
        self._bucket.wait_for_token()
        response = self._client.post(
            self.graphql_url(),
            json={"query": query, "variables": variables or {}},
        )
        result = self._handle_response(response)
        if isinstance(result, dict) and "errors" in result:
            raise ShopifyError(f"GraphQL errors: {result['errors']}")
        return result

    # --- High-level operations ---

    # -- Products --

    def get_products(self, limit: int = 250, since_id: int | None = None) -> list[dict]:
        params: dict[str, Any] = {"limit": limit}
        if since_id:
            params["since_id"] = since_id
        result = self.rest_get("products.json", params=params)
        if isinstance(result, dict):
            return result.get("products", [])
        return []

    def get_all_products(self) -> list[dict]:
        """Paginate through all products."""
        products = []
        since_id = None
        while True:
            batch = self.get_products(since_id=since_id)
            if not batch:
                break
            products.extend(batch)
            since_id = batch[-1]["id"]
        return products

    def create_product(self, product_data: dict) -> dict:
        result = self.rest_post("products.json", {"product": product_data})
        if isinstance(result, dict):
            return result.get("product", {})
        return {}

    def update_product(self, product_id: int, product_data: dict) -> dict:
        result = self.rest_put(
            f"products/{product_id}.json", {"product": product_data}
        )
        if isinstance(result, dict):
            return result.get("product", {})
        return {}

    def get_product_by_sku(self, sku: str) -> dict | None:
        """Look up a product by SKU via GraphQL."""
        query = """
        query($sku: String!) {
            productVariants(first: 1, query: $sku) {
                edges {
                    node {
                        product { id title handle }
                    }
                }
            }
        }
        """
        result = self.graphql(query, variables={"sku": sku})
        edges = (
            result.get("data", {})
            .get("productVariants", {})
            .get("edges", [])
        )
        if edges:
            return edges[0]["node"]["product"]
        return None

    def upload_product_image(self, product_id: int, image_path: str | Path) -> dict:
        """
        Upload an image to a product from a local file path.
        Uses base64-encoded image in the REST API.
        """
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {path}")
        content = path.read_bytes()
        encoded = b64encode(content).decode("utf-8")
        ext = path.suffix.lower().lstrip(".")
        mime_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "gif": "image/gif", "webp": "image/webp"}
        mime = mime_map.get(ext, "image/jpeg")
        attachment = encoded
        filename = path.name
        result = self.rest_post(
            f"products/{product_id}/images.json",
            {
                "image": {
                    "attachment": attachment,
                    "filename": filename,
                }
            },
        )
        if isinstance(result, dict):
            return result.get("image", {})
        return {}

    # -- Orders --

    def get_orders(
        self,
        status: str = "any",
        created_at_min: str | None = None,
        created_at_max: str | None = None,
        limit: int = 250,
    ) -> list[dict]:
        params: dict[str, Any] = {"status": status, "limit": limit}
        if created_at_min:
            params["created_at_min"] = created_at_min
        if created_at_max:
            params["created_at_max"] = created_at_max
        result = self.rest_get("orders.json", params=params)
        if isinstance(result, dict):
            return result.get("orders", [])
        return []

    def get_all_orders(
        self,
        status: str = "any",
        created_at_min: str | None = None,
        created_at_max: str | None = None,
    ) -> list[dict]:
        """Paginate through all orders in a date range."""
        orders = []
        page_info = None
        while True:
            params: dict[str, Any] = {
                "status": status,
                "limit": 250,
            }
            if created_at_min:
                params["created_at_min"] = created_at_min
            if created_at_max:
                params["created_at_max"] = created_at_max
            if page_info:
                params["page_info"] = page_info
            result = self.rest_get("orders.json", params=params)
            if isinstance(result, dict):
                orders.extend(result.get("orders", []))
                # Check Link header for next page
                link_header = ""
                # If there are fewer results than limit, we're done
                if len(result.get("orders", [])) < 250:
                    break
                # Fallback: increment offset via since_id
                last = result.get("orders", [])[-1] if result.get("orders") else None
                if last:
                    page_info = str(last["id"])
                else:
                    break
            else:
                break
            if len(result.get("orders", [])) < 250:
                break
        return orders

    def get_order_refunds(self, order_id: int) -> list[dict]:
        result = self.rest_get(f"orders/{order_id}/refunds.json")
        if isinstance(result, dict):
            return result.get("refunds", [])
        return []

    # -- Abandoned checkouts --

    def get_abandoned_checkouts(
        self,
        created_at_min: str | None = None,
        created_at_max: str | None = None,
        limit: int = 250,
    ) -> list[dict]:
        params: dict[str, Any] = {"limit": limit}
        if created_at_min:
            params["created_at_min"] = created_at_min
        if created_at_max:
            params["created_at_max"] = created_at_max
        result = self.rest_get("checkouts.json", params=params)
        if isinstance(result, dict):
            return result.get("checkouts", [])
        return []

    # -- Blogs & Articles --

    def get_blogs(self) -> list[dict]:
        result = self.rest_get("blogs.json")
        if isinstance(result, dict):
            return result.get("blogs", [])
        return []

    def get_blog_by_handle(self, handle: str) -> dict | None:
        """Find a blog by its handle."""
        blogs = self.get_blogs()
        for blog in blogs:
            if blog.get("handle") == handle:
                return blog
        return None

    def create_article(self, blog_id: int, article_data: dict) -> dict:
        result = self.rest_post(
            f"blogs/{blog_id}/articles.json",
            {"article": article_data},
        )
        if isinstance(result, dict):
            return result.get("article", {})
        return {}

    def get_articles(self, blog_id: int) -> list[dict]:
        result = self.rest_get(f"blogs/{blog_id}/articles.json")
        if isinstance(result, dict):
            return result.get("articles", [])
        return []

    # -- Metafields (for storing cost price) --

    def get_product_metafields(self, product_id: int) -> list[dict]:
        result = self.rest_get(f"products/{product_id}/metafields.json")
        if isinstance(result, dict):
            return result.get("metafields", [])
        return []

    def set_product_metafield(self, product_id: int, namespace: str, key: str, value: str, value_type: str = "string") -> dict:
        result = self.rest_post(
            f"products/{product_id}/metafields.json",
            {
                "metafield": {
                    "namespace": namespace,
                    "key": key,
                    "value": value,
                    "type": value_type,
                }
            },
        )
        if isinstance(result, dict):
            return result.get("metafield", {})
        return {}

    # -- Price Rules & Discounts --

    def create_price_rule(self, rule_data: dict) -> dict:
        result = self.rest_post("price_rules.json", {"price_rule": rule_data})
        if isinstance(result, dict):
            return result.get("price_rule", {})
        return {}

    def create_discount_code(self, price_rule_id: int, code: str) -> dict:
        result = self.rest_post(
            f"price_rules/{price_rule_id}/discount_codes.json",
            {"discount_code": {"code": code}},
        )
        if isinstance(result, dict):
            return result.get("discount_code", {})
        return {}

    # --- Webhook verification ---

    @staticmethod
    def verify_webhook_hmac(
        secret: str, data: bytes, hmac_header: str
    ) -> bool:
        """Verify Shopify webhook HMAC signature."""
        digest = hmac.new(
            secret.encode("utf-8"), data, hashlib.sha256
        ).digest()
        computed = b64encode(digest).decode("utf-8")
        return hmac.compare_digest(computed, hmac_header)
