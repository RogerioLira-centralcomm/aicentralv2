#!/usr/bin/env python3
"""Run the incremental report-source migration using the same atomic runner."""
from pathlib import Path
import run_add_connect_report_workspace as runner

runner.SQL_PATH = Path(__file__).with_name('add_connect_report_sources.sql')
runner.EXPECTED['cadu_connect_report_sources'] = {
    'id', 'report_id', 'batch_id', 'sha256', 'image_bytes', 'mime_type',
    'width', 'height', 'supplier', 'period_start', 'period_end', 'status',
    'original_name', 'created_by', 'created_at',
}

if __name__ == '__main__':
    runner.main()
