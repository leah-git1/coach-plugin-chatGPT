"""
ChatGPT Coach — local service.

The surface adapter for the browser half. `extension/` catches a `/coach:` command and asks this
for an answer; this translates it into the Evolve Coach backend's real call and renders the reply
as the text the bubble shows. It is the same job `evolve-coach-cli` does for the Claude Code and
Copilot surfaces — a web page cannot run a compiled binary per keystroke, so the adapter is a
local HTTP service instead.

    uvicorn server:app --host 127.0.0.1 --port 8787 --reload

Run it from the repo root. The browser half lives in extension/ and Python never writes there,
which is the point of the split: Chrome refuses to load an unpacked extension containing any name
that starts with an underscore, and __pycache__ is exactly that.

Nothing here listens on a public interface. 127.0.0.1 is your own machine.

## Two ports, not one

The Evolve Coach backend defaults to 8787 as well, and the extension's port is baked into
`manifest.json` (`host_permissions`) and `background.js`. Moving the backend is the cheaper change:

    PORT=8788 bun run dev        # in evolve-coach/projects/backend

`COACH_BACKEND_URL` must then point at it. Nothing else needs touching.

## What the three commands map to

| Command | Backend call |
| --- | --- |
| `/coach:status` | `GET /status?user_id=...` |
| `/coach:dashboard` | `POST /dashboard/provision` |
| `/coach:feedback` | `POST /prompt-feedback` — see the note on that endpoint |

The rendering matches the CLI's word for word: the same glyph legend, the same failure sentences.
A person moving between Claude Code and ChatGPT should not be able to tell which surface answered.
"""

import hmac
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Annotated, Any, Literal
from urllib.parse import quote

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, status as http_status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


# --- Configuration -------------------------------------------------------------------------------
# Read before anything below uses it. `servers=` on the app is evaluated at import time, so a
# setting defined further down the file is a NameError at startup, not a fallback.

PORT_HINT = "http://127.0.0.1:8787"

COACH_BACKEND_URL = os.environ.get("COACH_BACKEND_URL", "http://127.0.0.1:8788").rstrip("/")
COACH_AUTH_TOKEN = os.environ.get("COACH_AUTH_TOKEN")
# Who the coaching is about. The CLI reads this from the AI tool's own config; a web page has no
# equivalent, so it is configuration here. Without it, status and dashboard cannot be asked for.
COACH_USER_ID = os.environ.get("COACH_USER_ID")

# Set this ONLY on an instance that is reachable from outside this machine — a tunnel, or a real
# deploy for a Custom GPT Action. When set, every command route demands it as a bearer token.
#
# Unset is the right setting for the extension: it talks to 127.0.0.1 and sends no credential, and
# adding one would only put a secret in the extension's source. Run two instances rather than one
# compromise — the loopback one for the browser, a key-protected one for anything exposed.
COACH_API_KEY = os.environ.get("COACH_API_KEY")

# The absolute URL a Custom GPT Action should call. It becomes the spec's `servers` entry, which is
# the address ChatGPT uses regardless of where it fetched the spec from.
PUBLIC_BASE_URL = os.environ.get("COACH_PUBLIC_BASE_URL")

# A one-time dashboard link signs its holder in. Handing one to a remote caller is account takeover,
# not a data leak, so on an exposed instance the route is off unless this is deliberately set.
ALLOW_REMOTE_DASHBOARD = os.environ.get("COACH_ALLOW_REMOTE_DASHBOARD") == "1"

SURFACE = "chatgpt"
SURFACE_VERSION = "0.5.0"

# The read budget is generous because /prompt-feedback runs a judge on the backend. It sits under
# the extension's own 40 s abort, so whichever side gives up first, the message names the right
# culprit.
#
# `connect` is not tuned down to fail fast, and deliberately: measured on Windows, a refused
# connection to a dead local port takes ~2 s to come back from the OS itself — a raw
# socket.create_connection is just as slow, so no client setting improves it. Meanwhile a real
# backend across a VPN legitimately needs seconds to connect, and a tight connect timeout would
# turn that into a phantom outage.
TIMEOUT = httpx.Timeout(35.0, connect=5.0)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """One HTTP client for the process, not one per command.

    Measured: constructing and closing an `httpx.AsyncClient` costs ~0.7 s on this machine. Built
    per request, every command paid that before the backend was even contacted.
    """
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        app.state.client = client
        yield


bearer_scheme = HTTPBearer(auto_error=False)


