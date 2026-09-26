"""Apply the additive schema for the public Planner portal directory."""
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv


def main():
    root = Path(__file__).resolve().parents[1]
    load_dotenv(root / '.env')
    with psycopg.connect(host=os.getenv('DB_HOST', 'localhost'),
                         port=int(os.getenv('DB_PORT', '5432')),
                         dbname=os.getenv('DB_NAME', 'aicentralv2'),
                         user=os.getenv('DB_USER', 'postgres'),
                         password=os.getenv('DB_PASSWORD', '')) as conn:
        conn.execute(Path(__file__).with_name('add_cadu_planner_portals.sql').read_text())
    print('Planner: catálogo de portais criado.')


if __name__ == '__main__':
    main()
