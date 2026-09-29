"""Value Objects do contexto Documentos Auxiliares (Pdf: Danfe/Dacte/Danfse).

NÃO TESTADO ainda contra a API real — baseado só no Swagger legado (seção
Pdf, 21/09/2026), que documenta as rotas sem prefixo /api/v1/, igual ao já
visto no contexto Documentos Fiscais.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ResultadoPdf:
    """CONFIRMADO no Swagger: "O Danfe/Dacte/Danfse é retornado em bytes[]
    e criptografado em Base64." Não há doc de um envelope com outros
    campos (tipo nome de arquivo) — hipótese é que o conteúdo já vem
    puro, como string Base64. Ainda não confirmado contra dado real.
    """

    conteudo_base64: str
