"""OpenRouter client with 1 pinned upstream provider, a response cache, and a request journal.

Same cache and journal design as Armaan's `experiment 1/groq_model.py`, without the Groq quota ledger.
The API key is read from the environment and is never written to the journal.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
import threading
import time
import urllib.error
import urllib.request

from exp1.agents import response_schema

URL = "https://openrouter.ai/api/v1/chat/completions"
RETRIES = 3  # retries after the first attempt


class BudgetExceeded(RuntimeError):
    """The run reached its cost cap. The run stops."""


class ModelFailed(RuntimeError):
    """A request that failed after all retries. Never scored; the game fails."""


class OpenRouterModel:
    def __init__(self, model, journal, max_calls, settings):
        self.model = model
        self.journal = journal
        self.max_calls = max_calls
        self.settings = settings
        self.provider = settings["openrouter_provider"]
        self.key = os.environ["OPENROUTER_API_KEY"]
        self.cache = journal.path.parent / "model-cache"
        self.cache.mkdir(exist_ok=True)
        self.lock = threading.Lock()
        self.calls = sum(1 for line in journal.path.read_text().splitlines()
                         if json.loads(line).get("event") == "model_request") if journal.path.exists() else 0
        self.usage = {"prompt_tokens": 0, "completion_tokens": 0, "cost": 0.0}
        self.max_cost = None  # USD; set by the command line (--max-cost)

    def complete(self, messages, seed, purpose):
        body = {"model": self.model, "messages": messages, "temperature": 1, "seed": seed,
                "max_tokens": self.settings.get("max_completion_tokens", 700),
                "reasoning": {"effort": "low"},
                "response_format": (response_schema(purpose) if self.settings.get("strict_schema")
                                    else {"type": "json_object"}),
                "provider": {"order": [self.provider], "allow_fallbacks": False}}
        if self.settings.get("strict_schema"):
            body["provider"]["require_parameters"] = True  # fail rather than ignore the schema
        encoded = json.dumps(body, sort_keys=True, separators=(",", ":"))
        key = hashlib.sha256(encoded.encode()).hexdigest()
        path = self.cache / (key + ".json")
        if path.exists():
            self.journal.event("model_cache_hit", cache_key=key, purpose=purpose)
            return json.loads(path.read_text())["answer"]
        last_error = None
        for attempt in range(1, RETRIES + 2):
            with self.lock:
                if self.max_cost is not None and self.usage["cost"] >= self.max_cost:
                    raise BudgetExceeded(f"cost cap ${self.max_cost} reached (${self.usage['cost']:.4f})")
                if self.calls >= self.max_calls:
                    raise RuntimeError("model call budget exhausted")
                self.calls += 1
                call = self.calls
            self.journal.event("model_request", call=call, purpose=purpose, attempt=attempt,
                               cache_key=key, body=body)
            started = time.time()
            request = urllib.request.Request(URL, data=json.dumps(body, separators=(",", ":")).encode(),
                                             method="POST",
                                             headers={"Authorization": "Bearer " + self.key,
                                                      "Content-Type": "application/json",
                                                      "User-Agent": "gridworld-experiment/1.0"})
            try:
                with urllib.request.urlopen(request, timeout=180) as response:
                    raw = response.read().decode()
                payload = json.loads(raw)
                usage = payload.get("usage", {})
                self.journal.event("model_response", call=call, provider=payload.get("provider"),
                                   seconds=round(time.time() - started, 3), usage=usage, raw=raw)
                with self.lock:
                    self.usage["prompt_tokens"] += usage.get("prompt_tokens", 0)
                    self.usage["completion_tokens"] += usage.get("completion_tokens", 0)
                    self.usage["cost"] += usage.get("cost") or 0.0
                if "error" in payload or not payload.get("choices"):
                    raise ValueError(f"error payload: {payload.get('error')}")
                if str(payload.get("provider", "")).lower() != self.provider.lower():
                    raise ValueError(f"answered by {payload.get('provider')!r}, not {self.provider!r}")
                choice = payload["choices"][0]
                if choice.get("finish_reason") == "length":
                    raise ValueError("model response truncated")
                answer = json.loads(choice["message"]["content"])
                path.write_text(json.dumps({"answer": answer, "response": payload, "request": body}))
                return answer
            except urllib.error.HTTPError as exc:
                error_body = exc.read().decode(errors="replace")
                self.journal.event("model_http_error", call=call, status=exc.code, body=error_body)
                if exc.code not in (408, 429, 500, 502, 503, 504):
                    raise RuntimeError(f"OpenRouter HTTP {exc.code}: {error_body}") from exc
                last_error = f"HTTP {exc.code}"
            except (TimeoutError, urllib.error.URLError, ConnectionError) as exc:
                self.journal.event("model_transport_error", call=call, error=str(exc))
                last_error = str(exc)
            except ValueError as exc:
                # Truncated or non-JSON content is a property of the answer, not a transport failure.
                # The agent policy logs it as an invalid output (open point 3). Not retried.
                if str(exc) == "model response truncated" or isinstance(exc, json.JSONDecodeError):
                    raise
                self.journal.event("model_bad_response", call=call, error=str(exc))
                last_error = str(exc)
            if attempt <= RETRIES:
                time.sleep(min(5 * 2 ** attempt, 60))
        self.journal.event("model_failed", purpose=purpose, cache_key=key, error=last_error)
        raise ModelFailed(f"OpenRouter request failed after {RETRIES} retries: {last_error}")
