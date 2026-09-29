"""Exceções do contexto Certificados.

Deliberadamente enxuto: a API SIEG responde 400 com uma Reason genérica
("Erro ao processar requisição") sem diferenciar "não encontrado" de outros
erros de validação nas rotas de habilitar/desabilitar/deletar/status. Mapear
isso para exceções mais específicas agora seria inventar uma distinção que
a API não garante — melhor esperar ver mensagens de erro reais.
"""


class CertificadoError(Exception):
    """Erro base do contexto Certificados."""


class CertificadoRequisicaoInvalidaError(CertificadoError):
    """A API respondeu 400/500 a uma operação de certificado.

    `mensagens` carrega o que a API devolveu (quando ela devolve um corpo
    com a lista `Mensagens` — nem toda rota documentada garante isso).
    """

    def __init__(self, mensagens: list[str] | None = None):
        mensagens = mensagens or []
        super().__init__("; ".join(mensagens) or "Erro ao processar requisição.")
        self.mensagens = mensagens
