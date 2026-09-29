"""Caso de uso central do contexto Orquestração — o "agente" propriamente
dito: recebe uma mensagem em linguagem natural, conversa com a Claude
(tool use), executa as ferramentas que ela pedir contra os casos de uso
reais dos outros bounded contexts, e devolve a resposta final.

Loop clássico de tool use: pergunta pra IA -> se ela pediu ferramenta(s),
executa e manda o resultado de volta -> pergunta de novo -> repete até a
IA devolver texto final sem pedir mais nada. MAX_ITERACOES é só uma trava
de segurança (ver LimiteIteracoesExcedidoError) — não esperado em uso
normal.

Este caso de uso não sabe nada sobre HTTP, Flask, sessão em disco/memória
ou o SDK da Claude — só conhece as portas (ClienteIAPort,
ExecutorFerramentaPort, AuditLoggerPort). Quem injeta as implementações
reais é a composição (app_factory.py).
"""
from __future__ import annotations

from ..ports import AuditLoggerPort, ClienteIAPort, ExecutorFerramentaPort
from ...domain.exceptions import LimiteIteracoesExcedidoError
from ...domain.value_objects import ArquivoGerado, MensagemConversa, RespostaAgente


class ResponderMensagem:
    MAX_ITERACOES = 8

    def __init__(
        self,
        cliente_ia: ClienteIAPort,
        executor_ferramentas: ExecutorFerramentaPort,
        ferramentas: list[dict],
        audit_logger: AuditLoggerPort | None = None,
    ):
        self._cliente_ia = cliente_ia
        self._executor_ferramentas = executor_ferramentas
        self._ferramentas = ferramentas
        self._audit_logger = audit_logger

    def executar(
        self,
        sessao_id: str,
        mensagem_usuario: str,
        historico: list[MensagemConversa] | None = None,
    ) -> RespostaAgente:
        mensagens = list(historico or [])
        mensagens.append(MensagemConversa(papel="usuario", conteudo=mensagem_usuario))
        arquivos_gerados: list[ArquivoGerado] = []

        for _ in range(self.MAX_ITERACOES):
            resposta = self._cliente_ia.perguntar(mensagens, self._ferramentas)
            mensagens.append(MensagemConversa(papel="agente", conteudo=resposta.mensagem_bruta))

            if resposta.finalizada:
                return RespostaAgente(
                    texto=resposta.texto or "",
                    historico=mensagens,
                    arquivos_gerados=arquivos_gerados,
                )

            resultados = []
            for chamada in resposta.chamadas_ferramenta:
                resultado = self._executor_ferramentas.executar(chamada, sessao_id)
                resultados.append((chamada, resultado))
                if resultado.arquivo is not None:
                    arquivos_gerados.append(resultado.arquivo)
                if self._audit_logger is not None:
                    self._audit_logger.registrar(
                        sessao_id=sessao_id,
                        nome_ferramenta=chamada.nome,
                        argumentos=chamada.argumentos,
                        sucesso=resultado.sucesso,
                        resumo_resultado=resultado.conteudo[:300],
                    )
            mensagens.append(MensagemConversa(papel="tool_resultado", conteudo=resultados))

        raise LimiteIteracoesExcedidoError(
            f"Passou de {self.MAX_ITERACOES} idas e vindas com a IA sem resposta final "
            "— algo está fazendo a Claude insistir em chamar ferramentas em loop."
        )
