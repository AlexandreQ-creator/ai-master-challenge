"""
Análise de causa raiz de churn — RavenStack (Challenge 001, AI Master G4).

Script determinístico: carrega as 5 tabelas, faz os cruzamentos e imprime
métricas cruas. A interpretação/causa raiz fica no relatório (README.md),
não aqui — este script só produz os números verificáveis que sustentam o
relatório.
"""

import csv
from collections import defaultdict
from datetime import datetime
from statistics import mean, median

DATA = "../data"


def load(fname):
    with open(f"{DATA}/{fname}", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def to_bool(v):
    return str(v).strip().lower() == "true"


def to_float(v, default=None):
    try:
        return float(v)
    except (ValueError, TypeError):
        return default


def to_date(v):
    if not v:
        return None
    return datetime.strptime(v[:10], "%Y-%m-%d")


accounts = load("ravenstack_accounts.csv")
subs = load("ravenstack_subscriptions.csv")
usage = load("ravenstack_feature_usage.csv")
tickets = load("ravenstack_support_tickets.csv")
churn = load("ravenstack_churn_events.csv")

acc_by_id = {a["account_id"]: a for a in accounts}
subs_by_account = defaultdict(list)
for s in subs:
    subs_by_account[s["account_id"]].append(s)
sub_by_id = {s["subscription_id"]: s for s in subs}

usage_by_sub = defaultdict(list)
for u in usage:
    usage_by_sub[u["subscription_id"]].append(u)

tickets_by_account = defaultdict(list)
for t in tickets:
    tickets_by_account[t["account_id"]].append(t)

churn_by_account = defaultdict(list)
for c in churn:
    churn_by_account[c["account_id"]].append(c)

print("=" * 70)
print("1. VISÃO GERAL")
print("=" * 70)
print(f"Contas: {len(accounts)}")
print(f"Contas com churn_flag=True: {sum(1 for a in accounts if to_bool(a['churn_flag']))}")
print(f"Assinaturas: {len(subs)}")
print(f"Assinaturas com churn_flag=True: {sum(1 for s in subs if to_bool(s['churn_flag']))}")
print(f"Eventos de churn: {len(churn)} (contas distintas: {len(churn_by_account)})")
reactivations = sum(1 for c in churn if to_bool(c["is_reactivation"]))
print(f"Eventos que são reativação prévia (is_reactivation=True): {reactivations}")
multi_churn_accounts = [acc for acc, evs in churn_by_account.items() if len(evs) > 1]
print(f"Contas com MAIS DE UM evento de churn (churn->reativação->churn de novo): {len(multi_churn_accounts)}")

print()
print("=" * 70)
print("2. REASON CODE — distribuição bruta")
print("=" * 70)
reason_counts = defaultdict(int)
reason_refund = defaultdict(list)
for c in churn:
    reason_counts[c["reason_code"]] += 1
    r = to_float(c["refund_amount_usd"])
    if r is not None:
        reason_refund[c["reason_code"]].append(r)
for reason, cnt in sorted(reason_counts.items(), key=lambda x: -x[1]):
    avg_refund = mean(reason_refund[reason]) if reason_refund[reason] else 0
    print(f"  {reason:15s} {cnt:4d} eventos  ({cnt/len(churn)*100:5.1f}%)  refund médio ${avg_refund:7.2f}")

print()
print("=" * 70)
print("3. CEO PARADOX — 'uso cresceu' é verdade para todo mundo?")
print("=" * 70)
# Para cada assinatura, soma de usage_count e média de error_count no período,
# separado por: assinatura que terminou em churn vs que não.
sub_usage_stats = {}
for sub_id, rows in usage_by_sub.items():
    total_usage = sum(to_float(r["usage_count"], 0) for r in rows)
    total_errors = sum(to_float(r["error_count"], 0) for r in rows)
    n_events = len(rows)
    n_features = len({r["feature_name"] for r in rows})
    sub_usage_stats[sub_id] = {
        "total_usage": total_usage,
        "total_errors": total_errors,
        "n_events": n_events,
        "n_features": n_features,
        "error_rate": total_errors / total_usage if total_usage else 0,
    }

churned_sub_ids = {s["subscription_id"] for s in subs if to_bool(s["churn_flag"])}
active_sub_ids = {s["subscription_id"] for s in subs if not to_bool(s["churn_flag"])}

churned_usage = [sub_usage_stats[sid]["total_usage"] for sid in churned_sub_ids if sid in sub_usage_stats]
active_usage = [sub_usage_stats[sid]["total_usage"] for sid in active_sub_ids if sid in sub_usage_stats]
churned_errrate = [sub_usage_stats[sid]["error_rate"] for sid in churned_sub_ids if sid in sub_usage_stats]
active_errrate = [sub_usage_stats[sid]["error_rate"] for sid in active_sub_ids if sid in sub_usage_stats]
churned_nfeat = [sub_usage_stats[sid]["n_features"] for sid in churned_sub_ids if sid in sub_usage_stats]
active_nfeat = [sub_usage_stats[sid]["n_features"] for sid in active_sub_ids if sid in sub_usage_stats]

print(f"Assinaturas churned com dados de uso: {len(churned_usage)} / {len(churned_sub_ids)}")
print(f"Assinaturas ativas com dados de uso:  {len(active_usage)} / {len(active_sub_ids)}")
print(f"Uso total médio (churned):  {mean(churned_usage):8.1f}   mediana: {median(churned_usage):8.1f}" if churned_usage else "  (sem dados)")
print(f"Uso total médio (ativas):   {mean(active_usage):8.1f}   mediana: {median(active_usage):8.1f}" if active_usage else "  (sem dados)")
print(f"Taxa de erro média (churned): {mean(churned_errrate)*100:6.2f}%" if churned_errrate else "")
print(f"Taxa de erro média (ativas):  {mean(active_errrate)*100:6.2f}%" if active_errrate else "")
print(f"Nº médio de features distintas usadas (churned): {mean(churned_nfeat):5.2f}" if churned_nfeat else "")
print(f"Nº médio de features distintas usadas (ativas):  {mean(active_nfeat):5.2f}" if active_nfeat else "")

print()
print("=" * 70)
print("4. SUPORTE — tickets de quem churnou vs quem ficou")
print("=" * 70)
churned_accounts_set = {a["account_id"] for a in accounts if to_bool(a["churn_flag"])}
active_accounts_set = {a["account_id"] for a in accounts if not to_bool(a["churn_flag"])}


def ticket_stats(account_ids):
    rel = [t for t in tickets if t["account_id"] in account_ids]
    sats = [to_float(t["satisfaction_score"]) for t in rel if to_float(t["satisfaction_score"]) is not None]
    res_times = [to_float(t["resolution_time_hours"]) for t in rel if to_float(t["resolution_time_hours"]) is not None]
    frt = [to_float(t["first_response_time_minutes"]) for t in rel if to_float(t["first_response_time_minutes"]) is not None]
    esc = sum(1 for t in rel if to_bool(t["escalation_flag"]))
    n_accounts_with_ticket = len({t["account_id"] for t in rel})
    return {
        "n_tickets": len(rel),
        "n_accounts_with_ticket": n_accounts_with_ticket,
        "tickets_per_account_overall": len(rel) / len(account_ids) if account_ids else 0,
        "avg_satisfaction": mean(sats) if sats else None,
        "n_with_satisfaction": len(sats),
        "avg_resolution_h": mean(res_times) if res_times else None,
        "avg_first_response_min": mean(frt) if frt else None,
        "pct_escalated": esc / len(rel) * 100 if rel else 0,
    }


churned_ticket_stats = ticket_stats(churned_accounts_set)
active_ticket_stats = ticket_stats(active_accounts_set)
print(f"Contas churned: {len(churned_accounts_set)}  | Contas ativas: {len(active_accounts_set)}")
print(f"Tickets/conta (churned): {churned_ticket_stats['tickets_per_account_overall']:.2f}  | (ativas): {active_ticket_stats['tickets_per_account_overall']:.2f}")
print(f"Satisfação média (churned): {churned_ticket_stats['avg_satisfaction']}  (n={churned_ticket_stats['n_with_satisfaction']})")
print(f"Satisfação média (ativas):  {active_ticket_stats['avg_satisfaction']}  (n={active_ticket_stats['n_with_satisfaction']})")
print(f"% escalados (churned): {churned_ticket_stats['pct_escalated']:.1f}%  | (ativas): {active_ticket_stats['pct_escalated']:.1f}%")
print(f"Tempo médio de 1ª resposta (churned): {churned_ticket_stats['avg_first_response_min']:.1f} min | (ativas): {active_ticket_stats['avg_first_response_min']:.1f} min")
print(f"Tempo médio de resolução (churned): {churned_ticket_stats['avg_resolution_h']:.1f} h | (ativas): {active_ticket_stats['avg_resolution_h']:.1f} h")

# Satisfação: quantos tickets sequer têm satisfaction_score preenchido?
all_sat_filled = sum(1 for t in tickets if to_float(t["satisfaction_score"]) is not None)
print(f"\nCOBERTURA do satisfaction_score: {all_sat_filled}/{len(tickets)} tickets ({all_sat_filled/len(tickets)*100:.1f}%) têm nota preenchida.")

print()
print("=" * 70)
print("5. SEGMENTAÇÃO — churn por plano, indústria, canal, trial")
print("=" * 70)


def segment_churn(field):
    seg_total = defaultdict(int)
    seg_churn = defaultdict(int)
    seg_mrr_lost = defaultdict(float)
    for a in accounts:
        key = a[field]
        seg_total[key] += 1
        if to_bool(a["churn_flag"]):
            seg_churn[key] += 1
    for key in seg_total:
        rate = seg_churn[key] / seg_total[key] * 100 if seg_total[key] else 0
        print(f"  {key:15s} total={seg_total[key]:4d}  churned={seg_churn[key]:4d}  taxa={rate:5.1f}%")


print("-- por plan_tier --")
segment_churn("plan_tier")
print("-- por industry --")
segment_churn("industry")
print("-- por referral_source --")
segment_churn("referral_source")
print("-- por is_trial --")
segment_churn("is_trial")
print("-- por country --")
segment_churn("country")

print()
print("=" * 70)
print("6. VALOR EM RISCO — MRR/ARR por conta churned, quem pesa mais")
print("=" * 70)
# Pega a assinatura MAIS RECENTE (maior start_date) de cada conta pra medir o MRR/ARR relevante
latest_sub_by_account = {}
for s in subs:
    acc = s["account_id"]
    sd = to_date(s["start_date"])
    if acc not in latest_sub_by_account or (sd and sd > to_date(latest_sub_by_account[acc]["start_date"])):
        latest_sub_by_account[acc] = s

churned_mrr = []
for acc_id in churned_accounts_set:
    s = latest_sub_by_account.get(acc_id)
    if s:
        mrr = to_float(s["mrr_amount"], 0)
        churned_mrr.append((acc_id, mrr, acc_by_id[acc_id]["account_name"], acc_by_id[acc_id]["plan_tier"]))

churned_mrr.sort(key=lambda x: -x[1])
total_mrr_lost = sum(x[1] for x in churned_mrr)
print(f"MRR total em contas churned (assinatura mais recente): ${total_mrr_lost:,.2f}/mês")
print(f"ARR equivalente: ${total_mrr_lost*12:,.2f}/ano")
print("\nTop 15 contas churned por MRR perdido:")
for acc_id, mrr, name, plan in churned_mrr[:15]:
    print(f"  {name:15s} ({plan:10s})  ${mrr:8,.2f}/mês  [{acc_id}]")

# Concentração: quanto % do MRR perdido vem do top 20% das contas churned?
n_top20 = max(1, len(churned_mrr) // 5)
top20_mrr = sum(x[1] for x in churned_mrr[:n_top20])
print(f"\nConcentração: top 20% das contas churned ({n_top20} contas) = ${top20_mrr:,.2f} = {top20_mrr/total_mrr_lost*100:.1f}% do MRR perdido total")

print()
print("=" * 70)
print("7. UPGRADE/DOWNGRADE antes do churn")
print("=" * 70)
preceding_upgrade = sum(1 for c in churn if to_bool(c["preceding_upgrade_flag"]))
preceding_downgrade = sum(1 for c in churn if to_bool(c["preceding_downgrade_flag"]))
print(f"Eventos de churn precedidos por upgrade:   {preceding_upgrade} ({preceding_upgrade/len(churn)*100:.1f}%)")
print(f"Eventos de churn precedidos por downgrade: {preceding_downgrade} ({preceding_downgrade/len(churn)*100:.1f}%)")

print()
print("=" * 70)
print("8. TEMPO ATÉ O CHURN (tenure) — por assinatura churned")
print("=" * 70)
tenures = []
for s in subs:
    if to_bool(s["churn_flag"]) and s["end_date"]:
        sd, ed = to_date(s["start_date"]), to_date(s["end_date"])
        if sd and ed:
            tenures.append((ed - sd).days)
if tenures:
    print(f"Tenure médio até churn: {mean(tenures):.0f} dias  | mediana: {median(tenures):.0f} dias")
    print(f"% que churnaram em <90 dias (early churn): {sum(1 for t in tenures if t < 90)/len(tenures)*100:.1f}%")
    print(f"% que churnaram em >365 dias: {sum(1 for t in tenures if t > 365)/len(tenures)*100:.1f}%")

print()
print("=" * 70)
print("9. CHURN AO LONGO DO TEMPO — subiu mesmo? quando?")
print("=" * 70)
churn_by_month = defaultdict(int)
for c in churn:
    d = to_date(c["churn_date"])
    if d:
        churn_by_month[(d.year, d.month)] += 1
for ym in sorted(churn_by_month):
    print(f"  {ym[0]}-{ym[1]:02d}: {churn_by_month[ym]} eventos")

print()
print("=" * 70)
print("10. FEATURE USAGE — quais features os churned menos usaram (ou mais erraram)")
print("=" * 70)
feature_usage_churned = defaultdict(lambda: {"usage": 0, "errors": 0, "events": 0})
feature_usage_active = defaultdict(lambda: {"usage": 0, "errors": 0, "events": 0})
for u in usage:
    sub_id = u["subscription_id"]
    s = sub_by_id.get(sub_id)
    if not s:
        continue
    target = feature_usage_churned if to_bool(s["churn_flag"]) else feature_usage_active
    fname = u["feature_name"]
    target[fname]["usage"] += to_float(u["usage_count"], 0)
    target[fname]["errors"] += to_float(u["error_count"], 0)
    target[fname]["events"] += 1

print("Feature        | erro% churned | erro% ativas | dif")
all_features = sorted(set(feature_usage_churned) | set(feature_usage_active))
diffs = []
for f in all_features:
    c = feature_usage_churned[f]
    a = feature_usage_active[f]
    err_c = c["errors"] / c["usage"] * 100 if c["usage"] else 0
    err_a = a["errors"] / a["usage"] * 100 if a["usage"] else 0
    diffs.append((f, err_c, err_a, err_c - err_a))
diffs.sort(key=lambda x: -x[3])
for f, ec, ea, d in diffs[:10]:
    print(f"  {f:14s}  {ec:6.2f}%       {ea:6.2f}%       {d:+.2f}pp")
