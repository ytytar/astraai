from typing import Any, Dict
from core.tool_creation.tool_factories import BaseFunctionToolFactory

# https://rally1.rallydev.com/slm/webservice/v2.0/portfolioitem/ppmfeature?query=%28%28c_SHSQuadrimester+%3D+%222026+Quad+1%22%29+and+%28%28WSJFScore+%3E+0%29+and+%28TechOwner+contains+%22Tytar%22%29%29%29&order=WSJFScore&start=1&pagesize=40

# /portfolioitem/ppmfeature

class RallyAPITool(BaseFunctionToolFactory):
    """Tool for interacting with the Rally API."""
    def __init__(self, name, description, **config):
        super().__init__(name, description, **config)


    def _collect_query_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Collect query parameters for the Rally API request."""
        query_params = {}
        if self.config.get("fetchFields"):
            query_params["fetch"] = self.config["fetchFields"]
            
        # Query filter
        if params.get("query"):
            if self.config.get("defaultQuery"):
                query_params["query"] = f'({self.config.get("defaultQuery")} and {params.get("query")})'
            else:
                query_params["query"] = params["query"]

            # Ordering
            if params.get("order"):
                query_params["order"] = params["order"]
            
            # Pagination
            query_params["start"] = params.get("start", 1)
            query_params["pagesize"] = min(params.get("pagesize", 20), 200)  # Max 200 items for safety
            
        return query_params
    
    def _get_nested_value(self, data, path, default=None):
        """
        Retrieve a value from nested dict/json using dot notation path.
        
        Args:
            data: The dictionary to search in
            path: Dot-separated path (e.g., "QueryResult.Results")
            default: Default value if path not found
            
        Returns:
            The value at the specified path, or default if not found
        """
        if not data or not path:
            return default
            
        try:
            current = data
            for key in path.split('.'):
                if isinstance(current, dict) and key in current:
                    current = current[key]
                else:
                    return default
            return current
        except (KeyError, TypeError, AttributeError):
            return default

    def generate_message_from_data(self, data):
        """Generate a message from the API response data."""
        if not data:
            return {"error": "No data available to generate message."}
        
        results_path = self.config.get("resultsPath", "QueryResult.Results")
        errors_path = self.config.get("errorsPath", "QueryResult.Errors")

        # Use the helper function to extract data by path
        results = self._get_nested_value(data, results_path, [])
        errors = self._get_nested_value(data, errors_path, [])
        isError = len(errors) > 0


        # Extract relevant information from the data
        message = {
            "total_result_count": len(results) if isinstance(results, list) else 1,
            "results": results,
            "success": not isError
        }

        if "QueryResult" in results_path:
            message["total_result_count"] = data.get("QueryResult", {}).get("TotalResultCount", 0)
            message["start_index"] = data.get("QueryResult", {}).get("StartIndex", 1)
            message["page_size"] = data.get("QueryResult", {}).get("PageSize", 0)

        if errors:
            message["errors"] = errors

        return message

    async def _execute(self, params) -> Any:
        """Execute Rally API request to get portfolio items."""
        try:
            import aiohttp
            import urllib.parse
            
            # Get API credentials from config
            api_key = self.config.get("api_key")
            
            if not (api_key):
                return {"error": "Rally API credentials not configured. Need either api_key or username/password"}
            
            # Build the endpoint URL
            endpoint = params.get("endpoint", self.config.get("endpoint", "portfolioitem/ppmfeature"))
            url = f"{self.config.get('host')}{endpoint}"

            # Build query parameters
            query_params = self._collect_query_params(params)
            print(f"Rally API request: {url} with params: {query_params}")
            
            # Prepare authentication
            auth = None
            headers = {"Content-Type": "application/json"}
            
            if api_key:
                headers["Authorization"] = f'Bearer {api_key}'
            
            # Make the API request
            async with aiohttp.ClientSession() as session:
                query_params = query_params if len(query_params.keys()) > 0 else None
                async with session.get(
                    url, 
                    params=query_params,
                    headers=headers,
                    auth=auth,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        message = self.generate_message_from_data(data)
                        message["url"] = url
                        return message
                    else:
                        error_text = await response.text()
                        return {
                            "error": f"Rally API request failed with status {response.status}",
                            "status_code": response.status,
                            "response": error_text,
                            "url": url
                        }
                        
        except Exception as e:
            return {"error": f"Rally API request failed: {str(e)}"}

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "endpoint": {
                    "type": "string",
                    "description": "Rally API endpoint (default: portfolioitem/ppmfeature)",
                    "default": "portfolioitem/ppmfeature"
                },
                "resultsPath": {
                  "type": "string",
                  "description": "Path to the result in the API response",
                  "default": "QueryResult.Results"
                },
                "errorsPath": {
                    "type": "string",
                    "description": "Path to the errors in the API response",
                    "default": "QueryResult.Errors"
                },
                "query": {
                    "type": "string",
                    "description": "Rally query filter (e.g., '(State = \"In-Progress\") and (TechOwner contains \"Smith\")')"
                },
                "order": {
                    "type": "string",
                    "description": "Field to order by (e.g., 'WSJFScore', 'Name')"
                },
                "start": {
                    "type": "integer",
                    "description": "Start index for pagination (1-based)",
                    "default": 1
                },
                "pagesize": {
                    "type": "integer",
                    "description": "Number of items per page (max 200)",
                    "default": 20
                },
                "fetch": {
                    "type": "string",
                    "description": "Comma-separated list of fields to fetch"
                },
                "workspace": {
                    "type": "string",
                    "description": "Workspace ID or reference"
                },
                "params": {
                    "type": "object",
                    "description": "Additional query parameters",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Rally query filter (e.g., '(State = \"In-Progress\") and (TechOwner contains \"Smith\")')"
                        },
                        "endpoint": {
                            "type": "string",
                            "description": "Rally API endpoint (default: portfolioitem/ppmfeature)",
                            "default": "portfolioitem/ppmfeature"
                        },
                        "order": {
                            "type": "string",
                            "description": "Field to order by (e.g., 'WSJFScore', 'Name')"
                        },
                        "start": {
                            "type": "integer",
                            "description": "Start index for pagination (1-based)",
                            "default": 1
                        },
                       "pagesize": {
                            "type": "integer",
                            "description": "Number of items per page (max 200)",
                            "default": 20
                        },
                       "fetch": {
                            "type": "string",
                            "description": "Comma-separated list of fields to fetch"
                        },
                    }
                }
            },
            "required": []
        }
