"""Shared Pydantic models for tool creation system."""

from typing import Any, List, Optional, Dict
from pydantic import BaseModel, Field, HttpUrl


class ToolParam(BaseModel):
    """Individual parameter definition for LLM callable parameters."""
    name: str = Field(description="Parameter name")
    type: str = Field(description="Parameter type (string, integer, number, boolean, array, object)")
    description: str = Field(description="Parameter description")
    default: Any = Field(default=None, description="Default value (optional)")
    required: bool = Field(default=True, description="Whether parameter is required")


class RemoteMCPToolsConfig(BaseModel):
    """Configuration schema for Remote MCP Tools."""
    url: HttpUrl = Field(description="MCP server URL endpoint")
    api_key: str = Field(description="API key for authentication")
    tools_filter: Optional[List[str]] = Field(
        default_factory=list,
        description="List of specific tool names to filter/include from the MCP server"
    )
    headers: Optional[Dict[str, str]] = Field(
        default_factory=dict,
        description="Additional HTTP headers to send with requests"
    )
