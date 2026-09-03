"""Dados fictícios em memória para o protótipo /crm-v3."""

import copy
import uuid
from datetime import date

from .crm_v3_helpers import pluralizar_contatos

CLASSIFICACOES_CLIENTE = ("Prospecção", "Ativo", "Geladeira")
COTACAO_STATUS = {
    "rascunho": "Rascunho",
    "enviada": "Enviada",
    "aprovada": "Aprovada",
    "rejeitada": "Rejeitada",
    "expirada": "Expirada",
    "em-acompanhamento": "Em Acompanhamento",
}
COTACAO_STATUS_ALIASES = {
    **{label.casefold(): slug for slug, label in COTACAO_STATUS.items()},
    **{slug: slug for slug in COTACAO_STATUS},
    "negociacao": "em-acompanhamento",
    "em negociação": "em-acompanhamento",
    "perdida": "rejeitada",
}

def _end(cep="", uf="", cidade="", bairro="", logradouro="", numero="", complemento=""):
    return {
        "cep": cep,
        "uf": uf,
        "cidade": cidade,
        "bairro": bairro,
        "logradouro": logradouro,
        "numero": numero,
        "complemento": complemento,
    }


_CLIENTE_REALISMO = {
    "auto-shopping": {
        "cnpj": "05.419.347/0001-47",
        "pessoa": "J",
        "razao_social": "Associação dos Lojistas do Portal Auto Shopping",
        "nome_fantasia": "Portal Auto Shopping",
        "inscricao_estadual": "062.417.881.0018",
        "inscricao_municipal": "0093184",
        "classificacao_cliente": "Ativo",
        "tipo": "Privado",
        "cidade": "Contagem",
        "uf": "MG",
        "segmento": "Automotivo",
        "fonte": "Indicação",
        "data_cadastro": "2023-02-14",
        "endereco": _end("32040-190", "MG", "Contagem", "Cidade Industrial", "Av. Portal do Auto Shopping", "1000", "Piso L1"),
        "is_agencia": False,
        "agencia_id": "fazcom",
        "bv_percentual": 12.0,
        "margem_cc": 8.5,
        "opera_midia": True,
        "demanda_dados": True,
        "demanda_programatica_canais": False,
        "observacoes_comerciais_adicionais": "Cliente atendido pela Fazcom. Foco em campanhas sazonais (Auto Show).",
    },
    "build-agencia": {
        "cnpj": "21.845.372/0001-60",
        "pessoa": "J",
        "razao_social": "Build Comunicação e Marketing Ltda.",
        "nome_fantasia": "Build Agência",
        "inscricao_estadual": "isento",
        "inscricao_municipal": "3.827.641-6",
        "classificacao_cliente": "Prospecção",
        "tipo": "Privado",
        "cidade": "São Paulo",
        "uf": "SP",
        "segmento": "Publicidade e Propaganda",
        "fonte": "Evento",
        "data_cadastro": "2024-01-22",
        "endereco": _end("01452-002", "SP", "São Paulo", "Jardins", "Rua Bandeira Paulista", "702", "Conjunto 92"),
        "is_agencia": True,
        "bv_percentual": 15.0,
        "margem_cc": 10.0,
        "opera_midia": True,
        "demanda_dados": True,
        "demanda_programatica_canais": True,
        "observacoes_comerciais_adicionais": "Agência com foco em varejo e mídia programática. Atende Grupo ABC.",
        "clientes_finais_ids": ["grupo-abc"],
    },
    "clx": {
        "cnpj": "36.124.908/0001-15",
        "pessoa": "J",
        "razao_social": "CLX Comunicação Integrada Ltda.",
        "nome_fantasia": "CLX",
        "inscricao_estadual": "isento",
        "inscricao_municipal": "0.442.618-8",
        "classificacao_cliente": "Ativo",
        "tipo": "Privado",
        "cidade": "Rio de Janeiro",
        "uf": "RJ",
        "segmento": "Publicidade e Propaganda",
        "fonte": "Prospecção ativa",
        "data_cadastro": "2022-11-08",
        "endereco": _end("22440-032", "RJ", "Rio de Janeiro", "Leblon", "Av. Ataulfo de Paiva", "1235", "9º andar"),
        "is_agencia": True,
        "bv_percentual": 14.0,
        "margem_cc": 9.0,
        "opera_midia": True,
        "demanda_dados": True,
        "demanda_programatica_canais": True,
        "observacoes_comerciais_adicionais": "Agência full service. Atende Link Care.",
        "clientes_finais_ids": ["link-care"],
    },
    "copasa-mg": {
        "cnpj": "17.281.106/0001-03",
        "pessoa": "J",
        "razao_social": "Companhia de Saneamento de Minas Gerais",
        "nome_fantasia": "COPASA MG",
        "inscricao_estadual": "062.417.881.0002",
        "inscricao_municipal": "0044501",
        "classificacao_cliente": "Ativo",
        "tipo": "Público",
        "cidade": "Belo Horizonte",
        "uf": "MG",
        "segmento": "Saneamento",
        "fonte": "Licitação",
        "data_cadastro": "2021-06-17",
        "endereco": _end("30190-131", "MG", "Belo Horizonte", "Santo Agostinho", "Rua Mar de Espanha", "525", "Bloco B"),
        "is_agencia": False,
        "bv_percentual": 10.0,
        "margem_cc": 6.0,
        "opera_midia": False,
        "demanda_dados": True,
        "demanda_programatica_canais": False,
        "observacoes_comerciais_adicionais": "Cliente público. Contratação por licitação. Verba concentrada em campanhas institucionais.",
    },
    "crp-04": {
        "cnpj": "16.718.255/0001-37",
        "pessoa": "J",
        "razao_social": "Conselho Regional de Psicologia da 4ª Região",
        "nome_fantasia": "CRP 04",
        "inscricao_estadual": "isento",
        "inscricao_municipal": "0011239",
        "classificacao_cliente": "Geladeira",
        "tipo": "Público",
        "cidade": "Belo Horizonte",
        "uf": "MG",
        "segmento": "Conselho profissional",
        "fonte": "Licitação",
        "data_cadastro": "2020-09-03",
        "endereco": _end("30130-004", "MG", "Belo Horizonte", "Centro", "Rua Timbiras", "1532", "Sala 301"),
        "is_agencia": False,
        "bv_percentual": 0.0,
        "margem_cc": 5.0,
        "opera_midia": False,
        "demanda_dados": False,
        "demanda_programatica_canais": False,
        "observacoes_comerciais_adicionais": "Cliente em pausa; retomar próximo à próxima licitação (ago/26).",
    },
    "fazcom": {
        "cnpj": "08.702.516/0001-42",
        "pessoa": "J",
        "razao_social": "Fazcom Comunicação Ltda.",
        "nome_fantasia": "Fazcom",
        "inscricao_estadual": "062.417.881.0100",
        "inscricao_municipal": "0125718",
        "classificacao_cliente": "Ativo",
        "tipo": "Privado",
        "cidade": "Belo Horizonte",
        "uf": "MG",
        "segmento": "Publicidade e Propaganda",
        "fonte": "Indicação",
        "data_cadastro": "2022-04-12",
        "endereco": _end("30140-071", "MG", "Belo Horizonte", "Funcionários", "Rua Sergipe", "1400", "Andar 6"),
        "is_agencia": True,
        "bv_percentual": 13.5,
        "margem_cc": 9.5,
        "opera_midia": True,
        "demanda_dados": True,
        "demanda_programatica_canais": True,
        "observacoes_comerciais_adicionais": "Agência com longa relação. Atende Portal Auto Shopping e MG Minas.",
        "clientes_finais_ids": ["auto-shopping", "mg-minas"],
    },
    "full-solucoes": {
        "cnpj": "42.507.193/0001-08",
        "pessoa": "J",
        "razao_social": "Full Soluções em Tecnologia Ltda.",
        "nome_fantasia": "Full Soluções",
        "inscricao_estadual": "062.117.554.0011",
        "inscricao_municipal": "0064732",
        "classificacao_cliente": "Prospecção",
        "tipo": "Privado",
        "cidade": "Nova Lima",
        "uf": "MG",
        "segmento": "Tecnologia",
        "fonte": "Site",
        "data_cadastro": "2024-03-19",
        "endereco": _end("34006-070", "MG", "Nova Lima", "Vale do Sereno", "Alameda das Latânias", "480", "Sala 1104"),
        "is_agencia": False,
        "bv_percentual": 8.0,
        "margem_cc": 7.0,
        "opera_midia": False,
        "demanda_dados": True,
        "demanda_programatica_canais": True,
        "observacoes_comerciais_adicionais": "Prospecção com potencial de conta digital. Precisa apresentar case da concorrência.",
    },
    "grupo-abc": {
        "cnpj": "29.630.481/0001-74",
        "pessoa": "J",
        "razao_social": "Grupo ABC Participações S.A.",
        "nome_fantasia": "Grupo ABC",
        "inscricao_estadual": "isento",
        "inscricao_municipal": "0298117",
        "classificacao_cliente": "Ativo",
        "tipo": "Privado",
        "cidade": "Curitiba",
        "uf": "PR",
        "segmento": "Varejo",
        "fonte": "Carteira comercial",
        "data_cadastro": "2021-10-25",
        "endereco": _end("80230-020", "PR", "Curitiba", "Batel", "Av. do Batel", "1230", "Torre B, 12º andar"),
        "is_agencia": False,
        "agencia_id": "build-agencia",
        "bv_percentual": 12.0,
        "margem_cc": 8.0,
        "opera_midia": True,
        "demanda_dados": True,
        "demanda_programatica_canais": True,
        "observacoes_comerciais_adicionais": "Cliente atendido pela Build. Campanhas sazonais forte no varejo (Q4).",
    },
    "link-care": {
        "cnpj": "45.918.206/0001-31",
        "pessoa": "J",
        "razao_social": "Link Care Serviços de Saúde Ltda.",
        "nome_fantasia": "Link Care",
        "inscricao_estadual": "662.417.881.9032",
        "inscricao_municipal": "0037210",
        "classificacao_cliente": "Geladeira",
        "tipo": "Privado",
        "cidade": "Campinas",
        "uf": "SP",
        "segmento": "Saúde",
        "fonte": "Inbound",
        "data_cadastro": "2023-07-06",
        "endereco": _end("13073-100", "SP", "Campinas", "Cambuí", "Rua Coronel Quirino", "560", "Sala 82"),
        "is_agencia": False,
        "agencia_id": "clx",
        "bv_percentual": 10.0,
        "margem_cc": 7.5,
        "opera_midia": False,
        "demanda_dados": False,
        "demanda_programatica_canais": False,
        "observacoes_comerciais_adicionais": "Cliente atendido pela CLX. Fluxo estagnado; agendar reunião de retomada.",
    },
    "mg-minas": {
        "cnpj": "33.741.925/0001-56",
        "pessoa": "J",
        "razao_social": "MG Minas Comércio e Serviços Ltda.",
        "nome_fantasia": "MG Minas",
        "inscricao_estadual": "062.417.881.7712",
        "inscricao_municipal": "0208611",
        "classificacao_cliente": "Geladeira",
        "tipo": "Privado",
        "cidade": "Uberlândia",
        "uf": "MG",
        "segmento": "Serviços",
        "fonte": "Prospecção ativa",
        "data_cadastro": "2022-08-30",
        "endereco": _end("38400-186", "MG", "Uberlândia", "Centro", "Av. Rondon Pacheco", "3350", "Sala 401"),
        "is_agencia": False,
        "agencia_id": "fazcom",
        "bv_percentual": 9.0,
        "margem_cc": 6.5,
        "opera_midia": False,
        "demanda_dados": True,
        "demanda_programatica_canais": False,
        "observacoes_comerciais_adicionais": "Cliente atendido pela Fazcom. Baixa recorrência; reforçar plano trimestral.",
    },
    "reciclo": {
        "cnpj": "14.286.509/0001-22",
        "pessoa": "J",
        "razao_social": "Reciclo Comunicação Socioambiental Ltda.",
        "nome_fantasia": "Reciclo",
        "inscricao_estadual": "isento",
        "inscricao_municipal": "0155442",
        "classificacao_cliente": "Prospecção",
        "tipo": "Privado",
        "cidade": "Belo Horizonte",
        "uf": "MG",
        "segmento": "Sustentabilidade",
        "fonte": "Evento",
        "data_cadastro": "2024-02-05",
        "endereco": _end("30160-042", "MG", "Belo Horizonte", "Savassi", "Rua Antônio de Albuquerque", "534", "Loja 3"),
        "is_agencia": False,
        "bv_percentual": 7.5,
        "margem_cc": 5.5,
        "opera_midia": False,
        "demanda_dados": True,
        "demanda_programatica_canais": False,
        "observacoes_comerciais_adicionais": "Prospecção com ticket menor mas alto NPS potencial. Focar em ESG.",
    },
}

