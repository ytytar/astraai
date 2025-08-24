import subprocess
import shlex
import re
from typing import Dict, Any, List, Optional
from pathlib import Path

from core.tool_creation.tool_factories import BaseFunctionToolFactory


class TerminalCommandTool(BaseFunctionToolFactory):
    """Tool for executing terminal commands with security restrictions."""
    
    async def _execute(self, params) -> Any:
        """Execute terminal command with safety checks."""
        # Configuration options
        allowed_commands = self.config.get("allowed_commands", [])  # List of allowed commands
        command_templates = self.config.get("command_templates", {})  # Pre-defined command templates
        fixed_command = self.config.get("command", None)  # Single fixed command template
        max_execution_time = self.config.get("max_execution_time", 30)  # Timeout in seconds
        allowed_working_dirs = self.config.get("allowed_working_dirs", [])  # Allowed working directories
        capture_output = self.config.get("capture_output", True)  # Whether to capture output
        max_output_size = self.config.get("max_output_size", 10000)  # Max characters in output
        config_working_dir = self.config.get("working_dir", None)  # Fixed working directory from config

        try:
            command = params.get("command")
            template_name = params.get("template_name")
            template_params = params.get("template_params", {})
            
            # Use config working_dir if specified, otherwise allow user to specify
            if config_working_dir:
                working_dir = config_working_dir
            else:
                working_dir = params.get("working_dir", ".")
            
            print(f"Executing command: {params}")

            # Determine the command to execute
            if fixed_command:
                # Use fixed command from config with parameter substitution
                command = self._replace_placeholders(fixed_command, template_params)
                
            elif template_name:
                # Use predefined template
                if template_name not in command_templates:
                    return {"error": f"Unknown command template: {template_name}"}
                
                command_template = command_templates[template_name]
                command = self._replace_placeholders(command_template, template_params)
                
            elif command:
                # Use direct command if allowed (only if no fixed_command is set)
                if not self._is_command_allowed(command, allowed_commands):
                    return {"error": f"Command not allowed: {command}"}
            else:
                return {"error": "Either 'command' or 'template_name' must be provided"}

            # Validate working directory
            if allowed_working_dirs and not self._is_working_dir_allowed(working_dir, allowed_working_dirs):
                return {"error": f"Working directory not allowed: {working_dir}"}

            # Validate working directory exists
            work_dir_path = Path(working_dir)
            if not work_dir_path.exists():
                return {"error": f"Working directory does not exist: {working_dir}"}
            
            if not work_dir_path.is_dir():
                return {"error": f"Working directory is not a directory: {working_dir}"}

            # Execute command
            result = await self._execute_command(
                command, 
                working_dir, 
                max_execution_time, 
                capture_output,
                max_output_size
            )
            
            return result

        except Exception as e:
            return {"error": f"Execution failed: {str(e)}"}

    def _replace_placeholders(self, template: str, params: Dict[str, Any]) -> str:
        """Replace placeholders in command template with actual values."""
        command = template
        
        # Replace placeholders like {param_name} with actual values
        for key, value in params.items():
            placeholder = f"{{{key}}}"
            if placeholder in command:
                # Escape shell special characters in the value
                escaped_value = shlex.quote(str(value))
                command = command.replace(placeholder, escaped_value)
        
        return command

    def _is_command_allowed(self, command: str, allowed_commands: List[str]) -> bool:
        """Check if a command is in the allowed list."""
        if not allowed_commands:
            return False  # If no allowed commands specified, nothing is allowed
        
        # Extract the base command (first word)
        base_command = command.split()[0] if command.split() else ""
        
        for allowed in allowed_commands:
            # Support wildcards and exact matches
            if allowed == "*":  # Allow all commands (dangerous!)
                return True
            elif allowed == base_command:  # Exact command match
                return True
            elif allowed.endswith("*") and base_command.startswith(allowed[:-1]):  # Prefix match
                return True
        
        return False

    def _is_working_dir_allowed(self, working_dir: str, allowed_dirs: List[str]) -> bool:
        """Check if working directory is allowed."""
        if not allowed_dirs:
            return True  # If no restrictions, allow all
        
        work_path = Path(working_dir).resolve()
        
        for allowed_dir in allowed_dirs:
            allowed_path = Path(allowed_dir).resolve()
            try:
                # Check if working_dir is within allowed directory
                work_path.relative_to(allowed_path)
                return True
            except ValueError:
                continue
        
        return False

    async def _execute_command(
        self, 
        command: str, 
        working_dir: str, 
        timeout: int, 
        capture_output: bool,
        max_output_size: int
    ) -> Dict[str, Any]:
        """Execute the command and return results."""
        try:
            # Use shell=True for complex commands, but be careful with security
            process = subprocess.Popen(
                command,
                shell=True,
                cwd=working_dir,
                stdout=subprocess.PIPE if capture_output else None,
                stderr=subprocess.PIPE if capture_output else None,
                text=True,
                universal_newlines=True
            )
            
            # Wait for completion with timeout
            try:
                stdout, stderr = process.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()
                return {
                    "command": command,
                    "working_dir": working_dir,
                    "return_code": -1,
                    "stdout": "",
                    "stderr": "Command timed out",
                    "error": f"Command exceeded timeout of {timeout} seconds"
                }
            
            # Truncate output if too long
            if stdout and len(stdout) > max_output_size:
                stdout = stdout[:max_output_size] + f"\n... (output truncated at {max_output_size} characters)"
            
            if stderr and len(stderr) > max_output_size:
                stderr = stderr[:max_output_size] + f"\n... (output truncated at {max_output_size} characters)"
            
            return {
                "command": command,
                "working_dir": working_dir,
                "return_code": process.returncode,
                "stdout": stdout or "",
                "stderr": stderr or "",
                "success": process.returncode == 0
            }
            
        except Exception as e:
            return {
                "command": command,
                "working_dir": working_dir,
                "return_code": -1,
                "stdout": "",
                "stderr": str(e),
                "error": f"Failed to execute command: {str(e)}"
            }

    def get_schema(self) -> Dict[str, Any]:
        # Check if working_dir is fixed in config
        config_working_dir = self.config.get("working_dir", None)
        fixed_command = self.config.get("command", None)
        
        schema = {
            "type": "object",
            "properties": {},
            "required": []
        }
        
        if fixed_command:
            # Only allow template_params when using fixed command
            schema["properties"]["template_params"] = {
                "type": "object",
                "description": "Parameters to substitute in the fixed command template",
                "additionalProperties": True
            }
        else:
            # Original schema when no fixed command
            schema["properties"].update({
                "command": {
                    "type": "string",
                    "description": "The terminal command to execute (if not using template)"
                },
                "template_name": {
                    "type": "string", 
                    "description": "Name of predefined command template to use"
                },
                "template_params": {
                    "type": "object",
                    "description": "Parameters to substitute in the command template",
                    "additionalProperties": True
                }
            })
            schema["anyOf"] = [
                {"required": ["command"]},
                {"required": ["template_name"]}
            ]
        
        # Only add working_dir to schema if not fixed in config
        if not config_working_dir:
            schema["properties"]["working_dir"] = {
                "type": "string",
                "description": "Working directory for command execution",
                "default": "."
            }
        
        return schema


