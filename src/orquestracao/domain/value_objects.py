"""Value Objects do contexto Orquestração (Agente).

Deliberadamente enxuto: o formato de mensagem usado aqui (`papel` +
`conteudo`) é genérico o suficiente pra não vazar o formato de wire da
API da Claude (Messages API) pra dentro de domain/ — quem traduz pra lá e
de volta é a infraestrutura (ClaudeClienteIA), não este módulo. Ainda
assim, `conteudo` aceita tanto string (texto puro) quanto list[dict] (o
formato de "content blocks" da Claude, incluindo tool_use/tool_result) —
uma simplificação pragmática, no mesmo espírito de ResultadoDownload
guardar o XML cru em vez de modelar cada campo: reconstruir o formato de
blocks aqui dentro seria reinventar o wire format da Claude sem ganhar
nada, já que quem realmente processa isso é sempre a infraestrutura.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MensagemConversa:
    """Um turno da conversa — usuário, agente (texto e/ou tool_use) ou
    resultado de ferramenta (papel="tool_resultado" volta pro histórico
    como contexto pro próximo turno)."""

    papel: str  # "usuario" | "agente" | "tool_resultado"
    conteudo: Any


@dataclass
class ChamadaFerramenta:
    """Uma tool_use pedida pela Claude num turno da conversa."""

    id: str
    nome: str
    argumentos: dict


@dataclass
class RespostaIA:
    """O que ClienteIAPort.perguntar() devolve pra um turno.

    `finalizada=True` quando a Claude respondeu com texto final (sem
    pedir nenhuma ferramenta) — o loop do agente para aqui. Quando False,
    `chamadas_ferramenta` traz o que precisa ser executado antes de
    perguntar de novo.
    """

    texto: str | None
    chamadas_ferramenta: list[ChamadaFerramenta]
    finalizada: bool
    mensagem_bruta: Any  # o content block bruto da Claude, reenviado no próximo turno como contexto


@dataclass
class ArquivoGerado:
    """Um arquivo binário (PDF de Danfe/Dacte/Danfse, ZIP de lote, Excel de
    relatório) produzido por uma ferramenta nesta rodada da conversa.

    Deliberadamente NÃO devolvemos o base64 inteiro pra dentro do
    tool_result que volta pra Claude — além de caro em tokens (um PDF de
    150KB vira ~200k caracteres em base64), a Claude não precisa "ler" os
    bytes do PDF pra saber que deu certo. O conteúdo vai direto pro disco
    (ver ExecutorFerramentasSieg) e só o metadado (nome + caminho) sobe
    pela cadeia até o controller, que expõe um link de download real."""

    nome_arquivo: str
    caminho_absoluto: str


@dataclass
class ResultadoFerramenta:
    """O que ExecutorFerramentaPort.executar() devolve — `conteudo` é
    sempre serializado pra texto porque é isso que volta pra Claude como
    tool_result. `sucesso=False` não é uma falha do agente: é uma exceção
    de domínio conhecida (documento não encontrado, requisição inválida)
    que a própria Claude consegue ler e reagir (pedir outro filtro,
    explicar pro usuário, etc.) — só erros realmente inesperados devem
    escapar como exceção Python de verdade. `arquivo` vem preenchido só
    quando a ferramenta gerou um binário pro usuário baixar (ver
    ArquivoGerado)."""

    conteudo: str
    sucesso: bool = True
    arquivo: ArquivoGerado | None = None


@dataclass
class RespostaAgente:
    """O que o caso de uso ResponderMensagem devolve pro controller —
    texto final, histórico atualizado (que o controller é responsável por
    persistir na sessão — em memória, por enquanto, ver ressalva em
    app.py) e os arquivos binários gerados nesta rodada, se houver."""

    texto: str
    historico: list[MensagemConversa] = field(default_factory=list)
    arquivos_gerados: list[ArquivoGerado] = field(default_factory=list)
