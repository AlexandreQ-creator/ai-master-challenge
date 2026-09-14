#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Servidor local opcional do dashboard.html.

Por que existe: `dashboard.html` é HTML/CSS/JS estático, gerado uma vez
por `gerar_dashboard.py` — aberto via file:// (duplo-clique), o navegador
bloqueia qualquer chamada que precise rodar um processo no disco, então
não há como o próprio HTML disparar "reprocessar os dados". Este servidor
é a peça opcional que resolve isso, no mesmo padrão já usado em
`dashboard-carreira/servidor.py` deste mesmo projeto (http.server puro,
sem framework, 127.0.0.1 sem autenticação).

O que faz:
  - serve o dashboard em http://localhost:8735
  - POST /api/atualizar -> roda o guard de entrada + gerar_dashboard.py +
    gerar_excel.py sobre os CSVs atuais em data/, e devolve o resultado
  - GET  /api/status     -> confere se o guard de entrada aprova a base
    atual, sem reprocessar nada (usado pelo botão para mostrar o estado
    antes do clique)

**dashboard.html continua funcionando sozinho, sem este servidor.** Ele
detecta se está sendo servido via http:// ou aberto via file:// (checando
`location.protocol`) e desabilita o botão "Atualizar dados" com um aviso,
exatamente como o botão de status já esperava no arquivo estático — nenhum
comportamento existente muda para quem não rodar este servidor.

Uso:
    python servidor_dashboard.py
"""

import subprocess
import sys
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

PORTA = 8735
AQUI = Path(__file__).resolve().parent          # solution/
SUBMISSAO = AQUI.parent                          # pasta raiz da submissão


class ServidorReutilizavel(HTTPServer):
    # allow_reuse_address evita "Address already in use" ao reiniciar o
    # servidor logo em seguida (a porta anterior fica em TIME_WAIT por
    # alguns segundos no Windows) -- comportamento padrão esperado para
    # um servidor de desenvolvimento local, sem risco aqui porque só
    # escuta em 127.0.0.1.
    allow_reuse_address = True


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        # Serve os arquivos a partir da raiz da submissão (onde está
        # dashboard.html), não da pasta solution/ onde este script vive.
        super().__init__(*args, directory=str(SUBMISSAO), **kwargs)

    def log_message(self, format, *args):
        pass  # silencioso — mesmo padrão do dashboard-carreira/servidor.py

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/status":
            self._responder_status()
            return
        super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/atualizar":
            self._atualizar()
            return
        self.send_error(404)

    def _json(self, corpo: dict, codigo: int = 200):
        import json
        payload = json.dumps(corpo, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _responder_status(self):
        sys.path.insert(0, str(AQUI))
        from guard_entrada_dados import validar_entrada
        ok, erros = validar_entrada(pasta_data=str(AQUI / ".." / "data"), verbose=False)
        self._json({"base_valida": ok, "erros": [str(e) for e in erros]})

    def _atualizar(self):
        """
        Roda guard -> gerar_dashboard.py -> gerar_excel.py, nesse mesmo
        script Python (import direto, não subprocess) para reaproveitar a
        mesma lógica que compute_metrics() já usa — sem duplicar nada.
        Se o guard reprovar, aborta antes de tocar nos artefatos.
        """
        sys.path.insert(0, str(AQUI))
        from guard_entrada_dados import validar_entrada

        ok, erros = validar_entrada(pasta_data=str(AQUI / ".." / "data"), verbose=False)
        if not ok:
            self._json({
                "sucesso": False,
                "etapa": "guard_entrada_dados",
                "erros": [str(e) for e in erros],
            }, codigo=422)
            return

        resultado = subprocess.run(
            [sys.executable, str(AQUI / "gerar_dashboard.py")],
            cwd=str(AQUI), capture_output=True, text=True, encoding="utf-8",
        )
        if resultado.returncode != 0:
            self._json({
                "sucesso": False,
                "etapa": "gerar_dashboard.py",
                "saida": resultado.stdout + resultado.stderr,
            }, codigo=500)
            return

        resultado_excel = subprocess.run(
            [sys.executable, str(AQUI / "gerar_excel.py")],
            cwd=str(AQUI), capture_output=True, text=True, encoding="utf-8",
        )

        excel_aviso = None
        if resultado_excel.returncode != 0:
            erro = resultado_excel.stderr
            # Causa mais comum na prática: o .xlsx está aberto no Excel,
            # que trava o arquivo para escrita no Windows. Mensagem
            # específica em vez de reportar o traceback bruto ao usuário.
            if "PermissionError" in erro:
                excel_aviso = (
                    "Não consegui atualizar RavenStack_Diagnostico_Churn.xlsx — "
                    "o arquivo parece estar aberto no Excel. Feche-o e clique em "
                    "'Atualizar dados' de novo (o dashboard já foi atualizado normalmente)."
                )
            else:
                excel_aviso = "Excel não pôde ser regenerado: " + erro.strip().splitlines()[-1]

        self._json({
            "sucesso": True,
            "dashboard": resultado.stdout.strip(),
            "excel": resultado_excel.stdout.strip() if resultado_excel.returncode == 0 else None,
            "excel_aviso": excel_aviso,
        })


def main():
    abrir_navegador = "--no-browser" not in sys.argv
    servidor = ServidorReutilizavel(("127.0.0.1", PORTA), Handler)
    url = f"http://127.0.0.1:{PORTA}/dashboard.html"
    print(f"Servidor rodando em {url}", flush=True)
    print("Ctrl+C para encerrar.", flush=True)
    if abrir_navegador:
        # Abre o navegador DEPOIS que o servidor já está de pé (o socket
        # já fez bind e listen antes desta linha, já que ServidorReutilizavel
        # foi instanciado acima) -- não antes de serve_forever(), que seria
        # a ordem errada mas ainda assim não deveria travar por si só.
        webbrowser.open(url)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nEncerrado.")


if __name__ == "__main__":
    main()
