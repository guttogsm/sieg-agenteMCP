"""Porta do contexto Certificados.

A camada de aplicação depende só desta interface — nunca de requests,
da SiegHttpClient ou de qualquer detalhe de HTTP diretamente.
"""
from typing import Protocol

from ..domain.entities import Certificado, CertificadoResumo


class CertificadoGatewayPort(Protocol):
    def listar(self, active: bool, pagina: int = 0) -> list[CertificadoResumo]: ...

    def registrar(self, certificado: Certificado) -> Certificado: ...

    def editar(self, certificado: Certificado) -> Certificado: ...

    def habilitar(self, certificado_id: str) -> None: ...

    def desabilitar(self, certificado_id: str) -> None: ...

    def deletar(self, certificado_id: str) -> None: ...

    def status(self, certificado_id: str) -> str: ...
