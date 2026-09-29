"""Implementação de AuditLoggerPort — registra cada ferramenta chamada
como uma linha JSON num arquivo, com redação de dados sensíveis.

Redação por dois critérios, de propósito redundantes (defesa em
profundidade, não confia só em uma lista de nomes de campo):
1. Nome do argumento bate com um padrão conhecido de dado sensível/grande
   (senha, qualquer coisa "_base64", conteúdo de XML).
2. OU o valor é uma string grande (> LIMITE_TAMANHO_VALOR caracteres) —
   pega qualquer coisa grande que a lista de nomes não previu, sem
   precisar manter a lista 100% completa pra ser segura.

Mesmo raciocínio já aplicado em certificados/domain/value_objects.py
(CredenciaisCertificado/CredenciaisPortalMunicipal "nunca logar") —
aqui generalizado pra qualquer ferramenta, presente ou futura, sem exigir
que cada uma declare manualmente o que é sensível.
"""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone

_CAMPOS_SEMPRE_REDIGIDOS = {
    "senha",
    "senha_certificado",
    "senha_usuario",
    "arquivo_base64",
    "xml_base64",
    "conteudo_base64",
}
_LIMITE_TAMANHO_VALOR = 200


def _redigir_valor(chave: str, valor):
    if isinstance(valor, str):
        if chave.lower() in _CAMPOS_SEMPRE_REDIGIDOS or "base64" in chave.lower():
            return f"<redigido: {len(valor)} caracteres>"
        if len(valor) > _LIMITE_TAMANHO_VALOR:
            return f"<redigido: {len(valor)} caracteres>"
    return valor


def _redigir_argumentos(argumentos: dict) -> dict:
    return {chave: _redigir_valor(chave, valor) for chave, valor in argumentos.items()}


class LoggerAuditoriaArquivo:
    def __init__(self, caminho_arquivo: str):
        self._caminho_arquivo = caminho_arquivo
        os.makedirs(os.path.dirname(caminho_arquivo) or ".", exist_ok=True)
        self._lock = threading.Lock()

    def registrar(
        self,
        sessao_id: str,
        nome_ferramenta: str,
        argumentos: dict,
        sucesso: bool,
        resumo_resultado: str,
    ) -> None:
        evento = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sessao_id": sessao_id,
            "ferramenta": nome_ferramenta,
            "argumentos": _redigir_argumentos(argumentos),
            "sucesso": sucesso,
            "resumo_resultado": resumo_resultado,
        }
        linha = json.dumps(evento, ensure_ascii=False)
        with self._lock:
            with open(self._caminho_arquivo, "a", encoding="utf-8") as f:
                f.write(linha + "\n")
