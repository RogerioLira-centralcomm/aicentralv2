# Base Pública Cadu — plano separado de validação

## Objetivo

Criar uma base de evidências públicas brasileiras para planejamento de mídia,
isolada de organizações, marcas e projetos. Ela informa recomendações; nunca
se transforma automaticamente em fato privado de cliente.

## Fora do escopo do chat atual

- Nenhuma consulta web durante o envio de uma mensagem.
- Nenhuma fonte pública inserida no contexto de projeto sem revisão.
- Nenhum uso, armazenamento ou simulação de dados licenciados (IBOPE, Kantar,
  Comscore ou equivalentes) sem conector, contrato e escopo autorizados.

## Arquitetura de teste

```text
Fonte oficial / API pública
        │ conector agendado
        ▼
snapshot imutável + licença + data + validade
        │ normalização e chunking
        ▼
índice RAG público secundário
        │ consulta rápida e citável
        ▼
card de evidência no Cadu
```

O conector é o único componente que acessa a fonte. O chat consulta apenas o
índice secundário. A coleta deve ter cache por URL, hash de conteúdo, prazo de
validade e trilha de erro interna.

## Primeiro lote para prova de valor

1. Cetic.br — TIC Domicílios: acesso, uso, dispositivo, região e renda.
2. IBGE — PNAD TIC: acesso à internet, televisão e telefone móvel.
3. Anatel: conectividade e acessos agregados por território.
4. Fontes públicas de transparência criativa: leitura de presença e criativo,
   sem alegar segmentação, entrega ou audiência comercial.

Cada registro deve guardar URL, instituição, licença/termo de uso, data de
publicação, data de coleta, cobertura geográfica, população, método, período,
validade e nível de evidência.

## Consulta e qualidade

- Recuperação lexical inicialmente; embeddings só depois de medir ganho real.
- Resultado limitado a trechos com fonte, recorte e validade visíveis.
- Conflitos priorizam dado primário do projeto, depois fonte licenciada
  autorizada, fonte pública oficial, sinal de plataforma e inferência.
- Dados vencidos não entram na resposta como fatos atuais.
- Todo card público deve diferenciar `fato`, `evidência` e `premissa`.

## Critérios para integrar ao Cadu Conversas

- Pelo menos três fontes atualizadas e testadas em consultas reais.
- Citação e recorte corretos em 100% dos cards de evidência amostrados.
- Cache reduzindo chamadas externas repetidas.
- Custo, latência e falhas medidos fora da conversa principal.
- Revisão de licença, LGPD e escopo comercial aprovada.

Só então a Base Pública passa a alimentar cards de evidência e pesquisa do
Cadu. Até lá, o chat segue usando contexto privado, Base Cadu aprovada e
pesquisa explícita já existente.
