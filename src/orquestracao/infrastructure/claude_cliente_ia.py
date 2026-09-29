"""Implementação de ClienteIAPort usando a Claude Messages API (tool use).

Único lugar do sistema que conhece o formato de wire da Anthropic —
domain/ e application/ só enxergam MensagemConversa/RespostaIA/
ChamadaFerramenta (ver domain/value_objects.py). Se um dia trocarmos de
provedor de IA, é só escrever outro adapter que implemente ClienteIAPort;
nada no resto do sistema muda.

PROMPT CACHING: system prompt e catálogo de ferramentas são idênticos em
toda chamada (só o histórico de mensagens cresce) — e dentro de uma única
pergunta do usuário, ResponderMensagem chama perguntar() várias vezes
seguidas (uma por iteração do loop de tool use, até MAX_ITERACOES). Marcar
cache_control nesses dois blocos deixa a Claude reaproveitar o
processamento já feito deles entre chamadas, em vez de reprocessar do
zero toda hora — reduz latência e custo, sem risco de resposta
desatualizada (não cacheia o RESULTADO, só a leitura do que não muda).
Campo `cache_control` confirmado estável (não-beta) no SDK `anthropic`
instalado (1.8.0) via inspeção direta dos tipos — não presumido da
documentação.
"""
from __future__ import annotations

import anthropic

from ..domain.value_objects import ChamadaFerramenta, MensagemConversa, RespostaIA

_CACHE_CONTROL = {"type": "ephemeral"}


class ClaudeClienteIA:
    def __init__(
        self,
        api_key: str,
        modelo: str,
        prompt_sistema: str,
        max_tokens: int = 8192,
    ):
        self._client = anthropic.Anthropic(api_key=api_key)
        self._modelo = modelo
        self._prompt_sistema = prompt_sistema
        self._max_tokens = max_tokens

    def perguntar(self, mensagens: list[MensagemConversa], ferramentas: list[dict]) -> RespostaIA:
        resposta = self._client.messages.create(
            model=self._modelo,
            max_tokens=self._max_tokens,
            system=[
                {"type": "text", "text": self._prompt_sistema, "cache_control": _CACHE_CONTROL}
            ],
            tools=self._ferramentas_com_cache(ferramentas),
            messages=[self._para_mensagem_api(m) for m in mensagens],
        )
        return self._para_resposta_ia(resposta)

    # --- infraestrutura interna ---

    @staticmethod
    def _ferramentas_com_cache(ferramentas: list[dict]) -> list[dict]:
        # Marca cache_control só na última ferramenta do catálogo — a API
        # cacheia tudo até (e incluindo) o bloco marcado, então isso cobre
        # o array de tools inteiro numa marcação só. Copia em vez de mutar
        # o dict original (FERRAMENTAS é módulo compartilhado, reusado em
        # toda chamada/sessão — mutar in-place vazaria cache_control pro
        # catálogo canônico).
        if not ferramentas:
            return ferramentas
        copia = list(ferramentas)
        copia[-1] = {**copia[-1], "cache_control": _CACHE_CONTROL}
        return copia

    def _para_mensagem_api(self, m: MensagemConversa) -> dict:
        if m.papel == "usuario":
            return {"role": "user", "content": m.conteudo}
        if m.papel == "agente":
            # conteudo já é a lista de content blocks (dicts) devolvida por
            # _para_resposta_ia no turno anterior — reenviada como está.
            return {"role": "assistant", "content": m.conteudo}
        if m.papel == "tool_resultado":
            # conteudo é list[tuple[ChamadaFerramenta, ResultadoFerramenta]]
            # (ver ResponderMensagem.executar) — vira um único content
            # block por ferramenta chamada, respondendo ao tool_use_id
            # correspondente.
            blocos = []
            for chamada, resultado in m.conteudo:
                bloco = {
                    "type": "tool_result",
                    "tool_use_id": chamada.id,
                    "content": resultado.conteudo,
                }
                if not resultado.sucesso:
                    bloco["is_error"] = True
                blocos.append(bloco)
            return {"role": "user", "content": blocos}
        raise ValueError(f"Papel de mensagem desconhecido: {m.papel!r}")

    @staticmethod
    def _bloco_para_dict(bloco) -> dict:
        # Conversão explícita pros dois tipos conhecidos, em vez de confiar
        # em bloco.model_dump() puro — CONFIRMADO (teste local, SDK 1.8.0)
        # que model_dump() inclui campos extras específicos do SDK (ex.:
        # "caller", "toolset_name" em ToolUseBlock, ambos None) que não
        # fazem parte do formato de request da Messages API; reenviar isso
        # como está é arriscar a API rejeitar campo desconhecido num
        # request futuro. Um tipo de bloco não previsto aqui (a API
        # acrescentou algo novo) cai no fallback de model_dump() mesmo —
        # melhor preservar com campos extras do que descartar silenciosamente.
        if bloco.type == "text":
            return {"type": "text", "text": bloco.text}
        if bloco.type == "tool_use":
            return {"type": "tool_use", "id": bloco.id, "name": bloco.name, "input": bloco.input}
        return bloco.model_dump()

    @classmethod
    def _para_resposta_ia(cls, resposta) -> RespostaIA:
        texto_partes: list[str] = []
        chamadas: list[ChamadaFerramenta] = []
        blocos_brutos: list[dict] = []

        for bloco in resposta.content:
            blocos_brutos.append(cls._bloco_para_dict(bloco))
            if bloco.type == "text":
                texto_partes.append(bloco.text)
            elif bloco.type == "tool_use":
                chamadas.append(
                    ChamadaFerramenta(id=bloco.id, nome=bloco.name, argumentos=bloco.input or {})
                )

        return RespostaIA(
            texto="\n".join(texto_partes) if texto_partes else None,
            chamadas_ferramenta=chamadas,
            finalizada=resposta.stop_reason != "tool_use",
            mensagem_bruta=blocos_brutos,
        )
