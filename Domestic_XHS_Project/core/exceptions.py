class XHSException(Exception):
    """Base exception for XHS project."""
    pass


class BrowserError(XHSException):
    """Playwright/OpenCLI browser errors."""
    pass


class LoginError(XHSException):
    """XHS login failure."""
    pass


class RateLimitError(XHSException):
    """Triggered by XHS anti-spider mechanisms."""
    pass


class CookieExpiredError(XHSException):
    """Cookies expired and re-login required."""
    pass


class ProxyError(XHSException):
    """Proxy connectivity failure."""
    pass


class CaptchaError(XHSException):
    """CAPTCHA triggered — requires manual intervention."""
    pass


class DataParseError(XHSException):
    """Failed to parse scraped content."""
    pass


class ConfigError(XHSException):
    """Configuration issues."""
    pass
