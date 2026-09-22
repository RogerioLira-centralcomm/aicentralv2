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
    'https://trello.com/b/board', 'https://app.asana.com/0/123',
    'https://drive.google.com/file/d/123/view', 'https://meet.google.com/abc-defg-hij',
    'https://acme.slack.com/archives/123', 'https://miro.com/app/board/123',
    'https://chatgpt.com/c/123', 'https://claude.ai/chat/123',
    'https://gemini.google.com/app/123', 'https://notebooklm.google.com/notebook/123',
    'https://business.facebook.com/adsmanager/manage/campaigns', 'https://ads.tiktok.com/i18n/home',
    'https://www.linkedin.com/campaignmanager/accounts', 'https://www.instagram.com/marca/',
    'https://www.linkedin.com/company/marca/', 'https://ads.google.com/aw/overview',
    'https://analytics.google.com/analytics/web/', 'https://www.canva.com/design/demo',
  ];
  for (const url of cases) assert.match(dockProviderLogo(url), /^https:\/\//i, url);
  for (const url of ['https://trello.com.evil.test/', 'https://fake-asana.com/',
    'https://drive.google.com.evil.test/', 'https://chatgpt.com.evil.test/',
    'https://user:pass@miro.com/', 'http://slack.com/',
    'https://notinstagram.com/', 'https://business.facebook.com.evil.test/']) {
    assert.equal(dockProviderLogo(url), '', url);
  }
});
