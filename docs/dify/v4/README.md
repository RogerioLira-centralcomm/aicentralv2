# Cadu Conversations v4: implantação no Dify

O Cadu (backend) é o orquestrador:
- roteia o pedido;
- consulta o projeto, a web e as ferramentas;
- monta a evidência;
- escolhe um dos três apps Dify pelo `execution_mode` (`agent_v2/provider.py`).

Os apps Dify só geram a resposta. Por isso **não devem ter** nós de classificação, roteamento, base de conhecimento nem memória própria. Isso duplicaria o trabalho do backend e geraria respostas contraditórias.

## O que colar em cada app

O nó INICIAR de cada app declara 6 variáveis: `core`, `task`, `current_context`, `evidence`, `response_policy` e `output_contract`. A mensagem do usuário não é variável: chega como a mensagem da conversa. O backend envia outras entradas (veja abaixo); o Dify ignora as que o INICIAR não declara.

Cada app tem um JSON com o registro completo: configuração, entradas e o prompt em dois formatos de variável. **Do JSON, copie somente o valor de um campo e nada mais:**

| App | `execution_mode` | Arquivo |
|---|---|---|
| cadu-fast | `fast` | [cadu-fast.json](cadu-fast.json) |
| cadu-analyst | `analysis` | [cadu-analyst.json](cadu-analyst.json) |
| cadu-operator | `agentic` | [cadu-operator.json](cadu-operator.json) |

- **`system_prompt_chatflow`**: para Chatflow. Usa `{{#1789813203378.core#}}`, com o id do nó INICIAR do app de conversas. Se o INICIAR de outro app tiver id diferente, troque o número ou apague a variável e reinsira pelo seletor (digite `/`).
- **`system_prompt`**: para app de chat ou agente simples. Usa `{{core}}`.
- `settings`, `inputs`, `output_contract` e `runtime_contract` são o registro (modelo, memória, entradas). Não vão para o Dify. `settings` segue o formato do `cadu-conversations-orchestrator-v3.json`.
- Os `.md` são a fonte de edição. Depois de alterá-los, rode `python scripts/build_dify_prompts.py` para regenerar os JSON; um teste falha se ficarem fora de sincronia.

Se os três modos usam a mesma credencial de reserva (mesmo app), cole só o arquivo do `cadu-analyst`.

## Configuração recomendada por app

| | cadu-fast | cadu-analyst | cadu-operator |
|---|---|---|---|
| Modelo | GPT 5.4 | GPT 5.4 | GPT 5.4 |
| Esforço de raciocínio | baixo | médio | alto |
| Temperatura (se o Dify expuser) | 0,3 | 0,4 | 0,2 |
| Máx. tokens de saída | 3.000 | 10.000 | 14.000 |
| Memória da conversa | **desligada** | **desligada** | **desligada** |
| Base de conhecimento | nenhuma | nenhuma | nenhuma |

Valores sugeridos, a ajustar pelo que o Dify permitir para o GPT 5.4. Em modelos com raciocínio, o limite de tokens de saída inclui o raciocínio, por isso é maior que o tamanho da resposta visível. Se o modelo não aceitar temperatura, ignore essa linha.

**Por que a memória fica desligada.** O backend envia o histórico canônico em `evidence.conversation_history` e o estado em `evidence.conversation_state`. Com a memória do Dify ligada:
- o histórico chega duas vezes;
- o histórico diverge entre os três apps, porque cada um tem sua própria sessão.

## Entradas enviadas pelo backend e não usadas pelo prompt

`user_request`, `prompt_boundary`, `briefing_instruction`, `skill_context`, `projeto_context`, `files_context`, `user_memory_context`, `user_profile_context` e `is_first_message`. São aliases e campos legados. Depois que os três apps estiverem no v4, podem sair de `prompt_assembler.build_payload`. `briefing_instruction` já vem dentro de `core`.

## Verificação depois de publicar

Em uma conversa com projeto selecionado, envie estas três mensagens:

1. "Estruture um briefing para este projeto e destaque somente o que ainda precisa ser decidido." A resposta deve listar o que falta decidir, com base nos dados do projeto, sem dizer que não recebeu contexto.
2. "qual o público do projeto?" e, em seguida, "e o orçamento?". A segunda resposta deve continuar falando do mesmo projeto.
3. "compare Google Ads e Meta Ads para esse objetivo". A resposta deve vir completa, sem corte em poucas linhas.

E uma pergunta geral, como "qual a capital da França?". Deve responder direto, sem citar o projeto.

Em `/observabilidade`, o evento `run.admitted` de cada turno deve mostrar:
- `payload_diagnostics.retrieval.strategy`;
- `results_sent` maior que zero quando o projeto tiver conteúdo.
