"""
ChatGPT Coach — local service, Phase 1.

Three endpoints, one per command, each returning a hardcoded string. No
storage, no analysis. The point of this phase is to prove the service runs
and answers, so run it and hit it with curl.

    uvicorn main:app --host 127.0.0.1 --port 8765 --reload

Nothing here listens on a public interface. 127.0.0.1 is your own machine.
"""

from fastapi import FastAPI

app = FastAPI(title="ChatGPT Coach", version="0.1.0")

PORT_HINT = "http://127.0.0.1:8765"


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