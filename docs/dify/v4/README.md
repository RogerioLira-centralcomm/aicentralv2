# Cadu Conversations v4: implantação no Dify

O Cadu (backend) é o orquestrador:
- roteia o pedido;
- consulta o projeto, a web e as ferramentas;
- monta a evidência;
- escolhe um dos três apps Dify pelo `execution_mode` (`agent_v2/provider.py`).

Os apps Dify só geram a resposta. Por isso **não devem ter** nós de classificação, roteamento, base de conhecimento nem memória própria. Isso duplicaria o trabalho do backend e geraria respostas contraditórias.

| App | `execution_mode` | Credencial | Arquivo (cole o campo `system_prompt`) |
|---|---|---|---|
| cadu-fast | `fast` | `CADU_DIFY_FAST_URL` / `_KEY` | [cadu-fast.json](cadu-fast.json) |
| cadu-analyst | `analysis` | `CADU_DIFY_ANALYST_URL` / `_KEY` | [cadu-analyst.json](cadu-analyst.json) |
| cadu-operator | `agentic` | `CADU_DIFY_OPERATOR_URL` / `_KEY` | [cadu-operator.json](cadu-operator.json) |

Os JSON seguem o formato do `cadu-conversations-orchestrator-v3.json`: `system_prompt` já traz o prompt-base mais o bloco do app, e `settings` traz modelo, temperatura e memória desligada. Os `.md` são a fonte de edição; depois de alterá-los, rode `python scripts/build_dify_prompts.py` para regenerar os JSON (um teste falha se ficarem fora de sincronia).

Se as variáveis específicas não existirem, os três modos usam a mesma credencial de reserva, ou seja, o mesmo app e o mesmo prompt. Nesse caso cole só o prompt base e o bloco `cadu-analyst.md`.

## Configuração recomendada por app

| | cadu-fast | cadu-analyst | cadu-operator |
|---|---|---|---|
| Modelo | GPT 5.4 | GPT 5.4 | GPT 5.4 |
| Esforço de raciocínio | baixo | médio | alto |
| Temperatura (se o Dify expuser) | 0,3 | 0,4 | 0,2 |
| Máx. tokens de saída | 3.000 | 10.000 | 14.000 |

Valores sugeridos, a ajustar pelo que o Dify permitir para o GPT 5.4. Em modelos com raciocínio, o limite de tokens de saída inclui o raciocínio, por isso é maior que o tamanho da resposta visível. Se o modelo não aceitar temperatura, ignore essa linha.
| Memória da conversa | **desligada** | **desligada** | **desligada** |
| Base de conhecimento | nenhuma | nenhuma | nenhuma |

**Por que a memória fica desligada.** O backend envia o histórico canônico em `evidence.conversation_history` e o estado em `evidence.conversation_state`. Com a memória do Dify ligada:
- o histórico chega duas vezes;
- o histórico diverge entre os três apps, porque cada um tem sua própria sessão.

## Variáveis de entrada (início do app)

Variáveis que os prompts usam:
- `core`
- `task`
- `current_context`
- `user_request`
- `evidence`
- `response_policy`
- `output_contract`

Todas são texto (parágrafo). Configure `evidence` com limite de pelo menos 40.000 caracteres.

O backend ainda envia aliases legados: `skill_context`, `projeto_context`, `user_memory_context`, `user_profile_context`, `files_context`, `is_first_message`, `prompt_boundary` e `briefing_instruction`.
- O prompt v4 não usa nenhum deles. Remova-os do prompt publicado.
- `briefing_instruction` já vem dentro de `core`.
- Depois que os três apps estiverem no v4, os aliases podem sair de `prompt_assembler.build_payload`.

## Verificação depois de publicar

Em uma conversa com projeto selecionado, envie estas três mensagens:

1. "Estruture um briefing para este projeto e destaque somente o que ainda precisa ser decidido." A resposta deve listar o que falta decidir, com base nos dados do projeto, sem dizer que não recebeu contexto.
2. "qual o público do projeto?" e, em seguida, "e o orçamento?". A segunda resposta deve continuar falando do mesmo projeto.
3. "compare Google Ads e Meta Ads para esse objetivo". A resposta deve vir completa, sem corte em poucas linhas.

Em `/observabilidade`, o evento `run.admitted` de cada turno deve mostrar:
- `payload_diagnostics.retrieval.strategy`;
- `results_sent` maior que zero quando o projeto tiver conteúdo.
