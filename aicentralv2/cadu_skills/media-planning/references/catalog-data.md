# Catálogos CentralX

Os CSVs são snapshots gerados da base do Cadu por `aicentralv2/cadu_skills/scripts/export_official_catalogs.py`.

- `channels.csv`: um canal ativo por linha, com oferta, segmentações e audiências relacionadas.
- `audiences.csv`: uma audiência ativa por linha, com taxonomia, plataforma, qualidade, validade, canais disponíveis e medições.
- `formats.csv`: um formato por canal ou formato canônico, com dimensões, dispositivos, uso indicado e restrições.

Filtre primeiro por campos curtos (`slug`, nome, categoria, plataforma, mercado, papel e canal) e só depois leia JSONs extensos. Campos JSON preservam listas e estruturas; não os apresente crus ao usuário.

`snapshot_at` indica a data da extração. Alcance, viewability, disponibilidade e medição exigem leitura de qualidade/origem/validade e confirmação comercial quando aplicável. Preço de custo e preço de venda de audiência não fazem parte dos pacotes. Não exponha credenciais, notas privadas ou dados pessoais.
