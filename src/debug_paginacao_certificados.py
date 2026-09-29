"""Script de diagnóstico pontual — NÃO faz parte do agente, é só pra
investigar ao vivo o comportamento real de paginação de /api/v1/listar
numa conta com mais certificados do que uma página sozinha cobre.

HISTÓRICO (não apagar, é o que já ficou confirmado até agora):
- 23/09/2026, 1ª rodada: conta com 41 certificados reais (confirmado por
  export do hub em Excel), mas listar_certificados com pagina=0 variava
  entre 13 e 18 resultados entre chamadas, e pagina=1 sempre voltava um
  erro genérico sem ErrorMessage nem StatusCode no corpo.
- 23/09/2026, 2ª rodada (este script, v1): rodando direto contra
  montar_http_sieg() (sem passar pelo agente), active=True/pagina=0
  devolveu 26 itens de forma limpa e determinística, e pagina=1 em diante
  devolveu um requests.HTTPError 404 de verdade (não um SiegApiError com
  corpo — ou seja, é a própria infraestrutura HTTP recusando a URL, não a
  API respondendo IsSuccess=false). Isso indica que active=True realmente
  não tem página 1 — não é um erro escondendo mais dados.
  active=False, por outro lado, devolveu 100 itens já na página 0, e mais
  100 na página 1, sem esgotar em 3 páginas testadas (300+ itens) — muito
  mais do que os 41 certificados desta conta, e com nomes/CNPJs que não
  batem com nenhum dos 41 confirmados no export do hub. Ou seja,
  active=False parece devolver um universo BEM mais amplo do que "os
  certificados desativados desta conta" — não dá pra confiar nele pra
  completar o total.

O QUE ESTE SCRIPT (v2) FAZ A MAIS: imprime a lista COMPLETA dos itens de
active=True/pagina=0 (não só primeiro/último) e já compara automaticamente
contra os 41 CNPJs confirmados no export "Todos" do hub (23/09/2026) — pra
descobrir exatamente QUAIS certificados aparecem em active=True e quais
ficam de fora (a hipótese é que os que ficam de fora são os que estão com
`Ativo=False`, ou seja, com o monitoramento desligado — ver regra 7 do
prompt_sistema.py). Em especial, queremos saber se os 3 certificados que
"sumiram" numa resposta anterior do agente (Teste MG (cards), teste bug
MG, Teste card mg 2) estão dentro ou fora de active=True.

Roda igual aos outros scripts de teste do projeto (testar_v3.py,
testar_status_habilitar_desabilitar.py etc.):

    cd src
    python debug_paginacao_certificados.py
"""
from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()

from app_factory import montar_http_sieg  # noqa: E402 (depois do load_dotenv de propósito)
from shared.infrastructure.sieg_http_client import NivelAcesso, SiegApiError  # noqa: E402


