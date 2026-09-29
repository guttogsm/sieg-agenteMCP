"""Portas do contexto Documentos Auxiliares.

A camada de aplicação depende só destas interfaces — nunca de requests,
da SiegHttpClient, de subprocess ou de qualquer detalhe de infraestrutura
diretamente.
"""
from typing import Protocol

from ..domain.value_objects import ResultadoPdf


class DocumentoAuxiliarGatewayPort(Protocol):
    def gerar_danfe_via_chave(self, xml_key: str) -> ResultadoPdf: ...

    def gerar_danfe_via_xml(self, xml_base64: str) -> ResultadoPdf: ...

    def gerar_dacte_via_chave(self, xml_key: str) -> ResultadoPdf: ...

    def gerar_dacte_via_xml(self, xml_base64: str) -> ResultadoPdf: ...

    def gerar_danfse_via_chave(self, xml_key: str) -> ResultadoPdf: ...

    def gerar_danfse_via_xml(self, xml_base64: str) -> ResultadoPdf: ...


class GeradorPdfLocalPort(Protocol):
    """Geração de PDF que NÃO passa pela API SIEG — hoje só DANFCE (NFC-e),
    documento pra que a API não tem rota de geração (ver
    node_gerador_pdf_local.py). Recebe o XML já em bytes (nunca base64):
    diferente de DocumentoAuxiliarGatewayPort, isso nunca cruza a rede como
    payload HTTP, então não há motivo pra pagar o custo de base64 aqui.
    """

    def gerar_danfce_via_xml(self, xml_bytes: bytes) -> ResultadoPdf: ...
