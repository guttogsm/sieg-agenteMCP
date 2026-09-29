"""Implementação de TokenProviderPort para a API SIEG.

Fluxo confirmado em produção (não é suposição):
  1. Cadastro de "sistema" aprovado manualmente pela SIEG gera um par
     ClientId + SecretKey (enviados por e-mail).
  2. POST /api/v1/create-jwt com headers X-Client-Id e X-Secret-Key
     devolve um JWT válido por 24h: {"Token": "eyJ..."}.
  3. Esse JWT deve ser reenviado (header Authorization: Bearer {jwt})
     em toda chamada de negócio, junto com a X-API-Key da conta.

Este provider cacheia o token em memória e só chama /create-jwt de novo
quando ele está perto de expirar — assim os casos de uso nunca precisam
saber que existe uma renovação diária acontecendo por baixo.
"""
import threading
import time

import requests

from .ports import TokenProviderPort


class SiegJwtProvider(TokenProviderPort):
    """Thread-safe: chamadas concorrentes não disparam renovações duplicadas."""

    _MARGEM_SEGURANCA_SEGUNDOS = 300  # renova 5 min antes do vencimento real

    def __init__(
        self,
        base_url: str,
        client_id: str,
        secret_key: str,
        validade_segundos: int = 24 * 3600,
    ):
        self._base_url = base_url.rstrip("/")
        self._client_id = client_id
        self._secret_key = secret_key
        self._validade_segundos = validade_segundos
        self._token: str | None = None
        self._expira_em: float = 0.0
        self._lock = threading.Lock()

    def obter_jwt(self) -> str:
        with self._lock:
            if self._token is None or time.time() >= self._expira_em:
                self._renovar()
            return self._token

    def _renovar(self) -> None:
        resp = requests.post(
            f"{self._base_url}/api/v1/create-jwt",
            headers={
                "X-Client-Id": self._client_id,
                "X-Secret-Key": self._secret_key,
            },
            timeout=15,
        )
        resp.raise_for_status()
        dados = resp.json()
        # A API devolve o JWT puro como string (confirmado em teste real),
        # não envelopado em {"Token": "..."} como o schema documentado
        # (CreateJwtResponseDto) sugeria. Aceita os dois formatos por
        # segurança, caso isso mude entre ambientes/versões.
        self._token = dados if isinstance(dados, str) else dados["Token"]
        self._expira_em = time.time() + self._validade_segundos - self._MARGEM_SEGURANCA_SEGUNDOS
