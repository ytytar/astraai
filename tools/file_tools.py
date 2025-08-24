"""Example tools for AI agents."""

from typing import Dict, Any

from core.tool_creation.tool_factories import BaseFunctionToolFactory

class FileReaderTool(BaseFunctionToolFactory):
    """Tool for reading files."""
    
    async def _execute(self, params) -> Any:
        """Read file content."""
        allowed_extensions = self.config.get("allowed_extensions", [".txt", ".md"])
        max_size_mb = self.config.get("max_size_mb", 2)  # Default max size is 2MB

        try:
            from pathlib import Path

            file_path = params.get("path")
            encoding = params.get("encoding", "utf-8")

            print(f"Reading file: {params}")

            file_path_obj = Path(file_path)
            
            # Security checks
            if not file_path_obj.exists():
                return {"error": f"File not found: {file_path}"}
            
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

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to read"
                },
                "encoding": {
                    "type": "string",
                    "description": "File encoding",
                    "default": "utf-8"
                }
            },
            "required": ["file_path"]
        }


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
