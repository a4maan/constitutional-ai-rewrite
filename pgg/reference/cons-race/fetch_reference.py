"""Fetch a small, commit-pinned reference snapshot without running remote code."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import subprocess

REPO = "Arth-Singh/cons-race"
COMMIT = "0853a48aa3ae368b9cb15d053635be5b5e153150"
ROOT = Path(__file__).resolve().parent


def gh(*args):
    return subprocess.check_output(["gh", *args])


def main():
    tree = json.loads(gh("api", f"repos/{REPO}/git/trees/{COMMIT}?recursive=1"))
    if tree.get("truncated"):
        raise RuntimeError("Incomplete upstream tree")
    fixed = {
        "README.md", "RUN_LOGS_README.md", "requirements.txt",
        "openevolve_pgg_config.yaml", "src/environment/pgg.py",
        "src/environment/game.py", "src/config.py", "src/config_prompts.py",
        "src/experiments/pgg_scoring.py", "src/experiments/scoring.py",
        "src/core/pgg_action_mapping.py", "src/core/tools/pgg_registry.py",
        "src/core/langchain_resident.py", "src/util/logger.py", "scripts/coevolution_orchestrator.py",
        "scripts/pgg_coevolution_orchestrator.py", "scripts/evolution/pgg_evaluator.py",
        "scripts/evolution/initial_blue_pgg_constitution.py",
        "scripts/evolution/initial_red_pgg_constitution.py",
        "scripts/experiments/exp4_pgg_coevolution.py",
        "scripts/final_exp4_evolved_cstar.py", "scripts/final_exp5_evolved_cstar_best.py",
        "scripts/final_exp6_evolved_cstar_053.py", "scripts/final_exp7_evolved_cstar_057.py",
    }
    paths = [x["path"] for x in tree["tree"] if x["type"] == "blob" and (
        x["path"] in fixed
        or x["path"].startswith("paper/results/exp4-pgg/")
        or (x["path"].startswith("paper/results/") and "pgg" in x["path"]
            and x["path"].endswith(("evolution_trace.json", ".json"))
            and "/checkpoints/" not in x["path"])
        or (x["path"].startswith("logs/exp4-pgg/blue/") and (
            x["path"].endswith(("/best/best_program_info.json", "/best/best_program.py",
                                "/evolution_trace.jsonl"))))
        or x["path"] == "logs/exp4-pgg/run_config.json"
    )]

    def fetch(path):
        data = gh("api", f"repos/{REPO}/contents/{path}?ref={COMMIT}",
                  "-H", "Accept: application/vnd.github.raw+json")
        dest = ROOT / "upstream" / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return {"path": path, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                "url": f"https://github.com/{REPO}/blob/{COMMIT}/{path}"}

    with ThreadPoolExecutor(max_workers=6) as pool:
        files = list(pool.map(fetch, sorted(paths)))
    (ROOT / "manifest.json").write_text(json.dumps({"repository": REPO,
        "commit": COMMIT, "files": files}, indent=2) + "\n", encoding="utf-8")
    print(f"Fetched {len(files)} pinned files ({sum(x['bytes'] for x in files):,} bytes).")


if __name__ == "__main__":
    main()
