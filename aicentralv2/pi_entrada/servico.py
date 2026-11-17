"""Orquestra a leitura de uma entrada: arquivo -> leitor -> conferências -> banco. Roda em segundo plano."""

from __future__ import annotations

import hashlib
import logging
import os
import threading
import time
from pathlib import Path

from flask import current_app

from . import cadastro, conferencias, esquema, leitor, oportunidades, repositorio

logger = logging.getLogger(__name__)
LIMITE_ARQUIVOS_POR_ENVIO = 10


def pasta_privada() -> Path:
    """Fora de ``static/``: PI tem valores e dados de pessoas, só sai por rota autenticada."""
    base = current_app.config.get("PI_ENTRADA_DIR") or os.path.join(current_app.instance_path, "pi_entrada")
    pasta = Path(base)
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def guardar_arquivo(id_entrada: int, nome: str, conteudo: bytes) -> dict:
    sha = hashlib.sha256(conteudo).hexdigest()
    destino = pasta_privada() / str(id_entrada)
    destino.mkdir(parents=True, exist_ok=True)
    caminho = destino / f"{sha[:16]}.pdf"
    caminho.write_bytes(conteudo)
    return {"sha256": sha, "caminho": str(caminho), "tamanho": len(conteudo)}


def contexto_de_conferencia(pi: dict, ctx: dict, texto: str) -> dict:
    divergentes = leitor.conferir_contra_texto(pi, texto)
    return {"cliente_id": ctx.get("cliente_id"), "agencia_id": ctx.get("agencia_id"), "pi_existente": ctx.get("pi_existente"),
            "texto_divergente": divergentes, "texto_conferido": bool(texto.strip())}


def processar(id_entrada: int, *, chamar=None) -> None:
    """Lê o PDF da entrada e grava o resultado. Qualquer falha vira status ``erro`` com mensagem para o usuário."""
    inicio = time.monotonic()
    try:
        arquivo = repositorio.arquivo_da_entrada(id_entrada)
        if not arquivo:
            raise leitor.LeituraErro("A entrada não tem arquivo.")
        repositorio.mudar_status(id_entrada, "lendo")
        conteudo = Path(arquivo["caminho"]).read_bytes()
        leitura = leitor.ler(conteudo, arquivo["nome_original"], chamar=chamar)
        repositorio.registrar_log(id_entrada, "leitura", leitura.duracao_ms, f"{leitura.metodo}; {leitura.modelo}; {leitura.paginas} págs")
        ctx = cadastro.contexto(leitura.pi)
        conf_ctx = contexto_de_conferencia(leitura.pi, ctx, leitura.texto)
        itens = conferencias.conferir(leitura.pi, conf_ctx)
        ops = oportunidades.oportunidades(leitura.pi, ctx["cliente"], ctx["agencia"], ctx["emails"], ctx["observacoes"])
        resumo = {**conferencias.resumo(itens), "oportunidades": len(ops), "avisos": leitura.avisos}
        repositorio.salvar_leitura(
            id_entrada, pi=leitura.pi, bruto={"modelo": leitura.bruto, "texto_divergente": conf_ctx["texto_divergente"],
                                              "texto_conferido": conf_ctx["texto_conferido"]}, metodo=leitura.metodo, modelo=leitura.modelo,
            prompt_versao=esquema.PROMPT_VERSAO, tokens_entrada=leitura.tokens_entrada, tokens_saida=leitura.tokens_saida,
            resumo=resumo, ids=ctx)
        repositorio.registrar_log(id_entrada, "pronto", int((time.monotonic() - inicio) * 1000))
    except leitor.LeituraErro as exc:
        repositorio.mudar_status(id_entrada, "erro", str(exc))
        repositorio.registrar_log(id_entrada, "erro", int((time.monotonic() - inicio) * 1000), str(exc))
    except Exception as exc:                                                   # nunca deixar a entrada presa em "lendo"
        logger.exception("Entrada de PI %s falhou", id_entrada)
        repositorio.mudar_status(id_entrada, "erro", "Não foi possível ler este PI neste momento. Tente novamente ou comunique a equipe técnica.")
        repositorio.registrar_log(id_entrada, "erro", int((time.monotonic() - inicio) * 1000), repr(exc))


def iniciar_em_segundo_plano(id_entrada: int) -> None:
    app = current_app._get_current_object()

    def rodar():
        with app.app_context():
            processar(id_entrada)

    threading.Thread(target=rodar, name=f"pi-entrada-{id_entrada}", daemon=True).start()
