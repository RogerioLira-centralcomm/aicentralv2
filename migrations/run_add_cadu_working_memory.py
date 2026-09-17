"""Create the shared, reviewable Cadu working-memory tables."""
from pathlib import Path

from aicentralv2.db import get_db


def main():
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute(Path(__file__).with_name('add_cadu_working_memory.sql').read_text())
        conn.commit()
    except Exception:
        conn.rollback()
        raise


if __name__ == '__main__':
    main()
