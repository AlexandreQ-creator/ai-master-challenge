"""
Gap Analysis por clusterização — RavenStack (Challenge 001).

Por que este script existe: toda a análise anterior desta submissão cruzou
no máximo duas dimensões por vez (indústria × canal, tenure × churn, MRR ×
concentração). Isso responde bem as perguntas do brief, mas tem um limite
conhecido — um corte manual só encontra o padrão que alguém já suspeitou.
Clusterização multidimensional não depende de hipótese prévia: agrupa as
contas pelo comportamento real em 7 dimensões simultâneas e deixa os
grupos emergirem dos dados.

O padrão de referência (baseline) é o próprio dataset fornecido pelo
desafio — não uma fonte externa. A "gap analysis" aqui é: o que os
clusters revelam que os cortes manuais do README já não tinham capturado?

Features por conta (cobrindo as 5 tabelas):
  1. tenure_dias          — tempo de vida da conta (accounts + subscriptions)
  2. mrr                  — receita recorrente mensal (subscriptions)
  3. uso_medio            — uso médio por evento (feature_usage)
  4. n_features_distintas — amplitude de adoção do produto (feature_usage)
  5. taxa_erro            — erros / uso total (feature_usage)
  6. n_tickets            — volume de suporte (support_tickets)
  7. tempo_resolucao_h    — tempo médio de resolução (support_tickets)

Método: K-Means sobre features padronizadas (StandardScaler — obrigatório,
já que MRR está em milhares e taxa_erro em décimos; sem normalizar, o MRR
dominaria a distância euclidiana e o cluster viraria "faixa de preço",
não "comportamento"). k escolhido por silhouette score, não arbitrado.

RESULTADO: negativo, e mantido na entrega por isso. O melhor silhouette
foi 0,137 (k=6) — clusters mal separados — e o spread de churn entre o
melhor e o pior cluster foi de 14,6pp, menor que os 38,5pp que o corte
manual indústria × canal já entregava. A clusterização não encontrou
estrutura latente que os cortes simples não tivessem encontrado. O achado
real da gap analysis veio de outro caminho (ver gap_analysis_feedback.py).

Pré-requisito: `pip install scikit-learn` — este é o ÚNICO script da
submissão que precisa dele. Todos os outros rodam só com openpyxl (ou
biblioteca padrão), e continuam funcionando mesmo sem o scikit-learn
instalado.

Uso: python gap_analysis_clusters.py
"""

import json
import sys
from collections import defaultdict
from statistics import mean

from gerar_excel import load, to_bool, to_float, to_date
from guard_entrada_dados import validar_entrada

try:
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score
    from sklearn.preprocessing import StandardScaler
except ImportError:
    print("ERRO: scikit-learn não está instalado.")
    print("Rode: pip install scikit-learn")
    sys.exit(1)

DATA = "../data"
OUTPUT_JSON = "../process-log/gap-analysis-clusters.json"

FEATURES = [
    "tenure_dias",
    "mrr",
    "uso_medio",
    "n_features_distintas",
    "taxa_erro",
    "n_tickets",
    "tempo_resolucao_h",
]