_CONTATO_REALISMO = {
    "c1": ("Marketing", "Ativo"),
    "c2": ("Mídia", "Ativo"),
    "c3": ("Planejamento", "Ativo"),
    "c4": ("Atendimento", "Ativo"),
    "c5": ("Diretoria", "Ativo"),
    "c6": ("Comercial", "Ativo"),
    "c7": ("Atendimento", "Ativo"),
    "c8": ("Mídia", "Ativo"),
    "c9": ("Financeiro", "Inativo"),
    "c10": ("Marketing", "Ativo"),
}

_INITIAL_CLIENTES = [
    {
        "id": "auto-shopping",
        "nome": "ASSOCIAÇÃO DOS LOJISTAS DO PORTAL AUTO SHOPPING",
        "tipo_label": "Cliente final",
        "perfil": "direto",
        "status": "hoje",
        "badge": "Hoje",
        "badge_type": "success",
        "avatar": "A",
        "seguindo": True,
        "prioridade": "Alta",
        "categoria": "Privado",
        "responsavel": "Luisa Santana",
    },
    {
        "id": "build-agencia",
        "nome": "BUILD AGÊNCIA",
        "tipo_label": "Agência",
        "perfil": "agencia",
        "status": "atrasado",
        "badge": "Atrasado 2 dias",
        "badge_type": "warning",
        "avatar": "B",
        "seguindo": False,
        "prioridade": "Média",
        "categoria": "Privado",
        "responsavel": "Luisa Santana",
    },
    {
        "id": "clx",
        "nome": "CLX",
        "tipo_label": "Agência",
        "perfil": "agencia",
        "status": "amanha",
        "badge": "Amanhã",
        "badge_type": "info",
        "avatar": "C",
        "seguindo": True,
        "prioridade": "Média",
        "categoria": "Privado",
        "responsavel": "João Paulo",
    },
    {
        "id": "copasa-mg",
        "nome": "COPASA MG",
        "tipo_label": "Cliente final",
        "perfil": "direto",
        "status": "atrasado",
        "badge": "Atrasado 5 dias",
        "badge_type": "warning",
        "avatar": "C",
        "seguindo": False,
        "prioridade": "Baixa",
        "categoria": "Governo",
        "responsavel": "Luisa Santana",
    },
    {
        "id": "crp-04",
        "nome": "CRP 04",
        "tipo_label": "Cliente final",
        "perfil": "direto",
        "status": "sem-atividade",
        "badge": "Sem atividade 18 dias",
        "badge_type": "danger",
        "avatar": "C",
        "seguindo": False,
        "prioridade": "Baixa",
        "categoria": "Privado",
        "responsavel": "João Paulo",
    },
    {
        "id": "fazcom",
        "nome": "FAZCOM",
        "tipo_label": "Agência",
        "perfil": "agencia",
        "status": "hoje",
        "badge": "Hoje",
        "badge_type": "success",
        "avatar": "F",
        "seguindo": True,
        "prioridade": "Alta",
        "categoria": "Privado",
        "responsavel": "Luisa Santana",
    },
    {
        "id": "full-solucoes",
        "nome": "FULL SOLUÇÕES",
        "tipo_label": "Cliente final",
        "perfil": "direto",
        "status": "atrasado",
        "badge": "Em 3 dias",
        "badge_type": "warning",
        "avatar": "F",
        "seguindo": False,
        "prioridade": "Média",
        "categoria": "Privado",
        "responsavel": "João Paulo",
    },
    {
        "id": "grupo-abc",
        "nome": "GRUPO ABC",
        "tipo_label": "Cliente final",
        "perfil": "direto",
        "status": "hoje",
        "badge": "Hoje",
        "badge_type": "muted",
        "avatar": "G",
        "seguindo": True,
        "prioridade": "Média",
        "categoria": "Privado",
        "responsavel": "Luisa Santana",
    },
    {
        "id": "link-care",
        "nome": "LINK CARE",
        "tipo_label": "Cliente final",
        "perfil": "direto",
        "status": "sem-atividade",
        "badge": "Sem atividade 21 dias",
        "badge_type": "danger",
        "avatar": "L",
        "seguindo": False,
        "prioridade": "Baixa",
        "categoria": "Privado",
        "responsavel": "João Paulo",
    },
    {
        "id": "mg-minas",
        "nome": "MG MINAS",
        "tipo_label": "Cliente final",
        "perfil": "direto",
        "status": "sem-atividade",
        "badge": "Sem contato",
        "badge_type": "muted",
        "avatar": "M",
        "seguindo": False,
        "prioridade": "Baixa",
        "categoria": "Privado",
        "responsavel": "Luisa Santana",
    },
    {
        "id": "reciclo",
        "nome": "RECICLO",
        "tipo_label": "Agência",
        "perfil": "agencia",
        "status": "sem-atividade",
        "badge": "Sem contato",
        "badge_type": "muted",
        "avatar": "R",
        "seguindo": False,
        "prioridade": "Baixa",
        "categoria": "Privado",
        "responsavel": "João Paulo",
    },
]

