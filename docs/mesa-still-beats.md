# Mesa — herança das 4 batidas a partir do still

Entrega pontual da Mesa de Conceito. Não cobre Trocr, Black/Fit sem still, seletor de CTAs, nem QA visual amplo.

## Auditoria do ciclo de vida

```
still (URL ou data URL)
→ fingerprint SHA-256[:24] no servidor
→ OCR (read_still_blocks / read_swap_reference) só se não houver leitura persistida do mesmo fingerprint
→ still_read (registro) + still_bind (vínculo) + copy_origin (autoridade final)
→ conceito / ledger / HTML
→ persistência em cx_concept_sessions.payload + snapshot format_lab
→ restore via get_session / list_sessions.active
```

Onde a leitura se perdia:

| ponto | o que acontecia |
|---|---|
| `mc-mesa.js` `knobs()` | não enviava leitura; cada POST relia o still |
| `_desk_session` | descartava `copy_bind` / `still_read` |
| `normalize_knobs` | aceitava `still_read` do cliente como se fosse OCR |
| `payload_locks` | com slug + `lock_copy`, a campanha vence o still |

Storage já existente: sessão de conceito (`upsert_concept_session` / brief `format_lab`). Sem Redis.

Três objetos:

1. **Leitura** (`still_read`): `read_id`, fingerprint, chips, `ocr_status`, revisão, modelo, `schema_version`.
2. **Vínculo** (`copy_bind` / `still_bind`): bloco → batida.
3. **Copy final** (`copy_origin`): origem efetiva por campo (`still`, `campaign`, `operator`, `none`, `generated`).

## Regras

- POST público descarta `still_read` / `ocr_status` / `copy_bind` do cliente.
- Mesmo fingerprint + leitura persistida: não executa OCR.
- `reread_still=true`: nova leitura, novo `read_id`, `revision+1`.
- Troca de still: invalida o vínculo ativo; guarda `still_read_prev`.
- Sessão antiga sem registro: não declara herança (`unknown` / sem `read_id`).
- `lock_copy` continua vencendo o still nesta entrega; a UI mostra campanha travada e o aviso de conflito.
- PNG/base64 não entram no registro de leitura (`asset_ref` vira `data:image/attached`).

Concorrência: dois POSTs iniciais do mesmo still ainda podem OCR em paralelo. Sem garantia exactly-once.

## Papéis A

hook ← headline · benefit ← support · proof ← price · cta.botão ← cta · cta.headline ← price.

## Fixture TIM Black (leitura capturada)

| batida | papel | texto final | origem do still | vínculo |
|---|---|---|---|---|
| scene_01 | hook | Acesse vantagens exclusivas e um superbônus de internet | headline | bound |
| scene_02 | benefit | até 110GB + bônus para redes sociais | support | bound |
| scene_03 | proof | R$ 169,99 | price | bound |
| scene_04 | cta | Conferir planos | cta | bound |
| scene_04 | headline | R$ 169,99 | price | bound |

Validação visual do TIM Black real permanece pendente.
