import pytest
import os
from app.db import DB_PATH, init_db, save_goal, create_milestone, create_task, save_memory, get_goals, get_milestones, get_tasks

def test_db_logging_and_persistence(capsys):
    # Ensure fresh DB
    if os.path.exists(DB_PATH):
        try:
            os.remove(DB_PATH)
        except OSError:
            pass
    init_db()

    # Test save_goal logging
    goal_id = save_goal("Test Goal 10k", "Run 10k in a month")
    captured = capsys.readouterr()
    assert "Goal created" in captured.out
    assert "Database committed" in captured.out
    assert goal_id == 1

    # Test create_milestone logging
    milestone_id = create_milestone(goal_id, "Milestone 1", "Run 5k", "2026-07-20")
    captured = capsys.readouterr()
    assert "Milestones created" in captured.out
    assert "Database committed" in captured.out
    assert milestone_id == 1

    # Test create_task logging
    task_id = create_task(goal_id, "Task 1", "Running shoes prep", "high", "2026-07-10")
    captured = capsys.readouterr()
    assert "Tasks created" in captured.out
    assert "Database committed" in captured.out
    assert task_id == 1

    # Test save_memory logging
    save_memory("ai_recommendations", {"text": "Focus on consistent pacing."})
    captured = capsys.readouterr()
    assert "Memory updated" in captured.out
    assert "Database committed" in captured.out

    # Verify content in tables
    assert len(get_goals()) == 1
    assert len(get_milestones(goal_id)) == 1
    assert len(get_tasks()) == 1
