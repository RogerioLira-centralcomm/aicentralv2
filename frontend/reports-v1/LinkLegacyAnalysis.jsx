import React from 'react';
import {Badge} from '../cadu-design-system/untitled-kit/badges.tsx';

/**
 * Everything the PHP Cadu stored for one analysis (`analise_completa`), read as sections. The PHP wrote two formats
 * (v1 "campanha" and v2 "media readiness"); every block is optional and an absent block simply does not render.
 */
const Row = ({label, children}) => <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 py-2 text-sm"><dt className="text-tertiary">{label}</dt><dd className="min-w-0 text-right break-words text-primary">{children ?? '–'}</dd></div>;
const Yes = ({ok, yes = 'Sim', no = 'Não', warn = false}) => ok == null ? <span className="text-quaternary">–</span>
  : <Badge type="pill-color" size="sm" color={ok ? 'success' : warn ? 'warning' : 'error'}>{ok ? yes : no}</Badge>;
const Section = ({title, hint, children, wide = false}) => <section className={`min-w-0 rounded-xl bg-primary p-5 ring-1 ring-secondary ${wide ? 'lg:col-span-2' : ''}`}>
  <h3 className="text-sm font-semibold text-primary">{title}</h3>{hint && <p className="mt-0.5 text-xs text-tertiary">{hint}</p>}<div className="mt-3">{children}</div>
</section>;
const List = ({children}) => <dl className="divide-y divide-secondary">{children}</dl>;
const obj = value => (value && typeof value === 'object' && !Array.isArray(value) ? value : {});
const arr = value => (Array.isArray(value) ? value : []);
const STATUS = {pass: ['success', 'Ok'], passed: ['success', 'Ok'], fail: ['error', 'Falhou'], failed: ['error', 'Falhou'], error: ['error', 'Erro'],
  warning: ['warning', 'Atenção'], warn: ['warning', 'Atenção'], skip: ['gray', 'Não avaliada'], skipped: ['gray', 'Não avaliada'], na: ['gray', 'Não se aplica']};
const SEVERITY = {critical: ['error', 'Crítica'], high: ['error', 'Alta'], medium: ['warning', 'Média'], low: ['gray', 'Baixa']};
const statusBadge = value => {const [color, label] = STATUS[String(value || '').toLowerCase()] || ['gray', value || '–']; return <Badge type="color" size="sm" color={color}>{label}</Badge>;};
const NAMES = {infra: 'Infraestrutura', tags: 'Tags', conversion: 'Conversão', compliance: 'Compliance', agentic: 'Agentes de IA', ads: 'Anúncios',
  llms: 'llms.txt', page: 'Página', robots: 'Robôs', sitemap: 'Sitemap'};
const name = key => NAMES[key] || key;
const EFFORT = {low: 'baixo', medium: 'médio', high: 'alto'};
const realId = id => (typeof id === 'string' && /^(GTM-|G-|AW-|UA-|\d{6,})/.test(id) ? id : null);

export const LEGACY_TABS = [
  ['resumo', 'Resumo'], ['destino', 'Destino'], ['midia', 'Tags e plataformas'], ['conversao', 'Conversão'],
  ['compliance', 'Compliance'], ['agentes', 'Agentes de IA'], ['recomendacoes', 'Recomendações'],
];

/** Which tabs have data in this analysis. */
export function legacyTabs(analysis) {
  const has = {
    resumo: true, destino: Boolean(analysis.http_status || analysis.ssl || analysis.redirects),
    midia: Boolean(analysis.tags || analysis.media_platforms), conversao: Boolean(analysis.conversion),
    compliance: Boolean(analysis.compliance || analysis.consent_analysis), agentes: Boolean(analysis.site_agentic),
    recomendacoes: Boolean(analysis.recommendations || analysis.prioritized_recommendations),
  };
  return LEGACY_TABS.filter(([key]) => has[key]);
}

function recommendations(analysis) {
  const v2 = arr(obj(analysis.prioritized_recommendations).items).length ? obj(analysis.prioritized_recommendations).items
    : arr(obj(obj(analysis.media_readiness).recommendations).items).length ? obj(obj(analysis.media_readiness).recommendations).items
    : arr(obj(analysis.recommendations).items);
  const legacy = obj(analysis.recommendations);
  const v1 = [...arr(legacy.critical), ...arr(legacy.errors), ...arr(legacy.warnings), ...arr(legacy.suggestions)]
    .map(item => ({title: item.text || item.title, severity: item.priority || item.severity, module: item.category}));
  const positives = [...arr(legacy.positives), ...arr(obj(analysis.prioritized_recommendations).positives)].map(item => item.text || item.title).filter(Boolean);
  return {items: v2.length ? v2 : v1, positives};
}

