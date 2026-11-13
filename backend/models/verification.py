"""
Pydantic models for the Research Verification Agent.
Defines request, response, per-item check results, and summary report schemas.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class VerificationRequest(BaseModel):
    """
    Request model for research verification.
    Accepts structured output directly from the Data Collector Agent or raw research dicts.
    """
    query: str = Field(
        default="",
        max_length=300,
        description="Search query string associated with the research results"
    )
    agent: Optional[str] = Field(
        default=None,
        description="Originating data collection agent name"
    )
    agent_name: Optional[str] = Field(
        default=None,
        description="Canonical agent name"
    )
    result_count: Optional[int] = Field(
        default=None,
        description="Reported result count from data collection"
    )
    total_results: Optional[int] = Field(
        default=None,
        description="Reported total results from data collection"
    )
    retrieved_at: Optional[str] = Field(
        default=None,
        description="Timestamp when research was collected"
    )
    results: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of raw or structured result objects to verify"
    )


class VerificationItemChecks(BaseModel):
    """
    Individual boolean flags for each automated verification check on a result item.
    """
    title_valid: bool = Field(..., description="Whether title is present, a string, and non-empty")
    snippet_valid: bool = Field(..., description="Whether snippet is present, a string, and non-empty")
    https_valid: bool = Field(..., description="Whether source URL uses secure HTTPS protocol")
    domain_allowed: bool = Field(..., description="Whether domain is in the allowed sources whitelist")
    timestamp_valid: bool = Field(..., description="Whether retrieval timestamp is valid ISO 8601")
    is_duplicate_url: bool = Field(..., description="Whether source URL is a duplicate within the batch")
    is_duplicate_title: bool = Field(..., description="Whether title is a duplicate within the batch")
    doi_valid: Optional[bool] = Field(
        default=None,
        description="Whether DOI matches standard syntax when provided (None if not provided)"
    )
    is_duplicate_doi: bool = Field(
        default=False,
        description="Whether DOI is a duplicate within the batch"
    )


class VerificationItemReport(BaseModel):
    """
    Detailed verification breakdown for a single research result item.
    """
    index: int = Field(..., description="Zero-based index of the result item in the batch")
    title: Optional[str] = Field(default=None, description="Title of the article, if available")
    source_name: str = Field(default="wikipedia", description="Normalized source provider name")
    source_url: Optional[str] = Field(default=None, description="Source URL, if available")
    doi: Optional[str] = Field(default=None, description="DOI identifier evaluated, if present")
    status: str = Field(..., description="Item verification status: 'valid', 'warning', or 'invalid'")
    item_score: float = Field(..., ge=0.0, le=100.0, description="Calculated quality score for this item (0 to 100)")
    is_weakly_relevant: bool = Field(default=False, description="Whether the item was identified as weakly relevant to the query")
    relevance_reason: Optional[str] = Field(default=None, description="Explanation of relevance status")
    checks: VerificationItemChecks = Field(..., description="Detailed boolean check breakdown")
    errors: List[str] = Field(default_factory=list, description="Errors detected during verification")
    warnings: List[str] = Field(default_factory=list, description="Warnings or minor defects detected")


class VerificationSummary(BaseModel):
    """
    Aggregate counts and statistics across all evaluated research items.
    """
    total_checks: int = Field(..., description="Total individual checks evaluated across all items")
    passed_checks: int = Field(..., description="Count of individual checks that passed")
    failed_checks: int = Field(..., description="Count of individual checks that failed")
    warning_count: int = Field(..., description="Total count of warnings generated")
    error_count: int = Field(..., description="Total count of errors generated")
    duplicate_urls_count: int = Field(..., description="Number of duplicate source URLs found")
    duplicate_titles_count: int = Field(..., description="Number of duplicate titles found")
    duplicate_dois_count: int = Field(default=0, description="Number of duplicate DOIs found")
    structurally_valid_count: int = Field(default=0, description="Count of items meeting structural integrity requirements")
    directly_relevant_count: int = Field(default=0, description="Count of items assessed as directly relevant to query")
    weakly_relevant_count: int = Field(default=0, description="Count of items assessed as weakly relevant to query")
    excluded_count: int = Field(default=0, description="Count of items excluded from further analysis")


class VerificationResponse(BaseModel):
    """
    Complete structured verification report produced by the Research Verification Agent.
    """
    agent: str = Field(
        default="Research Verification Agent",
        description="Name of the agent responsible for verification"
    )
    agent_name: str = Field(
        default="Research Verification Agent",
        description="Canonical agent name identifier"
    )
    query: str = Field(..., description="The query that was executed")
    verified_at: str = Field(..., description="ISO 8601 UTC timestamp of verification execution")
    total_results: int = Field(..., description="Total number of items evaluated")
    valid_results_count: int = Field(..., description="Count of completely valid items (no errors)")
    invalid_results_count: int = Field(..., description="Count of items with one or more errors")
    structurally_valid_count: int = Field(default=0, description="Count of items meeting structural integrity requirements")
    directly_relevant_count: int = Field(default=0, description="Count of items assessed as directly relevant to query")
    weakly_relevant_count: int = Field(default=0, description="Count of items assessed as weakly relevant to query")
    excluded_count: int = Field(default=0, description="Count of items excluded due to structural failure")
    quality_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Overall quality score (0 to 100) based on transparent criteria"
    )
    status: str = Field(
        ...,
        description="Overall batch status: 'passed', 'passed_with_warnings', or 'failed'"
    )
    verification_type: str = Field(
        default="structural_and_source_integrity",
        description="Verification scope category"
    )
    is_factually_verified: bool = Field(
        default=False,
        description="Explicit flag confirming that factual accuracy is NOT claimed"
    )
    factual_accuracy_disclaimer: str = Field(
        default=(
            "This verification evaluates structural integrity, URL protocol compliance, "
            "domain whitelist adherence, timestamp validity, and deduplication. "
            "It does NOT assert that the factual claims within snippets are verified facts."
        ),
        description="Mandatory disclaimer distinguishing structural integrity from factual accuracy"
    )
    summary: VerificationSummary = Field(..., description="Aggregate verification statistics")
    results: List[VerificationItemReport] = Field(
        default_factory=list,
        description="Per-result detailed verification reports"
    )

