"""Exceções do contexto Documentos Auxiliares.

Mesmo raciocínio dos demais contextos (ver
certificados/domain/exceptions.py e documentos_fiscais/domain/exceptions.py):
uma única exceção de requisição inválida, sem inventar uma hierarquia que a
API não garante.
"""


class DocumentoAuxiliarError(Exception):
    """Erro base do contexto Documentos Auxiliares."""


class DocumentoAuxiliarRequisicaoInvalidaError(DocumentoAuxiliarError):
    """A API respondeu erro a uma operação de geração de Danfe/Dacte/Danfse.

    `mensagens` carrega o que a API devolveu (quando ela devolve um corpo
    com a lista `Mensagens` — nem toda rota documentada garante isso).
    """

    def __init__(self, mensagens: list[str] | None = None):
        mensagens = mensagens or []
        super().__init__("; ".join(mensagens) or "Erro ao processar requisição.")
        self.mensagens = mensagens
