"""Composição de dependências do Agente SIEG — a borda do sistema, onde
infraestrutura concreta é criada e injetada nos casos de uso através das
portas. Mesmo padrão já estabelecido em composicao_exemplo.py (que cobria
só Certificados); aqui estendido pra todos os 4 bounded contexts mais a
Orquestração/Agente que os une.

Nada em domain/ ou application/ de nenhum contexto aparece aqui por
acidente — só os gateways/clientes concretos, que são os únicos que
conhecem HTTP/JWT/API Key/Claude.
"""
from __future__ import annotations

import os

from certificados.application.use_cases.consultar_status_certificado import (
    ConsultarStatusCertificado,
)
from certificados.application.use_cases.deletar_certificado import DeletarCertificado
from certificados.application.use_cases.desabilitar_certificado import DesabilitarCertificado
from certificados.application.use_cases.habilitar_certificado import HabilitarCertificado
from certificados.application.use_cases.listar_certificados import ListarCertificados
from certificados.application.use_cases.resumir_certificados_por_vencimento import (
    ResumirCertificadosPorVencimento,
)
from certificados.infrastructure.sieg_certificado_gateway import SiegCertificadoGateway

from documentos_auxiliares.application.use_cases.gerar_dacte_via_chave import GerarDacteViaChave
from documentos_auxiliares.application.use_cases.gerar_dacte_via_xml import GerarDacteViaXml
from documentos_auxiliares.application.use_cases.gerar_danfce_via_xml import GerarDanfceViaXml
from documentos_auxiliares.application.use_cases.gerar_danfe_via_chave import GerarDanfeViaChave
from documentos_auxiliares.application.use_cases.gerar_danfe_via_xml import GerarDanfeViaXml
from documentos_auxiliares.application.use_cases.gerar_danfse_via_chave import (
    GerarDanfseViaChave,
)
from documentos_auxiliares.application.use_cases.gerar_danfse_via_xml import GerarDanfseViaXml
from documentos_auxiliares.infrastructure.node_gerador_pdf_local import (
    NodeGeradorPdfLocalAdapter,
)
from documentos_auxiliares.infrastructure.sieg_documento_auxiliar_gateway import (
    SiegDocumentoAuxiliarGateway,
)

from documentos_fiscais.application.use_cases.baixar_xml_especifico import BaixarXmlEspecifico
from documentos_fiscais.application.use_cases.baixar_xmls_em_lote import BaixarXmlsEmLote
from documentos_fiscais.infrastructure.sieg_documento_fiscal_gateway import (
    SiegDocumentoFiscalGateway,
)

from relatorios.application.use_cases.gerar_relatorio_xml import GerarRelatorioXml
from relatorios.infrastructure.sieg_relatorio_gateway import SiegRelatorioGateway

from shared.infrastructure.auth.sieg_jwt_provider import SiegJwtProvider
from shared.infrastructure.sieg_http_client import SiegHttpClient

from orquestracao.application.use_cases.responder_mensagem import ResponderMensagem
from orquestracao.infrastructure.auditoria.logger_auditoria_arquivo import LoggerAuditoriaArquivo
from orquestracao.infrastructure.claude_cliente_ia import ClaudeClienteIA
from orquestracao.infrastructure.gemini_cliente_ia import GeminiClienteIA
from orquestracao.infrastructure.ferramentas.definicoes import FERRAMENTAS
from orquestracao.infrastructure.ferramentas.executor_ferramentas_sieg import (
    ExecutorFerramentasSieg,
)
from orquestracao.infrastructure.prompt_sistema import montar_prompt_sistema


def montar_http_sieg() -> SiegHttpClient:
    base_url = os.environ.get("SIEG_BASE_URL", "https://api.sieg.com")
    token_provider = SiegJwtProvider(
        base_url=base_url,
        client_id=os.environ["SIEG_CLIENT_ID"],
        secret_key=os.environ["SIEG_SECRET_KEY"],
    )
    return SiegHttpClient(
        base_url=base_url,
        token_provider=token_provider,
        chave_leitura=os.environ["SIEG_API_KEY_LEITURA"],
        chave_escrita=os.environ["SIEG_API_KEY_ESCRITA"],
    )


