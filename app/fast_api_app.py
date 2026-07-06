# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import contextlib
import os
from collections.abc import AsyncIterator

import google.auth
from a2a.server.tasks import InMemoryTaskStore
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from google.adk.cli.fast_api import get_fast_api_app
from google.adk.runners import Runner
from google.cloud import logging as google_cloud_logging

from app.app_utils import services
from app.app_utils.a2a import attach_a2a_routes
from app.app_utils.reasoning_engine_adapter import (
    attach_reasoning_engine_routes,
)
from app.app_utils.telemetry import (
    setup_agent_engine_telemetry,
    setup_telemetry,
)
from app.app_utils.typing import Feedback

load_dotenv()
setup_telemetry()
# Must run before get_fast_api_app to set the tracer provider resource.
setup_agent_engine_telemetry()
try:
    _, project_id = google.auth.default()
    logging_client = google_cloud_logging.Client()
    logger = logging_client.logger(__name__)
except Exception:
    import logging as py_logging
    class LocalLogger:
        def log_struct(self, data, severity="INFO"):
            py_logging.info(f"[{severity}] {data}")
    logger = LocalLogger()
allow_origins = (
    os.getenv("ALLOW_ORIGINS", "").split(",") if os.getenv("ALLOW_ORIGINS") else None
)

AGENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Runner for the A2A path, sharing the same session/artifact services as the
    # adk_api and reasoning_engine paths (see services.py). Imported here so the
    # agent is built after env/telemetry setup.
    from app.agent import app as adk_app
    from app.agent import root_agent

    runner = Runner(
        app=adk_app,
        session_service=services.get_session_service(),
        artifact_service=services.get_artifact_service(),
        auto_create_session=True,
    )
    # Shared by the A2A path and the reasoning_engine adapter routes.
    app.state.runner = runner
    app.state.agent_app_name = adk_app.name
    await attach_a2a_routes(
        app,
        agent=root_agent,
        runner=runner,
        task_store=InMemoryTaskStore(),
        rpc_path=f"/a2a/{adk_app.name}",
    )
    yield


app: FastAPI = get_fast_api_app(
    agents_dir=AGENT_DIR,
    web=True,
    artifact_service_uri=services.ARTIFACT_SERVICE_URI,
    allow_origins=allow_origins,
    session_service_uri=services.SESSION_SERVICE_URI,
    otel_to_cloud=False,
    lifespan=lifespan,
)
app.title = "nova-os"
app.description = "API for interacting with the Agent nova-os"

app.mount("/static", StaticFiles(directory=os.path.join(AGENT_DIR, "static")), name="static")

@app.get("/")
def get_dashboard_root():
    return FileResponse(os.path.join(AGENT_DIR, "static", "index.html"))

@app.get("/api/dashboard")
def get_dashboard_data():
    print("Dashboard refreshed", flush=True)
    from app.db import get_goals, get_tasks, get_reflections, get_memory, get_milestones
    return {
        "goals": get_goals(),
        "tasks": get_tasks(),
        "milestones": get_milestones(),
        "reflections": get_reflections(),
        "recommendations": get_memory("ai_recommendations") or {}
    }

@app.post("/api/complete_task")
def post_complete_task(payload: dict):
    from app.db import complete_task
    task_id = payload.get("task_id")
    if task_id:
        complete_task(task_id)
        return {"status": "success"}
    return {"status": "error", "message": "Missing task_id"}

@app.post("/api/query")
async def post_query(payload: dict):
    prompt = payload.get("prompt", "")
    runner = app.state.runner
    session_id = "default_session"

    from google.genai import types
    response_text = ""
    try:
        async for event in runner.run_async(
            user_id="default_user",
            session_id=session_id,
            new_message=types.Content(role="user", parts=[types.Part.from_text(text=prompt)]),
        ):
            if event.output is not None:
                response_text = event.output
    except Exception as e:
        err_str = str(e)
        if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
            return {
                "response": (
                    "⚠️ API quota exhausted for today.\n\n"
                    "Your free-tier Gemini API key has hit its daily request limit.\n\n"
                    "To fix this:\n"
                    "1. Go to https://aistudio.google.com/apikey\n"
                    "2. Generate a new API key\n"
                    "3. Update GOOGLE_API_KEY in nova-os/.env\n"
                    "4. Restart the server\n\n"
                    "The quota resets daily at midnight Pacific Time."
                )
            }
        return {"response": f"❌ Error: {err_str[:300]}"}

    return {"response": response_text}


# Proxy routes so the Vertex AI Console Playground (reasoning_engine SDK) can
# talk to this agent alongside the native adk_api routes.
attach_reasoning_engine_routes(app)


@app.post("/feedback")
def collect_feedback(feedback: Feedback) -> dict[str, str]:
    """Collect and log feedback.

    Args:
        feedback: The feedback data to log

    Returns:
        Success message
    """
    logger.log_struct(feedback.model_dump(), severity="INFO")
    return {"status": "success"}


# Main execution
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
