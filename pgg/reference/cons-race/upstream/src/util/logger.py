"""Convenient experiment-scoped file logger and I/O helper."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, List


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LOG_DIR = PROJECT_ROOT / "logs"


class Logger:
    """Creates a dedicated directory for an experiment under ``./logs`` and
    provides helper methods for interacting with files inside that directory.
    """

    def __init__(
        self,
        name: str,
        base_dir: Path | str | None = None,
        use_timestamp: bool = True,
        timestamp_format: str = "%Y%m%d-%H%M%S",
    ) -> None:
        if not name or not name.strip():
            raise ValueError("Logger name cannot be empty.")

        self.name = name.strip()
        self.base_dir = Path(base_dir) if base_dir else DEFAULT_LOG_DIR
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.timestamp_format = timestamp_format

        experiment_dir_name = self._build_experiment_dir_name(use_timestamp)
        self.experiment_dir = self._create_unique_dir(experiment_dir_name)

    def _build_experiment_dir_name(self, use_timestamp: bool) -> str:
        slug = self._slugify(self.name)

        if use_timestamp:
            timestamp = datetime.now().strftime(self.timestamp_format)
            return f"{timestamp}-{slug}"

        return slug

    def _create_unique_dir(self, dir_name: str) -> Path:
        candidate = self.base_dir / dir_name
        suffix = 1

        while candidate.exists():
            candidate = self.base_dir / f"{dir_name}-{suffix}"
            suffix += 1

        candidate.mkdir(parents=True, exist_ok=False)
        return candidate

    def _resolve_path(self, relative_path: str | Path) -> Path:
        path = Path(relative_path)

        if path.is_absolute():
            raise ValueError("Only relative paths within the experiment directory are supported.")

        full_path = (self.experiment_dir / path).resolve()
        experiment_root = self.experiment_dir.resolve()

        try:
            full_path.relative_to(experiment_root)
        except ValueError as exc:  # pragma: no cover - defensive guard
            raise ValueError("Resolved path escapes the experiment directory.") from exc

        return full_path

    @staticmethod
    def _slugify(value: str) -> str:
        slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value.lower()).strip("-")
        return slug or "experiment"

    def file_path(self, relative_path: str | Path) -> Path:
        """Return the absolute path inside the experiment directory."""
        return self._resolve_path(relative_path)

    def write_text(
        self,
        relative_path: str | Path,
        data: str,
        append: bool = False,
        ensure_newline: bool = False,
    ) -> Path:
        """Write (or append) plain text to a file inside the experiment directory."""
        target = self.file_path(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)

        text = data if data is not None else ""
        if ensure_newline and text and not text.endswith("\n"):
            text += "\n"

        mode = "a" if append else "w"
        with target.open(mode, encoding="utf-8") as stream:
            stream.write(text)

        return target

    def append_text(
        self,
        relative_path: str | Path,
        data: str,
        ensure_newline: bool = True,
    ) -> Path:
        """Append text to a file, creating it (and parents) if needed."""
        return self.write_text(relative_path, data, append=True, ensure_newline=ensure_newline)

    def write_json(
        self,
        relative_path: str | Path,
        payload: Any,
        *,
        indent: int = 2,
        sort_keys: bool = True,
    ) -> Path:
        """Serialize JSON data to a file."""
        target = self.file_path(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)

        with target.open("w", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=indent, sort_keys=sort_keys)
            stream.write("\n")

        return target

    def read_text(self, relative_path: str | Path) -> str:
        """Read text from a file inside the experiment directory."""
        target = self.file_path(relative_path)
        return target.read_text(encoding="utf-8")

    def read_json(self, relative_path: str | Path) -> Any:
        """Read and deserialize JSON from a file inside the experiment directory."""
        target = self.file_path(relative_path)
        with target.open("r", encoding="utf-8") as stream:
            return json.load(stream)

    def log(self, message: str, filename: str = "events.log", timestamp: bool = True) -> Path:
        """Append a timestamped log entry to ``events.log``."""
        entry = message
        if timestamp:
            entry = f"[{datetime.now().isoformat()}] {message}"

        return self.append_text(filename, entry, ensure_newline=True)

    def list_files(self, relative: bool = True) -> List[Path]:
        """Return all files tracked for this experiment."""
        files: Iterable[Path] = (p for p in self.experiment_dir.rglob("*") if p.is_file())
        if relative:
            return sorted(p.relative_to(self.experiment_dir) for p in files)
        return sorted(files)

    def touch(self, relative_path: str | Path) -> Path:
        """Create an empty file (and parent directories) if it does not exist."""
        target = self.file_path(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.touch(exist_ok=True)
        return target

    def __repr__(self) -> str:
        return f"Logger(name='{self.name}', experiment_dir='{self.experiment_dir}')"