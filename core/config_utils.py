"""
Configuration utilities for handling environment variables in YAML files.
"""

import os
import re
import yaml
from typing import Any, Dict, Union
from pathlib import Path


def resolve_env_variables(data: Union[str, Dict, list]) -> Union[str, Dict, list]:
    """
    Recursively resolve environment variable placeholders in configuration data.
    
    Supports two formats:
    - ${VAR_NAME} - Required environment variable (raises error if not found)
    - ${VAR_NAME:default_value} - Optional with default value
    
    Args:
        data: Configuration data (string, dict, or list)
        
    Returns:
        Configuration data with environment variables resolved
        
    Raises:
        ValueError: If a required environment variable is not found
    """
    if isinstance(data, str):
        return _resolve_env_string(data)
    elif isinstance(data, dict):
        return {key: resolve_env_variables(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [resolve_env_variables(item) for item in data]
    else:
        return data


def _resolve_env_string(text: str) -> str:
    """
    Resolve environment variables in a string.
    
    Args:
        text: String that may contain environment variable placeholders
        
    Returns:
        String with environment variables resolved
    """
    # Pattern to match ${VAR_NAME} or ${VAR_NAME:default_value}
    pattern = r'\$\{([^}:]+)(?::([^}]*))?\}'
    
    def replace_env_var(match):
        var_name = match.group(1)
        default_value = match.group(2)
        
        env_value = os.getenv(var_name)
        
        if env_value is not None:
            return env_value
        elif default_value is not None:
            return default_value
        else:
            raise ValueError(f"Required environment variable '{var_name}' is not set")
    
    return re.sub(pattern, replace_env_var, text)


def load_from_file(file_path: str):
    with open(file_path, 'r', encoding='utf-8') as file:
        config = yaml.safe_load(file)
    
    return config

def load_config_with_env(file_path: str) -> Dict[str, Any]:
    """
    Load a YAML configuration file and resolve environment variables.
    
    Args:
        file_path: Path to the YAML configuration file
        
    Returns:
        Configuration dictionary with environment variables resolved
    """
    config = load_from_file(file_path)
    
    return resolve_env_variables(config)


def validate_required_env_vars(config: Dict[str, Any], 
                              required_vars: list = None) -> None:
    """
    Validate that all required environment variables are set.
    
    Args:
        config: Configuration dictionary
        required_vars: List of required environment variable names
    """
    if required_vars is None:
        required_vars = []
    
    missing_vars = []
    for var_name in required_vars:
        if os.getenv(var_name) is None:
            missing_vars.append(var_name)
    
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

def load_config(file_path, resolve_env_var: bool=True):
    config_file = Path(file_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {file_path}")

    # Load configuration with environment variable resolution
    if resolve_env_var:
        return load_config_with_env(str(config_file))
    return load_from_file(str(config_file))

# Example usage and testing
if __name__ == "__main__":
    # Test the environment variable resolution
    test_data = {
        "api_key": "${API_KEY}",
        "host": "${HOST:localhost}",
        "port": "${PORT:8080}",
        "nested": {
            "database_url": "${DATABASE_URL:sqlite:///default.db}",
            "debug": "${DEBUG:false}"
        }
    }
    
    # Set some test environment variables
    os.environ["API_KEY"] = "test-api-key-123"
    os.environ["PORT"] = "3000"
    
    try:
        resolved = resolve_env_variables(test_data)
        print("Resolved configuration:")
        import json
        print(json.dumps(resolved, indent=2))
    except ValueError as e:
        print(f"Error: {e}")
