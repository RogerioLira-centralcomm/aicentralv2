"""Create the durable delivery history for Workspace transactional e-mails."""
from pathlib import Path

from aicentralv2 import create_app
from aicentralv2.db import get_db


def main():
    app = create_app()
    with app.app_context():
        connection = get_db()
        try:
            with connection.cursor() as cursor:
                cursor.execute(Path(__file__).with_name('add_cadu_workspace_email_events.sql').read_text())
            connection.commit()
        except Exception:
            connection.rollback()
            raise


if __name__ == '__main__':
    main()
