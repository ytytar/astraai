"""Base tool interface for AI agent tools."""

from abc import ABC, abstractmethod
from typing import Any, Dict
import inspect

from google.adk.tools import BaseTool, FunctionTool, MCPToolset
from google.adk.tools.mcp_tool.mcp_toolset import StreamableHTTPConnectionParams



def create_function_with_signature(func_name: str, parameters: Dict[str, inspect.Parameter], 
                                  func_implementation: callable) -> callable:
    """
    Create a function with a specific signature using inspect.Parameter objects.
    
    Args:
        func_name: Name of the function
        parameters: Dict of parameter names to inspect.Parameter objects
        func_implementation: The implementation function
    
    Returns:
        Function with the specified signature
    """
    # Create signature
    sig = inspect.Signature(parameters=list(parameters.values()))
    
    # Create wrapper function
    async def dynamic_func(*args, **kwargs):
        # Bind arguments to signature
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()
        print(f"Bound arguments: {bound.arguments}")
        return await func_implementation(params=bound.arguments)
    
    # Set function attributes
    dynamic_func.__name__ = func_name
    dynamic_func.__signature__ = sig
    
    return dynamic_func


class BaseToolFactory(ABC):
    """Base class for all AI agent tools."""
    
    def __init__(self, name: str, description: str, **config):
        self.name = name
        self.description = description
        self.config = config
    
    @abstractmethod
    def create_instance(self) -> BaseTool:
        """Return the tool's parameter schema."""
        pass
    
    def validate_params(self, params: Dict[str, Any]) -> bool:
        """Validate parameters against schema. Override for custom validation."""
        # Basic implementation - can be enhanced
        return True
    
    def __str__(self):
        return f"{self.__class__.__name__}(name='{self.name}')"


class BaseFunctionToolFactory(BaseToolFactory):
    """Base class for function tools."""
    def __init__(self, name: str, description: str, **config):
        super().__init__(name, description, **config)
        
        print(f"Creating dynamic function: {name}, {config.get('params', {})}")
        
        # Convert parameter definitions to inspect.Parameter objects
        parameters = self._convert_params_to_inspect_parameters(config.get('params', []))
        
        # Generate docstring with parameter documentation
        docstring = self._generate_docstring(description, config.get('params', []))
        
        dynamic_function = create_function_with_signature(name, parameters, self._execute)
        dynamic_function.__doc__ = docstring
        setattr(self, name, dynamic_function)
    
    def _convert_params_to_inspect_parameters(self, param_defs):
        """Convert parameter definitions to inspect.Parameter objects.
        
        Args:
            param_defs: List of parameter definitions with 'name', 'type', 'description', and optional 'default'
            
        Returns:
            Dict of parameter names to inspect.Parameter objects
        """
        parameters = {}
        
        # Type mapping
        type_mapping = {
            'string': str,
            'str': str,
            'int': int,
            'integer': int,
            'float': float,
            'bool': bool,
            'boolean': bool,
            'list': list,
            'dict': dict,
            'any': Any
        }
        
        for param_def in param_defs:
            param_name = param_def['name']
            param_type = type_mapping.get(param_def.get('type', 'any'), str)
            
            # Determine if parameter has a default value
            if 'default' in param_def:
                default_value = param_def['default']
            else:
                default_value = inspect.Parameter.empty
            
            parameters[param_name] = inspect.Parameter(
                name=param_name,
                kind=inspect.Parameter.KEYWORD_ONLY,
                annotation=param_type,
                default=default_value
            )
        
        return parameters
    
    def _generate_docstring(self, description, param_defs):
        """Generate a docstring with parameter documentation.
        
        Args:
            description: Function description
            param_defs: List of parameter definitions
            
        Returns:
            Formatted docstring
        """
        docstring_parts = [description]
        
        if param_defs:
            docstring_parts.append("")
            docstring_parts.append("Args:")
            for param_def in param_defs:
                param_desc = f"    {param_def['name']} ({param_def.get('type', 'any')}): {param_def.get('description', '')}"
                if 'default' in param_def:
                    param_desc += f" Defaults to {param_def['default']}."
                docstring_parts.append(param_desc)
        
        return "\n".join(docstring_parts)
    
    def create_instance(self):
        # Get the dynamically created function by the name
        func = getattr(self, self.name)
        return FunctionTool(func)

    @abstractmethod
    async def _execute(self, params: Dict[str, Any]) -> Any:
        """Execute the tool's function."""
        pass