import os
import sqlite3
import json
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "nova_os.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Goals Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'in_progress',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    
    # 2. Milestones Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS milestones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            goal_id INTEGER,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'pending',
            due_date TEXT,
            FOREIGN KEY(goal_id) REFERENCES goals(id) ON DELETE CASCADE
        )
    """)
    
    # 3. Tasks Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            goal_id INTEGER,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'pending',
            priority TEXT DEFAULT 'medium',
            due_date TEXT,
            completed_at TEXT,
            FOREIGN KEY(goal_id) REFERENCES goals(id) ON DELETE CASCADE
        )
    """)
    
    # 4. Reflections Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reflections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL UNIQUE,
            completed_count INTEGER DEFAULT 0,
            missed_count INTEGER DEFAULT 0,
            feedback TEXT,
            patterns_identified TEXT,
            suggestions TEXT
        )
    """)
    
    # 5. Memories Table (Shared Long-term memory KV)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT NOT NULL UNIQUE,
            value TEXT NOT NULL
        )
    """)
    
    conn.commit()
    conn.close()

# Helper functions for database interaction
def save_goal(title: str, description: str = "", status: str = "in_progress"):
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute(
        "INSERT INTO goals (title, description, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (title, description, status, now, now)
    )
    goal_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return goal_id

def get_goals():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM goals ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_goal(goal_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM goals WHERE id = ?", (goal_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def update_goal(goal_id: int, title: str = None, description: str = None, status: str = None):
    conn = get_db_connection()
    cursor = conn.cursor()
    fields = []
    values = []
    if title is not None:
        fields.append("title = ?")
        values.append(title)
    if description is not None:
        fields.append("description = ?")
        values.append(description)
    if status is not None:
        fields.append("status = ?")
        values.append(status)
    
    if fields:
        fields.append("updated_at = ?")
        values.append(datetime.now().isoformat())
        values.append(goal_id)
        query = f"UPDATE goals SET {', '.join(fields)} WHERE id = ?"
        cursor.execute(query, tuple(values))
        conn.commit()
    conn.close()

def create_milestone(goal_id: int, title: str, description: str = "", due_date: str = None, status: str = "pending"):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO milestones (goal_id, title, description, due_date, status) VALUES (?, ?, ?, ?, ?)",
        (goal_id, title, description, due_date, status)
    )
    milestone_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return milestone_id

def get_milestones(goal_id: int = None):
    conn = get_db_connection()
    cursor = conn.cursor()
    if goal_id:
        cursor.execute("SELECT * FROM milestones WHERE goal_id = ?", (goal_id,))
    else:
        cursor.execute("SELECT * FROM milestones")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def create_task(goal_id: int, title: str, description: str = "", priority: str = "medium", due_date: str = None, status: str = "pending"):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO tasks (goal_id, title, description, priority, due_date, status) VALUES (?, ?, ?, ?, ?, ?)",
        (goal_id, title, description, priority, due_date, status)
    )
    task_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return task_id

def get_tasks(status: str = None):
    conn = get_db_connection()
    cursor = conn.cursor()
    if status:
        cursor.execute("SELECT * FROM tasks WHERE status = ?", (status,))
    else:
        cursor.execute("SELECT * FROM tasks")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def complete_task(task_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute(
        "UPDATE tasks SET status = 'completed', completed_at = ? WHERE id = ?",
        (now, task_id)
    )
    conn.commit()
    conn.close()

def save_reflection(date: str, completed_count: int, missed_count: int, feedback: str, patterns_identified: str, suggestions: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO reflections (date, completed_count, missed_count, feedback, patterns_identified, suggestions)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (date, completed_count, missed_count, feedback, patterns_identified, suggestions))
    conn.commit()
    conn.close()

def get_reflections():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM reflections ORDER BY date DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def save_memory(key: str, value: dict):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO memories (key, value)
        VALUES (?, ?)
    """, (key, json.dumps(value)))
    conn.commit()
    conn.close()

def get_memory(key: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM memories WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return json.loads(row["value"])
    return None

# Auto-initialize the DB
init_db()
