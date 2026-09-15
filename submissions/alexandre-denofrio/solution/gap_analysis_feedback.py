"""
Gap Analysis — o campo que ninguém olhou: `feedback_text`.

Este script isola o achado mais importante da submissão, encontrado só na
rodada de gap analysis: o `reason_code` de `ravenstack_churn_events.csv`
é estatisticamente INDEPENDENTE do que o próprio cliente escreveu no
`feedback_text` do mesmo evento de churn.

Como a análise original chegou perto e passou batido: o README observou
que `reason_code` estava distribuído quase uniformemente (15-19% em cada
um dos 6 valores) e concluiu que "não há razão declarada dominante — é um
problema estrutural que o cliente não sabe nomear". A conclusão estava
lendo um artefato de dado quebrado como se fosse um insight de negócio.
O `feedback_text`, na mesma tabela, nunca foi aberto.

Quando aberto: 3 valores distintos, concentrados, e com um líder claro —
"too expensive" (35,6%). O cruzamento dos dois campos mostra concordância
de 16,2%, contra 16,7% esperado por puro acaso (1 em 6).

Uso: python gap_analysis_feedback.py
"""

import json
import sys
from collections import Counter, defaultdict

sys.stdout.reconfigure(encoding="utf-8")

from gerar_excel import load, to_float
from guard_entrada_dados import validar_entrada

DATA = "../data"
OUTPUT_JSON = "../process-log/gap-analysis-feedback.json"

# Mapeamento "óbvio" texto -> código: o que um sistema de CRM funcionando
# produziria. Usado só para medir concordância, não para corrigir o dado.
MAPA_ESPERADO = {
    "too expensive": "pricing",
    "missing features": "features",
    "switched to competitor": "competitor",
}

# Valor crítico do qui-quadrado para p=0.05 com 10 graus de liberdade
# ((3 textos - 1) x (6 códigos - 1) = 10). Tabelado — evita depender de
# scipy só para uma constante.
CHI2_CRITICO_GL10_P005 = 18.31


def analisar():
    churn = load("ravenstack_churn_events.csv")
    com_texto = [c for c in churn if c["feedback_text"].strip()]
    sem_texto = len(churn) - len(com_texto)

    matriz = defaultdict(lambda: defaultdict(int))
    for c in com_texto:
        matriz[c["feedback_text"].strip()][c["reason_code"]] += 1

    textos = sorted(matriz)
    codigos = sorted({c["reason_code"] for c in com_texto})
    n = len(com_texto)

    tot_linha = {t: sum(matriz[t].values()) for t in textos}
    tot_col = {cod: sum(matriz[t][cod] for t in textos) for cod in codigos}

    chi2 = 0.0
    for t in textos:
        for cod in codigos:
            obs = matriz[t][cod]
            esp = tot_linha[t] * tot_col[cod] / n
            if esp > 0:
                chi2 += (obs - esp) ** 2 / esp

    acertos = sum(matriz[t][MAPA_ESPERADO[t]] for t in textos if t in MAPA_ESPERADO)
    concordancia = acertos / n * 100
    acaso = 100 / len(codigos)

    dist_real = Counter(c["feedback_text"].strip() for c in com_texto)
    dist_codigo = Counter(c["reason_code"] for c in churn)

    refund_por_motivo = defaultdict(list)
    for c in com_texto:
        refund_por_motivo[c["feedback_text"].strip()].append(to_float(c["refund_amount_usd"], 0))

    return {
        "n_eventos_churn": len(churn),
        "n_com_feedback": n,
        "n_sem_feedback": sem_texto,
        "pct_com_feedback": round(n / len(churn) * 100, 1),
        "matriz": {t: dict(matriz[t]) for t in textos},
        "chi2": round(chi2, 3),
        "graus_liberdade": (len(textos) - 1) * (len(codigos) - 1),
        "chi2_critico_p005": CHI2_CRITICO_GL10_P005,
        "independentes": chi2 < CHI2_CRITICO_GL10_P005,
        "concordancia_pct": round(concordancia, 1),
        "concordancia_acaso_pct": round(acaso, 1),
        "distribuicao_real_feedback": dict(dist_real),
        "distribuicao_reason_code": dict(dist_codigo),
        "refund_medio_por_motivo": {
            t: round(sum(v) / len(v), 2) for t, v in refund_por_motivo.items()
        },
    }


def imprimir(r):
    print("=" * 74)
    print("GAP ANALYSIS — o campo que ninguém olhou: feedback_text")
    print("=" * 74)
    print()
    print(f"Eventos de churn: {r['n_eventos_churn']}")
    print(f"Com feedback_text preenchido: {r['n_com_feedback']} ({r['pct_com_feedback']}%)")
    print(f"Sem feedback_text: {r['n_sem_feedback']}")
    print()

    print("-" * 74)
    print("CRUZAMENTO: o que o cliente escreveu x o que o sistema registrou")
    print("-" * 74)
    codigos = sorted(r["distribuicao_reason_code"])
    header = "feedback_text".ljust(24) + "".join(c.ljust(12) for c in codigos)
    print(header)
    print("-" * len(header))
    for texto in sorted(r["matriz"]):
        linha = texto.ljust(24)
        total = sum(r["matriz"][texto].values())
        for cod in codigos:
            v = r["matriz"][texto].get(cod, 0)
            linha += f"{v} ({v/total*100:.0f}%)".ljust(12)
        print(linha)
    print()

    print("-" * 74)
    print("TESTE ESTATÍSTICO DE INDEPENDÊNCIA")
    print("-" * 74)
    print(f"Qui-quadrado: {r['chi2']} (gl={r['graus_liberdade']}, "
          f"valor crítico p=0.05: {r['chi2_critico_p005']})")
    if r["independentes"]:
        print("NÃO rejeita independência — os dois campos são estatisticamente")
        print("independentes. O reason_code não carrega informação sobre o que")
        print("o cliente escreveu.")
    else:
        print("Rejeita independência — há associação real entre os campos.")
    print()
    print(f"Concordância real (texto -> código esperado): {r['concordancia_pct']}%")
    print(f"Concordância esperada por puro acaso (1 em {len(codigos)}): {r['concordancia_acaso_pct']}%")
    print()

    print("-" * 74)
    print("O GAP: duas versões da mesma realidade")
    print("-" * 74)
    print("\nO que a EMPRESA enxerga (reason_code, base de toda a análise até aqui):")
    for cod, v in sorted(r["distribuicao_reason_code"].items(), key=lambda x: -x[1]):
        print(f"  {cod:26s} {v:3d} ({v/r['n_eventos_churn']*100:.1f}%)")
    print("  -> leitura: 6 motivos pulverizados, nenhum dominante")

    print("\nO que o CLIENTE de fato disse (feedback_text):")
    for texto, v in sorted(r["distribuicao_real_feedback"].items(), key=lambda x: -x[1]):
        print(f"  {texto:26s} {v:3d} ({v/r['n_com_feedback']*100:.1f}%)")
    print("  -> leitura: 3 motivos concentrados, preço/custo lidera")
    print()
    print("=" * 74)


def main():
    ok, erros = validar_entrada(pasta_data=DATA, verbose=False)
    if not ok:
        print("ERRO: a base não passou no guard de entrada.")
        for e in erros:
            print(f"  {e}")
        sys.exit(1)

    r = analisar()
    imprimir(r)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(r, f, ensure_ascii=False, indent=2)
    print(f"Dados salvos para consulta: {OUTPUT_JSON}")
    return True


if __name__ == "__main__":
    main()