def authorize(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> None:
    """No-op unless COACH_API_KEY is set; a hard gate once it is.

    Comparison is constant-time: a timing oracle on a public endpoint is worth the one import.
    """
    if COACH_API_KEY is None:
        return
    if credentials is None or not hmac.compare_digest(credentials.credentials, COACH_API_KEY):
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
            headers={"WWW-Authenticate": "Bearer"},
        )


Authorized = Depends(authorize)

app = FastAPI(
    title="ChatGPT Coach",
    version="0.5.0",
    lifespan=lifespan,
    description="Evolve Coach status and dashboard access for one configured user.",
    servers=[{"url": PUBLIC_BASE_URL.rstrip("/")}] if PUBLIC_BASE_URL else None,
)

# The extension doesn't rely on this. It calls from a background service worker, which
# host_permissions exempts from CORS altogether. This stays so you can hit the endpoints from the
# devtools console of an open ChatGPT tab while debugging, which is otherwise blocked.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://chatgpt.com", "https://chat.openai.com"],
    allow_methods=["GET"],
)

# Sentences lifted from the CLI so the two surfaces read identically.
NOT_READY = "AI profile not ready yet, more activity needed."
AUTH_FAILURE = "Evolve Coach couldn't authorize this request — check the org-managed token."
UNREACHABLE = "Couldn't reach Evolve Coach, try again."
NOTHING_PENDING = "Nothing pending."
LEGEND = "■ Always ◧ Sometimes □ Never ○ N/A"
GLYPHS = {"always": "■", "sometimes": "◧", "never": "□"}
UNEXPECTED = "Evolve Coach returned an unexpected response — try again in a bit."

NO_USER_ID = (
    "No user is configured, so there is nothing to look up.\n\n"
    "Set COACH_USER_ID to your Evolve Coach user id and restart the service."
)

Outcome = Literal["ok", "unauthorized", "unreachable"]


def bubble(command: str, body: str) -> dict[str, str]:
    """The shape `content.js` renders: it reads `title` and `body`, and nothing else."""
    return {"command": command, "title": f"/coach:{command}", "body": body}


async def call_backend(method: str, path: str, payload: dict[str, Any] | None = None) -> tuple[Outcome, Any]:
    """One request to the coach backend, with the three outcomes the CLI distinguishes.

    `unauthorized` is kept apart from `unreachable` because the two need different things from the
    reader: a token to fix, versus waiting and retrying.
    """
    headers = {"Accept": "application/json"}
    if COACH_AUTH_TOKEN:
        headers["Authorization"] = f"Bearer {COACH_AUTH_TOKEN}"

    try:
        response = await app.state.client.request(method, f"{COACH_BACKEND_URL}{path}", json=payload, headers=headers)
    except httpx.HTTPError:
        # Covers the timeout too. The backend being down is the ordinary case when someone forgets
        # `bun run dev`, so it must never surface as a traceback.
        return "unreachable", None

    if response.status_code in (401, 403):
        return "unauthorized", None
    if not response.is_success:
        return "unreachable", None

    try:
        return "ok", response.json()
    except ValueError:
        return "unreachable", None


@app.get("/health", include_in_schema=False)
async def health() -> dict[str, Any]:
    """Is the service up? Useful as the first thing you curl.

    `ok` stays true whatever the backend is doing: this answers for the adapter, and the
    extension's troubleshooting reads it to decide whether the local half is at fault. The
    backend's state is reported alongside rather than folded in.
    """
    outcome, _ = await call_backend("GET", "/health")
    return {
        "ok": True,
        "coach_backend": {"url": COACH_BACKEND_URL, "reachable": outcome == "ok"},
        "user_configured": bool(COACH_USER_ID),
    }


@app.get("/status", operation_id="coach_status", dependencies=[Authorized])
async def status() -> dict[str, str]:
    if not COACH_USER_ID:
        return bubble("status", NO_USER_ID)

    outcome, body = await call_backend("GET", f"/status?user_id={quote(COACH_USER_ID)}")
    if outcome == "unauthorized":
        return bubble("status", AUTH_FAILURE)
    if outcome != "ok" or not isinstance(body, dict):
        return bubble("status", UNREACHABLE)

    return bubble("status", render_status(body))


