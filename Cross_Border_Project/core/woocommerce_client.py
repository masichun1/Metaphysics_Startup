"""WooCommerce REST API v3 client — WordPress + WooCommerce automation."""

import hashlib
import hmac
import json
import time
from base64 import b64encode
from typing import Any
from urllib.parse import urlencode, urljoin

import httpx

from core.exceptions import (
    ShopifyAuthError as WooCommerceAuthError,
    ShopifyError as WooCommerceError,
    ShopifyNotFoundError as WooCommerceNotFoundError,
    ShopifyRateLimitError as WooCommerceRateLimitError,
    ShopifyValidationError as WooCommerceValidationError,
)
from core.retry import retry_on_failure


class WooCommerceClient:
    """WooCommerce REST API v3 client with OAuth 1.0a authentication.

    Base URL: {site_url}/wp-json/wc/v3/
    Auth: Consumer Key + Consumer Secret
    """

    def __init__(
        self,
        site_url: str,
        consumer_key: str,
        consumer_secret: str,
        api_version: str = "wc/v3",
        timeout_seconds: int = 30,
    ):
        self.site_url = site_url.rstrip("/")
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.api_version = api_version
        self.base_url = f"{self.site_url}/wp-json/{api_version}/"
        self._client = httpx.Client(timeout=httpx.Timeout(timeout_seconds))

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "WooCommerceClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    # --- OAuth 1.0a ---

    def _get_oauth_params(self) -> dict[str, str]:
        """Build OAuth 1.0a query parameters."""
        return {
            "consumer_key": self.consumer_key,
            "consumer_secret": self.consumer_secret,
        }

    def _request(
        self,
        method: str,
        endpoint: str,
        params: dict | None = None,
        data: dict | None = None,
    ) -> dict | list:
        """Make an authenticated request to the WooCommerce REST API."""
        url = urljoin(self.base_url, endpoint.lstrip("/"))

        request_params = self._get_oauth_params()
        if params:
            request_params.update(params)

        try:
            if method == "GET":
                response = self._client.get(url, params=request_params)
            elif method == "POST":
                response = self._client.post(url, params=request_params, json=data)
            elif method == "PUT":
                response = self._client.put(url, params=request_params, json=data)
            elif method == "DELETE":
                response = self._client.delete(url, params=request_params)
            else:
                raise WooCommerceError(f"Unsupported method: {method}")
        except httpx.RequestError as e:
            raise WooCommerceError(f"Request failed: {e}") from e

        return self._handle_response(response)

    def _handle_response(self, response: httpx.Response) -> dict | list:
        """Parse and handle API response."""
        if response.status_code == 401:
            raise WooCommerceAuthError("Invalid WooCommerce API credentials")
        if response.status_code == 404:
            raise WooCommerceNotFoundError(f"Resource not found: {response.request.url}")
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After", "5")
            raise WooCommerceRateLimitError(f"Rate limited. Retry after {retry_after}s")
        if response.status_code >= 400:
            raise WooCommerceValidationError(
                f"WooCommerce error {response.status_code}: {response.text[:500]}"
            )
        if response.status_code >= 500:
            raise WooCommerceError(f"Server error {response.status_code}: {response.text[:500]}")
        return response.json() if response.text else {}

    # --- Products ---

    @retry_on_failure(
        max_attempts=3,
        retryable_exceptions=(WooCommerceRateLimitError, WooCommerceError),
    )
    def get_products(self, per_page: int = 100, page: int = 1, **filters) -> list[dict]:
        """Get products with pagination."""
        params = {"per_page": per_page, "page": page, **filters}
        result = self._request("GET", "products", params=params)
        return result if isinstance(result, list) else []

    def get_all_products(self, **filters) -> list[dict]:
        """Paginate through all products."""
        products = []
        page = 1
        while True:
            batch = self.get_products(per_page=100, page=page, **filters)
            if not batch:
                break
            products.extend(batch)
            if len(batch) < 100:
                break
            page += 1
        return products

    @retry_on_failure(
        max_attempts=3,
        retryable_exceptions=(WooCommerceRateLimitError, WooCommerceError),
    )
    def create_product(self, product_data: dict) -> dict:
        """Create a new product."""
        return self._request("POST", "products", data=product_data)

    @retry_on_failure(
        max_attempts=3,
        retryable_exceptions=(WooCommerceRateLimitError, WooCommerceError),
    )
    def update_product(self, product_id: int, product_data: dict) -> dict:
        """Update an existing product."""
        return self._request("PUT", f"products/{product_id}", data=product_data)

    @retry_on_failure(
        max_attempts=3,
        retryable_exceptions=(WooCommerceRateLimitError, WooCommerceError),
    )
    def delete_product(self, product_id: int, force: bool = True) -> dict:
        """Delete a product."""
        return self._request("DELETE", f"products/{product_id}", params={"force": force})

    def get_product_by_sku(self, sku: str) -> dict | None:
        """Look up a product by SKU."""
        results = self.get_products(sku=sku, per_page=1)
        return results[0] if results else None

    def create_product_variation(self, product_id: int, variation_data: dict) -> dict:
        """Create a product variation."""
        return self._request("POST", f"products/{product_id}/variations", data=variation_data)

    def batch_create_products(self, products: list[dict]) -> dict:
        """Batch create/update products (max 100 per request)."""
        return self._request("POST", "products/batch", data={"create": products})

    # --- Product Reviews ---

    @retry_on_failure(
        max_attempts=3,
        retryable_exceptions=(WooCommerceRateLimitError, WooCommerceError),
    )
    def get_reviews(self, per_page: int = 100, page: int = 1, product_id: int | None = None) -> list[dict]:
        """Get product reviews."""
        params: dict[str, Any] = {"per_page": per_page, "page": page}
        if product_id:
            params["product"] = product_id
        result = self._request("GET", "products/reviews", params=params)
        return result if isinstance(result, list) else []

    @retry_on_failure(
        max_attempts=3,
        retryable_exceptions=(WooCommerceRateLimitError, WooCommerceError),
    )
    def create_review(self, review_data: dict) -> dict:
        """Create a product review."""
        return self._request("POST", "products/reviews", data=review_data)

    def batch_create_reviews(self, reviews: list[dict]) -> dict:
        """Batch create reviews (max 100 per request)."""
        return self._request("POST", "products/reviews/batch", data={"create": reviews})

    # --- Orders ---

    @retry_on_failure(
        max_attempts=3,
        retryable_exceptions=(WooCommerceRateLimitError, WooCommerceError),
    )
    def get_orders(
        self,
        per_page: int = 100,
        page: int = 1,
        after: str | None = None,
        before: str | None = None,
        status: str | None = None,
    ) -> list[dict]:
        """Get orders with optional date range and status filter."""
        params: dict[str, Any] = {"per_page": per_page, "page": page}
        if after:
            params["after"] = after
        if before:
            params["before"] = before
        if status:
            params["status"] = status
        result = self._request("GET", "orders", params=params)
        return result if isinstance(result, list) else []

    def get_all_orders(
        self,
        after: str | None = None,
        before: str | None = None,
        status: str | None = None,
    ) -> list[dict]:
        """Paginate through all orders in a date range."""
        orders = []
        page = 1
        while True:
            batch = self.get_orders(per_page=100, page=page, after=after, before=before, status=status)
            if not batch:
                break
            orders.extend(batch)
            if len(batch) < 100:
                break
            page += 1
        return orders

    @retry_on_failure(
        max_attempts=3,
        retryable_exceptions=(WooCommerceRateLimitError, WooCommerceError),
    )
    def update_order_status(self, order_id: int, status: str) -> dict:
        """Update order status (pending, processing, completed, etc.)."""
        return self._request("PUT", f"orders/{order_id}", data={"status": status})

    # --- Coupons (for abandoned cart recovery) ---

    @retry_on_failure(
        max_attempts=3,
        retryable_exceptions=(WooCommerceRateLimitError, WooCommerceError),
    )
    def create_coupon(self, coupon_data: dict) -> dict:
        """Create a discount coupon."""
        return self._request("POST", "coupons", data=coupon_data)

    def get_coupons(self) -> list[dict]:
        """Get all coupons."""
        result = self._request("GET", "coupons", params={"per_page": 100})
        return result if isinstance(result, list) else []

    # --- Reports ---

    def get_sales_report(self, date_min: str, date_max: str) -> dict:
        """Get sales report for a date range."""
        params = {"date_min": date_min, "date_max": date_max}
        return self._request("GET", "reports/sales", params=params)

    def get_orders_report(self, date_min: str, date_max: str) -> dict:
        """Get orders report for a date range."""
        params = {"date_min": date_min, "date_max": date_max}
        return self._request("GET", "reports/orders/totals", params=params)

    def get_top_sellers(self, period: str = "month") -> list[dict]:
        """Get top selling products report."""
        return self._request("GET", "reports/products/top_sellers", params={"period": period})


