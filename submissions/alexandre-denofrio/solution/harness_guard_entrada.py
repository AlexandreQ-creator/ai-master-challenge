"""
Harness do guard de entrada — testa os 3 tipos de erro de usuário que
guard_entrada_dados.py deve pegar, de forma automatizada e reprodutível
(não manual, como a primeira verificação desta funcionalidade foi feita).

Mesmo padrão dos outros dois harnesses desta submissão: cenários com
assert real, rodando em uma pasta de dados temporária (nunca toca em
data/, a base real) para não arriscar corromper o dataset da submissão.

Cenários:
  1. Base diferente/incompatível — remove uma coluna obrigatória
  2. Valor traduzido/idioma errado — troca "Basic"/"Enterprise" por
     "Básico"/"Empresarial"
  3. Terminologia do domínio incorreta — reason_code com valor fora do
     vocabulário fechado, sem ser tradução conhecida
  4. (controle) Base correta — confirma que dado bom passa limpo

Uso: python harness_guard_entrada.py
"""

import csv
import os
import shutil
import sys
import tempfile
import time

from guard_entrada_dados import validar_entrada


DATA_REAL = "../data"


class HarnessGuardEntrada:
    def __init__(self):
        self.resultados = []
        self.start_time = None
        self.tmp_dir = None

    def run(self):
        self.start_time = time.time()
        print("=" * 70)
        print("HARNESS DO GUARD DE ENTRADA — 3 tipos de erro de usuário + controle")
        print("=" * 70)
        print()

        self.tmp_dir = tempfile.mkdtemp(prefix="raven_guard_test_")
        try:
            self.teste_0_controle_dado_correto()
            self.teste_1_base_incompativel_schema()
            self.teste_2_valor_traduzido()
            self.teste_3_terminologia_incorreta()
        finally:
            shutil.rmtree(self.tmp_dir, ignore_errors=True)

        return self.relatorio_final()

    def _copiar_dados_reais(self):
        for nome in os.listdir(DATA_REAL):
            if nome.endswith(".csv"):
                shutil.copy(f"{DATA_REAL}/{nome}", f"{self.tmp_dir}/{nome}")

    def _ok(self, id_, nome, detalhe):
        self.resultados.append({"id": id_, "nome": nome, "status": "PASSOU", "detalhe": detalhe})

    def _falhou(self, id_, nome, detalhe):
        self.resultados.append({"id": id_, "nome": nome, "status": "FALHOU", "detalhe": detalhe})

    def teste_0_controle_dado_correto(self):
        try:
            self._copiar_dados_reais()
            ok, erros = validar_entrada(pasta_data=self.tmp_dir, verbose=False)
            assert ok, f"dado correto foi rejeitado: {[str(e) for e in erros]}"
            self._ok("GUARD-0", "Controle: dado correto passa sem erro", "0 erros, como esperado")
        except Exception as e:
            self._falhou("GUARD-0", "Controle: dado correto passa sem erro", str(e))

    def teste_1_base_incompativel_schema(self):
        try:
            self._copiar_dados_reais()
            caminho = f"{self.tmp_dir}/ravenstack_accounts.csv"
            with open(caminho, encoding="utf-8") as f:
                linhas = list(csv.DictReader(f))
            campos = [c for c in linhas[0].keys() if c != "industry"]
            with open(caminho, "w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=campos)
                w.writeheader()
                for linha in linhas:
                    del linha["industry"]
                    w.writerow(linha)

            ok, erros = validar_entrada(pasta_data=self.tmp_dir, verbose=False)
            assert not ok, "guard deveria ter rejeitado schema incompatível, mas aprovou"
            erros_schema = [e for e in erros if e.categoria == "schema"]
            assert erros_schema, "erro não foi categorizado como 'schema'"
            assert "industry" in erros_schema[0].mensagem, "mensagem de erro não menciona a coluna faltante"
            self._ok("GUARD-1", "Base incompatível: coluna obrigatória ausente",
                      f"detectado corretamente: {erros_schema[0].mensagem[:80]}...")
        except Exception as e:
            self._falhou("GUARD-1", "Base incompatível: coluna obrigatória ausente", str(e))

    def teste_2_valor_traduzido(self):
        try:
            self._copiar_dados_reais()
            caminho = f"{self.tmp_dir}/ravenstack_accounts.csv"
            with open(caminho, encoding="utf-8") as f:
                linhas = list(csv.DictReader(f))
            linhas[0]["plan_tier"] = "Básico"
            linhas[1]["plan_tier"] = "Empresarial"
            with open(caminho, "w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=linhas[0].keys())
                w.writeheader()
                w.writerows(linhas)

            ok, erros = validar_entrada(pasta_data=self.tmp_dir, verbose=False)
            assert not ok, "guard deveria ter rejeitado valores traduzidos, mas aprovou"
            erros_idioma = [e for e in erros if e.categoria == "idioma/tradução"]
            assert len(erros_idioma) == 2, f"esperava 2 erros de idioma, achou {len(erros_idioma)}"
            assert "Basic" in erros_idioma[0].mensagem or "Basic" in erros_idioma[1].mensagem, \
                "sugestão de termo original (Basic) não apareceu na mensagem"
            self._ok("GUARD-2", "Valor traduzido/idioma errado (plan_tier)",
                      f"2/2 traduções detectadas, com sugestão do termo original")
        except Exception as e:
            self._falhou("GUARD-2", "Valor traduzido/idioma errado", str(e))

    def teste_3_terminologia_incorreta(self):
        try:
            self._copiar_dados_reais()
            caminho = f"{self.tmp_dir}/ravenstack_churn_events.csv"
            with open(caminho, encoding="utf-8") as f:
                linhas = list(csv.DictReader(f))
            linhas[0]["reason_code"] = "cancelled"
            with open(caminho, "w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=linhas[0].keys())
                w.writeheader()
                w.writerows(linhas)

            ok, erros = validar_entrada(pasta_data=self.tmp_dir, verbose=False)
            assert not ok, "guard deveria ter rejeitado terminologia incorreta, mas aprovou"
            erros_termo = [e for e in erros if e.categoria == "terminologia"]
            assert erros_termo, "erro não foi categorizado como 'terminologia'"
            assert "cancelled" in erros_termo[0].mensagem
            self._ok("GUARD-3", "Terminologia do domínio incorreta (reason_code)",
                      f"detectado corretamente: valor 'cancelled' fora do vocabulário fechado")
        except Exception as e:
            self._falhou("GUARD-3", "Terminologia do domínio incorreta", str(e))

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
            print(f"VEREDITO: {passou}/{total} — guard de entrada pega os 3 tipos de erro "
                  f"de usuário e não gera falso-positivo em dado correto.")
        else:
            print(f"VEREDITO: {falhou} teste(s) do guard FALHARAM — investigar antes do PR.")
        print("=" * 70)
        return falhou == 0


if __name__ == "__main__":
    h = HarnessGuardEntrada()
    sucesso = h.run()
    sys.exit(0 if sucesso else 1)
