import os
from google.adk.agents import LlmAgent
from google.adk.models import Gemini
from app.config import config

# Load instructions
instr_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "instructions.md")
with open(instr_path, "r", encoding="utf-8") as f:
    instructions = f.read()

orchestrator_agent = LlmAgent(
    name="orchestrator_agent",
    model=Gemini(
        model=config.model
    ),
    instruction=instructions,
)
