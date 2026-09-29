"""Cliente HTTP compartilhado por todos os gateways da API SIEG.

Centraliza os dois headers obrigatórios em toda chamada de negócio:
    Authorization: Bearer {jwt}
    X-API-Key: {chave da conta, com nível de acesso}

Nenhum gateway de contexto (Certificados, Documentos Fiscais, ...) deve
montar esses headers por conta própria — todos passam por aqui.
"""
from enum import Enum

import requests

from .auth.ports import TokenProviderPort


class NivelAcesso(Enum):
    """Nível de acesso da X-API-Key exigido pela chamada.

    Nota importante: em Minha Conta -> Integrações, a permissão "Apenas
    envio e escrita (sem leitura)" é literalmente write-only — uma chave
    nesse nível não consegue fazer GET. Por isso ESCRITA aqui é servida
    pela chave "Acesso total" (fullAccess), não por uma chave write-only:
    um caso de uso de edição pode precisar ler o estado atual antes de
    gravar, e uma chave write-only quebraria esse fluxo.
    """

    LEITURA = "leitura"
    ESCRITA = "escrita"


class SiegHttpClient:
    def __init__(
        self,
        base_url: str,
        token_provider: TokenProviderPort,
        chave_leitura: str,
        chave_escrita: str,
    ):
        self._base_url = base_url.rstrip("/")
        self._token_provider = token_provider
        self._chaves = {
            NivelAcesso.LEITURA: chave_leitura,
            NivelAcesso.ESCRITA: chave_escrita,
        }

    def _headers(self, nivel: NivelAcesso) -> dict:
        return {
            "Authorization": f"Bearer {self._token_provider.obter_jwt()}",
            "X-API-Key": self._chaves[nivel],
            "Content-Type": "application/json",
        }

    def get(self, path: str, nivel: NivelAcesso, params: dict | None = None) -> dict:
        resp = requests.get(
            f"{self._base_url}{path}", headers=self._headers(nivel), params=params, timeout=30
        )
        resp.raise_for_status()
        return resp.json() if resp.content else {}

    def post(self, path: str, nivel: NivelAcesso, payload: dict | None = None) -> dict:
        resp = requests.post(
            f"{self._base_url}{path}", headers=self._headers(nivel), json=payload, timeout=30
        )
        resp.raise_for_status()
        return resp.json() if resp.content else {}

    def post_query(self, path: str, nivel: NivelAcesso, params: dict) -> dict:
        """Para rotas como habilitar/desabilitar: POST sem corpo, id via query string."""
        resp = requests.post(
            f"{self._base_url}{path}", headers=self._headers(nivel), params=params, timeout=30
        )
        resp.raise_for_status()
        return resp.json() if resp.content else {}

    def delete(self, path: str, nivel: NivelAcesso, params: dict | None = None) -> dict:
        resp = requests.delete(
            f"{self._base_url}{path}", headers=self._headers(nivel), params=params, timeout=30
        )
        resp.raise_for_status()
        return resp.json() if resp.content else {}
