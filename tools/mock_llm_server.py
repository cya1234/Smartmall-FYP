"""A scripted stand-in for a local LLM, so the router can be tested without one.

Speaks just enough of the OpenAI chat API for lib/agent/llmRouter.js:

    GET  /v1/models
    POST /v1/chat/completions

The behaviour is chosen per request with the `X-Mock-Mode` header (or MOCK_MODE env
var), which lets one process serve every failure mode the router has to survive:

    normal          classify by keyword, return valid JSON
    garbage         return prose, not JSON         -> router must fall back
    unknown_intent  return an identifier not in the allowlist -> must fall back
    slow            sleep longer than the timeout -> must fall back
    error           HTTP 500                      -> must fall back

    python tools/mock_llm_server.py --port 11434
"""
import argparse
import json
import os
import re
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Deliberately simple keyword rules. This is a stub, not a competitor to the real
# model: its job is to prove the plumbing, and to be wrong in interesting ways.
RULES = [
    ("price_timing", r"減價|平啲|跌價|等唔等|值得等|幾時買|幾時最平|最平|幾時抵|cheaper|price drop|worth waiting|wait for|get cheaper|best time"),
    ("availability", r"有冇貨|有貨|缺貨|現貨|邊間|門市|取貨|in stock|available|which store|pickup"),
    ("size", r"咩碼|乜碼|幾多碼|尺碼|碼數|合身|偏大|偏細|what size|which size|runs? small|runs? large|\bfit\b"),
    ("outfit", r"穿咩|著咩|配搭|搭配|襯咩|造型|場合|整套|推介|what to wear|outfit|put together|style for"),
    ("stores", r"門市喺邊|門市地址|營業時間|store address|opening hours"),
]


def classify(text):
    q = text.lower()
    found = [name for name, pat in RULES if re.search(pat, q)]
    return found or ["product_search"]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.rstrip("/").endswith("/models"):
            return self._send(200, {"object": "list", "data": [{"id": "mock-llm", "object": "model"}]})
        self._send(404, {"error": "not found"})

    def do_POST(self):
        if not self.path.rstrip("/").endswith("/chat/completions"):
            return self._send(404, {"error": "not found"})

        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw or b"{}")
        except Exception:
            return self._send(400, {"error": "bad json"})

        # Mode selection, in priority order:
        #   X-Mock-Mode header  ->  model name "mock-<mode>"  ->  MOCK_MODE env
        # The model name is used by the test harness because the router sends it as a
        # normal request field, so no test-only plumbing is needed in the router.
        model = str(body.get("model") or "")
        from_model = model[len("mock-"):] if model.startswith("mock-") else ""
        mode = self.headers.get("X-Mock-Mode") or from_model or os.environ.get("MOCK_MODE") or "normal"

        if mode == "error":
            return self._send(500, {"error": "mock failure"})
        if mode == "slow":
            time.sleep(6)
            mode = "normal"

        user = ""
        for msg in body.get("messages", []):
            if msg.get("role") == "user":
                user = msg.get("content") or ""

        if mode == "garbage":
            content = "I think the shopper probably wants a jacket. Sorry, no JSON here."
        elif mode == "unknown_intent":
            content = json.dumps({"intents": ["teleport", "vibes"]})
        else:
            content = json.dumps({"intents": classify(user)}, ensure_ascii=False)

        self._send(200, {
            "id": "chatcmpl-mock",
            "object": "chat.completion",
            "model": body.get("model", "mock-llm"),
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }],
            "usage": {"prompt_tokens": len(user) // 4, "completion_tokens": 8, "total_tokens": len(user) // 4 + 8},
        })


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=11434)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"  mock LLM listening on http://{args.host}:{args.port}/v1", flush=True)
    print(f"  default mode: {os.environ.get('MOCK_MODE', 'normal')} "
          f"(override per request with the X-Mock-Mode header)", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
