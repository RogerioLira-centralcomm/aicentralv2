"""Delete expired Super Tag events and old rate-limit buckets in bounded batches."""
import os

import psycopg


def main():
    connection = psycopg.connect(
        dbname=os.getenv('DB_NAME', 'aicentral_db'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', 'postgres'),
        host=os.getenv('DB_HOST', 'localhost'),
        port=os.getenv('DB_PORT', '5432'),
    )
    deleted = 0
    try:
        with connection.cursor() as cursor:
            for _ in range(20):
                cursor.execute('''WITH expired AS (
                        SELECT id FROM cadu_reports_supertag_events
                        WHERE expires_at <= NOW() ORDER BY expires_at,id LIMIT 1000
                    ) DELETE FROM cadu_reports_supertag_events e USING expired x
                      WHERE e.id=x.id''')
                deleted += cursor.rowcount
                connection.commit()
                if cursor.rowcount < 1000:
                    break
            cursor.execute('''DELETE FROM cadu_reports_supertag_rate_limits
                WHERE bucket_start < NOW() - INTERVAL '2 days' ''')
            cursor.execute('''DELETE FROM cadu_reports_supertag_ip_rate_limits
                WHERE bucket_start < NOW() - INTERVAL '2 days' ''')
        connection.commit()
    finally:
        connection.close()
    print(f'Removed {deleted} expired Super Tag events.')


if __name__ == '__main__':
    main()
