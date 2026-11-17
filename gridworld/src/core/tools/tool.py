"""Tool abstractions for constitutional optimization.

The helpers in this module make it straightforward to declare tools as plain
functions, Pydantic models, or reusable base classes and then export them in
the shape expected by OpenRouter's
`tools` parameter. See https://openrouter.ai/docs/features/tool-calling
for the underlying wire format.
"""

from __future__ import annotations

import asyncio
import inspect
from abc import ABC, abstractmethod
from typing import Any, Callable, ClassVar

from pydantic import BaseModel, ConfigDict, Field

ToolCallable = Callable[..., Any]
DEFAULT_PARAMETERS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {},
    "additionalProperties": True,
}


class Tool(BaseModel):
    """Concrete tool definition bound to a callable handler."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    description: str
    parameters: dict[str, Any] | None = None
    returns: dict[str, Any] | None = None
    examples: list[dict[str, Any]] = Field(default_factory=list)
    handler: ToolCallable | None = Field(default=None, repr=False)
    args_model: type[BaseModel] | None = Field(default=None, repr=False)
    result_model: type[BaseModel] | None = Field(default=None, repr=False)

    def model_post_init(self, __context: Any) -> None:  # type: ignore[override]
        if self.args_model and self.parameters is None:
            self.parameters = self.args_model.model_json_schema()
        if self.result_model and self.returns is None:
            self.returns = self.result_model.model_json_schema()

    # ------------------------------------------------------------------ #
    # Export helpers
    # ------------------------------------------------------------------ #
    def export(self) -> dict[str, Any]:
        """Return the OpenRouter-ready tool definition."""
        schema = self.parameters or DEFAULT_PARAMETERS_SCHEMA
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": schema,
            },
        }

    # ------------------------------------------------------------------ #
    # Invocation helpers
    # ------------------------------------------------------------------ #
    def __call__(self, __arguments: dict[str, Any] | BaseModel | None = None, **kwargs: Any) -> Any:
        return self.invoke(__arguments, **kwargs)

    def invoke(self, __arguments: dict[str, Any] | BaseModel | None = None, **kwargs: Any) -> Any:
        """Synchronously execute the underlying handler."""
        prepared = self._prepare_arguments(__arguments, **kwargs)
        kwargs_ready = self._as_kwargs(prepared)
        result = self._execute_handler(kwargs_ready)
        return self._serialize_result(result)

    async def ainvoke(self, __arguments: dict[str, Any] | BaseModel | None = None, **kwargs: Any) -> Any:
        """Asynchronously execute the underlying handler."""
        prepared = self._prepare_arguments(__arguments, **kwargs)
        kwargs_ready = self._as_kwargs(prepared)
        result = await self._execute_handler_async(kwargs_ready)
        return self._serialize_result(result)

    def _prepare_arguments(self, arguments: dict[str, Any] | BaseModel | None, **kwargs: Any) -> dict[str, Any] | BaseModel:
        payload: dict[str, Any]
        if arguments is None:
            payload = {}
        elif isinstance(arguments, BaseModel):
            payload = arguments.model_dump()
        else:
            payload = dict(arguments)
        if kwargs:
            payload.update(kwargs)
        if self.args_model:
            return self.args_model(**payload)
        return payload

    @staticmethod
    def _as_kwargs(payload: dict[str, Any] | BaseModel) -> dict[str, Any]:
        if isinstance(payload, BaseModel):
            return payload.model_dump()
        return payload

    def _execute_handler(self, kwargs_ready: dict[str, Any]) -> Any:
        if self.handler is None:
            raise RuntimeError(f"Tool '{self.name}' does not have a bound handler.")
        result = self.handler(**kwargs_ready)
        if inspect.isawaitable(result):
            return asyncio.run(result)  # pragma: no cover - convenience fallback
        return result

    async def _execute_handler_async(self, kwargs_ready: dict[str, Any]) -> Any:
        if self.handler is None:
            raise RuntimeError(f"Tool '{self.name}' does not have a bound handler.")
        result = self.handler(**kwargs_ready)
        if inspect.isawaitable(result):
            result = await result
        return result

    def _serialize_result(self, result: Any) -> Any:
        if result is None:
            return None
        if isinstance(result, BaseModel):
            return result.model_dump()
        if self.result_model and isinstance(result, self.result_model):
            return result.model_dump()
        return result

    # ------------------------------------------------------------------ #
    # Construction helpers
    # ------------------------------------------------------------------ #
    @classmethod
    def from_callable(
        cls,
        func: ToolCallable,
        *,
        name: str | None = None,
        description: str | None = None,
        parameters_model: type[BaseModel] | None = None,
        returns_model: type[BaseModel] | None = None,
        examples: list[dict[str, Any]] | None = None,
        parameters_schema: dict[str, Any] | None = None,
        returns_schema: dict[str, Any] | None = None,
    ) -> "Tool":
        """Build a Tool from a plain Python callable."""
        doc = description or inspect.getdoc(func) or "No description provided."
        return cls(
            name=name or func.__name__,
            description=doc.strip(),
            handler=func,
            args_model=parameters_model,
            result_model=returns_model,
            parameters=parameters_schema,
            returns=returns_schema,
            examples=examples or [],
        )


def tool(
    *,
    name: str | None = None,
    description: str | None = None,
    parameters_model: type[BaseModel] | None = None,
    returns_model: type[BaseModel] | None = None,
    parameters_schema: dict[str, Any] | None = None,
    returns_schema: dict[str, Any] | None = None,
    examples: list[dict[str, Any]] | None = None,
) -> Callable[[ToolCallable], Tool]:
    """Decorator that converts a function into a Tool instance."""

    def decorator(func: ToolCallable) -> Tool:
        tool_obj = Tool.from_callable(
            func,
            name=name,
            description=description,
            parameters_model=parameters_model,
            returns_model=returns_model,
            parameters_schema=parameters_schema,
            returns_schema=returns_schema,
            examples=examples,
        )

        # Retain the original callable for direct execution while exposing the
        # Tool metadata via ``tool_obj.original_callable``.
        tool_obj.original_callable = func  # type: ignore[attr-defined]
        return tool_obj

    return decorator


class _EmptyArgs(BaseModel):
    pass


class BaseTool(ABC):
    """Base class for defining reusable tools as objects."""

    name: ClassVar[str]
    description: ClassVar[str]
    Args: ClassVar[type[BaseModel]] = _EmptyArgs
    Returns: ClassVar[type[BaseModel] | None] = None
    examples: ClassVar[list[dict[str, Any]]] = []

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if cls is BaseTool:
            return
        if not getattr(cls, "name", None):
            raise ValueError("Tool subclasses must define a 'name'.")
        if not getattr(cls, "description", None):
            raise ValueError("Tool subclasses must define a 'description'.")

    async def _call_wrapper(self, **kwargs: Any) -> Any:
        payload: BaseModel | dict[str, Any]
        if self.Args is _EmptyArgs:
            payload = kwargs
        else:
            payload = self.Args(**kwargs)

        result = self.run(payload)
        if inspect.isawaitable(result):
            result = await result
        return result

    def to_tool(self) -> Tool:
        """Convert the BaseTool instance into a Tool."""
        args_model = None if self.Args is _EmptyArgs else self.Args
        returns_model = None if self.Returns in (None, _EmptyArgs) else self.Returns
        return Tool(
            name=self.name,
            description=self.description,
            handler=self._call_wrapper,
            args_model=args_model,
            result_model=returns_model,
            examples=list(self.examples),
        )

    def export(self) -> dict[str, Any]:
        """Return the OpenRouter-ready definition."""
        return self.to_tool().export()

    def __call__(self, **kwargs: Any) -> Any:
        """Allow invoking the BaseTool instance directly."""
        return self.to_tool().invoke(kwargs)

    @abstractmethod
    def run(self, params: BaseModel | dict[str, Any]) -> Any:
        """Implement the actual tool logic."""
        raise NotImplementedError


__all__ = ["Tool", "tool", "BaseTool"]