# ============================================================
# WordPress REST API client for Blog/Site operations
# ============================================================

class WordPressClient:
    """WordPress REST API v2 client for blog and site management.

    Uses Application Passwords for authentication (WordPress 5.6+).
    """

    def __init__(
        self,
        site_url: str,
        username: str,
        app_password: str,
    ):
        self.site_url = site_url.rstrip("/")
        self.api_base = f"{self.site_url}/wp-json/wp/v2/"
        auth_str = b64encode(f"{username}:{app_password}".encode()).decode()
        self._client = httpx.Client(
            headers={
                "Authorization": f"Basic {auth_str}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(30.0),
        )

    def close(self) -> None:
        self._client.close()

    # --- Posts / Blog ---

    def get_posts(self, per_page: int = 100, page: int = 1, **filters) -> list[dict]:
        params = {"per_page": per_page, "page": page, **filters}
        response = self._client.get(f"{self.api_base}posts", params=params)
        return response.json() if response.status_code == 200 else []

    def create_post(self, post_data: dict) -> dict:
        response = self._client.post(f"{self.api_base}posts", json=post_data)
        response.raise_for_status()
        return response.json()

    def update_post(self, post_id: int, post_data: dict) -> dict:
        response = self._client.put(f"{self.api_base}posts/{post_id}", json=post_data)
        response.raise_for_status()
        return response.json()

    def get_categories(self) -> list[dict]:
        response = self._client.get(f"{self.api_base}categories", params={"per_page": 100})
        return response.json() if response.status_code == 200 else []

    def create_category(self, name: str, slug: str = "") -> dict:
        data = {"name": name}
        if slug:
            data["slug"] = slug
        response = self._client.post(f"{self.api_base}categories", json=data)
        response.raise_for_status()
        return response.json()

    def get_tags(self) -> list[dict]:
        response = self._client.get(f"{self.api_base}tags", params={"per_page": 100})
        return response.json() if response.status_code == 200 else []

    def create_tag(self, name: str) -> dict:
        response = self._client.post(f"{self.api_base}tags", json={"name": name})
        response.raise_for_status()
        return response.json()

    # --- Media ---

    def upload_media(self, file_path: str, title: str = "") -> dict:
        """Upload an image/file to WordPress media library."""
        import mimetypes
        from pathlib import Path

        path = Path(file_path)
        mime_type = mimetypes.guess_type(path)[0] or "image/jpeg"

        with open(path, "rb") as f:
            file_content = f.read()

        filename = path.name
        response = self._client.post(
            f"{self.api_base}media",
            files={"file": (filename, file_content, mime_type)},
            data={"title": title or path.stem},
        )
        response.raise_for_status()
        return response.json()
