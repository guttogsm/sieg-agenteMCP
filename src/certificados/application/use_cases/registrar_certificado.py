from ...domain.entities import Certificado
from ..ports import CertificadoGatewayPort


class RegistrarCertificado:
    def __init__(self, gateway: CertificadoGatewayPort):
        self._gateway = gateway

    def executar(self, certificado: Certificado) -> Certificado:
        if certificado.id is not None:
            # A própria API trata isso como edição se um id for enviado
            # (ver nota de "Registrar" no Swagger) — melhor deixar explícito
            # aqui do que confiar nesse comportamento implícito da API.
            raise ValueError(
                "RegistrarCertificado espera um certificado sem id; use EditarCertificado."
            )
        return self._gateway.registrar(certificado)
