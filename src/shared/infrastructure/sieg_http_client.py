"""Cliente HTTP compartilhado por todos os gateways da API SIEG.

Centraliza os dois headers obrigatórios em toda chamada de negócio:
    Authorization: Bearer {jwt}
    X-API-Key: {chave da conta, com nível de acesso}

Nenhum gateway de contexto (Certificados, Documentos Fiscais, ...) deve
montar esses headers por conta própria — todos passam por aqui.

CONFIRMADO em teste real (18/09/2026): toda resposta de negócio vem
embrulhada em {"IsSuccess", "ErrorMessage", "StatusCode", "Data",
"IsFailure"} — o mesmo formato ResultApiGeneralObject documentado no
fluxo de OAuth, agora visto também em /api/v1/listar. Este cliente
desembrulha isso automaticamente: quem chama get/post/delete recebe
só o conteúdo de "Data", e uma falha lógica (IsSuccess=false) vira
SiegApiError — mesmo que o HTTP status tenha sido 200.

CORRIGIDO (22/09/2026): `_unwrap` crashava com um `JSONDecodeError` cru
(não capturado por nenhum gateway) quando a API respondia com HTTP
2xx/404 mas corpo não-vazio e não-JSON — visto em teste real no
BaixarXmlsEmLote (NFe, CNPJ sem XML no hub). Agora isso vira SiegApiError,
com o texto bruto no campo `corpo`, e passa pelo mesmo tratamento de
diagnóstico que todo o resto (cada gateway já sabe formatar SiegApiError).

CONFIRMADO em teste real (22/09/2026), achado maior: pelo menos
/api/v1/baixar-xmls (lote) devolve, quando encontra XMLs de verdade, um
arquivo ZIP binário puro como corpo da resposta — sem JSON, sem envelope
IsSuccess/Data nenhum. Isso é um SUCESSO, não um erro (era isso que o
"corpo não-JSON" acima capturava incorretamente como SiegApiError antes
desta correção). `_unwrap` agora reconhece a assinatura de arquivo ZIP e
devolve os bytes crus pra quem chamou, sem tentar (e falhar) fazer
json.loads() neles.

CONFIRMADO em teste real (22/09/2026): /api/v1/baixar-xmls (lote) aplica
rate limiting — HTTP 429 "Too Many Requests. Try again later." em chamadas
em sequência. Espaçar as chamadas manualmente no script de teste (5s entre
cada uma) ajudou mas não eliminou o 429 por completo (uma das seis
chamadas ainda tomou 429 mesmo com a pausa). Corrigido aqui, no ponto
único por onde toda chamada HTTP passa: retry automático com backoff
quando a resposta vem 429, respeitando o header Retry-After se a API
mandar um. Assim nenhum gateway/script precisa reimplementar essa lógica.

CONFIRMADO em teste real via chat (24/09/2026): `/api/v1/baixar-xmls`
(lote) pediu um mês inteiro de CT-e pra um CNPJ e estourou
`requests.exceptions.ReadTimeout` com o timeout fixo de 30s de antes —
subiu cru pro usuário ("Erro inesperado no agente: ... Read timed out"),
sem nenhuma tentativa de novo, porque `_executar_com_retry_429` só
tratava resposta HTTP 429 — uma exceção de timeout/conexão levantada
pelo próprio `requests.get/post/...` nem chegava a entrar no laço de
retry, subia direto. Mesma classe de problema do 429 (falha transiente de
rede/latência da API externa), então tratada com a mesma filosofia:
timeout subido de 30s pra 60s (uma consulta de lote grande pode
legitimamente demorar mais que 30s do lado da SIEG) e `Timeout`/
`ConnectionError` agora também entram no retry automático (2 tentativas
extras, 5s de espera) — se persistir mesmo assim, a exceção original
ainda sobe (não esconde um problema real de rede indefinidamente).
"""
from enum import Enum
from typing import Any

import requests
import time

from .auth.ports import TokenProviderPort


class SiegApiError(Exception):
    """A API respondeu com IsSuccess=false no corpo, mesmo com HTTP 200."""

    def __init__(
        self,
        mensagem: str,
        status_code: int | None = None,
        corpo: dict | None = None,
    ):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.status_code = status_code
        # Corpo bruto do envelope (IsSuccess/ErrorMessage/StatusCode/Data/...).
        # Guardado pra diagnóstico: em rotas como habilitar/desabilitar a API
        # frequentemente não preenche ErrorMessage, então qualquer campo
        # extra que venha aqui pode ser o único sinal disponível.
        self.corpo = corpo or {}


class NivelAcesso(Enum):
    """Nível de acesso da X-API-Key exigido pela chamada.

    Nota importante: em Minha Conta -> Integrações, a permissão "Apenas
    envio e escrita (sem leitura)" é literalmente write-only — uma chave
    nesse nível não consegue fazer GET. Por isso ESCRITA aqui é servida
    pela chave "Acesso total" (fullAccess), não por uma chave write-only:
    um caso de uso de edição pode precisar ler o estado atual antes de
    gravar, e uma chave write-only quebraria esse fluxo.
    """

    LEITURA = "leitura"
    ESCRITA = "escrita"


