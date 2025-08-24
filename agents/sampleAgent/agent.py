import json
from google.adk.agents import Agent
import os
from pathlib import Path

from core.tool_creation.tool_registry import ToolRegistry
from core.agent_utils import create_agent
from core.config_utils import load_config


tool_registry = ToolRegistry()
# Get the directory where this file is located
current_dir = Path(__file__).parent
config_path = current_dir / "config.yaml"

tool_registry.load_from_config(str(config_path))

config = load_config(str(config_path))

print(json.dumps(config, indent=2))


root_agent = create_agent(config.get("root_agent"), tool_registry)