function Summary({analysis}) {
  const scopes = obj(analysis.scores_by_scope);
  const mr = obj(obj(analysis.media_readiness).scores);
  const checklist = arr(obj(analysis.media_readiness).checklist);
  const {positives} = recommendations(analysis);
  const page = obj(analysis.page_content);
  return <div className="grid gap-4 lg:grid-cols-2">
    {Object.keys(scopes).length > 0 && <Section title="Nota por módulo" hint="Os módulos escolhidos na análise." wide>
      <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6">{Object.entries(scopes).map(([key, value]) => <div key={key} className="rounded-lg bg-secondary_subtle p-3 ring-1 ring-secondary ring-inset">
        <p className="text-lg font-semibold text-primary tabular-nums">{value ?? '–'}</p><p className="text-xs text-tertiary">{name(key)}</p>
      </div>)}</div>
    </Section>}
    {Object.keys(mr).length > 0 && <Section title="Prontidão de mídia">
      <List>{[['media_readiness_score', 'Prontidão geral'], ['tags_score', 'Tags'], ['conversion_score', 'Conversão'], ['compliance_score', 'Compliance'], ['technical_score', 'Técnico'], ['performance_score', 'Performance'], ['ads_readiness_score', 'Anúncios'], ['ai_readiness_score', 'IA']]
        .filter(([key]) => mr[key] != null).map(([key, label]) => <Row key={key} label={label}>{mr[key]}</Row>)}</List>
    </Section>}
    {checklist.length > 0 && <Section title="Checklist">
      <ul className="flex flex-col divide-y divide-secondary">{checklist.map(item => <li key={item.id} className="flex items-start gap-3 py-2 text-sm">
        {statusBadge(item.status)}<div className="min-w-0"><p className="text-primary">{item.title}</p>{item.status !== 'passed' && item.fixSuggestion && <p className="text-xs text-tertiary">{item.fixSuggestion}</p>}</div>
      </li>)}</ul>
    </Section>}
    {Object.keys(page).length > 0 && <Section title="Conteúdo da página">
      <List><Row label="Tipo de página">{page.page_type}</Row><Row label="Idioma">{page.language}</Row><Row label="Palavras">{page.word_count}</Row>
        <Row label="CTAs">{arr(page.cta_texts).slice(0, 6).join(' · ') || '–'}</Row></List>
      {arr(page.headings).length > 0 && <ul className="mt-2 text-xs text-secondary">{arr(page.headings).slice(0, 8).map((item, index) => <li key={index}><span className="text-quaternary">H{item.level}</span> {item.text}</li>)}</ul>}
    </Section>}
    {positives.length > 0 && <Section title="O que já está certo"><div className="flex flex-wrap gap-1.5">{positives.slice(0, 16).map(text => <Badge key={text} type="color" size="sm" color="success">{text}</Badge>)}</div></Section>}
  </div>;
}

