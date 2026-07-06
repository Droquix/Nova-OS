import os
import json
from datetime import datetime
from google.adk.agents import LlmAgent
from google.adk.models import Gemini
from app.config import config
from app.db import (
    save_goal,
    get_goal,
    update_goal,
    create_task,
    complete_task,
    get_tasks,
    create_milestone,
    save_memory
)

# Load instructions
instr_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "instructions.md")
with open(instr_path, "r", encoding="utf-8") as f:
    instructions = f.read()

# Wrap DB helpers as direct Python tools
def tool_save_goal(title: str, description: str = "") -> str:
    """Save a new long-term goal.
    
    Args:
        title: The title of the goal.
        description: A short description of the goal.
    """
    goal_id = save_goal(title, description)
    return json.dumps({"status": "success", "goal_id": goal_id})

def tool_get_goal(goal_id: int) -> str:
    """Retrieve details of a specific goal.
    
    Args:
        goal_id: The ID of the goal to retrieve.
    """
    goal = get_goal(goal_id)
    if not goal:
        return json.dumps({"status": "error", "message": "Goal not found"})
    return json.dumps({"status": "success", "goal": goal})

def tool_update_goal(goal_id: int, title: str = None, description: str = None, status: str = None) -> str:
    """Update an existing goal's attributes or status (e.g. 'in_progress', 'completed').
    
    Args:
        goal_id: The target goal ID.
        title: Optional new title.
        description: Optional new description.
        status: Optional new status.
    """
    update_goal(goal_id, title, description, status)
    return json.dumps({"status": "success"})

def tool_create_task(goal_id: int, title: str, description: str = "", priority: str = "medium", due_date: str = None) -> str:
    """Create a daily/weekly task associated with a goal.
    
    Args:
        goal_id: The ID of the goal this task supports.
        title: The task title.
        description: Task description.
        priority: priority level ('high', 'medium', 'low').
        due_date: The due date in ISO or YYYY-MM-DD format.
    """
    task_id = create_task(goal_id, title, description, priority, due_date)
    return json.dumps({"status": "success", "task_id": task_id})

def tool_complete_task(task_id: int) -> str:
    """Mark a task as completed.
    
    Args:
        task_id: The target task ID.
    """
    complete_task(task_id)
    return json.dumps({"status": "success"})

def tool_get_today_tasks() -> str:
    """Retrieve all pending tasks due today or without a set due date."""
    tasks = get_tasks()
    today_str = datetime.now().strftime("%Y-%m-%d")
    today_tasks = [
        t for t in tasks 
        if t['status'] == 'pending' and (not t['due_date'] or today_str in t['due_date'])
    ]
    return json.dumps({"status": "success", "tasks": today_tasks})

def tool_create_milestone(goal_id: int, title: str, description: str = "", due_date: str = None) -> str:
    """Create a milestone checkpoint associated with a goal.
    
    Args:
        goal_id: The ID of the goal this milestone supports.
        title: The milestone title.
        description: Milestone description.
        due_date: The due date in ISO or YYYY-MM-DD format.
    """
    milestone_id = create_milestone(goal_id, title, description, due_date)
    return json.dumps({"status": "success", "milestone_id": milestone_id})

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

planning_agent = LlmAgent(
    name="planning_agent",
    model=Gemini(
        model=config.model
    ),
    instruction=instructions,
    tools=[
        tool_save_goal,
        tool_get_goal,
        tool_update_goal,
        tool_create_task,
        tool_complete_task,
        tool_get_today_tasks,
        tool_create_milestone,
        tool_save_memory
    ]
)
