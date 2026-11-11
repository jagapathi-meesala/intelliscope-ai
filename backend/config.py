"""
Configuration settings for IntelliScope AI backend.
Provides centralized settings with environment variable override support.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    # Project Information
    PROJECT_NAME: str = "IntelliScope AI"
    PROJECT_VERSION: str = "1.0.0"
    PROJECT_DESCRIPTION: str = "Autonomous Multi-Agent Research Platform"

    # Server Configuration
    HOST: str = "0.0.0.0"
    PORT: int = 8010

    # Data Collector Agent Configuration
    WIKIPEDIA_API_URL: str = "https://en.wikipedia.org/w/api.php"
    DEFAULT_USER_AGENT: str = "IntelliScopeAI/1.0 (https://github.com/jagapathi/intelliscope-ai; contact: dev@intelliscope.ai) httpx/0.28.1"
    DEFAULT_REQUEST_TIMEOUT: float = 15.0

    # Verification Agent Configuration
    ALLOWED_SOURCE_DOMAINS: list[str] = [
        "wikipedia.org",
        "en.wikipedia.org",
    ]

    # Query Validation Constraints
    MIN_QUERY_LENGTH: int = 1
    MAX_QUERY_LENGTH: int = 300
    MIN_RESULTS_LIMIT: int = 1
    MAX_RESULTS_LIMIT: int = 10
    DEFAULT_RESULTS_LIMIT: int = 5

    # Page Extract and Snippet Constraints
    DEFAULT_SNIPPET_LENGTH: int = 500
    MAX_SNIPPET_LENGTH: int = 1000
    ENABLE_PAGE_EXTRACTS: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()

