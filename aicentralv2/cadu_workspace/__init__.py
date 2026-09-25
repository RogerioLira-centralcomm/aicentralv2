"""Workspace comum dos agentes e skills da família Cadu."""

from .routes import bp, brand_api_bp
from .brand_audit_jobs import (
    worker_command as brand_audit_worker_command,
    worker_loop_command as brand_audit_worker_loop_command,
    enqueue_all_deep_command,
)
from .project_index_jobs import worker_command as project_index_worker_command
from .project_resource_jobs import worker_command as project_resource_worker_command, worker_loop_command as project_resource_worker_loop_command
from .agent_v2.long_job_worker import worker_command as long_job_worker_command
from .link_icon_jobs import worker_command as link_icon_worker_command, worker_loop_command as link_icon_worker_loop_command

bp.cli.add_command(brand_audit_worker_command)
bp.cli.add_command(brand_audit_worker_loop_command)
bp.cli.add_command(enqueue_all_deep_command)
bp.cli.add_command(project_index_worker_command)
bp.cli.add_command(project_resource_worker_command)
bp.cli.add_command(project_resource_worker_loop_command)
bp.cli.add_command(long_job_worker_command)
bp.cli.add_command(link_icon_worker_command)
bp.cli.add_command(link_icon_worker_loop_command)

__all__ = ["bp", "brand_api_bp"]
