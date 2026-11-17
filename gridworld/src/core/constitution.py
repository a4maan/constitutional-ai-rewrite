"""Constitution model that stores the moral code for all agents."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Sequence


@dataclass(slots=True)
class MoralRule:
    """Single moral directive that agents should consider before acting."""

    name: str
    guidance: str
    summary: str | None = None
    priority: int = 0
    tags: tuple[str, ...] = ()

    def render(self) -> str:
        headline = f"{self.name}"
        if self.priority:
            headline = f"{headline} [priority:{self.priority}]"
        if self.summary:
            headline = f"{headline} – {self.summary}"
        body = self.guidance.strip()
        if self.tags:
            tag_line = ", ".join(self.tags)
            body = f"{body} (tags: {tag_line})"
        return f"{headline}\n{body}"


@dataclass(slots=True)
class Constitution:
    """Collection of moral rules shared with every agent."""

    title: str = "Constitution"
    rules: list[MoralRule] = field(default_factory=list)

    def add_rule(self, rule: MoralRule) -> None:
        if any(existing.name == rule.name for existing in self.rules):
            raise ValueError(f"Rule '{rule.name}' already exists in the constitution.")
        self.rules.append(rule)

    def extend(self, rules: Iterable[MoralRule]) -> None:
        for rule in rules:
            self.add_rule(rule)

    def replace_rules(self, rules: Sequence[MoralRule]) -> None:
        names = {rule.name for rule in rules}
        if len(names) != len(rules):
            raise ValueError("Rule names must be unique.")
        self.rules = list(rules)

    def export_rules(self) -> str:
        if not self.rules:
            return f"{self.title}\n(Constitution is currently empty.)"

        # Lower numbers indicate higher priority; sort ascending.
        sorted_rules = sorted(self.rules, key=lambda rule: rule.priority)
        lines = [self.title]
        for idx, rule in enumerate(sorted_rules, start=1):
            lines.append(f"{idx}. {rule.render()}")
        return "\n".join(lines)

    def __str__(self) -> str:
        return self.export_rules()


__all__ = ["MoralRule", "Constitution"]