import test from 'node:test';
import assert from 'node:assert/strict';

test('inspector explains how each step is measured', async () => {
  // FlowInspector imports JSX components; read the pure helper from the source instead of executing the module.
  const {readFileSync} = await import('node:fs');
  const source = readFileSync(new URL('../../frontend/reports-v1/FlowInspector.jsx', import.meta.url), 'utf8');
  const body = source.slice(source.indexOf('export function measurementHint'), source.indexOf('export function FlowInspector('));
  const measurementHint = new Function(`${body.replace('export ', '')}; return measurementHint;`)();
  assert.match(measurementHint({type: 'event', event_name: 'scroll_depth'}), /Rolagem além de 50%/);
  assert.match(measurementHint({type: 'page', path: '/oferta', status: 'planned'}), /entra na medição quando/);
  assert.match(measurementHint({type: 'page', path: '/oferta', status: 'live'}), /Visita a esta URL/);
  assert.match(measurementHint({type: 'event', event_name: 'add_to_cart'}), /CaduSuperTag\.trackEvent\('add_to_cart'\)/);
  assert.match(measurementHint({type: 'conversion', event_name: 'purchase'}), /trackConversion\('purchase'\)/);
  assert.match(measurementHint({type: 'form'}), /automaticamente/);
});
