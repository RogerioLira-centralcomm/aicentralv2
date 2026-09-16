# Arraial de Belô — roteiro A/B e teste do editor

## Entrega
A: original-a.png. B: variant-b.png. Ambos 640×640.
B muda apenas a etiqueta “É de graça!”: fundo amarelo e texto roxo.
Pessoas, marcas e demais informações fora da máscara têm pixels idênticos ao original.
Uso como exercício com criativo histórico: as datas da peça são julho/agosto de 2026. Não publicar como evento futuro sem atualizar e verificar a programação.

## Hipótese e desenho
Hipótese: a etiqueta aumenta a percepção da gratuidade e o interesse pelo evento.
Variável: tratamento visual da gratuidade. Manter público, posicionamento, texto do anúncio, destino, orçamento e período iguais. Distribuir A/B aleatoriamente em partes iguais, sem sobreposição quando a plataforma permitir.
Antes da mídia, apresentar uma versão por pessoa durante cinco segundos. Perguntar: qual evento, onde, quando e é gratuito? Registrar acertos, tempo e confusões. Não mostrar B depois de A à mesma pessoa como comparação de lembrança.
Em mídia, métrica principal sugerida: visitas à página de programação por impressão. Acompanhar CTR de link e custo por visita como secundárias; validar instrumentação antes do início.
Definir duração e amostra antes de rodar, com taxa histórica e menor melhoria relevante. Não declarar vencedor com poucos cliques nem parar no primeiro resultado favorável. Se a amostra não permitir conclusão, registrar inconclusivo.
Nenhum teste com participantes nem campanha paga foi executado nesta tarefa.

## Roteiro de usabilidade no Trocr
1. Abrir campanha de teste, importar A e salvar. Recarregar: peça e base devem permanecer.
2. Conferir textos no original. OCR local leu “ABRITAL”, “Be 6 2025” e “1° e 2.a9°” incorretamente apesar de confiança 100%. Não aceitar automaticamente.
3. Selecionar a etiqueta por retângulo ou laço; revisar cabelo e rosto vizinhos. Alternar adicionar/subtrair; desfazer e refazer um traço.
4. Experimentar ponto na roupa ou fundo: conferir porcentagem e aviso de seleção ampla. Reduzir tolerância quando alcançar outros elementos. A segmentação local retornou uma única instância, não seis artistas separados.
5. Recriar somente a etiqueta: “Fundo amarelo, texto roxo É de graça!, preservar todo o restante”. Revisar máscara antes da geração.
6. Comparar A/B em tamanho real e miniatura. Conferir datas, nomes e rodapé. Exportar B e recarregar histórico.
7. Testar separadamente falha de rede, clique duplo e mudança de base. Esperado: pedido preservado na falha, sem duplicação e sem máscara aplicada à base errada.
8. Registrar tempo até seleção correta, desfazimentos, pedidos de ajuda e sucesso sem orientação. Essas sessões humanas ainda precisam ser realizadas.

## Evidência executada
OCR e máscara Apple Vision locais; geração real via image_gen; composição e recuperação do job pelo backend local. Zero pixels alterados fora da máscara. Backend de produção, navegador autenticado e usuários reais não foram validados neste ensaio.
