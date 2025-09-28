from google.adk.cli.fast_api import get_fast_api_app
from google.adk.cli.adk_web_server import AdkWebServer
from google.adk.cli.utils.agent_loader import AgentLoader

from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService
from google.adk.auth.credential_service.in_memory_credential_service import InMemoryCredentialService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService

from google.adk.evaluation.local_eval_set_results_manager import LocalEvalSetResultsManager
from google.adk.evaluation.local_eval_sets_manager import LocalEvalSetsManager

from fastapi import FastAPI, HTTPException, Request, Response
from typing import Dict, Any

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.tool_creation.tool_registry import ToolRegistry
from core.agent_utils import create_agent
from core.config_utils import load_config, load_from_file, resolve_env_variables
from core.api_backup import enhance_app_with_backup_endpoints, create_backup_before_update
from core.api_tools import enhance_app_with_tool_schema_endpoints

import json
import yaml

agents_schema_cache = {}


class YamlAgentLoader(AgentLoader):
    def load_agent(self, agent_name: str):
        with open(os.path.join(self.agents_dir, f"{agent_name}.yaml"), "r") as f:
            tool_registry = ToolRegistry()
            config_path = os.path.join(self.agents_dir, f"{agent_name}.yaml")

            tool_registry.load_from_config(str(config_path))

            config = load_from_file(str(config_path))
            agents_schema_cache[agent_name] = {
                "tools": config.get("tools", []),
                "root_agent": config.get("root_agent", {})
            }
            config = resolve_env_variables(config)

            return create_agent(config.get("root_agent"), tool_registry) 

    def list_agents(self):
        for file in os.listdir(self.agents_dir):
            if file.endswith(".yaml") and not file.startswith("config.example"):
                yield file.replace(".yaml", "")


def enhance_default_fast_api_app(app: FastAPI, agent_loader: AgentLoader) -> FastAPI:
    @app.get(
        "/version",
        tags=["system"],
        summary="Get application version"
    )
    async def get_version() -> Dict[str, Any]:
      """Get application version information."""
      return {
        "app": "astraAI",
        "version": "1.0.0"
        }

    @app.get(
        "/agents",
        tags=["agents"],
        summary="List all agents"
    )
    async def get_agents() -> Dict[str, Any]:
      """List all available agent configurations."""
      # Convert generator to list, then create dict with agents
      agents_list = list(agent_loader.list_agents())
      return {
          "agents": agents_list,
          "count": len(agents_list)
      }

    @app.post(
        "/agents",
        tags=["agents"],
        summary="Create new agent"
    )
    async def create_agent(request: Request) -> Dict[str, Any]:
      """Create a new agent configuration."""
      # Convert generator to list, then create dict with agents
      config = await request.json()
      agent_name = config.get("root_agent", {}).get("name", None)
      if agent_name is None:
        raise HTTPException(status_code=400, detail="Agent name is required")
      
      agents_list = list(agent_loader.list_agents())
    
      if agent_name in agents_list:
        raise HTTPException(status_code=400, detail="Agent already exists")

      with open(os.path.join(agent_loader.agents_dir, f"{agent_name}.yaml"), "w") as f:
        yaml.dump(config, f)
      
      return {
          "message": f"Agent {agent_name} created successfully",
          "agent_name": agent_name,
          "status": "success"
      }

    @app.put(
        "/agents/{agent_name}",
        tags=["agents"],
        summary="Update agent configuration"
    )
    async def update_agent(agent_name: str, request: Request) -> Dict[str, Any]:
      """Update an existing agent configuration with automatic backup."""
      agents_list = list(agent_loader.list_agents())
    
      if agent_name not in agents_list:
        raise HTTPException(status_code=404, detail="Agent not found")

      # Create backup before updating
      backup_path = create_backup_before_update(agent_name, agent_loader, "update")

      try:
        config = await request.json()
        with open(os.path.join(agent_loader.agents_dir, f"{agent_name}.yaml"), "w") as f:
          yaml.dump(config, f)
        
        # Clear cache to force reload
        if agent_name in agents_schema_cache:
          del agents_schema_cache[agent_name]
        
        return {
          "message": f"Agent {agent_name} updated successfully",
          "backup_created": backup_path,
          "agent_name": agent_name,
          "status": "success"
        }
      except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update agent: {str(e)}")
    
    @app.get(
        "/agents/{agent_name}",
        tags=["agents"],
        summary="Get agent configuration"
    )
    async def get_agent(agent_name: str) -> Dict[str, Any]:
        """Get agent configuration."""
        schema = agents_schema_cache.get(agent_name, None)
        if schema is None:
            agent_loader.load_agent(agent_name)
            schema = agents_schema_cache.get(agent_name, None)
        if schema is None:
            raise HTTPException(status_code=404, detail="Agent not found")
        return agents_schema_cache.get(agent_name, {})

    # Enhance app with backup endpoints
    app = enhance_app_with_backup_endpoints(app, agent_loader)
    
    # Enhance app with tool schema endpoints
    app = enhance_app_with_tool_schema_endpoints(app)
    
    return app

def get_fast_api_app() -> FastAPI:
    agents_dir = "./agents"
    agent_loader = YamlAgentLoader(agents_dir)

    session_service = InMemorySessionService()
    artifact_service = InMemoryArtifactService()
    credential_service = InMemoryCredentialService()
    memory_service = InMemoryMemoryService()
    eval_set_results_manager = LocalEvalSetResultsManager(agents_dir=agents_dir)
    eval_sets_manager = LocalEvalSetsManager(agents_dir=agents_dir)


    adk_web_server = AdkWebServer(
        agent_loader=agent_loader,
        session_service=session_service,
        artifact_service=artifact_service,
        memory_service=memory_service,
        credential_service=credential_service,
        agents_dir=agents_dir,
        eval_set_results_manager=eval_set_results_manager,
        eval_sets_manager=eval_sets_manager
    )

    app = adk_web_server.get_fast_api_app(allow_origins="*")

    return enhance_default_fast_api_app(app, agent_loader)
