"""Executor único das ferramentas registradas."""

import time

from .registry import get_tool, validate_arguments


def execute_tool(name, arguments, capabilities):
    tool = get_tool(name)
    if tool.capability not in capabilities:
        raise PermissionError("Usuário sem permissão para esta consulta.")
    if tool.operation_type != "read" or tool.confirmation_required:
        raise PermissionError("Ferramentas de escrita não estão habilitadas.")
    clean = validate_arguments(tool, arguments)
    started = time.monotonic()
    result = tool.handler(**clean)
    duration_ms = round((time.monotonic() - started) * 1000)
    return result, clean, duration_ms
