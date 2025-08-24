"""Simple AI Agent that uses the plugin tool system."""

import logging

from core.tool_creation import ToolRegistry
from google.adk.agents import Agent


logger = logging.getLogger(__name__)

def _validate_agent_config(config) -> bool:
    required_keys = ["name", "description", "instruction"]
    for key in required_keys:
        if key not in config:
            logger.error(f"Missing required config key: {key}")
            return False, f'Missing required config key: {key}'

    warning_keys = ["model"]
    for key in warning_keys:
        if key not in config:
            logger.warning(f"Key {key} is not present in the config. Will use default value.")
            
    return True, ""


def create_agent(config, tools_registry: ToolRegistry) -> Agent:
    """
    Create a simple AI agent with the given configuration and tools registry.

    Args:
        config: Agent configuration dictionary.
        tools_registry: Plugin registry instance.

    Returns:
        An instance of SimpleAgent.
    """
    is_config_valid, error_message = _validate_agent_config(config)
    if not is_config_valid:
        raise ValueError(f"Invalid agent configuration: {error_message}")

    tools = []
    for tool_name in config.get("tools", []):
        tool = tools_registry.get_tool(tool_name)
        if tool:
            tools.append(tool.create_instance())
        else:
            logger.warning(f"Tool '{tool_name}' not found in registry.")

    sub_agents = []
    for sub_agent_config in config.get("sub_agents", {}).values():
        sub_agents.append(create_agent(sub_agent_config, tools_registry))

    return Agent(
        name=config["name"],
        model=config.get("model", "gemini-2.0-flash"),
        description=config.get("description", ""),
        instruction=config.get("instruction", ""),
        sub_agents=sub_agents,
        tools=tools)