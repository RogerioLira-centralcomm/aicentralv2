const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const root = path.resolve(__dirname, '../..');

test('canonical workspace chrome loads after legacy design-system styles', () => {
  const entry = fs.readFileSync(path.join(root, 'frontend/conversations-v2/main.jsx'), 'utf8');
  const legacyIndex = entry.indexOf("import '../cadu-design-system/styles.css'");
  const chromeIndex = entry.indexOf("import '../cadu-design-system/workspace-chrome.css'");
  assert.ok(legacyIndex >= 0, 'legacy design-system styles remain available during migration');
  assert.ok(chromeIndex > legacyIndex, 'canonical chrome must be loaded last');
});

test('workspace chrome owns one stable dock geometry contract', () => {
  const chrome = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/workspace-chrome.css'), 'utf8');
  assert.match(chrome, /--cadu-dock-slot:40px/);
  assert.match(chrome, /--cadu-dock-plate:34px/);
  assert.match(chrome, /width:64px/);
  assert.match(chrome, /object-fit:contain/);
  assert.match(chrome, /\.has-fallback-content:not\(\.has-custom-background\)/);
  assert.match(chrome, /background:color-mix\(in srgb,var\(--cadu-identity-color/);
});

test('visual identity exposes rendered-image and fallback states to the canonical chrome', () => {
  const identity = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/components/VisualIdentity.jsx'), 'utf8');
  assert.match(identity, /has-rendered-image/);
  assert.match(identity, /has-fallback-content/);
  assert.match(identity, /onError=\{\(\) => setImageFailed\(true\)\}/);
});
