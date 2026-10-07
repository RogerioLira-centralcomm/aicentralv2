import React from 'react';
import {Badge} from '../cadu-design-system/untitled-kit/badges.tsx';

const Row = ({label, children}) => <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 py-2 text-sm"><dt className="text-tertiary">{label}</dt><dd className="min-w-0 text-right break-all text-primary">{children}</dd></div>;
const Yes = ({ok, yes = 'Sim', no = 'Não'}) => <Badge type="pill-color" size="sm" color={ok ? 'success' : 'warning'}>{ok ? yes : no}</Badge>;
const Block = ({title, hint, children}) => <section className="min-w-0"><h3 className="text-sm font-semibold text-primary">{title}</h3>{hint && <p className="mt-0.5 text-xs text-tertiary">{hint}</p>}<div className="mt-2">{children}</div></section>;

function Destination({evidence}) {
  const utm = Object.entries(evidence.utm || {});
  return <>
    <Block title="Caminho do clique" hint={`${evidence.redirects?.length || 0} etapa(s) · ${evidence.elapsed_ms ?? '–'} ms`}>
      <ol className="flex flex-col gap-1 text-xs">{(evidence.redirects || []).map((step, index) => <li key={index} className="flex gap-2"><Badge type="color" size="sm" color={step.status >= 400 ? 'error' : step.status >= 300 ? 'warning' : 'success'}>{step.status}</Badge><span className="font-mono break-all text-secondary">{step.url}</span></li>)}</ol>
    </Block>
    <Block title="Parâmetros UTM" hint="Sem eles, a mídia não é atribuída à campanha no relatório.">
      {utm.length ? <dl className="divide-y divide-secondary">{utm.map(([key, values]) => <Row key={key} label={key}>{values[0] || <span className="text-error-primary">vazio</span>}</Row>)}</dl> : <p className="text-sm text-tertiary">Nenhum parâmetro utm_ no link.</p>}
    </Block>
    <Block title="Página e segurança"><dl className="divide-y divide-secondary">
      <Row label="HTTP"><Yes ok={evidence.http_status < 400} yes={String(evidence.http_status)} no={String(evidence.http_status)}/></Row>
      <Row label="HTTPS"><Yes ok={evidence.ssl?.valid} yes="Válido" no="Não validado"/></Row>
      <Row label="Título">{evidence.title || '–'}</Row><Row label="Descrição">{evidence.description || '–'}</Row>
    </dl></Block>
  </>;
}

function Media({evidence}) {
  const conv = evidence.conversion || {};
  const supertag = evidence.supertag || {};
  return <>
    <div className="md:col-span-2"><Block title="Cadu Super Tag" hint="A tag do Reports que mede a jornada e as conversões do site.">
      <div className="flex flex-wrap items-center gap-2 text-sm text-secondary">
        <Badge type="pill-color" size="sm" color={supertag.detected ? (supertag.registered === false || supertag.host_matches === false ? 'warning' : 'success') : 'gray'}>{supertag.detected ? 'Instalada' : 'Não encontrada'}</Badge>
        {supertag.detected && <span>{supertag.via === 'gtm' ? 'Injetada pelo Google Tag Manager' : 'No código da página'}{supertag.site_label ? ` · site "${supertag.site_label}"` : ''}</span>}
        {!supertag.detected && supertag.registered && <span>Cadastrada para este domínio ({supertag.site_label}), mas ausente da página.</span>}
      </div>
    </Block></div>
    <Block title="Plataformas" hint="Presença das tags de cada plataforma de mídia.">
      <ul className="flex flex-col gap-2">{(evidence.platforms || []).map(item => <li key={item.name} className="text-sm"><div className="flex items-center justify-between"><span className="font-medium text-primary">{item.name}</span><Badge type="pill-color" size="sm" color={item.score >= 100 ? 'success' : item.score ? 'warning' : 'gray'}>{item.score}%</Badge></div>
        {item.missing?.length > 0 && <p className="text-xs text-tertiary">Falta: {item.missing.join(', ')}</p>}</li>)}</ul>
    </Block>
    <Block title="Tags detectadas"><div className="flex flex-wrap gap-1.5">{(evidence.tags || []).map(tag => <Badge key={tag.name} type="color" size="sm" color={tag.detected ? 'success' : 'gray'}>{tag.name}</Badge>)}</div></Block>
    <Block title="Conversões na página"><dl className="divide-y divide-secondary">
      <Row label="Formulários">{conv.forms || 0}</Row><Row label="WhatsApp"><Yes ok={conv.whatsapp}/></Row><Row label="Telefone"><Yes ok={conv.phone}/></Row>
      <Row label="Eventos">{evidence.events?.length ? evidence.events.join(', ') : 'nenhum encontrado'}</Row>
    </dl></Block>
    <Block title="Consentimento"><dl className="divide-y divide-secondary">
      <Row label="Aviso de cookies"><Yes ok={evidence.compliance?.consent_detected}/></Row><Row label="Política de privacidade"><Yes ok={evidence.compliance?.privacy_policy_detected}/></Row>
    </dl></Block>
  </>;
}

