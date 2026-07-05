import os
from typing import Any
from google.adk.workflow import Workflow, node, START, Edge
from google.adk.events.event import Event
from google.adk.agents.context import Context
from google.genai import types

from app.agents.security.agent import security_agent
from app.agents.orchestrator.agent import orchestrator_agent
from app.agents.memory.agent import memory_agent
from app.agents.planning.agent import planning_agent
from app.agents.reflection.agent import reflection_agent
from google.adk.apps import App

def _get_res_text(res) -> str:
    if isinstance(res, str):
        return res
    if hasattr(res, "parts") and res.parts:
        return "".join(p.text for p in res.parts if p.text)
    if hasattr(res, "text") and res.text:
        return res.text
    return str(res) if res is not None else ""

@node(name="security_check")
def security_check_node(ctx: Context, node_input: types.Content) -> Event:
    """Validate user input, scrub PII, and verify safety."""
    text = ""
    if node_input and node_input.parts:
        text = "".join(p.text for p in node_input.parts if p.text)
    
    res = security_agent.inspect_input(text)
    if not res["is_safe"]:
        return Event(
            output=res["reason"],
            route="blocked",
            content=types.Content(role="model", parts=[types.Part.from_text(text=res["reason"])])
        )
    return Event(
        output=res["scrubbed_text"],
        route="allowed",
        state={"user_query": res["scrubbed_text"]}
    )

@node(name="block_response")
def block_response_node(node_input: str) -> Event:
    """Security block handler."""
    msg = f"Request blocked due to security policies: {node_input}"
    return Event(
        content=types.Content(role="model", parts=[types.Part.from_text(text=msg)]),
        output=msg
    )

@node(name="orchestrator", rerun_on_resume=True)
async def orchestrator_node(ctx: Context, user_query: str) -> Event:
    """Determine the intent (planning, reflection, or general) of the user request."""
    prompt = f"""Analyze this user query: "{user_query}"
Categorize it into one of these intents:
- "planning": if the user is asking to create, update, list or reprioritize goals, milestones, or tasks.
- "reflection": if the user wants to log a daily reflection, analyze completed/missed tasks, get performance feedback, or look at insights.
- "general": for any other general personal operating system query, status request, etc.

Return only the intent name ("planning", "reflection", or "general") in lowercase as the first word on the first line, followed by a new line and a short summary of the user's specific request.
Example:
planning
User wants to create a python study goal."""

    res = await ctx.run_node(orchestrator_agent, node_input=prompt)
    res_text = _get_res_text(res).strip()
    
    lines = [l.strip() for l in res_text.split("\n") if l.strip()]
    intent = "general"
    summary = user_query
    if lines:
        first_line = lines[0].lower()
        if "planning" in first_line:
            intent = "planning"
        elif "reflection" in first_line:
            intent = "reflection"
        if len(lines) > 1:
            summary = " ".join(lines[1:])
            
    return Event(
        output={"intent": intent, "query": user_query, "summary": summary},
        state={"intent": intent, "query": user_query, "summary": summary}
    )

@node(name="memory_agent", rerun_on_resume=True)
async def memory_agent_node(ctx: Context, node_input: dict) -> Event:
    """Load the shared SQLite database state and provide context summary."""
    intent = node_input["intent"]
    query = node_input["query"]
    summary = node_input["summary"]
    
    from app.db import get_goals, get_tasks, get_reflections, get_memory
    goals = get_goals()
    tasks = get_tasks()
    reflections = get_reflections()
    profile = get_memory("user_profile") or {}
    recommendations = get_memory("ai_recommendations") or {}
    
    db_context = {
        "profile": profile,
        "goals": goals,
        "tasks": tasks,
        "reflections": reflections,
        "recommendations": recommendations
    }
    
    prompt = f"""The user is asking: "{query}".
Summary of request: {summary}
Here is the current state of goals/tasks/reflections:
Goals: {goals}
Tasks: {tasks}
Reflections: {reflections}
Profile: {profile}

Provide a short summary of the relevant history and state.
"""
    res = await ctx.run_node(memory_agent, node_input=prompt)
    summary_text = _get_res_text(res).strip()
        
    return Event(
        output={"intent": intent, "query": query, "db_context": db_context, "history_summary": summary_text},
        route=intent,
        state={"db_context": db_context, "history_summary": summary_text}
    )

