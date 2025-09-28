"""API tools for exposing tool schemas via FastAPI endpoints."""

from typing import Dict, Any
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import importlib
import os

import logging

logger = logging.getLogger(__name__)


class ToolSchemaRequest(BaseModel):
    """Request model for getting tool schema by class name."""
    class_name: str


class ToolTestRequest(BaseModel):
    """Request model for testing a tool execution."""
    tool_config: Dict[str, Any]  # Full tool configuration including class and config
    params: Dict[str, Any] = {}


def enhance_app_with_tool_schema_endpoints(app: FastAPI) -> FastAPI:
    """Enhance FastAPI app with tool schema endpoints."""
    
    def _import_tool_class(class_path: str):
        """Dynamically import a tool class from a string path."""
        try:
            module_path, class_name = class_path.rsplit('.', 1)
            module = importlib.import_module(module_path)
            return getattr(module, class_name)
        except (ValueError, ImportError, AttributeError) as e:
            raise ImportError(f"Could not import class '{class_path}': {e}")
    
    @app.post(
        "/tools/schema",
        tags=["tools", "schemas"],
        summary="Get tool schema by class name"
    )
    async def get_tool_schema_by_class(request: ToolSchemaRequest) -> Dict[str, Any]:
        """Get tool schema by providing the class name (e.g., 'tools.semantic_search.SemanticSearchTool')."""
        try:
            # Import the tool class
            tool_class = _import_tool_class(request.class_name)
            
            # Check if the class has a schema method or data_model
            if hasattr(tool_class, 'data_model'):
                # Use the static data_model if available
                schema = tool_class.data_model.model_json_schema()
                data_model_info = {
                    "data_model": tool_class.data_model.__name__,
                    "data_model_module": tool_class.data_model.__module__
                }
            elif hasattr(tool_class, 'schema'):
                # Fallback to schema method
                schema = tool_class.schema()
                data_model_info = {}
            else:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Tool class '{request.class_name}' does not implement schema() method or data_model attribute"
                )
            
            return {
                "class_name": request.class_name,
                "tool_class": tool_class.__name__,
                "module": tool_class.__module__,
                "schema": schema,
                **data_model_info
            }
                
        except ImportError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get tool schema: {str(e)}")

    @app.get(
        "/tools/schema/{class_path:path}",
        tags=["tools", "schemas"],
        summary="Get tool schema by class path (GET version)"
    )
    async def get_tool_schema_by_class_path(class_path: str) -> Dict[str, Any]:
        """Get tool schema by providing the class path in URL (e.g., tools.semantic_search.SemanticSearchTool)."""
        try:
            # Import the tool class
            tool_class = _import_tool_class(class_path)
            
            # Check if the class has a schema method or data_model
            if hasattr(tool_class, 'data_model'):
                # Use the static data_model if available
                schema = tool_class.data_model.model_json_schema()
                data_model_info = {
                    "data_model": tool_class.data_model.__name__,
                    "data_model_module": tool_class.data_model.__module__
                }
            elif hasattr(tool_class, 'schema'):
                # Fallback to schema method
                schema = tool_class.schema()
                data_model_info = {}
            else:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Tool class '{class_path}' does not implement schema() method or data_model attribute"
                )
            
            return {
                "class_name": class_path,
                "tool_class": tool_class.__name__,
                "module": tool_class.__module__,
                "schema": schema,
                **data_model_info
            }
                
        except ImportError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get tool schema: {str(e)}")

    @app.get(
        "/tools/available",
        tags=["tools"],
        summary="List available tool classes"
    )
    async def list_available_tool_classes() -> Dict[str, Any]:
        """List all available tool classes that can be imported."""
        try:
            # Common tool modules to check
            tool_modules = [
                "tools.semantic_search",
                "tools.file_tools", 
                "tools.rally_tools",
                "tools.oracle_tools",
                "tools.terminal_tools"
            ]
            
            available_tools = {}
            
            for module_name in tool_modules:
                try:
                    module = importlib.import_module(module_name)
                    
                    # Find classes that have schema method
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (isinstance(attr, type) and 
                            (hasattr(attr, 'schema') or hasattr(attr, 'data_model')) and 
                            attr_name.endswith('Tool')):
                            
                            class_path = f"{module_name}.{attr_name}"
                            available_tools[class_path] = {
                                "class_name": attr_name,
                                "module": module_name,
                                "has_schema": hasattr(attr, 'data_model') and attr.data_model is not None,
                                "data_model_name": attr.data_model.__name__ if hasattr(attr, 'data_model') and attr.data_model is not None else None
                            }
                            
                except ImportError:
                    # Skip modules that can't be imported
                    continue
            
            return {
                "available_tools": available_tools,
                "total_count": len(available_tools)
            }
                
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to list available tools: {str(e)}")

    @app.post(
        "/tools/test",
        tags=["tools", "testing"],
        summary="Test tool execution"
    )
    async def test_tool_execution(request: ToolTestRequest) -> Dict[str, Any]:
        """Test a tool by creating it from configuration and executing it with provided parameters."""
        
        try:
            # Extract tool configuration
            tool_config = request.tool_config
            
            # Validate required fields in tool config
            if 'class' not in tool_config:
                raise HTTPException(status_code=400, detail="Tool configuration must include 'class' field")
            
            class_path = tool_config['class']
            config = tool_config.get('config', {})
            tool_name = tool_config.get('name', 'test_tool')
            description = tool_config.get('description', 'Test tool instance')
            enabled = tool_config.get('enabled', True)
            
            if not enabled:
                raise HTTPException(status_code=400, detail="Tool is disabled")
            
            # Import the tool class dynamically
            tool_class = _import_tool_class(class_path)
            
            # Create tool factory instance
            tool_factory = tool_class(
                name=tool_name,
                description=description,
                **config
            )
            
            # Validate it's a proper tool factory
            from core.tool_creation.tool_factories import BaseToolFactory
            if not isinstance(tool_factory, BaseToolFactory):
                raise HTTPException(
                    status_code=400, 
                    detail=f"Tool class {class_path} must inherit from BaseToolFactory"
                )
            
            # Execute the tool
            result = await tool_factory._execute(request.params)
            
            return {
                "tool_class": class_path,
                "tool_name": tool_name,
                "tool_config": tool_config,
                "params": request.params,
                "result": result,
                "status": "success"
            }
            
        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except ImportError as e:
            raise HTTPException(status_code=404, detail=f"Could not import tool class: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to execute tool: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to execute tool: {str(e)}")

    return app
