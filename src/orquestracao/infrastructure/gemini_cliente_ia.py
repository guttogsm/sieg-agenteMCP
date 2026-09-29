"""Implementação de ClienteIAPort usando a Gemini API (Google), via
`client.models.generate_content` — a API síncrona/stateless "legada" (nos
termos do próprio Google), não a Interactions API mais nova.

Escolha deliberada: `generate_content` replica o mesmo modelo de estado da
Messages API da Anthropic (histórico completo reenviado a cada chamada,
sem sessão guardada no servidor) — por isso este adapter encaixa em
ClienteIAPort e em ResponderMensagem sem exigir nenhuma mudança ali. A
Interactions API do Gemini (`client.interactions.create`, com
`previous_interaction_id`) é stateful e teria contrato incompatível com o
resto do sistema; não foi usada aqui por esse motivo, não por
desconhecimento dela.

Único lugar do sistema que conhece o formato de wire do Gemini —
domain/ e application/ só enxergam MensagemConversa/RespostaIA/
ChamadaFerramenta (ver domain/value_objects.py), mesmo contrato que
ClaudeClienteIA implementa. Trocar de provedor de IA é só isso: escrever
outro adapter que implemente ClienteIAPort.

Verificado nesta sessão (22-23/09/2026), sem chave real (o sandbox de
nuvem não tem saída de rede liberada para generativelanguage.googleapis.com):
- pacote `google-genai==2.25.0` instalado e importado com sucesso;
- assinaturas reais de `types.Part.from_text/from_function_call/
  from_function_response`, `types.FunctionDeclaration`, `types.Tool`,
  `types.GenerateContentConfig`, `types.Content` e
  `Client.models.generate_content` inspecionadas diretamente no pacote
  instalado (não assumidas via documentação);
- modelo `gemini-3.8-flash` confirmado como GA (não preview) e com suporte
  a function calling via `generate_content`, checando a página oficial do
  modelo (ai.google.dev/gemini-api/docs/models/gemini-3.8-flash).
CONFIRMADO contra a API real (23/09/2026, testado pelo Guto): o modelo
`gemini-3.8-flash` (e presumivelmente os demais da linha 3.x — modelos
"thinking") exige que toda `function_call` devolvida numa resposta seja
reenviada no histórico do turno seguinte carregando de volta a mesma
`thought_signature` opaca (bytes) que veio junto dela — sem isso a API
responde HTTP 400 INVALID_ARGUMENT ("Function call is missing a
thought_signature..."). Isso não é documentado no schema estático do SDK
(o campo existe em `types.Part` mas nada indica que é obrigatório pra
tool use) — só apareceu rodando de verdade, exatamente o tipo de detalhe
que a regra do projeto de "nunca assumir formato sem testar contra dado
real" existe pra pegar. `_dict_para_part`/`_para_resposta_ia` abaixo
carregam essa assinatura (serializada em base64 dentro do bloco bruto,
já que é `bytes`) de ida e volta.

PROMPT/CONTEXT CACHING: diferente da Anthropic (marcação inline com
`cache_control`), o Gemini cacheia por recurso — `client.caches.create(...)`
cria um `CachedContent` guardado no servidor do Google, e chamadas
seguintes referenciam esse recurso por nome
(`GenerateContentConfig.cached_content=<nome>`) em vez de reenviar
system_instruction/tools toda hora. Criado uma vez (lazy, na primeira
chamada de `perguntar`) e reusado pelo resto da vida da instância, já que
system_instruction e o catálogo de ferramentas não mudam durante a sessão
do processo.

NÃO TESTADO CONTRA A API REAL (o sandbox de nuvem não alcança
generativelanguage.googleapis.com — ver nota acima). Dois riscos
conhecidos e não verificados aqui, por isso a criação do cache é
best-effort com fallback: (1) o Gemini historicamente exige um mínimo de
tokens no conteúdo cacheado (na época da API v1, 32768 tokens pro
Flash) — o nosso system prompt + catálogo de ferramentas pode não bater
esse mínimo, o que faria `caches.create` falhar; (2) não está confirmado
se esse mínimo mudou ou se ainda vale pra geração 3.x. Se a criação do
cache falhar por QUALQUER motivo, `_cache` fica `None` e todo o resto do
adapter funciona exatamente como antes (sem cache, sem quebrar o chat) —
guto precisa confirmar com a chave real se o cache chega a ser criado ou
se cai sempre no fallback.

RETRY EM ERRO TRANSIENTE (24/09/2026): reproduzido em produção — pergunta
comum ("quero o PDF do CNPJ X número Y de tal data") estourou com
`503 UNAVAILABLE — This model is currently experiencing high demand` e
subiu cru pro usuário via app.py ("Erro inesperado no agente: ..."), sem
nenhuma tentativa de novo. CONFIRMADO lendo o código-fonte do
`google-genai==2.25.0` instalado (`_api_client.py::retry_args`, não
documentado assim no guia da API): por padrão `Client(...)` NÃO faz
retry nenhum (`http_options.retry_options=None` vira
`stop_after_attempt(1)`) — é preciso passar
`http_options=types.HttpOptions(retry_options=types.HttpRetryOptions(...))`
explicitamente. Com isso, o próprio SDK já trata como retryable os
códigos 408/429/500/502/503/504 (config padrão do SDK, não escrita à
mão aqui) — cobre exatamente o 503 acima e também 429 RESOURCE_EXHAUSTED
(comum no tier gratuito). Attempts/delays abaixo foram encurtados dos
padrões do SDK (5 tentativas, até 60s de espera) porque aqui é dentro de
um request HTTP síncrono do Flask com o usuário esperando na tela —
4 tentativas / até 8s de espera cobre um pico passageiro sem travar o
chat por muito tempo. NÃO TESTADO contra a API real nesta sessão (mesma
limitação de rede do resto do arquivo) — guto precisa confirmar que um
503 real agora se resolve sozinho em vez de aparecer pro usuário.
"""
from __future__ import annotations

