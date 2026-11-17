"""FastAPI server that surfaces the live world state."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from visualizer.state import WorldStateSerializer


class VisualizerServer:
    """Wraps FastAPI with live hooks into the environment."""

    def __init__(self, serializer: WorldStateSerializer) -> None:
        self.serializer = serializer
        self.app = FastAPI()
        self._register_routes()

    def _register_routes(self) -> None:
        @self.app.get("/")
        async def index() -> HTMLResponse:
            return HTMLResponse(self.serializer.render_template())

        @self.app.get("/state")
        async def get_state() -> dict[str, Any]:
            return self.serializer.snapshot()

