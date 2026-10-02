import React, {useState} from 'react';
import {XClose} from '@untitledui/icons';
import {CaduModal} from '../../../cadu-design-system/components/CaduModal.jsx';
import {ReportsActionButton} from '../../ReportsActionButton.jsx';

const EXTRACTIONS = [
  ['Campanhas', 'Diário', 'Impressões, cliques, custo, conversões e valor por campanha e dia; status e tipo de campanha.', 'Resumo, comparação de períodos, ritmo do mês'],
  ['Configuração das campanhas', 'Foto a cada execução', 'Status, veiculação, estratégia de lances, orçamento diário (e se é compartilhado), CPA e ROAS desejados.', 'Metas, alertas de orçamento, histórico de mudanças'],
  ['Grupos de anúncios', 'Diário', 'Métricas por grupo, com status.', 'Detalhe, campanhas sem conversão'],
  ['Palavras-chave', 'Diário', 'Texto, correspondência, status, Índice de Qualidade e métricas.', 'Gasto sem conversão, IQ baixo, conflito com negativas'],
  ['Termos de pesquisa', 'Diário', 'O que as pessoas buscaram, se já foi adicionado ou excluído, e métricas.', 'Termos para negativar, termos que viram palavra-chave'],
  ['Palavras negativas', 'Foto a cada execução', 'Negativas de campanha, de grupo e de listas compartilhadas (com as campanhas que usam cada lista).', 'Cobertura de termos, conflitos, negativas removidas'],
  ['Dispositivos', 'Diário', 'Métricas por celular, computador, tablet e TV.', 'Custo por conversão por dispositivo'],
  ['Páginas de destino', 'Diário', 'URL final de cada anúncio com métricas.', 'Ligação com a Página 360 e com a Super Tag'],
];

const RULES = [
  ['Trava a conta', 'Script parado há mais de 48 h, teto de orçamento atingido, campanha gastando depois da data final, negativa bloqueando palavra-chave ativa.'],
  ['Metas e ritmo', 'Projeção do mês acima do teto (com o orçamento diário que fecha no teto), CPA ou ROAS fora da meta, meta de conversões em risco, orçamento sobrando com CPA dentro da meta.'],
  ['Desperdício', 'Termos com 10+ cliques e nenhuma conversão ainda não negativados, palavras-chave e campanhas com gasto e sem conversão, dispositivo com CPA 2× a conta.'],
  ['Oportunidade', 'Termos que convertem e ainda não são palavra-chave, campanha que converte limitada pelo orçamento, Índice de Qualidade baixo.'],
];

/** "Como funciona" for Google Ads operators: what the script reads, what Reports computes and how it fits the day to day. */
export function GoogleAdsHowItWorks() {
  const [open, setOpen] = useState(false);
  return <>
    <ReportsActionButton color="secondary" size="sm" onClick={() => setOpen(true)}>Como funciona</ReportsActionButton>
    {open && <CaduModal className="ga-how" closeOnBackdrop onClose={() => setOpen(false)}>{({titleId}) => <div className="ga-how__body">
      <header className="ga-how__head">
        <div><span className="ga-how__eyebrow">Google Ads no Cadu Reports</span>
          <h2 id={titleId}>Uma camada de inteligência sobre a sua operação</h2>
          <p>O script lê a conta todos os dias, guarda o histórico e transforma os números em próximos passos. Quem decide e executa é você; nada é alterado no Google Ads.</p></div>
        <button type="button" className="ga-how__close" aria-label="Fechar" onClick={() => setOpen(false)}><XClose size={20}/></button>
      </header>

      <ol className="ga-how__steps">
        <li><strong>1. Instale uma vez</strong><span>Gere o script aqui, cole em Ferramentas → Scripts (na conta ou na MCC), autorize e programe para rodar <b>diariamente</b>.</span></li>
        <li><strong>2. Coleta diária</strong><span>Cada execução relê os <b>últimos 14 dias</b> (conversões chegam atrasadas) e busca mais <b>45 dias do passado</b>, até completar <b>13 meses</b> de histórico. Nada é apagado: o histórico só cresce.</span></li>
        <li><strong>3. Análise</strong><span>O Reports compara com o período anterior ou com o mesmo período do ano passado, acompanha o ritmo do mês contra as metas e aplica as regras abaixo.</span></li>
        <li><strong>4. Execução</strong><span>Em Mídia → Google Ads você recebe os próximos passos em ordem e exporta negativas e palavras-chave em CSV para o <b>Google Ads Editor</b>.</span></li>
      </ol>

      <h3>O que extraímos</h3>
      <div className="ga-how__table" role="region" aria-label="Extrações do Google Ads" tabIndex={0}><table>
        <thead><tr><th>Conjunto</th><th>Frequência</th><th>O que vem</th><th>Para que usamos</th></tr></thead>
        <tbody>{EXTRACTIONS.map(([name, kind, what, use]) => <tr key={name}><td>{name}</td><td>{kind}</td><td>{what}</td><td>{use}</td></tr>)}</tbody>
      </table></div>

      <h3>Como decidimos os próximos passos</h3>
      <dl className="ga-how__rules">{RULES.map(([title, text]) => <div key={title}><dt>{title}</dt><dd>{text}</dd></div>)}</dl>
      <p className="ga-how__note">As metas (teto mensal ou total, período, objetivo, CPA, ROAS e conversões por mês) são definidas pela equipe em Mídia → Google Ads → Campanhas e ficam registradas no Reports, ao lado do CPA e do ROAS desejados que estiverem configurados no Google Ads.</p>

      <h3>Segurança e limites</h3>
      <ul className="ga-how__list">
        <li><b>Somente leitura.</b> O script não cria, pausa nem edita nada. Ele usa uma chave exclusiva deste cliente, que pode ser revogada aqui a qualquer momento.</li>
        <li><b>Sem dados pessoais.</b> São lidos apenas métricas e configurações da conta.</li>
        <li><b>Limites de uma execução.</b> 30 minutos por execução; conjuntos muito grandes são cortados pelos itens de maior custo e o corte aparece na saúde da coleta.</li>
        <li><b>Ainda não coletamos</b> conversões por ação, parcela de impressões, anúncios e recursos, geografia, horário, públicos, negativas da conta e de Performance Max.</li>
        <li><b>Meta Ads e outras plataformas</b> terão áreas próprias, alimentadas por prints e, no futuro, por extensão do Chrome.</li>
      </ul>
      <footer className="ga-how__foot"><ReportsActionButton color="primary" onClick={() => setOpen(false)}>Entendi</ReportsActionButton></footer>
    </div>}</CaduModal>}
  </>;
}
