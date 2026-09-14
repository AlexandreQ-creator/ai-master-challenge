"""
Gera o dashboard HTML (`../dashboard.html`) a partir dos mesmos dados de
`analise.py` / `gerar_excel.py`. Standalone: abre com duplo-clique em
qualquer navegador, sem servidor, sem instalar nada além do Python usado
para gerar o arquivo uma vez.
"""

import csv
import json
from collections import defaultdict
from datetime import datetime
from statistics import mean

from gap_analysis_feedback import analisar as analisar_feedback

DATA = "../data"
OUTPUT = "../dashboard.html"


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


def build_data():
    accounts = load("ravenstack_accounts.csv")
    subs = load("ravenstack_subscriptions.csv")
    usage = load("ravenstack_feature_usage.csv")
    tickets = load("ravenstack_support_tickets.csv")
    churn = load("ravenstack_churn_events.csv")

    churned_set = {a["account_id"] for a in accounts if to_bool(a["churn_flag"])}
    out = {}

    cbm = defaultdict(int)
    for c in churn:
        d = to_date(c["churn_date"])
        if d:
            cbm[f"{d.year}-{d.month:02d}"] += 1
    out["churn_by_month"] = dict(sorted(cbm.items()))

    sbm = defaultdict(int)
    for a in accounts:
        d = to_date(a["signup_date"])
        if d:
            sbm[f"{d.year}-{d.month:02d}"] += 1
    cum, cum_accounts = 0, {}
    for k in sorted(sbm):
        cum += sbm[k]
        cum_accounts[k] = cum
    out["cumulative_accounts"] = cum_accounts

    ubm_total = defaultdict(float)
    ubm_subs = defaultdict(set)
    for u in usage:
        d = to_date(u["usage_date"])
        if not d:
            continue
        k = f"{d.year}-{d.month:02d}"
        ubm_total[k] += to_float(u["usage_count"], 0)
        ubm_subs[k].add(u["subscription_id"])
    out["usage_per_sub"] = {k: round(ubm_total[k] / len(ubm_subs[k]), 2) for k in sorted(ubm_total)}

    tenures = []
    for s in subs:
        if to_bool(s["churn_flag"]) and s["end_date"]:
            sd, ed = to_date(s["start_date"]), to_date(s["end_date"])
            if sd and ed:
                tenures.append((ed - sd).days)
    buckets = {"0-30d": 0, "31-90d": 0, "91-180d": 0, "181-365d": 0, "365d+": 0}
    for t in tenures:
        if t <= 30:
            buckets["0-30d"] += 1
        elif t <= 90:
            buckets["31-90d"] += 1
        elif t <= 180:
            buckets["91-180d"] += 1
        elif t <= 365:
            buckets["181-365d"] += 1
        else:
            buckets["365d+"] += 1
    out["tenure_buckets"] = buckets
    out["pct_early_churn"] = round(sum(1 for t in tenures if t < 90) / len(tenures) * 100, 1) if tenures else 0

    seg = defaultdict(lambda: [0, 0])
    for a in accounts:
        key = f"{a['industry']} / {a['referral_source']}"
        seg[key][1] += 1
        if to_bool(a["churn_flag"]):
            seg[key][0] += 1
    seg_list = [(k, v[0], v[1], round(v[0] / v[1] * 100, 1)) for k, v in seg.items() if v[1] >= 10]
    seg_list.sort(key=lambda x: -x[3])
    out["segmentation"] = seg_list

    churned_sat = [to_float(t["satisfaction_score"]) for t in tickets if t["account_id"] in churned_set and to_float(t["satisfaction_score"]) is not None]
    active_sat = [to_float(t["satisfaction_score"]) for t in tickets if t["account_id"] not in churned_set and to_float(t["satisfaction_score"]) is not None]
    out["satisfaction"] = {
        "churned": round(mean(churned_sat), 2) if churned_sat else 0,
        "active": round(mean(active_sat), 2) if active_sat else 0,
        "coverage_pct": round(sum(1 for t in tickets if to_float(t["satisfaction_score"]) is not None) / len(tickets) * 100, 1),
    }

    latest_sub = {}
    for s in subs:
        acc = s["account_id"]
        sd = to_date(s["start_date"])
        if acc not in latest_sub or (sd and sd > to_date(latest_sub[acc]["start_date"])):
            latest_sub[acc] = s
    acc_by_id = {a["account_id"]: a for a in accounts}
    churned_mrr = []
    for acc_id in churned_set:
        s = latest_sub.get(acc_id)
        if s:
            churned_mrr.append({
                "name": acc_by_id[acc_id]["account_name"],
                "industry": acc_by_id[acc_id]["industry"],
                "plan": acc_by_id[acc_id]["plan_tier"],
                "mrr": to_float(s["mrr_amount"], 0),
            })
    churned_mrr.sort(key=lambda x: -x["mrr"])
    out["top_accounts"] = churned_mrr[:15]
    out["total_mrr_lost"] = round(sum(x["mrr"] for x in churned_mrr), 2)
    out["n_accounts"] = len(accounts)
    out["n_churned"] = len(churned_set)
    out["churn_rate"] = round(len(churned_set) / len(accounts) * 100, 1)

    # O momento Aha! (achado 7 do README): reason_code é estatisticamente
    # independente do que o cliente escreveu em feedback_text. Reaproveita
    # a mesma função de análise de gap_analysis_feedback.py — não duplica
    # o cálculo do qui-quadrado, só consome o resultado já validado.
    out["achado_reason_code"] = analisar_feedback()

    return out


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<title>RavenStack — Diagnóstico de Churn</title>
<style>
  :root {{
    --bg: #f8f9fb; --card: #ffffff; --ink: #1a1d29; --muted: #6b7280;
    --accent: #dc2626; --accent-soft: #fee2e2; --line: #e5e7eb;
    --good: #059669;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 32px 20px; background: var(--bg); color: var(--ink);
    font-family: -apple-system, "Segoe UI", Arial, sans-serif;
  }}
  .wrap {{ max-width: 1100px; margin: 0 auto; }}
  h1 {{ font-size: 26px; margin: 0 0 4px; }}
  .subtitle {{ color: var(--muted); margin: 0 0 28px; font-size: 14px; }}
  .kpi-row {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px,1fr)); gap: 14px; margin-bottom: 28px; }}
  .kpi {{ background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: 16px 18px; }}
  .kpi .label {{ font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: .04em; }}
  .kpi .value {{ font-size: 26px; font-weight: 700; margin-top: 4px; }}
  .kpi .value.risk {{ color: var(--accent); }}
  section {{ background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 22px 24px; margin-bottom: 20px; }}
  section h2 {{ font-size: 16px; margin: 0 0 4px; }}
  section .desc {{ color: var(--muted); font-size: 13px; margin: 0 0 16px; }}
  .grid2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
  @media (max-width: 800px) {{ .grid2 {{ grid-template-columns: 1fr; }} }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th, td {{ text-align: left; padding: 7px 10px; border-bottom: 1px solid var(--line); }}
  th {{ color: var(--muted); font-weight: 600; font-size: 11px; text-transform: uppercase; }}
  tr.risk td {{ background: var(--accent-soft); }}
  .bar-row {{ display: flex; align-items: center; gap: 10px; margin: 6px 0; font-size: 13px; }}
  .bar-label {{ width: 90px; flex-shrink: 0; color: var(--muted); }}
  .bar-track {{ flex: 1; background: #f1f2f5; border-radius: 4px; height: 18px; overflow: hidden; }}
  .bar-fill {{ height: 100%; background: var(--accent); border-radius: 4px; }}
  .bar-fill.good {{ background: var(--good); }}
  .bar-val {{ width: 50px; text-align: right; font-variant-numeric: tabular-nums; }}
  footer {{ color: var(--muted); font-size: 12px; text-align: center; margin-top: 24px; }}
  canvas {{ max-width: 100%; }}
  .update-bar {{ display: flex; align-items: center; gap: 10px; margin-bottom: 24px; flex-wrap: wrap; }}
  .update-bar button {{
    background: var(--ink); color: #fff; border: none; border-radius: 8px;
    padding: 9px 16px; font-size: 13px; cursor: pointer; font-weight: 600;
  }}
  .update-bar button:disabled {{ background: #c7cad1; cursor: not-allowed; }}
  .update-bar .hint {{ font-size: 12px; color: var(--muted); }}
  .update-bar .hint code {{ background: #f1f2f5; padding: 1px 5px; border-radius: 4px; }}
  .update-bar .msg {{ font-size: 13px; font-weight: 600; }}
  .update-bar .msg.ok {{ color: var(--good); }}
  .update-bar .msg.erro {{ color: var(--accent); }}
  .aha {{
    background: linear-gradient(135deg, #1a1d29 0%, #2d1520 100%);
    color: #fff; border-radius: 14px; padding: 26px 28px; margin-bottom: 22px;
    border: 1px solid #3a2530;
  }}
  .aha .tag {{
    display: inline-block; background: var(--accent); color: #fff; font-size: 11px;
    font-weight: 700; text-transform: uppercase; letter-spacing: .06em;
    padding: 3px 10px; border-radius: 20px; margin-bottom: 10px;
  }}
  .aha h2 {{ font-size: 19px; margin: 0 0 10px; color: #fff; }}
  .aha p {{ font-size: 13.5px; line-height: 1.6; color: #d8dae0; margin: 0 0 14px; }}
  .aha p:last-child {{ margin-bottom: 0; }}
  .aha .compare {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin: 16px 0; }}
  @media (max-width: 700px) {{ .aha .compare {{ grid-template-columns: 1fr; }} }}
  .aha .col {{ background: rgba(255,255,255,.06); border-radius: 10px; padding: 14px 16px; }}
  .aha .col .col-title {{ font-size: 11px; text-transform: uppercase; letter-spacing: .04em; color: #9aa0ad; margin-bottom: 8px; }}
  .aha .col .row {{ display: flex; justify-content: space-between; font-size: 13px; padding: 4px 0; border-bottom: 1px solid rgba(255,255,255,.08); }}
  .aha .col .row:last-child {{ border-bottom: none; }}
  .aha .col .row .lead {{ color: #fca5a5; font-weight: 700; }}
  .aha .stat {{ font-size: 12.5px; color: #9aa0ad; }}
  .aha .stat b {{ color: #fff; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>RavenStack — Diagnóstico de Churn</h1>
  <p class="subtitle">Gerado automaticamente a partir de data/*.csv — Challenge 001, AI Master G4 Educação. Ver README.md para a análise completa e recomendações.</p>

  <div class="update-bar">
    <button id="btnAtualizar" onclick="atualizarDados()">Atualizar dados</button>
    <span class="hint" id="hintAtualizar">Reprocessa os CSVs de <code>data/</code> e regrava este dashboard <b>e</b> a planilha Excel a partir da mesma fonte — prova que os dois nunca divergem.</span>
    <span class="msg" id="msgAtualizar"></span>
  </div>

  <div class="kpi-row">
    <div class="kpi"><div class="label">Contas totais</div><div class="value">{n_accounts}</div></div>
    <div class="kpi"><div class="label">Contas com churn</div><div class="value risk">{n_churned} ({churn_rate}%)</div></div>
    <div class="kpi"><div class="label">MRR perdido</div><div class="value risk">${total_mrr_lost:,.0f}/mês</div></div>
    <div class="kpi"><div class="label">Churn em &lt;90 dias</div><div class="value risk">{pct_early_churn}%</div></div>
  </div>

  <div class="aha">
    <span class="tag">Momento Aha</span>
    <h2>O motivo de cancelamento que a RavenStack enxerga não é o motivo real</h2>
    <p>A tabela de eventos de churn tem duas colunas sobre o motivo: <code>reason_code</code> (o que o sistema registrou) e <code>feedback_text</code> (o que o cliente escreveu). Cruzando as duas, elas são <strong>estatisticamente independentes</strong> — um cliente que escreveu "too expensive" foi classificado como <code>pricing</code> em apenas {aha_concordancia}% dos casos, contra {aha_acaso}% que se esperaria sorteando ao acaso entre os 6 códigos (χ² = {aha_chi2}, gl = {aha_gl}).</p>
    <div class="compare">
      <div class="col">
        <div class="col-title">O que a empresa enxerga (reason_code)</div>
        {aha_reason_code_rows}
      </div>
      <div class="col">
        <div class="col-title">O que o cliente de fato disse (feedback_text)</div>
        {aha_feedback_rows}
      </div>
    </div>
    <p class="stat">{aha_pct_com_feedback}% dos {aha_n_eventos} eventos de churn têm <code>feedback_text</code> preenchido — <b>preço lidera com {aha_top_pct}%</b>, o dobro do que o <code>reason_code</code> sugere. Detalhe completo e a correção metodológica (o achado não é "um campo quebrado", é dataset sem estrutura categórica — ver auditor genérico) no README, achado 7.</p>
  </div>

  <section>
    <h2>O paradoxo do CEO: "uso cresceu" e "satisfação está ok" — nenhum dos dois é sinal confiável</h2>
    <p class="desc">Uso por assinatura (normalizado, não o total agregado) e satisfação entre contas que cancelaram vs. que ficaram.</p>
    <div class="grid2">
      <div>
        <strong style="font-size:13px;">Uso por assinatura ao longo do tempo (achatado, sem tendência de alta)</strong>
        <canvas id="usageChart" height="140"></canvas>
      </div>
      <div>
        <strong style="font-size:13px;">Satisfação média (escala 0-10)</strong>
        <div class="bar-row"><div class="bar-label">Churned</div><div class="bar-track"><div class="bar-fill" style="width:{sat_churned_pct}%"></div></div><div class="bar-val">{sat_churned}</div></div>
        <div class="bar-row"><div class="bar-label">Ativas</div><div class="bar-track"><div class="bar-fill good" style="width:{sat_active_pct}%"></div></div><div class="bar-val">{sat_active}</div></div>
        <p class="desc" style="margin-top:10px;">Cobertura do score: apenas {sat_coverage}% dos tickets têm nota preenchida — diferença entre os grupos não é confiável como sinal de risco.</p>
      </div>
    </div>
  </section>

  <section>
    <h2>Churn está acelerando — muito além do crescimento da base de contas</h2>
    <p class="desc">Eventos de churn por mês vs. crescimento cumulativo de contas no mesmo período.</p>
    <canvas id="churnChart" height="90"></canvas>
  </section>

  <div class="grid2">
    <section>
      <h2>Quando o cliente cancela (tenure)</h2>
      <p class="desc">{pct_early_churn}% dos cancelamentos acontecem nos primeiros 90 dias.</p>
      <canvas id="tenureChart" height="180"></canvas>
    </section>
    <section>
      <h2>Segmentos de maior risco</h2>
      <p class="desc">Indústria × canal de aquisição, mínimo 10 contas por célula.</p>
      <table>
        <thead><tr><th>Segmento</th><th>Contas</th><th>Churned</th><th>Taxa</th></tr></thead>
        <tbody>{segmentation_rows}</tbody>
      </table>
    </section>
  </div>

  <section>
    <h2>Contas específicas em maior risco (por MRR perdido)</h2>
    <p class="desc">Top 15 contas já canceladas, ordenadas por valor mensal — linhas em vermelho = top 20% concentram a maior parte do valor perdido.</p>
    <table>
      <thead><tr><th>Conta</th><th>Indústria</th><th>Plano</th><th>MRR perdido</th></tr></thead>
      <tbody>{accounts_rows}</tbody>
    </table>
  </section>

  <footer>Relatório de diagnóstico completo, recomendações e process log em README.md. Dados: dataset Kaggle "SaaS Subscription &amp; Churn Analytics" (MIT).</footer>
</div>

<script>
const usageData = {usage_json};
const churnData = {churn_json};
const cumAccountsData = {cum_accounts_json};
const tenureData = {tenure_json};

function drawLineChart(canvasId, labels, series, color) {{
  const canvas = document.getElementById(canvasId);
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.clientWidth, h = canvas.clientHeight || 140;
  canvas.width = w * dpr; canvas.height = h * dpr;
  ctx.scale(dpr, dpr);
  const pad = {{l: 36, r: 10, t: 10, b: 20}};
  const max = Math.max(...series) * 1.15;
  const min = 0;
  const plotW = w - pad.l - pad.r, plotH = h - pad.t - pad.b;
  ctx.strokeStyle = '#e5e7eb'; ctx.lineWidth = 1;
  for (let i = 0; i <= 3; i++) {{
    const y = pad.t + plotH - (plotH * i / 3);
    ctx.beginPath(); ctx.moveTo(pad.l, y); ctx.lineTo(w - pad.r, y); ctx.stroke();
    ctx.fillStyle = '#9ca3af'; ctx.font = '10px sans-serif';
    ctx.fillText(Math.round(max * i / 3), 2, y + 3);
  }}
  ctx.strokeStyle = color; ctx.lineWidth = 2; ctx.beginPath();
  series.forEach((v, i) => {{
    const x = pad.l + (plotW * i / (series.length - 1));
    const y = pad.t + plotH - (plotH * (v - min) / (max - min));
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  }});
  ctx.stroke();
  ctx.fillStyle = '#9ca3af'; ctx.font = '10px sans-serif';
  [0, Math.floor(labels.length/2), labels.length-1].forEach(i => {{
    const x = pad.l + (plotW * i / (series.length - 1));
    ctx.fillText(labels[i], Math.max(pad.l, x - 15), h - 4);
  }});
}}

function drawBarChart(canvasId, labels, series, color) {{
  const canvas = document.getElementById(canvasId);
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.clientWidth, h = canvas.clientHeight || 180;
  canvas.width = w * dpr; canvas.height = h * dpr;
  ctx.scale(dpr, dpr);
  const pad = {{l: 36, r: 10, t: 10, b: 26}};
  const max = Math.max(...series) * 1.15;
  const plotW = w - pad.l - pad.r, plotH = h - pad.t - pad.b;
  const barW = plotW / series.length * 0.6;
  const gap = plotW / series.length;
  series.forEach((v, i) => {{
    const barH = plotH * (v / max);
    const x = pad.l + gap * i + (gap - barW) / 2;
    const y = pad.t + plotH - barH;
    ctx.fillStyle = color;
    ctx.fillRect(x, y, barW, barH);
    ctx.fillStyle = '#374151'; ctx.font = '11px sans-serif'; ctx.textAlign = 'center';
    ctx.fillText(v, x + barW/2, y - 4);
    ctx.fillStyle = '#9ca3af'; ctx.font = '10px sans-serif';
    ctx.fillText(labels[i], x + barW/2, h - 8);
  }});
  ctx.textAlign = 'left';
}}

const usageLabels = Object.keys(usageData);
const usageValues = Object.values(usageData);
drawLineChart('usageChart', usageLabels, usageValues, '#1a1d29');

const churnLabels = Object.keys(churnData);
const churnValues = Object.values(churnData);
drawLineChart('churnChart', churnLabels, churnValues, '#dc2626');

const tenureLabels = Object.keys(tenureData);
const tenureValues = Object.values(tenureData);
drawBarChart('tenureChart', tenureLabels, tenureValues, '#dc2626');

// Botão "Atualizar dados": só funciona quando servido por servidor_dashboard.py
// (http://), porque um arquivo aberto via file:// não pode disparar um
// processo Python no disco -- o navegador bloqueia por segurança. Detecta
// o protocolo e desabilita com uma explicação em vez de falhar em silêncio
// ou mostrar um botão morto.
(function initBotaoAtualizar() {{
  const btn = document.getElementById('btnAtualizar');
  const hint = document.getElementById('hintAtualizar');
  const msg = document.getElementById('msgAtualizar');
  const servidoPorHttp = location.protocol === 'http:' || location.protocol === 'https:';

  if (!servidoPorHttp) {{
    btn.disabled = true;
    hint.innerHTML = 'Desabilitado neste modo (<code>file://</code>). Rode <code>python solution/servidor_dashboard.py</code> para habilitar, ou <code>gerar-relatorio.bat</code> e reabra este arquivo.';
    return;
  }}
  hint.textContent = 'Reprocessa os CSVs de data/ e regrava este dashboard e a planilha Excel a partir da mesma fonte — prova que os dois nunca divergem.';
}})();

async function atualizarDados() {{
  const btn = document.getElementById('btnAtualizar');
  const msg = document.getElementById('msgAtualizar');
  btn.disabled = true;
  msg.className = 'msg';
  msg.textContent = 'Atualizando...';
  try {{
    const resp = await fetch('/api/atualizar', {{ method: 'POST' }});
    const dados = await resp.json();
    if (dados.sucesso) {{
      if (dados.excel_aviso) {{
        msg.className = 'msg erro';
        msg.textContent = dados.excel_aviso;
        btn.disabled = false;
      }} else {{
        msg.className = 'msg ok';
        msg.textContent = 'Dashboard e RavenStack_Diagnostico_Churn.xlsx atualizados a partir da mesma fonte. Recarregando...';
        setTimeout(() => location.reload(), 1100);
      }}
    }} else {{
      msg.className = 'msg erro';
      const detalhe = dados.erros ? dados.erros.join('; ') : (dados.saida || 'erro desconhecido');
      msg.textContent = 'Falhou (' + dados.etapa + '): ' + detalhe;
      btn.disabled = false;
    }}
  }} catch (e) {{
    msg.className = 'msg erro';
    msg.textContent = 'Não foi possível conectar ao servidor local.';
    btn.disabled = false;
  }}
}}
</script>
</body>
</html>
"""


def render(data):
    seg_rows = ""
    for i, (name, churned_n, total, rate) in enumerate(data["segmentation"][:8]):
        cls = ' class="risk"' if i < 2 else ""
        seg_rows += f"<tr{cls}><td>{name}</td><td>{total}</td><td>{churned_n}</td><td>{rate}%</td></tr>"

    acc_rows = ""
    n_top20 = max(1, len(data["top_accounts"]) // 5)
    for i, acc in enumerate(data["top_accounts"]):
        cls = ' class="risk"' if i < n_top20 else ""
        acc_rows += f'<tr{cls}><td>{acc["name"]}</td><td>{acc["industry"]}</td><td>{acc["plan"]}</td><td>${acc["mrr"]:,.2f}/mês</td></tr>'

    sat = data["satisfaction"]

    aha = data["achado_reason_code"]
    rc_rows = ""
    for cod, n in sorted(aha["distribuicao_reason_code"].items(), key=lambda x: -x[1]):
        pct = n / aha["n_eventos_churn"] * 100
        rc_rows += f'<div class="row"><span>{cod}</span><span>{pct:.1f}%</span></div>'
    fb_rows = ""
    top_texto, top_n = max(aha["distribuicao_real_feedback"].items(), key=lambda x: x[1])
    for texto, n in sorted(aha["distribuicao_real_feedback"].items(), key=lambda x: -x[1]):
        pct = n / aha["n_com_feedback"] * 100
        cls = ' class="lead"' if texto == top_texto else ""
        fb_rows += f'<div class="row"><span{cls}>{texto}</span><span{cls}>{pct:.1f}%</span></div>'
    aha_top_pct = round(top_n / aha["n_com_feedback"] * 100, 1)

    html = HTML_TEMPLATE.format(
        n_accounts=data["n_accounts"],
        n_churned=data["n_churned"],
        churn_rate=data["churn_rate"],
        total_mrr_lost=data["total_mrr_lost"],
        pct_early_churn=data["pct_early_churn"],
        sat_churned=sat["churned"],
        sat_active=sat["active"],
        sat_churned_pct=sat["churned"] / 10 * 100,
        sat_active_pct=sat["active"] / 10 * 100,
        sat_coverage=sat["coverage_pct"],
        segmentation_rows=seg_rows,
        accounts_rows=acc_rows,
        usage_json=json.dumps(data["usage_per_sub"]),
        churn_json=json.dumps(data["churn_by_month"]),
        cum_accounts_json=json.dumps(data["cumulative_accounts"]),
        tenure_json=json.dumps(data["tenure_buckets"]),
        aha_concordancia=aha["concordancia_pct"],
        aha_acaso=aha["concordancia_acaso_pct"],
        aha_chi2=aha["chi2"],
        aha_gl=aha["graus_liberdade"],
        aha_reason_code_rows=rc_rows,
        aha_feedback_rows=fb_rows,
        aha_pct_com_feedback=aha["pct_com_feedback"],
        aha_n_eventos=aha["n_eventos_churn"],
        aha_top_pct=aha_top_pct,
    )
    return html


if __name__ == "__main__":
    data = build_data()
    html = render(data)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Dashboard gerado: {OUTPUT}")
