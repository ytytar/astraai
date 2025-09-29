"""Example tools for AI agents."""

from typing import Dict, Any, List
from pydantic import BaseModel, Field

from core.tool_creation.tool_factories import BaseFunctionToolFactory
from core.tool_creation.models import ToolParam


class FileReaderConfig(BaseModel):
    """Configuration for file reader tool."""
    allowed_extensions: List[str] = Field(
        default=[".txt", ".md"],
        description="List of allowed file extensions"
    )
    max_size_mb: float = Field(
        default=2.0,
        ge=0.1,
        le=100.0,
        description="Maximum file size in MB"
    )
    allowed_directories: List[str] = Field(
        default=["."],
        description="List of allowed directory paths that files can be read from. Paths are resolved and checked for containment."
    )
    allow_subdirectories: bool = Field(
        default=True,
        description="Whether to allow reading files from subdirectories of allowed directories"
    )

    # LLM callable parameters definition
    params: List[ToolParam] = Field(
        default=[
            ToolParam(
                name="path",
                type="string",
                description="Path to the file to read",
                required=True
            ),
            ToolParam(
                name="encoding",
                type="string",
                description="File encoding",
                default="utf-8",
                required=False
            )
        ],
        description="Parameters that the LLM can use when calling this tool"
    )

class FileReaderTool(BaseFunctionToolFactory):
    """Tool for reading files."""

    # Static Pydantic data model for this tool
    data_model = FileReaderConfig

    def __init__(self, name: str, description: str, **config):
        super().__init__(name, description, **config)
        # Validate configuration using the static data model
        self.tool_config = self.data_model(**config)

    async def _execute(self, params) -> Any:
        """Read file content."""
        allowed_extensions = self.tool_config.allowed_extensions
        max_size_mb = self.tool_config.max_size_mb
        allowed_directories = self.tool_config.allowed_directories
        allow_subdirectories = self.tool_config.allow_subdirectories

        try:
            from pathlib import Path
            import os

            file_path = params.get("path")
            encoding = params.get("encoding", "utf-8")

            print(f"Reading file: {params}")

            file_path_obj = Path(file_path).resolve()  # Resolve to absolute path

            # Security checks
            if not file_path_obj.exists():
                return {"error": f"File not found: {file_path}"}

            if not file_path_obj.is_file():
                return {"error": f"Path is not a file: {file_path}"}

            # Directory access control - prevent path traversal attacks
            allowed = False
            resolved_file_path = str(file_path_obj)

            for allowed_dir in allowed_directories:
                allowed_dir_path = Path(allowed_dir).resolve()

                # Additional security: ensure allowed directory exists
                if not allowed_dir_path.exists():
                    print(f"Warning: Allowed directory does not exist: {allowed_dir_path}")
                    continue

                if allow_subdirectories:
                    # Check if file is within allowed directory or its subdirectories
                    # This prevents path traversal attacks like /opt/data/../../root/file.txt
                    try:
                        relative_path = file_path_obj.relative_to(allowed_dir_path)
                        # Additional check: ensure no upward traversal in the relative path
                        if '..' not in str(relative_path):
                            allowed = True
                            print(f"File access granted: {resolved_file_path} is within {allowed_dir_path}")
                            break
                    except ValueError:
                        # Not within this allowed directory
                        continue
                else:
                    # Check if file is directly in allowed directory (no subdirectories)
                    if file_path_obj.parent == allowed_dir_path:
                        allowed = True
                        print(f"File access granted: {resolved_file_path} is directly in {allowed_dir_path}")
                        break

            if not allowed:
                allowed_dirs_str = ", ".join([str(Path(d).resolve()) for d in allowed_directories])
                subdir_msg = " or their subdirectories" if allow_subdirectories else ""
                print(f"File access denied: {resolved_file_path} not in allowed directories")
                return {"error": f"File access denied. File must be within allowed directories: {allowed_dirs_str}{subdir_msg}. Resolved path: {resolved_file_path}"}

            if file_path_obj.suffix.lower() not in allowed_extensions:
                return {"error": f"File extension not allowed: {file_path_obj.suffix}. The following extensions are allowed: {allowed_extensions}"}

            file_size_mb = file_path_obj.stat().st_size / (1024 * 1024)
            if file_size_mb > max_size_mb:
                return {"error": f"File too large: {file_size_mb:.2f}MB > {max_size_mb}MB"}

            # Read file
            with open(file_path_obj, 'r', encoding=encoding) as f:
                content = f.read()

            return {
                "file_path": str(file_path_obj),
                "size_bytes": file_path_obj.stat().st_size,
                "encoding": encoding,
                "content": content
            }
        except Exception as e:
            return {"error": str(e)}

    @classmethod
    def schema(cls) -> Dict[str, Any]:
        """Return the full configuration schema matching YAML structure."""
        return cls.data_model.model_json_schema()

    def get_config_schema(self) -> Dict[str, Any]:
        """Get the configuration schema for this tool instance."""
        return self.tool_config.model_dump()

    def get_llm_params(self) -> List[Dict[str, Any]]:
        """Get the parameters that LLM can use when calling this tool."""
        return [param.model_dump() for param in self.tool_config.params]

    def get_schema(self) -> Dict[str, Any]:
        """Legacy method for backward compatibility."""
        # Generate schema from the params for LLM usage
        properties = {}
        required = []

        for param in self.tool_config.params:
            prop_def = {
                "type": param.type,
                "description": param.description
            }
            if param.default is not None:
                prop_def["default"] = param.default

            properties[param.name] = prop_def

            if param.required:
                required.append(param.name)

        return {
            "type": "object",
            "properties": properties,
            "required": required
        }

    @classmethod
    def validate_config(cls, config: Dict[str, Any]) -> FileReaderConfig:
        """Validate and return typed configuration."""
        return cls.data_model(**config)