class SiegHttpClient:
    def __init__(
        self,
        base_url: str,
        token_provider: TokenProviderPort,
        chave_leitura: str,
        chave_escrita: str,
    ):
        self._base_url = base_url.rstrip("/")
        self._token_provider = token_provider
        self._chaves = {
            NivelAcesso.LEITURA: chave_leitura,
            NivelAcesso.ESCRITA: chave_escrita,
        }

    def _headers(self, nivel: NivelAcesso) -> dict:
        return {
            "Authorization": f"Bearer {self._token_provider.obter_jwt()}",
            "X-API-Key": self._chaves[nivel],
            "Content-Type": "application/json",
        }

    # Assinaturas de arquivo ZIP (local file header, central directory
    # vazio, data descriptor) — CONFIRMADO em teste real que pelo menos
    # /api/v1/baixar-xmls usa isso pra devolver XMLs de verdade direto no
    # corpo, sem envelope JSON nenhum.
    _ZIP_MAGIC_PREFIXES = (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")

    # CONFIRMADO em teste real (22/09/2026): rate limiting (HTTP 429) em
    # /api/v1/baixar-xmls. Backoff linear (15s, 30s, 45s) — respeita
    # Retry-After se a API mandar um, senao usa esses valores por padrao.
    _MAX_TENTATIVAS_429 = 3
    _ESPERA_BASE_429_SEGUNDOS = 15.0

    # Ver nota de módulo (24/09/2026) — timeout/conexão são falha
    # transiente igual ao 429, só que mais rara, daí menos tentativas e
    # espera mais curta (não vale a pena impor 15s+ de espera adicional
    # numa API que já demorou até o timeout de 60s só pra responder).
    _MAX_TENTATIVAS_TIMEOUT = 2
    _ESPERA_TIMEOUT_SEGUNDOS = 5.0

    def _executar_com_retry_429(self, fn) -> requests.Response:
        """Executa `fn` (uma chamada requests.get/post/...) tentando de novo
        automaticamente quando a resposta vem HTTP 429 "Too Many Requests"
        OU quando a própria chamada estoura timeout/erro de conexão (ver
        nota de módulo, 24/09/2026) — falhas transientes da API externa,
        não da nossa lógica.

        Ponto único por onde toda chamada HTTP passa (get/post/post_query/
        delete abaixo) — corrige isso pra todos os gateways de uma vez, sem
        cada um (ou cada script de teste) ter que reimplementar retry.
        """
        tentativa_429 = 0
        tentativa_timeout = 0
        while True:
            try:
                resp = fn()
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
                tentativa_timeout += 1
                if tentativa_timeout > self._MAX_TENTATIVAS_TIMEOUT:
                    raise
                time.sleep(self._ESPERA_TIMEOUT_SEGUNDOS)
                continue
            if resp.status_code != 429 or tentativa_429 >= self._MAX_TENTATIVAS_429:
                resp.raise_for_status()
                return resp
            tentativa_429 += 1
            espera = self._ESPERA_BASE_429_SEGUNDOS * tentativa_429
            retry_after = resp.headers.get("Retry-After")
            if retry_after:
                try:
                    espera = max(espera, float(retry_after))
                except ValueError:
                    pass
            time.sleep(espera)

    def _unwrap(self, resp: requests.Response) -> Any:
        if not resp.content:
            return None
        if any(resp.content.startswith(p) for p in self._ZIP_MAGIC_PREFIXES):
            # Conteúdo binário (ZIP) — não é JSON e não é erro; devolve os
            # bytes crus pra quem chamou decidir o que fazer (ex.: salvar
            # em disco, converter pra base64).
            return resp.content
        try:
            dados = resp.json()
        except ValueError as exc:
            # CONFIRMADO em teste real (22/09/2026): a API pode devolver
            # HTTP não-erro (ou um 404 tratado como "sem HTTPError" por
            # algum motivo) com corpo não-vazio e não-JSON — sem isso, um
            # JSONDecodeError cru vazava pra fora do gateway, sem passar
            # pelo tratamento de erro/diagnóstico padrão (cada gateway já
            # sabe formatar SiegApiError com o corpo bruto).
            raise SiegApiError(
                mensagem="Resposta da API não é JSON válido.",
                status_code=resp.status_code,
                corpo={"corpo_bruto_nao_json": resp.text[:500]},
            ) from exc
        if isinstance(dados, dict) and "IsSuccess" in dados:
            if not dados.get("IsSuccess", True):
                raise SiegApiError(
                    mensagem=dados.get("ErrorMessage") or "Erro ao processar requisição.",
                    status_code=dados.get("StatusCode"),
                    corpo=dados,
                )
            return dados.get("Data")
        return dados

    def get(self, path: str, nivel: NivelAcesso, params: dict | None = None) -> Any:
        resp = self._executar_com_retry_429(
            lambda: requests.get(
                f"{self._base_url}{path}", headers=self._headers(nivel), params=params, timeout=60
            )
        )
        return self._unwrap(resp)

    def post(self, path: str, nivel: NivelAcesso, payload: dict | None = None) -> Any:
        resp = self._executar_com_retry_429(
            lambda: requests.post(
                f"{self._base_url}{path}", headers=self._headers(nivel), json=payload, timeout=60
            )
        )
        return self._unwrap(resp)

    def post_query(self, path: str, nivel: NivelAcesso, params: dict) -> Any:
        """Para rotas como habilitar/desabilitar: POST sem corpo, id via query string."""
        resp = self._executar_com_retry_429(
            lambda: requests.post(
                f"{self._base_url}{path}", headers=self._headers(nivel), params=params, timeout=60
            )
        )
        return self._unwrap(resp)

    def delete(self, path: str, nivel: NivelAcesso, params: dict | None = None) -> Any:
        resp = self._executar_com_retry_429(
            lambda: requests.delete(
                f"{self._base_url}{path}", headers=self._headers(nivel), params=params, timeout=60
            )
        )
        return self._unwrap(resp)