class SafeTerminalTool(BaseFunctionToolFactory):
    """A more restrictive terminal tool that only allows predefined commands."""
    
    async def _execute(self, params) -> Any:
        """Execute only predefined safe commands."""
        # This tool only works with predefined command templates for maximum security
        command_templates = self.config.get("command_templates", {})
        fixed_command = self.config.get("command", None)  # Single fixed command template
        max_execution_time = self.config.get("max_execution_time", 10)
        allowed_working_dirs = self.config.get("allowed_working_dirs", ["."])
        max_output_size = self.config.get("max_output_size", 5000)
        config_working_dir = self.config.get("working_dir", None)  # Fixed working directory from config

        try:
            template_name = params.get("template_name")
            template_params = params.get("template_params", {})
            
            # Use config working_dir if specified, otherwise allow user to specify
            if config_working_dir:
                working_dir = config_working_dir
            else:
                working_dir = params.get("working_dir", ".")
            
            print(f"Executing safe command template: {params}")

            if fixed_command:
                # Use fixed command from config with parameter substitution
                command = self._replace_placeholders_safe(fixed_command, template_params)
                
            elif template_name:
                if not template_name:
                    return {"error": "template_name is required"}
                
                if template_name not in command_templates:
                    available_templates = list(command_templates.keys())
                    return {
                        "error": f"Unknown command template: {template_name}",
                        "available_templates": available_templates
                    }

                # Get command template
                command_template = command_templates[template_name]
                
                # Replace placeholders
                command = self._replace_placeholders_safe(command_template, template_params)
            else:
                return {"error": "Either fixed command must be configured or template_name must be provided"}
            
            # Validate working directory
            if not self._is_working_dir_allowed(working_dir, allowed_working_dirs):
                return {"error": f"Working directory not allowed: {working_dir}"}

            # Execute command
            terminal_tool = TerminalCommandTool(
                name="internal_terminal",
                description="Internal terminal tool",
                **self.config
            )
            
            result = await terminal_tool._execute_command(
                command,
                working_dir,
                max_execution_time,
                True,
                max_output_size
            )
            
            # Add template info to result
            if fixed_command:
                result["fixed_command"] = fixed_command
            else:
                result["template_name"] = template_name
            result["template_params"] = template_params
            
            return result

        except Exception as e:
            return {"error": f"Safe execution failed: {str(e)}"}

    def _replace_placeholders_safe(self, template: str, params: Dict[str, Any]) -> str:
        """Safely replace placeholders with validation."""
        command = template
        
        # Find all placeholders in template
        placeholders = re.findall(r'\{(\w+)\}', template)
        
        for placeholder in placeholders:
            if placeholder not in params:
                raise ValueError(f"Missing required parameter: {placeholder}")
            
            value = params[placeholder]
            
            # Basic validation - no shell injection characters
            if self._contains_dangerous_chars(str(value)):
                raise ValueError(f"Parameter '{placeholder}' contains potentially dangerous characters")
            
            # Replace placeholder
            escaped_value = shlex.quote(str(value))
            command = command.replace(f"{{{placeholder}}}", escaped_value)
        
        return command

    def _contains_dangerous_chars(self, value: str) -> bool:
        """Check if value contains potentially dangerous shell characters."""
        dangerous_chars = [';', '&', '|', '`', '$', '(', ')', '<', '>', '\\n', '\\r']
        return any(char in value for char in dangerous_chars)

    def _is_working_dir_allowed(self, working_dir: str, allowed_dirs: List[str]) -> bool:
        """Check if working directory is allowed."""
        if not allowed_dirs:
            return False  # Require explicit allowlist
        
        work_path = Path(working_dir).resolve()
        
        for allowed_dir in allowed_dirs:
            allowed_path = Path(allowed_dir).resolve()
            try:
                # Check if working_dir is within allowed directory
                work_path.relative_to(allowed_path)
                return True
            except ValueError:
                continue
        
        return False

    def get_schema(self) -> Dict[str, Any]:
        # Check if working_dir is fixed in config
        config_working_dir = self.config.get("working_dir", None)
        fixed_command = self.config.get("command", None)
        
        schema = {
            "type": "object",
            "properties": {
                "template_params": {
                    "type": "object",
                    "description": "Parameters to substitute in the command template",
                    "additionalProperties": True
                }
            }
        }
        
        if not fixed_command:
            # Only require template_name if no fixed command
            schema["properties"]["template_name"] = {
                "type": "string",
                "description": "Name of predefined command template to use"
            }
            schema["required"] = ["template_name"]
        
        # Only add working_dir to schema if not fixed in config
        if not config_working_dir:
            schema["properties"]["working_dir"] = {
                "type": "string",
                "description": "Working directory for command execution",
                "default": "."
            }
        
        return schema
