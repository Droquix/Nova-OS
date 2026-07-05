import os
from google.adk.agents import LlmAgent
from google.adk.models import Gemini
from app.config import config
from app.db import get_goals, get_tasks, get_reflections, get_memory, save_memory

# Load instructions
instr_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "instructions.md")
with open(instr_path, "r", encoding="utf-8") as f:
    instructions = f.read()

# Let's wrap database helpers into tools that the LLM agent can invoke.
def db_read_goals() -> str:
    """Gets the list of all current goals in the system."""
    goals = get_goals()
    if not goals:
        return "No goals found in SQLite database."
    return "\n".join([f"Goal ID {g['id']}: {g['title']} - Description: {g['description']} (Status: {g['status']})" for g in goals])

def db_read_tasks() -> str:
    """Gets the list of all tasks in the system."""
    tasks = get_tasks()
    if not tasks:
        return "No tasks found in SQLite database."
    return "\n".join([f"Task ID {t['id']} (Goal ID {t['goal_id']}): {t['title']} (Priority: {t['priority']}, Due: {t['due_date']}, Status: {t['status']})" for t in tasks])

def db_read_reflections() -> str:
    """Gets all historical daily reflections."""
    reflections = get_reflections()
    if not reflections:
        return "No reflections found in SQLite database."
    return "\n".join([f"Date {r['date']}: Completed Tasks: {r['completed_count']}, Missed Tasks: {r['missed_count']}\nFeedback: {r['feedback']}\nPatterns: {r['patterns_identified']}\nSuggestions: {r['suggestions']}" for r in reflections])

def db_read_preference(key: str) -> str:
    """Gets a personal preference or profile memory value by key (e.g. 'user_profile', 'recommendations')."""
    val = get_memory(key)
    if not val:
        return f"No memory record found for key '{key}'."
    return f"Memory '{key}': {val}"

def db_write_preference(key: str, value_dict_json: str) -> str:
    """Saves or updates a JSON-formatted memory record under a key."""
    import json
    try:
        data = json.loads(value_dict_json)
        save_memory(key, data)
        return f"Successfully saved key '{key}' in memories."
    except Exception as e:
        return f"Error saving memory: {e}"

memory_agent = LlmAgent(
    name="memory_agent",
    model=Gemini(
        model=config.model
    ),
    instruction=instructions,
    tools=[db_read_goals, db_read_tasks, db_read_reflections, db_read_preference, db_write_preference]
)
