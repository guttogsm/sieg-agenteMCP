"""Política de confirmação para ações destrutivas.

Regra do projeto (ver instruções): "Ações destrutivas (desabilitar/deletar
certificado) exigem confirmação explícita antes de executar." Nada mais no
catálogo de ferramentas de hoje é destrutivo o suficiente pra exigir isso —
habilitar é reversível (o próprio desabilitar desfaz), e downloads/geração
de PDF/relatório são só leitura.

Desenho: em vez de a política tentar interpretar a linguagem natural da
conversa pra decidir se o usuário "já confirmou", cada ferramenta sensível
declara um parâmetro `confirmado: bool` no próprio schema (ver
infrastructure/ferramentas/definicoes.py), com uma descrição que instrui a
Claude a só marcar True depois de uma confirmação explícita do usuário no
turno anterior. Esta política então só faz a checagem mecânica — sem essa
flag True, a ferramenta nunca executa, ponto único e determinístico onde a
regra é aplicada de verdade (não depende da Claude "se comportar bem" sem
verificação — ver ExecutorFerramentasSieg.executar).
"""
from __future__ import annotations

FERRAMENTAS_DESTRUTIVAS = frozenset({"desabilitar_certificado", "deletar_certificado"})


class PoliticaConfirmacao:
    @staticmethod
    def exige_confirmacao(nome_ferramenta: str) -> bool:
        return nome_ferramenta in FERRAMENTAS_DESTRUTIVAS

    @staticmethod
    def foi_confirmado(argumentos: dict) -> bool:
        return bool(argumentos.get("confirmado", False))

    @staticmethod
    def mensagem_pedido_confirmacao(nome_ferramenta: str, argumentos: dict) -> str:
        """Devolvida como tool_result quando a Claude chama uma ferramenta
        destrutiva sem confirmado=True — instrui a própria Claude a parar e
        perguntar ao usuário, em vez de silenciosamente tentar de novo."""
        alvo = argumentos.get("certificado_id", "?")
        return (
            f"AÇÃO BLOQUEADA: '{nome_ferramenta}' (certificado_id={alvo}) é uma ação "
            "destrutiva e exige confirmação explícita do usuário antes de executar. "
            "NÃO execute de novo automaticamente. Pergunte ao usuário se ele confirma "
            "essa ação, em português, deixando claro o que vai acontecer. Só chame "
            "esta ferramenta de novo, com confirmado=true, depois de uma resposta "
            "afirmativa explícita do usuário nesta conversa."
        )
