from ..ports import CertificadoGatewayPort


class DeletarCertificado:
    """Ação destrutiva e irreversível — mesma observação de
    DesabilitarCertificado: a confirmação já aconteceu antes de chegar aqui."""

    def __init__(self, gateway: CertificadoGatewayPort):
        self._gateway = gateway

    def executar(self, certificado_id: str) -> None:
        self._gateway.deletar(certificado_id)
