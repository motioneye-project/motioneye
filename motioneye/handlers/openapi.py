from __future__ import annotations

import json
import os

from motioneye import VERSION, settings
from motioneye.handlers.base import BaseHandler

__all__ = ('OpenApiHandler',)

_SPEC_PATH = os.path.join(settings.PROJECT_PATH, 'openapi.json')


class OpenApiHandler(BaseHandler):
    """Serves the OpenAPI description of the HTTP API, open to anyone, as it
    describes the API and nothing about this server but its version."""

    _spec: str | None = None

    def get(self):
        if OpenApiHandler._spec is None:
            with open(_SPEC_PATH, encoding='utf-8') as f:
                spec = json.load(f)

            spec['info']['version'] = VERSION
            OpenApiHandler._spec = json.dumps(spec)

        self.set_header('Content-Type', 'application/json')
        self.finish(OpenApiHandler._spec)
