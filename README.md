# AgenticFlow - AI Agent Tools & Multi-Agent System

A powerful plugin system for AI agents that enables you to define tools in YAML configuration files, create multi-agent hierarchies, and use dependency injection for tool instantiation. Built on Google ADK (Agent Development Kit) with support for various external systems.

## Features

- 🔧 **YAML Configuration**: Define tools, agents, and configurations in YAML with environment variable support
- 🏗️ **Dependency Injection**: Automatic instantiation with configuration parameters
- 🔌 **Plugin Architecture**: Easy to add new tools by implementing the `BaseFunctionToolFactory` interface
- 🤖 **Multi-Agent Support**: Create hierarchical agent structures with specialized sub-agents
- 🛡️ **Security**: Built-in security features for file access, command execution, and database queries
- 🌐 **External Integrations**: Oracle DB, Rally API, GitHub, Terminal commands, and MCP tools
- 📦 **Async Support**: All tools support async execution
- 🔒 **Environment Variables**: Secure configuration with `.env` file support

## Quick Start

### 1. Install Dependencies

```bash
python -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Set Up Environment Variables

Copy the example environment file and configure your credentials:

```bash
cp .env.example .env
# Edit .env with your actual credentials
```

Required environment variables:
- `GOOGLE_GENAI_USE_VERTEXAI` - Set to TRUE for Vertex AI
- `GOOGLE_CLOUD_PROJECT` - Your Google Cloud project ID
- `GOOGLE_CLOUD_LOCATION` - Your preferred GCP location
- `RALLY_API_KEY` - Rally API key (if using Rally tools)
- `GITHUB_TOKEN` - GitHub token (if using GitHub tools)
- `ORACLE_USERNAME`, `ORACLE_PASSWORD`, `ORACLE_DSN` - Oracle DB credentials (if using Oracle tools)

### 3. Run the Agent

```bash
adk web --allow_origins "*"
```

This will start the web interface for interacting with your multi-agent system.

## Project Structure

```
core/
├── agent_utils/
│   ├── __init__.py
│   └── agent_loader.py           # Agent creation and configuration
├── tool_creation/
│   ├── __init__.py
│   ├── tool_factories.py         # Base tool factory classes
│   ├── tool_registry.py          # Plugin registry with DI
│   └── generic_tools.py          # Generic tool implementations (MCP)
└── config_utils.py               # Environment variable resolution

tools/
├── __init__.py
├── file_tools.py                 # File system operations
├── oracle_tools.py               # Oracle database queries
├── rally_tools.py                # Rally API integration
└── terminal_tools.py             # Terminal command execution

hs_agent/
├── agent.py                      # Main agent entry point
└── config.yaml                   # Agent and tools configuration

requirements.txt                   # Python dependencies
.env.example                      # Environment variables template
```

## Configuration Format

The system uses YAML configuration files that support environment variable substitution:

```yaml
# Tool configuration
tools:
  tool_name:
    class: "module.path.ToolClass"
    description: "Tool description"
    config:
      param1: "${ENV_VARIABLE:default_value}"
      param2: 42
      params:
        - name: "parameter_name"
          type: "string"
          description: "Parameter description"
          default: "default_value"

# Agent configuration
root_agent:
  name: 'main_agent'
  model: 'gemini-2.5-pro'
  description: 'Main AI Agent'
  instruction: 'You are a helpful AI assistant'
  tools:
    - tool_name
  sub_agents:
    specialized_agent:
      name: "specialized_agent"
      model: "gemini-2.5-pro" 
      description: "Specialized agent for specific tasks"
      instruction: "Handle specialized tasks"
      tools:
        - specialized_tool
```

### Environment Variable Support

Use `${VARIABLE_NAME}` for required variables or `${VARIABLE_NAME:default}` for optional ones:

```yaml
api_key: "${API_KEY}"                    # Required
host: "${HOST:localhost}"               # Optional with default
debug: "${DEBUG:false}"                 # Boolean with default
```

## Creating Custom Tools

### 1. Inherit from BaseFunctionToolFactory

```python
from core.tool_creation.tool_factories import BaseFunctionToolFactory
from typing import Dict, Any

