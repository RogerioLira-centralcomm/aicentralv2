#!/usr/bin/env python3
from pathlib import Path
import run_add_connect_report_sources as sources

runner = sources.runner
runner.SQL_PATH = Path(__file__).with_name('add_connect_report_public_links.sql')
runner.EXPECTED['cadu_connect_report_public_links'] = {
    'id', 'report_id', 'token', 'expires_at', 'revoked_at', 'created_by', 'created_at',
}

if __name__ == '__main__':
    runner.main()
