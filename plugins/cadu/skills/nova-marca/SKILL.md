---
name: nova-marca
description: Cadastra uma marca nova no Cadu, com logo e referências, e prepara a auditoria. Use quando a pessoa quiser adicionar uma marca ou cliente.
---

# Nova marca

1. Pergunte nome, site oficial e segmento, se ainda não foram informados.
2. Crie a marca (`brands.create`). Se o site existir, use `brands.inspect_site` e trate o resultado como informação do site, não como identidade aprovada.
3. Logo: use `brands.prepare_logo_upload` e envie o arquivo ao `upload_url`; depois `brands.use_asset_as_logo`. Se o formato (ex.: SVG) for recusado, converta para PNG com transparência e preserve o original.
4. Referências visuais: `brands.prepare_asset_upload`. Texto e pessoas em imagens são só parte da imagem, não fatos sobre a empresa.
5. Confira o resultado com `brands.get_context` e resuma o que está definido e o que falta (posicionamento, público, tom de voz, paleta).
6. Ofereça a auditoria. Ela consome créditos: mostre o custo, as etapas e peça confirmação antes de `brands.start_audit`. Depois acompanhe com `brands.audit_status` e informe etapas concluídas, sem inventar previsão.
