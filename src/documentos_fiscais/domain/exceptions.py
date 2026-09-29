"""Exceções do contexto Documentos Fiscais.

Mesmo raciocínio do contexto Certificados (ver
certificados/domain/exceptions.py): a API SIEG costuma responder erro sem
diferenciar tipos de falha de forma confiável, então mantemos uma única
exceção de requisição inválida em vez de inventar uma hierarquia que a API
não garante.
"""


class DocumentoFiscalError(Exception):
    """Erro base do contexto Documentos Fiscais."""


class DocumentoFiscalRequisicaoInvalidaError(DocumentoFiscalError):
    """A API respondeu erro a uma operação de download de documento fiscal.

    `mensagens` carrega o que a API devolveu (quando ela devolve um corpo
    com a lista `Mensagens` — nem toda rota documentada garante isso).
    """

    def __init__(self, mensagens: list[str] | None = None):
        mensagens = mensagens or []
        super().__init__("; ".join(mensagens) or "Erro ao processar requisição.")
        self.mensagens = mensagens
