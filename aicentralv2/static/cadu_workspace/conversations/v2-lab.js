(() => {
  'use strict';

  const root = document.querySelector('[data-v2-lab]');
  if (!root) return;

  const form = root.querySelector('[data-form]');
  const input = root.querySelector('[data-message]');
  const send = root.querySelector('[data-send]');
  const thread = root.querySelector('[data-thread]');
  const trace = root.querySelector('[data-trace]');
  const runtime = root.querySelector('[data-runtime-state]');
  const surface = root.querySelector('[data-surface]');
  const project = root.querySelector('[data-project]');
  const projectState = root.querySelector('[data-project-state]');
  const composerContext = root.querySelector('[data-composer-context]');
  const conversationTitle = root.querySelector('[data-conversation-title]');
  const diagnostics = root.querySelector('.v2-lab-diagnostics');
  const artifactShell = root.querySelector('[data-artifact-shell]');
  const artifactContent = root.querySelector('[data-artifact]');
  const artifactTitle = root.querySelector('[data-artifact-title]');
  const artifactKind = root.querySelector('[data-artifact-kind]');
  const artifactSavebar = root.querySelector('[data-artifact-savebar]');
  const artifactStatus = root.querySelector('[data-artifact-status]');
  const artifactSave = root.querySelector('[data-artifact-save]');
  const workspaceRecent = document.getElementById('workspace-sidebar-recent-conversations');

  let conversationId = null;
  let currentRunId = null;
  let currentArtifact = null;
  let artifactRenderer = 'document';
  let running = false;
  let runStartedAt = 0;
  let selectedContext = {};

  const escape = value => String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[char]);
  const csrf = () => document.querySelector('meta[name="csrf-token"]')?.content || '';
  const scrollThread = () => { thread.scrollTop = thread.scrollHeight; };
  const json = async response => response.json().catch(() => ({}));

  const request = async (url, options = {}) => {
    const response = await fetch(url, {credentials: 'same-origin', ...options});
    const data = await json(response);
    if (!response.ok) {
      const error = new Error(data.error || `Não foi possível concluir (${response.status}).`);
      error.status = response.status;
      throw error;
    }
    return data;
  };

  const setRuntime = (label, busy = false) => {
    const visibleLabel = label === 'Pronto' ? '' : label;
    runtime.textContent = visibleLabel;
    runtime.hidden = !visibleLabel;
    root.classList.toggle('is-running', busy);
  };

  const autoGrow = () => {
    input.style.height = 'auto';
    input.style.height = `${Math.min(input.scrollHeight, 150)}px`;
    send.disabled = running || !input.value.trim();
  };

  const addTrace = (title, detail = '', tone = '') => {
    if (trace.querySelector(':scope > p')) trace.replaceChildren();
    const row = document.createElement('div');
    row.className = `v2-trace-row ${tone}`;
    row.innerHTML = `<i></i><div><b>${escape(title)}</b>${detail ? `<small>${escape(detail)}</small>` : ''}</div>`;
    trace.append(row);
  };

  const addUser = message => {
    thread.querySelector('.v2-lab-empty')?.remove();
    const node = document.createElement('article');
    const content = document.createElement('p');
    node.className = 'v2-lab-message is-user';
    content.textContent = message;
    node.append(content);
    thread.append(node);
    scrollThread();
  };

  const closeArtifact = () => {
    artifactShell.hidden = true;
    root.classList.remove('is-artifact-open');
    input.focus();
  };

  const openArtifact = () => {
    artifactShell.hidden = false;
    root.classList.add('is-artifact-open');
  };

  const artifactLabel = type => ({
    brief: 'Briefing',
    document: 'Documento',
    note: 'Nota',
    executive_summary: 'Resumo executivo',
    media_plan: 'Plano de mídia',
    scenario: 'Cenário',
    research: 'Pesquisa',
    project_map: 'Mapa do projeto'
  })[type] || 'Artefato';

  const markArtifactDirty = () => {
    if (!currentArtifact?.id) return;
    artifactStatus.textContent = 'Alterações não salvas';
    artifactSavebar.hidden = false;
  };

  const resourceTypeLabel = type => ({
    file: 'Arquivo', artifact: 'Artefato', media_plan: 'Plano', report: 'Relatório',
    image: 'Imagem', video: 'Vídeo', analysis: 'Análise', link: 'Link'
  })[type] || 'Recurso';

  const moveResource = (content, resourceId, groupId) => {
    const resource = content.resources.find(item => item.id === resourceId);
    if (!resource || resource.group_id === groupId) return false;
    content.groups.forEach(group => {
      group.resource_ids = (group.resource_ids || []).filter(id => id !== resourceId);
      if (group.id === groupId) group.resource_ids.push(resourceId);
    });
    resource.group_id = groupId;
    return true;
  };

  const showMapResource = (viewport, content, resource) => {
    const map = viewport.closest('.v2-project-map');
    map?.querySelector('.v2-map-resource-inspector')?.remove();
    const inspector = document.createElement('aside');
    const head = document.createElement('header');
    const copy = document.createElement('div');
    const kind = document.createElement('span');
    const title = document.createElement('h3');
    const close = document.createElement('button');
    inspector.className = 'v2-map-resource-inspector';
    kind.textContent = resourceTypeLabel(resource.type);
    title.textContent = resource.title;
    close.type = 'button';
    close.textContent = '×';
    close.setAttribute('aria-label', 'Fechar detalhes');
    close.addEventListener('click', () => inspector.remove());
    copy.append(kind, title);
    head.append(copy, close);
    inspector.append(head);

    const facts = document.createElement('dl');
    const values = [
      ['Estado', resource.status || 'Ativo'],
      ['Categoria', resource.category || 'Outro'],
      ['Versão', String(resource.version || 1)],
      ['Origem', resource.source_system || 'Projeto']
    ];
    values.forEach(([label, value]) => {
      const wrapper = document.createElement('div');
      const term = document.createElement('dt');
      const description = document.createElement('dd');
      term.textContent = label;
      description.textContent = value;
      wrapper.append(term, description);
      facts.append(wrapper);
    });
    inspector.append(facts);

    const groupLabel = document.createElement('label');
    const groupSelect = document.createElement('select');
    groupLabel.append(document.createTextNode('Mover para'));
    content.groups.forEach(group => groupSelect.add(new Option(group.title, group.id)));
    groupSelect.value = resource.group_id;
    groupSelect.addEventListener('change', () => {
      if (moveResource(content, resource.id, groupSelect.value)) {
        currentArtifact.content = content;
        markArtifactDirty();
        renderProjectMap(content);
      }
    });
    groupLabel.append(groupSelect);
    inspector.append(groupLabel);

    if (resource.possible_duplicate) {
      const warning = document.createElement('p');
      warning.className = 'is-warning';
      warning.textContent = 'Pode ser uma versão duplicada de outro arquivo.';
      inspector.append(warning);
    }
    if (resource.url) {
      const link = document.createElement('a');
      link.href = resource.url;
      link.target = '_blank';
      link.rel = 'noopener';
      link.textContent = 'Abrir origem';
      inspector.append(link);
    }
    map?.append(inspector);
  };

  const renderProjectMap = content => {
    artifactRenderer = 'project-map';
    artifactContent.classList.add('is-project-map');
    artifactContent.replaceChildren();
    const map = document.createElement('section');
    const viewport = document.createElement('div');
    const scene = document.createElement('div');
    const connections = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    const controls = document.createElement('div');
    map.className = 'v2-project-map';
    viewport.className = 'v2-project-map-viewport';
    scene.className = 'v2-project-map-scene';
    connections.classList.add('v2-project-map-relations');
    controls.className = 'v2-project-map-controls';

    content.groups = Array.isArray(content.groups) ? content.groups : [];
    content.resources = Array.isArray(content.resources) ? content.resources : [];
    content.relations = Array.isArray(content.relations) ? content.relations : [];
    content.layout = {...(content.layout || {}), zoom: Number(content.layout?.zoom || 1)};
    currentArtifact.content = {...currentArtifact.content, ...content};

    const sceneWidth = Math.max(820, ...content.groups.map(group => Number(group.x || 0) + Number(group.width || 310) + 80));
    const sceneHeight = Math.max(680, ...content.groups.map(group => Number(group.y || 0) + 310));
    scene.style.width = `${sceneWidth}px`;
    scene.style.height = `${sceneHeight}px`;
    connections.setAttribute('viewBox', `0 0 ${sceneWidth} ${sceneHeight}`);
    scene.append(connections);

    const groupNodes = new Map();
    const resourceGroups = new Map(content.resources.map(item => [item.id, item.group_id]));
    const renderRelations = () => {
      connections.replaceChildren();
      const pairs = new Set();
      content.relations.forEach(relation => {
        const sourceGroup = resourceGroups.get(relation.source);
        const targetGroup = resourceGroups.get(relation.target);
        if (!sourceGroup || !targetGroup || sourceGroup === targetGroup) return;
        const pair = [sourceGroup, targetGroup].sort().join(':');
        if (pairs.has(pair)) return;
        pairs.add(pair);
        const source = content.groups.find(group => group.id === sourceGroup);
        const target = content.groups.find(group => group.id === targetGroup);
        if (!source || !target) return;
        const line = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        const x1 = Number(source.x || 0) + Number(source.width || 310) / 2;
        const y1 = Number(source.y || 0) + 40;
        const x2 = Number(target.x || 0) + Number(target.width || 310) / 2;
        const y2 = Number(target.y || 0) + 40;
        line.setAttribute('d', `M${x1} ${y1} C${x1} ${(y1 + y2) / 2},${x2} ${(y1 + y2) / 2},${x2} ${y2}`);
        connections.append(line);
      });
    };

    content.groups.forEach(group => {
      const panel = document.createElement('section');
      const header = document.createElement('header');
      const heading = document.createElement('h3');
      const count = document.createElement('span');
      const list = document.createElement('div');
      const resources = content.resources.filter(resource => resource.group_id === group.id);
      panel.className = 'v2-project-map-group';
      panel.dataset.groupId = group.id;
      panel.style.left = `${Number(group.x || 0)}px`;
      panel.style.top = `${Number(group.y || 0)}px`;
      panel.style.width = `${Number(group.width || 310)}px`;
      header.tabIndex = 0;
      header.setAttribute('aria-label', `${group.title}. Use as setas para mover o grupo.`);
      heading.textContent = group.title;
      count.textContent = String(resources.length);
      header.append(heading, count);
      list.className = 'v2-project-map-files';

      resources.forEach(resource => {
        const row = document.createElement('button');
        const icon = document.createElement('span');
        const copy = document.createElement('span');
        const title = document.createElement('strong');
        const meta = document.createElement('small');
        row.type = 'button';
        row.className = 'v2-project-map-file';
        row.draggable = true;
        row.dataset.resourceId = resource.id;
        icon.textContent = resourceTypeLabel(resource.type).slice(0, 1);
        title.textContent = resource.title;
        meta.textContent = `${resourceTypeLabel(resource.type)} · v${resource.version || 1}`;
        if (resource.possible_duplicate) meta.textContent += ' · possível duplicata';
        copy.append(title, meta);
        row.append(icon, copy);
        row.addEventListener('click', () => showMapResource(viewport, content, resource));
        row.addEventListener('dragstart', event => {
          event.dataTransfer.effectAllowed = 'move';
          event.dataTransfer.setData('text/plain', resource.id);
        });
        list.append(row);
      });

      panel.addEventListener('dragover', event => {
        event.preventDefault();
        panel.classList.add('is-drop-target');
      });
      panel.addEventListener('dragleave', () => panel.classList.remove('is-drop-target'));
      panel.addEventListener('drop', event => {
        event.preventDefault();
        panel.classList.remove('is-drop-target');
        if (moveResource(content, event.dataTransfer.getData('text/plain'), group.id)) {
          currentArtifact.content = content;
          markArtifactDirty();
          renderProjectMap(content);
        }
      });

      const moveGroup = (x, y) => {
        group.x = Math.max(16, Math.round(x));
        group.y = Math.max(16, Math.round(y));
        panel.style.left = `${group.x}px`;
        panel.style.top = `${group.y}px`;
      };
      header.addEventListener('keydown', event => {
        const movement = {ArrowLeft: [-12, 0], ArrowRight: [12, 0], ArrowUp: [0, -12], ArrowDown: [0, 12]}[event.key];
        if (!movement) return;
        event.preventDefault();
        moveGroup(Number(group.x || 0) + movement[0], Number(group.y || 0) + movement[1]);
        currentArtifact.content = content;
        markArtifactDirty();
        renderRelations();
      });
      header.addEventListener('pointerdown', event => {
        if (event.button !== 0) return;
        const startX = event.clientX;
        const startY = event.clientY;
        const originX = Number(group.x || 0);
        const originY = Number(group.y || 0);
        header.setPointerCapture(event.pointerId);
        panel.classList.add('is-moving');
        const moving = moveEvent => moveGroup(
          originX + (moveEvent.clientX - startX) / content.layout.zoom,
          originY + (moveEvent.clientY - startY) / content.layout.zoom
        );
        const finish = () => {
          panel.classList.remove('is-moving');
          header.removeEventListener('pointermove', moving);
          header.removeEventListener('pointerup', finish);
          currentArtifact.content = content;
          markArtifactDirty();
          renderRelations();
        };
        header.addEventListener('pointermove', moving);
        header.addEventListener('pointerup', finish, {once: true});
      });

      panel.append(header, list);
      scene.append(panel);
      groupNodes.set(group.id, panel);
    });

    const applyZoom = next => {
      content.layout.zoom = Math.min(1.35, Math.max(.62, Number(next.toFixed(2))));
      scene.style.transform = `scale(${content.layout.zoom})`;
      controls.querySelector('[data-map-zoom-value]').textContent = `${Math.round(content.layout.zoom * 100)}%`;
      currentArtifact.content = content;
    };
    [
      ['−', 'Reduzir zoom', () => applyZoom(content.layout.zoom - .1)],
      ['', 'Restaurar zoom', () => applyZoom(1)],
      ['+', 'Aumentar zoom', () => applyZoom(content.layout.zoom + .1)]
    ].forEach(([label, aria, handler], index) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = label;
      button.setAttribute('aria-label', aria);
      if (index === 1) button.dataset.mapZoomValue = '';
      button.addEventListener('click', handler);
      controls.append(button);
    });
    viewport.addEventListener('wheel', event => {
      if (!event.ctrlKey && !event.metaKey) return;
      event.preventDefault();
      applyZoom(content.layout.zoom + (event.deltaY < 0 ? .08 : -.08));
    }, {passive: false});

    renderRelations();
    viewport.append(scene);
    map.append(viewport, controls);
    artifactContent.append(map);
    applyZoom(content.layout.zoom);
  };

  const showArtifact = value => {
    if (!value || typeof value !== 'object') return;

    const persisted = value.id && value.content ? value : null;
    if (persisted) currentArtifact = persisted;
    const content = persisted?.content || value;
    if (!persisted && currentArtifact?.id) {
      currentArtifact = {...currentArtifact, content: {...currentArtifact.content, ...content}};
    }
    const type = persisted?.type || currentArtifact?.type;
    const fields = Array.isArray(content.fields) ? content.fields : [];

    artifactTitle.textContent = persisted?.title || content.title || currentArtifact?.title || 'Trabalho em andamento';
    artifactKind.textContent = artifactLabel(type);
    artifactContent.replaceChildren();

    if (type === 'project_map' && Array.isArray(currentArtifact?.content?.groups)) {
      renderProjectMap(currentArtifact.content);
      artifactSavebar.hidden = true;
      openArtifact();
      return;
    }

    artifactRenderer = 'document';
    artifactContent.classList.remove('is-project-map');

    const article = document.createElement('article');
    const summary = document.createElement('textarea');
    summary.className = 'v2-artifact-summary';
    summary.value = String(content.summary || '');
    summary.placeholder = 'Resumo do trabalho';
    summary.setAttribute('aria-label', 'Resumo do artefato');
    summary.readOnly = !currentArtifact?.id;
    article.append(summary);

    if (fields.length) {
      const sections = document.createElement('div');
      sections.className = 'v2-artifact-sections';
      fields.forEach((field, index) => {
        const row = document.createElement('label');
        const label = document.createElement('span');
        const editor = document.createElement('textarea');
        row.className = 'v2-artifact-field';
        label.textContent = String(field.key || `Seção ${index + 1}`);
        editor.value = String(field.value || '');
        editor.rows = Math.max(2, Math.min(10, editor.value.split('\n').length + 1));
        editor.dataset.fieldIndex = String(index);
        editor.readOnly = !currentArtifact?.id;
        editor.setAttribute('aria-label', label.textContent);
        row.append(label, editor);
        sections.append(row);
      });
      article.append(sections);
    }

    artifactContent.append(article);
    artifactSavebar.hidden = true;
    article.addEventListener('input', markArtifactDirty);
    openArtifact();
  };

  const addAnswer = response => {
    const node = document.createElement('article');
    node.className = 'v2-lab-message is-cadu';

    const answer = document.createElement('p');
    answer.textContent = response.answer || '';
    node.append(answer);

    const questions = Array.isArray(response.questions) ? response.questions : [];
    if (questions.length) {
      const block = document.createElement('div');
      block.className = 'v2-lab-questions';
      questions.forEach(item => {
        const question = document.createElement('p');
        question.textContent = item;
        block.append(question);
      });
      node.append(block);
    }

    const assumptions = Array.isArray(response.assumptions) ? response.assumptions : [];
    if (assumptions.length) {
      const details = document.createElement('details');
      const summary = document.createElement('summary');
      const list = document.createElement('ul');
      details.className = 'v2-response-notes';
      summary.textContent = assumptions.length === 1 ? 'Premissa usada' : `${assumptions.length} premissas usadas`;
      assumptions.forEach(item => {
        const entry = document.createElement('li');
        entry.textContent = item;
        list.append(entry);
      });
      details.append(summary, list);
      node.append(details);
    }

    const actions = Array.isArray(response.actions) ? response.actions : [];
    if (actions.length) {
      const controls = document.createElement('div');
      controls.className = 'v2-lab-actions';
      actions.slice(0, 3).forEach(item => {
        const button = document.createElement('button');
        button.type = 'button';
        button.textContent = item.label;
        button.dataset.actionPrompt = item.prompt || '';
        controls.append(button);
      });
      node.append(controls);
    }

    if (response.artifact_patch) {
      showArtifact(response.artifact_patch);
      const artifactLink = document.createElement('button');
      artifactLink.type = 'button';
      artifactLink.className = 'v2-artifact-link';
      artifactLink.textContent = `Abrir ${artifactTitle.textContent}`;
      artifactLink.addEventListener('click', openArtifact);
      node.append(artifactLink);
    }

    thread.append(node);
    scrollThread();
  };

  const addAction = (action, runId) => {
    const node = document.createElement('article');
    const summary = document.createElement('p');
    const controls = document.createElement('div');
    node.className = 'v2-lab-message is-cadu';
    summary.textContent = action.summary || 'Esta ação precisa da sua confirmação.';
    controls.className = 'v2-lab-actions';

    ['Cancelar', 'Confirmar'].forEach((label, index) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = label;
      button.addEventListener('click', async () => {
        controls.querySelectorAll('button').forEach(item => { item.disabled = true; });
        try {
          const data = await request(`/workspace/api/v2/runs/${encodeURIComponent(runId)}/steps/${encodeURIComponent(action.step_id)}/decision`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf()},
            body: JSON.stringify({approved: index === 1})
          });
          summary.textContent = data.step?.status === 'completed'
            ? 'Ação concluída.'
            : index === 1 ? 'Ação confirmada.' : 'Ação cancelada.';
          controls.remove();
          addTrace('Decisão registrada', data.step?.status || '', 'is-ok');
        } catch (error) {
          controls.querySelectorAll('button').forEach(item => { item.disabled = false; });
          addTrace('Falha na ação', error.message, 'is-error');
        }
      });
      controls.append(button);
    });

    node.append(summary, controls);
    thread.append(node);
    scrollThread();
  };

  const addRunSummary = () => {
    if (!runStartedAt) return;
    const seconds = Math.max(1, Math.round((Date.now() - runStartedAt) / 1000));
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'v2-lab-worked';
    button.textContent = `Trabalhou por ${seconds} s ›`;
    button.addEventListener('click', () => {
      diagnostics.open = true;
      diagnostics.querySelector('summary')?.focus();
    });
    thread.append(button);
    runStartedAt = 0;
  };

  const handleEvent = event => {
    const kind = event.event || 'evento';
    if (kind === 'run.started') {
      conversationId = event.conversation_id;
      currentRunId = event.run_id;
      runStartedAt = Date.now();
      addTrace('Execução iniciada', event.run_id, 'is-ok');
    } else if (kind === 'route.selected') {
      addTrace('Rota selecionada', `${event.route?.domain || ''} / ${event.route?.action || ''}`, 'is-ok');
    } else if (kind === 'tool.completed') {
      addTrace('Consulta concluída', event.name, 'is-ok');
    } else if (kind === 'tool.unavailable') {
      addTrace('Recurso indisponível', `${event.name} · ${event.code || ''}`, 'is-error');
    } else if (kind === 'action.proposed') {
      addAction(event.action || {}, currentRunId);
      addTrace('Confirmação solicitada', event.action?.name || '', 'is-ok');
    } else if (kind === 'artifact.created') {
      addTrace('Artefato criado', event.artifact?.id || '', 'is-ok');
      showArtifact(event.artifact);
    } else if (kind === 'answer.completed') {
      addAnswer(event.response || {});
      addTrace('Resposta concluída', event.response?.confidence || '', 'is-ok');
    } else if (kind === 'run.failed') {
      addTrace('Execução interrompida', event.message || '', 'is-error');
      setRuntime('Não foi possível concluir');
    } else if (kind === 'run.completed') {
      addTrace('Execução concluída', event.status || '', event.status === 'completed' ? 'is-ok' : 'is-error');
      setRuntime(event.status === 'completed' ? 'Concluído' : 'Não foi possível concluir');
      addRunSummary();
      loadRecent();
    }
  };

  const parseStream = async response => {
    if (!response.ok) {
      const data = await json(response);
      throw new Error(data.error || `Não foi possível concluir (${response.status}).`);
    }
    if (!response.body) throw new Error('A resposta não pôde ser transmitida.');
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    while (true) {
      const {value, done} = await reader.read();
      buffer += decoder.decode(value || new Uint8Array(), {stream: !done});
      const frames = buffer.split('\n\n');
      buffer = frames.pop() || '';
      frames.forEach(frame => {
        const raw = frame.split('\n')
          .filter(line => line.startsWith('data:'))
          .map(line => line.slice(5).trimStart())
          .join('\n');
        if (!raw) return;
        try { handleEvent(JSON.parse(raw)); }
        catch (_) { addTrace('Evento não reconhecido', '', 'is-error'); }
      });
      if (done) break;
    }
  };

  const setProjectLabel = label => {
    composerContext.textContent = label || 'Contexto pessoal';
  };

  const loadContext = async () => {
    try {
      const data = await request(root.dataset.contextEndpoint, {headers: {'Accept': 'application/json'}});
      selectedContext = data.context || {};
      const projects = (data.entities || []).filter(item => item.kind === 'project');
      project.replaceChildren(new Option('Contexto pessoal', ''));
      projects.forEach(item => project.add(new Option(item.name, item.ref)));
      project.value = selectedContext.project_ref || '';
      const active = projects.find(item => item.ref === project.value);
      projectState.textContent = active ? `Usando ${active.name}` : 'Nenhum projeto selecionado';
      setProjectLabel(active?.name);
    } catch (error) {
      projectState.textContent = error.message;
    }
  };

  const selectProject = async () => {
    project.disabled = true;
    projectState.textContent = 'Atualizando contexto…';
    try {
      const data = await request(root.dataset.contextEndpoint, {
        method: 'POST',
        headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf()},
        body: JSON.stringify({project_ref: project.value || null, brand_ref: selectedContext.brand_ref || null})
      });
      selectedContext = data.context || {};
      conversationId = null;
      const label = project.value ? project.options[project.selectedIndex].text : 'Contexto pessoal';
      projectState.textContent = project.value ? `Usando ${label}` : 'Nenhum projeto selecionado';
      setProjectLabel(label);
      addTrace('Contexto alterado', label, 'is-ok');
    } catch (error) {
      projectState.textContent = error.message;
      await loadContext();
    } finally {
      project.disabled = false;
    }
  };

  const resetConversation = () => {
    conversationId = null;
    currentRunId = null;
    currentArtifact = null;
    runStartedAt = 0;
    conversationTitle.textContent = 'Nova conversa';
    trace.innerHTML = '<p>Nenhuma execução iniciada.</p>';
    thread.innerHTML = '<div class="v2-lab-empty"><span class="v2-lab-mark" aria-hidden="true">C</span><h2>Em que vamos trabalhar?</h2><p>Converse, analise arquivos ou crie algo usando o contexto do projeto.</p><div class="v2-lab-starters" aria-label="Sugestões"><button type="button" data-prompt="Estruture um briefing para esta campanha e destaque somente o que ainda precisa ser decidido.">Criar um briefing</button><button type="button" data-prompt="Pesquise nos documentos do projeto o que já definimos sobre orçamento e prazo.">Pesquisar no projeto</button><button type="button" data-prompt="Compare as opções disponíveis e recomende a melhor com uma justificativa curta.">Comparar opções</button></div></div>';
    artifactContent.innerHTML = '<p>O resultado aparecerá aqui.</p>';
    artifactSavebar.hidden = true;
    closeArtifact();
    setRuntime('Pronto');
    workspaceRecent?.querySelectorAll('[aria-current="page"]').forEach(item => item.removeAttribute('aria-current'));
    input.value = '';
    autoGrow();
  };

  const openConversation = async (id, title) => {
    if (running) return;
    setRuntime('Abrindo conversa');
    try {
      const data = await request(`${root.dataset.historyEndpoint}/${encodeURIComponent(id)}/messages`, {
        headers: {'Accept': 'application/json'}
      });
      conversationId = id;
      currentArtifact = null;
      conversationTitle.textContent = title || 'Conversa';
      thread.replaceChildren();
      (data.messages || []).forEach(message => {
        if (message.role === 'user') addUser(message.content || '');
        else addAnswer({answer: message.content || '', assumptions: [], questions: [], actions: []});
      });
      if (!thread.childElementCount) resetConversation();
      workspaceRecent?.querySelectorAll('button[data-conversation-id]').forEach(button => {
        if (button.dataset.conversationId === id) button.setAttribute('aria-current', 'page');
        else button.removeAttribute('aria-current');
      });
      setRuntime('Pronto');
    } catch (error) {
      setRuntime('Não foi possível abrir');
      addTrace('Falha ao abrir conversa', error.message, 'is-error');
    }
  };

  const loadRecent = async () => {
    if (!workspaceRecent) return;
    try {
      const data = await request(root.dataset.historyEndpoint, {headers: {'Accept': 'application/json'}});
      const conversations = (data.conversations || [])
        .filter(item => !['arquivada', 'archived'].includes(String(item.status || '').toLowerCase()))
        .slice(0, 8);
      workspaceRecent.replaceChildren();
      conversations.forEach(item => {
        const button = document.createElement('button');
        button.type = 'button';
        button.textContent = item.title || 'Conversa sem título';
        button.dataset.conversationId = String(item.id);
        if (String(item.id) === conversationId) button.setAttribute('aria-current', 'page');
        button.addEventListener('click', () => openConversation(String(item.id), button.textContent));
        workspaceRecent.append(button);
      });
      if (!conversations.length) {
        workspaceRecent.innerHTML = '<span class="workspace-sidebar-conversations-loading">Nenhuma conversa recente</span>';
      }
    } catch (_) {
      workspaceRecent.innerHTML = '<span class="workspace-sidebar-conversations-loading">Histórico indisponível</span>';
    }
  };

  const submit = async message => {
    if (running || !message.trim()) return;
    const cleanMessage = message.trim();
    running = true;
    send.disabled = true;
    setRuntime('Trabalhando', true);
    addUser(cleanMessage);
    if (!conversationId) conversationTitle.textContent = cleanMessage.slice(0, 62);
    input.value = '';
    autoGrow();
    try {
      const response = await fetch(root.dataset.endpoint, {
        method: 'POST',
        credentials: 'same-origin',
        headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf()},
        body: JSON.stringify({
          message: cleanMessage,
          request_id: crypto.randomUUID(),
          conversation_id: conversationId,
          surface: surface.value
        })
      });
      await parseStream(response);
    } catch (error) {
      addTrace('Falha na conversa', error.message, 'is-error');
      setRuntime('Não foi possível concluir');
    } finally {
      running = false;
      root.classList.remove('is-running');
      autoGrow();
      input.focus();
    }
  };

  artifactSave.addEventListener('click', async () => {
    if (!currentArtifact?.id) return;
    artifactSave.disabled = true;
    artifactSave.textContent = 'Salvando…';
    const fields = Array.from(artifactContent.querySelectorAll('[data-field-index]'));
    const content = artifactRenderer === 'project-map' ? currentArtifact.content : {
        ...currentArtifact.content,
        summary: artifactContent.querySelector('.v2-artifact-summary')?.value.trim() || '',
        fields: (currentArtifact.content.fields || []).map((field, index) => ({
          ...field,
          value: fields.find(inputField => Number(inputField.dataset.fieldIndex) === index)?.value.trim() || ''
        }))
      };
    try {
      const data = await request(`/workspace/api/v2/artifacts/${encodeURIComponent(currentArtifact.id)}`, {
        method: 'PATCH',
        headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf()},
        body: JSON.stringify({
          conversation_id: conversationId,
          expected_version: currentArtifact.current_version,
          content,
          title: artifactTitle.textContent,
          change_summary: 'Revisão na conversa'
        })
      });
      currentArtifact = data.artifact;
      artifactStatus.textContent = `Salvo · versão ${currentArtifact.current_version}`;
      artifactSave.textContent = 'Salvo';
      window.setTimeout(() => { artifactSavebar.hidden = true; artifactSave.textContent = 'Salvar'; }, 1100);
    } catch (error) {
      artifactStatus.textContent = error.status === 409
        ? 'Este artefato mudou em outra sessão. Atualize antes de salvar.'
        : error.message;
      artifactSave.textContent = 'Tentar novamente';
    } finally {
      artifactSave.disabled = false;
    }
  });

  root.addEventListener('click', event => {
    const prompt = event.target.closest('[data-prompt]');
    if (prompt) {
      input.value = prompt.dataset.prompt || '';
      autoGrow();
      input.focus();
      return;
    }
    const action = event.target.closest('[data-action-prompt]');
    if (action) {
      input.value = action.dataset.actionPrompt || '';
      autoGrow();
      input.focus();
    }
  });

  root.querySelector('[data-reset]').addEventListener('click', resetConversation);
  root.querySelector('[data-artifact-close]').addEventListener('click', closeArtifact);
  project.addEventListener('change', selectProject);
  form.addEventListener('submit', event => { event.preventDefault(); submit(input.value); });
  input.addEventListener('input', autoGrow);
  input.addEventListener('keydown', event => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      form.requestSubmit();
    }
  });

  document.addEventListener('click', event => {
    if (diagnostics.open && !diagnostics.contains(event.target)) diagnostics.open = false;
  });

  autoGrow();
  loadContext();
  loadRecent();
})();
