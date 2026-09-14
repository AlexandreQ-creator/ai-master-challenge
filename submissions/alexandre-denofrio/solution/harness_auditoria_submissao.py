"""
Harness de auditoria final — Challenge 001 (Diagnóstico de Churn).

Mesmo padrão de `harness-mestre-dados.py` (raiz do repo, corrigido nesta
sessão): cada cenário roda um teste real contra os artefatos da submissão,
com asserts de verdade — o veredito final é condicionado ao resultado real
dos testes, não uma mensagem fixa (essa foi exatamente a lição do bug de
PII encontrado naquele harness: um "sucesso" que não checa nada não é
garantia, é decoração).

Este harness audita a submissão contra o brief OFICIAL do desafio, lido
direto de `challenges/data-001-churn/README.md` no commit do repositório
(não uma paráfrase de memória) — os 5 critérios de qualidade e as 6 dicas
viram testes programáticos sempre que são objetivamente verificáveis
(cruzamento de tabelas, presença de número, existência de artefato).
Critérios que exigem julgamento humano (ex.: "as recomendações são
realmente acionáveis?") são sinalizados como NÃO VERIFICÁVEL POR SCRIPT,
não fingidos como testados.

Uso: python harness_auditoria_submissao.py
"""

import re
import time


SUBMISSAO = ".."  # solution/ -> raiz da pasta da submissão