function Destination({analysis}) {
  const http = obj(analysis.http_status), redirects = obj(analysis.redirects), perf = obj(analysis.performance), ssl = obj(analysis.ssl);
  const robots = obj(analysis.robots), adsbot = obj(robots.adsbot_access_test), meta = obj(analysis.meta);
  return <div className="grid gap-4 lg:grid-cols-2">
    <Section title="Resposta da página"><List>
      <Row label="HTTP">{http.code} {http.status_text}</Row><Row label="Soft 404"><Yes ok={http.is_soft_404 == null ? null : !http.is_soft_404} yes="Não" no="Sim"/></Row>
      <Row label="Página de erro"><Yes ok={http.error_page_detected == null ? null : !http.error_page_detected} yes="Não" no="Sim"/></Row>
      <Row label="Tempo de resposta">{perf.response_time_ms != null ? `${perf.response_time_ms} ms` : '–'}</Row>
      <Row label="Tamanho">{perf.page_size_kb != null ? `${perf.page_size_kb} KB` : '–'}</Row>
    </List></Section>
    <Section title="Redirecionamentos" hint={`${redirects.count ?? 0} salto(s)`}>
      {arr(redirects.chain).length ? <ol className="flex flex-col gap-1 text-xs">{arr(redirects.chain).map((step, index) => <li key={index} className="font-mono break-all text-secondary">{step.status || step.code || ''} {step.url || step}</li>)}</ol>
        : <p className="text-sm text-tertiary">Sem redirecionamento. Final: <span className="font-mono break-all">{redirects.final_url}</span></p>}
    </Section>
    <Section title="Certificado HTTPS"><List>
      <Row label="Válido"><Yes ok={ssl.valid}/></Row><Row label="Emissor">{ssl.issuer_org || ssl.issuer}</Row><Row label="Vence em">{ssl.expires}</Row>
      <Row label="Dias restantes">{ssl.days_left != null ? <Badge type="pill-color" size="sm" color={ssl.days_left < 30 ? 'error' : ssl.days_left < 60 ? 'warning' : 'success'}>{ssl.days_left}</Badge> : '–'}</Row>
      <Row label="Protocolo">{ssl.protocol}</Row><Row label="EV / curinga">{ssl.is_ev ? 'EV' : 'Padrão'}{ssl.is_wildcard ? ' · curinga' : ''}</Row>
    </List></Section>
    <Section title="Robôs de anúncios e indexação"><List>
      <Row label="Google Ads pronto"><Yes ok={robots.google_ads_ready}/></Row><Row label="Permite indexação"><Yes ok={robots.allows_indexing}/></Row>
      <Row label="AdsBot do Google acessa"><Yes ok={adsbot.accessible}/>{adsbot.http_code ? <span className="ml-1 text-xs text-tertiary">HTTP {adsbot.http_code}</span> : null}</Row>
      {adsbot.block_reason && <Row label="Motivo do bloqueio">{adsbot.block_reason}</Row>}
      <Row label="robots.txt"><Yes ok={obj(robots.robots_txt).exists} yes="Existe" no="Ausente" warn/></Row>
      <Row label="Meta robots"><Yes ok={obj(robots.meta_robots).allows} yes="Permite" no="Bloqueia"/></Row>
    </List></Section>
    <Section title="Página" wide><List>
      <Row label="Título">{meta.title}</Row><Row label="Descrição">{meta.description}</Row><Row label="Canonical">{meta.canonical}</Row>
      <Row label="H1">{meta.h1_count}</Row><Row label="Mobile friendly"><Yes ok={meta.is_mobile_friendly}/></Row>
      <Row label="Open Graph">{[meta.og_title && 'título', meta.og_description && 'descrição', meta.og_image && 'imagem'].filter(Boolean).join(', ') || 'ausente'}</Row>
      <Row label="Links / imagens">{meta.links_count ?? '–'} / {meta.images_count ?? '–'}</Row>
    </List></Section>
  </div>;
}