const SEVERITY = {critical: ['error', 'Crítico'], warning: ['warning', 'Atenção'], info: ['gray', 'Sugestão'], ok: ['success', 'Ok']};

function Agentic({evidence}) {
  const findings = evidence.findings || [];
  const problems = findings.filter(item => item.severity !== 'ok');
  const passed = findings.filter(item => item.severity === 'ok');
  return <>
    <div className="md:col-span-2"><Block title="Pontuação por área" hint={evidence.raw_score !== undefined && evidence.caps?.length ? `Soma das áreas: ${evidence.raw_score}. A nota final foi limitada pelos bloqueios abaixo.` : 'Quanto cada área contribui para a nota.'}>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">{(evidence.categories || []).map(item => <div key={item.name} className="rounded-lg bg-secondary_subtle p-3 ring-1 ring-secondary ring-inset">
        <p className="text-lg font-semibold text-primary tabular-nums">{item.score}<span className="text-xs font-normal text-tertiary">/{item.max}</span></p>
        <p className="text-xs font-medium text-secondary">{item.name}</p><p className="text-xs text-tertiary">{item.question}</p>
        <div className="mt-2 h-1.5 rounded-full bg-quaternary"><div className="h-1.5 rounded-full" style={{width: `${Math.round(item.score * 100 / item.max)}%`, background: '#7a5af8'}}/></div>
      </div>)}</div>
    </Block></div>
    {evidence.caps?.length > 0 && <div className="md:col-span-2"><Block title="O que limita a nota" hint="Estes problemas travam a nota, independentemente do resto.">
      <ul className="flex flex-col gap-1.5">{evidence.caps.map(cap => <li key={cap.reason} className="flex items-center gap-2 text-sm text-secondary"><Badge type="color" size="sm" color="error">máx. {cap.limit}</Badge>{cap.reason}</li>)}</ul>
    </Block></div>}
    <div className="md:col-span-2"><Block title={`O que corrigir (${problems.length})`} hint="Ordenado por gravidade.">
      {problems.length ? <ul className="flex flex-col divide-y divide-secondary">{problems.map((item, index) => <li key={index} className="flex gap-3 py-3">
        <Badge type="color" size="sm" color={SEVERITY[item.severity][0]}>{SEVERITY[item.severity][1]}</Badge>
        <div className="min-w-0"><p className="text-sm font-medium text-primary">{item.title} <span className="text-xs font-normal text-tertiary">· {item.category}</span></p><p className="text-sm text-secondary">{item.detail}</p>{item.fix && <p className="mt-1 text-sm text-brand-secondary">Como corrigir: {item.fix}</p>}</div>
      </li>)}</ul> : <p className="text-sm text-tertiary">Nenhum problema encontrado.</p>}
    </Block></div>
    <Block title="Robôs de IA" hint="Busca e usuário decidem se o site pode ser citado; treinamento é escolha da empresa."><div className="flex flex-wrap gap-1.5">{(evidence.bot_access || []).map(bot => <Badge key={bot.name} type="color" size="sm" color={bot.blocked ? (bot.purpose === 'training' ? 'gray' : 'error') : 'success'}>{bot.name} · {bot.blocked ? 'bloqueado' : 'liberado'}</Badge>)}</div></Block>
    <Block title="Arquivos do domínio" hint={evidence.domain}><dl className="divide-y divide-secondary">{Object.entries(evidence.resources || {}).map(([name, item]) => <Row key={name} label={name}><Yes ok={item.available} yes="Válido" no={item.status === 200 ? 'Resposta inválida' : item.status ? `HTTP ${item.status}` : 'Ausente'}/></Row>)}</dl></Block>
    {passed.length > 0 && <div className="md:col-span-2"><Block title={`O que já está certo (${passed.length})`}><div className="flex flex-wrap gap-1.5">{passed.map((item, index) => <Badge key={index} type="color" size="sm" color="success">{item.title}</Badge>)}</div></Block></div>}
  </>;
}


