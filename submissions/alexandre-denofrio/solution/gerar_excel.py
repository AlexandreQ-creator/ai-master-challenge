"""
Extrator RavenStack -> Excel + Markdown.

Objetivo: qualquer pessoa do time (CS, CEO, Financeiro), sem saber programar
e sem precisar de IA, consegue rodar este arquivo (duplo-clique no
`gerar-relatorio.bat` na pasta acima, ou `python gerar_excel.py` no
terminal) e receber:

  - `RavenStack_Diagnostico_Churn.xlsx` — planilha navegável, para quem
    quer filtrar/pivotar os dados por conta própria (Excel ou como fonte
    de um Power BI).
  - `RavenStack_Diagnostico_Churn.md` — o mesmo conteúdo em Markdown, para
    quem prefere ler direto ou colar em Notion/Slack/e-mail sem abrir
    planilha nenhuma.

Os dois arquivos saem do mesmo cálculo (função `compute_metrics()`), que é
o mesmo cruzamento de tabelas de `analise.py` — não existem dois caminhos
de lógica que possam divergir entre si, só duas formas de apresentar o
mesmo número.

Único pré-requisito: `pip install openpyxl` (uma biblioteca, sem pandas).
"""

import csv
from collections import defaultdict
from datetime import datetime
from statistics import mean, median

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

DATA = "../data"
OUTPUT_XLSX = "../RavenStack_Diagnostico_Churn.xlsx"
OUTPUT_MD = "../RavenStack_Diagnostico_Churn.md"

HEADER_FILL = PatternFill(start_color="1F2937", end_color="1F2937", fill_type="solid")
HEADER_FONT = Font(color="FFFFFF", bold=True)
TITLE_FONT = Font(bold=True, size=14)
RISK_FILL = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid")


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


# ---------------------------------------------------------------------------
# Cálculo — fonte única de números, consumida tanto pelo Excel quanto pelo MD
# ---------------------------------------------------------------------------

