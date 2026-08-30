"""
ChatGPT Coach — local service, Phase 1.

Three endpoints, one per command, each returning a hardcoded string. No
storage, no analysis. The point of this phase is to prove the service runs
and answers, so run it and hit it with curl.

    uvicorn server:app --host 127.0.0.1 --port 8787 --reload

Run it from the repo root. The browser half lives in extension/ and Python
never writes there, which is the point of the split: Chrome refuses to load
an unpacked extension containing any name that starts with an underscore, and
__pycache__ is exactly that.

Nothing here listens on a public interface. 127.0.0.1 is your own machine.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="ChatGPT Coach", version="0.1.0")

# The extension doesn't rely on this. It calls from a background service
# worker, which host_permissions exempts from CORS altogether. This stays so
# you can hit the endpoints from the devtools console of an open ChatGPT tab
# while debugging, which is otherwise blocked.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://chatgpt.com", "https://chat.openai.com"],
    allow_methods=["GET"],
)

PORT_HINT = "http://127.0.0.1:8787"


@app.get("/health")
def health():
    """Is the service up? Useful as the first thing you curl."""
    return {"ok": True}


@app.get("/status")
def status():
    return {
        "command": "status",
        "title": "/coach:status",
        "body": "Your request to status was received.",
    }


@app.get("/feedback")
def feedback():
    return {
        "command": "feedback",
        "title": "/coach:feedback",
        "body": "Your request to feedback was received.",
    }


@app.get("/dashboard")
def dashboard():
    return {
        "command": "dashboard",
        "title": "/coach:dashboard",
        "body": "Your request to dashboard was received.",
    }


@app.get("/")
def index():
    """A directory of what exists, so you never have to guess a path."""
    return {
        "service": "chatgpt-coach",
        "endpoints": [f"{PORT_HINT}{p}" for p in ("/health", "/status", "/feedback", "/dashboard")],
    }