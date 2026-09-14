"""
Auditor de integridade semântica de campos categóricos.

ORIGEM: este auditor é a generalização de um achado específico desta
submissão (achado 7 do README). Ao cruzar `reason_code` com `feedback_text`
em `ravenstack_churn_events.csv`, descobriu-se que os dois campos são
estatisticamente independentes — um cliente que escreveu "too expensive"
recebia o código `pricing` em 16% dos casos, contra 16,7% esperado por
puro acaso. O campo estava sendo preenchido sem relação com a realidade, e
ninguém tinha percebido porque o dado *parecia* normal: preenchido, com
valores válidos, sem nulo.

A lição que vale além deste caso: **um campo categórico pode estar
completamente quebrado e ainda passar por todas as validações usuais.**
O guard de entrada (`guard_entrada_dados.py`) checa schema, vocabulário e
formato — e o `reason_code` passava em todos os três. O que denuncia o
problema não é a forma do dado, é a ausência de relação semântica com os
outros campos que deveriam explicá-lo.

O QUE ESTE AUDITOR FAZ: em vez de testar só o par que já sabemos ser
problemático, varre TODOS os pares de colunas categóricas de TODAS as
tabelas e roda um teste de independência em cada um. Não precisa de
hipótese prévia — descobriria o mesmo problema num dataset novo, em um
campo que ninguém suspeitou.

DISCIPLINA ESTATÍSTICA: com ~50 pares testados simultaneamente, a chance
de um falso positivo por acaso é alta (problema de comparações
múltiplas). Por isso o auditor:
  1. Aplica correção de Bonferroni ao nível de significância.
  2. Exige tamanho de amostra mínimo por célula (regra de Cochran).
  3. Separa "independente" (suspeito) de "associação fraca" — nem toda
     independência é um bug: dois campos podem ser legitimamente não
     relacionados (ex.: país e prioridade de ticket).
  4. Classifica a severidade pelo que se ESPERARIA da semântica dos
     nomes, não só pela estatística — um par que *deveria* ser
     relacionado e não é vale um alerta alto; um par sem relação
     esperada vale nota informativa.

Uso:
  python auditor_integridade_semantica.py            # audita data/
  python auditor_integridade_semantica.py --json     # só o JSON, sem relatório
"""

import json
import sys
from collections import defaultdict
from itertools import combinations

from gerar_excel import load
from guard_entrada_dados import SCHEMA_ESPERADO, validar_entrada

DATA = "../data"
OUTPUT_JSON = "../process-log/auditoria-integridade-semantica.json"

# Uma coluna é tratada como categórica se tiver entre 2 e MAX_CARDINALIDADE
# valores distintos. Acima disso é identificador ou medida contínua.
MIN_CARDINALIDADE = 2
MAX_CARDINALIDADE = 20

# Regra de Cochran: o teste de qui-quadrado não é confiável se as
# frequências esperadas forem muito baixas. Exigimos que ao menos 80% das
# células tenham esperado >= 5.
MIN_ESPERADO_POR_CELULA = 5
PCT_MIN_CELULAS_OK = 0.8

# Nível de significância antes da correção para comparações múltiplas.
ALFA_BASE = 0.05

# Pares cuja semântica dos nomes sugere que DEVERIAM estar relacionados.
# Independência aqui é sinal forte de dado quebrado, não de dois campos
# legitimamente não relacionados. Lista editada à mão — é justamente o
# tipo de julgamento de domínio que um script não infere sozinho.
PARES_COM_RELACAO_ESPERADA = {
    frozenset({"reason_code", "feedback_text"}),
    frozenset({"plan_tier", "mrr_amount"}),
    frozenset({"upgrade_flag", "downgrade_flag"}),
    frozenset({"priority", "escalation_flag"}),
    frozenset({"priority", "satisfaction_score"}),
    frozenset({"is_trial", "plan_tier"}),
    frozenset({"churn_flag", "auto_renew_flag"}),
}