_INITIAL_CONTATOS = {
    "auto-shopping": [
        {
            "id": "c1",
            "nome": "marketing",
            "cargo": "Analista de Mídias",
            "email": "marketing@portalautoshopping.com.br",
            "telefone": "(31) 99399-9939",
            "telefone_secundario": "",
            "principal": True,
            "avatar": "M",
            "conversas": 2,
        }
    ],
    "build-agencia": [
        {
            "id": "c2",
            "nome": "Ana Paula Ribeiro",
            "cargo": "Diretora de Mídia",
            "email": "ana.ribeiro@buildagencia.com.br",
            "telefone": "(11) 98765-4321",
            "telefone_secundario": "(11) 3456-7890",
            "principal": True,
            "avatar": "AR",
            "conversas": 5,
        },
        {
            "id": "c3",
            "nome": "Carlos Mendes",
            "cargo": "Planejamento",
            "email": "carlos@buildagencia.com.br",
            "telefone": "(11) 91234-5678",
            "telefone_secundario": "",
            "principal": False,
            "avatar": "CM",
            "conversas": 1,
        },
        {
            "id": "c4",
            "nome": "Fernanda Souza",
            "cargo": "Atendimento",
            "email": "fernanda@buildagencia.com.br",
            "telefone": "(11) 99876-1234",
            "telefone_secundario": "",
            "principal": False,
            "avatar": "FS",
            "conversas": 0,
        },
    ],
    "clx": [
        {
            "id": "c5",
            "nome": "Roberto Lima",
            "cargo": "CEO",
            "email": "roberto@clx.com.br",
            "telefone": "(21) 97654-3210",
            "telefone_secundario": "",
            "principal": True,
            "avatar": "RL",
            "conversas": 3,
        },
        {
            "id": "c6",
            "nome": "Juliana Costa",
            "cargo": "Comercial",
            "email": "juliana@clx.com.br",
            "telefone": "(21) 91234-0000",
            "telefone_secundario": "",
            "principal": False,
            "avatar": "JC",
            "conversas": 0,
        },
    ],
    "fazcom": [
        {
            "id": "c7",
            "nome": "Pedro Alves",
            "cargo": "Gerente de Contas",
            "email": "pedro@fazcom.com.br",
            "telefone": "(31) 98888-7777",
            "telefone_secundario": "(31) 3333-4444",
            "principal": True,
            "avatar": "PA",
            "conversas": 4,
        },
        {
            "id": "c8",
            "nome": "Marina Dias",
            "cargo": "Mídia",
            "email": "marina@fazcom.com.br",
            "telefone": "(31) 97777-6666",
            "telefone_secundario": "",
            "principal": False,
            "avatar": "MD",
            "conversas": 1,
        },
        {
            "id": "c9",
            "nome": "Lucas Ferreira",
            "cargo": "Financeiro",
            "email": "lucas@fazcom.com.br",
            "telefone": "(31) 96666-5555",
            "telefone_secundario": "",
            "principal": False,
            "avatar": "LF",
            "conversas": 0,
        },
    ],
    "grupo-abc": [
        {
            "id": "c10",
            "nome": "Helena Martins",
            "cargo": "Marketing",
            "email": "helena@grupoabc.com.br",
            "telefone": "(41) 99999-1111",
            "telefone_secundario": "",
            "principal": True,
            "avatar": "HM",
            "conversas": 1,
        }
    ],
}


