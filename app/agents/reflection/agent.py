import os
import json
from datetime import datetime
from google.adk.agents import LlmAgent
from google.adk.models import Gemini
from app.config import config
from app.db import (
    save_reflection,
    get_reflections,
    save_memory,
    get_tasks
)

# Load instructions
instr_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "instructions.md")
with open(instr_path, "r", encoding="utf-8") as f:
    instructions = f.read()

# Wrap DB helpers as direct Python tools
def tool_save_reflection(date: str, completed_count: int, missed_count: int, feedback: str, patterns: str, suggestions: str) -> str:
    """Save daily reflection metrics and insights.
    
    Args:
        date: YYYY-MM-DD reflection date.
        completed_count: Count of completed tasks.
        missed_count: Count of missed tasks.
        feedback: Qualitative reflection feedback from the user.
        patterns: Patterns of behavior/performance detected.
        suggestions: Recommendations for future planning.
    """
    save_reflection(date, completed_count, missed_count, feedback, patterns, suggestions)
    return json.dumps({"status": "success"})

def tool_get_reflections() -> str:
    """Retrieve all daily reflections, sorted by date descending."""
    refs = get_reflections()
    return json.dumps({"status": "success", "reflections": refs})

def tool_save_memory(key: str, value_dict_json: str) -> str:
    """Save or update general profile/preferences memory.
    
    Args:
        key: Unique memory key (e.g., 'user_preferences', 'personal_profile', 'ai_recommendations').
        value_dict_json: The dictionary content stringified as JSON.
    """
    try:
        val = json.loads(value_dict_json)
        save_memory(key, val)
        return json.dumps({"status": "success"})
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})

def tool_get_today_tasks() -> str:
    """Retrieve all pending tasks due today or without a set due date."""
    tasks = get_tasks()
    today_str = datetime.now().strftime("%Y-%m-%d")
    today_tasks = [
        t for t in tasks 
        if t['status'] == 'pending' and (not t['due_date'] or today_str in t['due_date'])
    ]
    return json.dumps({"status": "success", "tasks": today_tasks})

reflection_agent = LlmAgent(
    name="reflection_agent",
    model=Gemini(
        model=config.model
    ),
    instruction=instructions,
    tools=[
        tool_save_reflection,
        tool_get_reflections,
        tool_save_memory,
        tool_get_today_tasks
    ]
)
