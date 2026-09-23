import React, {useEffect, useMemo, useRef, useState} from 'react';

const DURATION = 30;
const initialBlocks = [
  {id:'a', name:'Abertura', text:'A primavera chegou. É tempo de descobrir novas histórias.', start:0, duration:5},
  {id:'b', name:'Oferta', text:'Produtos selecionados com até 40% de desconto. Renove o que faz bem.', start:5, duration:10},
  {id:'c', name:'Prova', text:'Mais conforto, estilo e qualidade para acompanhar todos os dias.', start:15, duration:10},
  {id:'d', name:'Encerramento', text:'Aproveite nas lojas e no site. Primavera é agora.', start:25, duration:5},
];
const initialTracks = [
  {id:'voice', name:'Locução', kind:'voice', gain:0, muted:false, solo:false, clips:[{id:'a1', name:'Abertura', start:0.3, duration:8.3},{id:'a2', name:'Oferta', start:8.9, duration:10.5},{id:'a3', name:'Prova', start:19.8, duration:6.5}]},
  {id:'voice2', name:'Segunda voz', kind:'voice2', gain:-2, muted:false, solo:false, clips:[{id:'b1', name:'Encerramento', start:23.6, duration:5.8}]},
  {id:'music', name:'Música', kind:'music', gain:-6, muted:false, solo:false, clips:[{id:'c1', name:'Trilha principal', start:0, duration:30}]},
  {id:'ambient', name:'Ambiente', kind:'ambient', gain:-12, muted:false, solo:false, clips:[{id:'d1', name:'Sala leve', start:0, duration:30}]},
  {id:'effects', name:'Efeitos', kind:'effect', gain:-6, muted:false, solo:false, clips:[{id:'e1', name:'Vinheta', start:0.2, duration:4.2},{id:'e2', name:'Transição', start:27.5, duration:2.2}]},
];
const uid = () => globalThis.crypto?.randomUUID?.() || `id-${Date.now()}-${Math.random()}`;
const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
const time = value => `00:${String(Math.floor(value)).padStart(2,'0')}.${String(Math.round((value % 1)*1000)).padStart(3,'0')}`;

function Waveform({seed=1}) {
  const bars = useMemo(() => Array.from({length:90}, (_, index) => {
    const wave = Math.abs(Math.sin((index + seed*9)*2.17) * Math.cos((index + seed*3)*0.29));
    return Math.max(8, Math.round((0.12 + wave*0.88) * (seed === 4 ? 31 : 46)));
  }), [seed]);
  return <span className="au-wave" aria-hidden="true">{bars.map((height,index)=><i key={index} style={{height:`${height}%`}}/>)}</span>;
}

function Topbar({bootstrap, projects, project, projectLoading, projectError, onProjectChange, onExport}) {
  const links = bootstrap.links || {};
  return <header className="au-topbar">
    <a className="au-brand" href={links.home || '/'}><img src={bootstrap.logo || '/static/images/cadu/brand-icons/studio-192.png'} alt=""/><strong>Cadu</strong><span>Studio</span></a>
    <nav aria-label="Navegação do Studio">{[['Criar','create'],['Editor','editor'],['Vídeos','videos'],['Áudio','audio'],['Analyzer','analyzer'],['Biblioteca','library']].map(([label,key])=><a key={key} href={links[key] || '#'} className={key==='audio'?'is-active':''} aria-current={key==='audio'?'page':undefined}>{label}</a>)}</nav>
    <label className="au-project-picker"><span>Projeto e marca</span><select aria-label="Projeto ativo" value={project?.id || ''} onChange={event=>onProjectChange(event.target.value)} disabled={projectLoading}><option value="">{projectLoading?'Carregando projetos…':'Sessão pessoal'}</option>{projects.map(item=><option key={item.id} value={item.id}>{item.name}{item.brand_name?` · ${item.brand_name}`:''}</option>)}</select>{projectError&&<small title={projectError}>Projetos indisponíveis</small>}</label>
    <a className="au-credits" href={links.credits || '#'}><small>Uso e créditos</small><b>{Number(bootstrap.credits || 0).toLocaleString('pt-BR')}</b><i><em style={{width:`${Math.min(100,Number(bootstrap.usagePercent || 0))}%`}}/></i></a>
    <button className="au-primary au-export" onClick={onExport}>Exportar áudio</button>
    <a className="au-avatar" href={links.profile || '#'} aria-label="Abrir conta">{bootstrap.user?.avatar?<img src={bootstrap.user.avatar} alt=""/>:String(bootstrap.user?.name || 'C').slice(0,1).toUpperCase()}</a>
  </header>;
}

