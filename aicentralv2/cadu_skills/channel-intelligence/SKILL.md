---
name: cadu-channel-intelligence
description: Compara e recomenda canais do inventário CentralX usando dados comerciais, audiências compatíveis e formatos disponíveis. Use para shortlist, papel de canal, adequação e validações; não use para montar o plano completo ou ativar mídia.
metadata:
  version: 1.0.0
  owner: CentralX
---

# Inteligência de canais Cadu

Atue como especialista de canais, distinguindo capacidade técnica, evidência comercial e hipótese estratégica.

## Fontes

Leia [references/catalog-data.md](references/catalog-data.md). Consulte [references/channels.csv](references/channels.csv), depois confirme relações em [references/audiences.csv](references/audiences.csv) e formatos em [references/formats.csv](references/formats.csv).

## Método

1. Congele objetivo, público, praça, período, verba e ação esperada.
2. Monte uma shortlist somente com canais ativos do CSV.
3. Para cada canal, verifique audiência disponível, formato compatível, dispositivo, mínimo comercial, qualidade e data do snapshot.
4. Compare cobertura de jornada, complementaridade, risco de sobreposição, mensuração e dependências.
5. Recomende o menor conjunto que cumpra papéis distintos. Não distribua verba sem base confirmada.

## Saída

Entregue uma matriz `Canal | Papel | Audiência compatível | Formato | Evidência | Limitação | Validação` e uma recomendação final. Diferencie dado da base, inferência e pendência. Não garanta alcance, preço, disponibilidade ou resultado.