class MyCustomTool(BaseFunctionToolFactory):
    def __init__(self, name: str, description: str, **config):
        super().__init__(name, description, **config)
    
    async def _execute(self, params: Dict[str, Any]) -> Any:
        """Execute the tool's main logic."""
        try:
            input_param = params.get("input_param")
            my_config_value = self.config.get("my_param", "default")
            
            # Your tool logic here
            result = f"Processed: {input_param} with {my_config_value}"
            
            return {
                "success": True,
                "result": result,
                "input": input_param
            }
        except Exception as e:
            return {"error": str(e)}
    
    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "input_param": {
                    "type": "string",
                    "description": "Input parameter description"
                }
            },
            "required": ["input_param"]
        }
```

### 2. Add to Configuration

```yaml
tools:
  my_custom_tool:
    class: "my_module.MyCustomTool"
    description: "My custom tool"
    config:
      my_param: "custom_value"
      params:
        - name: "input_param"
          type: "string"
          description: "The input parameter"
```

### 3. Use in Agent Configuration

```yaml
root_agent:
  name: 'my_agent'
  tools:
    - my_custom_tool
```

## Built-in Tools

### File Tools

#### FileReaderTool
Safely reads text files with extension and size validation.

**Configuration:**
```yaml
file_reader:
  class: "tools.file_tools.FileReaderTool"
  config:
    allowed_extensions: [".txt", ".md", ".json", ".yaml"]
    max_size_mb: 10
    root_path: "/path/to/allowed/directory"
```

#### DirectoryListTool
Lists directory contents with filtering capabilities.

**Configuration:**
```yaml
directory_list:
  class: "tools.file_tools.DirectoryListTool"
  config:
    max_items: 100
    show_hidden: false
    excluded_patterns: ["*.pyc", ".DS_Store"]
```

### Database Tools

#### OracleQueryTool
Executes parameterized Oracle database queries with bind variables.

**Configuration:**
```yaml
oracle_query:
  class: "tools.oracle_tools.OracleQueryTool"
  config:
    connection:
      username: "${ORACLE_USERNAME}"
      password: "${ORACLE_PASSWORD}"
      dsn: "${ORACLE_DSN}"
    query: "SELECT * FROM table WHERE id = {id}"
    max_rows: 1000
```

### API Integration Tools

#### RallyAPITool
Integrates with Rally API for project management data.

**Configuration:**
```yaml
rally_api:
  class: "tools.rally_tools.RallyAPITool"
  config:
    api_key: "${RALLY_API_KEY}"
    host: "https://rally1.rallydev.com/slm/webservice/v2.0"
    endpoint: "/portfolioitem/ppmfeature"
```

### Terminal Tools

#### TerminalCommandTool
Executes terminal commands with security restrictions.

**Configuration:**
```yaml
terminal_tool:
  class: "tools.terminal_tools.TerminalCommandTool"
  config:
    allowed_commands: ["git", "ls", "pwd"]
    max_execution_time: 30
    allowed_working_dirs: ["/safe/directory"]
```

#### SafeTerminalTool
More restrictive terminal tool using only predefined command templates.

**Configuration:**
```yaml
safe_terminal:
  class: "tools.terminal_tools.SafeTerminalTool"
  config:
    command_templates:
      git_status: "git status"
      list_files: "ls -la {directory}"
```

### External Integration Tools

#### RemoteMCPTools
Connects to Model Context Protocol (MCP) servers.

**Configuration:**
```yaml
mcp_tools:
  class: "core.tool_creation.generic_tools.RemoteMCPTools"
  config:
    url: "https://api.example.com/mcp/"
    api_key: "${MCP_API_KEY}"
    tools_filter: ["specific_tool_name"]
```

## Multi-Agent System Usage

### Creating Agents Programmatically

```python
from core.tool_creation.tool_registry import ToolRegistry
from core.agent_utils import create_agent
from core.config_utils import load_config

# Load tools registry
tool_registry = ToolRegistry()
tool_registry.load_from_config("config.yaml")

# Load agent configuration
config = load_config("config.yaml")