function Timeline({tracks, setTracks, playhead, setPlayhead, selectedClip, setSelectedClip, onSplit, onSeparate}) {
  const rulerRef = useRef(null);
  const drag = useRef(null);
  const [draft, setDraft] = useState(null);
  const updateTrack = (trackId, patch) => setTracks(rows => rows.map(row => row.id === trackId ? {...row,...patch} : row));
  const selectedData = tracks.find(row=>row.id===selectedClip?.trackId)?.clips.find(clip=>clip.id===selectedClip?.clipId);
  const updateSelected = (field,value) => setTracks(rows=>rows.map(row=>row.id===selectedClip?.trackId?{...row,clips:row.clips.map(clip=>clip.id===selectedClip?.clipId?{...clip,[field]:field==='start'?clamp(value,0,DURATION-clip.duration):clamp(value,.5,DURATION-clip.start)}:clip)}:row));
  const beginDrag = (event, trackId, clip, edge) => {
    if (event.button !== 0) return;
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    const row = tracks.find(item=>item.id===trackId);
    drag.current = {trackId,clipId:clip.id,edge,x:event.clientX,start:clip.start,duration:clip.duration,row};
    setSelectedClip({trackId,clipId:clip.id});
  };
  const moveDrag = event => {
    if (!drag.current) return;
    const width = event.currentTarget.closest('.au-track-line')?.getBoundingClientRect().width || 1;
    const delta = ((event.clientX - drag.current.x) / width) * DURATION;
    const {start,duration,edge} = drag.current;
    let nextStart = start, nextDuration = duration;
    if (edge === 'left') { nextStart = clamp(start + delta, 0, start + duration - .5); nextDuration = duration - (nextStart-start); }
    else if (edge === 'right') nextDuration = clamp(duration + delta,.5,DURATION-start);
    else nextStart = clamp(start + delta,0,DURATION-duration);
    setDraft({trackId:drag.current.trackId,clipId:drag.current.clipId,start:nextStart,duration:nextDuration});
  };
  const finishDrag = () => {
    if (draft) setTracks(rows=>rows.map(row=>row.id===draft.trackId?{...row,clips:row.clips.map(clip=>clip.id===draft.clipId?{...clip,start:draft.start,duration:draft.duration}:clip)}:row));
    drag.current=null; setDraft(null);
  };
  const rulerClick = event => { const rect=rulerRef.current.getBoundingClientRect(); setPlayhead(clamp((event.clientX-rect.left)/rect.width*DURATION,0,DURATION)); };
  return <section className="au-timeline" aria-label="Editor multifaixa">
    <div className="au-timeline-head"><div><h2>Montagem</h2><span>{tracks.length} faixas · 30 segundos</span></div><div className="au-timeline-tools">{selectedData&&<div className="au-clip-fields"><label>Início <input type="number" min="0" max="30" step="0.1" value={Number(selectedData.start.toFixed(1))} onChange={event=>updateSelected('start',Number(event.target.value))}/></label><label>Duração <input type="number" min="0.5" max="30" step="0.1" value={Number(selectedData.duration.toFixed(1))} onChange={event=>updateSelected('duration',Number(event.target.value))}/></label></div>}<button onClick={onSplit} disabled={!selectedClip}>Dividir no cursor</button><button onClick={onSeparate} disabled={!selectedClip}>Separar em faixa</button><button onClick={()=>{setTracks(rows=>[...rows,{id:uid(),name:`Nova faixa ${rows.length+1}`,kind:'other',gain:0,muted:false,solo:false,clips:[]}]);}}>+ Nova faixa</button></div></div>
    <div className="au-timeline-grid">
      <div className="au-ruler-label">Faixas</div><div className="au-ruler" ref={rulerRef} onClick={rulerClick} role="slider" tabIndex={0} aria-label="Posição do cursor" aria-valuemin={0} aria-valuemax={30} aria-valuenow={Math.round(playhead)} onKeyDown={event=>{if(event.key==='ArrowRight')setPlayhead(clamp(playhead+.5,0,30));if(event.key==='ArrowLeft')setPlayhead(clamp(playhead-.5,0,30));}}>{Array.from({length:7},(_,index)=><span key={index} style={{left:`${index/6*100}%`}}>{index*5}s</span>)}<i className="au-playhead-marker" style={{left:`${playhead/DURATION*100}%`}}/></div>
      {tracks.map((track,index)=><React.Fragment key={track.id}><div className="au-track-label"><span className={`au-track-dot is-${track.kind}`}/><input aria-label={`Nome da faixa ${index+1}`} value={track.name} onChange={event=>updateTrack(track.id,{name:event.target.value})}/><button className={track.muted?'is-on':''} onClick={()=>updateTrack(track.id,{muted:!track.muted})} aria-label={`Silenciar ${track.name}`} aria-pressed={track.muted}>M</button><button className={track.solo?'is-on':''} onClick={()=>updateTrack(track.id,{solo:!track.solo})} aria-label={`Solo ${track.name}`} aria-pressed={track.solo}>S</button><small>{track.gain} dB</small></div><div className={`au-track-line is-${track.kind} ${track.muted?'is-muted':''}`}>
        {track.clips.map((clip,clipIndex)=>{const data=draft?.clipId===clip.id?draft:clip;return <div key={clip.id} className={`au-clip ${selectedClip?.clipId===clip.id?'is-selected':''}`} style={{left:`${data.start/DURATION*100}%`,width:`${data.duration/DURATION*100}%`}} onPointerDown={event=>beginDrag(event,track.id,clip,'move')} onPointerMove={moveDrag} onPointerUp={finishDrag} onPointerCancel={finishDrag} onClick={event=>event.stopPropagation()}><Waveform seed={index+clipIndex+1}/><span className="au-clip-name">{clip.name}</span><span className="au-trim is-left" onPointerDown={event=>{event.stopPropagation();beginDrag(event,track.id,clip,'left');}} onPointerMove={moveDrag} onPointerUp={finishDrag} aria-hidden="true"/><span className="au-trim is-right" onPointerDown={event=>{event.stopPropagation();beginDrag(event,track.id,clip,'right');}} onPointerMove={moveDrag} onPointerUp={finishDrag} aria-hidden="true"/>{track.kind==='music'&&<svg className="au-duck" viewBox="0 0 100 30" preserveAspectRatio="none"><polyline points="0,6 34,6 39,21 58,21 63,6 100,6"/></svg>}</div>})}
        <span className="au-playhead" style={{left:`${playhead/DURATION*100}%`}}/>
      </div></React.Fragment>)}
    </div>
    <p className="au-timeline-help">Arraste o corpo do clipe para mover. Arraste as extremidades para aparar; selecione e use “Dividir no cursor” para separar.</p>
  </section>;
}

