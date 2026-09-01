"""NOT THE REAL BACKEND. A stand-in for Evolve Coach on :8788, for developing the browser half.

The real backend is `evolve-coach/projects/backend` and needs Bun:

    PORT=8788 bun run dev

Use this only when Bun is unavailable, or when you want the surface to answer without the whole
stack up. It returns fixed data, so nothing it says about an AI profile means anything.

It implements only the four routes the adapter calls, with the shapes taken from that backend's
`src/server.ts` and the CLI's parsers — so code that works against this works against the real one.

    python dev_backend_stub.py
"""

import json
from http.server import BaseHTTPRequestHandler, HTTPServer


class Coach(BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split("?")[0]
        query = self.path.split("?")[1] if "?" in self.path else ""
        print(f"[coach] GET {self.path}  auth={self.headers.get('Authorization')}", flush=True)

        if path == "/health":
            return self._json(200, {"ok": True})

        if path == "/status":
            if "user_id=" not in query:
                return self._json(400, {"error": "user_id required"})
            return self._json(
                200,
                {
                    "ready": True,
                    "ai_profile_name": "Collaborator",
                    "microskills": [
                        {"label": "State the goal before the steps", "mark": "always"},
                        {"label": "Give the model the failing output", "mark": "sometimes"},
                        {"label": "Ask for the plan before the patch", "mark": "never"},
                        {"label": "Name the files in scope", "mark": "bogus-value"},
                    ],
                },
            )

        return self._json(404, {"error": "not_found"})

    def do_POST(self):
        path = self.path.split("?")[0]
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        try:
            body = json.loads(raw or b"{}")
        except ValueError:
            body = {}
        print(f"[coach] POST {path}  body={json.dumps(body)[:220]}", flush=True)

        if path == "/dashboard/provision":
            if not body.get("user_id"):
                return self._json(400, {"error": "user_id required"})
            return self._json(200, {"token": "one-time-token-abc123"})

        if path == "/prompt-feedback":
            # Mirror the contract's required fields; a miss should surface as a 400, not silence.
            missing = [f for f in ("user_id", "chat_id", "submitted_at", "prompt") if f not in body]
            if missing:
                return self._json(400, {"error": f"missing: {missing}"})
            return self._json(200, {"show": True, "feedback": "Say what the code should do, not just what broke."})

        return self._json(404, {"error": "not_found"})

    def _json(self, status, body):
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass


print("stub coach backend on :8788", flush=True)
HTTPServer(("127.0.0.1", 8788), Coach).serve_forever()
