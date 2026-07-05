from mcp.server.fastmcp import FastMCP
import json
import sqlite3
from datetime import datetime
from app.db import (
    save_goal as db_save_goal,
    get_goals as db_get_goals,
    get_goal as db_get_goal,
    update_goal as db_update_goal,
    create_task as db_create_task,
    complete_task as db_complete_task,
    get_tasks as db_get_tasks,
    save_memory as db_save_memory,
    get_memory as db_get_memory,
    save_reflection as db_save_reflection,
    get_reflections as db_get_reflections,
    DB_PATH
)

mcp = FastMCP("NovaOS MCP Server")

# 1. Goal Tools
@mcp.tool()
def save_goal(title: str, description: str = "") -> str:
    """Save a new long-term goal.
    
    Args:
        title: The title of the goal.
        description: A short description of the goal.
    """
    goal_id = db_save_goal(title, description)
    return json.dumps({"status": "success", "goal_id": goal_id})

@mcp.tool()
def get_goal(goal_id: int) -> str:
    """Retrieve details of a specific goal.
    
    Args:
        goal_id: The ID of the goal to retrieve.
    """
    goal = db_get_goal(goal_id)
    if not goal:
        return json.dumps({"status": "error", "message": "Goal not found"})
    return json.dumps({"status": "success", "goal": goal})

@mcp.tool()
def update_goal(goal_id: int, title: str = None, description: str = None, status: str = None) -> str:
    """Update an existing goal's attributes or status (e.g. 'in_progress', 'completed').
    
    Args:
        goal_id: The target goal ID.
        title: Optional new title.
        description: Optional new description.
        status: Optional new status.
    """
    db_update_goal(goal_id, title, description, status)
    return json.dumps({"status": "success"})

# 2. Task Tools
@mcp.tool()
def create_task(goal_id: int, title: str, description: str = "", priority: str = "medium", due_date: str = None) -> str:
    """Create a daily/weekly task associated with a goal.
    
    Args:
        goal_id: The ID of the goal this task supports.
        title: The task title.
        description: Task description.
        priority: priority level ('high', 'medium', 'low').
        due_date: The due date in ISO or YYYY-MM-DD format.
    """
    task_id = db_create_task(goal_id, title, description, priority, due_date)
    return json.dumps({"status": "success", "task_id": task_id})

@mcp.tool()
def complete_task(task_id: int) -> str:
    """Mark a task as completed.
    
    Args:
        task_id: The target task ID.
    """
    db_complete_task(task_id)
    return json.dumps({"status": "success"})

@mcp.tool()
def get_today_tasks() -> str:
    """Retrieve all pending tasks due today or without a set due date."""
    tasks = db_get_tasks()
    today_str = datetime.now().strftime("%Y-%m-%d")
    today_tasks = [
        t for t in tasks 
        if t['status'] == 'pending' and (not t['due_date'] or today_str in t['due_date'])
    ]
    return json.dumps({"status": "success", "tasks": today_tasks})

# 3. Memory Tools
@mcp.tool()
def save_memory(key: str, value_dict_json: str) -> str:
    """Save or update general profile/preferences memory.
    
    Args:
        key: Unique memory key (e.g., 'user_preferences', 'personal_profile').
        value_dict_json: The dictionary content stringified as JSON.
    """
    try:
        val = json.loads(value_dict_json)
        db_save_memory(key, val)
        return json.dumps({"status": "success"})
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})

@mcp.tool()
def search_memory(query: str) -> str:
    """Search for relevant records in memories using keyword queries.
    
    Args:
        query: The keyword search query.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM memories WHERE key LIKE ? OR value LIKE ?", 
        (f"%{query}%", f"%{query}%")
    )
    rows = cursor.fetchall()
    conn.close()
    return json.dumps({"status": "success", "matches": [dict(r) for r in rows]})

# 4. Reflection Tools
@mcp.tool()
def save_reflection(date: str, completed_count: int, missed_count: int, feedback: str, patterns: str, suggestions: str) -> str:
    """Save daily reflection metrics and insights.
    
    Args:
        date: YYYY-MM-DD reflection date.
        completed_count: Count of completed tasks.
        missed_count: Count of missed tasks.
        feedback: Qualitative reflection feedback from the user.
        patterns: Patterns of behavior/performance detected.
        suggestions: Recommendations for future planning.
    """
    db_save_reflection(date, completed_count, missed_count, feedback, patterns, suggestions)
    return json.dumps({"status": "success"})

@mcp.tool()
def get_reflections() -> str:
    """Retrieve all daily reflections, sorted by date descending."""
    refs = db_get_reflections()
    return json.dumps({"status": "success", "reflections": refs})

if __name__ == "__main__":
    mcp.run()
