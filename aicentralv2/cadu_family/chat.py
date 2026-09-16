"""Compatibility facade. Shared conversations are owned by Workspace."""
from ..cadu_workspace.conversations.service import (
    modes, valid_mode, set_active_mode, update_mode_prompt, reset_mode_prompt,
    lock_organization_generation, prepare, stream,
    repository, dify,
)

__all__ = ['modes', 'valid_mode', 'set_active_mode', 'update_mode_prompt', 'reset_mode_prompt',
           'lock_organization_generation', 'prepare', 'stream']
