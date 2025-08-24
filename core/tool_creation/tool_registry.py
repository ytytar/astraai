"""Simple plugin registry with dependency injection for AI agent tools."""

import yaml
import importlib
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

from core.tool_creation.tool_factories import BaseToolFactory
from core.config_utils import load_config_with_env
from google.adk.tools import BaseTool


logger = logging.getLogger(__name__)


class ToolRegistry:
    """Simple plugin registry that loads tools from YAML configuration."""
    
    def __init__(self):
        self._tools: Dict[str, BaseToolFactory] = {}
        self._config: Dict[str, Any] = {}
    
    def load_from_config(self, config_path: str) -> None:
        """Load tools from YAML configuration file with environment variable resolution."""
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        # Load configuration with environment variable resolution
        self._config = load_config_with_env(str(config_file))
        
        tools_config = self._config.get('tools', {})
        
        for tool_name, tool_config in tools_config.items():
            try:
                self._load_tool(tool_name, tool_config)
                logger.info(f"Successfully loaded tool: {tool_name}")
            except Exception as e:
                logger.error(f"Failed to load tool '{tool_name}': {e}")
                raise
    
    def _load_tool(self, tool_name: str, tool_config: Dict[str, Any]) -> None:
        """Load a single tool from configuration."""
        class_path = tool_config['class']
        config = tool_config.get('config', {})
        enabled = tool_config.get('enabled', True)
        
        if not enabled:
            logger.info(f"Tool '{tool_name}' is disabled, skipping...")
            return
        
        # Import the tool class
        tool_class = self._import_class(class_path)
        
        # Create tool instance with dependency injection
        tool_factory = tool_class(
            name=tool_name,
            description=tool_config.get('description', ''),
            **config
        )

        # Validate it's a proper tool
        if not isinstance(tool_factory, BaseToolFactory):
            raise TypeError(f"Tool class {class_path} must inherit from BaseToolFactory")

        self._tools[tool_name] = tool_factory
    
    def _import_class(self, class_path: str):
        """Dynamically import a class from a string path."""
        try:
            module_path, class_name = class_path.rsplit('.', 1)
            module = importlib.import_module(module_path)
            return getattr(module, class_name)
        except (ValueError, ImportError, AttributeError) as e:
            raise ImportError(f"Could not import class '{class_path}': {e}")

    def get_tool(self, tool_name: str) -> Optional[BaseToolFactory]:
        """Get a tool by name."""
        return self._tools.get(tool_name)

    def get_all_available_tools(self) -> Dict[str, BaseToolFactory]:
        """Get all loaded tools."""
        return self._tools.copy()
    
    def list_tool_names(self) -> List[str]:
        """Get list of all tool names."""
        return list(self._tools.keys())
    
    def has_tool(self, tool_name: str) -> bool:
        """Check if a tool is registered."""
        return tool_name in self._tools
    
    def get_tool_schema(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Get the schema for a specific tool."""
        tool = self.get_tool(tool_name)
        return tool.get_schema() if tool else None
    
    def get_all_schemas(self) -> Dict[str, Dict[str, Any]]:
        """Get schemas for all tools."""
        return {
            name: tool.get_schema() 
            for name, tool in self._tools.items()
        }
        
    
    def reload_config(self, config_path: str) -> None:
        """Reload configuration and tools with environment variable resolution."""
        self._tools.clear()
        self.load_from_config(config_path)
        logger.info("Plugin registry reloaded successfully")
