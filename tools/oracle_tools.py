try:
    import cx_Oracle
except ImportError:
    cx_Oracle = None
import re
from typing import Dict, Any, List, Optional, Union
from pathlib import Path

from core.tool_creation.tool_factories import BaseFunctionToolFactory


class OracleQueryTool(BaseFunctionToolFactory):
    """Tool for executing parameterized Oracle database queries."""
    
    async def _execute(self, params) -> Any:
        """Execute Oracle query with parameter substitution."""
        # Check if cx_Oracle is available
        if cx_Oracle is None:
            return {"error": "cx_Oracle library is not installed. Please install it with: pip install cx_Oracle"}
        
        # Configuration options
        connection_config = self.config.get("connection", {})  # Database connection parameters
        query_template = self.config.get("query", None)  # Fixed query template
        query_templates = self.config.get("query_templates", {})  # Pre-defined query templates
        max_rows = self.config.get("max_rows", 1000)  # Maximum rows to return
        timeout = self.config.get("timeout", 30)  # Query timeout in seconds
        
        try:
            query = params.get("query") if not query_template else None
            template_name = params.get("template_name")
            query_params = params
            
            print(f"Executing Oracle query: {params}")

            # Determine the query to execute
            if query_template:
                # Use fixed query from config with parameter substitution
                query, bind_params = self._prepare_query_with_binds(query_template, query_params)
                
            elif template_name:
                # Use predefined template
                if template_name not in query_templates:
                    available_templates = list(query_templates.keys())
                    return {
                        "error": f"Unknown query template: {template_name}",
                        "available_templates": available_templates
                    }
                
                query_template_str = query_templates[template_name]
                query, bind_params = self._prepare_query_with_binds(query_template_str, query_params)
                
            elif query:
                # Use direct query (if no fixed query is set)
                if not self._is_query_safe(query):
                    return {"error": f"Query contains potentially unsafe operations: {query}"}
                # For direct queries, assume no bind parameters
                bind_params = {}
            else:
                return {"error": "Either 'query' or 'template_name' must be provided"}

            # Validate connection configuration
            connection_error = self._validate_connection_config(connection_config)
            if connection_error:
                return {"error": connection_error}

            # Execute query
            result = await self._execute_query(
                query, 
                bind_params,
                connection_config,
                max_rows,
                timeout
            )
            
            return result

        except Exception as e:
            return {"error": f"Query execution failed: {str(e)}"}

    def _prepare_query_with_binds(self, query_template: str, params: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
        """Convert placeholders to bind variables and return query with bind parameters."""
        query = query_template
        bind_params = {}
        
        # Find all placeholders like {param_name} and convert to :param_name
        placeholders = re.findall(r'\{(\w+)\}', query_template)
        
        for placeholder in placeholders:
            if placeholder not in params:
                raise ValueError(f"Missing required parameter: {placeholder}")
            
            # Replace {param_name} with :param_name (Oracle bind variable syntax)
            query = query.replace(f"{{{placeholder}}}", f":{placeholder}")
            # Store the actual parameter value
            bind_params[placeholder] = params[placeholder]
        
        return query, bind_params

    def _is_query_safe(self, query: str) -> bool:
        """Basic safety check for SQL queries."""
        # Convert to uppercase for checking
        query_upper = query.upper().strip()
        
        # Only allow SELECT statements for safety
        if not query_upper.startswith('SELECT'):
            return False
        
        # Check for dangerous keywords
        dangerous_keywords = [
            'DROP', 'DELETE', 'INSERT', 'UPDATE', 'ALTER', 'CREATE',
            'TRUNCATE', 'GRANT', 'REVOKE', 'EXEC', 'EXECUTE',
            'DBMS_', 'UTL_', 'SYS.'
        ]
        
        for keyword in dangerous_keywords:
            if keyword in query_upper:
                return False
        
        return True

    def _validate_connection_config(self, connection_config: Dict[str, Any]) -> Optional[str]:
        """Validate that required connection parameters are present."""
        required_fields = ['username', 'password', 'dsn']
        
        for field in required_fields:
            if field not in connection_config:
                return f"Missing required connection parameter: {field}"
        
        return None

    async def _execute_query(
        self, 
        query: str, 
        bind_params: Dict[str, Any],
        connection_config: Dict[str, Any],
        max_rows: int,
        timeout: int
    ) -> Dict[str, Any]:
        """Execute the Oracle query with bind parameters and return results."""
        connection = None
        try:
            # Establish connection
            connection = cx_Oracle.connect(
                user=connection_config['username'],
                password=connection_config['password'],
                dsn=connection_config['dsn'],
                encoding="UTF-8"
            )
            
            # Set timeout
            connection.callTimeout = timeout * 1000  # cx_Oracle uses milliseconds
            
            # Create cursor
            cursor = connection.cursor()
            
            # Execute query with bind parameters
            cursor.execute(query, bind_params)
            
            # Fetch results
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            rows = cursor.fetchmany(max_rows)
            
            # Check if there are more rows
            has_more = len(rows) == max_rows
            if has_more:
                # Try to fetch one more row to confirm
                extra_row = cursor.fetchone()
                has_more = extra_row is not None
            
            # Convert rows to list of dictionaries
            result_data = []
            for row in rows:
                row_dict = {}
                for i, column in enumerate(columns):
                    value = row[i]
                    # Convert Oracle-specific types to JSON-serializable types
                    if hasattr(value, 'read'):  # CLOB/BLOB
                        value = value.read()
                    elif hasattr(value, 'isoformat'):  # datetime
                        value = value.isoformat()
                    row_dict[column] = value
                result_data.append(row_dict)
            
            return {
                "query": query,
                "bind_params": bind_params,
                "columns": columns,
                "rows": result_data,
                "row_count": len(result_data),
                "has_more_rows": has_more,
                "max_rows_limit": max_rows,
                "success": True
            }
            
        except cx_Oracle.Error as e:
            error_obj, = e.args
            return {
                "query": query,
                "bind_params": bind_params,
                "error": f"Oracle error: {error_obj.message}",
                "error_code": error_obj.code if hasattr(error_obj, 'code') else None,
                "success": False
            }
        except Exception as e:
            return {
                "query": query,
                "bind_params": bind_params,
                "error": f"Failed to execute query: {str(e)}",
                "success": False
            }
        finally:
            if connection:
                try:
                    connection.close()
                except:
                    pass

    def get_schema(self) -> Dict[str, Any]:
        query_template = self.config.get("query", None)
        
        schema = {
            "type": "object",
            "properties": {},
            "required": []
        }
        
        if query_template:
            # Only allow query_params when using fixed query
            schema["properties"]["query_params"] = {
                "type": "object",
                "description": "Parameters to substitute in the fixed query template",
                "additionalProperties": True
            }
        else:
            # Original schema when no fixed query
            schema["properties"].update({
                "query": {
                    "type": "string",
                    "description": "The SQL query to execute (if not using template)"
                },
                "template_name": {
                    "type": "string", 
                    "description": "Name of predefined query template to use"
                },
                "query_params": {
                    "type": "object",
                    "description": "Parameters to substitute in the query template",
                    "additionalProperties": True
                }
            })
            schema["anyOf"] = [
                {"required": ["query"]},
                {"required": ["template_name"]}
            ]
        
        return schema