_INITIAL_ATIVIDADES = {
    "auto-shopping": [
        {
            "id": "a1",
            "titulo": "Ligar para responsável financeiro",
            "descricao": "Alinhar pendências e próximos passos",
            "data_label": "Hoje — 26 de maio",
            "data": "2024-05-26",
            "hora": "10:30",
            "prioridade": "Alta",
            "status": "pendente",
            "tipo": "ligacao",
            "responsavel": "LS",
        },
        {
            "id": "a2",
            "titulo": "Enviar proposta comercial",
            "descricao": "Proposta de campanha Q3",
            "data_label": "Hoje — 26 de maio",
            "data": "2024-05-26",
            "hora": "14:00",
            "prioridade": "Média",
            "status": "pendente",
            "tipo": "doc",
            "responsavel": "JP",
        },
        {
            "id": "a3",
            "titulo": "Reunião de alinhamento",
            "descricao": "Apresentar estratégias e cronograma",
            "data_label": "Hoje — 26 de maio",
            "data": "2024-05-26",
            "hora": "16:00",
            "prioridade": "Alta",
            "status": "pendente",
            "tipo": "reuniao",
            "responsavel": "LS",
        },
        {
            "id": "a4",
            "titulo": "Acompanhar aprovação de mídia",
            "descricao": "Verificar status com aprovação",
            "data_label": "Amanhã — 27 de maio",
            "data": "2024-05-27",
            "hora": "10:30",
            "prioridade": "Média",
            "status": "pendente",
            "tipo": "doc",
            "responsavel": "CM",
        },
    ],
}

_INITIAL_OBJETIVOS = {
    "auto-shopping": [
        {"id": "o1", "texto": "Voltar a falar para 2º semestre", "prazo": "21/06", "concluido": False},
        {"id": "o2", "texto": "Reunião com Serasa", "prazo": "21/06", "concluido": False},
        {"id": "o3", "texto": "Acesso ao Cadu", "prazo": "21/06", "concluido": False},
    ],
}

_INITIAL_COTACOES = {
    "auto-shopping": [
        {
            "id": "cot1",
            "numero_cotacao": "COT-202405-A3F9",
            "nome_campanha": "Campanha institucional Q3",
            "titulo": "Proposta comercial Q3",
            "valor_total": 45000.00,
            "valor": "R$ 45.000,00",
            "status": "em-acompanhamento",
            "status_canonico": "Em Acompanhamento",
            "status_label": "Em Acompanhamento",
            "periodo_inicio": "2024-07-01",
            "periodo_fim": "2024-09-30",
            "data": "15/05/2024",
        },
        {
            "id": "cot2",
            "numero_cotacao": "COT-202405-7BC2",
            "nome_campanha": "Presença de marca 2024",
            "titulo": "Campanha institucional",
            "valor_total": 28500.00,
            "valor": "R$ 28.500,00",
            "status": "enviada",
            "status_canonico": "Enviada",
            "status_label": "Enviada",
            "periodo_inicio": "2024-06-01",
            "periodo_fim": "2024-06-30",
            "data": "02/05/2024",
        },
        {
            "id": "cot3",
            "numero_cotacao": "COT-202404-D81E",
            "nome_campanha": "Performance digital Q2",
            "titulo": "Mídia digital Q2",
            "valor_total": 12000.00,
            "valor": "R$ 12.000,00",
            "status": "rejeitada",
            "status_canonico": "Rejeitada",
            "status_label": "Rejeitada",
            "periodo_inicio": "2024-04-01",
            "periodo_fim": "2024-06-30",
            "data": "20/04/2024",
        },
    ],
}

_INITIAL_NOTAS = {
    "auto-shopping": [
        {
            "id": "n1",
            "texto": "Cliente prefere contato pela manhã.",
            "autor": "Luisa Santana",
            "data": "2024-05-26",
        }
    ],
}


def _validate_iso_date(value, field="data"):
    value = str(value or "").strip()
    if value:
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(f"{field.capitalize()} deve estar no formato ISO YYYY-MM-DD") from exc
    return value


def _require_text(data, field, label):
    value = str(data.get(field) or "").strip()
    if not value:
        raise ValueError(f"{label} é obrigatório")
    return value


def _cotacao_status(value):
    raw = str(value or "Rascunho").strip()
    slug = COTACAO_STATUS_ALIASES.get(raw.casefold())
    if not slug:
        permitidos = ", ".join(COTACAO_STATUS.values())
        raise ValueError(f"Status de cotação inválido. Use: {permitidos}")
    return slug, COTACAO_STATUS[slug]


