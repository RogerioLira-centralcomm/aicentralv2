"""Create the manual credit-request workflow table."""
from pathlib import Path
from aicentralv2.db import get_db

sql = Path(__file__).with_name('add_cadu_credit_requests.sql').read_text(encoding='utf-8')
conn = get_db()
with conn.cursor() as cursor:
    cursor.execute(sql)
conn.commit()
print('Migration cadu_credit_requests executada com sucesso.')