# Os 41 certificados confirmados no export "Todos" do hub em 23/09/2026
# (planilha Excel que o Guto exportou) — CNPJ/CPF, Status do hub e Nome.
CERTIFICADOS_HUB_23_09_2026 = [
    ("20947407000138", "No Prazo", "SIEG SOLUCOES INTELIGENTES LTDA"),
    ("24201527000142", "Vencido", "Sefaz RN - teste 2"),
    ("32848559000162", "Vencido", "SUPERMERCADOS FACHINI LTDA"),
    ("02310194000238", "No Prazo", "SUPERMERCADO SAO FRANCISCO DE MARILIA LTDA"),
    ("67888032000146", "Vencido", "SUPERMERCADO SAO JUDAS"),
    ("02310194000157", "Vencido", "SUPERMERCADO SAO FRANCISCO DE MARILIA LTDA"),
    ("21095439000115", "À Vencer", "Empire Power"),
    ("07144980000145", "No Prazo", "T DO NASCIMENTO E CIA LTDA"),
    ("33726770000175", "Vencido", "MACHADO SUPERMERCADOS LTDA"),
    ("32324444000179", "À Vencer", "AEC.RICNPJ da empresa *O INTELIGENCIA CONTABIL LTDA"),
    ("41468090100", "Vencido", "test"),
    ("97470314000190", "Vencido", "test-CENTERLUCAS"),
    ("62307822000177", "Vencido", "test-500-error"),
    ("10854771000108", "Vencido", "test-500-2"),
    ("10838110000180", "Vencido", "test-500-3"),
    ("02100263000106", "Vencido", "test-nfse"),
    ("15556601000152", "Vencido", "A10 DISTRIBUIDORA DE MOVEIS LTDA"),
    ("40492478000109", "No Prazo", "test certificado admin"),
    ("34255087000160", "Vencido", "JOSE EDSON SCARDUELI"),
    ("17083305000107", "Vencido", "B E P COMERCIO DE PRODUTOS IMPORTADOS LTDA"),
    ("05992969000100", "Vencido", "ILHABELA SHOPPING DA CONSTRUCAO LTDA"),
    ("55925793000141", "Vencido", "Teste Eltton RS"),
    ("07792269000105", "Vencido", "CONSTRUTORA LYTORANEA LTDA - EM RECUPERACAO JUDICIAL"),
    ("40613458000130", "Vencido", "Usina Steak"),
    ("61578022000128", "Vencido", "FREEMADE COMERCIO DE MADEIRAS LTDA"),
    ("03672173000144", "Vencido", "Teste MG (cards)"),
    ("37636249000106", "Vencido", "teste bug MG"),
    ("47251972000112", "Vencido", "Teste card mg 2"),
    ("39625641000177", "No Prazo", "EMPRETESTE"),
    ("13952851000186", "No Prazo", "CHASSI MONOBLOCO LTDA"),
    ("12317258000103", "Vencido", "CLINICA OFTALMOLOGICA DR. ALESSANDRO PERUSSI LTDA"),
    ("42221436000150", "À Vencer", "TRES IRMAOS CENTRO COMERCIAL DE LUBRIFICACAO E SE"),
    ("51901207000178", "No Prazo", "COLEGIO IDEAL E VESTIBULARES LTDA"),
    ("07937141000184", "No Prazo", "ENURE CONSULTORIA CONTABIL LTDA"),
    ("15132425000121", "À Vencer", "ESPACO GASTRONOMICO IMPORTADORA LTDA"),
    ("95640789620", "No Prazo", "LUANY CRISTINA MORAIS GARCIA"),
    ("27553264000129", "No Prazo", "CLEBER ROGERIO MARTINS"),
    ("59142032000174", "No Prazo", "TESTE MA"),
    ("05389782000116", "No Prazo", "PADARIA PRIMAVERA LTDA"),
    ("44168156000151", "No Prazo", "TESTE BA"),
    ("48952373000199", "À Vencer", "MC DOC SERVICOS MEDICOS LTDA"),
]


def _tentar(http, *, active: bool, pagina: int, listar_tudo: bool = False):
    print(f"--- active={active} pagina={pagina} ---")
    try:
        dados = http.get(
            "/api/v1/listar", NivelAcesso.LEITURA, params={"active": active, "pagina": pagina}
        )
        qtd = len(dados) if isinstance(dados, list) else "N/A (não é lista)"
        print(f"  OK — itens devolvidos: {qtd}")
        if isinstance(dados, list) and dados:
            if listar_tudo:
                for item in dados:
                    print(f"    {item.get('CnpjCpf')} | Ativo={item.get('Ativo')} | {item.get('Nome')}")
            else:
                print(f"  primeiro: {dados[0].get('Nome')} | {dados[0].get('CnpjCpf')}")
                print(f"  último:   {dados[-1].get('Nome')} | {dados[-1].get('CnpjCpf')}")
        print()
        return dados if isinstance(dados, list) else []
    except SiegApiError as exc:
        print(f"  SiegApiError — mensagem={exc.mensagem!r} status_code={exc.status_code!r}")
        print(f"  corpo bruto completo: {exc.corpo!r}")
        print()
        return []
    except Exception as exc:  # noqa: BLE001 — script de diagnóstico, queremos ver tudo
        print(f"  {type(exc).__name__}: {exc}")
        print()
        return []


def main() -> None:
    http = montar_http_sieg()

    print("=== active=True, pagina=0 (lista completa) ===")
    itens_ativos = _tentar(http, active=True, pagina=0, listar_tudo=True)

    print("=== active=True, pagina=1 (só pra confirmar que continua 404) ===")
    _tentar(http, active=True, pagina=1)

    cnpjs_ativos = {item.get("CnpjCpf") for item in itens_ativos}

    print("=== Comparação com os 41 certificados do export do hub (23/09/2026) ===")
    faltando = [c for c in CERTIFICADOS_HUB_23_09_2026 if c[0] not in cnpjs_ativos]
    print(f"  active=True devolveu {len(cnpjs_ativos)} CNPJs distintos.")
    print(f"  Do export do hub (41 certificados), {len(faltando)} NÃO aparecem em active=True:")
    for cnpj, status, nome in faltando:
        print(f"    {cnpj} | hub={status} | {nome}")

    alvo = {"03672173000144", "37636249000106", "47251972000112"}
    print()
    print("  Os 3 certificados que sumiram numa resposta anterior do agente:")
    for cnpj in alvo:
        onde = "DENTRO de active=True" if cnpj in cnpjs_ativos else "FORA de active=True (nao retornado)"
        print(f"    {cnpj} -> {onde}")


if __name__ == "__main__":
    main()