def montar_cliente_ia():
    # SIEG_AGENTE_PROVEDOR_IA escolhe o adapter de IA sem tocar em mais
    # nada do sistema — é exatamente pra isso que ClienteIAPort existe.
    # "claude" é o padrão porque é o único testado ponta a ponta até agora;
    # "gemini" existe pra quem não tem (ainda) uma ANTHROPIC_API_KEY paga.
    provedor = os.environ.get("SIEG_AGENTE_PROVEDOR_IA", "claude").strip().lower()
    prompt_sistema = montar_prompt_sistema()

    if provedor == "claude":
        return ClaudeClienteIA(
            api_key=os.environ["ANTHROPIC_API_KEY"],
            modelo=os.environ.get("SIEG_AGENTE_MODELO", "claude-sonnet-4-5-20250929"),
            prompt_sistema=prompt_sistema,
        )
    if provedor == "gemini":
        return GeminiClienteIA(
            api_key=os.environ["GEMINI_API_KEY"],
            modelo=os.environ.get("SIEG_AGENTE_MODELO", "gemini-3.8-flash"),
            prompt_sistema=prompt_sistema,
        )
    raise ValueError(
        f"SIEG_AGENTE_PROVEDOR_IA={provedor!r} desconhecido — use 'claude' ou 'gemini'."
    )


def montar_responder_mensagem(diretorio_arquivos_gerados: str, diretorio_logs: str) -> ResponderMensagem:
    http = montar_http_sieg()

    gateway_certificados = SiegCertificadoGateway(http)
    gateway_documentos_fiscais = SiegDocumentoFiscalGateway(http)
    gateway_documentos_auxiliares = SiegDocumentoAuxiliarGateway(http)
    gateway_relatorios = SiegRelatorioGateway(http)
    # NFC-e não tem rota de geração de PDF na API SIEG — geração local via
    # Node.js, reaproveitando o motor da extensão Chrome de DANFE do
    # usuário (ver documentos_auxiliares/infrastructure/node_gerador_pdf_local.py
    # e gerador_pdf_local/gerar_danfce.js). SIEG_AGENTE_NODE_EXECUTAVEL
    # permite apontar pra um binário node específico se "node" não estiver
    # no PATH do processo do app.py.
    gerador_pdf_local = NodeGeradorPdfLocalAdapter(
        node_executavel=os.environ.get("SIEG_AGENTE_NODE_EXECUTAVEL", "node"),
    )

    executor_ferramentas = ExecutorFerramentasSieg(
        listar_certificados=ListarCertificados(gateway_certificados),
        resumir_certificados_por_vencimento=ResumirCertificadosPorVencimento(gateway_certificados),
        consultar_status_certificado=ConsultarStatusCertificado(gateway_certificados),
        habilitar_certificado=HabilitarCertificado(gateway_certificados),
        desabilitar_certificado=DesabilitarCertificado(gateway_certificados),
        deletar_certificado=DeletarCertificado(gateway_certificados),
        baixar_xml_especifico=BaixarXmlEspecifico(gateway_documentos_fiscais),
        baixar_xmls_em_lote=BaixarXmlsEmLote(gateway_documentos_fiscais),
        gerar_danfe_via_chave=GerarDanfeViaChave(gateway_documentos_auxiliares),
        gerar_danfe_via_xml=GerarDanfeViaXml(gateway_documentos_auxiliares),
        gerar_dacte_via_chave=GerarDacteViaChave(gateway_documentos_auxiliares),
        gerar_dacte_via_xml=GerarDacteViaXml(gateway_documentos_auxiliares),
        gerar_danfse_via_chave=GerarDanfseViaChave(gateway_documentos_auxiliares),
        gerar_danfse_via_xml=GerarDanfseViaXml(gateway_documentos_auxiliares),
        gerar_danfce_via_xml=GerarDanfceViaXml(gerador_pdf_local),
        gerar_relatorio_xml=GerarRelatorioXml(gateway_relatorios),
        diretorio_arquivos_gerados=diretorio_arquivos_gerados,
    )

    cliente_ia = montar_cliente_ia()

    audit_logger = LoggerAuditoriaArquivo(os.path.join(diretorio_logs, "auditoria_agente.jsonl"))

    return ResponderMensagem(
        cliente_ia=cliente_ia,
        executor_ferramentas=executor_ferramentas,
        ferramentas=FERRAMENTAS,
        audit_logger=audit_logger,
    )
