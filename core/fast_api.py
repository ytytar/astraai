from google.adk.cli.fast_api import get_fast_api_app
from google.adk.cli.adk_web_server import AdkWebServer
from google.adk.cli.utils.agent_loader import AgentLoader

from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService
from google.adk.auth.credential_service.in_memory_credential_service import InMemoryCredentialService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService

from google.adk.evaluation.local_eval_set_results_manager import LocalEvalSetResultsManager
from google.adk.evaluation.local_eval_sets_manager import LocalEvalSetsManager

from fastapi import FastAPI
from typing import Dict, Any

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.tool_creation.tool_registry import ToolRegistry
from core.agent_utils import create_agent
from core.config_utils import load_config

import json

agents_schema_cache = {}


class YamlAgentLoader(AgentLoader):
    def load_agent(self, agent_name: str):
        with open(os.path.join(self.agents_dir, f"{agent_name}.yaml"), "r") as f:
            tool_registry = ToolRegistry()
            config_path = os.path.join(self.agents_dir, f"{agent_name}.yaml")

            tool_registry.load_from_config(str(config_path))

            config = load_config(str(config_path))
            agents_schema_cache[agent_name] = config.get("root_agent")

            return create_agent(config.get("root_agent"), tool_registry) 

    def list_agents(self):
        for file in os.listdir(self.agents_dir):
            if file.endswith(".yaml") and not file.startswith("config.example"):
                yield file.replace(".yaml", "")

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
    
    @app.get(
        "/apps/{app_name}/config",
    )
    async def get_config(app_name: str) -> Dict[str, Any]:
      """Lists all eval sets for the given app."""
      print(agents_schema_cache)
      return agents_schema_cache.get(app_name, {})

    # TODO: Add file observer for agents directory to reload the app when a new agent is added
    
    return app