# Create the main agent with sub-agents
main_agent = create_agent(config["root_agent"], tool_registry)
```

### Agent Configuration Structure

```yaml
root_agent:
  name: 'main_agent'
  model: 'gemini-2.5-pro'
  description: 'Main coordinating agent'
  instruction: 'You coordinate tasks between specialized agents'
  tools:
    - general_tool1
    - general_tool2
  sub_agents:
    database_agent:
      name: "database_agent"
      model: "gemini-2.5-pro"
      description: "Handles all database operations"
      instruction: "You are expert in database queries and schema"
      tools:
        - oracle_query
        - table_discovery
    
    api_agent:
      name: "api_agent"
      model: "gemini-2.5-pro"
      description: "Handles external API integrations"
      instruction: "You manage external service integrations"
      tools:
        - rally_api
        - github_api
```

### Running the Agent System

```bash
# Navigate to agent directory
cd hs_agent

# Start the web interface
adk web --allow_origins "*"

# Or run programmatically
python agent.py
```

## Advanced Features

### Environment Variable Resolution
All configuration files support environment variable substitution:

```yaml
# Required variables (will fail if not set)
api_key: "${API_KEY}"

# Optional variables with defaults
host: "${HOST:localhost}"
port: "${PORT:8080}"
debug: "${DEBUG:false}"

# Complex nested configurations
database:
  connection:
    username: "${DB_USER}"
    password: "${DB_PASS}"
    dsn: "${DB_DSN:localhost:1521/XE}"
```

### Tool Parameter Definition
Tools can define their parameters with type information and validation:

```yaml
tools:
  my_tool:
    class: "tools.my_tools.MyTool"
    config:
      params:
        - name: "required_param"
          type: "string"
          description: "This parameter is required"
        - name: "optional_param"
          type: "integer"
          description: "This parameter has a default"
          default: 42
```

### Security Features

#### File Access Control
```yaml
file_reader:
  config:
    allowed_extensions: [".txt", ".md"]  # Restrict file types
    max_size_mb: 10                     # Limit file size
    root_path: "/safe/directory"        # Restrict to specific directory
```

#### Command Execution Control
```yaml
terminal_tool:
  config:
    allowed_commands: ["git", "ls"]     # Whitelist commands
    allowed_working_dirs: ["/safe"]     # Restrict directories
    max_execution_time: 30              # Timeout protection
```

#### Database Query Safety
```yaml
oracle_tool:
  config:
    max_rows: 1000                      # Limit result size
    timeout: 30                         # Query timeout
    # Only SELECT statements allowed, bind parameters prevent injection
```

### Tool Registry Management

```python
from core.tool_creation.tool_registry import ToolRegistry

registry = ToolRegistry()
registry.load_from_config("config.yaml")

# Get available tools
tools = registry.get_all_available_tools()

# Check if tool exists
if registry.has_tool("my_tool"):
    tool = registry.get_tool("my_tool")

# Get tool schema
schema = registry.get_tool_schema("my_tool")

# Reload configuration
registry.reload_config("config.yaml")
```

## Extending the System

### Adding New Tool Types

1. **Create the Tool Class**
```python
from core.tool_creation.tool_factories import BaseFunctionToolFactory

class MyNewTool(BaseFunctionToolFactory):
    async def _execute(self, params):
        # Tool implementation
        return {"result": "success"}
    
    def get_schema(self):
        return {
            "type": "object",
            "properties": {
                "param1": {"type": "string", "description": "Parameter description"}
            }
        }
```

2. **Add to Configuration**
```yaml
tools:
  my_new_tool:
    class: "tools.my_tools.MyNewTool"
    description: "My new tool"
    config:
      # Tool-specific configuration
```

3. **Register with Agent**
```yaml
root_agent:
  tools:
    - my_new_tool
```

### Creating Specialized Agents

```python
from google.adk.agents import Agent
from core.tool_creation.tool_registry import ToolRegistry

# Create specialized agent
def create_database_agent(tool_registry):
    tools = [
        tool_registry.get_tool("oracle_query").create_instance(),
        tool_registry.get_tool("table_discovery").create_instance()
    ]
    
    return Agent(
        name="database_expert",
        model="gemini-2.5-pro",
        description="Database operations specialist",
        instruction="You are an expert in database queries and schema analysis",
        tools=tools
    )
