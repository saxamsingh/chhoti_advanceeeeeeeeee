"""FastAPI dependencies: everything a route needs comes from `app.state`, set once by the factory."""

from __future__ import annotations

from fastapi import Request

from .channels.notify import Notifier
from .config import Settings
from .db import Repository
from .tinyfish import WebClient


def settings_dep(request: Request) -> Settings:
    return request.app.state.settings


def repo_dep(request: Request) -> Repository:
    return request.app.state.repo


def web_dep(request: Request) -> WebClient:
    return request.app.state.web


def notifier_dep(request: Request) -> Notifier:
    return request.app.state.notifier
