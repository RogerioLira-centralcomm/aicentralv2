import React, {useState} from 'react';
import {Check} from '@untitledui/icons';
import {ReportsWizard} from './ReportsWizard.jsx';
import {KindIcon} from './linkKinds.jsx';
import {ReportsFieldInput} from './ReportsFieldInput.jsx';

const ART = '/static/images/reports/illustrations/';
const STEPS = [
  {key: 'tipo', label: 'Análise', art: 'link-tester/lt-wizard-1-pergunta.webp', focus: '30%', title: 'O que você quer descobrir?', text: 'Cada análise responde a uma pergunta diferente. Escolha a que combina com o momento da campanha.'},
  {key: 'link', label: 'Link', art: 'link-tester/lt-base.webp', focus: '50%', title: 'Qual link vamos testar?', text: 'Cole o link do anúncio, com os parâmetros UTM. Seguimos os redirecionamentos até a página final.'},
  {key: 'revisao', label: 'Revisão', art: 'link-tester/lt-hero-destination.webp', focus: '50%', title: 'Pronto para analisar', text: 'Confira o resumo. O resultado aparece na página e fica no histórico para associar à campanha.'},
];
const KINDS = [
  {id: 'destination', when: 'Antes de publicar o anúncio', question: 'O clique chega ao site?',
   detail: 'Simula o clique do anúncio e confere o que o visitante encontra.',
   checks: ['Redirecionamentos até a página final', 'Parâmetros UTM presentes e preenchidos', 'Certificado HTTPS válido', 'Resposta da página e tempo de carregamento'],
   gives: 'Nota de 0 a 100 e a lista do que corrigir antes de gastar mídia.'},
  {id: 'media', when: 'Antes de investir em mídia', question: 'A conversão será medida?',
   detail: 'Lê a página procurando o que permite atribuir resultado à campanha.',
   checks: ['GTM, GA4, Google Ads, Meta, TikTok e LinkedIn', 'Formulários, WhatsApp e telefone na página', 'Eventos de conversão disparados', 'Aviso de cookies e política de privacidade'],
   gives: 'Quais plataformas estão prontas, o que falta em cada uma e as lacunas de medição.'},
  {id: 'agentic', when: 'Para ser encontrado por IA', question: 'Agentes de IA conseguem ler o site?',
   detail: 'Audita o domínio inteiro, não a campanha. Qualquer página do site serve.',
   checks: ['robots.txt e bloqueio de ChatGPT, Claude, Perplexity e Google-Extended', 'llms.txt e llms-full.txt', 'sitemap.xml', 'Dados estruturados (schema.org)'],
   gives: 'Quais robôs de IA são bloqueados e quais arquivos faltam para o site ser citado.'},
];

/** Guided link test: pick the question, choose the link (client sites are suggested), review, run. */
export const LINK_KINDS = KINDS;
export function LinkTestWizard({sites = [], initial, onRun, onClose}) {
  const [form, setForm] = useState({url: initial?.url || '', mode: initial?.mode || 'destination'});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const valid = /^https?:\/\/\S+\.\S+/i.test(form.url.trim());
  const kind = KINDS.find(item => item.id === form.mode);
  const finish = async () => {
    setBusy(true); setError('');
    try {await onRun({...form, url: form.url.trim()}); onClose();} catch (failure) {setError(failure.message || 'Não foi possível analisar o link.'); setBusy(false);}
  };
  const renderStep = index => {
    if (index === 0) return <div className="rw__options" role="radiogroup" aria-label="Tipo de análise">
      {KINDS.map(item => <button key={item.id} type="button" role="radio" aria-checked={form.mode === item.id} className={`rw__option${form.mode === item.id ? ' is-chosen' : ''}`} onClick={() => setForm({...form, mode: item.id})}>
        <KindIcon kind={item.id} size={40}/>
        <span style={{flex: 1, textAlign: 'left', display: 'flex', flexDirection: 'column', gap: 2}}>
          <span style={{fontSize: 12, color: 'var(--color-text-tertiary)'}}>{item.when}</span>
          <strong style={{fontSize: 15}}>{item.question}</strong>
          <span style={{fontSize: 13, color: 'var(--color-text-secondary)', lineHeight: 1.45}}>{item.detail}</span>
          {form.mode === item.id && <>
            <ul style={{margin: '6px 0 0', paddingLeft: 18, listStyle: 'disc', fontSize: 13, lineHeight: 1.6, color: 'var(--color-text-secondary)'}}>{item.checks.map(check => <li key={check}>{check}</li>)}</ul>
            <span style={{fontSize: 13, marginTop: 6, color: 'var(--color-text-secondary)'}}><strong>Você recebe:</strong> {item.gives}</span>
          </>}
        </span>
        {form.mode === item.id && <Check size={18} aria-hidden="true"/>}
      </button>)}
    </div>;
    if (index === 1) return <div className="rw__fields">
      <ReportsFieldInput label="URL" required type="url" maxLength={2048} value={form.url} onChange={event => setForm({...form, url: event.target.value})} placeholder="https://exemplo.com/pagina?utm_source=…"
        hint={form.mode === 'agentic' ? 'A análise olha o domínio inteiro; qualquer página do site serve.' : 'Use o link exato que será colado no anúncio.'}/>
      {sites.length > 0 && <p className="text-sm font-medium text-secondary">Sites deste cliente</p>}
      {sites.length > 0 && <div className="rw__options" role="group" aria-label="Sites deste cliente">
        {sites.map(site => <button key={site.host} type="button" className={`rw__option${form.url === site.url ? ' is-chosen' : ''}`} onClick={() => setForm({...form, url: site.url})}><strong>{site.host}</strong></button>)}
      </div>}
    </div>;
    return <dl className="rw__summary">
      <div><dt>Análise</dt><dd>{kind?.question}</dd></div>
      <div><dt>Link</dt><dd className="break-all">{form.url.trim()}</dd></div>
    </dl>;
  };
  // The review step shows the scene of the analysis that was chosen.
  const steps = STEPS.map(step => step.key === 'revisao' ? {...step, art: `link-tester/lt-hero-${form.mode}.webp`} : step);
  return <ReportsWizard label="Teste de link" steps={steps} artBase={ART} renderStep={renderStep} canContinue={index => index === 1 ? valid : index === 2 ? valid : true}
    onFinish={finish} onClose={onClose} finishLabel="Analisar link" busy={busy} error={error}/>;
}
