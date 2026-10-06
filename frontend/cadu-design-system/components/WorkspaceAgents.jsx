import React, {useCallback, useEffect, useState} from 'react';
import {CaduButton} from './CaduButton';

const CLIENTS = [
  {id: 'codex', title: 'Codex', hint: 'Requer o Codex CLI instalado e um terminal.', command: endpoint => `codex mcp add cadu --url ${endpoint}\ncodex mcp login cadu`,
    steps: ['Execute os dois comandos. O segundo abre o login no navegador.', 'Confira o aplicativo e aprove as permissões no Cadu.', 'Confirme `cadu` em `codex mcp list` e abra uma nova conversa.']},
  {id: 'claude', title: 'Claude (web e desktop)', hint: 'Não precisa instalar nada.', command: endpoint => endpoint,
    steps: ['Em Configurações → Conectores, escolha adicionar conector personalizado.', 'Cole a URL acima como endereço do servidor.', 'Entre no Cadu quando o navegador abrir e aprove as permissões.']},
  {id: 'claude-code', title: 'Claude Code', hint: 'Requer o Claude Code instalado.', command: endpoint => `claude mcp add --transport http cadu ${endpoint}`,
    steps: ['Execute o comando no terminal.', 'Dentro do Claude Code, abra /mcp e escolha cadu para entrar.', 'Aprove as permissões no Cadu.']},
  {id: 'vscode', title: 'VS Code', hint: 'Abre o editor com a instalação pronta.', command: endpoint => endpoint,
    install: endpoint => `vscode:mcp/install?${encodeURIComponent(JSON.stringify({name: 'cadu', type: 'http', url: endpoint}))}`,
    steps: ['Use o botão para abrir o VS Code e confirme a instalação.', 'Inicie o servidor cadu; o navegador abre o login.', 'Aprove as permissões no Cadu.']},
  {id: 'cursor', title: 'Cursor', hint: 'Abre o Cursor com a instalação pronta.', command: endpoint => endpoint,
    install: endpoint => `https://cursor.com/en-US/install-mcp?name=cadu&config=${encodeURIComponent(btoa(JSON.stringify({url: endpoint})))}`,
    steps: ['Use o botão para instalar no Cursor.', 'Habilite cadu e entre no Cadu quando o navegador abrir.', 'Aprove as permissões.']},
  {id: 'chatgpt', title: 'ChatGPT', hint: 'Plugin do Cadu ainda não publicado.', unavailable: true, command: () => '',
    steps: ['A instalação depende da publicação do plugin Cadu no ChatGPT.', 'Enquanto isso, use Claude ou Codex.']},
  {id: 'other', title: 'Outro aplicativo MCP', hint: 'Qualquer cliente compatível com MCP remoto e OAuth.', command: endpoint => endpoint,
    steps: ['Adicione um servidor MCP remoto com a URL acima.', 'Quando o aplicativo pedir autenticação, entre no Cadu e aprove.']},
];

const STATUS = {concluida: {label: 'Concluída', mark: '✓'}, pendente: {label: 'Pendente', mark: '·'}, falhou: {label: 'Falhou', mark: '!'}};
const dateTime = value => value ? new Intl.DateTimeFormat('pt-BR', {dateStyle: 'short', timeStyle: 'short'}).format(new Date(value)) : '—';

