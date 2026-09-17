"""Workspace comum dos agentes e skills da família Cadu."""

from .routes import bp, brand_api_bp
from .brand_audit_jobs import worker_command as brand_audit_worker_command

bp.cli.add_command(brand_audit_worker_command)

__all__ = ["bp", "brand_api_bp"]