def construir_features():
    """Uma linha por conta, 7 features, cruzando as 5 tabelas."""
    accounts = load("ravenstack_accounts.csv")
    subs = load("ravenstack_subscriptions.csv")
    usage = load("ravenstack_feature_usage.csv")
    tickets = load("ravenstack_support_tickets.csv")

    subs_by_account = defaultdict(list)
    for s in subs:
        subs_by_account[s["account_id"]].append(s)

    usage_by_sub = defaultdict(list)
    for u in usage:
        usage_by_sub[u["subscription_id"]].append(u)

    tickets_by_account = defaultdict(list)
    for t in tickets:
        tickets_by_account[t["account_id"]].append(t)

    linhas = []
    for a in accounts:
        acc_id = a["account_id"]
        acc_subs = subs_by_account.get(acc_id, [])
        if not acc_subs:
            continue

        # assinatura mais recente = a que representa o estado atual da conta
        sub_atual = max(acc_subs, key=lambda s: to_date(s["start_date"]) or to_date("1970-01-01"))
        mrr = to_float(sub_atual["mrr_amount"], 0)

        # tenure: soma dos dias de todas as assinaturas da conta
        tenure = 0
        for s in acc_subs:
            sd = to_date(s["start_date"])
            ed = to_date(s["end_date"]) if s["end_date"] else to_date("2024-12-31")
            if sd and ed:
                tenure += max(0, (ed - sd).days)

        # uso agregado de todas as assinaturas da conta
        usos, erros, features_vistas = [], 0, set()
        for s in acc_subs:
            for u in usage_by_sub.get(s["subscription_id"], []):
                usos.append(to_float(u["usage_count"], 0))
                erros += to_float(u["error_count"], 0)
                features_vistas.add(u["feature_name"])
        uso_medio = mean(usos) if usos else 0.0
        taxa_erro = (erros / sum(usos)) if usos and sum(usos) > 0 else 0.0

        # suporte
        acc_tickets = tickets_by_account.get(acc_id, [])
        tempos = [to_float(t["resolution_time_hours"]) for t in acc_tickets]
        tempos = [t for t in tempos if t is not None]

        linhas.append({
            "account_id": acc_id,
            "account_name": a["account_name"],
            "industry": a["industry"],
            "referral_source": a["referral_source"],
            "plan_tier": a["plan_tier"],
            "churn_flag": to_bool(a["churn_flag"]),
            "tenure_dias": float(tenure),
            "mrr": float(mrr),
            "uso_medio": float(uso_medio),
            "n_features_distintas": float(len(features_vistas)),
            "taxa_erro": float(taxa_erro),
            "n_tickets": float(len(acc_tickets)),
            "tempo_resolucao_h": float(mean(tempos)) if tempos else 0.0,
        })
    return linhas


def escolher_k(X, k_min=2, k_max=8):
    """k por silhouette score — não arbitrado. Retorna (melhor_k, scores)."""
    scores = {}
    for k in range(k_min, k_max + 1):
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = km.fit_predict(X)
        scores[k] = float(silhouette_score(X, labels))
    melhor = max(scores, key=scores.get)
    return melhor, scores


def perfilar_clusters(linhas, labels):
    """Estatística descritiva por cluster + taxa de churn (a variável-alvo)."""
    por_cluster = defaultdict(list)
    for linha, label in zip(linhas, labels):
        por_cluster[int(label)].append(linha)

    perfis = []
    for cid in sorted(por_cluster):
        membros = por_cluster[cid]
        n = len(membros)
        n_churn = sum(1 for m in membros if m["churn_flag"])
        perfil = {
            "cluster": cid,
            "n_contas": n,
            "n_churned": n_churn,
            "taxa_churn_pct": round(n_churn / n * 100, 1),
            "mrr_total": round(sum(m["mrr"] for m in membros), 2),
            "medias": {f: round(mean(m[f] for m in membros), 2) for f in FEATURES},
            "industria_dominante": _dominante(membros, "industry"),
            "canal_dominante": _dominante(membros, "referral_source"),
            "plano_dominante": _dominante(membros, "plan_tier"),
        }
        perfis.append(perfil)
    return perfis, por_cluster


def _dominante(membros, campo):
    contagem = defaultdict(int)
    for m in membros:
        contagem[m[campo]] += 1
    total = len(membros)
    chave = max(contagem, key=contagem.get)
    return {"valor": chave, "pct": round(contagem[chave] / total * 100, 1)}