export function AgentConnect({bootstrap}) {
  const stateUrl = bootstrap.endpoints.agentState;
  const [state, setState] = useState(null);
  const [error, setError] = useState('');
  const [client, setClient] = useState(CLIENTS[0].id);
  const [copied, setCopied] = useState(false);
  const [message, setMessage] = useState('');

  const load = useCallback(async () => {
    setError('');
    try {
      const response = await fetch(stateUrl, {credentials: 'same-origin'});
      if (!response.ok) throw new Error();
      setState(await response.json());
    } catch { setError('Não foi possível verificar a conexão agora.'); }
  }, [stateUrl]);
  useEffect(() => { load(); }, [load]);

  const post = async (url, body) => {
    setMessage('Atualizando…');
    try {
      const response = await fetch(url, {method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': bootstrap.csrf}, body: JSON.stringify(body || {})});
      const result = await response.json().catch(() => ({}));
      setMessage(response.ok ? 'Atualizado.' : result.error || 'Não foi possível atualizar.');
      if (response.ok) load();
    } catch { setMessage('Não foi possível concluir agora.'); }
  };

  const current = CLIENTS.find(item => item.id === client) || CLIENTS[0];
  const endpoint = state?.endpoint || '';
  const command = endpoint ? current.command(endpoint) : '';
  const copy = async () => {
    try { await navigator.clipboard.writeText(command); setCopied(true); setTimeout(() => setCopied(false), 1600); } catch { setMessage('Copie o texto manualmente.'); }
  };
  const diagnosis = state?.diagnosis;
  const totalSteps = (diagnosis?.steps || []).length;
  const doneSteps = (diagnosis?.steps || []).filter(step => step.status === 'concluida').length;
  const activeGrants = (state?.grants || []).filter(grant => grant.status === 'active');
  const toggleModule = (grant, moduleId) => {
    const next = grant.modules.includes(moduleId) ? grant.modules.filter(item => item !== moduleId) : [...grant.modules, moduleId];
    if (!next.length) return setMessage('Ative ao menos um módulo.');
    post(`${bootstrap.endpoints.agentGrantBase}/${grant.id}/modules`, {modules: next});
  };

  return <section className="cadu-ds-account-section cadu-ds-agents" id="agentes">
    <header><div><h2>Agentes de IA</h2></div><small>{diagnosis?.connected ? 'Conectado' : 'Não conectado'}</small></header>
    <p className="cadu-ds-agents__lead">Conecte o Cadu ao seu aplicativo de IA com o login da sua conta. Não é preciso copiar chave nem segredo.</p>
    {error && <p className="cadu-ds-account-empty" role="alert">{error} <CaduButton type="button" size="xs" onClick={load}>Tentar de novo</CaduButton></p>}
    {state && !state.oauthReady && <p className="cadu-ds-account-empty" role="alert">O login por conta Cadu ainda não está habilitado neste ambiente. Os comandos abaixo só funcionam depois da habilitação.</p>}

    <div className="cadu-ds-agents__clients" role="tablist" aria-label="Aplicativo">
      {CLIENTS.map(item => <button key={item.id} type="button" role="tab" aria-selected={item.id === client} className={item.id === client ? 'is-active' : ''} onClick={() => { setClient(item.id); setCopied(false); }}>{item.title}</button>)}
    </div>
    <div className="cadu-ds-agents__panel">
      <small>{current.hint}</small>
      {current.unavailable ? <p className="cadu-ds-account-empty">Indisponível por enquanto.</p> : <>
        {command && <pre className="cadu-ds-agents__command"><code>{command}</code></pre>}
        <div className="cadu-ds-integration-actions">
          {command && <CaduButton type="button" variant="secondary" onClick={copy}>{copied ? 'Copiado' : 'Copiar'}</CaduButton>}
          {current.install && endpoint && <a className="is-primary" href={current.install(endpoint)}>Instalar com um clique</a>}
        </div>
      </>}
      <ol className="cadu-ds-agents__steps">{current.steps.map(step => <li key={step}>{step}</li>)}</ol>
    </div>

    <div className="cadu-ds-agents__accordions">
      <details className="cadu-ds-agents__fold" open>
        <summary><span>Estado da conexão</span><em>{doneSteps} de {totalSteps} concluídas</em></summary>
        <ol className="cadu-ds-agents__diagnosis">
          {(diagnosis?.steps || []).map(step => <li key={step.id} data-status={step.status}>
            <i aria-hidden="true">{(STATUS[step.status] || STATUS.pendente).mark}</i>
            <div><b>{step.label}</b><small>{step.detail}{step.action ? ` ${step.action}` : ''}</small></div>
            <em>{(STATUS[step.status] || STATUS.pendente).label}</em>
          </li>)}
        </ol>
        <div className="cadu-ds-integration-actions"><CaduButton type="button" variant="secondary" onClick={load}>Verificar de novo</CaduButton></div>
      </details>
      <details className="cadu-ds-agents__fold">
        <summary><span>Aplicativos conectados</span><em>{activeGrants.length}</em></summary>
        <div className="cadu-ds-integration-services">
          {activeGrants.map(grant => <article key={grant.id}>
            <i>{grant.clientName.slice(0, 2).toUpperCase()}</i>
            <div><b>{grant.clientName}</b><small>Autorizado em {dateTime(grant.consentedAt)} · último uso {dateTime(grant.lastUsedAt)}</small></div>
            <CaduButton type="button" variant="danger" onClick={() => post(`${bootstrap.endpoints.agentGrantBase}/${grant.id}/revoke`)}>Revogar</CaduButton>
          </article>)}
          {!activeGrants.length && <p className="cadu-ds-account-empty">Nenhum aplicativo conectado ainda.</p>}
        </div>
      </details>
      <details className="cadu-ds-agents__fold">
        <summary><span>Acessos e autorizações</span><em>Permissões por aplicativo</em></summary>
        <div className="cadu-ds-integration-services">
          {activeGrants.map(grant => <article key={grant.id}>
            <i>{grant.clientName.slice(0, 2).toUpperCase()}</i>
            <div><b>{grant.clientName}</b><small>Autorizado em {dateTime(grant.consentedAt)}</small>
              <span className="cadu-ds-agents__modules">{(state.modules || []).map(item => <label key={item.id}><input type="checkbox" checked={grant.modules.includes(item.id)} onChange={() => toggleModule(grant, item.id)}/> {item.label}</label>)}</span>
            </div>
          </article>)}
          {!activeGrants.length && <p className="cadu-ds-account-empty">As permissões aparecem aqui quando um aplicativo for autorizado.</p>}
        </div>
      </details>
    </div>
    {message && <p className="cadu-ds-account-message" role="status">{message}</p>}
    <p className="cadu-ds-agents__legacy"><a href={bootstrap.endpoints.agentLegacy}>Método de compatibilidade com chave (avançado)</a></p>
  </section>;
}
