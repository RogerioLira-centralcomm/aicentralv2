# planner_consistency_v1

Compare One Page e Plano Completo. Não reescreva fatos.

Campos imutáveis: cliente, campanha, objetivo, tese, público, verba, período, praça, canais, places, interativos, mix, mensagem, benefícios, outputs, parâmetros de estimativa.

Conflito crítico (tese, verba, canal novo, estimativa inventada): reporte.
Aprofundamento compatível: permitido.
Novo fato sem fonte: conflito; remova do documento final.
Devolva JSON: {"consistent": true, "conflicts": [], "warnings": []}
