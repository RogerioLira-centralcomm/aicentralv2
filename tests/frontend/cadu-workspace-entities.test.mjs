import assert from 'node:assert/strict';
import test from 'node:test';
import {entityHref, entityIdentity, entityLabel, groupWorkspaceProjects, normalizedEntityKey} from '../../frontend/cadu-design-system/workspaceEntities.mjs';

test('workspace entities preserve every supported identity and label shape', () => {
  assert.equal(normalizedEntityKey('studio:42'), '42');
  assert.equal(normalizedEntityKey('ci:Projeto-1'), 'projeto-1');
  assert.equal(entityIdentity({project_ref:'ci:9'}), 'ci:9');
  assert.equal(entityLabel({project_name:'Plano anual'}), 'Plano anual');
  assert.equal(entityHref({url:'/workspace/projects/9'}), '/workspace/projects/9');
});

test('workspace projects group by ids, refs, related refs or brand names without losing unlinked items', () => {
  const brands = [
    {id:'1', name:'Centralcomm'},
    {ref:'studio:2', name:'Uhurú'},
  ];
  const projects = [
    {id:'p1', name:'Mídia Paga', brand_id:'1', updated_at:'2026-09-20'},
    {id:'p2', name:'Campanha', related_refs:['studio:2'], updated_at:'2026-09-21'},
    {id:'p3', name:'Planejamento', brandName:'Centralcomm', updated_at:'2026-09-22'},
    {id:'p4', name:'Sem marca', updated_at:'2026-09-23'},
    {id:'p5', name:'Arquivado', brand_id:'1', status:'arquivado', updated_at:'2026-09-24'},
  ];
  const result = groupWorkspaceProjects(brands, projects);
  assert.deepEqual(result.groups.map(group => [group.name, group.projects.map(project => project.id)]), [
    ['Centralcomm', ['p3', 'p1']],
    ['Uhurú', ['p2']],
  ]);
  assert.deepEqual(result.ungrouped.map(project => project.id), ['p4']);
});
