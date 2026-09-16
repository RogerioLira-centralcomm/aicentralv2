#!/usr/bin/env python3
from pathlib import Path
import run_add_connect_report_sources as sources
runner=sources.runner; runner.SQL_PATH=Path(__file__).with_name('add_connect_report_imports.sql')
runner.EXPECTED['cadu_connect_report_imports']={'id','organization_id','client_id','original_name','sha256','image_bytes','mime_type','supplier','period_start','period_end','status','report_id','created_by','created_at'}
if __name__=='__main__': runner.main()
