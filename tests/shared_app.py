"""One real Flask app per test process: create_app registers module-level blueprints, so a second call fails."""
_APP = None


def get_app():
    global _APP
    if _APP is None:
        from aicentralv2 import create_app
        _APP = create_app()
    return _APP
