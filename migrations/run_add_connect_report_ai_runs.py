#!/usr/bin/env python3
from pathlib import Path
import run_add_connect_report_sources as sources
runner=sources.runner; runner.SQL_PATH=Path(__file__).with_name('add_connect_report_ai_runs.sql')
runner.EXPECTED['cadu_connect_report_ai_runs']={'id','report_id','source_id','created_by','operation','model','usage','status','created_at'}
if __name__=='__main__': runner.main()