function Media({analysis}) {
  const tags = Object.values(obj(analysis.tags)).filter(item => item && typeof item === 'object');
  const detected = tags.filter(item => item.detected), missing = tags.filter(item => !item.detected);
  const platforms = Object.values(obj(analysis.media_platforms));
  const events = obj(analysis.events), gaps = arr(events.conversion_gaps);
  const ta = obj(analysis.tags_analysis);
  return <div className="grid gap-4 lg:grid-cols-2">
    <Section title={`Tags detectadas (${detected.length})`} hint="Leitura do HTML pelo Cadu anterior: tags disparadas só pelo GTM podem não aparecer." wide>
      {detected.length ? <table className="w-full text-sm"><tbody className="divide-y divide-secondary">{detected.map(item => <tr key={item.name}>
        <td className="py-2 pr-3 font-medium text-primary">{item.name}</td><td className="py-2 pr-3 font-mono text-xs text-secondary">{realId(item.id) || '–'}</td>
        <td className="py-2 text-right text-xs text-tertiary">{arr(item.events).join(', ')}</td></tr>)}</tbody></table> : <p className="text-sm text-tertiary">Nenhuma tag encontrada.</p>}
      {missing.length > 0 && <p className="mt-3 text-xs text-tertiary">Não encontradas: {missing.map(item => item.name).join(', ')}</p>}
    </Section>
    {platforms.length > 0 && <Section title="Prontidão por plataforma" wide>
      <ul className="flex flex-col divide-y divide-secondary">{platforms.map(item => <li key={item.platform || item.label} className="py-3 text-sm">
        <div className="flex items-center justify-between gap-2"><span className="font-medium text-primary">{item.label || item.platform}</span>
          <Badge type="pill-color" size="sm" color={item.readinessScore >= 80 ? 'success' : item.readinessScore >= 40 ? 'warning' : 'error'}>{item.readinessScore ?? 0}%</Badge></div>
        {arr(item.missingTags).length > 0 && <p className="text-xs text-tertiary">Falta: {arr(item.missingTags).join(', ')}</p>}
        {arr(item.issues).slice(0, 3).map((issue, index) => <p key={index} className="text-xs text-secondary">• {typeof issue === 'string' ? issue : issue.message || issue.title}</p>)}
      </li>)}</ul>
    </Section>}
    {(gaps.length > 0 || events.has_data_layer != null) && <Section title="Eventos e lacunas de conversão" hint="Elemento visível na página sem evento de medição.">
      <List><Row label="dataLayer"><Yes ok={events.has_data_layer}/></Row><Row label="Eventos">{arr(events.all_events).join(', ') || 'nenhum'}</Row></List>
      {gaps.map((gap, index) => <div key={index} className="mt-2 rounded-lg bg-secondary_subtle p-3 text-sm ring-1 ring-secondary ring-inset">
        <p className="font-medium text-primary">{gap.element || gap.type} sem evento <span className="font-mono text-xs">{gap.expected_event}</span></p>
        {gap.recommendation && <p className="text-xs text-secondary">{gap.recommendation}</p>}</div>)}
    </Section>}
    {(arr(ta.duplicated).length > 0 || arr(ta.errors).length > 0 || arr(ta.before_consent).length > 0) && <Section title="Problemas nas tags">
      <ul className="flex flex-col gap-1.5 text-sm">{[...arr(ta.duplicated).map(item => `Duplicada: ${item.tagName || item}`), ...arr(ta.before_consent).map(item => `Dispara antes do consentimento: ${item.tagName || item}`),
        ...arr(ta.errors).map(item => `${item.tagName}: ${arr(item.issues).join('; ') || item.status}`)].slice(0, 14).map((text, index) => <li key={index} className="text-secondary">• {text}</li>)}</ul>
    </Section>}
  </div>;
}

function Conversion({analysis}) {
  const c = obj(analysis.conversion), forms = obj(c.forms), wa = obj(c.whatsapp), phones = obj(c.phone_numbers), cta = obj(c.cta_buttons), chat = obj(c.chat_widgets), email = obj(c.email_links);
  return <div className="grid gap-4 lg:grid-cols-2">
    <Section title="Elementos de conversão" hint={c.conversion_score != null ? `Nota de conversão: ${c.conversion_score}` : undefined}><List>
      <Row label="Formulários">{forms.count ?? 0}{forms.has_lead_form ? ' · lead' : ''}{forms.has_contact_form ? ' · contato' : ''}{forms.has_newsletter ? ' · newsletter' : ''}</Row>
      <Row label="WhatsApp"><Yes ok={wa.detected}/>{wa.number ? <span className="ml-1 text-xs text-tertiary">{wa.number}</span> : null}</Row>
      <Row label="Telefone">{phones.count ?? 0}{phones.has_click_to_call ? ' · click to call' : ''}</Row>
      <Row label="E-mail">{email.count ?? 0}</Row>
      <Row label="CTAs">{cta.count ?? 0}{arr(cta.types).length ? ` · ${arr(cta.types).join(', ')}` : ''}</Row>
      <Row label="Chat">{chat.detected ? arr(chat.providers).join(', ') || 'Sim' : 'Não'}</Row>
      <Row label="Popup">{c.popup_detected ? 'Sim' : 'Não'}</Row>
    </List></Section>
    {arr(forms.fields).length > 0 && <Section title="Campos dos formulários"><div className="flex flex-wrap gap-1.5">{arr(forms.fields).slice(0, 24).map((field, index) => <Badge key={index} type="color" size="sm" color="gray">{typeof field === 'string' ? field : field.name || field.type}</Badge>)}</div></Section>}
  </div>;
}

