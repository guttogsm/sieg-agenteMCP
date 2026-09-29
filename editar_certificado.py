from ...domain.entities import Certificado
from ..ports import CertificadoGatewayPort


class EditarCertificado:
    def __init__(self, gateway: CertificadoGatewayPort):
        self._gateway = gateway

    def executar(self, certificado: Certificado) -> Certificado:
        if certificado.id is None:
            raise ValueError("EditarCertificado exige um certificado com id existente.")
        return self._gateway.editar(certificado)
