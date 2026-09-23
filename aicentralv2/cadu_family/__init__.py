"""Customer product shell and scoped context, enabled per deployment."""
from .routes import bp


def register(app):
    import os
    app.config.setdefault('CADU_FAMILY_ENABLED', os.getenv('CADU_FAMILY_ENABLED', '0') == '1')
    app.config.setdefault('CADU_FAMILY_WRITES_ENABLED', False)
    app.register_blueprint(bp)
    # Operational commands are top-level so deployment runbooks can use the
    # documented `flask conversation-memory-*` names without a blueprint group.
    from ..cadu_workspace.conversations.conversation_memory import rebuild_command
    from ..cadu_workspace.agent_v2.memory_checkpoint import worker_command as memory_worker_command
    app.cli.add_command(rebuild_command)
    app.cli.add_command(memory_worker_command)

    @app.context_processor
    def family_flags():
        return {'cadu_family_enabled': app.config['CADU_FAMILY_ENABLED'],
                'cadu_family_writes_enabled': app.config['CADU_FAMILY_WRITES_ENABLED']}
