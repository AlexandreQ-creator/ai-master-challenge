"""
Harness do servidor do dashboard.

Sobe servidor_dashboard.py de verdade (subprocess), bate nas rotas reais
via HTTP, e derruba o processo ao final — mesmo padrão de teste de ponta a
ponta já usado para o resto da submissão, não um mock da lógica interna.

Cenários:
  1. GET /api/status responde e reflete o guard de entrada real
  2. POST /api/atualizar regenera dashboard.html com timestamp novo
  3. POST /api/atualizar regenera o Excel quando ele não está bloqueado
  4. Rota inexistente devolve 404, não trava o servidor
  5. POST /api/perguntar chama a IA de consulta de verdade (não mock)
  6. POST /api/perguntar rejeita pergunta vazia (400)
  7. POST /api/perguntar rejeita pergunta > 500 caracteres (400)
  8. POST /api/perguntar preserva acentuação UTF-8 no round-trip JSON

Uso: python harness_servidor_dashboard.py
"""

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request

PORTA = 8735
BASE = f"http://127.0.0.1:{PORTA}"


class HarnessServidorDashboard:
    def __init__(self):
        self.resultados = []
        self.proc = None

    def run(self):
        print("=" * 70)
        print("HARNESS DO SERVIDOR DO DASHBOARD — sobe o processo real, bate via HTTP")
        print("=" * 70)
        print()

        self.proc = subprocess.Popen(
            [sys.executable, "servidor_dashboard.py", "--no-browser"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8",
        )
        time.sleep(2)

        try:
            self.teste_1_status()
            self.teste_2_atualizar_dashboard()
            self.teste_3_atualizar_excel()
            self.teste_4_rota_inexistente()
            self.teste_5_perguntar_valida()
            self.teste_6_perguntar_vazia()
            self.teste_7_perguntar_muito_longa()
            self.teste_8_perguntar_acentos()
        finally:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()

        return self.relatorio()

    def _ok(self, id_, nome, detalhe):
        self.resultados.append({"id": id_, "nome": nome, "status": "PASSOU", "detalhe": detalhe})

    def _falhou(self, id_, nome, detalhe):
        self.resultados.append({"id": id_, "nome": nome, "status": "FALHOU", "detalhe": detalhe})

    def teste_1_status(self):
        try:
            with urllib.request.urlopen(f"{BASE}/api/status", timeout=5) as r:
                dados = json.loads(r.read().decode())
            assert "base_valida" in dados, "resposta sem campo 'base_valida'"
            assert dados["base_valida"] is True, "guard de entrada deveria aprovar os dados reais"
            self._ok("SRV-1", "GET /api/status reflete o guard de entrada real",
                     f"base_valida={dados['base_valida']}")
        except Exception as e:
            self._falhou("SRV-1", "GET /api/status", str(e))

    def teste_2_atualizar_dashboard(self):
        try:
            import os
            caminho_dashboard = "../dashboard.html"
            antes = os.path.getmtime(caminho_dashboard)
            time.sleep(1.1)  # garante resolução de mtime diferente

            req = urllib.request.Request(f"{BASE}/api/atualizar", method="POST")
            with urllib.request.urlopen(req, timeout=15) as r:
                dados = json.loads(r.read().decode())
            assert dados["sucesso"] is True, f"esperava sucesso, veio: {dados}"

            depois = os.path.getmtime(caminho_dashboard)
            assert depois > antes, "dashboard.html não foi realmente regravado (mtime igual)"
            self._ok("SRV-2", "POST /api/atualizar regenera dashboard.html de verdade",
                     f"mtime mudou de {antes} para {depois}")
        except Exception as e:
            self._falhou("SRV-2", "POST /api/atualizar regenera dashboard.html", str(e))

    def teste_3_atualizar_excel(self):
        try:
            req = urllib.request.Request(f"{BASE}/api/atualizar", method="POST")
            with urllib.request.urlopen(req, timeout=15) as r:
                dados = json.loads(r.read().decode())
            if dados.get("excel_aviso"):
                # Excel bloqueado (ex.: aberto no Microsoft Excel) é um
                # cenário real e esperado, não falha do servidor — o
                # importante é que ele reporta com mensagem clara, testado
                # separadamente. Aqui só confirmamos que não travou o resto.
                self._ok("SRV-3", "POST /api/atualizar trata Excel bloqueado sem travar",
                         f"excel_aviso presente: {dados['excel_aviso'][:60]}...")
            else:
                assert dados.get("excel"), "excel deveria ter conteúdo quando não há aviso"
                self._ok("SRV-3", "POST /api/atualizar regenera o Excel",
                         "planilha regenerada sem aviso de bloqueio")
        except Exception as e:
            self._falhou("SRV-3", "POST /api/atualizar regenera o Excel", str(e))

    def teste_4_rota_inexistente(self):
        try:
            try:
                urllib.request.urlopen(f"{BASE}/api/rota-que-nao-existe", timeout=5)
                assert False, "deveria ter lançado HTTPError 404"
            except urllib.error.HTTPError as e:
                assert e.code == 404, f"esperava 404, veio {e.code}"
            # confirma que o servidor continua respondendo depois do 404
            with urllib.request.urlopen(f"{BASE}/api/status", timeout=5) as r:
                json.loads(r.read().decode())
            self._ok("SRV-4", "Rota inexistente devolve 404 sem travar o servidor",
                     "404 recebido, servidor segue respondendo depois")
        except Exception as e:
            self._falhou("SRV-4", "Rota inexistente / robustez", str(e))

    def _post_json(self, caminho, corpo):
        data = json.dumps(corpo).encode("utf-8")
        req = urllib.request.Request(
            f"{BASE}{caminho}", data=data,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode("utf-8"))

    def teste_5_perguntar_valida(self):
        try:
            status, dados = self._post_json("/api/perguntar", {"pergunta": "qual o MRR da Company_4?"})
            assert status == 200, f"esperava 200, veio {status}"
            assert "21,691.00" in dados["resposta"], "resposta não bate com o valor real de Company_4"
            self._ok("SRV-5", "POST /api/perguntar chama a IA de consulta de verdade",
                     "resposta contém o MRR real (US$ 21,691.00)")
        except Exception as e:
            self._falhou("SRV-5", "POST /api/perguntar resposta válida", str(e))

    def teste_6_perguntar_vazia(self):
        try:
            status, dados = self._post_json("/api/perguntar", {"pergunta": ""})
            assert status == 400, f"esperava 400, veio {status}"
            assert "erro" in dados
            self._ok("SRV-6", "POST /api/perguntar rejeita pergunta vazia", f"HTTP {status}, erro reportado")
        except Exception as e:
            self._falhou("SRV-6", "POST /api/perguntar rejeita pergunta vazia", str(e))

    def teste_7_perguntar_muito_longa(self):
        try:
            status, dados = self._post_json("/api/perguntar", {"pergunta": "a" * 600})
            assert status == 400, f"esperava 400, veio {status}"
            self._ok("SRV-7", "POST /api/perguntar rejeita pergunta > 500 caracteres",
                     f"HTTP {status}")
        except Exception as e:
            self._falhou("SRV-7", "POST /api/perguntar limite de tamanho", str(e))

    def teste_8_perguntar_acentos(self):
        try:
            status, dados = self._post_json("/api/perguntar", {"pergunta": "por que o churn está subindo?"})
            assert status == 200, f"esperava 200, veio {status}"
            assert dados["pergunta"] == "por que o churn está subindo?", \
                "acentuação corrompida no round-trip JSON UTF-8"
            self._ok("SRV-8", "POST /api/perguntar preserva acentuação UTF-8",
                     "pergunta com acento volta idêntica na resposta")
        except Exception as e:
            self._falhou("SRV-8", "POST /api/perguntar acentuação UTF-8", str(e))

    def relatorio(self):
        total = len(self.resultados)
        passou = sum(1 for r in self.resultados if r["status"] == "PASSOU")
        falhou = total - passou
        print(f"Testes: {total} | Passou: {passou} | Falhou: {falhou}")
        print("-" * 70)
        print()
        for r in self.resultados:
            icone = "✅" if r["status"] == "PASSOU" else "❌"
            print(f"{icone} [{r['id']}] {r['nome']}")
            print(f"   {r['status']} — {r['detalhe']}\n")
        print("=" * 70)
        if falhou == 0:
            print(f"VEREDITO: {passou}/{total} — servidor sobe, responde, atualiza os artefatos")
            print("de verdade, e é robusto a rota inexistente.")
        else:
            print(f"VEREDITO: {falhou} teste(s) FALHARAM.")
        print("=" * 70)
        return falhou == 0


if __name__ == "__main__":
    h = HarnessServidorDashboard()
    sys.exit(0 if h.run() else 1)
