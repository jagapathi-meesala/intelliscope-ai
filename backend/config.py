"""
Configuration settings for IntelliScope AI backend.
Provides centralized settings with environment variable override support.
"""

from typing import Dict, List, Optional
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
    CORS_ALLOWED_ORIGINS: str = "*"

    # History Storage Configuration
    HISTORY_STORAGE_PATH: Optional[str] = None

    # Data Collector Agent Configuration
    WIKIPEDIA_API_URL: str = "https://en.wikipedia.org/w/api.php"
    ARXIV_API_URL: str = "https://export.arxiv.org/api/query"
    CROSSREF_API_URL: str = "https://api.crossref.org/works"
    DEFAULT_USER_AGENT: str = "IntelliScopeAI/1.0 (https://github.com/jagapathi/intelliscope-ai; mailto:dev@intelliscope.ai) httpx/0.28.1"
    DEFAULT_REQUEST_TIMEOUT: float = 15.0
    SUPPORTED_RESEARCH_SOURCES: List[str] = ["wikipedia", "arxiv", "crossref"]
    DEFAULT_RESEARCH_SOURCES: List[str] = ["wikipedia"]

    # Pipeline Orchestration & Interoperability Constraints
    PIPELINE_STEP_TIMEOUT_SECONDS: float = 30.0
    INTEGRATION_DEFAULT_TIMEOUT_SECONDS: float = 15.0
    INTEGRATION_MAX_RETRIES: int = 1

    # Sponsor Platform Configuration (Environment-driven, no secrets in code)
    BAND_REST_URL: str = "https://app.band.ai"
    BAND_WS_URL: str = "wss://app.band.ai/api/v1/socket/websocket"
    BAND_AGENT_ID: Optional[str] = None
    BAND_API_KEY: Optional[str] = None
    BAND_USER_API_KEY: Optional[str] = None
    BAND_CONFIG_PATH: str = "agent_config.yaml"

    LYZR_API_KEY: Optional[str] = None
    LYZR_AGENT_ID: Optional[str] = None
    LYZR_WORKFLOW_ID: Optional[str] = None
    LYZR_ENABLE_PIPELINE_DELEGATION: bool = False
    LYZR_BASE_URL: str = "https://agent-prod.studio.lyzr.ai/v3"
    LYZR_USER_ID: str = "intelliscope-orchestrator"

    AGENT37_API_KEY: Optional[str] = None
    AGENT37_INSTANCE_ID: Optional[str] = None
    AGENT37_API_URL: str = "https://api.agent37.com"
    AGENT37_SANDBOX_URL: str = "https://sandbox.agent37.app"

    ADAL_ENABLED: bool = False
    ADAL_CLI_PATH: Optional[str] = None

    FINCH_ENABLED: bool = False
    FINCH_MCP_URL: Optional[str] = None

    # Verification Agent Configuration
    ALLOWED_SOURCE_DOMAINS: List[str] = [
        "wikipedia.org",
        "en.wikipedia.org",
    ]
    SOURCE_ALLOWED_DOMAINS: Dict[str, List[str]] = {
        "wikipedia": ["wikipedia.org", "en.wikipedia.org"],
        "arxiv": ["arxiv.org", "export.arxiv.org"],
        "crossref": ["doi.org", "dx.doi.org", "crossref.org", "api.crossref.org"],
    }

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

