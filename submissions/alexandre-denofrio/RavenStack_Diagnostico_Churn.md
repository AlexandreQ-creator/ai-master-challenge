# RavenStack — Diagnóstico de Churn

_Gerado automaticamente em 14/09/2026 20:34 a partir de `data/*.csv` — arquivo reproduzível, rode `gerar-relatorio.bat` de novo quando os dados mudarem._

## Resumo executivo

| Métrica | Valor |
|---|---|
| Total de contas | 500 |
| Contas com churn | 110 (22.0%) |
| MRR perdido | US$ 255,442.00/mês |
| ARR equivalente perdido | US$ 3,065,304.00/ano |
| Churn em menos de 90 dias | 67.9% (mediana: 42 dias) |

**Causa raiz identificada:** concentração de cancelamentos nos primeiros 90 dias de assinatura, combinada a fit ruim de aquisição em segmentos específicos — não é explicada por uso nem por satisfação (ver seção abaixo).

## Teste das alegações do CEO

### "O uso da plataforma cresceu"

Verdade só em volume agregado. Por assinatura, o uso está achatado, sem tendência de alta:

| Mês | Uso total | Assinaturas ativas | Uso por assinatura |
|---|---|---|---|
| 2023-01 | 10877 | 969 | 11.22 |
| 2023-02 | 9492 | 875 | 10.85 |
| 2023-03 | 11031 | 989 | 11.15 |
| 2023-04 | 10369 | 932 | 11.13 |
| 2023-05 | 10757 | 978 | 11.0 |
| 2023-06 | 10002 | 907 | 11.03 |
| 2023-07 | 11083 | 960 | 11.54 |
| 2023-08 | 10335 | 953 | 10.84 |
| 2023-09 | 9737 | 878 | 11.09 |
| 2023-10 | 10968 | 971 | 11.3 |
| 2023-11 | 9475 | 868 | 10.92 |
| 2023-12 | 10435 | 945 | 11.04 |
| 2024-01 | 10621 | 949 | 11.19 |
| 2024-02 | 10247 | 931 | 11.01 |
| 2024-03 | 10725 | 963 | 11.14 |
| 2024-04 | 10131 | 922 | 10.99 |
| 2024-05 | 10552 | 938 | 11.25 |
| 2024-06 | 10106 | 915 | 11.04 |
| 2024-07 | 10601 | 959 | 11.05 |
| 2024-08 | 10559 | 958 | 11.02 |
| 2024-09 | 10195 | 918 | 11.11 |
| 2024-10 | 11450 | 1027 | 11.15 |
| 2024-11 | 10039 | 905 | 11.09 |
| 2024-12 | 10738 | 973 | 11.04 |

Uso também não cai nos 30 dias imediatamente antes do churn real (média 9.84) frente ao período de 31-90 dias antes (média 10.04) — não há sinal de alerta comportamental antes do cancelamento.

A estagnação vale para todas as indústrias, não é um segmento mascarando outro (uso por assinatura, H1-2023 vs. H2-2024):

| Indústria | Uso/assinatura H1-2023 | Uso/assinatura H2-2024 | Variação |
|---|---|---|---|
| Cybersecurity | 18.16 | 17.82 | -1.9% |
| DevTools | 17.24 | 16.58 | -3.8% |
| EdTech | 17.46 | 17.99 | +3.0% |
| FinTech | 17.5 | 17.76 | +1.4% |
| HealthTech | 17.03 | 17.69 | +3.8% |

### "A satisfação está ok"

Cobertura do `satisfaction_score`: 1175/2000 tickets (58.8%). Satisfação média entre contas que cancelaram: **4.01**. Entre as que ficaram: **3.97**. Diferença estatisticamente irrelevante — a nota não é preditiva de churn neste dataset.

## Segmentos de maior risco

Cruzamento indústria × canal de aquisição (mínimo 10 contas por célula):

| Indústria | Canal | Total de contas | Churned | Taxa |
|---|---|---|---|---|
| DevTools | event | 23 | 10 | 43.5% |
| DevTools | ads | 26 | 10 | 38.5% |
| HealthTech | partner | 14 | 5 | 35.7% |
| FinTech | ads | 22 | 7 | 31.8% |
| HealthTech | event | 16 | 5 | 31.2% |
| DevTools | other | 24 | 7 | 29.2% |
| DevTools | organic | 24 | 6 | 25.0% |
| Cybersecurity | other | 20 | 5 | 25.0% |
| FinTech | other | 25 | 6 | 24.0% |
| EdTech | other | 17 | 4 | 23.5% |

## Contas específicas em maior risco (por MRR perdido)

Top 15 de 110 contas canceladas, ordenadas por valor mensal. As top 22 contas (20%) concentram **62.1%** do MRR perdido total.

| Conta | Indústria | Plano | Canal | MRR perdido |
|---|---|---|---|---|
| Company_4 | HealthTech | Enterprise | event | US$ 21,691.00/mês |
| Company_99 | FinTech | Enterprise | other | US$ 11,144.00/mês |
| Company_240 | FinTech | Enterprise | event | US$ 10,945.00/mês |
| Company_27 | HealthTech | Basic | partner | US$ 9,751.00/mês |
| Company_84 | DevTools | Pro | event | US$ 9,154.00/mês |
| Company_234 | FinTech | Pro | organic | US$ 8,756.00/mês |
| Company_171 | Cybersecurity | Pro | event | US$ 7,960.00/mês |
| Company_68 | FinTech | Pro | ads | US$ 7,164.00/mês |
| Company_42 | EdTech | Pro | organic | US$ 6,766.00/mês |
| Company_115 | FinTech | Enterprise | partner | US$ 6,766.00/mês |
| Company_497 | DevTools | Basic | organic | US$ 6,567.00/mês |
| Company_140 | HealthTech | Basic | partner | US$ 6,169.00/mês |
| Company_125 | DevTools | Basic | organic | US$ 5,970.00/mês |
| Company_400 | FinTech | Pro | other | US$ 5,572.00/mês |
| Company_195 | EdTech | Basic | other | US$ 5,572.00/mês |

---

_Relatório de diagnóstico completo, recomendações priorizadas e process log em `README.md`. Este arquivo (`RavenStack_Diagnostico_Churn.md`) e a planilha `RavenStack_Diagnostico_Churn.xlsx` são gerados pelo mesmo script (`solution/gerar_excel.py`) a partir dos mesmos dados — reproduza com `gerar-relatorio.bat` sempre que os CSVs em `data/` forem atualizados._