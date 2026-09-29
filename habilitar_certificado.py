from ..ports import CertificadoGatewayPort


class HabilitarCertificado:
    def __init__(self, gateway: CertificadoGatewayPort):
        self._gateway = gateway

    def executar(self, certificado_id: str) -> None:
        self._gateway.habilitar(certificado_id)
