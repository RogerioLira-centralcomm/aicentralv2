"""Create the shared, reviewable Cadu working-memory tables."""
import os
from pathlib import Path
import psycopg
from dotenv import load_dotenv

root = Path(__file__).resolve().parents[1]
load_dotenv(root / '.env')
with psycopg.connect(host=os.getenv('DB_HOST', 'localhost'), port=os.getenv('DB_PORT', '5432'),
                     dbname=os.getenv('DB_NAME', 'aicentralv2'), user=os.getenv('DB_USER', 'postgres'),
                     password=os.getenv('DB_PASSWORD', '')) as connection:
    with connection.cursor() as cursor:
        cursor.execute(Path(__file__).with_name('add_cadu_working_memory.sql').read_text())
