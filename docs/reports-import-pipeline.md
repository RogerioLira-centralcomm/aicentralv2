# Reports P2 · importação universal de mídia

## Decisão de produto

O Reports recebe dados **exportados** pelas plataformas, sem conectar diretamente às APIs de Meta Ads, Microsoft Ads, TikTok Ads ou outras redes. CSV/XLSX e prints chegam à mesma caixa de entrada do `client_id`. O Google Ads Script da V1 continua como opção própria de monitoramento; não determina o formato das outras fontes.

O usuário começa escolhendo somente o cliente e enviando arquivos. Plataforma, conta, campanha, período e métricas são extraídos dos dados. Marca, projeto e relatório podem ser associados depois. A origem bruta e cada decisão ficam disponíveis para auditoria.

## Fluxo de uma importação

| Etapa | Regra | Saída |
| --- | --- | --- |
| Receber | Aceitar arquivo com limite de tamanho e hash; registrar usuário, `client_id`, nome, MIME, data e lote. Mesmo conteúdo no mesmo cliente retorna o lote anterior. | Original preservado e status `received`. |
| Ler | CSV/XLSX usa parser de linhas, abas e cabeçalhos; print usa OCR ou leitor visual para localizar texto, IDs, datas e números. Manter linha/aba ou trecho de imagem como evidência. | Observações brutas, sem alterar campanhas. |
| Interpretar | Normalizar campos conhecidos, unidades, moeda, fuso, período e nível da métrica. TypeSafe pode julgar qual cabeçalho corresponde a um campo ou qual campanha de uma lista curta é mais provável. | Prévia estruturada com valor, evidência e incerteza. |
| Resolver identidade | Procurar conta por `(client_id, plataforma, external_account_id)` e campanha por `(conta, external_campaign_id)`. Um ID exato e sem conflito permite criar ou atualizar automaticamente. Sem ID suficiente, criar entidade provisória específica da fonte ou apresentar candidatas, sem fundir nomes parecidos automaticamente. | Conta/campanha confirmada ou provisória; conflitos visíveis. |
| Persistir | Guardar fatos imutáveis ligados ao lote e uma projeção atual por chave canônica. Reenvio idêntico é idempotente; novo arquivo para o mesmo período substitui a projeção após regra de precedência ou revisão. | Série incremental rastreável, sem somar snapshots duplicados. |
| Revisar | Mostrar prévia antes de consolidar métricas ambíguas. Usuário escolhe conta/campanha, confirma mapeamentos e resolve conflito de período, moeda ou unidade. | Decisão humana com autor, data e versão. |

## Identidade automática e limites

1. Nunca usar apenas o nome da campanha como chave global. Nomes podem se repetir entre contas, plataformas e períodos.
2. Preservar IDs externos como texto, inclusive zeros à esquerda e hífens; comparar no escopo da plataforma e da conta. Salvar nome atual e aliases observados em fontes anteriores.
3. Se o arquivo trouxer ID de campanha mas não ID de conta, só vincular automaticamente se houver uma única campanha compatível no mesmo cliente e plataforma, sem conflito de nome/conta. Caso contrário, deixar provisória.
4. Se não houver ID, criar uma identidade provisória com chave estável do lote e da linha/aba, para que reimportar o mesmo material não gere outra campanha. Sugerir vínculo com campanhas existentes para confirmação.
5. Print pode conter vários painéis, campanhas ou períodos. Separar blocos por escopo; não atribuir um total geral à campanha escolhida por proximidade visual.

## Fatos e incrementalidade

Cada observação precisa registrar `client_id`, plataforma declarada ou inferida, conta/campanha resolvida, nome e ID vistos na fonte, métrica original, métrica normalizada, valor bruto, valor normalizado, unidade, moeda, granularidade (`day`, `week`, `month`, `range`, `unknown`), início/fim, dimensões, identificador do lote e evidência. O esquema da P2 deve separar observação imutável de projeção consolidada.

- **Diário:** uma nova exportação da mesma campanha, métrica, data, dimensão e fonte revisa o valor projetado, mantendo a versão anterior no histórico.
- **Total de intervalo:** é um snapshot daquele intervalo. Dois prints com períodos sobrepostos não são somados. Um total acumulado só vira diferença incremental quando os limites e a definição forem comprovadamente comparáveis.
- **Fonte divergente:** dados do Google Ads Script, CSV e print podem representar definições diferentes de conversão ou janelas de atribuição. Exibir lado a lado até haver uma regra explícita de precedência.
- **Moeda e unidade:** valores de moedas distintas não são agregados; porcentagens e contagens não compartilham soma.

## Interface e serviços da P2

Adicionar **Importações** ao menu do Reports quando a caixa de entrada estiver funcional. A tela terá envio em lote, progresso de leitura, prévia por campanha/período, conflitos, decisões pendentes e histórico de arquivos. Contas e campanhas criadas automaticamente aparecem no inventário com selo de origem e estado; o usuário pode confirmar ou corrigir antes que fatos provisórios entrem nos totais publicados.

O backend deve oferecer upload, status de extração, prévia, confirmação e histórico por `client_id`, além de trabalhadores assíncronos para OCR/leitura visual e arquivos grandes. Reaproveitar a validação de imagens, o armazenamento de fontes, a revisão de métricas e o versionamento existentes onde couber. A extração visual atual exige um relatório antes do print; a nova caixa de entrada precisa aceitar o material **antes** de existir campanha ou relatório.

## Implementação inicial

- `add_reports_universal_imports_v1.sql` cria a caixa de entrada, linhas e observações imutáveis com escopo de organização e cliente. O deploy aplica a migração; não foi aplicada a banco remoto durante o desenvolvimento.
- `/connect/api/v1/reports/imports` recebe um CSV, XLSX ou print por vez. O mesmo hash no mesmo cliente retorna o lote anterior. A leitura tabular aceita até 5 MiB e 2.000 linhas; imagens seguem os limites e a limpeza de metadados da biblioteca de fontes.
- Cabeçalhos conhecidos, datas, números, moeda e IDs exatos geram conta e campanha no inventário e observações por métrica. Linhas com IDs ausentes, datas ambíguas, moeda conflitante ou campanha/data repetida ficam para revisão. Nomes já cadastrados não são substituídos pelo export.
- A interface **Importações** mostra lote e até 100 linhas de prévia. Prints ficam em `awaiting_extraction` e não alimentam métricas ainda. Observações tabulares ficam prontas para reconciliação; os totais do painel continuam independentes delas até existir uma regra de projeção para snapshots sobrepostos.

Próximos blocos: leitor visual com evidência por região, mapeamento assistido de cabeçalhos desconhecidos, revisão/confirmação de identidade e projeção versionada por campanha, dia e métrica. Um arquivo real de cada plataforma é necessário para ampliar os aliases sem adivinhar o formato do export.