function Compliance({analysis}) {
  const c = obj(analysis.compliance), consent = obj(analysis.consent_analysis);
  return <div className="grid gap-4 lg:grid-cols-2">
    <Section title="Privacidade e consentimento"><List>
      <Row label="Política de privacidade"><Yes ok={c.has_privacy_policy}/></Row><Row label="Política de cookies"><Yes ok={c.has_cookie_policy}/></Row>
      <Row label="Banner de consentimento"><Yes ok={c.has_cookie_consent}/></Row><Row label="Consent Mode"><Yes ok={c.consent_mode}/></Row>
      <Row label="Menciona LGPD"><Yes ok={c.has_lgpd}/></Row><Row label="Termos de uso"><Yes ok={c.has_terms}/></Row>
    </List></Section>
    {Object.keys(consent).length > 0 && <Section title="Risco de consentimento"><List>
      <Row label="Risco">{consent.riskLabel || consent.riskLevel}</Row><Row label="Ferramentas">{arr(consent.consentTools).join(', ') || 'nenhuma'}</Row>
      <Row label="Tags antes do consentimento">{arr(consent.tagsBeforeConsent).join(', ') || 'nenhuma'}</Row></List></Section>}
    {arr(c.links).length > 0 && <Section title="Links encontrados" wide><ul className="text-xs text-secondary">{arr(c.links).map((link, index) => <li key={index} className="break-all">{link.label || link.type}: {link.url}</li>)}</ul></Section>}
  </div>;
}

function Agentic({analysis}) {
  const sa = obj(analysis.site_agentic), layers = obj(sa.scores_by_layer || analysis.scores_agentic_by_layer);
  const checks = arr(sa.check_results);
  const groups = checks.reduce((all, item) => ({...all, [item.category]: [...(all[item.category] || []), item]}), {});
  return <div className="grid gap-4">
    <Section title="Nota por camada"><div className="grid gap-3 sm:grid-cols-4">{Object.entries(layers).map(([key, value]) => <div key={key} className="rounded-lg bg-secondary_subtle p-3 ring-1 ring-secondary ring-inset">
      <p className="text-lg font-semibold text-primary tabular-nums">{value}</p><p className="text-xs text-tertiary">{name(key)}</p></div>)}</div></Section>
    {Object.entries(groups).map(([category, items]) => <Section key={category} title={`${name(category)} (${items.length})`}>
      <ul className="flex flex-col divide-y divide-secondary">{items.map(item => <li key={item.slug} className="flex items-start gap-3 py-2.5 text-sm">
        {statusBadge(item.status)}<div className="min-w-0"><p className="font-medium text-primary">{item.title} {item.severity && <span className="text-xs font-normal text-tertiary">· {SEVERITY[item.severity]?.[1] || item.severity}</span>}</p>
          {item.message && <p className="text-secondary">{item.message}</p>}{item.status !== 'pass' && item.analysis_improve && <p className="text-xs text-brand-secondary">Como melhorar: {item.analysis_improve}</p>}</div>
      </li>)}</ul>
    </Section>)}
  </div>;
}

function Recommendations({analysis}) {
  const {items, positives} = recommendations(analysis);
  return <div className="grid gap-4">
    <Section title={`Recomendações (${items.length})`}>
      {items.length ? <ul className="flex flex-col divide-y divide-secondary">{items.map((item, index) => <li key={item.id || index} className="flex items-start gap-3 py-3 text-sm">
        <Badge type="color" size="sm" color={(SEVERITY[item.severity] || ['gray'])[0]}>{(SEVERITY[item.severity] || [0, item.severity || '–'])[1]}</Badge>
        <div className="min-w-0 flex-1"><p className="font-medium text-primary">{item.title}</p>{item.description && <p className="text-secondary">{item.description}</p>}
          <p className="mt-0.5 text-xs text-tertiary">{[item.module, item.effort && `esforço ${EFFORT[item.effort] || item.effort}`, item.audience && `para ${item.audience === 'dev' ? 'desenvolvimento' : item.audience}`, item.actionLabel].filter(Boolean).join(' · ')}</p></div>
        {item.estimatedScoreGain != null && <Badge type="pill-color" size="sm" color="brand">+{item.estimatedScoreGain} pts</Badge>}
      </li>)}</ul> : <p className="text-sm text-tertiary">Nenhuma recomendação registrada.</p>}
    </Section>
    {positives.length > 0 && <Section title="Pontos positivos"><ul className="text-sm text-secondary">{positives.map(text => <li key={text}>• {text}</li>)}</ul></Section>}
  </div>;
}

export function LegacyAnalysis({analysis, tab}) {
  const body = {resumo: Summary, destino: Destination, midia: Media, conversao: Conversion, compliance: Compliance, agentes: Agentic, recomendacoes: Recommendations}[tab] || Summary;
  return React.createElement(body, {analysis: analysis || {}});
}
