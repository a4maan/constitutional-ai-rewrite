"""Adversarial two-faction gridworld. Subclasses the inherited engine; the engine is not changed."""

from __future__ import annotations

import random

from config import AttackSettings, EnvironmentSettings, HungerSettings, StealSettings
from environment.game import AgentSpawn, CellType, GridWorldEnvironment, ProjectState, ResourcePool

FACTIONS = ("Blue", "Red")
# Neutral names: a name does not show the faction. The seed assigns names to factions.
NAMES = ("Ash", "Birch", "Cedar", "Dune", "Elm", "Fern")


class AdversarialGridWorld(GridWorldEnvironment):
    def __init__(self, game: dict, seed: int) -> None:
        settings = EnvironmentSettings(
            grid_width=game["grid_width"], grid_height=game["grid_height"],
            max_turns=game["turns"], random_seed=seed, reveal_teams=False,
            hunger=HungerSettings(enabled=False),
            attack=AttackSettings(enabled=True, success_chance=game["attack_success"]),
            steal=StealSettings(enabled=True, success_chance=game["steal_success"]),
        )
        super().__init__(settings)  # engine dice: random.Random(seed)
        self.game = game
        self.projects = {name: ProjectState(name, dict(required))
                         for faction in FACTIONS
                         for name, required in game["projects"][faction].items()}
        self.project_owner = {name: faction for faction in FACTIONS
                              for name in game["projects"][faction]}
        n = game["agents_per_faction"]
        if not 1 <= n <= len(NAMES) // 2:
            raise ValueError("agents_per_faction must be between 1 and 3")
        setup = random.Random(f"setup-{seed}")
        names = list(NAMES[: 2 * n])
        setup.shuffle(names)
        self.faction_of = {name: FACTIONS[i // n] for i, name in enumerate(names)}
        self._build_grid()
        empty = [(r, c) for r in range(self.settings.grid_height) for c in range(self.settings.grid_width)
                 if self.grid[r][c].cell_type == CellType.EMPTY]
        cells = setup.sample(empty, len(names))
        self.reset([AgentSpawn(name, self.faction_of[name], cell) for name, cell in zip(sorted(names), cells)])
        self.spawns = {name: list(cell) for name, cell in zip(sorted(names), cells)}
        self._order_rng = random.Random(f"order-{seed}")

    def _build_grid(self):
        """Map of the old adversarial gridworld (Arth-Singh/cons-race src/environment/game.py _build_grid,
        described there; this code is written new). Top half: wood in the left half of the columns, stone in
        the next columns up to the last 2, gems in the last 2 columns of the first 2 rows. Everything else is
        empty (hunger is off, so no food). The wood projects (shelter, fortress) share the top-left corner;
        the stone/gem projects (market, armory) share the bottom-right corner. Pool sizes as in the old game."""
        super()._build_grid()
        h, w = self.settings.grid_height, self.settings.grid_width
        for r in range(h):
            for c in range(w):
                cell = self.grid[r][c]
                cell.resources.clear()
                if r < h // 2 and c < w // 2:
                    cell.cell_type, cell.resources["wood"] = CellType.WOOD, ResourcePool(20, 20, 4)
                elif r < h // 2 and c < w - 2:
                    cell.cell_type, cell.resources["stone"] = CellType.STONE, ResourcePool(16, 16, 3)
                elif r < 2:
                    cell.cell_type, cell.resources["gems"] = CellType.GEM, ResourcePool(6, 6, 1)
                else:
                    cell.cell_type = CellType.EMPTY
        self.grid[0][0].cell_type = CellType.SHELTER
        self.grid[0][0].resources.clear()
        self.grid[h - 1][w - 1].cell_type = CellType.MARKET

    def project_location(self, project):
        """Old game: wood projects at the top-left corner, stone/gem projects at the bottom-right corner."""
        if "wood" in self.projects[project].required:
            return [0, 0]
        return [self.settings.grid_height - 1, self.settings.grid_width - 1]

    # Ben (2026-11-28): deposits go only to the agent's own projects, and only on the project's cell.
    # The old game accepted deposits from any cell and into any project; both are changed on purpose.
    def _handle_deposit(self, agent_id, resource, project):
        state = self.agent_states.get(agent_id)
        if not state or self.project_owner.get(project) != state.team_id:
            return {"agent": agent_id, "error": f"{project} is not one of your projects."}
        if list(state.position) != self.project_location(project):
            return {"agent": agent_id,
                    "error": f"Stand on the {project} location {self.project_location(project)} to deposit."}
        return super()._handle_deposit(agent_id, resource, project)

    def view(self, position):
        """3x3 terrain and resident names around a position (no faction labels)."""
        cells = []
        row, col = position
        for r in range(max(0, row - 1), min(self.settings.grid_height, row + 2)):
            for c in range(max(0, col - 1), min(self.settings.grid_width, col + 2)):
                cell = self.grid[r][c]
                item = {"pos": [r, c], "terrain": cell.cell_type.value,
                        "residents": sorted(cell.agents_present)}
                # As in the old game's local view: dropped items and remains of removed residents.
                dropped = {k: v for k, v in cell.dropped_items.items() if v > 0}
                if dropped:
                    item["dropped_items"] = dropped
                if cell.corpses:
                    item["remains"] = [{"who": x.resident_id, "turn": x.turn} for x in cell.corpses]
                cells.append(item)
        return cells

    def observe(self, name: str) -> dict:
        state = self.agent_states[name]
        k = self.game["messages_shown"]
        own = [p for p, f in self.project_owner.items() if f == state.team_id]
        return {
            "turn": self.turn + 1, "turns_total": self.settings.max_turns, "you": name,
            "position": list(state.position),
            "inventory": {r: state.inventory[r] for r in ("wood", "stone", "gems")},
            "your_projects": {p: {"required": self.projects[p].required,
                                  "stored": {r: self.projects[p].stored.get(r, 0)
                                             for r in self.projects[p].required}} for p in own},
            "deposit_locations": {p: {"position": self.project_location(p),
                                      "accepts": list(self.projects[p].required)} for p in own},
            "nearby": self.view(state.position),
            "residents": [{"name": n, "alive": s.alive} for n, s in sorted(self.agent_states.items())],
            "public_messages": state.inbox_public[-k:],
            "private_messages": state.inbox_private[-k:],
            "notifications": list(state.notifications),
        }

    def play_turn(self, decisions: dict) -> tuple[list, list]:
        """Apply decisions (name -> list of (request_dict, ActionRequest)) in a seeded random order."""
        self.turn += 1
        order = list(self.agent_states)
        self._order_rng.shuffle(order)
        log = []
        for name in order:
            entry = {"agent": name, "results": []}
            for request, action in decisions.get(name, []):
                if not self.agent_states[name].alive:
                    entry["results"].append({"request": request, "skipped": "agent removed earlier this turn"})
                    continue
                result = self._dispatch_action(name, action)
                entry["results"].append({"request": request, "result": result,
                                         "events": list(self._pending_events)})
                self._pending_events.clear()
            log.append(entry)
        self._regenerate_resources()
        return order, log

    def snapshot(self) -> dict:
        return {
            "positions": {n: list(s.position) for n, s in self.agent_states.items()},
            "inventories": {n: dict(s.inventory) for n, s in self.agent_states.items()},
            "alive": {n: s.alive for n, s in self.agent_states.items()},
            "projects": {p: dict(ps.stored) for p, ps in self.projects.items()},
            "pools": [[{r: pool.amount for r, pool in cell.resources.items()} for cell in row]
                      for row in self.grid],
        }
