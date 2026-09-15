"""Customer product shell and scoped context, enabled per deployment."""
from .routes import bp


def register(app):
    import os
    app.config.setdefault('CADU_FAMILY_ENABLED', os.getenv('CADU_FAMILY_ENABLED', '0') == '1')
    app.config.setdefault('CADU_FAMILY_WRITES_ENABLED', False)
    app.register_blueprint(bp)

    @app.context_processor
    def family_flags():
        return {'cadu_family_enabled': app.config['CADU_FAMILY_ENABLED'],
                'cadu_family_writes_enabled': app.config['CADU_FAMILY_WRITES_ENABLED']}
