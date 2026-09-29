"""Exceções do contexto Relatórios.

Mesmo raciocínio dos demais contextos (ver
certificados/domain/exceptions.py, documentos_fiscais/domain/exceptions.py
e documentos_auxiliares/domain/exceptions.py): uma única exceção de
requisição inválida, sem inventar uma hierarquia que a API não garante.
"""


class RelatorioError(Exception):
    """Erro base do contexto Relatórios."""


class RelatorioRequisicaoInvalidaError(RelatorioError):
    """A API respondeu erro a uma solicitação de relatório.

    `mensagens` carrega o que a API devolveu (quando ela devolve um corpo
    com a lista `Mensagens` — nem toda rota documentada garante isso).
    """

    def __init__(self, mensagens: list[str] | None = None):
        mensagens = mensagens or []
        super().__init__("; ".join(mensagens) or "Erro ao processar requisição.")
        self.mensagens = mensagens