def render_status(body: dict[str, Any]) -> str:
    if body.get("ready") is not True:
        return NOT_READY

    lines = [f"Your AI profile: {body.get('ai_profile_name', '')}", ""]

    microskills = [item for item in body.get("microskills", []) if isinstance(item, dict) and "label" in item]
    if not microskills:
        lines.append(NOTHING_PENDING)
        return "\n".join(lines)

    lines.append(LEGEND)
    # Sorted by label, like the CLI: the order must not shift between calls, or a reader cannot
    # tell what changed since last time.
    for item in sorted(microskills, key=lambda item: str(item["label"])):
        lines.append(f"{GLYPHS.get(item.get('mark'), '○')} {item['label']}")
    return "\n".join(lines)


@app.get("/dashboard", operation_id="coach_dashboard", dependencies=[Authorized])
async def dashboard() -> dict[str, str]:
    if COACH_API_KEY is not None and not ALLOW_REMOTE_DASHBOARD:
        return bubble(
            "dashboard",
            "Disabled on this instance.\n\n"
            "A one-time dashboard link signs in whoever holds it, and this instance is reachable\n"
            "from outside this machine. Use the local instance, or set\n"
            "COACH_ALLOW_REMOTE_DASHBOARD=1 if you accept that.",
        )

    if not COACH_USER_ID:
        return bubble("dashboard", NO_USER_ID)

    outcome, body = await call_backend("POST", "/dashboard/provision", {"user_id": COACH_USER_ID})
    if outcome == "unauthorized":
        return bubble("dashboard", AUTH_FAILURE)
    if outcome != "ok" or not isinstance(body, dict):
        return bubble("dashboard", UNREACHABLE)

    token = body.get("token")
    if not isinstance(token, str) or not token:
        return bubble("dashboard", UNEXPECTED)

    # The CLI opens this in the browser itself. A bubble cannot: an extension may not navigate on
    # the page's behalf without a click, so the link is printed for the reader to follow.
    url = f"{COACH_BACKEND_URL}/insights/start?p={token}"
    return bubble(
        "dashboard",
        "Your Evolve Coach dashboard — sign in with your organization account to continue.\n"
        f"One-time link (valid for 2 minutes):\n{url}",
    )


@app.get("/feedback", operation_id="coach_feedback", dependencies=[Authorized])
async def feedback(
    prompt: str | None = Query(default=None, description="The prompt to be judged."),
    chat_id: str = Query(default="chatgpt-web", pattern=r"^[A-Za-z0-9._-]{1,128}$"),
) -> dict[str, str]:
    """Feedback on a prompt — which requires the prompt itself.

    The extension does not send one. That is deliberate and documented in its README: the only
    thing that leaves the page is the command name. Sending a prompt means capturing conversation
    content, which is a decision about what the tool does rather than a detail of how it works — so
    this endpoint accepts `?prompt=` and is ready the moment that decision is made, instead of the
    extension being quietly changed to start reading the thread.
    """
    if not COACH_USER_ID:
        return bubble("feedback", NO_USER_ID)

    if not prompt:
        return bubble(
            "feedback",
            "Feedback needs the prompt it should judge, and the extension does not send one.\n\n"
            "By design: its README states the only thing leaving the page is the command name.\n"
            "Sending your last prompt means capturing conversation content — a product decision,\n"
            "not a bug.\n\n"
            "This endpoint already accepts it:\n"
            f"  {PORT_HINT}/feedback?prompt=<text>",
        )

    submission = {
        "user_id": COACH_USER_ID,
        "chat_id": chat_id,
        # The contract wants an RFC 3339 instant, and its own example uses `Z` rather than +00:00.
        "submitted_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "prompt": {"text": prompt},
        "on_demand": True,
        "surface": {"id": SURFACE, "version": SURFACE_VERSION},
    }

    outcome, body = await call_backend("POST", "/prompt-feedback", submission)
    if outcome == "unauthorized":
        return bubble("feedback", AUTH_FAILURE)
    if outcome != "ok" or not isinstance(body, dict):
        return bubble("feedback", "Coach feedback: No feedback ready yet.")

    if body.get("show") and isinstance(body.get("feedback"), str):
        return bubble("feedback", f"Coach feedback: {body['feedback']}")
    return bubble("feedback", "Coach feedback: The coach reviewed that prompt and has nothing to add.")


@app.get("/", include_in_schema=False)
def index() -> dict[str, Any]:
    """A directory of what exists, so you never have to guess a path."""
    return {
        "service": "chatgpt-coach",
        "surface": SURFACE,
        "coach_backend": COACH_BACKEND_URL,
        "endpoints": [f"{PORT_HINT}{path}" for path in ("/health", "/status", "/feedback", "/dashboard")],
    }