# Valores críticos do qui-quadrado tabelados por graus de liberdade, para
# vários níveis alfa. Evita depender de scipy — a submissão inteira roda
# sem dependência pesada exceto o script de clusterização.
# Fonte: tabela padrão da distribuição qui-quadrado.
CHI2_CRITICO = {
    # gl: {alfa: valor}
    1:  {0.05: 3.841,  0.01: 6.635,  0.001: 10.828},
    2:  {0.05: 5.991,  0.01: 9.210,  0.001: 13.816},
    3:  {0.05: 7.815,  0.01: 11.345, 0.001: 16.266},
    4:  {0.05: 9.488,  0.01: 13.277, 0.001: 18.467},
    5:  {0.05: 11.070, 0.01: 15.086, 0.001: 20.515},
    6:  {0.05: 12.592, 0.01: 16.812, 0.001: 22.458},
    8:  {0.05: 15.507, 0.01: 20.090, 0.001: 26.125},
    10: {0.05: 18.307, 0.01: 23.209, 0.001: 29.588},
    12: {0.05: 21.026, 0.01: 26.217, 0.001: 32.909},
    15: {0.05: 24.996, 0.01: 30.578, 0.001: 37.697},
    16: {0.05: 26.296, 0.01: 32.000, 0.001: 39.252},
    20: {0.05: 31.410, 0.01: 37.566, 0.001: 45.315},
    24: {0.05: 36.415, 0.01: 42.980, 0.001: 51.179},
    25: {0.05: 37.652, 0.01: 44.314, 0.001: 52.620},
    30: {0.05: 43.773, 0.01: 50.892, 0.001: 59.703},
}


def _critico(gl, alfa):
    """Valor crítico para gl graus de liberdade. Usa o gl tabelado mais
    próximo por cima — conservador (exige evidência mais forte)."""
    if gl in CHI2_CRITICO and alfa in CHI2_CRITICO[gl]:
        return CHI2_CRITICO[gl][alfa]
    disponiveis = sorted(g for g in CHI2_CRITICO if g >= gl)
    if not disponiveis:
        return None
    return CHI2_CRITICO[disponiveis[0]].get(alfa)


def colunas_categoricas(linhas):
    if not linhas:
        return []
    cats = []
    for col in linhas[0].keys():
        valores = {l[col].strip() for l in linhas if l[col].strip()}
        if MIN_CARDINALIDADE <= len(valores) <= MAX_CARDINALIDADE:
            cats.append(col)
    return cats


def testar_par(linhas, col_a, col_b):
    """Qui-quadrado de independência entre duas colunas categóricas.
    Só considera linhas em que AMBAS estão preenchidas."""
    matriz = defaultdict(lambda: defaultdict(int))
    n = 0
    for l in linhas:
        va, vb = l[col_a].strip(), l[col_b].strip()
        if va and vb:
            matriz[va][vb] += 1
            n += 1
    if n == 0:
        return None

    vals_a = sorted(matriz)
    vals_b = sorted({vb for va in matriz for vb in matriz[va]})
    if len(vals_a) < 2 or len(vals_b) < 2:
        return None

    tot_a = {va: sum(matriz[va].values()) for va in vals_a}
    tot_b = {vb: sum(matriz[va][vb] for va in vals_a) for vb in vals_b}

    chi2 = 0.0
    celulas_ok = 0
    total_celulas = len(vals_a) * len(vals_b)
    for va in vals_a:
        for vb in vals_b:
            obs = matriz[va][vb]
            esp = tot_a[va] * tot_b[vb] / n
            if esp >= MIN_ESPERADO_POR_CELULA:
                celulas_ok += 1
            if esp > 0:
                chi2 += (obs - esp) ** 2 / esp

    gl = (len(vals_a) - 1) * (len(vals_b) - 1)
    confiavel = (celulas_ok / total_celulas) >= PCT_MIN_CELULAS_OK

    # Cramér's V — força da associação, independente do tamanho da amostra.
    # Necessário porque o qui-quadrado cresce com n: num dataset grande,
    # associações irrelevantes viram "significativas".
    k_min = min(len(vals_a), len(vals_b))
    cramers_v = (chi2 / (n * (k_min - 1))) ** 0.5 if n > 0 and k_min > 1 else 0.0

    return {
        "col_a": col_a,
        "col_b": col_b,
        "n": n,
        "chi2": round(chi2, 3),
        "gl": gl,
        "cramers_v": round(cramers_v, 4),
        "confiavel": confiavel,
        "pct_celulas_validas": round(celulas_ok / total_celulas * 100, 1),
    }