class DirectoryListTool(BaseFunctionToolFactory):
    """Tool for listing files and folders in a directory."""
    
    async def _execute(self, params) -> Any:
        """List directory contents with safety limit and filtering."""
        max_items = self.config.get("max_items", 100)  # Default max items is 100
        root_path = self.config.get("root_path", ".")  # Default to current directory
        
        # Filter configuration
        allowed_extensions = self.config.get("allowed_extensions", None)  # None means allow all
        excluded_patterns = self.config.get("excluded_patterns", [])  # Patterns to exclude
        show_hidden = self.config.get("show_hidden", False)  # Show hidden files/folders
        
        # Runtime filter parameters
        filter_type = params.get("filter_type", "all")  # "all", "files", "directories"
        name_pattern = params.get("name_pattern", None)  # Pattern to match names

        try:
            from pathlib import Path
            import os
            import fnmatch
            import re

            # Use provided path or fall back to configured root path
            directory_path = params.get("path", root_path)
            
            print(f"Listing directory: {params}")

            dir_path_obj = Path(directory_path)
            
            # Security checks
            if not dir_path_obj.exists():
                return {"error": f"Directory not found: {directory_path}"}
            
            if not dir_path_obj.is_dir():
                return {"error": f"Path is not a directory: {directory_path}"}

            # Helper function to check if item should be filtered
            def should_include_item(item_path):
                item_name = item_path.name
                
                # Check hidden files
                if not show_hidden and item_name.startswith('.'):
                    return False
                
                # Check excluded patterns
                for pattern in excluded_patterns:
                    if fnmatch.fnmatch(item_name, pattern):
                        return False
                
                # Check name pattern if provided
                if name_pattern:
                    if not fnmatch.fnmatch(item_name.lower(), name_pattern.lower()):
                        return False
                
                # Check file extension filter
                if item_path.is_file() and allowed_extensions:
                    if item_path.suffix.lower() not in [ext.lower() for ext in allowed_extensions]:
                        return False
                
                # Check filter type
                if filter_type == "files" and not item_path.is_file():
                    return False
                elif filter_type == "directories" and not item_path.is_dir():
                    return False
                
                return True

            # List directory contents
            items = []
            item_count = 0
            total_items_scanned = 0
            
            try:
                for item in dir_path_obj.iterdir():
                    total_items_scanned += 1
                    
                    if not should_include_item(item):
                        continue
                    
                    if item_count >= max_items:
                        break
                    
                    item_info = {
                        "name": item.name,
                        "path": str(item),
                        "is_directory": item.is_dir(),
                        "is_file": item.is_file()
                    }
                    
                    # Add size info for files
                    if item.is_file():
                        try:
                            item_info["size_bytes"] = item.stat().st_size
                            item_info["extension"] = item.suffix.lower()
                        except (OSError, PermissionError):
                            item_info["size_bytes"] = None
                            item_info["extension"] = item.suffix.lower()
                    
                    items.append(item_info)
                    item_count += 1
                
                # Sort items: directories first, then files, both alphabetically
                items.sort(key=lambda x: (not x["is_directory"], x["name"].lower()))
                
                return {
                    "directory_path": str(dir_path_obj.absolute()),
                    "total_items_scanned": total_items_scanned,
                    "total_items_found": item_count,
                    "max_items_limit": max_items,
                    "truncated": item_count >= max_items,
                    "filter_applied": {
                        "filter_type": filter_type,
                        "name_pattern": name_pattern,
                        "allowed_extensions": allowed_extensions,
                        "excluded_patterns": excluded_patterns,
                        "show_hidden": show_hidden
                    },
                    "items": items
                }
                
            except PermissionError:
                return {"error": f"Permission denied accessing directory: {directory_path}"}
                
        except Exception as e:
            return {"error": str(e)}

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the directory to list (optional, uses configured root_path if not provided)"
                },
                "filter_type": {
                    "type": "string",
                    "description": "Filter by item type: 'all', 'files', or 'directories'",
                    "enum": ["all", "files", "directories"],
                    "default": "all"
                },
                "name_pattern": {
                    "type": "string",
                    "description": "Pattern to match file/folder names (supports wildcards like *.txt)"
                }
            },
            "required": []
        }
