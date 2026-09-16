"""Inbox-level validation before an import is associated with a campaign."""
from datetime import date
from .report_sources import prepare_image


def validate_inbox_upload(upload, form):
    image = prepare_image(upload)
    supplier = str(form.get('supplier') or '').strip()
    if len(supplier) > 200: raise ValueError('Fornecedor deve ter até 200 caracteres.')
    start = date.fromisoformat(form['period_start']) if form.get('period_start') else None
    end = date.fromisoformat(form['period_end']) if form.get('period_end') else None
    if start and end and start > end: raise ValueError('O período dos dados está invertido.')
    return dict(**image, supplier=supplier, period_start=start, period_end=end)
