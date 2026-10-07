import React, {useState} from 'react';
import {Check, Copy01, Download01} from '@untitledui/icons';
import {Button} from '../cadu-design-system/untitled-kit/button.tsx';
import {Badge} from '../cadu-design-system/untitled-kit/badges.tsx';
import {Card} from './ReportsBlocks.jsx';

export const validGoogleAdsAccountId = value => /^(?:\d{10}|\d{3}-\d{3}-\d{4})$/.test(String(value || '').trim());
export const formatGoogleId = value => String(value).replace(/^(\d{3})(\d{3})(\d{4})$/, '$1-$2-$3');
export const digits = value => String(value || '').replace(/\D/g, '');
export const SCRIPTS = {
  read: {file: '/static/cadu_connect/google-ads-engine-v2.js', title: 'Leitura', schedule: 'diariamente', kind: 'google_ads_script'},
  actions: {file: '/static/cadu_connect/google-ads-actions.js', title: 'Acoes', schedule: 'de hora em hora', kind: 'google_ads_actions'},
};

/** Name used for the .txt file and suggested for the script in Google Ads: product, script, account and version. */
export function scriptName(kind, accountLabel, version) {
  return `Cadu_GoogleAds_${SCRIPTS[kind].title}_${accountLabel}_v${version}`;
}
export const versionOf = template => (template.match(/engineVersion:\s*'([^']+)'/) || [])[1] || '0';
export function downloadText(text, name) {
  const url = URL.createObjectURL(new Blob([text], {type: 'text/plain;charset=utf-8'}));
  const link = Object.assign(document.createElement('a'), {href: url, download: `${name}.txt`});
  document.body.append(link); link.click(); link.remove(); URL.revokeObjectURL(url);
}
export async function template(kind) {
  const response = await fetch(SCRIPTS[kind].file, {credentials: 'same-origin', cache: 'no-store'});
  if (!response.ok) throw new Error('Não foi possível carregar o script do Google Ads.');
  return response.text();
}

/** One generated script: suggested name, download as .txt and copy. */
export function ScriptCard({item}) {
  const [copied, setCopied] = useState('');
  const copy = async (value, what) => {try {await navigator.clipboard.writeText(value); setCopied(what);} catch {setCopied('');}};
  return <Card title={`Script de ${item.kind === 'read' ? 'Leitura' : 'Ações'} · v${item.version}`}
    badge={<Badge type="pill-color" size="sm" color="warning">Baixe ou copie agora</Badge>}
    description={item.kind === 'read'
      ? 'Lê métricas, termos e negativas e envia ao Reports. Nunca altera a conta. Agende diariamente.'
      : `Aplica as mudanças aprovadas no Reports (pausar, ativar, negativar, palavras-chave, lance e orçamento até ±${item.limits.max_budget_change_pct}%/±${item.limits.max_cpc_change_pct}%). Agende de hora em hora.`}
    actions={<div className="flex flex-wrap gap-2">
      <Button size="md" color="primary" iconLeading={Download01} onPress={() => downloadText(item.text, item.name)}>Baixar .txt</Button>
      <Button size="md" color="secondary" iconLeading={copied === 'code' ? Check : Copy01} onPress={() => copy(item.text, 'code')}>{copied === 'code' ? 'Copiado' : 'Copiar código'}</Button>
    </div>}>
    <div className="mb-3 flex flex-wrap items-center gap-2 rounded-lg bg-secondary_subtle px-3 py-2 text-sm ring-1 ring-secondary ring-inset">
      <span className="text-tertiary">Nome no Google Ads:</span>
      <code className="font-mono text-xs font-semibold text-primary">{item.name}</code>
      <Button size="sm" color="link-color" onPress={() => copy(item.name, 'name')}>{copied === 'name' ? 'Copiado' : 'Copiar nome'}</Button>
      <span className="ml-auto text-xs text-tertiary">Ferramentas › Scripts › + › cole o código › Programar: {SCRIPTS[item.kind].schedule}</span>
    </div>
    <pre aria-label={`Código do script de ${item.kind === 'read' ? 'Leitura' : 'Ações'}`} className="max-h-64 overflow-auto rounded-lg bg-secondary p-4 font-mono text-xs leading-5 whitespace-pre text-secondary ring-1 ring-secondary ring-inset">{item.text}</pre>
  </Card>;
}


/**
 * Creates one ingestion key per script (Leitura, and Ações when asked) and fills each script template with its key.
 * Returns [{kind, name, version, text, limits}]; the keys are shown only once, so the caller must present the texts at once.
 */
export async function generateGoogleScripts({save, withActions, label, managerExternalId, accountIds, limits}) {
  const kinds = withActions ? ['read', 'actions'] : ['read'];
  const templates = await Promise.all(kinds.map(template));
  const accountLabel = managerExternalId ? `MCC-${formatGoogleId(managerExternalId)}` : formatGoogleId(accountIds[0]);
  const today = new Date().toLocaleDateString('pt-BR');
  const generated = [];
  for (const [index, kind] of kinds.entries()) {
    const created = await save('/ingest-keys', {label: kind === 'read' ? label : `${label} · Ações`, source_kind: SCRIPTS[kind].kind,
      manager_account_id: managerExternalId, account_ids: accountIds, limits: kind === 'actions' ? limits : undefined}, false);
    const version = versionOf(templates[index]);
    const name = scriptName(kind, accountLabel, version);
    const accounts = created.allowed_account_ids.map(formatGoogleId);
    const title = `${name} · ${managerExternalId ? `MCC ${formatGoogleId(managerExternalId)} · contas ${accounts.join(', ')}` : `conta ${accounts.join(', ')}`} · gerado em ${today}`;
    let text = templates[index].replace('__CADU_INGEST_URL__', `${location.origin}/connect/api/gads`).replace('__CADU_API_KEY__', created.token)
      .replace('__CADU_ACCOUNT_IDS__', JSON.stringify(accounts));
    text = kind === 'actions'
      ? text.replace('__CADU_SCRIPT_TITLE__', title).replace('__CADU_MAX_BUDGET_PCT__', String(created.limits.max_budget_change_pct))
        .replace('__CADU_MAX_CPC_PCT__', String(created.limits.max_cpc_change_pct))
      : `// ${title}\n${text}`;
    generated.push({kind, name, version, text, limits: created.limits || {}, keyId: created.id});
  }
  return generated;
}
