"""Porta de autenticação compartilhada por todos os gateways da API SIEG."""
from typing import Protocol


class TokenProviderPort(Protocol):
    """Fornece um JWT válido para chamadas à API SIEG.

    Quem implementa esta porta é responsável por todo o ciclo de vida do
    token (gerar, cachear, renovar antes de expirar) — quem consome nunca
    deve se preocupar com isso, só pede um token válido.
    """

    def obter_jwt(self) -> str:
        """Retorna um JWT válido, renovando internamente se necessário."""
        ...