def main():
    ok, erros = validar_entrada(pasta_data=DATA, verbose=False)
    if not ok:
        print("ERRO: a base não passou no guard de entrada. Rode guard_entrada_dados.py.")
        for e in erros:
            print(f"  {e}")
        sys.exit(1)

    print("=" * 74)
    print("GAP ANALYSIS POR CLUSTERIZAÇÃO — o que os cortes manuais não capturaram")
    print("=" * 74)
    print()

    linhas = construir_features()
    print(f"Contas com vetor de features completo: {len(linhas)}")
    print(f"Features ({len(FEATURES)}): {', '.join(FEATURES)}")
    print()

    X_raw = [[linha[f] for f in FEATURES] for linha in linhas]
    X = StandardScaler().fit_transform(X_raw)

    melhor_k, scores = escolher_k(X)
    print("Escolha de k por silhouette score (não arbitrado):")
    for k, s in sorted(scores.items()):
        marca = "  <-- escolhido" if k == melhor_k else ""
        print(f"  k={k}: {s:.4f}{marca}")
    print()

    km = KMeans(n_clusters=melhor_k, random_state=42, n_init=10)
    labels = km.fit_predict(X)
    perfis, por_cluster = perfilar_clusters(linhas, labels)

    taxa_global = sum(1 for l in linhas if l["churn_flag"]) / len(linhas) * 100
    print(f"Taxa de churn GLOBAL (baseline do dataset fornecido): {taxa_global:.1f}%")
    print()
    print("-" * 74)
    print("PERFIL DE CADA CLUSTER")
    print("-" * 74)
    for p in sorted(perfis, key=lambda x: -x["taxa_churn_pct"]):
        delta = p["taxa_churn_pct"] - taxa_global
        sinal = "+" if delta >= 0 else ""
        print(f"\nCluster {p['cluster']} — {p['n_contas']} contas | "
              f"churn {p['taxa_churn_pct']}% ({sinal}{delta:.1f}pp vs. global) | "
              f"MRR total ${p['mrr_total']:,.0f}")
        m = p["medias"]
        print(f"   tenure médio: {m['tenure_dias']:.0f} dias | MRR médio: ${m['mrr']:,.0f} | "
              f"uso médio: {m['uso_medio']:.2f}")
        print(f"   features distintas: {m['n_features_distintas']:.1f} | "
              f"taxa erro: {m['taxa_erro']*100:.2f}% | tickets: {m['n_tickets']:.1f} | "
              f"resolução: {m['tempo_resolucao_h']:.1f}h")
        print(f"   dominantes: {p['industria_dominante']['valor']} ({p['industria_dominante']['pct']}%) / "
              f"{p['canal_dominante']['valor']} ({p['canal_dominante']['pct']}%) / "
              f"{p['plano_dominante']['valor']} ({p['plano_dominante']['pct']}%)")

    print()
    print("-" * 74)
    print("GAP ANALYSIS — clusters vs. os cortes manuais já feitos no README")
    print("-" * 74)

    pior = max(perfis, key=lambda p: p["taxa_churn_pct"])
    melhor = min(perfis, key=lambda p: p["taxa_churn_pct"])
    spread = pior["taxa_churn_pct"] - melhor["taxa_churn_pct"]

    print(f"\nSpread entre o cluster de maior e menor churn: {spread:.1f}pp")
    print(f"  pior:  Cluster {pior['cluster']} ({pior['taxa_churn_pct']}%, {pior['n_contas']} contas)")
    print(f"  melhor: Cluster {melhor['cluster']} ({melhor['taxa_churn_pct']}%, {melhor['n_contas']} contas)")
    print(f"\nComparação — spread dos cortes manuais já reportados no README:")
    print(f"  indústria × canal (DevTools/event vs. Cybersecurity/partner): 38.5pp")
    print(f"  plano isolado (Basic/Pro/Enterprise): ~0.2pp (não discrimina)")

    # concentração de MRR em risco por cluster
    mrr_em_risco = [(p["cluster"], p["mrr_total"], p["taxa_churn_pct"]) for p in perfis]
    mrr_total_geral = sum(m[1] for m in mrr_em_risco)
    print(f"\nDistribuição de MRR por cluster (total ${mrr_total_geral:,.0f}):")
    for cid, mrr, taxa in sorted(mrr_em_risco, key=lambda x: -x[1]):
        print(f"  Cluster {cid}: ${mrr:,.0f} ({mrr/mrr_total_geral*100:.1f}% do MRR) | churn {taxa}%")

    saida = {
        "baseline": "dataset fornecido pelo desafio (challenges/data-001-churn)",
        "taxa_churn_global_pct": round(taxa_global, 1),
        "k_escolhido": melhor_k,
        "silhouette_scores": {str(k): round(v, 4) for k, v in scores.items()},
        "features": FEATURES,
        "n_contas": len(linhas),
        "perfis": perfis,
        "spread_clusters_pp": round(spread, 1),
        "spread_corte_manual_industria_canal_pp": 38.5,
    }
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(saida, f, ensure_ascii=False, indent=2)
    print(f"\nDados salvos para consulta: {OUTPUT_JSON}")
    print("=" * 74)

    return perfis, por_cluster, taxa_global


if __name__ == "__main__":
    main()
