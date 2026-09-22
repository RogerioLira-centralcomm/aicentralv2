const {test} = require('node:test');
const assert = require('node:assert/strict');

test('external dock links use an internal viewer with an external escape hatch', async () => {
  const {dockExternalPresentation} = await import('../../frontend/cadu-design-system/dockExternal.mjs');
  assert.deepEqual(dockExternalPresentation('https://trello.com/b/demo').kind, 'iframe');
  assert.equal(dockExternalPresentation('https://drive.google.com/file/d/abc123/view').embedUrl,
    'https://drive.google.com/file/d/abc123/preview');
  assert.equal(dockExternalPresentation('https://docs.google.com/document/d/abc123/edit').embedUrl,
    'https://docs.google.com/document/d/abc123/preview');
  assert.equal(dockExternalPresentation('https://meet.google.com/abc-defg-hij').kind, 'external');
});

test('image links get an image viewer and unsafe protocols are rejected', async () => {
  const {dockExternalPresentation} = await import('../../frontend/cadu-design-system/dockExternal.mjs');
  assert.equal(dockExternalPresentation('https://example.com/logo.png?size=2').kind, 'image');
  assert.equal(dockExternalPresentation('javascript:alert(1)'), null);
  assert.equal(dockExternalPresentation('https://user:password@example.com/'), null);
});

test('official provider logos match only their real domains', async () => {
  const {dockProviderLogo} = await import('../../frontend/cadu-design-system/dockExternal.mjs');
  const cases = [
    ['https://trello.com/b/board', 'trello.svg'],
    ['https://app.asana.com/0/123', 'asana.svg'],
    ['https://drive.google.com/file/d/123/view', 'drive.google.com/favicon.ico'],
    ['https://meet.google.com/abc-defg-hij', 'meet.google.com/favicon.ico'],
    ['https://acme.slack.com/archives/123', 'slack.svg'],
    ['https://miro.com/app/board/123', 'miro.com/favicon.ico'],
  ];
  for (const [url, suffix] of cases) assert.ok(dockProviderLogo(url).endsWith(suffix), url);
  for (const url of ['https://trello.com.evil.test/', 'https://fake-asana.com/',
    'https://drive.google.com.evil.test/', 'https://user:pass@miro.com/', 'http://slack.com/']) {
    assert.equal(dockProviderLogo(url), '', url);
  }
});