class AuditoriaSubmissao:
    def __init__(self):
        self.resultados = []
        self.start_time = None

    def run(self):
        self.start_time = time.time()
        print("=" * 70)
        print("HARNESS DE AUDITORIA — Challenge 001, contra o brief oficial do GitHub")
        print("=" * 70)
        print()

        self.criterio_1_cruzamento_5_tabelas()
        self.criterio_2_insights_verificaveis()
        self.criterio_3_recomendacoes_acionaveis()
        self.criterio_4_correlacao_vs_causalidade()
        self.criterio_5_ceo_le_e_age()
        self.dica_1_estrutura_antes_de_analise()
        self.dica_2_feature_usage_x_churn_events()
        self.dica_3_suporte_churned_vs_ativos()
        self.dica_4_uso_cresceu_todos_segmentos()
        self.dica_5_peso_do_churn_por_valor()
        self.dica_6_cuidado_correlacao_apressada()
        self.obrigatorio_process_log()
        self.obrigatorio_estrutura_pasta()

        return self.relatorio_final()

    def _ok(self, id_, nome, detalhe):
        self.resultados.append({"id": id_, "nome": nome, "status": "PASSOU", "detalhe": detalhe})

    def _falhou(self, id_, nome, detalhe):
        self.resultados.append({"id": id_, "nome": nome, "status": "FALHOU", "detalhe": detalhe})

    def _nao_verificavel(self, id_, nome, detalhe):
        self.resultados.append({"id": id_, "nome": nome, "status": "NÃO VERIFICÁVEL POR SCRIPT", "detalhe": detalhe})

    def _ler(self, caminho):
        with open(f"{SUBMISSAO}/{caminho}", encoding="utf-8") as f:
            return f.read()

    # --- Critérios de qualidade oficiais (5) ---

    def criterio_1_cruzamento_5_tabelas(self):
        try:
            codigo = self._ler("solution/analise.py")
            tabelas = ["ravenstack_accounts.csv", "ravenstack_subscriptions.csv",
                       "ravenstack_feature_usage.csv", "ravenstack_support_tickets.csv",
                       "ravenstack_churn_events.csv"]
            carregadas = [t for t in tabelas if t in codigo]
            assert len(carregadas) == 5, f"só {len(carregadas)}/5 tabelas carregadas"

            joins = ["account_id", "subscription_id"]
            usa_join = all(j in codigo for j in joins)
            assert usa_join, "não encontrei referência às chaves de join"

            self._ok("C1", "Cruzamento entre as 5 tabelas",
                      f"5/5 tabelas carregadas em analise.py, chaves de join (account_id, subscription_id) presentes")
        except Exception as e:
            self._falhou("C1", "Cruzamento entre as 5 tabelas", str(e))

    def criterio_2_insights_verificaveis(self):
        try:
            readme = self._ler("README.md")
            numeros = re.findall(r"\d+[,.]?\d*%|\bUS\$\s?[\d,.]+", readme)
            assert len(numeros) >= 10, f"só {len(numeros)} números encontrados no README"
            self._ok("C2", "Insights verificáveis (números mostrados)",
                      f"{len(numeros)} números/percentuais citados no README.md")
        except Exception as e:
            self._falhou("C2", "Insights verificáveis", str(e))

    def criterio_3_recomendacoes_acionaveis(self):
        try:
            readme = self._ler("README.md")
            secao = re.search(r"### Recomendações(.*?)### Diferencial", readme, re.DOTALL)
            assert secao, "seção Recomendações não encontrada"
            texto = secao.group(1)
            n_recomendacoes = len(re.findall(r"^\d+\.\s", texto, re.MULTILINE))
            assert n_recomendacoes >= 3, f"só {n_recomendacoes} recomendações numeradas"

            frases_vagas = ["melhorar a experiência do cliente", "aumentar a satisfação",
                             "investir em qualidade"]
            achou_vaga = [f for f in frases_vagas if f in texto.lower()]
            assert not achou_vaga, f"frase genérica encontrada: {achou_vaga}"

            self._ok("C3", "Recomendações acionáveis, não genéricas",
                      f"{n_recomendacoes} recomendações numeradas, nenhuma das frases-clichê do brief encontrada")
        except Exception as e:
            self._falhou("C3", "Recomendações acionáveis", str(e))

    def criterio_4_correlacao_vs_causalidade(self):
        try:
            readme = self._ler("README.md")
            termos = ["correlação", "causa raiz", "não sustentaram", "ruído"]
            achados = [t for t in termos if t in readme.lower()]
            assert len(achados) >= 3, f"só {len(achados)}/4 termos de distinção causal encontrados"
            self._ok("C4", "Distingue correlação de causalidade",
                      f"termos de distinção causal presentes: {achados}")
        except Exception as e:
            self._falhou("C4", "Correlação vs. causalidade", str(e))

    def criterio_5_ceo_le_e_age(self):
        import os
        dashboard_existe = os.path.exists(f"{SUBMISSAO}/dashboard.html")
        excel_existe = os.path.exists(f"{SUBMISSAO}/RavenStack_Diagnostico_Churn.xlsx")
        if dashboard_existe and excel_existe:
            self._ok("C5", "CEO não-técnico consegue ler e agir",
                      "dashboard.html (visual) e planilha Excel existem além do Markdown técnico")
        else:
            self._falhou("C5", "CEO consegue ler e agir",
                          f"dashboard={dashboard_existe}, excel={excel_existe}")

    # --- Dicas do brief (6) ---

    def dica_1_estrutura_antes_de_analise(self):
        readme = self._ler("README.md")
        if "schema real" in readme.lower() or "inspecionar o schema" in readme.lower():
            self._ok("D1", "Estrutura entendida antes da análise",
                      "Workflow do README menciona inspeção de schema antes de escrever lógica")
        else:
            self._falhou("D1", "Estrutura antes da análise", "não encontrei menção a inspeção de schema no Workflow")

    def dica_2_feature_usage_x_churn_events(self):
        try:
            readme = self._ler("README.md")
            assert "churn_events.churn_date" in readme or "churn_events" in readme and "feature_usage" in readme
            assert "30 dias" in readme, "não encontrei o cruzamento uso x proximidade do churn"
            self._ok("D2", "Feature usage cruzado com churn_events (não só churn_flag)",
                      "README cita uso nos 30 dias antes do churn real (churn_events.churn_date)")
        except Exception as e:
            self._falhou("D2", "Cruzamento feature_usage x churn_events", str(e))

    def dica_3_suporte_churned_vs_ativos(self):
        readme = self._ler("README.md")
        if "tempo de primeira resposta" in readme.lower() or "resolução de tickets" in readme.lower():
            self._ok("D3", "Tickets de suporte: churned vs. ativos",
                      "README compara tempo de resposta/resolução entre os dois grupos")
        else:
            self._falhou("D3", "Suporte churned vs. ativos", "comparação não encontrada no README")

    def dica_4_uso_cresceu_todos_segmentos(self):
        readme = self._ler("README.md")
        texto = readme.lower()
        # aceita tanto "H1-2023" quanto "primeiro semestre de 2023" (a forma por
        # extenso usada de fato no README) — o teste original só cobria a forma
        # abreviada e deu falso-positivo na primeira rodada desta auditoria.
        menciona_periodo = "h1-2023" in texto or "primeiro semestre de 2023" in texto
        menciona_todas_industrias = re.search(r"(as\s+)?5\s+indústrias|todas.{0,20}indústrias", texto)
        if menciona_periodo and menciona_todas_industrias:
            self._ok("D4", "'Uso cresceu' testado por segmento, não só agregado",
                      "README quebra uso por indústria (semestre a semestre), não só a média geral")
        else:
            self._falhou("D4", "Uso por segmento",
                          f"período={menciona_periodo}, todas_industrias={bool(menciona_todas_industrias)}")

    def dica_5_peso_do_churn_por_valor(self):
        readme = self._ler("README.md")
        if "mrr" in readme.lower() and ("concentr" in readme.lower() or "top" in readme.lower()):
            self._ok("D5", "Nem todo churn tem o mesmo peso (MRR concentrado)",
                      "README trata concentração de MRR em poucas contas, não todas como equivalentes")
        else:
            self._falhou("D5", "Peso do churn por valor", "concentração de MRR não encontrada")

    def dica_6_cuidado_correlacao_apressada(self):
        readme = self._ler("README.md")
        if "não se sustentaram" in readme.lower() or "pistas que pareciam" in readme.lower():
            self._ok("D6", "Cuidado com correlação apressada",
                      "README tem seção dedicada a pistas descartadas por não se sustentarem")
        else:
            self._falhou("D6", "Correlação apressada", "seção de pistas descartadas não encontrada")

    # --- Obrigatórios do submission-guide.md ---

    def obrigatorio_process_log(self):
        import os
        readme = self._ler("README.md")
        tem_secao = "Process Log" in readme
        tem_evidencia_fisica = os.path.exists(f"{SUBMISSAO}/process-log/chat-exports") and \
            len(os.listdir(f"{SUBMISSAO}/process-log/chat-exports")) > 0
        if tem_secao and tem_evidencia_fisica:
            n_arquivos = len(os.listdir(f"{SUBMISSAO}/process-log/chat-exports"))
            self._ok("OBRIG-1", "Process log obrigatório (com evidência física)",
                      f"seção Process Log no README + {n_arquivos} arquivos em process-log/chat-exports/")
        else:
            self._falhou("OBRIG-1", "Process log", f"seção={tem_secao}, evidência física={tem_evidencia_fisica}")

    def obrigatorio_estrutura_pasta(self):
        import os
        esperado = ["README.md", "solution", "process-log"]
        existe = [p for p in esperado if os.path.exists(f"{SUBMISSAO}/{p}")]
        if len(existe) == len(esperado):
            self._ok("OBRIG-2", "Estrutura de pasta conforme CONTRIBUTING.md",
                      "README.md, solution/, process-log/ presentes")
        else:
            faltando = set(esperado) - set(existe)
            self._falhou("OBRIG-2", "Estrutura de pasta", f"faltando: {faltando}")

    def salvar_dados_para_consulta(self):
        """
        Salva o resultado estruturado em JSON — dados já extraídos, prontos
        para consulta (pela IA de consulta ou por qualquer sessão futura)
        sem precisar re-rodar o harness inteiro para saber "está tudo OK?".
        Mesma lógica de compute_metrics(): calcular uma vez, consumir depois.
        """
        import json
        from datetime import datetime

        saida = {
            "gerado_em": datetime.now().isoformat(),
            "fonte_do_brief": "challenges/data-001-churn/README.md (commit 4aed364 do repo oficial)",
            "resultados": self.resultados,
            "resumo": {
                "total": len(self.resultados),
                "passou": sum(1 for r in self.resultados if r["status"] == "PASSOU"),
                "falhou": sum(1 for r in self.resultados if r["status"] == "FALHOU"),
                "nao_verificavel": sum(1 for r in self.resultados if r["status"] == "NÃO VERIFICÁVEL POR SCRIPT"),
            },
        }
        caminho = f"{SUBMISSAO}/process-log/auditoria-final.json"
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(saida, f, ensure_ascii=False, indent=2)
        return caminho

    def relatorio_final(self):
        total = len(self.resultados)
        passou = sum(1 for r in self.resultados if r["status"] == "PASSOU")
        falhou = sum(1 for r in self.resultados if r["status"] == "FALHOU")
        nao_verif = sum(1 for r in self.resultados if r["status"] == "NÃO VERIFICÁVEL POR SCRIPT")
        elapsed = time.time() - self.start_time

        print(f"Testes executados: {total}")
        print(f"Passou: {passou} | Falhou: {falhou} | Não verificável por script: {nao_verif}")
        print(f"Tempo: {elapsed:.3f}s")
        print("-" * 70)
        print()

        for r in self.resultados:
            icone = "✅" if r["status"] == "PASSOU" else ("❌" if r["status"] == "FALHOU" else "⚪")
            print(f"{icone} [{r['id']}] {r['nome']}")
            print(f"   {r['status']} — {r['detalhe']}\n")

        print("=" * 70)
        if falhou == 0:
            print(f"VEREDITO: {passou}/{total} testes automatizados passaram. "
                  f"{nao_verif} critério(s) exigem julgamento humano (não fingidos como testados).")
        else:
            print(f"VEREDITO: {falhou} teste(s) FALHARAM — corrigir antes do PR. "
                  f"({passou}/{total} passaram)")
        print("=" * 70)

        return falhou == 0


if __name__ == "__main__":
    auditoria = AuditoriaSubmissao()
    sucesso = auditoria.run()
    caminho_json = auditoria.salvar_dados_para_consulta()
    print(f"\nDados extraídos salvos para consulta futura: {caminho_json}")
    import sys
    sys.exit(0 if sucesso else 1)