const WHERE = {code: 'no código', injected: 'injetada (GTM/JS)'};
const REVIEW_TONE = {critico: 'error', atencao: 'warning', sugestao: 'gray'};

/** What the page loads: platforms with their IDs, JavaScript by origin, events. The same payload the reviewer reads. */
function Inventory({inventory, findings}) {
  if (!inventory) return null;
  const scripts = inventory.scripts || {};
  const events = Object.entries(inventory.events || {});
  return <>
    <div className="md:col-span-2"><Block title="Plataformas e IDs" hint="Onde cada tag foi vista: no código entregue pelo servidor ou só depois do JavaScript/GTM rodar.">
      {inventory.platforms?.length ? <div className="overflow-x-auto"><table className="w-full text-sm"><tbody className="divide-y divide-secondary">{inventory.platforms.map(item => <tr key={item.name}>
        <td className="py-2 pr-3 font-medium text-primary">{item.name}</td>
        <td className="py-2 pr-3 font-mono text-xs break-all text-secondary">{item.ids?.join(', ') || '–'}</td>
        <td className="py-2 text-right whitespace-nowrap"><Badge type="color" size="sm" color={item.where === 'code' ? 'brand' : 'gray'}>{WHERE[item.where]}</Badge>{item.script_loads > 1 && <Badge className="ml-1" type="color" size="sm" color="warning">{item.script_loads}× carregada</Badge>}</td>
      </tr>)}</tbody></table></div> : <p className="text-sm text-tertiary">Nenhuma plataforma de mídia ou analytics encontrada.</p>}
    </Block></div>
    <Block title="JavaScript da página" hint={`${scripts.external || 0} externos (${scripts.third_party || 0} de terceiros, ${scripts.injected || 0} injetados) · ${scripts.inline_in_code || 0} inline (${scripts.inline_kb || 0} KB) · ${scripts.blocking_in_code || 0} bloqueantes`}>
      <ul className="flex flex-col gap-1 text-xs">{(scripts.by_host || []).slice(0, 10).map(host => <li key={host.host} className="flex justify-between gap-2"><span className="truncate font-mono text-secondary">{host.host}</span>
        <span className="shrink-0 text-tertiary">{host.scripts}{host.injected ? ` · ${host.injected} inj.` : ''} · {host.origin === 'first_party' ? 'próprio' : 'terceiro'}</span></li>)}</ul>
      {scripts.list?.length > 0 && <details className="mt-2 text-xs"><summary className="cursor-pointer text-tertiary">Ver os {scripts.list.length} scripts</summary>
        <ul className="mt-1 flex max-h-56 flex-col gap-0.5 overflow-auto font-mono text-secondary">{scripts.list.map(item => <li key={item.src} className="break-all">{item.loaded === 'injected' ? '↳ ' : ''}{item.src}</li>)}</ul></details>}
    </Block>
    <Block title="Eventos e consentimento" hint={inventory.consent?.tools?.length ? `Consentimento: ${inventory.consent.tools.join(', ')}${inventory.consent.consent_mode ? ' · Consent Mode ativo' : ''}` : 'Nenhuma ferramenta de consentimento detectada.'}>
      {events.length ? <dl className="divide-y divide-secondary">{events.map(([source, names]) => <Row key={source} label={source}>{names.join(', ')}</Row>)}</dl> : <p className="text-sm text-tertiary">Nenhum evento encontrado no código.</p>}
    </Block>
    {findings?.length > 0 && <div className="md:col-span-2"><Block title="Achados nas tags">
      <ul className="flex flex-col divide-y divide-secondary">{findings.map((item, index) => <li key={index} className="flex gap-3 py-2.5">
        <Badge type="color" size="sm" color={SEVERITY[item.severity][0]}>{SEVERITY[item.severity][1]}</Badge>
        <div className="min-w-0"><p className="text-sm font-medium text-primary">{item.title}</p><p className="text-sm text-secondary">{item.detail}</p>{item.fix && <p className="mt-0.5 text-sm text-brand-secondary">Como corrigir: {item.fix}</p>}</div>
      </li>)}</ul>
    </Block></div>}
  </>;
}

