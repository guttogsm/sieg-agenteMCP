"""Adapter que gera DANFCE (NFC-e, modelo 65) localmente via subprocesso
Node.js — a API SIEG não tem rota de geração de PDF pra NFC-e (só Danfe/
Dacte/Danfse, confirmado no Swagger "engine" real; ver
sieg_documento_auxiliar_gateway.py), então esta é a única forma de entregar
esse PDF ao usuário.

O script Node (gerador_pdf_local/gerar_danfce.js) reaproveita, sem alterar
a lógica, o motor de renderização já testado na extensão Chrome
"Documentos Fiscais" do próprio Guto (nfce-dados.js/nfce-pdf.js,
vendorizados em gerador_pdf_local/lib_extensao/) — a mesma DANFCE que ele
já gera manualmente pelo hub, só que chamada pelo agente.

PRÉ-REQUISITOS na máquina onde app.py roda:
  1. Node.js instalado (qualquer LTS recente) e no PATH como `node`.
  2. `npm install` executado uma vez dentro de
     documentos_auxiliares/infrastructure/gerador_pdf_local/ (instala a
     dependência `linkedom`, usada só pra ter um DOMParser compatível com
     querySelector em Node — o mesmo código do XML/PDF da extensão não
     precisa de nenhuma outra mudança).

NÃO CONFIRMADO ainda contra um XML real de NFC-e do Guto (só validado
nesta sessão contra um XML real de NF-e, pra provar que o pipeline
Node/linkedom/jsPDF funciona) — pendente de teste real antes de considerar
fechado (mesma disciplina de todo o resto deste projeto).
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
import tempfile

from ..domain.exceptions import DocumentoAuxiliarRequisicaoInvalidaError
from ..domain.value_objects import ResultadoPdf


class TipoDocumentoIncompativelError(DocumentoAuxiliarRequisicaoInvalidaError):
    """O XML fornecido não é de NFC-e (campo <ide><mod> != 65) — erro
    específico (mas ainda um DocumentoAuxiliarRequisicaoInvalidaError, pra
    caber no mesmo tratamento genérico do executor) pra quem chama poder
    distinguir "documento errado" de qualquer outra falha de geração."""

    def __init__(self, mod_detectado: str | None):
        self.mod_detectado = mod_detectado
        super().__init__(
            [f"XML não é de NFC-e (campo mod detectado: {mod_detectado or 'desconhecido'})."]
        )


class NodeGeradorPdfLocalAdapter:
    def __init__(self, *, node_executavel: str = "node", timeout_segundos: float = 30.0):
        self._node = node_executavel
        self._timeout = timeout_segundos
        self._script = os.path.join(
            os.path.dirname(__file__), "gerador_pdf_local", "gerar_danfce.js"
        )

    def gerar_danfce_via_xml(self, xml_bytes: bytes) -> ResultadoPdf:
        with tempfile.TemporaryDirectory() as tmp:
            caminho_xml = os.path.join(tmp, "entrada.xml")
            caminho_pdf = os.path.join(tmp, "saida.pdf")
            with open(caminho_xml, "wb") as f:
                f.write(xml_bytes)

            try:
                resultado = subprocess.run(
                    [self._node, self._script, caminho_xml, caminho_pdf],
                    capture_output=True,
                    timeout=self._timeout,
                    text=True,
                )
            except FileNotFoundError as exc:
                raise DocumentoAuxiliarRequisicaoInvalidaError(
                    [
                        "Node.js não encontrado nesta máquina (comando "
                        f"{self._node!r}) — instale o Node.js (LTS) pra gerar "
                        "PDF de NFC-e localmente."
                    ]
                ) from exc
            except subprocess.TimeoutExpired as exc:
                raise DocumentoAuxiliarRequisicaoInvalidaError(
                    ["Geração local do PDF de NFC-e demorou demais e foi cancelada."]
                ) from exc

            if resultado.returncode == 2:
                detalhe = self._parse_erro_stderr(resultado.stderr)
                mod = (detalhe or {}).get("modDetectado")
                raise TipoDocumentoIncompativelError(mod)
            if resultado.returncode != 0:
                detalhe = self._parse_erro_stderr(resultado.stderr)
                mensagem = (detalhe or {}).get("erro") or resultado.stderr.strip() or "erro desconhecido"
                raise DocumentoAuxiliarRequisicaoInvalidaError(
                    [f"Falha ao gerar DANFCE localmente: {mensagem}"]
                )

            with open(caminho_pdf, "rb") as f:
                pdf_bytes = f.read()

        return ResultadoPdf(conteudo_base64=base64.b64encode(pdf_bytes).decode("ascii"))

    @staticmethod
    def _parse_erro_stderr(stderr: str) -> dict | None:
        try:
            linha = (stderr or "").strip().splitlines()[-1]
            return json.loads(linha)
        except (ValueError, IndexError):
            return None