@node(name="planning_agent", rerun_on_resume=True)
async def planning_agent_node(ctx: Context, node_input: dict) -> Event:
    """Formulate or update plans using planning tools."""
    query = node_input["query"]
    db_context = node_input["db_context"]
    history_summary = node_input["history_summary"]
    
    prompt = f"""User request: "{query}"
History summary: {history_summary}
Current Database State:
- Goals: {db_context['goals']}
- Tasks: {db_context['tasks']}

If the user wants to add/update a goal or create/complete/reprioritize a task, use the appropriate tools.
Provide an encouraging and structured response explaining the updates made, including the list of tasks or goal status."""

    res = await ctx.run_node(planning_agent, node_input=prompt)
    res_text = _get_res_text(res)
        
    return Event(
        output=res_text,
        content=res
    )

@node(name="reflection_agent", rerun_on_resume=True)
async def reflection_agent_node(ctx: Context, node_input: dict) -> Event:
    """Analyze completed vs missed tasks and generate reflections and suggestions."""
    query = node_input["query"]
    db_context = node_input["db_context"]
    history_summary = node_input["history_summary"]
    
    prompt = f"""User request: "{query}"
History summary: {history_summary}
Current reflections: {db_context['reflections']}
Current tasks: {db_context['tasks']}

Analyze the tasks. Calculate how many are completed vs pending/missed.
If the user wants to save a reflection, use 'save_reflection' to record it.
Also call 'save_memory' or update recommendations to provide personalized, actionable tips.
Respond with a synthesis of their progress, identified patterns, and tips."""

    res = await ctx.run_node(reflection_agent, node_input=prompt)
    res_text = _get_res_text(res)
        
    return Event(
        output=res_text,
        content=res
    )

@node(name="memory_update")
def memory_update_node(node_input: str) -> Event:
    """Persist reflection outcomes and recommendations."""
    return Event(
        output=node_input
    )

@node(name="final_response")
def final_response_node(node_input: Any) -> Event:
    """Prepare the final response event for client display."""
    if isinstance(node_input, str):
        return Event(
            content=types.Content(role="model", parts=[types.Part.from_text(text=node_input)]),
            output=node_input
        )
        
    # General fallback response summarizing current state
    from app.db import get_goals, get_tasks, get_memory
    goals = get_goals()
    tasks = get_tasks()
    rec = get_memory("ai_recommendations") or {"text": "Set your first goal to get personalized recommendations."}
    
    pending_tasks = [t for t in tasks if t['status'] == 'pending']
    
    summary = f"""### Welcome to NovaOS

**Today's AI Recommendation:**
> {rec.get('text')}

**Current Goals:**
{chr(10).join(f"- {g['title']} ({g['status']})" for g in goals) if goals else "No active goals."}

**Pending Tasks:**
{chr(10).join(f"- {t['title']} [Priority: {t['priority']}]" for t in pending_tasks) if pending_tasks else "All caught up for today!"}
"""
    return Event(
        content=types.Content(role="model", parts=[types.Part.from_text(text=summary)]),
        output=summary
    )

# Connect the nodes according to the workflow specification
root_agent = Workflow(
    name="nova_os",
    edges=[
        Edge(from_node=START, to_node=security_check_node),
        Edge(from_node=security_check_node, to_node=block_response_node, route="blocked"),
        Edge(from_node=security_check_node, to_node=orchestrator_node, route="allowed"),
        Edge(from_node=orchestrator_node, to_node=memory_agent_node),
        Edge(from_node=memory_agent_node, to_node=planning_agent_node, route="planning"),
        Edge(from_node=memory_agent_node, to_node=reflection_agent_node, route="reflection"),
        Edge(from_node=memory_agent_node, to_node=final_response_node, route="__DEFAULT__"),
        Edge(from_node=planning_agent_node, to_node=final_response_node),
        Edge(from_node=reflection_agent_node, to_node=memory_update_node),
        Edge(from_node=memory_update_node, to_node=final_response_node)
    ]
)

app = App(
    root_agent=root_agent,
    name="app",
)
