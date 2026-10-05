# Vídeo: do briefing ao storyboard editável

Decisão de 2026-10-05: fluxo principal = **briefing → storyboard completo (rascunho editável) → só então gerar**.
Pedido: cartões por cena, reordenar/trocar cena, regerar uma cena, checagem de coerência.

## Por que hoje as cenas não se encaixam

1. **As cenas nascem de variações da cena anterior.** `createNextSceneWithTrocr`
   (`static/js/mc-cadu-video.js`) manda a cena em foco ao Trocr com uma nota genérica
   ("crie a próxima tomada… varie enquadramento e ambiente"). Não existe narrativa que diga o que a
   cena 2, 3 ou 4 precisa mostrar; cada imagem só se parece com a anterior.
2. **O roteiro vem depois das imagens.** `buildScript` (`/animate/script`) lê as imagens por OCR e
   descreve o que elas já mostram. O roteiro segue as imagens, quando deveria conduzi-las.
3. **O roteiro completo é texto livre.** `parseScript` (`static/js/cadu-video/utils.js`) divide por
   linha em branco e rótulos (`visual:`, `fala:`…) e liga cada bloco à cena **pela posição**. Editar o
   texto, reordenar ou remover cena desencaixa roteiro e cenas.
4. Só existe um cartão (da cena selecionada) e ele fica escondido atrás do texto livre.

## Desenho

O **beat é a fonte de verdade**; imagem e texto completo são derivados dele.

```
Briefing (texto + marca + duração + proporção)
   └─► Diretor (LLM de texto, barato)   → N beats: função, visual, movimento, fala, transição, duração
         └─► Cartões por cena (editáveis, sem custo de imagem)
               └─► Aprovar → gera só as imagens que faltam (uma por beat, mesma âncora de estilo)
                     └─► Checagem de coerência → gerar vídeo
```

## Fases

| Fase | Entrega | Custo de crédito | Aceite |
|---|---|---|---|
| 0 | Beats com ID estável como fonte de verdade; cartões por cena (todos visíveis); reordenar, trocar imagem e remover sem desencaixar; "Roteiro completo" vira só visão de leitura/exportação | nenhum | reordenar 5 cenas e editar 3 cartões mantém cada fala na cena certa; teste automatizado |
| 1 | Briefing → rascunho de storyboard (`agent/storyboard`): N beats sem imagem, editáveis | só texto | 3 briefings reais geram arco coerente (abertura → desenvolvimento → oferta → fechamento) |
| 2 | Imagem por beat a partir do `visual` do cartão, com a 1ª imagem aprovada como âncora de estilo; mostrar custo antes | imagem | cenas geradas respeitam marca, proporção e ordem |
| 3 | Regerar uma cena, ou só o texto de um beat, sem refazer o resto | imagem ou texto | trocar uma cena preserva as demais |
| 4 | Checagem antes de gerar: cena sem imagem, proporções diferentes, beat vazio, falas que não cabem na duração, estilos muito diferentes | nenhum (regras) | bloqueia ou avisa antes de gastar |

## Regras e riscos

- A qualidade do diretor (fase 1) e da âncora de estilo (fase 2) deve ser **medida no Lab antes de ir ao
  Studio**: A/B com os mesmos briefings. O Studio só muda com ganho medido.
- Imagem cobra crédito (saldo baixo): nada de gerar imagem sem aprovação explícita do rascunho.
- Compatibilidade: projetos salvos com `script.beats` ligados por posição precisam migrar para ID
  estável sem perder falas.
- "Criar próxima imagem" (Trocr) fica como atalho secundário, não como fluxo principal.

## Medição do diretor no Lab (2026-10-05)

`scripts/lab_storyboard.py`: 4 briefings (telecom 15 s, varejo 15 s, institucional 8 s, lançamento 30 s) em 3 modelos,
só texto, custo de centavos.

| Modelo | Tempo médio | Resultado |
|---|---|---|
| `openai/gpt-5-nano` | ~13 s | Descartado: devolveu o visual como objeto, escreveu "produo", fala curta que perdeu a oferta |
| `openai/gpt-5-mini` | ~9 s | **Escolhido.** Visual concreto e consistente com a marca em todas as cenas, oferta falada completa |
| `anthropic/claude-haiku-4.5` | ~15 s | Bom e comparável, ~5× mais caro; fica como reserva |

Todos abriram com hook, fecharam com end/offer, sem repetir cenas e dentro do orçamento de fala. Os "números
inventados" da 1ª rodada eram a proporção citada no visual (`1:1`, `16:9`); a checagem ignora proporções e o
prompt pede para não citá-las. Segunda rodada com o prompt final: `gpt-5-mini` sem nenhum aviso nos 4 briefings.

Pendente da fase 1: endpoint `agent/storyboard` com cobrança de texto, e rascunho editável no Vídeo (beats sem
imagem, ainda não ligados a cenas). Leitura humana das cenas deve confirmar o arco antes de ativar no Studio.