```

### Integration Patterns

#### With External APIs
```yaml
api_integration:
  class: "tools.api_tools.GenericAPITool"
  config:
    base_url: "${API_BASE_URL}"
    auth_header: "Bearer ${API_TOKEN}"
    endpoints:
      get_data: "/api/data/{id}"
      post_data: "/api/data"
```

#### With Message Queues
```yaml
queue_tool:
  class: "tools.queue_tools.MessageQueueTool"
  config:
    queue_url: "${QUEUE_URL}"
    queue_name: "agent_tasks"
```

#### With File Systems
```yaml
file_processor:
  class: "tools.file_tools.FileProcessorTool"
  config:
    input_directory: "/data/input"
    output_directory: "/data/output"
    allowed_formats: [".json", ".csv", ".xml"]
```

## Security Considerations

### File System Security
- **Extension Filtering**: Only allow specific file types
- **Size Limits**: Prevent reading of large files
- **Path Restrictions**: Limit access to specific directories
- **Symbolic Link Protection**: Resolve paths to prevent directory traversal

### Command Execution Security
- **Command Whitelisting**: Only allow approved commands
- **Working Directory Restrictions**: Limit execution to safe directories
- **Timeout Protection**: Prevent long-running commands
- **Output Size Limits**: Prevent memory exhaustion
- **Parameter Sanitization**: Escape shell special characters

### Database Security
- **Query Type Restrictions**: Only SELECT statements allowed
- **Bind Parameters**: Prevent SQL injection
- **Row Limits**: Prevent large result sets
- **Connection Timeouts**: Prevent hanging connections
- **Credential Management**: Use environment variables for sensitive data

### API Security
- **Token Management**: Secure API key storage
- **Rate Limiting**: Respect API rate limits
- **Request Validation**: Validate all parameters
- **Error Handling**: Don't expose sensitive information in errors

### General Security Best Practices
- **Environment Variables**: Never commit secrets to version control
- **Least Privilege**: Tools should have minimal required permissions
- **Input Validation**: Validate all user inputs
- **Error Logging**: Log security events for monitoring
- **Configuration Auditing**: Review tool configurations regularly

## Testing

### Unit Testing Tools

```python
import pytest
from unittest.mock import AsyncMock, patch
from tools.file_tools import FileReaderTool

@pytest.mark.asyncio
async def test_file_reader_tool():
    tool = FileReaderTool(
        name="test_reader",
        description="Test file reader",
        allowed_extensions=[".txt"],
        max_size_mb=1
    )
    
    # Mock file system
    with patch("pathlib.Path.exists", return_value=True), \
         patch("pathlib.Path.stat") as mock_stat, \
         patch("builtins.open", mock_open(read_data="test content")):
        
        mock_stat.return_value.st_size = 100
        
        result = await tool._execute({"path": "test.txt"})
        
        assert "content" in result
        assert result["content"] == "test content"
```

### Integration Testing

```python
import pytest
from core.tool_creation.tool_registry import ToolRegistry
from core.agent_utils import create_agent

@pytest.mark.asyncio
async def test_agent_with_tools():
    # Create test configuration
    test_config = {
        "tools": {
            "test_tool": {
                "class": "tools.file_tools.FileReaderTool",
                "config": {"allowed_extensions": [".txt"]}
            }
        },
        "root_agent": {
            "name": "test_agent",
            "description": "Test agent",
            "instruction": "Test instruction",
            "tools": ["test_tool"]
        }
    }
    
    # Test agent creation
    registry = ToolRegistry()
    # Load test configuration...
    
    agent = create_agent(test_config["root_agent"], registry)
    assert agent.name == "test_agent"
```

### Configuration Testing

```python
def test_environment_variable_resolution():
    import os
    from core.config_utils import resolve_env_variables
    
    os.environ["TEST_VAR"] = "test_value"
    
    config = {
        "api_key": "${TEST_VAR}",
        "host": "${MISSING_VAR:localhost}"
    }
    
    resolved = resolve_env_variables(config)
    
    assert resolved["api_key"] == "test_value"
    assert resolved["host"] == "localhost"
