class MetaphysicsException(Exception):
    """Base exception for the entire project."""
    pass


# --- Configuration errors ---
class ConfigError(MetaphysicsException):
    pass


class MissingApiKeyError(ConfigError):
    pass


class InvalidConfigError(ConfigError):
    pass


# --- Shopify errors ---
class ShopifyError(MetaphysicsException):
    pass


class ShopifyRateLimitError(ShopifyError):
    pass


class ShopifyAuthError(ShopifyError):
    pass


class ShopifyValidationError(ShopifyError):
    pass


class ShopifyNotFoundError(ShopifyError):
    pass


# --- AI errors ---
class AIError(MetaphysicsException):
    pass


class AITokenLimitError(AIError):
    pass


class AIResponseParseError(AIError):
    pass


class AIQuotaExceededError(AIError):
    pass


# --- Skill errors ---
class SkillError(MetaphysicsException):
    pass


class SkillConfigError(SkillError):
    pass


class SkillExecutionError(SkillError):
    pass


class ComplianceGateError(SkillError):
    """Raised when a skill requires a compliance flag to proceed."""
    pass


# --- Network errors ---
class NetworkError(MetaphysicsException):
    pass


class TimeoutError(NetworkError):
    pass


class ConnectionError(NetworkError):
    pass


# --- Retry exhaustion ---
class MaxRetriesExceeded(MetaphysicsException):
    pass
