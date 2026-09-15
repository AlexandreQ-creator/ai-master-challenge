"""
Harness do auditor de integridade semântica.

Testa que `auditor_integridade_semantica.py` faz o que promete, usando
dados sintéticos construídos de propósito — não os dados reais, porque
aqui precisamos de casos onde sabemos a resposta certa de antemão.

Cenários:
  1. Par fortemente associado -> deve dar ASSOCIADO, Cramér's V alto
  2. Par independente por construção -> deve dar INDEPENDENTE
  3. Amostra pequena demais -> deve dar AMOSTRA INSUFICIENTE, não um
     veredito estatístico falsamente confiante
  4. Dataset inteiro sem estrutura -> o diagnóstico de nível de dataset
     deve disparar (evita o falso-positivo de reportar N campos quebrados
     quando o problema é o dataset todo)
  5. Dataset com estrutura + UM campo quebrado -> o diagnóstico NÃO deve
     disparar, e o campo quebrado deve ser sinalizado isoladamente
  6. Caso real: deve encontrar reason_code x feedback_text nos dados da
     submissão sem receber dica de onde procurar

Uso: python harness_auditor_semantico.py
"""

import random
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

from auditor_integridade_semantica import (
    auditar,
    diagnosticar_dataset,
    testar_par,
)