```

### Security Testing

```python
@pytest.mark.asyncio
async def test_command_injection_protection():
    from tools.terminal_tools import SafeTerminalTool
    
    tool = SafeTerminalTool(
        name="safe_terminal",
        description="Safe terminal",
        command_templates={"echo": "echo {message}"}
    )
    
    # Test injection attempt
    result = await tool._execute({
        "template_name": "echo",
        "template_params": {"message": "hello; rm -rf /"}
    })
    
    # Should be safely escaped
    assert "rm -rf" not in result.get("stdout", "")
```

## Dependencies

The system is built on several key dependencies:

```txt
google-adk>=1.11.0          # Google Agent Development Kit
PyYAML>=6.0                 # YAML configuration parsing
httpx>=0.25.0              # HTTP client for API calls
aiohttp>=3.8.0             # Async HTTP client
cx_Oracle>=8.0.0           # Oracle database connectivity
```

### Optional Dependencies

Install based on your tool requirements:

- **Oracle Database**: `cx_Oracle` (requires Oracle Instant Client)
- **Additional HTTP clients**: `requests`, `urllib3`
- **Testing**: `pytest`, `pytest-asyncio`
- **Development**: `black`, `flake8`, `mypy`

## Deployment

### Docker Deployment

```dockerfile
FROM python:3.11-slim

# Install Oracle Instant Client (if using Oracle tools)
RUN apt-get update && apt-get install -y libaio1 wget unzip

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Set environment variables
ENV GOOGLE_GENAI_USE_VERTEXAI=TRUE

EXPOSE 8000

CMD ["adk", "web", "--host", "0.0.0.0", "--port", "8000"]
```

### Environment Configuration

```bash
# Production environment variables
export GOOGLE_GENAI_USE_VERTEXAI=TRUE
export GOOGLE_CLOUD_PROJECT="your-project-id"
export GOOGLE_CLOUD_LOCATION="us-central1"

# Application-specific variables
export RALLY_API_KEY="your-rally-key"
export GITHUB_TOKEN="your-github-token"
export ORACLE_USERNAME="your-db-user"
export ORACLE_PASSWORD="your-db-password" 
export ORACLE_DSN="your-db-connection-string"
```

## Future Enhancements

- [ ] **Runtime Tool Registration**: Add/remove tools without restarting
- [ ] **Tool Composition**: Chain tools together for complex workflows
- [ ] **Enhanced Validation**: JSON Schema validation for all parameters
- [ ] **Usage Analytics**: Track tool usage and performance metrics
- [ ] **Caching Layer**: Cache expensive operations and API calls
- [ ] **Distributed Execution**: Scale tool execution across multiple nodes
- [ ] **Tool Marketplace**: Discover and share community tools
- [ ] **Visual Configuration**: Web-based tool and agent configuration
- [ ] **Monitoring Dashboard**: Real-time monitoring of agent activities
- [ ] **Plugin Hot-reload**: Update tools without system restart
- [ ] **Advanced Security**: Role-based access control and audit logging
- [ ] **Workflow Engine**: Define complex multi-step workflows

## Examples

### Complete Working Example

See the `hs_agent/config.yaml` file for a complete working configuration that includes:

- **Multi-agent hierarchy** with specialized sub-agents
- **Oracle database integration** for schema discovery
- **Rally API integration** for project management
- **GitHub integration** via MCP tools
- **File system tools** with security restrictions
- **Terminal command execution** with safety controls

### Common Use Cases

1. **Data Analysis Agent**: Combines database queries with file processing
2. **DevOps Agent**: Integrates Git, CI/CD, and monitoring tools
3. **Project Management Agent**: Connects Rally, GitHub, and documentation
4. **Research Agent**: Combines web search, file reading, and data analysis
5. **Customer Support Agent**: Integrates ticketing systems with knowledge bases

## Contributing

1. **Fork the repository** and create a feature branch
2. **Follow the tool factory pattern** for new tools
3. **Add comprehensive schemas** and parameter validation
4. **Include proper error handling** and security measures
5. **Write tests** for your tools and configurations
6. **Update documentation** with examples and use cases
7. **Submit a pull request** with detailed description

### Development Setup

```bash
git clone <repository-url>
cd agenticFlow
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your configuration
cd hs_agent
adk web --allow_origins "*"
```

## License

This project is open source. Feel free to use and modify as needed.

---

For more information about Google ADK, visit the [official documentation](https://developers.google.com/adk).
