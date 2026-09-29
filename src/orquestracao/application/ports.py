"""Portas do contexto Orquestração (Agente).

A camada de aplicação depende só destas interfaces — nunca do SDK da
Claude, do Flask ou de qualquer detalhe de infraestrutura diretamente.
Três portas, cada uma isolando uma responsabilidade externa diferente:

- ClienteIAPort: fala com o modelo de linguagem (hoje, Claude via Messages
  API com tool use). Pura pergunta/resposta — não sabe nada sobre
  certificados, XML ou SIEG.
- ExecutorFerramentaPort: executa uma tool_use pedida pela IA contra os
  casos de uso reais dos outros bounded contexts (Certificados,
  Documentos Fiscais, Documentos Auxiliares, Relatórios). É aqui que a
  política de confirmação (ver domain/politica_confirmacao.py) é
  aplicada de fato, antes de qualquer ação destrutiva rodar.
- AuditLoggerPort: registra cada ferramenta chamada, com redação de dados
  sensíveis — implementação concreta decide onde/como persistir.
"""
from typing import Protocol

from ..domain.value_objects import ChamadaFerramenta, MensagemConversa, ResultadoFerramenta, RespostaIA


class ClienteIAPort(Protocol):
    def perguntar(
        self,
        mensagens: list[MensagemConversa],
        ferramentas: list[dict],
    ) -> RespostaIA: ...


class ExecutorFerramentaPort(Protocol):
    def executar(self, chamada: ChamadaFerramenta, sessao_id: str) -> ResultadoFerramenta: ...


class AuditLoggerPort(Protocol):
    def registrar(
        self,
        sessao_id: str,
        nome_ferramenta: str,
        argumentos: dict,
        sucesso: bool,
        resumo_resultado: str,
    ) -> None: ...
