"""Caso de uso que resolve, em código, a classificação Vencido/À
Vencer/No Prazo dos certificados com monitoramento ativo desta conta —
em vez de pedir pra Claude enumerar e contar isso sozinha.

Por que isso existe: nesta base de código, mais de uma vez, o modelo
errou esse cálculo sobre uma lista de só ~26 itens — item duplicado ou
inventado pra fechar um total já dito, comparação de vencimento por hora
em vez de dia, total que não batia com o tamanho da própria lista
enumerada (ver sieg-agente-registro-sessao.docx, seção 36 e addenda).
Contar itens e comparar datas é determinístico e barato em Python — não
deveria depender do modelo acertar aritmética sobre texto.

Também resolve a paginação aqui, uma vez só, em vez de deixar isso a
cargo do prompt: CONFIRMADO (23/09/2026, debug_paginacao_certificados.py,
rodado direto contra a API real) que `active=True` termina de verdade
quando a página seguinte dá erro — não é um erro escondendo mais
certificados, é fim de listagem legítimo. `active=False`, por outro
lado, NÃO é usado aqui: devolve um volume muito maior do que os
certificados desta conta, com CNPJs que não pertencem a ela — não dá pra
confiar nele pra completar com os certificados de monitoramento
desligado (ver regra 8 do prompt_sistema.py). Por isso este resumo cobre
só `Ativo=True` e deixa isso explícito no resultado, em vez de fingir
que é o total de certificados da conta.
"""
from __future__ import annotations

from datetime import date

from ..ports import CertificadoGatewayPort
from ...domain.entities import CertificadoResumo, ResumoVencimentoCertificados
from ...domain.exceptions import CertificadoRequisicaoInvalidaError


class ResumirCertificadosPorVencimento:
    # Trava de sanidade contra loop infinito se a API mudar de
    # comportamento (ex.: parar de erroar e começar a repetir a última
    # página) — não é um limite esperado na prática (a conta de teste
    # real usada nesta investigação tinha só 26 certificados ativos).
    LIMITE_PAGINAS_SEGURANCA = 50

    def __init__(self, gateway: CertificadoGatewayPort):
        self._gateway = gateway

    def executar(self, data_referencia: date | None = None) -> ResumoVencimentoCertificados:
        hoje = data_referencia or date.today()
        todos: list[CertificadoResumo] = list(self._paginar_todos_ativos())

        vencidos: list[CertificadoResumo] = []
        a_vencer: list[CertificadoResumo] = []
        no_prazo: list[CertificadoResumo] = []
        for certificado in todos:
            situacao = certificado.situacao_vencimento(hoje)
            if situacao.name == "VENCIDO":
                vencidos.append(certificado)
            elif situacao.name == "A_VENCER":
                a_vencer.append(certificado)
            else:
                no_prazo.append(certificado)

        return ResumoVencimentoCertificados(
            data_referencia=hoje,
            total_com_monitoramento_ativo=len(todos),
            vencidos=vencidos,
            a_vencer=a_vencer,
            no_prazo=no_prazo,
        )

    def _paginar_todos_ativos(self):
        pagina = 0
        while pagina < self.LIMITE_PAGINAS_SEGURANCA:
            try:
                itens = self._gateway.listar(active=True, pagina=pagina)
            except CertificadoRequisicaoInvalidaError:
                # CONFIRMADO em teste real: pra active=True, esse erro na
                # página seguinte é fim de listagem de verdade, não um
                # erro escondendo mais dados (ver docstring do módulo).
                break
            if not itens:
                break
            yield from itens
            pagina += 1