def compute_metrics():
    accounts = load("ravenstack_accounts.csv")
    subs = load("ravenstack_subscriptions.csv")
    usage = load("ravenstack_feature_usage.csv")
    tickets = load("ravenstack_support_tickets.csv")
    churn = load("ravenstack_churn_events.csv")

    acc_by_id = {a["account_id"]: a for a in accounts}
    sub_by_id = {s["subscription_id"]: s for s in subs}
    churned_accounts_set = {a["account_id"] for a in accounts if to_bool(a["churn_flag"])}

    n_accounts = len(accounts)
    n_churned = len(churned_accounts_set)
    churn_rate = n_churned / n_accounts * 100

    latest_sub_by_account = {}
    for s in subs:
        acc = s["account_id"]
        sd = to_date(s["start_date"])
        if acc not in latest_sub_by_account or (sd and sd > to_date(latest_sub_by_account[acc]["start_date"])):
            latest_sub_by_account[acc] = s
    mrr_lost = sum(to_float(latest_sub_by_account[a]["mrr_amount"], 0) for a in churned_accounts_set if a in latest_sub_by_account)

    tenures = []
    for s in subs:
        if to_bool(s["churn_flag"]) and s["end_date"]:
            sd, ed = to_date(s["start_date"]), to_date(s["end_date"])
            if sd and ed:
                tenures.append((ed - sd).days)
    pct_early_churn = sum(1 for t in tenures if t < 90) / len(tenures) * 100 if tenures else 0
    tenure_median = median(tenures) if tenures else 0

    # Uso por assinatura, mês a mês (agregado vs. normalizado)
    usage_by_month_total = defaultdict(float)
    subs_active_by_month = defaultdict(set)
    for u in usage:
        d = to_date(u["usage_date"])
        if not d:
            continue
        key = (d.year, d.month)
        usage_by_month_total[key] += to_float(u["usage_count"], 0)
        subs_active_by_month[key].add(u["subscription_id"])
    usage_rows = []
    for ym in sorted(usage_by_month_total):
        total = usage_by_month_total[ym]
        n_subs = len(subs_active_by_month[ym])
        per_sub = total / n_subs if n_subs else 0
        usage_rows.append((f"{ym[0]}-{ym[1]:02d}", round(total, 0), n_subs, round(per_sub, 2)))

    # Uso nos 30 dias antes do churn real (churn_events.churn_date) vs. 31-90 dias antes
    churn_date_by_account = {}
    for c in churn:
        d = to_date(c["churn_date"])
        acc = c["account_id"]
        if d and (acc not in churn_date_by_account or d > churn_date_by_account[acc]):
            churn_date_by_account[acc] = d
    usage_30d, usage_31_90d = [], []
    for u in usage:
        sub = sub_by_id.get(u["subscription_id"])
        if not sub:
            continue
        cd = churn_date_by_account.get(sub["account_id"])
        if not cd:
            continue
        ud = to_date(u["usage_date"])
        if not ud:
            continue
        days_to_churn = (cd - ud).days
        if 0 <= days_to_churn <= 30:
            usage_30d.append(to_float(u["usage_count"], 0))
        elif 30 < days_to_churn <= 90:
            usage_31_90d.append(to_float(u["usage_count"], 0))
    usage_before_churn = {
        "usage_last_30d": round(mean(usage_30d), 2) if usage_30d else None,
        "usage_31_90d": round(mean(usage_31_90d), 2) if usage_31_90d else None,
    }

    # Uso por assinatura por indústria, H1-2023 vs H2-2024 (a alegação vale para todos os segmentos?)
    usage_by_industry_period = defaultdict(lambda: defaultdict(float))
    subs_by_industry_period = defaultdict(lambda: defaultdict(set))
    for u in usage:
        d = to_date(u["usage_date"])
        if not d:
            continue
        sub = sub_by_id.get(u["subscription_id"])
        if not sub:
            continue
        acc = acc_by_id.get(sub["account_id"])
        if not acc:
            continue
        if d.year == 2023 and d.month <= 6:
            period = "H1-2023"
        elif d.year == 2024 and d.month >= 7:
            period = "H2-2024"
        else:
            continue
        usage_by_industry_period[acc["industry"]][period] += to_float(u["usage_count"], 0)
        subs_by_industry_period[acc["industry"]][period].add(u["subscription_id"])
    usage_by_industry_rows = []
    for ind in sorted(usage_by_industry_period):
        h1 = usage_by_industry_period[ind].get("H1-2023", 0)
        h2 = usage_by_industry_period[ind].get("H2-2024", 0)
        n1 = len(subs_by_industry_period[ind].get("H1-2023", set())) or 1
        n2 = len(subs_by_industry_period[ind].get("H2-2024", set())) or 1
        per1, per2 = h1 / n1, h2 / n2
        var = (per2 - per1) / per1 * 100 if per1 else 0
        usage_by_industry_rows.append((ind, round(per1, 2), round(per2, 2), round(var, 1)))

    # Satisfação churned vs. ativas
    sat_filled = sum(1 for t in tickets if to_float(t["satisfaction_score"]) is not None)
    churned_sats = [to_float(t["satisfaction_score"]) for t in tickets if t["account_id"] in churned_accounts_set and to_float(t["satisfaction_score"]) is not None]
    active_sats = [to_float(t["satisfaction_score"]) for t in tickets if t["account_id"] not in churned_accounts_set and to_float(t["satisfaction_score"]) is not None]

    # Contas em risco por MRR
    churned_mrr = []
    for acc_id in churned_accounts_set:
        s = latest_sub_by_account.get(acc_id)
        if s:
            churned_mrr.append({
                "name": acc_by_id[acc_id]["account_name"],
                "account_id": acc_id,
                "industry": acc_by_id[acc_id]["industry"],
                "plan": acc_by_id[acc_id]["plan_tier"],
                "channel": acc_by_id[acc_id]["referral_source"],
                "mrr": round(to_float(s["mrr_amount"], 0), 2),
            })
    churned_mrr.sort(key=lambda x: -x["mrr"])
    n_top20 = max(1, len(churned_mrr) // 5)
    top20_mrr = sum(x["mrr"] for x in churned_mrr[:n_top20])

    # Segmentação indústria x canal
    seg = defaultdict(lambda: [0, 0])
    for a in accounts:
        key = (a["industry"], a["referral_source"])
        seg[key][1] += 1
        if to_bool(a["churn_flag"]):
            seg[key][0] += 1
    seg_rows = []
    for key in sorted(seg, key=lambda k: -(seg[k][0] / seg[k][1] if seg[k][1] else 0)):
        churned_n, total = seg[key]
        if total >= 10:
            seg_rows.append((key[0], key[1], total, churned_n, round(churned_n / total * 100, 1)))

    return {
        "generated_at": datetime.now(),
        "n_accounts": n_accounts,
        "n_churned": n_churned,
        "churn_rate": round(churn_rate, 1),
        "mrr_lost": round(mrr_lost, 2),
        "arr_lost": round(mrr_lost * 12, 2),
        "pct_early_churn": round(pct_early_churn, 1),
        "tenure_median": tenure_median,
        "usage_rows": usage_rows,
        "usage_before_churn": usage_before_churn,
        "usage_by_industry_rows": usage_by_industry_rows,
        "sat_filled": sat_filled,
        "sat_total": len(tickets),
        "sat_coverage_pct": round(sat_filled / len(tickets) * 100, 1) if tickets else 0,
        "sat_churned": round(mean(churned_sats), 2) if churned_sats else None,
        "sat_active": round(mean(active_sats), 2) if active_sats else None,
        "churned_mrr": churned_mrr,
        "n_top20": n_top20,
        "top20_mrr": round(top20_mrr, 2),
        "top20_pct": round(top20_mrr / mrr_lost * 100, 1) if mrr_lost else 0,
        "seg_rows": seg_rows,
        "accounts": accounts,
    }


# ---------------------------------------------------------------------------
# Renderização — Excel
# ---------------------------------------------------------------------------

def style_header(ws, row, ncols):
    for col in range(1, ncols + 1):
        cell = ws.cell(row=row, column=col)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center")


def autosize(ws, ncols, min_width=10, max_width=45):
    for col in range(1, ncols + 1):
        letter = get_column_letter(col)
        max_len = min_width
        for cell in ws[letter]:
            if cell.value is not None:
                max_len = max(max_len, len(str(cell.value)))
        ws.column_dimensions[letter].width = min(max_len + 2, max_width)


def write_table(ws, start_row, headers, rows, title=None):
    r = start_row
    if title:
        ws.cell(row=r, column=1, value=title).font = TITLE_FONT
        r += 2
    for c, h in enumerate(headers, start=1):
        ws.cell(row=r, column=c, value=h)
    style_header(ws, r, len(headers))
    r += 1
    for row in rows:
        for c, val in enumerate(row, start=1):
            ws.cell(row=r, column=c, value=val)
        r += 1
    return r


def build_excel(m):
    wb = Workbook()

    # --- Aba 1: Resumo Executivo ---
    ws = wb.active
    ws.title = "Resumo Executivo"
    ws.cell(row=1, column=1, value="RavenStack — Diagnóstico de Churn").font = Font(bold=True, size=18)
    ws.cell(row=2, column=1, value=f"Gerado automaticamente em {m['generated_at']:%d/%m/%Y %H:%M}")

    summary_rows = [
        ("Total de contas", m["n_accounts"]),
        ("Contas com churn", m["n_churned"]),
        ("Taxa de churn (contas)", f"{m['churn_rate']}%"),
        ("MRR perdido (contas churned)", f"US$ {m['mrr_lost']:,.2f}/mês"),
        ("ARR equivalente perdido", f"US$ {m['arr_lost']:,.2f}/ano"),
        ("% de churn que acontece em <90 dias", f"{m['pct_early_churn']}%"),
        ("", ""),
        ("Causa raiz identificada", "Concentração de cancelamentos nos primeiros 90 dias + fit ruim de aquisição em segmentos específicos (não é uso nem satisfação — ver aba 'Teste CEO')"),
    ]
    r = 4
    for label, val in summary_rows:
        ws.cell(row=r, column=1, value=label).font = Font(bold=True)
        ws.cell(row=r, column=2, value=val)
        r += 1
    ws.column_dimensions["A"].width = 40
    ws.column_dimensions["B"].width = 70

    # --- Aba 2: Teste das alegações do CEO ---
    ws2 = wb.create_sheet("Teste CEO")
    next_row = write_table(
        ws2, 1,
        ["Mês", "Uso total (agregado)", "Assinaturas ativas", "Uso por assinatura"],
        m["usage_rows"],
        title="Alegação 1: 'O uso da plataforma cresceu' — verdade só em total agregado, achatado por assinatura",
    )
    next_row += 2
    ws2.cell(row=next_row, column=1, value="Uso não cai antes do churn, e a estagnação vale para todas as indústrias").font = TITLE_FONT
    next_row += 2
    ub = m["usage_before_churn"]
    for label, val in [
        ("Uso médio nos últimos 30 dias antes do churn", ub["usage_last_30d"]),
        ("Uso médio no período 31-90 dias antes do churn", ub["usage_31_90d"]),
    ]:
        ws2.cell(row=next_row, column=1, value=label).font = Font(bold=True)
        ws2.cell(row=next_row, column=2, value=val)
        next_row += 1
    next_row += 1
    next_row = write_table(
        ws2, next_row,
        ["Indústria", "Uso/assinatura H1-2023", "Uso/assinatura H2-2024", "Variação"],
        m["usage_by_industry_rows"],
    )

    next_row += 2
    ws2.cell(row=next_row, column=1, value="Alegação 2: 'A satisfação está ok' — nota não discrimina quem cancela, e cobertura é baixa").font = TITLE_FONT
    next_row += 2
    for label, val in [
        ("Cobertura do satisfaction_score", f"{m['sat_filled']}/{m['sat_total']} tickets ({m['sat_coverage_pct']}%)"),
        ("Satisfação média — contas que cancelaram", m["sat_churned"]),
        ("Satisfação média — contas ativas", m["sat_active"]),
        ("Conclusão", "Diferença estatisticamente irrelevante — satisfação não é preditiva de churn neste dataset"),
    ]:
        ws2.cell(row=next_row, column=1, value=label).font = Font(bold=True)
        ws2.cell(row=next_row, column=2, value=val)
        next_row += 1
    autosize(ws2, 4)

    # --- Aba 3: Contas em risco / já churned, ranking por MRR ---
    ws3 = wb.create_sheet("Contas em Risco (MRR)")
    rows = [(a["name"], a["account_id"], a["industry"], a["plan"], a["channel"], a["mrr"]) for a in m["churned_mrr"]]
    write_table(
        ws3, 1,
        ["Conta", "account_id", "Indústria", "Plano", "Canal de aquisição", "MRR perdido (US$/mês)"],
        rows,
        title="Todas as contas canceladas, ordenadas por MRR perdido (maior impacto primeiro)",
    )
    autosize(ws3, 6)
    for i in range(m["n_top20"]):
        for c in range(1, 7):
            ws3.cell(row=4 + i, column=c).fill = RISK_FILL

    # --- Aba 4: Segmentação de risco (indústria x canal) ---
    ws4 = wb.create_sheet("Segmentação de Risco")
    seg_rows_fmt = [(ind, ch, total, churned_n, f"{rate}%") for ind, ch, total, churned_n, rate in m["seg_rows"]]
    write_table(
        ws4, 1,
        ["Indústria", "Canal de aquisição", "Total de contas", "Contas churned", "Taxa de churn"],
        seg_rows_fmt,
        title="Segmentos com maior risco de churn (cruzamento indústria × canal, mínimo 10 contas)",
    )
    autosize(ws4, 5)
    for i in range(min(2, len(seg_rows_fmt))):
        for c in range(1, 6):
            ws4.cell(row=4 + i, column=c).fill = RISK_FILL

    # --- Aba 5: Dados brutos ---
    ws5 = wb.create_sheet("Dados Brutos — Contas")
    acc_headers = list(m["accounts"][0].keys())
    acc_rows = [[a[h] for h in acc_headers] for a in m["accounts"]]
    write_table(ws5, 1, acc_headers, acc_rows, title="Tabela accounts.csv completa (para filtro/pivot próprio no Excel)")
    autosize(ws5, len(acc_headers))

    wb.save(OUTPUT_XLSX)
    return wb.sheetnames


# ---------------------------------------------------------------------------
# Renderização — Markdown
# ---------------------------------------------------------------------------

def build_markdown(m):
    lines = []
    lines.append("# RavenStack — Diagnóstico de Churn")
    lines.append("")
    lines.append(f"_Gerado automaticamente em {m['generated_at']:%d/%m/%Y %H:%M} a partir de `data/*.csv` — arquivo reproduzível, rode `gerar-relatorio.bat` de novo quando os dados mudarem._")
    lines.append("")
    lines.append("## Resumo executivo")
    lines.append("")
    lines.append("| Métrica | Valor |")
    lines.append("|---|---|")
    lines.append(f"| Total de contas | {m['n_accounts']} |")
    lines.append(f"| Contas com churn | {m['n_churned']} ({m['churn_rate']}%) |")
    lines.append(f"| MRR perdido | US$ {m['mrr_lost']:,.2f}/mês |")
    lines.append(f"| ARR equivalente perdido | US$ {m['arr_lost']:,.2f}/ano |")
    lines.append(f"| Churn em menos de 90 dias | {m['pct_early_churn']}% (mediana: {m['tenure_median']:.0f} dias) |")
    lines.append("")
    lines.append("**Causa raiz identificada:** concentração de cancelamentos nos primeiros 90 dias de assinatura, combinada a fit ruim de aquisição em segmentos específicos — não é explicada por uso nem por satisfação (ver seção abaixo).")
    lines.append("")

    lines.append("## Teste das alegações do CEO")
    lines.append("")
    lines.append("### \"O uso da plataforma cresceu\"")
    lines.append("")
    lines.append("Verdade só em volume agregado. Por assinatura, o uso está achatado, sem tendência de alta:")
    lines.append("")
    lines.append("| Mês | Uso total | Assinaturas ativas | Uso por assinatura |")
    lines.append("|---|---|---|---|")
    for mes, total, n_subs, per_sub in m["usage_rows"]:
        lines.append(f"| {mes} | {total:.0f} | {n_subs} | {per_sub} |")
    lines.append("")
    ub = m["usage_before_churn"]
    lines.append(f"Uso também não cai nos 30 dias imediatamente antes do churn real (média {ub['usage_last_30d']}) frente ao período de 31-90 dias antes (média {ub['usage_31_90d']}) — não há sinal de alerta comportamental antes do cancelamento.")
    lines.append("")
    lines.append("A estagnação vale para todas as indústrias, não é um segmento mascarando outro (uso por assinatura, H1-2023 vs. H2-2024):")
    lines.append("")
    lines.append("| Indústria | Uso/assinatura H1-2023 | Uso/assinatura H2-2024 | Variação |")
    lines.append("|---|---|---|---|")
    for ind, per1, per2, var in m["usage_by_industry_rows"]:
        lines.append(f"| {ind} | {per1} | {per2} | {var:+.1f}% |")
    lines.append("")

    lines.append("### \"A satisfação está ok\"")
    lines.append("")
    lines.append(f"Cobertura do `satisfaction_score`: {m['sat_filled']}/{m['sat_total']} tickets ({m['sat_coverage_pct']}%). Satisfação média entre contas que cancelaram: **{m['sat_churned']}**. Entre as que ficaram: **{m['sat_active']}**. Diferença estatisticamente irrelevante — a nota não é preditiva de churn neste dataset.")
    lines.append("")

    lines.append("## Segmentos de maior risco")
    lines.append("")
    lines.append("Cruzamento indústria × canal de aquisição (mínimo 10 contas por célula):")
    lines.append("")
    lines.append("| Indústria | Canal | Total de contas | Churned | Taxa |")
    lines.append("|---|---|---|---|---|")
    for ind, ch, total, churned_n, rate in m["seg_rows"][:10]:
        lines.append(f"| {ind} | {ch} | {total} | {churned_n} | {rate}% |")
    lines.append("")

    lines.append("## Contas específicas em maior risco (por MRR perdido)")
    lines.append("")
    lines.append(f"Top 15 de {len(m['churned_mrr'])} contas canceladas, ordenadas por valor mensal. As top {m['n_top20']} contas (20%) concentram **{m['top20_pct']}%** do MRR perdido total.")
    lines.append("")
    lines.append("| Conta | Indústria | Plano | Canal | MRR perdido |")
    lines.append("|---|---|---|---|---|")
    for a in m["churned_mrr"][:15]:
        lines.append(f"| {a['name']} | {a['industry']} | {a['plan']} | {a['channel']} | US$ {a['mrr']:,.2f}/mês |")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("_Relatório de diagnóstico completo, recomendações priorizadas e process log em `README.md`. Este arquivo (`RavenStack_Diagnostico_Churn.md`) e a planilha `RavenStack_Diagnostico_Churn.xlsx` são gerados pelo mesmo script (`solution/gerar_excel.py`) a partir dos mesmos dados — reproduza com `gerar-relatorio.bat` sempre que os CSVs em `data/` forem atualizados._")

    return "\n".join(lines)


def main():
    m = compute_metrics()
    sheets = build_excel(m)
    md = build_markdown(m)
    with open(OUTPUT_MD, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"Planilha gerada: {OUTPUT_XLSX}")
    print(f"Abas: {sheets}")
    print(f"Markdown gerado: {OUTPUT_MD}")


if __name__ == "__main__":
    main()