export default function AudioStudioApp({bootstrap={}}) {
  const [projects,setProjects]=useState(bootstrap.projects || []);
  const [projectId,setProjectId]=useState(bootstrap.projectId || '');
  const [projectLoading,setProjectLoading]=useState(!bootstrap.projects && Boolean(bootstrap.apiRoot));
  const [projectError,setProjectError]=useState('');
  const [blocks,setBlocks]=useState(initialBlocks);
  const [tracks,setTracks]=useState(initialTracks);
  const [playhead,setPlayhead]=useState(8.24);
  const [selectedClip,setSelectedClip]=useState(null);
  const [activeBlock,setActiveBlock]=useState('b');
  const [agentText,setAgentText]=useState('Deixe a voz mais clara e abaixe a música durante a fala.');
  const [proposal,setProposal]=useState(null);
  const [notice,setNotice]=useState('');
  const [playing,setPlaying]=useState(false);
  const [tab,setTab]=useState('Roteiro');
  const [modal,setModal]=useState(false);
  const [imported,setImported]=useState([]);
  const importedUrls=useRef([]);
  const timer=useRef(null);
  useEffect(()=>{if(!bootstrap.apiRoot||bootstrap.projects)return;let active=true;fetch(`${bootstrap.apiRoot}/format-lab/studio/project-contexts`,{credentials:'same-origin',headers:{Accept:'application/json'}}).then(async response=>{const body=await response.json();if(!response.ok||!body.success)throw new Error(body.error||'Não foi possível abrir os projetos.');return body.data?.items||[];}).then(items=>{if(!active)return;setProjects(items);const requested=String(bootstrap.projectId||'').replace(/^ci:/,'');const match=items.find(item=>[item.id,item.external_project_id].some(id=>String(id||'').replace(/^ci:/,'')===requested));setProjectId(match?.id||'');setProjectError('');}).catch(error=>{if(active)setProjectError(error.message);}).finally(()=>{if(active)setProjectLoading(false);});return()=>{active=false;};},[bootstrap.apiRoot,bootstrap.projectId,bootstrap.projects]);
  const project=projects.find(item=>String(item.id)===String(projectId))||null;
  useEffect(()=>{if(!playing)return;timer.current=window.setInterval(()=>setPlayhead(value=>value>=DURATION?(setPlaying(false),0):value+.05),50);return()=>window.clearInterval(timer.current);},[playing]);
  const chars=blocks.reduce((sum,block)=>sum+block.text.length,0);
  const split=()=>{if(!selectedClip)return;setTracks(rows=>rows.map(row=>row.id!==selectedClip.trackId?row:{...row,clips:row.clips.flatMap(clip=>{if(clip.id!==selectedClip.clipId||playhead<=clip.start+.2||playhead>=clip.start+clip.duration-.2)return [clip];return [{...clip,duration:playhead-clip.start},{...clip,id:uid(),name:`${clip.name} · corte`,start:playhead,duration:clip.start+clip.duration-playhead}];})}));setNotice('Clipe dividido no cursor.');};
  const separate=()=>{if(!selectedClip)return;const source=tracks.find(row=>row.id===selectedClip.trackId);const clip=source?.clips.find(item=>item.id===selectedClip.clipId);if(!clip)return;const trackId=uid();setTracks(rows=>[...rows.map(row=>row.id===source.id?{...row,clips:row.clips.filter(item=>item.id!==clip.id)}:row),{id:trackId,name:`${source.name} · separado`,kind:source.kind,gain:source.gain,muted:false,solo:false,clips:[clip]}]);setSelectedClip({trackId,clipId:clip.id});setNotice('Clipe movido para uma faixa independente.');};
  const analyzeAgent=()=>{const lower=agentText.toLowerCase();const actions=[];if(/roteiro|texto|frase|curt|resum/.test(lower))actions.push({type:'script.rewrite',target:activeBlock,label:'Refinar o bloco selecionado',paid:true});if(/música|trilha|abaix|volume|duck/.test(lower))actions.push({type:'track.gain',target:'music',value:-7,label:'Reduzir a música em 7 dB durante a fala',paid:false});if(/ruído|limp|clara|clareza/.test(lower))actions.push({type:'track.denoise',target:'voice',value:'leve',label:'Limpar ruído da locução',paid:true});if(!actions.length)actions.push({type:'session.review',target:'session',label:'Revisar roteiro e montagem',paid:true});setProposal({id:uid(),intent:agentText,scope:selectedClip?{trackId:selectedClip.trackId,clipId:selectedClip.clipId}:{blockId:activeBlock},context:{duration:DURATION,playhead,script:blocks.map(({id,name,text,start,duration})=>({id,name,text,start,duration})),tracks:tracks.map(({id,name,kind,gain,clips})=>({id,name,kind,gain,clips:clips.map(({id,start,duration})=>({id,start,duration}))}))},constraints:{preserveApprovedText:true,neverTruncateSpeech:true,requireTokenQuote:true},actions,estimatedTokens:actions.some(action=>action.paid)?1240:0});};
  const applyProposal=()=>{if(!proposal)return;if(proposal.actions.some(action=>action.paid)){setNotice('Proposta preparada. A integração paga e o débito de tokens ainda não estão conectados neste protótipo.');return;}setTracks(rows=>rows.map(row=>row.id==='music'?{...row,gain:-7}:row));setProposal(null);setNotice('Volume da música ajustado na sessão.');};
  const importAudio=event=>{const files=Array.from(event.target.files || []);if(!files.length)return;const additions=files.map(file=>({id:uid(),name:file.name,url:URL.createObjectURL(file)}));importedUrls.current.push(...additions.map(file=>file.url));setImported(rows=>[...rows,...additions]);setNotice(`${files.length} arquivo(s) adicionado(s) à biblioteca local.`);event.target.value='';};
  useEffect(()=>()=>importedUrls.current.forEach(url=>URL.revokeObjectURL(url)),[]);
  return <div className="au-app"><Topbar bootstrap={bootstrap} projects={projects} project={project} projectLoading={projectLoading} projectError={projectError} onProjectChange={id=>{setProjectId(id);setNotice(id?'Projeto selecionado. Esta prévia ainda não persiste a sessão.':'Sessão pessoal selecionada.');}} onExport={()=>setModal(true)}/>
    <div className="au-sessionbar"><div><strong>Campanha primavera · Spot 30s</strong><span>{project?`${project.name} · ${project.brand_name||'Marca vinculada'}`:'Sessão pessoal de áudio'}</span></div><span className="au-saved">● Rascunho local</span><div className="au-session-actions"><button onClick={()=>setNotice('Histórico de revisões disponível na implementação da sessão.')}>Histórico</button><button onClick={()=>setNotice('A sessão será salva no projeto após conectar o serviço de áudio.')}>Salvar sessão</button></div></div>
    <main className="au-main">
      <div className="au-upper">
        <aside className="au-library"><div className="au-section-title"><h2>Biblioteca</h2><button onClick={()=>document.getElementById('au-file')?.click()}>+ Importar</button></div><input id="au-file" type="file" accept="audio/*" multiple hidden onChange={importAudio}/><label className="au-search"><span>⌕</span><input placeholder="Buscar áudio" aria-label="Buscar áudio"/></label><div className="au-library-category"><strong>Nesta sessão</strong><span>Roteiro aprovado</span><span>Locuções <small>2</small></span><span>Música <small>1</small></span><span>Efeitos <small>2</small></span></div><div className="au-library-category"><strong>Arquivos importados</strong>{imported.length?imported.map(file=><audio key={file.id} controls src={file.url} title={file.name}/>):<p>Importe um arquivo para ouvir e organizar nesta sessão.</p>}</div><button className="au-library-voice" onClick={()=>{setTab('Criar voz');setNotice('Escolha um bloco do roteiro para preparar uma voz.');}}>＋ Criar voz a partir do roteiro</button></aside>
        <section className="au-script"><div className="au-section-title"><div><h1>Roteiro e criação</h1><p>Escreva por blocos. Cada voz entra na montagem no tempo escolhido.</p></div><span>{chars} caracteres</span></div><div className="au-tabs" role="tablist" aria-label="Atividade">{['Roteiro','Criar voz','Música','Efeitos','Transcrição'].map(item=><button key={item} role="tab" aria-selected={tab===item} className={tab===item?'is-active':''} onClick={()=>setTab(item)}>{item}</button>)}</div>{tab==='Roteiro'||tab==='Criar voz'?<div className="au-blocks">{blocks.map(block=><div className={`au-block ${activeBlock===block.id?'is-active':''}`} key={block.id}><button className="au-block-name" onClick={()=>{setActiveBlock(block.id);setPlayhead(block.start);}}>{block.name}<small>{block.start}–{block.start+block.duration}s</small></button><textarea aria-label={`Texto de ${block.name}`} value={block.text} onFocus={()=>setActiveBlock(block.id)} onChange={event=>setBlocks(rows=>rows.map(row=>row.id===block.id?{...row,text:event.target.value}:row))}/></div>)}</div>:<div className="au-activity"><h2>{tab==='Música'?'Criar uma trilha':tab==='Efeitos'?'Criar um efeito':'Transcrever áudio'}</h2><p>{tab==='Transcrição'?'Selecione um áudio da biblioteca para criar texto sincronizado.':`Descreva o que você precisa e escolha uma faixa para inserir ${tab==='Música'?'a música':'o efeito'}.`}</p><textarea placeholder={tab==='Música'?'Ex.: trilha leve, otimista, sem voz…':tab==='Efeitos'?'Ex.: vinheta curta de abertura…':'Selecione um áudio importado…'} /><button className="au-primary" onClick={()=>setNotice('Geração e transcrição serão conectadas ao tokenizador antes de serem executadas.')}>Preparar atividade</button></div>}<div className="au-script-footer"><span>{chars} caracteres · duração alvo 30 s</span><button onClick={()=>setNotice('A amostra de voz será disponibilizada com a integração de áudio.')}>Ouvir amostra</button><button className="au-primary" onClick={()=>setNotice('A geração de voz será conectada ao tokenizador antes de iniciar.')}>Criar voz neste intervalo</button></div></section>
        <aside className="au-agent"><div className="au-section-title"><div><h2>Agente de áudio</h2><p>Roteiro, voz e mixagem no contexto da sessão.</p></div><span>✦</span></div><div className="au-agent-scope">Escopo: {selectedClip?`clipe selecionado · ${tracks.find(track=>track.id===selectedClip.trackId)?.name}`:`bloco ${blocks.find(block=>block.id===activeBlock)?.name}`}</div><div className="au-agent-thread"><div className="au-agent-user">{agentText}</div>{proposal&&<div className="au-agent-proposal"><strong>Proposta de edição</strong>{proposal.actions.map((action,index)=><p key={index}>{action.label}</p>)}<small>{proposal.estimatedTokens?`Estimativa: ${proposal.estimatedTokens.toLocaleString('pt-BR')} tokens`:'Sem custo de IA'}</small><div><button onClick={()=>setNotice('A prévia de áudio será ligada ao render da sessão.')}>Ouvir proposta</button><button className="au-primary" onClick={applyProposal}>Aplicar</button><button onClick={()=>setProposal(null)}>Descartar</button></div></div>}</div><label className="au-agent-input"><textarea value={agentText} onChange={event=>setAgentText(event.target.value)} placeholder="Peça uma alteração no roteiro ou no som…"/><button className="au-primary" onClick={analyzeAgent} disabled={!agentText.trim()}>Preparar proposta</button></label><div className="au-agent-shortcuts"><button onClick={()=>setAgentText('Refine o bloco selecionado mantendo a oferta e a duração.')}>Refinar roteiro</button><button onClick={()=>setAgentText('Reduza a música durante a locução.')}>Equilibrar música</button></div></aside>
      </div>
      <div className="au-transport"><div><button className="au-play" onClick={()=>setPlaying(!playing)} aria-label={playing?'Pausar':'Reproduzir'}>{playing?'Ⅱ':'▶'}</button><button onClick={()=>setPlayhead(0)} aria-label="Voltar ao início">↤</button><button onClick={()=>setNotice('Gravação de microfone será integrada à faixa selecionada.')} aria-label="Gravar">●</button><strong>{time(playhead)} <span>/ 00:30.000</span></strong></div><div><span>Montagem multifaixa</span><button onClick={split} disabled={!selectedClip}>✂ Dividir</button><button onClick={()=>setPlayhead(8.24)}>↺ Voltar à seleção</button></div><div><span>Saída final</span><i className="au-meter"><b/></i><small>-14,2 LUFS</small><small>Pico -1,0 dB</small></div></div>
      <Timeline tracks={tracks} setTracks={setTracks} playhead={playhead} setPlayhead={setPlayhead} selectedClip={selectedClip} setSelectedClip={setSelectedClip} onSplit={split} onSeparate={separate}/>
    </main>
    {notice&&<div className="au-toast" role="status">{notice}<button onClick={()=>setNotice('')} aria-label="Fechar aviso">×</button></div>}
    {modal&&<div className="au-modal-backdrop" onClick={()=>setModal(false)}><section className="au-modal" role="dialog" aria-modal="true" aria-labelledby="au-export-title" onClick={event=>event.stopPropagation()}><button className="au-modal-close" onClick={()=>setModal(false)} aria-label="Fechar">×</button><h2 id="au-export-title">Exportar áudio</h2><p>Este protótipo mostra a montagem e seus controles. A renderização final será conectada ao serviço de áudio e ao tokenizador.</p><label>Formato<select><option>WAV · 48 kHz · estéreo</option><option>MP3 · 320 kb/s</option></select></label><button className="au-primary" onClick={()=>setModal(false)}>Voltar à edição</button></section></div>}
  </div>;
}