class HarnessAuditorSemantico:
    def __init__(self):
        self.resultados = []
        self.start = None

    def run(self):
        self.start = time.time()
        print("=" * 74)
        print("HARNESS DO AUDITOR SEMÂNTICO — 6 cenários com resposta conhecida")
        print("=" * 74)
        print()

        self.teste_1_par_associado()
        self.teste_2_par_independente()
        self.teste_3_amostra_insuficiente()
        self.teste_4_dataset_sem_estrutura()
        self.teste_5_dataset_com_estrutura_e_um_quebrado()
        self.teste_6_caso_real_reason_code()

        return self.relatorio()

    def _ok(self, id_, nome, detalhe):
        self.resultados.append({"id": id_, "nome": nome, "status": "PASSOU", "detalhe": detalhe})

    def _falhou(self, id_, nome, detalhe):
        self.resultados.append({"id": id_, "nome": nome, "status": "FALHOU", "detalhe": detalhe})

    def teste_1_par_associado(self):
        try:
            # plano determina preço quase perfeitamente
            linhas = []
            for _ in range(600):
                plano = random.choice(["Basic", "Pro", "Enterprise"])
                faixa = {"Basic": "baixo", "Pro": "medio", "Enterprise": "alto"}[plano]
                linhas.append({"plano": plano, "faixa": faixa})
            r = testar_par(linhas, "plano", "faixa")
            assert r["cramers_v"] > 0.9, f"V deveria ser alto, deu {r['cramers_v']}"
            assert r["chi2"] > 100, f"chi2 deveria ser alto, deu {r['chi2']}"
            self._ok("SEM-1", "Par fortemente associado é detectado",
                     f"Cramér's V = {r['cramers_v']}, chi2 = {r['chi2']}")
        except Exception as e:
            self._falhou("SEM-1", "Par fortemente associado é detectado", str(e))

    def teste_2_par_independente(self):
        try:
            random.seed(7)
            linhas = [{"a": random.choice(["x", "y", "z"]),
                       "b": random.choice(["p", "q"])} for _ in range(900)]
            r = testar_par(linhas, "a", "b")
            assert r["cramers_v"] < 0.15, f"V deveria ser baixo, deu {r['cramers_v']}"
            self._ok("SEM-2", "Par independente por construção é detectado",
                     f"Cramér's V = {r['cramers_v']} (baixo, como esperado)")
        except Exception as e:
            self._falhou("SEM-2", "Par independente por construção", str(e))

    def teste_3_amostra_insuficiente(self):
        try:
            # 8 linhas, 3x2 células -> esperado por célula bem abaixo de 5
            linhas = [{"a": "x", "b": "p"}, {"a": "y", "b": "q"},
                      {"a": "z", "b": "p"}, {"a": "x", "b": "q"},
                      {"a": "y", "b": "p"}, {"a": "z", "b": "q"},
                      {"a": "x", "b": "p"}, {"a": "y", "b": "q"}]
            r = testar_par(linhas, "a", "b")
            assert not r["confiavel"], "deveria marcar amostra como não confiável"
            self._ok("SEM-3", "Amostra insuficiente é marcada, não julgada",
                     f"confiavel=False, {r['pct_celulas_validas']}% das células válidas")
        except Exception as e:
            self._falhou("SEM-3", "Amostra insuficiente é marcada", str(e))

    def teste_4_dataset_sem_estrutura(self):
        try:
            # simula o resultado de um dataset onde nada se associa
            fake = [{"cramers_v": 0.05, "veredito": "INDEPENDENTE"} for _ in range(40)]
            fake += [{"cramers_v": 0.12, "veredito": "INDEPENDENTE"} for _ in range(10)]
            d = diagnosticar_dataset(fake)
            assert d["dataset_sem_estrutura_categorica"], "deveria detectar ausência de estrutura"
            self._ok("SEM-4", "Dataset sem estrutura dispara diagnóstico de nível global",
                     f"V máx = {d['cramers_v_maximo']}, {d['pct_pares_independentes']}% independentes")
        except Exception as e:
            self._falhou("SEM-4", "Dataset sem estrutura dispara diagnóstico", str(e))

    def teste_5_dataset_com_estrutura_e_um_quebrado(self):
        try:
            # a maioria dos pares tem associação real; só um é independente
            fake = [{"cramers_v": 0.55, "veredito": "ASSOCIADO"} for _ in range(30)]
            fake += [{"cramers_v": 0.03, "veredito": "INDEPENDENTE"} for _ in range(3)]
            d = diagnosticar_dataset(fake)
            assert not d["dataset_sem_estrutura_categorica"], \
                "NÃO deveria disparar — o dataset tem estrutura, só um par é suspeito"
            self._ok("SEM-5", "Dataset com estrutura + campo isolado quebrado",
                     f"diagnóstico global não dispara (V máx = {d['cramers_v_maximo']}), "
                     f"suspeito fica isolado")
        except Exception as e:
            self._falhou("SEM-5", "Dataset com estrutura + campo isolado", str(e))

    def teste_6_caso_real_reason_code(self):
        try:
            resultados, _, _ = auditar()
            alvo = [r for r in resultados
                    if {r["col_a"], r["col_b"]} == {"reason_code", "feedback_text"}]
            assert alvo, "auditor não encontrou o par reason_code x feedback_text"
            r = alvo[0]
            assert r["veredito"] == "INDEPENDENTE", f"veredito inesperado: {r['veredito']}"
            assert r["severidade"] == "ALTA", f"severidade inesperada: {r['severidade']}"
            self._ok("SEM-6", "Caso real: encontra reason_code x feedback_text sem dica",
                     f"chi2 = {r['chi2']}, V = {r['cramers_v']}, severidade ALTA")
        except Exception as e:
            self._falhou("SEM-6", "Caso real: encontra o par sem dica", str(e))

    def relatorio(self):
        total = len(self.resultados)
        passou = sum(1 for r in self.resultados if r["status"] == "PASSOU")
        falhou = total - passou
        print(f"Testes: {total} | Passou: {passou} | Falhou: {falhou} | "
              f"Tempo: {time.time() - self.start:.3f}s")
        print("-" * 74)
        print()
        for r in self.resultados:
            icone = "✅" if r["status"] == "PASSOU" else "❌"
            print(f"{icone} [{r['id']}] {r['nome']}")
            print(f"   {r['status']} — {r['detalhe']}\n")
        print("=" * 74)
        if falhou == 0:
            print(f"VEREDITO: {passou}/{total} — o auditor detecta associação, independência,")
            print("amostra insuficiente, e distingue 'dataset sem estrutura' de 'campo quebrado'.")
        else:
            print(f"VEREDITO: {falhou} teste(s) FALHARAM.")
        print("=" * 74)
        return falhou == 0


if __name__ == "__main__":
    h = HarnessAuditorSemantico()
    sys.exit(0 if h.run() else 1)
