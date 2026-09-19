"""Backend runtime for Cadu Conversations V2.

The package deliberately has no dependency on the chat UI.  Its contracts,
router and tool registry are shared by the HTTP API and the internal MCP
adapter.
"""

from .router import route_request

__all__ = ["route_request"]
