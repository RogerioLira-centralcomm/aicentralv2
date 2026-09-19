const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.resolve(__dirname, '../..');

test('runtime v2 translates internal events into public UI events', () => {
  const window = {};
  vm.runInNewContext(fs.readFileSync(path.join(root, 'aicentralv2/static/cadu_workspace/conversations/runtime-v2.js'), 'utf8'), {window, TextDecoder});
  const runtime = window.CaduConversationV2;
  assert.equal(runtime.normalize({event:'run.started', conversation_id:'c', run_id:'r'}).event, 'start');
  assert.deepEqual(
    JSON.parse(JSON.stringify(runtime.normalize({event:'route.selected', route:{action:'create_brief'}}))),
    {event:'progress', message:'Preparando o briefing…'}
  );
  assert.equal(runtime.normalize({event:'tool.completed', name:'private.tool'}).message.includes('private.tool'), false);
  assert.equal(runtime.normalize({event:'answer.completed', response:{answer:'Pronto'}}).event, 'v2.answer');
  assert.equal(runtime.normalize({event:'artifact.created', artifact:{id:'a'}}).event, 'v2.artifact');
  assert.equal(runtime.normalize({event:'run.completed', status:'completed'}).event, 'done');
  assert.equal(runtime.normalize({event:'run.completed', status:'cancelled'}).status, 'stopped');
});

test('official conversation screen wires v2 without removing legacy fallback', () => {
  const template = fs.readFileSync(path.join(root, 'aicentralv2/templates/cadu_workspace/conversations.html'), 'utf8');
  const chat = fs.readFileSync(path.join(root, 'aicentralv2/static/cadu_workspace/conversations/chat.js'), 'utf8');
  assert.match(template, /data-runtime=/);
  assert.match(template, /data-v2-endpoint=/);
  assert.match(template, /runtime-v2\.js/);
  assert.match(template, /artifacts-v2\.js/);
  assert.match(chat, /CaduConversationV2\.events/);
  assert.match(chat, /CaduV2Artifacts/);
  assert.match(chat, /\/familia\/api\/conversations\/send/);
});

test('v2 artifact surface uses optimistic version checks', () => {
  const artifact = fs.readFileSync(path.join(root, 'aicentralv2/static/cadu_workspace/conversations/artifacts-v2.js'), 'utf8');
  assert.match(artifact, /expected_version/);
  assert.match(artifact, /current_version/);
  assert.match(artifact, /Este artefato mudou em outra sessão/);
});

test('v2 attachments require an explicit project usage choice', () => {
  const attachments = fs.readFileSync(path.join(root, 'aicentralv2/static/cadu_workspace/conversations/attachments.js'), 'utf8');
  assert.match(attachments, /Usar nesta conversa/);
  assert.match(attachments, /Fonte do projeto/);
  assert.match(attachments, /Somente anexar ao projeto/);
  assert.match(attachments, /projects\.prepare_source_upload/);
  assert.match(attachments, /use_as_knowledge/);
});

test('conversations 2.0 restores artifacts and protects unsaved work', () => {
  const lab = fs.readFileSync(path.join(root, 'aicentralv2/static/cadu_workspace/conversations/v2-lab.js'), 'utf8');
  const styles = fs.readFileSync(path.join(root, 'aicentralv2/static/cadu_workspace/conversations/v2-lab.css'), 'utf8');
  const template = fs.readFileSync(path.join(root, 'aicentralv2/templates/cadu_workspace/conversations_v2_lab.html'), 'utf8');
  const base = fs.readFileSync(path.join(root, 'aicentralv2/templates/cadu_portals/base.html'), 'utf8');
  assert.match(lab, /metadata\.artifact_id/);
  assert.match(lab, /fetchArtifact\(lastArtifactId\)/);
  assert.match(lab, /confirmDiscard/);
  assert.match(lab, /beforeunload/);
  assert.match(lab, /resource\.editor_url/);
  assert.match(lab, /resource\.download_url/);
  assert.match(lab, /setAttribute\('sandbox', 'allow-scripts'\)/);
  assert.match(lab, /Content-Security-Policy/);
  assert.doesNotMatch(lab, /img-src data: blob: https:/);
  assert.match(lab, /displayProjectContext\(data\.context \|\| selectedContext\)/);
  assert.match(lab, /v2-response-sources/);
  assert.match(lab, /const addFailure/);
  assert.match(lab, /input\.value = lastSubmittedMessage/);
  assert.match(lab, /const renderChatText/);
  assert.match(lab, /Ver resposta completa/);
  assert.match(lab, /if \(!href\) return/);
  assert.match(lab, /if \(!runTerminalReceived\) throw new Error/);
  assert.match(lab, /artifactSave\.dataset\.conflict/);
  assert.match(lab, /await loadContext\(\);[\s\S]*await loadRecent\(\);/);
  assert.match(styles, /\.portal main\.v2-lab \{[\s\S]*width: 100%;[\s\S]*max-width: none;[\s\S]*margin: 0;/);
  assert.match(styles, /@media \(max-width: 1080px\)[\s\S]*\.v2-lab-artifact-shell \{[\s\S]*inset: 0;/);
  assert.match(lab, /\/versions\/\$\{item\.version\}/);
  assert.match(lab, /workspace\/api\/v2\/uploads/);
  assert.match(template, /data-unsaved-dialog/);
  assert.match(template, /data-versions-dialog/);
  assert.match(template, /data-file-input/);
  assert.match(base, /request\.endpoint not in \('cadu_workspace\.conversations', 'cadu_agent_v2_lab\.conversations_v2_lab'\)/);
});
