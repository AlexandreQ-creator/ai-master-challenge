"""
Harness de consistência entre artefatos — extração até o dashboard.

O harness_auditoria_submissao.py já testa se o CONTEÚDO do README cobre o
brief oficial. Este harness testa uma coisa diferente e complementar: se o
MESMO número aparece igual em todos os formatos de saída — o Excel, o
dashboard HTML, e a resposta da IA de consulta — comparados contra
compute_metrics(), a fonte única de verdade.

Isso é o "piloto de teste do processo, da extração de dados até o
dashboard" pedido: em vez de confiar que "os quatro artefatos vêm da mesma
fonte, então não podem divergir" (afirmação no README), este harness
VERIFICA isso de fato, extraindo o mesmo número por 4 caminhos
independentes e comparando.

Números-âncora escolhidos por serem citados em múltiplos artefatos e
fáceis de extrair de cada formato sem ambiguidade:
  - MRR da Company_4 (a maior conta em risco)
  - Total de contas churned (n_churned)
  - Taxa de churn (%)
  - % de churn em menos de 90 dias

Uso: python harness_consistencia_artefatos.py
"""

import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

from gerar_excel import compute_metrics
from openpyxl import load_workbook


class HarnessConsistencia:
    def __init__(self):
        self.resultados = []
        self.start_time = None
        self.fonte = None

    def run(self):
        self.start_time = time.time()
        print("=" * 70)
        print("HARNESS DE CONSISTÊNCIA — extração → Excel → dashboard → IA de consulta")
        print("=" * 70)
        print()

        self.fonte = compute_metrics()
        print(f"Fonte única (compute_metrics()): MRR Company_4=${self._mrr_company4_fonte():,.2f}, "
              f"n_churned={self.fonte['n_churned']}, churn_rate={self.fonte['churn_rate']}%, "
              f"pct_early_churn={self.fonte['pct_early_churn']}%\n")

        self.teste_1_mrr_company4_no_excel()
        self.teste_2_mrr_company4_no_dashboard()
        self.teste_3_mrr_company4_na_ia_consulta()
        self.teste_4_churn_rate_no_excel()
        self.teste_5_churn_rate_no_dashboard()
        self.teste_6_pct_early_churn_no_dashboard()
        self.teste_7_top_segmento_consistente_excel_dashboard()

        return self.relatorio_final()

    def _mrr_company4_fonte(self):
        for conta in self.fonte["churned_mrr"]:
            if conta["name"] == "Company_4":
                return conta["mrr"]
        raise AssertionError("Company_4 não encontrada na fonte")

    def _ok(self, id_, nome, detalhe):
        self.resultados.append({"id": id_, "nome": nome, "status": "PASSOU", "detalhe": detalhe})

    def _falhou(self, id_, nome, detalhe):
        self.resultados.append({"id": id_, "nome": nome, "status": "FALHOU", "detalhe": detalhe})

    # --- Excel ---

    def teste_1_mrr_company4_no_excel(self):
        try:
            mrr_fonte = self._mrr_company4_fonte()
            wb = load_workbook("../RavenStack_Diagnostico_Churn.xlsx", data_only=True)
            ws = wb["Contas em Risco (MRR)"]
            mrr_excel = None
            for row in ws.iter_rows(min_row=1, values_only=True):
                if row and row[0] == "Company_4":
                    mrr_excel = row[5]
                    break
            assert mrr_excel is not None, "Company_4 não encontrada na aba 'Contas em Risco (MRR)'"
            assert abs(mrr_excel - mrr_fonte) < 0.01, f"fonte=${mrr_fonte} vs excel=${mrr_excel}"
            self._ok("CONS-1", "MRR Company_4: fonte vs. Excel",
                      f"${mrr_fonte:,.2f} idêntico nos dois")
        except Exception as e:
            self._falhou("CONS-1", "MRR Company_4: fonte vs. Excel", str(e))

    # --- Dashboard HTML ---

    def teste_2_mrr_company4_no_dashboard(self):
        try:
            mrr_fonte = self._mrr_company4_fonte()
            with open("../dashboard.html", encoding="utf-8") as f:
                html = f.read()
            # a tabela de contas em risco formata como "$21,691.00/mês" (sem
            # "US" antes do símbolo — diferente de outras seções do
            # dashboard que usam "US$"; confirmado lendo o HTML real antes
            # de escrever este regex, depois que a primeira versão deu
            # falso-positivo procurando por "US\$")
            padrao = re.compile(r"Company_4</td><td>[^<]*</td><td>[^<]*</td><td>\$([\d,]+\.\d{2})")
            match = padrao.search(html)
            assert match, "não encontrei a linha da Company_4 no HTML do dashboard"
            mrr_dashboard = float(match.group(1).replace(",", ""))
            assert abs(mrr_dashboard - mrr_fonte) < 0.01, f"fonte=${mrr_fonte} vs dashboard=${mrr_dashboard}"
            self._ok("CONS-2", "MRR Company_4: fonte vs. dashboard.html",
                      f"${mrr_fonte:,.2f} idêntico nos dois")
        except Exception as e:
            self._falhou("CONS-2", "MRR Company_4: fonte vs. dashboard.html", str(e))

    # --- IA de consulta ---

    def teste_3_mrr_company4_na_ia_consulta(self):
        try:
            mrr_fonte = self._mrr_company4_fonte()
            resultado = subprocess.run(
                [sys.executable, "ia_consulta.py", "qual o MRR da Company_4?"],
                capture_output=True, text=True, encoding="utf-8", timeout=10,
            )
            saida = resultado.stdout
            match = re.search(r"US\$\s*([\d,]+\.\d{2})", saida)
            assert match, f"não encontrei número de MRR na resposta da IA: {saida!r}"
            mrr_ia = float(match.group(1).replace(",", ""))
            assert abs(mrr_ia - mrr_fonte) < 0.01, f"fonte=${mrr_fonte} vs IA de consulta=${mrr_ia}"
            self._ok("CONS-3", "MRR Company_4: fonte vs. IA de consulta",
                      f"${mrr_fonte:,.2f} idêntico nos dois (subprocess real, não import direto)")
        except Exception as e:
            self._falhou("CONS-3", "MRR Company_4: fonte vs. IA de consulta", str(e))

    # --- Taxa de churn geral ---

    def teste_4_churn_rate_no_excel(self):
        try:
            taxa_fonte = self.fonte["churn_rate"]
            wb = load_workbook("../RavenStack_Diagnostico_Churn.xlsx", data_only=True)
            ws = wb["Resumo Executivo"]
            taxa_excel = None
            for row in ws.iter_rows(values_only=True):
                if row and row[0] == "Taxa de churn (contas)":
                    taxa_excel = row[1]
                    break
            assert taxa_excel is not None, "linha 'Taxa de churn (contas)' não encontrada"
            taxa_excel_num = float(taxa_excel.replace("%", ""))
            assert abs(taxa_excel_num - taxa_fonte) < 0.01, f"fonte={taxa_fonte}% vs excel={taxa_excel_num}%"
            self._ok("CONS-4", "Taxa de churn: fonte vs. Excel", f"{taxa_fonte}% idêntico nos dois")
        except Exception as e:
            self._falhou("CONS-4", "Taxa de churn: fonte vs. Excel", str(e))

    def teste_5_churn_rate_no_dashboard(self):
        try:
            taxa_fonte = self.fonte["churn_rate"]
            with open("../dashboard.html", encoding="utf-8") as f:
                html = f.read()
            padrao = re.compile(r"Contas com churn</div><div class=\"value risk\">\d+\s*\(([\d.]+)%\)")
            match = padrao.search(html)
            assert match, "não encontrei a taxa de churn no KPI do dashboard"
            taxa_dashboard = float(match.group(1))
            assert abs(taxa_dashboard - taxa_fonte) < 0.01, f"fonte={taxa_fonte}% vs dashboard={taxa_dashboard}%"
            self._ok("CONS-5", "Taxa de churn: fonte vs. dashboard.html", f"{taxa_fonte}% idêntico nos dois")
        except Exception as e:
            self._falhou("CONS-5", "Taxa de churn: fonte vs. dashboard.html", str(e))

    def teste_6_pct_early_churn_no_dashboard(self):
        try:
            pct_fonte = self.fonte["pct_early_churn"]
            with open("../dashboard.html", encoding="utf-8") as f:
                html = f.read()
            padrao = re.compile(r"Churn em &lt;90 dias</div><div class=\"value risk\">([\d.]+)%")
            match = padrao.search(html)
            assert match, "não encontrei o KPI de early churn no dashboard"
            pct_dashboard = float(match.group(1))
            assert abs(pct_dashboard - pct_fonte) < 0.01, f"fonte={pct_fonte}% vs dashboard={pct_dashboard}%"
            self._ok("CONS-6", "% early churn: fonte vs. dashboard.html", f"{pct_fonte}% idêntico nos dois")
        except Exception as e:
            self._falhou("CONS-6", "% early churn: fonte vs. dashboard.html", str(e))

    def teste_7_top_segmento_consistente_excel_dashboard(self):
        try:
            top_fonte = self.fonte["seg_rows"][0]  # (industria, canal, total, churned, taxa)
            industria_fonte, canal_fonte = top_fonte[0], top_fonte[1]

            wb = load_workbook("../RavenStack_Diagnostico_Churn.xlsx", data_only=True)
            ws = wb["Segmentação de Risco"]
            linha_excel = None
            for row in ws.iter_rows(min_row=4, max_row=4, values_only=True):
                linha_excel = row
            assert linha_excel is not None, "primeira linha de dado não encontrada na aba de segmentação"
            assert linha_excel[0] == industria_fonte and linha_excel[1] == canal_fonte, \
                f"fonte={industria_fonte}/{canal_fonte} vs excel={linha_excel[0]}/{linha_excel[1]}"

            with open("../dashboard.html", encoding="utf-8") as f:
                html = f.read()
            assert f"{industria_fonte} / {canal_fonte}" in html, \
                f"segmento top '{industria_fonte} / {canal_fonte}' não aparece no dashboard"

            self._ok("CONS-7", "Top segmento de risco: fonte vs. Excel vs. dashboard",
                      f"{industria_fonte}/{canal_fonte} consistente nos 3")
        except Exception as e:
            self._falhou("CONS-7", "Top segmento de risco entre os 3 artefatos", str(e))

    def salvar_dados_para_consulta(self):
        """Mesma disciplina de harness_auditoria_submissao.py: calcular uma
        vez, salvar o resultado estruturado, consultar depois sem re-rodar."""
        import json
        from datetime import datetime

        saida = {
            "gerado_em": datetime.now().isoformat(),
            "descricao": "Consistência de números entre compute_metrics(), Excel, dashboard.html e IA de consulta",
            "resultados": self.resultados,
            "resumo": {
                "total": len(self.resultados),
                "passou": sum(1 for r in self.resultados if r["status"] == "PASSOU"),
                "falhou": sum(1 for r in self.resultados if r["status"] == "FALHOU"),
            },
        }
        caminho = "../process-log/consistencia-artefatos.json"
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(saida, f, ensure_ascii=False, indent=2)
        return caminho

    def relatorio_final(self):
        total = len(self.resultados)
        passou = sum(1 for r in self.resultados if r["status"] == "PASSOU")
        falhou = total - passou
        elapsed = time.time() - self.start_time

        print(f"Testes executados: {total} | Passou: {passou} | Falhou: {falhou} | Tempo: {elapsed:.3f}s")
        print("-" * 70)
        print()
        for r in self.resultados:
            icone = "✅" if r["status"] == "PASSOU" else "❌"
            print(f"{icone} [{r['id']}] {r['nome']}")
            print(f"   {r['status']} — {r['detalhe']}\n")

        print("=" * 70)
        if falhou == 0:
            print(f"VEREDITO: {passou}/{total} — todos os números batem entre extração, "
                  f"Excel, dashboard e IA de consulta. Nenhuma divergência encontrada.")
        else:
            print(f"VEREDITO: {falhou} DIVERGÊNCIA(S) encontrada(s) entre artefatos — investigar antes do PR.")
        print("=" * 70)
        return falhou == 0


if __name__ == "__main__":
    h = HarnessConsistencia()
    sucesso = h.run()
    caminho_json = h.salvar_dados_para_consulta()
    print(f"\nDados extraídos salvos para consulta futura: {caminho_json}")
    sys.exit(0 if sucesso else 1)