/** The AI reviewer's reading of the clean payload. */
export function ReviewPanel({review}) {
  if (!review) return null;
  return <section className="mt-4 rounded-lg bg-secondary_subtle p-4 ring-1 ring-secondary ring-inset" aria-label="Revisão do Cadu">
    <div className="flex flex-wrap items-center gap-2"><h3 className="text-sm font-semibold text-primary">Revisão do Cadu</h3>
      <Badge type="pill-color" size="sm" color={review.verdict === 'pronto' ? 'success' : review.verdict === 'bloqueado' ? 'error' : 'warning'}>{review.verdict || 'sem veredito'}</Badge></div>
    {review.summary && <p className="mt-1 text-sm text-secondary">{review.summary}</p>}
    {review.problems?.length > 0 && <ul className="mt-3 flex flex-col divide-y divide-secondary">{review.problems.map((item, index) => <li key={index} className="flex gap-3 py-2.5">
      <Badge type="color" size="sm" color={REVIEW_TONE[item.gravidade] || 'gray'}>{item.plataforma || item.gravidade}</Badge>
      <div className="min-w-0 text-sm"><p className="font-medium text-primary">{item.problema}</p>{item.evidencia && <p className="text-secondary">{item.evidencia}</p>}{item.correcao && <p className="mt-0.5 text-brand-secondary">Como corrigir: {item.correcao}</p>}</div>
    </li>)}</ul>}
    {review.check_in_gtm?.length > 0 && <div className="mt-3"><p className="text-xs font-semibold text-secondary">Verificar no GTM</p><ul className="mt-1 list-disc pl-5 text-sm text-secondary">{review.check_in_gtm.map(item => <li key={item}>{item}</li>)}</ul></div>}
    {review.questions?.length > 0 && <div className="mt-3"><p className="text-xs font-semibold text-secondary">Perguntar ao cliente</p><ul className="mt-1 list-disc pl-5 text-sm text-secondary">{review.questions.map(item => <li key={item}>{item}</li>)}</ul></div>}
  </section>;
}

/** Detailed evidence behind the score, one layout per analysis kind. */
export function ResultEvidence({result}) {
  const evidence = result?.evidence;
  const Body = {destination: Destination, media: Media, agentic: Agentic}[result?.kind];
  if (!evidence || !Body) return null;
  return <div className="mt-4 grid gap-6 border-t border-secondary pt-4 md:grid-cols-2">
    {evidence.capture_note && <p className="text-sm text-tertiary md:col-span-2">{evidence.capture_note}</p>}
    <Body evidence={evidence}/>
    <Inventory inventory={evidence.inventory} findings={evidence.tag_findings}/>
  </div>;
}