def diagnosticar_dataset(resultados):
    """
    Distingue "alguns campos quebrados" de "dataset inteiro sem estrutura".

    Esta checagem existe por causa de um falso-positivo real desta
    auditoria: na primeira rodada, o auditor marcou 7 pares como suspeitos
    de campo quebrado. Investigando, descobriu-se que 46 dos 50 pares eram
    independentes e NENHUM par tinha Cramér's V acima de 0,2 — inclusive
    pares que em qualquer base real teriam associação forte (is_trial x
    plan_tier com trials distribuídos uniformemente entre os três tiers,
    upgrade_flag x downgrade_flag com chi2 exatamente 0,0).

    Isso não é "vários campos quebrados", é a assinatura de um dataset
    SINTÉTICO cujas colunas categóricas foram geradas de forma
    independente. Relatar 7 campos quebrados seria tecnicamente derivado
    dos números e substantivamente errado.
    """
    if not resultados:
        return None
    vs = [r["cramers_v"] for r in resultados]
    v_max = max(vs)
    n_independentes = sum(1 for r in resultados if r["veredito"] == "INDEPENDENTE")
    pct_independentes = n_independentes / len(resultados) * 100
    # Limiar 0,2: abaixo disso não há associação de utilidade prática em
    # nenhum par; se NENHUM par do dataset inteiro passa disso, o problema
    # não é campo a campo.
    sem_estrutura = v_max < 0.2 and pct_independentes > 70
    return {
        "cramers_v_maximo": round(v_max, 4),
        "pct_pares_independentes": round(pct_independentes, 1),
        "dataset_sem_estrutura_categorica": sem_estrutura,
    }


def auditar():
    resultados = []
    for arquivo in SCHEMA_ESPERADO:
        linhas = load(arquivo)
        cats = colunas_categoricas(linhas)
        for col_a, col_b in combinations(cats, 2):
            r = testar_par(linhas, col_a, col_b)
            if r:
                r["arquivo"] = arquivo
                resultados.append(r)

    n_testes = len(resultados)
    # Bonferroni: com n_testes simultâneos, o alfa de cada teste vira
    # alfa/n para manter o erro tipo I global em 5%.
    alfa_corrigido = ALFA_BASE / n_testes if n_testes else ALFA_BASE
    alfa_usado = 0.001 if alfa_corrigido < 0.01 else (0.01 if alfa_corrigido < 0.05 else 0.05)

    for r in resultados:
        critico = _critico(r["gl"], alfa_usado)
        r["alfa_usado"] = alfa_usado
        r["chi2_critico"] = critico
        if critico is None:
            r["veredito"] = "INCONCLUSIVO"
        elif not r["confiavel"]:
            r["veredito"] = "AMOSTRA INSUFICIENTE"
        elif r["chi2"] < critico:
            r["veredito"] = "INDEPENDENTE"
        else:
            r["veredito"] = "ASSOCIADO"

        par = frozenset({r["col_a"], r["col_b"]})
        r["relacao_esperada"] = par in PARES_COM_RELACAO_ESPERADA
        if r["relacao_esperada"] and r["veredito"] == "INDEPENDENTE":
            r["severidade"] = "ALTA"
        elif r["relacao_esperada"] and r["veredito"] == "ASSOCIADO" and r["cramers_v"] < 0.1:
            r["severidade"] = "MÉDIA"
        elif r["veredito"] == "AMOSTRA INSUFICIENTE":
            r["severidade"] = "INFO"
        else:
            r["severidade"] = "OK"

    return resultados, n_testes, alfa_usado


