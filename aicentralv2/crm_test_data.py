"""Dados fictícios em memória para o protótipo /teste-crm."""

import copy
import uuid
from datetime import date

from .crm_test_helpers import pluralizar_contatos

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
            "titulo": "Proposta comercial Q3",
            "valor": "R$ 45.000,00",
            "status": "negociacao",
            "status_label": "Em negociação",
            "data": "15/05/2024",
        },
        {
            "id": "cot2",
            "titulo": "Campanha institucional",
            "valor": "R$ 28.500,00",
            "status": "enviada",
            "status_label": "Enviada",
            "data": "02/05/2024",
        },
        {
            "id": "cot3",
            "titulo": "Mídia digital Q2",
            "valor": "R$ 12.000,00",
            "status": "perdida",
            "status_label": "Perdida",
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


class CrmTestStore:
    def __init__(self):
        self.reset()

    def reset(self):
        self.clientes = copy.deepcopy(_INITIAL_CLIENTES)
        self.contatos = copy.deepcopy(_INITIAL_CONTATOS)
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
        item = dict(c)
        item["seguindo"] = bool(item.get("seguindo", False))
        item["favorito"] = bool(item.get("favorito", False))
        item["qtd_contatos"] = qtd
        item["sub"] = f"{c['tipo_label']} · {pluralizar_contatos(qtd)}"
        item["metrics"] = {
            "contatos": qtd,
            "oportunidades": len(cotacoes),
            "faturamento": c.get("faturamento") or "R$ 12.500,00",
            "valor_pis": c.get("valor_pis") or "R$ 8.900,00",
            "tarefas_abertas": tarefas,
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
        cliente = {
            "id": cliente_id,
            "nome": nome,
            "tipo_label": data.get("tipo_label") or "Cliente final",
            "perfil": data.get("perfil") or "direto",
            "status": status,
            "badge": "Novo",
            "badge_type": "info",
            "avatar": nome[0].upper(),
            "seguindo": False,
            "favorito": bool(data.get("favorito", False)),
            "prioridade": data.get("prioridade") or "Média",
            "categoria": data.get("categoria") or "Privado",
            "responsavel": data.get("responsavel") or "Luisa Santana",
        }
        self.clientes.append(cliente)
        self.contatos[cliente_id] = []
        self.atividades[cliente_id] = []
        self.objetivos[cliente_id] = []
        self.cotacoes[cliente_id] = []
        self.notas[cliente_id] = []
        return self.get_cliente(cliente_id)

    def update_cliente(self, cliente_id, data):
        for i, cliente in enumerate(self.clientes):
            if cliente["id"] != cliente_id:
                continue
            updated = dict(cliente)
            text_fields = (
                "nome", "tipo_label", "perfil", "status", "badge", "badge_type",
                "prioridade", "categoria", "responsavel",
            )
            for key in text_fields:
                if key in data:
                    value = str(data[key] or "").strip()
                    if key == "nome" and not value:
                        raise ValueError("Nome é obrigatório")
                    updated[key] = value
            for key in ("seguindo", "favorito"):
                if key in data:
                    if not isinstance(data[key], bool):
                        raise ValueError(f"{key.capitalize()} deve ser booleano")
                    updated[key] = data[key]
            if "nome" in data:
                updated["avatar"] = updated["nome"][0].upper()
            self.clientes[i] = updated
            return self.get_cliente(cliente_id)
        return None

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
                    for key in ("nome", "cargo", "email", "telefone", "telefone_secundario"):
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
        cotacao = {
            "id": f"cot-{uuid.uuid4().hex[:8]}",
            "titulo": _require_text(data, "titulo", "Título"),
            "valor": str(data.get("valor") or "").strip(),
            "status": str(data.get("status") or "rascunho").strip(),
            "status_label": str(data.get("status_label") or "Rascunho").strip(),
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
                for key in ("titulo", "valor", "status", "status_label", "data"):
                    if key in data:
                        updated[key] = str(data[key] or "").strip()
                if "titulo" in data and not updated["titulo"]:
                    raise ValueError("Título é obrigatório")
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