import base64
import logging

from google import genai
from google.genai import types

from ..domain.value_objects import ChamadaFerramenta, MensagemConversa, RespostaIA

_logger = logging.getLogger(__name__)

_TTL_CACHE_PADRAO = "3600s"  # 1h — mesmo teto usado no lado Claude (ttl="1h")

# Ver nota de módulo "RETRY EM ERRO TRANSIENTE": sem isso, Client(...) não
# tenta de novo em erro transiente nenhum (503, 429) — sobe cru pro chat.
_RETRY_TENTATIVAS = 4
_RETRY_ATRASO_INICIAL_S = 1.0
_RETRY_ATRASO_MAXIMO_S = 8.0


class GeminiClienteIA:
    def __init__(
        self,
        api_key: str,
        modelo: str,
        prompt_sistema: str,
        max_tokens: int = 8192,
    ):
        self._client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                retry_options=types.HttpRetryOptions(
                    attempts=_RETRY_TENTATIVAS,
                    initial_delay=_RETRY_ATRASO_INICIAL_S,
                    max_delay=_RETRY_ATRASO_MAXIMO_S,
                )
            ),
        )
        self._modelo = modelo
        self._prompt_sistema = prompt_sistema
        self._max_tokens = max_tokens
        # Cache é criado sob demanda na 1ª chamada (precisa do catálogo de
        # ferramentas, que só chega em perguntar(), não no __init__).
        # None = ainda não tentou OU tentou e falhou (best-effort, ver nota
        # de módulo) — nos dois casos perguntar() segue sem cache.
        self._cache_nome: str | None = None
        self._cache_tentado = False

    def perguntar(self, mensagens: list[MensagemConversa], ferramentas: list[dict]) -> RespostaIA:
        if not self._cache_tentado:
            self._cache_nome = self._criar_cache_se_possivel(ferramentas)
            self._cache_tentado = True

        if self._cache_nome:
            # Cache já carrega system_instruction e tools no servidor — não
            # reenvia nenhum dos dois aqui, só referencia o recurso.
            config = types.GenerateContentConfig(
                max_output_tokens=self._max_tokens,
                cached_content=self._cache_nome,
            )
        else:
            config = types.GenerateContentConfig(
                system_instruction=self._prompt_sistema,
                max_output_tokens=self._max_tokens,
                tools=[self._ferramentas_para_tool(ferramentas)] if ferramentas else None,
            )

        resposta = self._client.models.generate_content(
            model=self._modelo,
            contents=[self._para_content_api(m) for m in mensagens],
            config=config,
        )
        return self._para_resposta_ia(resposta)

    # --- infraestrutura interna ---

    def _criar_cache_se_possivel(self, ferramentas: list[dict]) -> str | None:
        # Best-effort de propósito (ver nota de módulo): o mínimo de tokens
        # exigido pelo Gemini pra aceitar um cache não está confirmado nesta
        # sessão (sem acesso de rede à API real), e um system prompt +
        # catálogo de ferramentas pequeno pode não bater esse mínimo. Se
        # falhar por isso ou qualquer outro motivo (rede, quota, campo
        # incompatível), loga e segue sem cache — nunca deixa a falha de
        # cache derrubar o chat.
        try:
            config = types.CreateCachedContentConfig(
                display_name="sieg-agente-system-tools",
                system_instruction=self._prompt_sistema,
                tools=[self._ferramentas_para_tool(ferramentas)] if ferramentas else None,
                ttl=_TTL_CACHE_PADRAO,
            )
            cache = self._client.caches.create(model=self._modelo, config=config)
            _logger.info(
                "Cache do Gemini criado: %s (expira %s)", cache.name, cache.expire_time
            )
            return cache.name
        except Exception:
            _logger.warning(
                "Não foi possível criar cache do Gemini (provavelmente conteúdo "
                "abaixo do mínimo de tokens exigido, ou rede) — seguindo sem "
                "cache neste provedor.",
                exc_info=True,
            )
            return None

    @staticmethod
    def _ferramentas_para_tool(ferramentas: list[dict]) -> types.Tool:
        # Formato de tool da Messages API (Anthropic) e o `input_schema`
        # aqui usado já são JSON Schema puro — só muda o nome da chave
        # (`input_schema` -> `parameters_json_schema`); nenhuma reescrita
        # de schema é necessária.
        return types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name=f["name"],
                    description=f.get("description", ""),
                    parameters_json_schema=f.get(
                        "input_schema", {"type": "object", "properties": {}}
                    ),
                )
                for f in ferramentas
            ]
        )

    def _para_content_api(self, m: MensagemConversa) -> types.Content:
        if m.papel == "usuario":
            return types.Content(role="user", parts=[types.Part.from_text(text=m.conteudo)])
        if m.papel == "agente":
            # conteudo é a lista de blocos (dicts) devolvida por
            # _para_resposta_ia no turno anterior — reconstruída como Part.
            return types.Content(
                role="model", parts=[self._dict_para_part(bloco) for bloco in m.conteudo]
            )
        if m.papel == "tool_resultado":
            # conteudo é list[tuple[ChamadaFerramenta, ResultadoFerramenta]]
            # (ver ResponderMensagem.executar). O Gemini não tem um id de
            # chamada equivalente ao tool_use_id da Anthropic — a
            # correspondência é por nome/ordem dentro do turno, então cada
            # resultado vira um Part de function_response nomeado.
            partes = [
                types.Part.from_function_response(
                    name=chamada.nome,
                    response={"resultado": resultado.conteudo, "sucesso": resultado.sucesso},
                )
                for chamada, resultado in m.conteudo
            ]
            return types.Content(role="user", parts=partes)
        raise ValueError(f"Papel de mensagem desconhecido: {m.papel!r}")

    @staticmethod
    def _dict_para_part(bloco: dict) -> types.Part:
        if bloco["type"] == "text":
            return types.Part.from_text(text=bloco["text"])
        if bloco["type"] == "function_call":
            parte = types.Part.from_function_call(name=bloco["name"], args=bloco["args"])
            # Reenvia a thought_signature de volta pro Gemini — obrigatória
            # nos modelos 3.x pra tool use funcionar (ver nota no topo do
            # arquivo). `from_function_call` não aceita esse campo direto,
            # então é setado depois; `Part` permite atribuição normal.
            assinatura = bloco.get("thought_signature")
            if assinatura:
                parte.thought_signature = base64.b64decode(assinatura)
            return parte
        raise ValueError(f"Tipo de bloco desconhecido: {bloco['type']!r}")

    @classmethod
    def _para_resposta_ia(cls, resposta: types.GenerateContentResponse) -> RespostaIA:
        texto_partes: list[str] = []
        chamadas: list[ChamadaFerramenta] = []
        blocos_brutos: list[dict] = []

        candidato = resposta.candidates[0]
        for part in candidato.content.parts or []:
            if part.text:
                texto_partes.append(part.text)
                blocos_brutos.append({"type": "text", "text": part.text})
            elif part.function_call:
                fc = part.function_call
                argumentos = dict(fc.args or {})
                # Sem id nativo no Gemini — usa o próprio nome da
                # ferramenta como id (ver nota acima sobre correspondência
                # por nome/ordem; não é usado como chave de cache em
                # nenhum lugar do sistema, só circula dentro do turno).
                chamadas.append(
                    ChamadaFerramenta(id=fc.name or "", nome=fc.name or "", argumentos=argumentos)
                )
                bloco = {"type": "function_call", "name": fc.name, "args": argumentos}
                # thought_signature vem em bytes — serializada em base64 pra
                # caber no bloco bruto (dict JSON-friendly, ver ClaudeClienteIA
                # pro mesmo padrão de "bloco bruto"). Sem isso, o próximo
                # turno que reenviar essa function_call é rejeitado com
                # HTTP 400 pelos modelos 3.x (ver nota no topo do arquivo).
                if part.thought_signature:
                    bloco["thought_signature"] = base64.b64encode(part.thought_signature).decode()
                blocos_brutos.append(bloco)

        return RespostaIA(
            texto="\n".join(texto_partes) if texto_partes else None,
            chamadas_ferramenta=chamadas,
            finalizada=len(chamadas) == 0,
            mensagem_bruta=blocos_brutos,
        )
