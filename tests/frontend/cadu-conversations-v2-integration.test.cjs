const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {pathToFileURL} = require('node:url');

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

test('conversations 2.0 is one React surface with streaming, artifacts and protected work', () => {
  const app = fs.readFileSync(path.join(root, 'frontend/conversations-v2/App.jsx'), 'utf8');
  const artifact = fs.readFileSync(path.join(root, 'frontend/conversations-v2/components/ArtifactPane.jsx'), 'utf8');
  const conversation = fs.readFileSync(path.join(root, 'frontend/conversations-v2/components/Conversation.jsx'), 'utf8');
  const responseBlocks = fs.readFileSync(path.join(root, 'frontend/conversations-v2/components/ResponseBlocks.jsx'), 'utf8');
  const styles = fs.readFileSync(path.join(root, 'frontend/conversations-v2/styles.css'), 'utf8');
  const template = fs.readFileSync(path.join(root, 'aicentralv2/templates/cadu_workspace/conversations_v2_lab.html'), 'utf8');
  const base = fs.readFileSync(path.join(root, 'aicentralv2/templates/cadu_portals/base.html'), 'utf8');
  assert.match(app, /metadata\.artifact_id/);
  assert.match(app, /fetchArtifact\(lastArtifact\)/);
  assert.match(app, /confirmDiscard/);
  assert.doesNotMatch(app, /window\.confirm/);
  assert.match(app, /ConfirmDialog/);
  assert.match(app, /beforeunload/);
  assert.match(app, /streamEvents/);
  assert.match(app, /let runStarted = false/);
  assert.match(app, /if \(runStarted\)/);
  assert.match(app, /event\.message \|\| 'O agente não conseguiu concluir/);
  assert.match(app, /expected_version/);
  assert.match(app, /\/versions\/\$\{version\}/);
  assert.match(artifact, /resource\.editor_url/);
  assert.match(artifact, /resource\.download_url/);
  assert.match(artifact, /sandbox="allow-scripts"/);
  assert.match(artifact, /Content-Security-Policy/);
  assert.doesNotMatch(artifact, /img-src data: blob: https:/);
  assert.match(conversation, /Ver resposta completa/);
  assert.match(conversation, /ResponseBlocks/);
  assert.match(conversation, /cv-conversation-title/);
  assert.match(conversation, /cv-composer-shell/);
  assert.match(conversation, /cv-thread-content/);
  assert.match(responseBlocks, /Usar esta opção/);
  assert.match(responseBlocks, /Continuar com/);
  assert.match(responseBlocks, /block\.type === 'insights'/);
  assert.match(responseBlocks, /block\.type === 'files'/);
  assert.match(artifact, /Criar versão editável/);
  assert.match(styles, /cv-artifact-open/);
  assert.match(styles, /prefers-reduced-motion/);
  assert.match(styles, /#cadu-conversations-v2-root \.cv-composer-input/);
  assert.match(styles, /padding-bottom: 204px !important/);
  assert.match(styles, /@media \(max-width: 1080px\)[\s\S]*\.cv-artifact-overlay/);
  assert.match(template, /cadu-conversations-v2-root/);
  assert.match(template, /cadu-conversations-v2-bootstrap/);
  assert.match(template, /react\/app\.js/);
  assert.match(template, /react\/app\.css'\) }}\?v=2/);
  assert.match(template, /react\/app\.js'\) }}\?v=2/);
  assert.doesNotMatch(template, /_app_sidebar\.html/);
  assert.doesNotMatch(template, /v2-lab\.js/);
  assert.match(base, /request\.endpoint not in \('cadu_workspace\.conversations', 'cadu_agent_v2_lab\.conversations_v2_lab'\)/);
});

test('conversation response model preserves execution order and explicit checklist selection', async () => {
  const model = await import(pathToFileURL(path.join(root, 'frontend/conversations-v2/lib/responseModel.mjs')).href);
  const messages = [
    {id: 'u', turnId: 'turn-1', role: 'user'},
    {id: 'a', turnId: 'turn-1', role: 'assistant', response: {answer: 'Pronto'}},
  ];
  const ordered = model.insertWorkedBeforeResult(messages, 'turn-1', {
    id: 'w', turnId: 'turn-1', role: 'assistant', kind: 'worked', seconds: 3,
  });
  assert.deepEqual(ordered.map(item => item.id), ['u', 'w', 'a']);
  assert.equal(model.checklistPrompt([]), '');
  assert.equal(model.checklistPrompt([{title: 'Validar casting', prompt: 'Revise o casting.'}]), 'Revise o casting.');
  assert.equal(model.checklistPrompt([{title: 'Casting'}, {title: 'Locação'}]), 'Revise estes itens comigo: Casting; Locação.');
});
