"""Nome da ferramenta para clientes: "seu hub de mídia na Centralcomm".

Faz parte da entrega do serviço de mídia (plataforma facilitadora), não é um produto à parte.
"Área do Cliente" deixou de ser o nome. Todo texto novo usa estas constantes, direto no Python
ou pelos globais do Jinja (``HUB_*``), para trocar o nome em um lugar só no futuro.
"""

HUB_NOME = "seu hub de mídia na Centralcomm"   # frase corrida: "no seu hub de mídia na Centralcomm"
HUB_ROTULO = "Hub de mídia"                     # menu, título de página, etiquetas
HUB_APP = "Hub Centralcomm"                     # nome do app instalado e prévia de link
HUB_BOTAO = "Abrir meu hub de mídia"            # botão padrão de todo e-mail ao cliente
HUB_REMETENTE = "Centralcomm"                   # nome de quem envia

GLOBAIS_JINJA = {
    "HUB_NOME": HUB_NOME, "HUB_ROTULO": HUB_ROTULO, "HUB_APP": HUB_APP,
    "HUB_BOTAO": HUB_BOTAO, "HUB_REMETENTE": HUB_REMETENTE,
}
