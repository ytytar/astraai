from core.tool_creation.tool_factories import BaseToolFactory
from core.tool_creation.models import RemoteMCPToolsConfig
from google.adk.tools import MCPToolset
from google.adk.tools.mcp_tool.mcp_toolset import StreamableHTTPConnectionParams
from typing import Any, Dict


class RemoteMCPTools(BaseToolFactory):
    """Base class for MCP tools."""
    
    data_model = RemoteMCPToolsConfig
    
    def __init__(self, name: str, description: str, **config):
        super().__init__(name, description, **config)
        # Validate configuration using Pydantic model
        self.config = self.validate_config(config)

    def create_instance(self):
        # Use validated config for better type safety
        config = self.config
        # Build headers with authorization
        headers = {}
        if isinstance(config, RemoteMCPToolsConfig) and config.headers:
            headers = {"Authorization": f"Bearer {config.api_key}"}
            headers.update(config.headers if config.headers else {})
        elif isinstance(config, dict) and config.get('headers'):
            headers = {"Authorization": f"Bearer {config.get('api_key', '')}"}
            headers.update(config.get('headers', {}))
        
        return MCPToolset(
            connection_params=StreamableHTTPConnectionParams(
                url=str(config.get('url', '') if isinstance(config, dict) else config.url),
                headers=headers
            ),
            tool_filter=config.get('tools_filter', []) if isinstance(config, dict) else config.tools_filter
        )