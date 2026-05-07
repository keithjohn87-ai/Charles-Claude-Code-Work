"""Importing this package registers all tools via @tool decorators."""
from . import (  # noqa: F401
    filesystem,
    goals,
    memory,
    notify,
    scheduler,
    self_modify,
    shell,
    time,
    weather,
)
