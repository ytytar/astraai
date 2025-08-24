from core.tool_creation.tool_factories import BaseToolFactory
from google.adk.tools import MCPToolset
from google.adk.tools.mcp_tool.mcp_toolset import StreamableHTTPConnectionParams


class RemoteMCPTools(BaseToolFactory):
    """Base class for MCP tools."""
    def __init__(self, name: str, description: str, **config):
        super().__init__(name, description, **config)

    def create_instance(self):
        return MCPToolset(
    connection_params=StreamableHTTPConnectionParams(
        url=self.config.get('url', ''),
        headers={"Authorization": f"Bearer {self.config.get('api_key', '')}"}
    ),
    tool_filter=self.config.get('tools_filter', [])
)