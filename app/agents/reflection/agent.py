import os
from google.adk.agents import LlmAgent
from google.adk.models import Gemini
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters
from app.config import config

# Load instructions
instr_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "instructions.md")
with open(instr_path, "r", encoding="utf-8") as f:
    instructions = f.read()

# Setup Local MCP server via stdio using uv run python -m app.mcp_server
# This exposes: save_reflection, get_reflections, save_memory, get_today_tasks
mcp_toolset = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="uv",
            args=["run", "python", "-m", "app.mcp_server"],
        ),
    ),
    tool_filter=["save_reflection", "get_reflections", "save_memory", "get_today_tasks"]
)

reflection_agent = LlmAgent(
    name="reflection_agent",
    model=Gemini(
        model=config.model
    ),
    instruction=instructions,
    tools=[mcp_toolset]
)
