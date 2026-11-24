"""Durable Groq requests with a shared rolling quota ledger and response cache."""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import time
import urllib.error
import urllib.request

from pgg.replay import write_trace


def compact_observation(observation):
    """Keep all past actions and resulting balances, avoiding redundant settlement fields."""
    names = [row["name"] for row in observation["players"]]
    return {
        **{key: value for key, value in observation.items() if key != "history"},
        "history_encoding": "Each round lists actions and ending wallets in players order. "
        "Pool returns and penalties follow the game rules. Full settlement details can be reconstructed.",
        "initial_wallets": [observation["history"][0]["wallets_before"][name]
                            if observation["history"] else observation["players"][i]["wallet"]
                            for i, name in enumerate(names)],
        "history": [
            {"round": row["round"], "actions": [
                {key: value for key, value in row["actions"][name].items()
                 if key == "kind" or (key == "fraction" and row["actions"][name]["kind"] == "contribute")
                 or (key in ("target", "amount") and row["actions"][name]["kind"] == "punish")
                 or (key == "message" and row["actions"][name]["kind"] == "broadcast")}
                for name in names],
             "ending_wallets": [row["wallets_after"][name] for name in names]}
            for row in observation["history"]],
    }


class GroqModel:
    def __init__(self, model, journal, max_calls, settings):
        import tiktoken
        self.encoder = tiktoken.get_encoding("o200k_base")
        self.model = model
        self.journal = journal
        self.max_calls = max_calls
        self.settings = settings
        self.cache = journal.path.parent / "model-cache"
        self.cache.mkdir(exist_ok=True)
        keys_file = os.environ.get("GROQ_KEYS_FILE")
        keys = json.loads(Path(keys_file).read_text()) if keys_file else [os.environ["GROQ_API_KEY"]]
        if len(set(keys)) != len(keys) or any(not isinstance(key, str) or not key for key in keys):
            raise ValueError("provide distinct nonempty API keys")
        self.accounts = []
        for index, key in enumerate(keys):
            ledger_path = self.cache / f"quota-account-{index + 1}.json"
            self.accounts.append({"key": key, "label": f"account-{index + 1}", "path": ledger_path,
                "ledger": json.loads(ledger_path.read_text()) if ledger_path.exists() else []})
        self.calls = sum(1 for line in journal.path.read_text().splitlines()
                         if json.loads(line).get("event") == "model_request") if journal.path.exists() else 0

    def wait(self, seconds, reason):
        self.journal.event("quota_wait", seconds=seconds, reason=reason,
                           resume_utc=datetime.fromtimestamp(time.time() + seconds, timezone.utc).isoformat())
        write_trace(self.journal.path.parent / "progress.json",
                    {"state": "waiting", "reason": reason, "seconds": seconds,
                     "resume_utc": datetime.fromtimestamp(time.time() + seconds, timezone.utc).isoformat()})
        time.sleep(max(0, seconds))

    def reserve(self, tokens):
        limits = self.settings["rate_limits"]
        if tokens > limits["tokens_per_minute"]:
            raise ValueError(f"request reserves {tokens} tokens, exceeding minute allowance")
        while True:
            now = time.time()
            options = []
            for account in self.accounts:
                account["ledger"] = [row for row in account["ledger"] if now - row["time"] < 86401]
                waits = []
                for seconds, requests, token_limit in (
                    (61, limits["requests_per_minute"], limits["tokens_per_minute"]),
                    (86401, limits["requests_per_day"], limits["tokens_per_day"]),
                ):
                    rows = [row for row in account["ledger"] if now - row["time"] < seconds]
                    if len(rows) >= requests or sum(row["tokens"] for row in rows) + tokens > token_limit:
                        waits.append(rows[0]["time"] + seconds - now + 1)
                wait = max([0, account.get("blocked_until", 0) - now, *waits])
                if tokens > account.get("remote_tokens", float("inf")):
                    wait = max(wait, account.get("remote_reset", 0) - now)
                if account.get("remote_requests", 1) <= 0:
                    wait = max(wait, account.get("requests_reset", 0) - now)
                options.append((wait, len(account["ledger"]), account))
            delay, _, account = min(options, key=lambda option: option[:2])
            if delay <= 0:
                entry = {"time": now, "tokens": tokens}
                account["ledger"].append(entry)
                write_trace(account["path"], account["ledger"])
                return entry, account
            self.wait(delay, "all accounts at rolling request/token budget")

    def complete(self, messages, seed, purpose):
        body = {"model": self.model, "messages": messages, "temperature": 1,
                "seed": seed, "max_completion_tokens": self.settings.get("max_completion_tokens", 700),
                "reasoning_effort": "low", "response_format": {"type": "json_object"}}
        encoded = json.dumps(body, sort_keys=True, separators=(",", ":"))
        key = hashlib.sha256(encoded.encode()).hexdigest()
        path = self.cache / (key + ".json")
        if path.exists():
            self.journal.event("model_cache_hit", cache_key=key, purpose=purpose)
            return json.loads(path.read_text())["answer"]
        tokens = len(self.encoder.encode(json.dumps(messages, separators=(",", ":")))) + body["max_completion_tokens"] + 256
        for attempt in range(1, 9):
            if self.calls >= self.max_calls:
                raise RuntimeError("model call budget exhausted")
            entry, account = self.reserve(tokens)
            self.calls += 1
            self.journal.event("model_request", call=self.calls, purpose=purpose,
                               attempt=attempt, account=account["label"], cache_key=key,
                               reserved_tokens=tokens, body=body)
            write_trace(self.journal.path.parent / "progress.json",
                        {"state": "requesting", "purpose": purpose, "calls": self.calls,
                         "time_utc": datetime.now(timezone.utc).isoformat()})
            request = urllib.request.Request("https://api.groq.com/openai/v1/chat/completions",
                data=json.dumps(body, separators=(",", ":")).encode(), method="POST",
                headers={"Authorization": "Bearer " + account["key"],
                         "Content-Type": "application/json", "User-Agent": "pgg-experiment/1.0"})
            try:
                with urllib.request.urlopen(request, timeout=120) as response:
                    raw = response.read().decode()
                    headers = dict(response.headers)
                self.journal.event("model_response", call=self.calls, raw=raw, headers=headers)
                payload = json.loads(raw)
                lower = {key.lower(): value for key, value in headers.items()}
                def reset_seconds(value):
                    units = {"ms": .001, "s": 1, "m": 60, "h": 3600, "d": 86400}
                    return sum(float(number) * units[unit] for number, unit in
                               re.findall(r"([\d.]+)(ms|s|m|h|d)", value))
                account["remote_tokens"] = float(lower.get("x-ratelimit-remaining-tokens", "inf"))
                account["remote_requests"] = float(lower.get("x-ratelimit-remaining-requests", "inf"))
                account["remote_reset"] = time.time() + reset_seconds(lower.get("x-ratelimit-reset-tokens", "0s")) + 1
                account["requests_reset"] = time.time() + reset_seconds(lower.get("x-ratelimit-reset-requests", "0s")) + 1
                usage = payload.get("usage", {})
                cached = usage.get("prompt_tokens_details", {}).get("cached_tokens", 0)
                entry["tokens"] = usage.get("total_tokens", tokens) - cached
                write_trace(account["path"], account["ledger"])
                message = payload["choices"][0]["message"]
                answer = json.loads(message["content"])
                if payload["choices"][0].get("finish_reason") == "length":
                    raise ValueError("model response truncated")
                write_trace(path, {"answer": answer, "response": payload, "request": body})
                return answer
            except urllib.error.HTTPError as exc:
                error_body = exc.read().decode(errors="replace")
                self.journal.event("model_http_error", call=self.calls, status=exc.code,
                                   body=error_body, headers=dict(exc.headers))
                if exc.code not in (429, 500, 502, 503, 504):
                    raise RuntimeError(f"Groq HTTP {exc.code}: {error_body}") from exc
                delay = max(float(exc.headers.get("retry-after", 0)), min(60 * 2**attempt, 3600)) + 2
                account["blocked_until"] = time.time() + delay
            except (TimeoutError, urllib.error.URLError) as exc:
                self.journal.event("model_transport_error", call=self.calls, error=str(exc))
                self.wait(min(10 * 2**attempt, 300), "transport retry")
        raise RuntimeError("Groq retry limit exhausted")
