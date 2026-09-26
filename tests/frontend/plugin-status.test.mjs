import assert from 'node:assert/strict';
import test from 'node:test';
import {routeSelectedStatus, unavailableToolStatus} from '../../frontend/conversations-v2/lib/pluginStatus.mjs';

test('preserves the selected plugin status while context is prepared', () => {
  assert.equal(routeSelectedStatus({plugin: {name: 'Busca no projeto'}}), 'Acionando Busca no projeto');
});

test('shows the selected artifact when a plugin is revising it', () => {
  assert.equal(routeSelectedStatus({
    plugin: {name: 'Planner'},
    targetArtifact: {title: 'Plano de mídia'},
  }), 'Revisando Plano de mídia');
});

test('uses a generic status only when no plugin or artifact is selected', () => {
  assert.equal(routeSelectedStatus({}), 'Preparando o contexto');
});

test('uses a human-readable status when a tool is unavailable', () => {
  assert.equal(unavailableToolStatus('web.search'), 'Pesquisa externa indisponível');
  assert.equal(unavailableToolStatus('google.list_calendar_events'), 'Google Workspace indisponível');
  assert.equal(unavailableToolStatus('workspace.search_project_content'), 'Dados do projeto indisponíveis');
  assert.equal(unavailableToolStatus('unknown.tool'), 'Uma etapa do plugin está indisponível');
});
