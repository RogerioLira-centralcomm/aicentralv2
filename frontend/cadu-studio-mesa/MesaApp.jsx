import React, {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import {createApi} from './api.js';
import {addVersion, uid, emptyBoard, findVersion, layout, newPiece, newSeries, patchVersion, pinPiece, retireVersions, setAnchor, setStar, starOf, TYPES, unpinAll} from './board.js';
import {Canvas, ACTION_LABEL} from './Canvas.jsx';
import {anchorReference, DEFAULT_FORMAT, FORMATS, formatByKey, formatGroups, intentFor, recipeFor, UNFOLD_DEFAULT} from './formats.js';
import {pruneForTarget, References} from './References.jsx';
import {Glyph, Ico} from './Glyph.jsx';
import {Minimap} from './Minimap.jsx';
import {makeZip, saveBlob, slug} from './zip.js';

const ACTIONS = [
  {key: 'adjust', label: 'Ajustar', hint: 'Muda só o que você pedir na peça selecionada. Vira uma nova versão.', needs: 'selection'},
  {key: 'variation', label: 'Variação', hint: 'Peça irmã com a mesma campanha e estilo.', needs: 'anchor'},
  {key: 'unfold', label: 'Desdobrar', hint: 'A mesma peça em vários formatos (social, display IAB, página). Cada formato vira uma peça ligada à original.', needs: 'selection'},
  {key: 'series', label: 'Nova série', hint: 'Um pedido ou um plano inteiro. Se tiver várias peças, você revisa a lista antes de gerar.', needs: null},
];
const CONCURRENCY = 2;

export function MesaApp({boot}) {
  const api = useMemo(() => createApi(boot), [boot]);
  const [projects, setProjects] = useState(null);
  const [ctx, setCtx] = useState({quick: true, clientId: '', projectId: '', projectName: '', brandName: ''});
  const [board, setBoard] = useState(emptyBoard);
  const [session, setSession] = useState({id: new URLSearchParams(location.search).get('session') || '', revision: 0, title: 'Quadro sem nome'});
  const [loaded, setLoaded] = useState(false);
  const [camera, setCamera] = useState({x: 80, y: 80, z: 0.6});
  const [selected, setSelected] = useState(() => new Set());
  const [action, setAction] = useState('series');
  const [actionTouched, setActionTouched] = useState(false);
  const [text, setText] = useState('');
  const [unfold, setUnfold] = useState(() => new Set(UNFOLD_DEFAULT.anuncio));
  const [unfoldOpen, setUnfoldOpen] = useState(false);
  const [shelf, setShelf] = useState({masks: [], items: []});
  const [shelfLoading, setShelfLoading] = useState(false);
  const [refs, setRefs] = useState([]);
  const [refsOpen, setRefsOpen] = useState(true);
  const [startOpen, setStartOpen] = useState(false);
  const [draft, setDraft] = useState(null); // {type, title, rules, pieces: [{title, format, prompt}]}
  const [kind, setKind] = useState('anuncio');
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const [seriesOpen, setSeriesOpen] = useState(true);
  const canvas = useRef(null);
  const boardRef = useRef(board); boardRef.current = board;
  const queue = useRef({running: 0, waiting: []});
  const fresh = useRef(new Set()); // versões criadas nesta visita: só elas animam ao entrar

  const scene = useMemo(() => layout(board), [board]);
  const say = useCallback(message => { setNotice(message); window.clearTimeout(say.t); say.t = window.setTimeout(() => setNotice(''), 5200); }, []);

  // ---- Contexto e carregamento ---------------------------------------------------------------------------------
  useEffect(() => {
    api.projects().then(items => {
      setProjects(items);
      const wanted = new URLSearchParams(location.search).get('project_id') || (() => { try { return localStorage.getItem('cadu-studio-project') || ''; } catch { return ''; } })();
      const hit = items.find(item => String(item.id) === wanted || String(item.external_project_id || '') === wanted);
      if (hit) pickProject(hit);
    }).catch(() => setProjects([]));
  }, [api]);

  useEffect(() => {
    if (!ctx.quick && !ctx.projectId) return;
    let alive = true;
    setShelfLoading(true);
    api.shelf(ctx).then(data => { if (alive) setShelf(data); }).catch(() => { if (alive) setShelf({masks: [], items: []}); }).finally(() => { if (alive) setShelfLoading(false); });
    return () => { alive = false; };
  }, [api, ctx.projectId, ctx.quick]);
  const uploadRefs = async files => {
    try { const added = await api.upload(ctx, files); setShelf(current => ({...current, items: [...added, ...current.items]})); setRefs(current => [...current, ...added].slice(-2)); say('Referência enviada e selecionada.'); }
    catch (error) { say(error.message); }
  };

  const pickProject = item => {
    if (!item) { setCtx({quick: true, clientId: '', projectId: '', projectName: '', brandName: ''}); return; }
    setCtx({quick: false, clientId: String(item.client_id), projectId: String(item.id), projectName: item.name, brandName: item.brand_name || ''});
    try { localStorage.setItem('cadu-studio-project', String(item.id)); } catch { /* opcional */ }
  };

  useEffect(() => {
    if (!session.id) { setLoaded(true); setStartOpen(true); return; }
    api.session(session.id, new URLSearchParams(location.search).get('client_id') || '').then(data => {
      let saved = data?.metadata?.board;
      // Gerações rodam nesta aba: o que ficou pendente numa visita anterior foi interrompido.
      if (saved?.series) {
        // Ajustes têm tarefa no servidor (task_id) e são retomados; criações rodam nesta aba e ficam como interrompidas.
        const resume = [];
        saved = {...saved, series: saved.series.map(series => ({...series, pieces: series.pieces.map(piece => ({...piece,
          versions: piece.versions.map(item => {
            if (item.status !== 'pending') return item;
            if (item.task_id) { resume.push(item); return item; }
            return {...item, status: 'error', error: 'Interrompida ao sair da página. Use "Tentar de novo".'};
          })}))}))};
        setBoard(saved);
        const clientId = new URLSearchParams(location.search).get('client_id') || '';
        resume.forEach(item => api.waitTask({ctx: {clientId}, taskId: item.task_id, prompt: item.prompt})
          .then(result => setBoard(current => patchVersion(current, item.id, {status: 'ready', url: result.url, base: result.url, asset_id: result.asset_id})))
          .catch(error => setBoard(current => patchVersion(current, item.id, {status: 'error', error: error.message}))));
      }
      setSession(current => ({...current, revision: data.revision || 0, title: data.title || current.title}));
      if (saved?.camera) setCamera(saved.camera);
      else setTimeout(() => canvas.current?.fit(layout(saved || emptyBoard()).bounds), 60);
    }).catch(error => say(error.message)).finally(() => setLoaded(true));
  }, []);

  // ---- Salvamento (sessão do Studio, metadata.board) ------------------------------------------------------------
  const saving = useRef({timer: 0, inflight: false, again: false});
  const persist = useCallback(async () => {
    const state = saving.current;
    if (state.inflight) { state.again = true; return; }
    state.inflight = true;
    const snapshot = {...boardRef.current, camera};
    try {
      if (!session.id) {
        const created = await api.createSession({ctx, title: session.title, board: snapshot});
        setSession(current => ({...current, id: created.id, revision: created.revision || 0}));
        const url = new URL(location.href); url.searchParams.set('session', created.id);
        if (!ctx.quick) { url.searchParams.set('client_id', ctx.clientId); url.searchParams.set('project_id', ctx.projectId); }
        history.replaceState(null, '', url);
      } else {
        try {
          const saved = await api.saveSession({id: session.id, ctx, revision: session.revision, title: session.title, board: snapshot});
          setSession(current => ({...current, revision: saved.revision}));
        } catch (error) {
          if (error.status !== 409) throw error;
          const fresh = await api.session(session.id, ctx.clientId);
          const saved = await api.saveSession({id: session.id, ctx, revision: fresh.revision, title: session.title, board: snapshot});
          setSession(current => ({...current, revision: saved.revision}));
        }
      }
    } catch (error) { say(`Não foi possível salvar o quadro: ${error.message}`); }
    finally { state.inflight = false; if (state.again) { state.again = false; window.setTimeout(() => persistRef.current(), 300); } }
  }, [api, ctx, session, camera, say]);
  const persistRef = useRef(persist); persistRef.current = persist;
  useEffect(() => {
    if (!loaded || !board.series.length) return undefined;
    window.clearTimeout(saving.current.timer);
    saving.current.timer = window.setTimeout(() => persistRef.current(), 1200);
    return () => window.clearTimeout(saving.current.timer);
  }, [board, loaded]);

  // ---- Fila de geração ----------------------------------------------------------------------------------------
  const enqueue = task => new Promise((resolve, reject) => {
    const q = queue.current;
    const run = async () => {
      q.running += 1;
      try { resolve(await task()); } catch (error) { reject(error); }
      finally { q.running -= 1; const next = q.waiting.shift(); if (next) next(); }
    };
    if (q.running < CONCURRENCY) run(); else q.waiting.push(run);
  });

  // Cada versão guarda o pedido (`req`) para poder tentar de novo: motor `create` (diretor + imagem) ou `adjust` (Editar).
  const call = (req, versionId) => req.engine === 'adjust'
    ? api.adjust({ctx, base: req.base, instruction: req.prompt, format: req.format, sourceFormat: req.sourceFormat, references: req.references || [], sessionId: session.id, brandName: ctx.brandName,
        onTask: taskId => setBoard(current => patchVersion(current, versionId, {task_id: taskId}))})
    : api.create({ctx, format: req.format, prompt: req.prompt, variationBase: req.variationBase || '', references: req.references || [], recipe: req.recipe || '', intent: req.intent, creationType: req.creationType});

  /** Gera uma versão de uma peça: cria a versão pendente, chama a rota e grava o resultado na mesma versão. */
  const generate = (pieceId, versionInit, req, versionId = uid('v')) => {
    setBoard(current => {
      const exists = findVersion(current, versionId);
      fresh.current.add(versionId); setTimeout(() => fresh.current.delete(versionId), 800);
      return exists ? patchVersion(current, versionId, {status: 'pending', error: ''}) : addVersion(current, pieceId, {...versionInit, id: versionId, req})[0];
    });
    return enqueue(async () => {
      try {
        const result = await call(req, versionId);
        setBoard(current => patchVersion(current, versionId, {status: 'ready', url: result.url, url2x: result.url2x, base: result.base || result.url, asset_id: result.asset_id, title: result.title, director: result.prompt, review: result.review || null}));
        return {...result, versionId};
      } catch (error) {
        setBoard(current => patchVersion(current, versionId, {status: 'error', error: error.message}));
        throw error;
      }
    });
  };
  const retry = hit => { if (hit?.version?.req) generate(hit.piece.id, null, hit.version.req, hit.version.id).catch(error => say(error.message)); };

  // ---- Seleção ------------------------------------------------------------------------------------------------
  const selectedHits = useMemo(() => [...selected].map(id => findVersion(board, id)).filter(Boolean), [selected, board]);
  const selectedVersions = useMemo(() => selectedHits.filter(hit => hit.version.status === 'ready'), [selectedHits]);
  const primaryHit = selectedHits[selectedHits.length - 1] || null;
  const primary = selectedVersions[selectedVersions.length - 1] || null;
  const currentSeries = primaryHit?.series || board.series[board.series.length - 1] || null;
  // Âncora da série: a escolhida pelo usuário; sem escolha, a base da primeira peça pronta.
  const anchorOf = series => {
    if (!series) return null;
    const chosen = series.anchor && findVersion(board, series.anchor);
    if (chosen?.version.status === 'ready' && !chosen.version.retired) return chosen.version;
    const first = series.pieces.find(piece => !piece.origin && starOf(piece)?.status === 'ready');
    return first ? starOf(first) : null;
  };

  // Padrão do seletor: com peça pronta selecionada → Ajustar; com seleção só de erro/pendente → mantém; sem seleção →
  // Variação (série com âncora) ou Nova série. Nunca cai sozinho em "Nova série" enquanto houver algo selecionado.
  useEffect(() => {
    if (actionTouched) return;
    if (selectedVersions.length) setAction('adjust');
    else if (selectedHits.length) return;
    else setAction(anchorOf(currentSeries) && text.length < 280 ? 'variation' : 'series');
  }, [selectedVersions.length, selectedHits.length, board.series.length, text.length > 280]);

  const onSelect = (id, additive) => {
    setSelected(current => {
      if (!id) return new Set();
      const next = new Set(additive ? current : []);
      if (additive && next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
    setActionTouched(false);
  };
  const onLasso = (ids, additive) => setSelected(current => new Set([...(additive ? current : []), ...ids]));
  const selectWhere = predicate => setSelected(new Set(scene.nodes.filter(node => node.kind === 'version' && predicate(node)).map(node => node.id)));

  // ---- Ações --------------------------------------------------------------------------------------------------
  const derive = (kindOf, {series, piece, version}, instruction, format) => {
    const pieceId = uid('p');
    const title = kindOf === 'adapt' ? `${piece.title} · ${format.label}` : `${piece.title} · variação`;
    setBoard(current => newPiece(current, series.id, {id: pieceId, title, format, origin: {piece: piece.id, version: version.id, kind: kindOf}})[0]);
    if (kindOf === 'adapt') {
      // Desdobrar = o motor do Editar recompondo a mesma peça na nova proporção (preserva elementos, textos e marca).
      const prompt = [`Adapte esta peça para ${format.label} (${format.width}×${format.height}), mantendo todos os elementos, textos, logo e cores; apenas reorganize o layout e estenda o fundo para a nova proporção. Não acrescente nem duplique elementos.`, instruction].filter(Boolean).join('\n');
      generate(pieceId, {action: 'adapt', parent: version.id, prompt: instruction}, {engine: 'adjust', base: {id: version.id, url: version.url}, format, sourceFormat: piece.format, prompt, references: refs})
        .catch(error => say(error.message));
      return;
    }
    const anchor = anchorOf(series);
    const style = anchor && anchor.id !== version.id ? anchorReference(anchor) : null;
    generate(pieceId, {action: kindOf, parent: version.id, prompt: instruction}, {engine: 'create', format, prompt: instruction || 'Outra tomada da mesma peça, mesma campanha e mensagem.',
      variationBase: version.base || version.url, references: [...(style ? [style] : []), ...refs].slice(0, 2), creationType: series.type,
      recipe: recipeFor(series.type, {anchor: Boolean(style), rules: series.rules}), intent: intentFor(series.type)}).catch(error => say(error.message));
  };

  const submit = async event => {
    event?.preventDefault();
    const instruction = text.trim();
    if (busy) return;
    if (action !== 'series' && selectedHits.length && !selectedVersions.length) { say('A peça selecionada ainda não está pronta. Use "Tentar de novo" no painel ou escolha outra.'); return; }
    try {
      if (action === 'series') {
        if (!instruction) { setStartOpen(true); return; }
        setBusy(true);
        let plan = null;
        try { plan = await api.decompose({ctx, text: instruction, type: kind}); } catch (error) { say(`Não deu para separar as peças (${error.message}). Vou tratar como uma peça.`); }
        const pieces = plan?.pieces?.length ? plan.pieces : [{title: 'Peça 1', format: DEFAULT_FORMAT[kind], prompt: instruction}];
        const draftNext = {type: plan?.type || kind, title: plan?.title || instruction.slice(0, 60), rules: plan?.rules || '', pieces: pieces.map(piece => ({...piece, format: formatByKey(piece.format).key}))};
        if (draftNext.pieces.length >= 2) setDraft({...draftNext, review: true});
        else startSeries(draftNext);
        setText('');
        return;
      }
      if (action === 'adjust') {
        if (!instruction) { say('Escreva o que mudar na peça.'); return; }
        selectedVersions.forEach(({piece, version}) => generate(piece.id, {action: 'adjust', parent: version.id, prompt: instruction},
          {engine: 'adjust', base: {id: version.id, url: version.url}, format: piece.format, prompt: instruction, references: refs}).catch(error => say(error.message)));
        setText('');
        return;
      }
      if (action === 'variation') {
        const sources = selectedVersions.length ? selectedVersions : (() => { const anchor = anchorOf(currentSeries); return anchor ? [findVersion(board, anchor.id)] : []; })();
        if (!sources.length) { say('Selecione uma peça pronta para variar.'); return; }
        sources.forEach(hit => derive('variation', hit, instruction, hit.piece.format));
        setText('');
        return;
      }
      if (action === 'unfold') {
        const targets = [...unfold].map(formatByKey);
        if (!targets.length) { setUnfoldOpen(true); say('Escolha os formatos do desdobramento.'); return; }
        selectedVersions.forEach(hit => targets.filter(format => format.key !== hit.piece.format?.key).forEach(format => derive('adapt', hit, instruction, format)));
        setUnfoldOpen(false);
        setText('');
      }
    } finally { setBusy(false); }
  };

  /** Cria a série e as peças. Tipos com consistência geram a primeira e usam como âncora nas outras. */
  const startSeries = plan => {
    setDraft(null); setStartOpen(false);
    const seriesId = uid('s');
    const pieceIds = plan.pieces.map(() => uid('p'));
    setBoard(current => {
      let [next] = newSeries(current, {id: seriesId, title: plan.title, type: plan.type, rules: plan.rules});
      plan.pieces.forEach((item, index) => { [next] = newPiece(next, seriesId, {id: pieceIds[index], title: item.title, format: formatByKey(item.format)}); });
      return next;
    });
    setTimeout(() => {
      const band = layout(boardRef.current).bands.find(item => item.series.id === seriesId);
      if (band) canvas.current?.fit(band, 120);
      const anchored = plan.type !== 'anuncio' && plan.pieces.length > 1;
      // A âncora entra como referência de ESTILO (não como base de variação): as peças seguintes herdam traço e paleta, não a composição.
      const run = (index, style = null) => generate(pieceIds[index], {action: 'create', prompt: plan.pieces[index].prompt}, {engine: 'create', format: formatByKey(plan.pieces[index].format),
        prompt: plan.pieces[index].prompt, references: style ? [style, ...refs.filter(item => item.role !== 'composition')].slice(0, 2) : refs,
        creationType: plan.type, recipe: recipeFor(plan.type, {anchor: Boolean(style), rules: plan.rules}), intent: intentFor(plan.type)});
      if (!anchored) { plan.pieces.forEach((_, index) => run(index).catch(error => say(error.message))); return; }
      run(0).then(first => {
        setBoard(current => setAnchor(current, seriesId, first.versionId));
        const style = anchorReference({id: first.versionId, url: first.url, base: first.base});
        plan.pieces.slice(1).forEach((_, offset) => run(offset + 1, style).catch(error => say(error.message)));
      })
        .catch(error => say(`A primeira peça falhou e as outras esperam por ela. Use "Tentar de novo": ${error.message}`));
    }, 0);
    say(plan.pieces.length > 1 ? `${plan.pieces.length} peças na fila.` : 'Gerando a peça.');
  };

  // ---- Biblioteca da marca ----------------------------------------------------------------------------------
  const publish = async () => {
    const pending = selectedVersions.filter(hit => !hit.version.published);
    if (!pending.length) { say('Essas peças já estão na biblioteca da marca.'); return; }
    setBusy(true);
    try {
      const result = await api.publish({ctx, items: pending.map(({series, piece, version}) => ({version_id: version.id, url: version.url, title: piece.title, kind: series.type}))});
      setBoard(current => (result.published || []).reduce((next, item) => patchVersion(next, item.version_id, {published: {asset_id: item.asset_id, role: item.role, brand: ctx.brandName, at: Date.now()}}), current));
      say(`${result.published?.length || 0} ${result.published?.length === 1 ? 'peça aprovada' : 'peças aprovadas'} na biblioteca da marca ${ctx.brandName}.`);
    } catch (error) { say(error.message); }
    finally { setBusy(false); }
  };

  // ---- Download -----------------------------------------------------------------------------------------------
  const download = async versions => {
    const list = versions.filter(hit => hit?.version?.url);
    if (!list.length) { say('Selecione peças prontas para baixar.'); return; }
    if (list.length === 1) {
      const {piece, version} = list[0];
      const ext = (version.url.split('?')[0].split('.').pop() || 'png');
      const link = Object.assign(document.createElement('a'), {href: version.url, download: `${slug(piece.title)}.${ext}`}); document.body.append(link); link.click(); link.remove();
      return;
    }
    say(`Preparando ${list.length} imagens…`);
    const files = [];
    for (const {series, piece, version} of list) {
      const response = await fetch(version.url, {credentials: 'same-origin'});
      if (!response.ok) continue;
      const ext = (version.url.split('?')[0].split('.').pop() || 'png').slice(0, 5);
      const index = piece.versions.indexOf(version) + 1;
      files.push({name: `${slug(series.title)}/${slug(piece.title)}/${slug(piece.title)}_${piece.format?.width || ''}x${piece.format?.height || ''}_v${index}${piece.star === version.id ? '-base' : ''}.${ext}`,
        bytes: new Uint8Array(await response.arrayBuffer())});
    }
    saveBlob(makeZip(files), `${slug(session.title || 'quadro')}.zip`);
  };

  // ---- Atalhos ------------------------------------------------------------------------------------------------
  useEffect(() => {
    const key = event => {
      if (/INPUT|TEXTAREA|SELECT/.test(document.activeElement?.tagName)) return;
      if (event.shiftKey && event.code === 'Digit1') { canvas.current?.fit(scene.bounds); event.preventDefault(); }
      if (event.shiftKey && event.code === 'Digit2') { focusSelection(); event.preventDefault(); }
      if (event.shiftKey && event.code === 'Digit0') { setCamera(cam => ({...cam, z: 1})); event.preventDefault(); }
      if (event.key === 'Escape') setSelected(new Set());
      if ((event.key === 'Delete' || event.key === 'Backspace') && selected.size) { setBoard(current => retireVersions(current, selected)); setSelected(new Set()); }
      if ((event.metaKey || event.ctrlKey) && event.key === 'a') { selectWhere(() => true); event.preventDefault(); }
    };
    window.addEventListener('keydown', key);
    return () => window.removeEventListener('keydown', key);
  }, [scene, selected]);

  const focusSelection = () => {
    const nodes = scene.nodes.filter(node => selected.has(node.id));
    if (!nodes.length) return;
    const x0 = Math.min(...nodes.map(n => n.x)), y0 = Math.min(...nodes.map(n => n.y)), x1 = Math.max(...nodes.map(n => n.x + n.w)), y1 = Math.max(...nodes.map(n => n.y + n.h));
    canvas.current?.fit({x: x0, y: y0, w: x1 - x0, h: y1 - y0}, 160);
  };

  useEffect(() => {
    const leave = event => { if (queue.current.running || queue.current.waiting.length) { event.preventDefault(); event.returnValue = ''; } };
    window.addEventListener('beforeunload', leave);
    return () => window.removeEventListener('beforeunload', leave);
  }, []);

  const target = useMemo(() => {
    if (action === 'series') return {format: formatByKey(DEFAULT_FORMAT[kind]), type: kind, multi: false};
    if (action === 'unfold') return {format: primary?.piece.format, type: primary?.series.type, multi: true};
    const hit = primary || (anchorOf(currentSeries) ? findVersion(board, anchorOf(currentSeries).id) : null);
    return {format: hit?.piece.format, type: hit?.series.type || kind, multi: selectedVersions.length > 1 && new Set(selectedVersions.map(item => item.piece.format?.key)).size > 1};
  }, [action, kind, primary, currentSeries, board, selectedVersions]);
  useEffect(() => { setRefs(current => { const next = pruneForTarget(current, target); return next.length === current.length ? current : next; }); }, [target.format?.key, target.type, target.multi]);
  // Desdobramento sugerido segue o tipo da série selecionada.
  useEffect(() => { if (primary) setUnfold(new Set(UNFOLD_DEFAULT[primary.series.type] || UNFOLD_DEFAULT.anuncio)); }, [primary?.series.id]);

  const pending = board.series.reduce((sum, series) => sum + series.pieces.reduce((count, piece) => count + piece.versions.filter(item => item.status === 'pending').length, 0), 0);
  const actionInfo = ACTIONS.find(item => item.key === action);
  const disabledAction = item => (item.needs === 'selection' && !selectedVersions.length) || (item.needs === 'anchor' && !selectedVersions.length && !anchorOf(currentSeries));

  return <div className="mq">
    <Canvas ref={canvas} scene={scene} camera={camera} setCamera={setCamera} selected={selected} fresh={fresh.current} onSelect={onSelect} onLasso={onLasso}
      onOpen={id => { setSelected(new Set([id])); focusSelection(); }} onPin={(pieceId, pin) => setBoard(current => pinPiece(current, pieceId, pin))}/>

    {/* Superior esquerdo: quadro, projeto e séries */}
    <div className="mq-hud mq-hud--tl">
      <div className="mq-panel">
        <a className="mq-back" href={boot.links.home} aria-label="Voltar ao Studio"><Ico name="back"/></a>
        <input className="mq-title" value={session.title} onChange={event => setSession(current => ({...current, title: event.target.value}))} onBlur={() => board.series.length && persistRef.current()} aria-label="Nome do quadro"/>
      </div>
      <div className="mq-panel mq-panel--col">
        <label className="mq-field"><span>Projeto e marca</span>
          <select value={ctx.projectId} onChange={event => pickProject(projects?.find(item => String(item.id) === event.target.value))}>
            <option value="">Criação rápida · sem projeto</option>
            {(projects || []).map(item => <option key={item.id} value={item.id}>{item.name} · {item.brand_name}</option>)}
          </select></label>
        {board.series.length > 0 && <>
          <button type="button" className="mq-link-btn" onClick={() => setSeriesOpen(value => !value)}>{seriesOpen ? 'Esconder séries' : `Séries (${board.series.length})`}</button>
          {seriesOpen && <ul className="mq-series">{scene.bands.map(band => <li key={band.series.id}><button type="button" onClick={() => canvas.current?.fit(band, 120)}>
            <Glyph name={TYPES[band.series.type]?.icon || 'midia'} size={18}/><span>{band.series.title}</span><em>{band.series.pieces.length}</em></button></li>)}</ul>}
        </>}
      </div>
      <References shelf={shelf} loading={shelfLoading} target={target} picked={refs} setPicked={setRefs} onUpload={uploadRefs} open={refsOpen} setOpen={setRefsOpen}/>
    </div>

    {/* Superior direito: seleção e download */}
    <div className="mq-hud mq-hud--tr">
      <div className="mq-panel">
        {pending > 0 && <span className="mq-pending"><i/>{pending} gerando</span>}
        <button type="button" className="mq-btn" onClick={() => selectWhere(node => node.star)}>Selecionar bases ★</button>
        <button type="button" className="mq-btn" onClick={() => selectWhere(() => true)}>Todas</button>
        <button type="button" className="mq-btn" disabled={!selectedVersions.length} onClick={() => download(selectedVersions)}><Ico name="download"/>Baixar{selectedVersions.length ? ` (${selectedVersions.length})` : ''}</button>
        <button type="button" className="mq-btn is-primary" disabled={!selectedVersions.length || ctx.quick || busy} onClick={publish}
          title={ctx.quick ? 'Escolha um projeto com marca' : 'As peças aprovadas entram na biblioteca da marca'}>Aprovar na marca{selectedVersions.length ? ` (${selectedVersions.length})` : ''}</button>
      </div>
    </div>

    {/* Inspetor: só com uma peça selecionada */}
    {primaryHit && selectedHits.length === 1 && <Inspector hit={primaryHit} isAnchor={anchorOf(primaryHit.series)?.id === primaryHit.version.id}
      onAnchor={() => { setBoard(current => setAnchor(current, primaryHit.series.id, primaryHit.version.id)); say('Âncora de estilo da série atualizada. As próximas peças seguem este estilo.'); }}
      onStar={() => setBoard(current => setStar(current, primaryHit.piece.id, primaryHit.version.id))}
      onRetry={() => retry(primaryHit)} onPick={id => setSelected(new Set([id]))} onRetire={() => { setBoard(current => retireVersions(current, new Set([primaryHit.version.id]))); setSelected(new Set()); }}
      onClose={() => setSelected(new Set())}/>}

    {/* Inferior esquerdo: zoom */}
    <div className="mq-hud mq-hud--bl">
      <div className="mq-panel mq-zoom">
        <button type="button" onClick={() => canvas.current?.zoomAt(1 / 1.25)} aria-label="Diminuir zoom"><Ico name="minus"/></button>
        <button type="button" className="mq-zoom__pct" onClick={() => setCamera(cam => ({...cam, z: 1}))} title="100% (Shift+0)">{Math.round(camera.z * 100)}%</button>
        <button type="button" onClick={() => canvas.current?.zoomAt(1.25)} aria-label="Aumentar zoom"><Ico name="plus"/></button>
        <span className="mq-sep"/>
        <button type="button" onClick={() => canvas.current?.fit(scene.bounds)} title="Ver tudo (Shift+1)"><Ico name="fit"/></button>
        <button type="button" onClick={focusSelection} disabled={!selected.size} title="Ir para a seleção (Shift+2)"><Ico name="target"/></button>
        <button type="button" onClick={() => setBoard(unpinAll)} title="Reorganizar"><Ico name="grid"/></button>
      </div>
    </div>

    {/* Inferior direito: minimapa */}
    {board.series.length > 0 && <div className="mq-hud mq-hud--br"><div className="mq-panel mq-panel--flush">
      <Minimap scene={scene} camera={camera} viewport={canvas.current?.size || {w: 1200, h: 800}} onJump={(x, y) => canvas.current?.centerOn(x, y)}/>
    </div></div>}

    {/* Chat flutuante */}
    <form className="mq-chat" onSubmit={submit}>
      <div className="mq-chat__actions" role="radiogroup" aria-label="O que fazer">
        {ACTIONS.map(item => <button key={item.key} type="button" role="radio" aria-checked={action === item.key} className={action === item.key ? 'is-on' : ''}
          disabled={disabledAction(item)} onClick={() => { setAction(item.key); setActionTouched(true); }}>{item.label}</button>)}
        {action === 'unfold' && <button type="button" className="mq-chat__type" onClick={() => setUnfoldOpen(value => !value)} aria-expanded={unfoldOpen}>{unfold.size} {unfold.size === 1 ? 'formato' : 'formatos'} ▾</button>}
        {action === 'series' && <button type="button" className="mq-chat__type" onClick={() => setStartOpen(true)}><Glyph name={TYPES[kind].icon} size={16}/>{TYPES[kind].label}</button>}
      </div>
      {action === 'unfold' && unfoldOpen && <div className="mq-unfold">{formatGroups().map(([group, items]) => <fieldset key={group}><legend>{group}</legend>
        {items.map(item => <label key={item.key} className={primary?.piece.format?.key === item.key ? 'is-source' : ''}><input type="checkbox" checked={unfold.has(item.key)} disabled={primary?.piece.format?.key === item.key}
          onChange={() => setUnfold(current => { const next = new Set(current); next.has(item.key) ? next.delete(item.key) : next.add(item.key); return next; })}/>{item.label}</label>)}</fieldset>)}
        <footer><span>{selectedVersions.length > 1 ? `${selectedVersions.length} peças × ` : ''}{unfold.size} {unfold.size === 1 ? 'formato' : 'formatos'} = {selectedVersions.length * unfold.size} {selectedVersions.length * unfold.size === 1 ? 'peça nova' : 'peças novas'}</span><button type="button" className="mq-link-btn" onClick={() => setUnfold(new Set())}>Limpar</button></footer></div>}
      {refs.length > 0 && <div className="mq-chat__chips">{refs.map(item => <span key={item.id} className="mq-chip is-ref"><img src={item.url} alt=""/>{item.role === 'composition' ? 'Composição' : 'Referência'}
        <button type="button" aria-label="Tirar referência" onClick={() => setRefs(current => current.filter(entry => entry.id !== item.id))}>×</button></span>)}</div>}
      {selectedVersions.length > 0 && action !== 'series' && <div className="mq-chat__chips">{selectedVersions.slice(0, 6).map(({piece, version}) => <span key={version.id} className="mq-chip"><img src={version.url} alt=""/>{piece.title}</span>)}
        {selectedVersions.length > 6 && <span className="mq-chip">+{selectedVersions.length - 6}</span>}</div>}
      <div className="mq-chat__row">
        <textarea value={text} onChange={event => setText(event.target.value)} rows={text.length > 120 ? 4 : 1}
          placeholder={action === 'adjust' ? 'O que mudar? Ex.: trocar o fundo por noite, corrigir "HORAA" para "HORAS"' : action === 'variation' ? 'O que muda nesta variação? (opcional)' : action === 'unfold' ? 'Algum cuidado no desdobramento? (opcional)' : 'Descreva a criação ou cole o plano com todas as peças'}
          onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey) submit(event); }} aria-label="Instrução"/>
        <button type="submit" className="mq-send" disabled={busy || (action === 'adjust' && !text.trim())} aria-label="Enviar"><Ico name="send"/></button>
      </div>
      <small className="mq-chat__hint">{actionInfo?.hint}{action !== 'series' && selectedVersions.length > 1 ? ` Vale para as ${selectedVersions.length} selecionadas.` : ''}</small>
    </form>

    {notice && <div className="mq-toast" role="status">{notice}</div>}
    {startOpen && <StartModal current={kind} onPick={type => { setKind(type); setAction('series'); setActionTouched(true); setStartOpen(false); }} onClose={() => setStartOpen(false)} hasBoard={board.series.length > 0}/>}
    {draft?.review && <DraftReview draft={draft} setDraft={setDraft} onGo={() => startSeries(draft)}/>}
    {busy && <div className="mq-busy"><i/>Separando as peças do pedido…</div>}
  </div>;
}

function Inspector({hit, isAnchor, onAnchor, onStar, onRetry, onPick, onRetire, onClose}) {
  const {piece, version, series} = hit;
  const live = piece.versions.filter(item => !item.retired);
  return <aside className="mq-hud mq-inspector mq-panel mq-panel--col" aria-label="Detalhes da peça">
    <header><div><small>{series.title}</small><strong>{piece.title}</strong><em>{piece.format?.label} · {piece.format?.width}×{piece.format?.height}</em></div>
      <button type="button" className="mq-icon" onClick={onClose} aria-label="Fechar"><Ico name="close"/></button></header>
    <div className="mq-inspector__versions">{live.map((item, index) => <button key={item.id} type="button" className={`${item.id === version.id ? 'is-on' : ''}${item.id === piece.star ? ' is-star' : ''}`} onClick={() => onPick(item.id)}>
      {item.status === 'ready' ? <img src={item.url} alt=""/> : <span>{item.status === 'pending' ? '…' : '!'}</span>}<em>v{piece.versions.indexOf(item) + 1}{item.id === piece.star ? ' ★' : ''}</em></button>)}</div>
    {version.prompt && <p className="mq-inspector__prompt"><b>{ACTION_LABEL[version.action] || 'Pedido'}:</b> {version.prompt.slice(0, 280)}</p>}
    {version.status === 'error' && <p className="mq-inspector__error">{version.error}</p>}
    {version.published && <p className="mq-inspector__published">✓ Na biblioteca da marca {version.published.brand} ({ {illustration: 'Ilustração', icon: 'Ícone', creative: 'Peça criativa'}[version.published.role] || version.published.role })</p>}
    {version.review?.reviewed && <div className="mq-inspector__review"><b>Revisão automática{version.review.score != null ? ` · ${version.review.score}` : ''}</b>
      {version.review.retried && <span>Corrigida por edição: {version.review.reason_text || 'problema encontrado na 1ª versão'}.</span>}
      {(version.review.notes || []).map(note => <span key={note}>⚠ {note}</span>)}
      {!version.review.retried && !(version.review.notes || []).length && <span>Sem problemas encontrados.</span>}</div>}
    <div className="mq-inspector__actions">
      {version.status === 'error' && version.req && <button type="button" className="mq-btn is-primary" onClick={onRetry}>Tentar de novo</button>}
      {version.status === 'ready' && <button type="button" className="mq-btn" disabled={piece.star === version.id} onClick={onStar}><Ico name="star"/>{piece.star === version.id ? 'É a base' : 'Usar como base'}</button>}
      {version.status === 'ready' && <button type="button" className="mq-btn" disabled={isAnchor} onClick={onAnchor} title="As próximas peças da série copiam o estilo desta, não a composição">⚓ {isAnchor ? 'É a âncora da série' : 'Usar como âncora'}</button>}
      <button type="button" className="mq-btn" onClick={onRetire}><Ico name="trash"/>Retirar</button>
    </div>
  </aside>;
}

function StartModal({current, onPick, onClose, hasBoard}) {
  return <div className="mq-modal" role="dialog" aria-modal="true" aria-labelledby="mqStartTitle" onPointerDown={event => event.target === event.currentTarget && hasBoard && onClose()}>
    <div className="mq-modal__box mq-start">
      <header><div><small>Cadu Studio</small><h1 id="mqStartTitle">O que vamos criar?</h1>
        <p>Escolha o tipo. A marca do projeto (logo, cores, fontes e tom) entra em todas as peças. Se você já tem um plano com várias peças, escolha o tipo e cole o plano no chat: o Studio separa as peças para você revisar antes de gerar.</p></div>
        {hasBoard && <button type="button" className="mq-icon" onClick={onClose} aria-label="Fechar"><Ico name="close"/></button>}</header>
      <div className="mq-start__grid">{Object.entries(TYPES).map(([key, item]) => <button key={key} type="button" className={current === key ? 'is-on' : ''} onClick={() => onPick(key)}>
        <span className="mq-start__icon"><Glyph name={item.icon} size={34}/></span><strong>{item.label}</strong><small>{item.hint}</small></button>)}</div>
    </div>
  </div>;
}

function DraftReview({draft, setDraft, onGo}) {
  const update = (index, patch) => setDraft(current => ({...current, pieces: current.pieces.map((piece, at) => at === index ? {...piece, ...patch} : piece)}));
  const remove = index => setDraft(current => ({...current, pieces: current.pieces.filter((_, at) => at !== index)}));
  return <div className="mq-modal" role="dialog" aria-modal="true" aria-labelledby="mqDraftTitle">
    <div className="mq-modal__box mq-draft">
      <header><div><small>{TYPES[draft.type]?.label} · revise antes de gerar</small><h1 id="mqDraftTitle">{draft.pieces.length} peças encontradas no pedido</h1></div>
        <button type="button" className="mq-icon" onClick={() => setDraft(current => ({...current, review: false}))} aria-label="Cancelar"><Ico name="close"/></button></header>
      <label className="mq-field"><span>Nome da série</span><input value={draft.title} onChange={event => setDraft(current => ({...current, title: event.target.value}))}/></label>
      <label className="mq-field"><span>Regras que valem para todas as peças</span><textarea rows={2} value={draft.rules} onChange={event => setDraft(current => ({...current, rules: event.target.value}))}/></label>
      <ol className="mq-draft__list">{draft.pieces.map((piece, index) => <li key={index}>
        <input value={piece.title} onChange={event => update(index, {title: event.target.value})} aria-label="Nome da peça"/>
        <select value={piece.format} onChange={event => update(index, {format: event.target.value})} aria-label="Formato">{FORMATS.map(item => <option key={item.key} value={item.key}>{item.label}</option>)}</select>
        <textarea rows={2} value={piece.prompt} onChange={event => update(index, {prompt: event.target.value})} aria-label="Pedido da peça"/>
        <button type="button" className="mq-icon" onClick={() => remove(index)} aria-label="Tirar peça"><Ico name="trash"/></button>
      </li>)}</ol>
      <footer><span>{draft.type !== 'anuncio' && draft.pieces.length > 1 ? 'A primeira peça é gerada antes e vira a âncora de estilo das outras.' : 'As peças são geradas em paralelo.'}</span>
        <button type="button" className="mq-btn is-primary" disabled={!draft.pieces.length} onClick={onGo}>Gerar {draft.pieces.length} {draft.pieces.length === 1 ? 'peça' : 'peças'}</button></footer>
    </div>
  </div>;
}
