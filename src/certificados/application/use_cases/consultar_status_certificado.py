from ..ports import CertificadoGatewayPort


class ConsultarStatusCertificado:
    def __init__(self, gateway: CertificadoGatewayPort):
        self._gateway = gateway

    def executar(self, certificado_id: str) -> str:
        return self._gateway.status(certificado_id)
