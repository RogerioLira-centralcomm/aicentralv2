// Shared harness for Studio browser tests: project Playwright, fresh fixtures, ignored artifacts.
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');
const { chromium: playwright } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

const ROOT = path.resolve(__dirname, '../..');
const FIXTURE = path.join(ROOT, 'tests/frontend/.fixtures/studio-editor');
const HOME_FIXTURE = path.join(ROOT, 'tests/frontend/.fixtures/studio-home');
const ARTIFACTS = path.join(ROOT, 'tests/frontend/.artifacts/studio');
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const PYTHON = fs.existsSync(path.join(ROOT, '.venv/bin/python')) ? path.join(ROOT, '.venv/bin/python') : 'python3';

process.chdir(ROOT);
fs.mkdirSync(ARTIFACTS, { recursive: true });

function render(script) {
  execFileSync(PYTHON, [script], { cwd: ROOT, stdio: 'inherit' });
}

const chromium = {
  launch(options = {}) {
    const opts = { ...options };
    if (opts.executablePath && !fs.existsSync(opts.executablePath)) delete opts.executablePath;
    if (!opts.executablePath && fs.existsSync(CHROME)) opts.executablePath = CHROME;
    return playwright.launch(opts);
  },
};

module.exports = {
  chromium,
  FIXTURE,
  HOME_FIXTURE,
  ARTIFACTS,
  ensureEditorFixture: () => render('tests/frontend/render-video-editor-fixture.py'),
  ensureHomeFixture: () => render('tests/frontend/render-studio-fixture.py'),
};