def imprimir(resultados, n_testes, alfa_usado, diagnostico):
    print("=" * 78)
    print("AUDITOR DE INTEGRIDADE SEMÂNTICA — campos categóricos que podem ser ruído")
    print("=" * 78)
    print()
    print(f"Pares testados: {n_testes} (todas as combinações de colunas categóricas")
    print(f"                das 5 tabelas, sem hipótese prévia sobre onde procurar)")
    print(f"Correção para comparações múltiplas: Bonferroni")
    print(f"  alfa base {ALFA_BASE} / {n_testes} testes -> alfa por teste: {alfa_usado}")
    print()

    if diagnostico and diagnostico["dataset_sem_estrutura_categorica"]:
        print("!" * 78)
        print("DIAGNÓSTICO PRÉVIO: dataset sem estrutura categórica")
        print("!" * 78)
        print(f"  Cramér's V máximo em {n_testes} pares: {diagnostico['cramers_v_maximo']}")
        print(f"  Pares independentes: {diagnostico['pct_pares_independentes']}%")
        print()
        print("  NENHUM par de colunas categóricas deste dataset tem associação de")
        print("  relevância prática (V > 0,2) — incluindo pares que em qualquer base")
        print("  real de negócio seriam fortemente associados.")
        print()
        print("  Interpretação: isto NÃO é 'vários campos quebrados'. É a assinatura")
        print("  de um dataset sintético cujas colunas categóricas foram geradas")
        print("  independentemente umas das outras.")
        print()
        print("  CONSEQUÊNCIA PRÁTICA: qualquer achado deste dataset que dependa da")
        print("  relação entre dois campos categóricos precisa ser reportado como")
        print("  propriedade do dado, não como insight sobre o negócio. A lista")
        print("  abaixo é informativa — não trate como 7 bugs a corrigir.")
        print()

    altas = [r for r in resultados if r["severidade"] == "ALTA"]
    medias = [r for r in resultados if r["severidade"] == "MÉDIA"]
    infos = [r for r in resultados if r["severidade"] == "INFO"]

    if altas:
        print("-" * 78)
        print("SEVERIDADE ALTA — campos que DEVERIAM se relacionar e não se relacionam")
        print("-" * 78)
        for r in altas:
            print(f"\n  {r['arquivo']}")
            print(f"  {r['col_a']} x {r['col_b']}")
            print(f"    chi2 = {r['chi2']} (gl={r['gl']}, crítico={r['chi2_critico']}) -> {r['veredito']}")
            print(f"    Cramér's V = {r['cramers_v']} (0 = nenhuma associação)")
            print(f"    n = {r['n']} linhas com ambos preenchidos")
            print(f"    => Estes dois campos descrevem a mesma realidade, mas são")
            print(f"       estatisticamente independentes. Um deles provavelmente não")
            print(f"       está sendo preenchido com base na realidade.")
    else:
        print("Nenhum par de severidade ALTA encontrado.")

    if medias:
        print()
        print("-" * 78)
        print("SEVERIDADE MÉDIA — relação esperada existe, mas é fraca")
        print("-" * 78)
        for r in medias:
            print(f"  [{r['arquivo']}] {r['col_a']} x {r['col_b']}: "
                  f"associação significativa mas Cramér's V = {r['cramers_v']} (fraca)")

    print()
    print("-" * 78)
    print("RESUMO DOS 5 PARES COM MAIOR ASSOCIAÇÃO (contexto — o que é normal aqui)")
    print("-" * 78)
    associados = sorted([r for r in resultados if r["veredito"] == "ASSOCIADO"],
                        key=lambda x: -x["cramers_v"])[:5]
    for r in associados:
        print(f"  [{r['arquivo'].replace('ravenstack_','').replace('.csv','')}] "
              f"{r['col_a']} x {r['col_b']}: V = {r['cramers_v']}")
    if not associados:
        print("  (nenhum par com associação significativa)")

    print()
    contagem = defaultdict(int)
    for r in resultados:
        contagem[r["veredito"]] += 1
    print("Vereditos:", dict(contagem))
    print()
    print("=" * 78)
    if diagnostico and diagnostico["dataset_sem_estrutura_categorica"]:
        print("VEREDITO: dataset sem estrutura categórica detectável.")
        print(f"  {len(altas)} par(es) de relação esperada saíram independentes, mas o")
        print("  diagnóstico acima mostra que isso vale para o dataset inteiro, não")
        print("  para campos específicos. Reportar como propriedade do dado.")
    elif altas:
        print(f"VEREDITO: {len(altas)} campo(s) suspeito(s) de ser ruído — investigar antes de")
        print("usar esses dados para qualquer decisão ou priorização.")
    else:
        print("VEREDITO: nenhum campo categórico com assinatura de ruído detectado.")
    print("=" * 78)


def main():
    apenas_json = "--json" in sys.argv

    ok, erros = validar_entrada(pasta_data=DATA, verbose=False)
    if not ok:
        print("ERRO: a base não passou no guard de entrada.")
        for e in erros:
            print(f"  {e}")
        sys.exit(1)

    resultados, n_testes, alfa_usado = auditar()
    diagnostico = diagnosticar_dataset(resultados)

    if not apenas_json:
        imprimir(resultados, n_testes, alfa_usado, diagnostico)

    saida = {
        "n_pares_testados": n_testes,
        "alfa_base": ALFA_BASE,
        "alfa_corrigido_bonferroni": alfa_usado,
        "diagnostico_dataset": diagnostico,
        "resultados": resultados,
        "suspeitos_alta_severidade": [
            {"arquivo": r["arquivo"], "col_a": r["col_a"], "col_b": r["col_b"],
             "chi2": r["chi2"], "cramers_v": r["cramers_v"]}
            for r in resultados if r["severidade"] == "ALTA"
        ],
    }
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(saida, f, ensure_ascii=False, indent=2)

    if not apenas_json:
        print(f"\nDados salvos para consulta: {OUTPUT_JSON}")

    # Exit code reflete o resultado (lição do bug de exit code corrigido
    # nos outros harnesses). Dataset sem estrutura categórica não é falha
    # do auditor nem bug a corrigir — é uma propriedade do dado, já
    # reportada. Só retorna erro se houver suspeito isolado num dataset
    # que, no resto, TEM estrutura.
    if diagnostico and diagnostico["dataset_sem_estrutura_categorica"]:
        return True
    return len(saida["suspeitos_alta_severidade"]) == 0


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