def _decimal_value(value):
    if value in (None, ""):
        return 0.0
    try:
        if isinstance(value, str):
            normalized = value.replace("R$", "").replace(" ", "")
            if "," in normalized:
                normalized = normalized.replace(".", "").replace(",", ".")
            value = normalized
        return round(float(value), 2)
    except (TypeError, ValueError) as exc:
        raise ValueError("Valor total deve ser numérico") from exc


def _format_brl(value):
    inteiro, centavos = f"{value:,.2f}".split(".")
    inteiro = inteiro.replace(",", ".")
    return f"R$ {inteiro},{centavos}"


class CrmTestStore:
    def __init__(self):
        self.reset()

    def reset(self):
        self.clientes = copy.deepcopy(_INITIAL_CLIENTES)
        self.contatos = copy.deepcopy(_INITIAL_CONTATOS)
        for cliente in self.clientes:
            cliente.update(_CLIENTE_REALISMO[cliente["id"]])
        for contatos in self.contatos.values():
            for contato in contatos:
                setor, status = _CONTATO_REALISMO[contato["id"]]
                contato.update({"setor": setor, "status": status})
        self.atividades = copy.deepcopy(_INITIAL_ATIVIDADES)
        self.objetivos = copy.deepcopy(_INITIAL_OBJETIVOS)
        self.cotacoes = copy.deepcopy(_INITIAL_COTACOES)
        self.notas = copy.deepcopy(_INITIAL_NOTAS)

    def _enrich_cliente(self, c):
        cliente_id = c["id"]
        qtd = len(self.contatos.get(cliente_id, []))
        ativs = self.atividades.get(cliente_id, [])
        tarefas = sum(1 for a in ativs if a.get("status") != "concluida")
        cotacoes = self.cotacoes.get(cliente_id, [])
        cotacoes_abertas = sum(
            1
            for cot in cotacoes
            if str(cot.get("status") or "").lower() not in ("aprovada", "rejeitada", "expirada")
        )
        item = dict(c)
        item["seguindo"] = bool(item.get("seguindo", False))
        item["favorito"] = bool(item.get("favorito", False))
        item["qtd_contatos"] = qtd
        item["sub"] = f"{c['tipo_label']} · {pluralizar_contatos(qtd)}"

        # Vínculos agência↔clientes finais
        is_agencia = bool(item.get("is_agencia"))
        item["is_agencia"] = is_agencia
        clientes_finais_ids = list(item.get("clientes_finais_ids") or [])
        item["clientes_finais_ids"] = clientes_finais_ids
        item["clientes_finais_count"] = len(clientes_finais_ids)
        agencia_id = item.get("agencia_id") or ""
        item["agencia_id"] = agencia_id
        # Resolver nomes de vínculos
        if is_agencia and clientes_finais_ids:
            filhos = []
            for fid in clientes_finais_ids:
                filho = next((x for x in self.clientes if x["id"] == fid), None)
                if filho:
                    filhos.append(
                        {
                            "id": filho["id"],
                            "nome": filho.get("nome_fantasia") or filho.get("nome"),
                            "classificacao_cliente": filho.get("classificacao_cliente"),
                        }
                    )
            item["clientes_finais"] = filhos
        else:
            item["clientes_finais"] = []
        if agencia_id and not is_agencia:
            ag = next((x for x in self.clientes if x["id"] == agencia_id), None)
            item["agencia_nome"] = ag.get("nome_fantasia") if ag else ""
        else:
            item["agencia_nome"] = ""

        # Estrutura de agencias_vinculadas (N:N) para formulário
        agencias_vinculadas = list(item.get("agencias_vinculadas") or [])
        if not agencias_vinculadas and agencia_id:
            agencias_vinculadas = [{"agencia_id": agencia_id, "is_principal": True}]
        item["agencias_vinculadas"] = agencias_vinculadas

        # Endereço garantido como dict
        endereco = item.get("endereco") or {}
        item["endereco"] = {
            "cep": endereco.get("cep") or item.get("cep") or "",
            "uf": (endereco.get("uf") or item.get("uf") or "").upper(),
            "cidade": endereco.get("cidade") or item.get("cidade") or "",
            "bairro": endereco.get("bairro") or item.get("bairro") or "",
            "logradouro": endereco.get("logradouro") or item.get("logradouro") or "",
            "numero": endereco.get("numero") or item.get("numero") or "",
            "complemento": endereco.get("complemento") or item.get("complemento") or "",
        }

        # Comerciais com default
        item["pessoa"] = item.get("pessoa") or "J"
        item["inscricao_estadual"] = item.get("inscricao_estadual") or ""
        item["inscricao_municipal"] = item.get("inscricao_municipal") or ""
        item["bv_percentual"] = float(item.get("bv_percentual") or 0)
        item["margem_cc"] = float(item.get("margem_cc") or 0)
        item["opera_midia"] = bool(item.get("opera_midia"))
        item["demanda_dados"] = bool(item.get("demanda_dados"))
        item["demanda_programatica_canais"] = bool(item.get("demanda_programatica_canais"))
        item["observacoes_comerciais_adicionais"] = (
            item.get("observacoes_comerciais_adicionais") or ""
        )

        item["metrics"] = {
            "contatos": qtd,
            "oportunidades": len(cotacoes),
            "faturamento": c.get("faturamento") or "R$ 12.500,00",
            "valor_pis": c.get("valor_pis") or "R$ 8.900,00",
            "tarefas_abertas": tarefas,
            "cotacoes_abertas": cotacoes_abertas,
            "ultimo_contato": c.get("ultimo_contato") or "Hoje",
        }
        return item

    def list_clientes(self):
        return [self._enrich_cliente(c) for c in self.clientes]

    def get_cliente(self, cliente_id):
        for c in self.clientes:
            if c["id"] == cliente_id:
                return self._enrich_cliente(c)
        return None

    def create_cliente(self, data):
        nome = _require_text(data, "nome", "Nome")
        cliente_id = data.get("id") or uuid.uuid4().hex[:12]
        if self.get_cliente(cliente_id):
            raise ValueError("ID de cliente já existe")
        status = str(data.get("status") or "sem-atividade").strip()
        if status == "seguindo":
            status = "sem-atividade"
        classificacao = str(
            data.get("classificacao_cliente") or "Prospecção"
        ).strip()
        if classificacao not in CLASSIFICACOES_CLIENTE:
            raise ValueError(
                "Classificação do cliente deve ser Prospecção, Ativo ou Geladeira"
            )
        data_cadastro = _validate_iso_date(
            data.get("data_cadastro") or date.today().isoformat(),
            "data_cadastro",
        )
        endereco_data = data.get("endereco") or {}
        cliente = {
            "id": cliente_id,
            "nome": nome,
            "pessoa": str(data.get("pessoa") or "J").strip() or "J",
            "cnpj": str(data.get("cnpj") or "").strip(),
            "razao_social": str(data.get("razao_social") or nome).strip(),
            "nome_fantasia": str(data.get("nome_fantasia") or nome).strip(),
            "inscricao_estadual": str(data.get("inscricao_estadual") or "").strip(),
            "inscricao_municipal": str(data.get("inscricao_municipal") or "").strip(),
            "classificacao_cliente": classificacao,
            "tipo": str(data.get("tipo") or data.get("categoria") or "Privado").strip(),
            "tipo_label": data.get("tipo_label") or ("Agência" if data.get("is_agencia") or data.get("perfil") == "agencia" else "Cliente final"),
            "perfil": data.get("perfil") or ("agencia" if data.get("is_agencia") else "direto"),
            "is_agencia": bool(data.get("is_agencia") or data.get("perfil") == "agencia"),
            "cidade": str(endereco_data.get("cidade") or data.get("cidade") or "").strip(),
            "uf": str(endereco_data.get("uf") or data.get("uf") or "").strip().upper(),
            "segmento": str(data.get("segmento") or "").strip(),
            "fonte": str(data.get("fonte") or "Cadastro manual").strip(),
            "data_cadastro": data_cadastro,
            "status": status,
            "badge": "Novo",
            "badge_type": "info",
            "avatar": nome[0].upper(),
            "seguindo": False,
            "favorito": bool(data.get("favorito", False)),
            "prioridade": data.get("prioridade") or "Média",
            "categoria": data.get("categoria") or "Privado",
            "responsavel": data.get("responsavel") or "Luisa Santana",
            "endereco": {
                "cep": str(endereco_data.get("cep") or "").strip(),
                "uf": str(endereco_data.get("uf") or "").strip().upper(),
                "cidade": str(endereco_data.get("cidade") or "").strip(),
                "bairro": str(endereco_data.get("bairro") or "").strip(),
                "logradouro": str(endereco_data.get("logradouro") or "").strip(),
                "numero": str(endereco_data.get("numero") or "").strip(),
                "complemento": str(endereco_data.get("complemento") or "").strip(),
            },
            "bv_percentual": float(data.get("bv_percentual") or 0),
            "margem_cc": float(data.get("margem_cc") or 0),
            "opera_midia": bool(data.get("opera_midia")),
            "demanda_dados": bool(data.get("demanda_dados")),
            "demanda_programatica_canais": bool(data.get("demanda_programatica_canais")),
            "observacoes_comerciais_adicionais": str(data.get("observacoes_comerciais_adicionais") or "").strip(),
            "clientes_finais_ids": [],
            "agencia_id": "",
            "agencias_vinculadas": [],
        }
        self.clientes.append(cliente)
        self.contatos[cliente_id] = []
        self.atividades[cliente_id] = []
        self.objetivos[cliente_id] = []
        self.cotacoes[cliente_id] = []
        self.notas[cliente_id] = []
        # Aplicar vínculos, se fornecidos
        vinculos = data.get("agencias_vinculadas") or []
        if vinculos:
            self._aplicar_agencias_vinculadas(cliente_id, vinculos)
        return self.get_cliente(cliente_id)

    def update_cliente(self, cliente_id, data):
        for i, cliente in enumerate(self.clientes):
            if cliente["id"] != cliente_id:
                continue
            updated = dict(cliente)
            text_fields = (
                "nome", "tipo_label", "perfil", "status", "badge", "badge_type",
                "prioridade", "categoria", "responsavel", "cnpj", "razao_social",
                "nome_fantasia", "tipo", "cidade", "uf", "segmento", "fonte",
                "pessoa", "inscricao_estadual", "inscricao_municipal",
                "observacoes_comerciais_adicionais",
            )
            for key in text_fields:
                if key in data:
                    value = str(data[key] or "").strip()
                    if key == "nome" and not value:
                        raise ValueError("Nome é obrigatório")
                    updated[key] = value
            if "classificacao_cliente" in data:
                classificacao = str(data["classificacao_cliente"] or "").strip()
                if classificacao not in CLASSIFICACOES_CLIENTE:
                    raise ValueError(
                        "Classificação do cliente deve ser Prospecção, Ativo ou Geladeira"
                    )
                updated["classificacao_cliente"] = classificacao
            if "data_cadastro" in data:
                updated["data_cadastro"] = _validate_iso_date(
                    data["data_cadastro"], "data_cadastro"
                )
            if "uf" in data:
                updated["uf"] = (updated.get("uf") or "").upper()
            for key in ("seguindo", "favorito", "is_agencia", "opera_midia", "demanda_dados", "demanda_programatica_canais"):
                if key in data:
                    if not isinstance(data[key], bool):
                        raise ValueError(f"{key} deve ser booleano")
                    updated[key] = data[key]
            for key in ("bv_percentual", "margem_cc"):
                if key in data:
                    try:
                        updated[key] = float(data[key] or 0)
                    except (TypeError, ValueError) as exc:
                        raise ValueError(f"{key} deve ser numérico") from exc
            if "endereco" in data and isinstance(data["endereco"], dict):
                end = data["endereco"]
                updated["endereco"] = {
                    "cep": str(end.get("cep") or "").strip(),
                    "uf": str(end.get("uf") or "").strip().upper(),
                    "cidade": str(end.get("cidade") or "").strip(),
                    "bairro": str(end.get("bairro") or "").strip(),
                    "logradouro": str(end.get("logradouro") or "").strip(),
                    "numero": str(end.get("numero") or "").strip(),
                    "complemento": str(end.get("complemento") or "").strip(),
                }
                if not updated.get("cidade"):
                    updated["cidade"] = updated["endereco"]["cidade"]
                if not updated.get("uf"):
                    updated["uf"] = updated["endereco"]["uf"]
            if "is_agencia" in data:
                updated["tipo_label"] = "Agência" if updated["is_agencia"] else "Cliente final"
                updated["perfil"] = "agencia" if updated["is_agencia"] else "direto"
            if "nome" in data:
                updated["avatar"] = (updated["nome"] or "?")[0].upper()
            self.clientes[i] = updated
            # Reconciliar vínculos, se informados
            if "agencias_vinculadas" in data:
                self._aplicar_agencias_vinculadas(cliente_id, data.get("agencias_vinculadas") or [])
            return self.get_cliente(cliente_id)
        return None

    def _aplicar_agencias_vinculadas(self, cliente_id, vinculos):
        """Reconcilia agencia_id (lado cliente final) e clientes_finais_ids (lado agência).

        vinculos: [{"agencia_id": str, "is_principal": bool}]
        """
        cliente = next((c for c in self.clientes if c["id"] == cliente_id), None)
        if not cliente:
            return
        vinculos_validos = [v for v in vinculos if v.get("agencia_id")]
        # Remover cliente_id de agências antigas
        old_agencia_id = cliente.get("agencia_id") or ""
        if old_agencia_id and old_agencia_id not in [v.get("agencia_id") for v in vinculos_validos]:
            ag_old = next((c for c in self.clientes if c["id"] == old_agencia_id), None)
            if ag_old:
                cf = list(ag_old.get("clientes_finais_ids") or [])
                if cliente_id in cf:
                    cf.remove(cliente_id)
                    ag_old["clientes_finais_ids"] = cf
        # Definir agência principal
        principal = next((v for v in vinculos_validos if v.get("is_principal")), None)
        if not principal and vinculos_validos:
            principal = vinculos_validos[0]
        cliente["agencia_id"] = principal.get("agencia_id") if principal else ""
        cliente["agencias_vinculadas"] = [
            {
                "agencia_id": v.get("agencia_id"),
                "is_principal": bool(v.get("is_principal")),
            }
            for v in vinculos_validos
        ]
        # Adicionar cliente_id nas agências correspondentes
        for v in vinculos_validos:
            ag = next((c for c in self.clientes if c["id"] == v.get("agencia_id")), None)
            if not ag:
                continue
            cf = list(ag.get("clientes_finais_ids") or [])
            if cliente_id not in cf:
                cf.append(cliente_id)
                ag["clientes_finais_ids"] = cf

    def list_contatos(self, cliente_id):
        if not self.get_cliente(cliente_id):
            return None
        return list(self.contatos.get(cliente_id, []))

    def create_contato(self, cliente_id, data):
        if not self.get_cliente(cliente_id):
            return None
        nome = (data.get("nome") or "").strip()
        email = (data.get("email") or "").strip()
        if not nome or not email:
            raise ValueError("Nome e e-mail são obrigatórios")
        contato_id = f"c-{uuid.uuid4().hex[:8]}"
        principal = bool(data.get("principal"))
        contatos = self.contatos.setdefault(cliente_id, [])
        if principal or not contatos:
            for c in contatos:
                c["principal"] = False
        contato = {
            "id": contato_id,
            "nome": nome,
            "cargo": (data.get("cargo") or "").strip(),
            "setor": (data.get("setor") or "Comercial").strip(),
            "status": (data.get("status") or "Ativo").strip(),
            "email": email,
            "telefone": (data.get("telefone") or "").strip(),
            "telefone_secundario": (data.get("telefone_secundario") or "").strip(),
            "principal": principal or not contatos,
            "avatar": nome.split()[0][0].upper() + (nome.split()[1][0].upper() if len(nome.split()) > 1 else ""),
            "conversas": 0,
        }
        contatos.append(contato)
        return contato

    def update_contato(self, contato_id, data):
        for cliente_id, contatos in self.contatos.items():
            for i, c in enumerate(contatos):
                if c["id"] == contato_id:
                    updated = dict(c)
                    for key in (
                        "nome", "cargo", "setor", "status", "email", "telefone",
                        "telefone_secundario",
                    ):
                        if key in data and data[key] is not None:
                            updated[key] = str(data[key]).strip()
                    if data.get("principal"):
                        for other in contatos:
                            other["principal"] = False
                        updated["principal"] = True
                    nome = updated["nome"]
                    parts = nome.split()
                    updated["avatar"] = parts[0][0].upper() + (parts[1][0].upper() if len(parts) > 1 else "")
                    contatos[i] = updated
                    return updated, cliente_id
        return None, None

    def list_atividades(self, cliente_id):
        if not self.get_cliente(cliente_id):
            return None
        return list(self.atividades.get(cliente_id, []))

    def create_atividade(self, cliente_id, data):
        if not self.get_cliente(cliente_id):
            return None
        titulo = _require_text(data, "titulo", "Título")
        data_iso = _validate_iso_date(data.get("data"))
        ativ = {
            "id": f"a-{uuid.uuid4().hex[:8]}",
            "titulo": titulo,
            "descricao": (data.get("descricao") or "").strip(),
            "data_label": data.get("data_label") or "Agendada",
            "data": data_iso,
            "hora": data.get("hora") or "",
            "prioridade": data.get("prioridade") or "Média",
            "status": "pendente",
            "tipo": data.get("tipo") or "atividade",
            "responsavel": data.get("responsavel") or "LS",
        }
        self.atividades.setdefault(cliente_id, []).append(ativ)
        return ativ

    def update_atividade(self, atividade_id, data):
        for cliente_id, items in self.atividades.items():
            for i, a in enumerate(items):
                if a["id"] == atividade_id:
                    updated = dict(a)
                    for key in (
                        "titulo", "descricao", "hora", "prioridade", "status",
                        "data_label", "tipo", "responsavel",
                    ):
                        if key in data and data[key] is not None:
                            updated[key] = str(data[key]).strip()
                    if "titulo" in data and not updated["titulo"]:
                        raise ValueError("Título é obrigatório")
                    if "data" in data:
                        updated["data"] = _validate_iso_date(data["data"])
                    items[i] = updated
                    return updated, cliente_id
        return None, None

    def delete_atividade(self, atividade_id):
        for cliente_id, items in self.atividades.items():
            for i, a in enumerate(items):
                if a["id"] == atividade_id:
                    items.pop(i)
                    return True, cliente_id
        return False, None

    def list_objetivos(self, cliente_id):
        if not self.get_cliente(cliente_id):
            return None
        return list(self.objetivos.get(cliente_id, []))

    def create_objetivo(self, cliente_id, data):
        if not self.get_cliente(cliente_id):
            return None
        concluido = data.get("concluido", False)
        if not isinstance(concluido, bool):
            raise ValueError("Concluido deve ser booleano")
        objetivo = {
            "id": f"o-{uuid.uuid4().hex[:8]}",
            "texto": _require_text(data, "texto", "Texto"),
            "prazo": str(data.get("prazo") or "").strip(),
            "concluido": concluido,
        }
        self.objetivos.setdefault(cliente_id, []).append(objetivo)
        return objetivo

    def update_objetivo(self, objetivo_id, data):
        for cliente_id, items in self.objetivos.items():
            for i, objetivo in enumerate(items):
                if objetivo["id"] != objetivo_id:
                    continue
                updated = dict(objetivo)
                for key in ("texto", "prazo"):
                    if key in data:
                        updated[key] = str(data[key] or "").strip()
                if "texto" in data and not updated["texto"]:
                    raise ValueError("Texto é obrigatório")
                if "concluido" in data:
                    if not isinstance(data["concluido"], bool):
                        raise ValueError("Concluido deve ser booleano")
                    updated["concluido"] = data["concluido"]
                items[i] = updated
                return updated, cliente_id
        return None, None

    def delete_objetivo(self, objetivo_id):
        for cliente_id, items in self.objetivos.items():
            for i, o in enumerate(items):
                if o["id"] == objetivo_id:
                    items.pop(i)
                    return True, cliente_id
        return False, None

    def list_cotacoes(self, cliente_id):
        if not self.get_cliente(cliente_id):
            return None
        return list(self.cotacoes.get(cliente_id, []))

    def create_cotacao(self, cliente_id, data):
        if not self.get_cliente(cliente_id):
            return None
        titulo = str(data.get("titulo") or data.get("nome_campanha") or "").strip()
        if not titulo:
            raise ValueError("Título é obrigatório")
        nome_campanha = str(data.get("nome_campanha") or titulo).strip()
        status, status_canonico = _cotacao_status(
            data.get("status_canonico") or data.get("status") or "Rascunho"
        )
        periodo_inicio = _validate_iso_date(
            data.get("periodo_inicio"), "periodo_inicio"
        )
        periodo_fim = _validate_iso_date(data.get("periodo_fim"), "periodo_fim")
        if periodo_inicio and periodo_fim and periodo_fim < periodo_inicio:
            raise ValueError("Período final não pode ser anterior ao período inicial")
        referencia = periodo_inicio or date.today().isoformat()
        numero_cotacao = str(data.get("numero_cotacao") or "").strip()
        if not numero_cotacao:
            numero_cotacao = (
                f"COT-{referencia[:4]}{referencia[5:7]}-{uuid.uuid4().hex[:4].upper()}"
            )
        valor_total = _decimal_value(
            data.get("valor_total")
            if data.get("valor_total") not in (None, "")
            else data.get("valor")
        )
        cotacao = {
            "id": f"cot-{uuid.uuid4().hex[:8]}",
            "numero_cotacao": numero_cotacao,
            "nome_campanha": nome_campanha,
            "titulo": titulo,
            "valor_total": valor_total,
            "valor": str(data.get("valor") or _format_brl(valor_total)).strip(),
            "status": status,
            "status_canonico": status_canonico,
            "status_label": status_canonico,
            "periodo_inicio": periodo_inicio,
            "periodo_fim": periodo_fim,
            "data": str(data.get("data") or "").strip(),
        }
        self.cotacoes.setdefault(cliente_id, []).append(cotacao)
        return cotacao

    def update_cotacao(self, cotacao_id, data):
        for cliente_id, items in self.cotacoes.items():
            for i, cotacao in enumerate(items):
                if cotacao["id"] != cotacao_id:
                    continue
                updated = dict(cotacao)
                for key in (
                    "numero_cotacao", "nome_campanha", "titulo", "valor", "data",
                ):
                    if key in data:
                        updated[key] = str(data[key] or "").strip()
                if "titulo" in data and not updated["titulo"]:
                    raise ValueError("Título é obrigatório")
                if "valor_total" in data:
                    updated["valor_total"] = _decimal_value(data["valor_total"])
                    if "valor" not in data:
                        updated["valor"] = _format_brl(updated["valor_total"])
                elif "valor" in data:
                    updated["valor_total"] = _decimal_value(data["valor"])
                if "status" in data or "status_canonico" in data:
                    status, status_canonico = _cotacao_status(
                        data.get("status_canonico") or data.get("status")
                    )
                    updated["status"] = status
                    updated["status_canonico"] = status_canonico
                    updated["status_label"] = status_canonico
                for key in ("periodo_inicio", "periodo_fim"):
                    if key in data:
                        updated[key] = _validate_iso_date(data[key], key)
                if (
                    updated.get("periodo_inicio")
                    and updated.get("periodo_fim")
                    and updated["periodo_fim"] < updated["periodo_inicio"]
                ):
                    raise ValueError(
                        "Período final não pode ser anterior ao período inicial"
                    )
                items[i] = updated
                return updated, cliente_id
        return None, None

    def delete_cotacao(self, cotacao_id):
        for cliente_id, items in self.cotacoes.items():
            for i, cotacao in enumerate(items):
                if cotacao["id"] == cotacao_id:
                    items.pop(i)
                    return True, cliente_id
        return False, None

    def list_notas(self, cliente_id):
        if not self.get_cliente(cliente_id):
            return None
        return list(self.notas.get(cliente_id, []))

    def create_nota(self, cliente_id, data):
        if not self.get_cliente(cliente_id):
            return None
        nota = {
            "id": f"n-{uuid.uuid4().hex[:8]}",
            "texto": _require_text(data, "texto", "Texto"),
            "autor": str(data.get("autor") or "Usuário").strip(),
            "data": _validate_iso_date(data.get("data")),
        }
        self.notas.setdefault(cliente_id, []).append(nota)
        return nota

    def update_nota(self, nota_id, data):
        for cliente_id, items in self.notas.items():
            for i, nota in enumerate(items):
                if nota["id"] != nota_id:
                    continue
                updated = dict(nota)
                for key in ("texto", "autor"):
                    if key in data:
                        updated[key] = str(data[key] or "").strip()
                if "texto" in data and not updated["texto"]:
                    raise ValueError("Texto é obrigatório")
                if "data" in data:
                    updated["data"] = _validate_iso_date(data["data"])
                items[i] = updated
                return updated, cliente_id
        return None, None

    def delete_nota(self, nota_id):
        for cliente_id, items in self.notas.items():
            for i, nota in enumerate(items):
                if nota["id"] == nota_id:
                    items.pop(i)
                    return True, cliente_id
        return False, None

    def import_contatos(self, cliente_id, contatos_data):
        if not self.get_cliente(cliente_id):
            return None
        created = []
        backup = copy.deepcopy(self.contatos.get(cliente_id, []))
        try:
            for row in contatos_data:
                c = self.create_contato(cliente_id, row)
                if c:
                    created.append(c)
        except Exception:
            self.contatos[cliente_id] = backup
            raise
        return created


store = CrmTestStore()
