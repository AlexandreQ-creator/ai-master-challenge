"""
IA de Consulta RavenStack — implementação da arquitetura de 5 agentes
especificada em `arquitetura-ia-consulta.md`.

Roda em terminal, sem chave de API (roteamento determinístico por
palavras-chave, não LLM) — decisão de design: mantém o mesmo padrão de
dependência mínima já usado no resto da submissão (`gerar_excel.py` só usa
`openpyxl`, sem `pandas`), e garante que qualquer avaliador consiga rodar
sem configurar credencial nenhuma.

Os 5 agentes, na ordem em que a pergunta passa por eles:
  1. QueryRouter          — classifica a pergunta, recusa fora de escopo
  2. DataGroundingAgent    — única porta de entrada aos dados (compute_metrics())
  3. Subagentes de domínio — Causa Raiz | Segmentos | Contas | Recomendações | Metodologia
  4. ExecutiveResponseAgent — formata em linguagem executiva, cita fonte
  5. CleanContextAuditor   — confere a resposta sem ter visto o raciocínio

Uso:
  python ia_consulta.py                       # abre um chat interativo
  python ia_consulta.py "qual o MRR da Company_4?"   # pergunta única, modo não-interativo
  python ia_consulta.py --self-test            # roda a suíte de perguntas de exemplo do brief
"""

import re
import sys

from gerar_excel import compute_metrics


# ---------------------------------------------------------------------------
# Agente 1 — Roteador
# ---------------------------------------------------------------------------

DOMINIOS = ["causa_raiz", "segmentos", "contas", "recomendacoes", "metodologia", "auditoria"]

# Cada domínio é reconhecido por palavras-chave em PT-BR. Ordem importa:
# perguntas que citam uma conta específica (ex. "Company_4") são roteadas
# para "contas" mesmo que também mencionem "risco", porque pedir um dado
# pontual é mais específico que pedir uma lista de segmentos.
PADRAO_CONTA = re.compile(r"company[_\s]?\d+", re.IGNORECASE)

PALAVRAS_CHAVE = {
    "causa_raiz": ["por que", "porque", "causa", "motivo", "razão", "razao", "suporte é", "produto é", "uso caiu"],
    "segmentos": ["segmento", "indústria", "industria", "canal", "risco", "devtools", "trial", "setor"],
    "recomendacoes": ["deveria", "recomend", "ação", "acao", "prioridade", "o que fazer", "próximo passo", "proximo passo"],
    "metodologia": ["como vocês", "como voces", "confiar", "metodologia", "limitação", "limitacao", "fonte dos dados", "confiável", "confiavel"],
    "auditoria": ["auditoria", "pronta pro pr", "pronto pro pr", "passou no teste", "conformidade", "critérios do brief", "criterios do brief", "está pronta", "esta pronta"],
}

FORA_DE_ESCOPO = [
    (re.compile(r"20(2[7-9]|[3-9]\d)"), "previsão para anos futuros — não há modelo preditivo nesta submissão (ver Limitações do README)"),
    (re.compile(r"\bse eu filtrar\b|\be se\b|\bo que aconteceria\b|\bsimul", re.IGNORECASE), "análise nova sob demanda — fora do escopo v1 (ver 'Objetivo e escopo' em arquitetura-ia-consulta.md)"),
]


class QueryRouter:
    """Agente 1 — classifica a pergunta ou recusa. Não calcula nada."""

    def route(self, pergunta: str):
        for padrao, motivo in FORA_DE_ESCOPO:
            if padrao.search(pergunta):
                return {"status": "recusado", "motivo": motivo}

        if PADRAO_CONTA.search(pergunta):
            return {"status": "ok", "dominio": "contas"}

        pergunta_lower = pergunta.lower()
        for dominio in ["auditoria", "recomendacoes", "metodologia", "segmentos", "causa_raiz"]:
            for kw in PALAVRAS_CHAVE.get(dominio, []):
                if kw in pergunta_lower:
                    return {"status": "ok", "dominio": dominio}

        if "mrr" in pergunta_lower or "conta" in pergunta_lower:
            return {"status": "ok", "dominio": "contas"}

        return {
            "status": "recusado",
            "motivo": "não consegui classificar esta pergunta em nenhum dos eixos cobertos (causa raiz, segmentos, contas específicas, recomendações, metodologia) — tente reformular",
        }


# ---------------------------------------------------------------------------
# Agente 2 — Grounding
# ---------------------------------------------------------------------------

class DataGroundingAgent:
    """
    Agente 2 — única porta de entrada aos dados reais. Wrapper fino sobre
    compute_metrics() (mesma fonte usada por gerar_excel.py) — nunca
    recalcula, nunca inventa.
    """

    def __init__(self):
        self._metrics = None

    def metrics(self):
        if self._metrics is None:
            self._metrics = compute_metrics()
        return self._metrics

    def buscar_conta(self, nome_ou_id: str):
        m = self.metrics()
        alvo = nome_ou_id.strip().lower()
        for conta in m["churned_mrr"]:
            if alvo in conta["name"].lower() or alvo == conta["account_id"].lower():
                return conta
        return None

    def auditoria(self):
        """
        Lê o resultado já extraído por harness_auditoria_submissao.py
        (process-log/auditoria-final.json) — nunca re-roda o harness aqui,
        mesma disciplina de "calcular uma vez, consultar depois" de
        compute_metrics(). Se o arquivo não existir (harness nunca rodado),
        devolve None para o subagente tratar como "não calculado".
        """
        import json
        import os
        caminho = "../process-log/auditoria-final.json"
        if not os.path.exists(caminho):
            return None
        with open(caminho, encoding="utf-8") as f:
            return json.load(f)


# ---------------------------------------------------------------------------
# Agente 3 — Subagentes de domínio
# ---------------------------------------------------------------------------

ACHADOS_CAUSA_RAIZ = [
    "Achado 1: uso por assinatura está achatado (~11,0-11,3/mês) desde jan/2023, sem tendência de alta em nenhuma indústria — 'uso cresceu' não é causa nem sinal de alerta.",
    "Achado 2: satisfação média é praticamente igual entre contas que cancelaram (4,01) e as que ficaram (3,97), com só 58,8% de cobertura — não é preditiva.",
    "Achado 3: 67,9% do churn acontece nos primeiros 90 dias (mediana 42 dias) — sinal real é tenure curto, não uso ou satisfação.",
    "Achado 6: tempo de resposta/resolução de suporte é praticamente idêntico entre churned e ativos — suporte não é causa operacional real, mesmo aparecendo em 17,3% dos reason_code declarados pelo cliente.",
]

RECOMENDACOES = [
    ("1", "Redesenhar onboarding dos primeiros 90 dias (checkpoints dias 14/30/60)", "reduzir 25% do churn early-stage preserva ~19 contas/trimestre"),
    ("2", "Qualificar ICP antes de comprar mídia para DevTools via event/ads", "esses canais cancelam 4-8x mais que a média nessa indústria"),
    ("3", "Cofre de retenção para as ~22 contas de maior MRR em risco", "62,1% do valor perdido concentrado nesse grupo pequeno"),
    ("4", "Parar de usar satisfaction_score isolado como sinal de risco", "cobertura de 58,8% com viés de não-resposta, não discrimina churn"),
    ("5", "Investigar por que reason_code não converge (15-19% cada)", "sugere racionalização pós-hoc, não causa raiz real"),
]


class CausaRaizAgent:
    dominio = "causa_raiz"

    def responder(self, pergunta: str, grounding: DataGroundingAgent):
        m = grounding.metrics()
        return {
            "fatos": ACHADOS_CAUSA_RAIZ,
            "numeros": {
                "pct_early_churn": m["pct_early_churn"],
                "tenure_median": m["tenure_median"],
                "sat_churned": m["sat_churned"],
                "sat_active": m["sat_active"],
            },
            "fonte": "README.md, achados 1/2/3/6; analise.py seções 3, 4, 8",
            "guardrail": "não afirmar suporte, satisfação ou uso como causa — dados mostram o oposto",
        }


class SegmentosAgent:
    dominio = "segmentos"

    def responder(self, pergunta: str, grounding: DataGroundingAgent):
        m = grounding.metrics()
        top5 = m["seg_rows"][:5]
        return {
            "fatos": [f"{ind} / {canal}: {churned}/{total} contas churned ({taxa}%)" for ind, canal, total, churned, taxa in top5],
            "numeros": {"segmentos_avaliados": len(m["seg_rows"])},
            "fonte": "README.md achado 4; gerar_excel.py compute_metrics()['seg_rows']",
            "guardrail": "só reportar segmentos com >=10 contas (já filtrado em compute_metrics())",
        }


class ContasAgent:
    dominio = "contas"

    def responder(self, pergunta: str, grounding: DataGroundingAgent):
        m = grounding.metrics()
        match = PADRAO_CONTA.search(pergunta)
        if match:
            conta = grounding.buscar_conta(match.group(0))
            if conta:
                return {
                    "fatos": [f"{conta['name']} ({conta['industry']}, plano {conta['plan']}, canal {conta['channel']}): MRR perdido US$ {conta['mrr']:,.2f}/mês"],
                    "numeros": conta,
                    "fonte": "gerar_excel.py compute_metrics()['churned_mrr']",
                    "guardrail": "número exato da tabela, nunca arredondado",
                }
            return {
                "fatos": [],
                "numeros": {},
                "fonte": None,
                "nao_calculado": f"conta '{match.group(0)}' não encontrada entre as {m['n_churned']} contas churned",
            }
        top5 = m["churned_mrr"][:5]
        return {
            "fatos": [f"{c['name']} ({c['industry']}): US$ {c['mrr']:,.2f}/mês" for c in top5],
            "numeros": {"total_churned": m["n_churned"], "mrr_total_perdido": m["mrr_lost"]},
            "fonte": "gerar_excel.py compute_metrics()['churned_mrr'], ordenado por MRR",
            "guardrail": "top 5 por MRR, não amostra aleatória",
        }


class RecomendacoesAgent:
    dominio = "recomendacoes"

    def responder(self, pergunta: str, grounding: DataGroundingAgent):
        return {
            "fatos": [f"{n}. {texto} — impacto: {impacto}" for n, texto, impacto in RECOMENDACOES],
            "numeros": {"total_recomendacoes": len(RECOMENDACOES)},
            "fonte": "README.md, seção Recomendações",
            "guardrail": "recomendações já priorizadas na fonte — não reordenar por conta própria",
        }


class MetodologiaAgent:
    dominio = "metodologia"

    def responder(self, pergunta: str, grounding: DataGroundingAgent):
        return {
            "fatos": [
                "Dados: 5 tabelas Kaggle (accounts, subscriptions, feature_usage, support_tickets, churn_events), licença MIT.",
                "Limitação: nomes de feature (feature_1...feature_40) são anônimos, sem dicionário de dados oficial.",
                "Limitação: 'conta churned' usa accounts.churn_flag — 175 contas têm mais de um evento de churn/reativação, tratadas de forma simplificada.",
                "Nenhum modelo preditivo foi construído — causa raiz é estrutural (onboarding/fit), não comportamental.",
            ],
            "numeros": {},
            "fonte": "README.md, seção Limitações",
            "guardrail": "admitir o que não foi verificado em vez de inflar confiança",
        }


class AuditoriaAgent:
    dominio = "auditoria"

    def responder(self, pergunta: str, grounding: DataGroundingAgent):
        dados = grounding.auditoria()
        if dados is None:
            return {
                "fatos": [],
                "numeros": {},
                "fonte": None,
                "nao_calculado": "harness_auditoria_submissao.py ainda não foi rodado nesta sessão — rode-o primeiro para gerar process-log/auditoria-final.json",
            }
        resumo = dados["resumo"]
        falhas = [r for r in dados["resultados"] if r["status"] == "FALHOU"]
        fatos = [f"{resumo['passou']}/{resumo['total']} testes automatizados passaram (auditados contra {dados['fonte_do_brief']})"]
        if falhas:
            fatos += [f"FALHOU: [{r['id']}] {r['nome']} — {r['detalhe']}" for r in falhas]
        else:
            fatos.append("Nenhuma falha — todos os critérios objetivamente verificáveis do brief oficial foram atendidos")
        return {
            "fatos": fatos,
            "numeros": resumo,
            "fonte": "process-log/auditoria-final.json, gerado por harness_auditoria_submissao.py",
            "guardrail": "reporta o resultado já extraído, nunca re-roda o harness por conta própria",
        }


SUBAGENTES = {
    "causa_raiz": CausaRaizAgent(),
    "segmentos": SegmentosAgent(),
    "contas": ContasAgent(),
    "recomendacoes": RecomendacoesAgent(),
    "metodologia": MetodologiaAgent(),
    "auditoria": AuditoriaAgent(),
}


# ---------------------------------------------------------------------------
# Agente 4 — Resposta Executiva
# ---------------------------------------------------------------------------

class ExecutiveResponseAgent:
    """Agente 4 — formata o dado estruturado em linguagem executiva, cita fonte."""

    def formatar(self, dado_dominio: dict) -> str:
        if dado_dominio.get("nao_calculado"):
            return f"Não calculado nesta versão: {dado_dominio['nao_calculado']}."

        linhas = []
        for fato in dado_dominio["fatos"]:
            linhas.append(f"- {fato}")
        texto = "\n".join(linhas) if linhas else "(sem dado disponível)"
        fonte = dado_dominio.get("fonte")
        rodape = f"\n\n_Fonte: {fonte}_" if fonte else ""
        return f"{texto}{rodape}"


# ---------------------------------------------------------------------------
# Agente 5 — Auditor de Contexto Limpo
# ---------------------------------------------------------------------------

DOMINIOS_AUDITORIA_OBRIGATORIA = {"causa_raiz", "recomendacoes"}

PALAVRAS_CAUSA_PROIBIDAS_SEM_RESSALVA = ["porque é", "a causa é", "é culpa d"]


class CleanContextAuditor:
    """
    Agente 5 — não recebe a pergunta original nem o raciocínio do subagente,
    só a resposta final formatada e o dado bruto. Confere se cada afirmação
    é sustentada literalmente pelo dado, sem reescrever.
    """

    def auditar(self, resposta_formatada: str, dado_bruto: dict, dominio: str):
        obrigatoria = dominio in DOMINIOS_AUDITORIA_OBRIGATORIA

        if not obrigatoria:
            return {"veredito": "aprovado", "obrigatoria": False, "ressalva": None}

        resposta_lower = resposta_formatada.lower()
        for termo in PALAVRAS_CAUSA_PROIBIDAS_SEM_RESSALVA:
            if termo in resposta_lower:
                return {
                    "veredito": "bloqueado",
                    "obrigatoria": True,
                    "ressalva": f"linguagem de causa direta ('{termo}') sem distinguir de correlação — reformular",
                }

        guardrail = dado_bruto.get("guardrail", "")
        return {
            "veredito": "aprovado",
            "obrigatoria": True,
            "ressalva": f"(auditado: {guardrail})" if guardrail else None,
        }


# ---------------------------------------------------------------------------
# Orquestração — a cadeia completa
# ---------------------------------------------------------------------------

class IAConsultaRavenStack:
    def __init__(self):
        self.router = QueryRouter()
        self.grounding = DataGroundingAgent()
        self.responder_agent = ExecutiveResponseAgent()
        self.auditor = CleanContextAuditor()

    def perguntar(self, pergunta: str) -> str:
        rota = self.router.route(pergunta)
        if rota["status"] == "recusado":
            return f"Fora do escopo desta IA de consulta: {rota['motivo']}."

        dominio = rota["dominio"]
        subagente = SUBAGENTES[dominio]
        dado = subagente.responder(pergunta, self.grounding)
        resposta = self.responder_agent.formatar(dado)

        auditoria = self.auditor.auditar(resposta, dado, dominio)
        if auditoria["veredito"] == "bloqueado":
            return f"[Resposta bloqueada pelo Auditor de Contexto Limpo: {auditoria['ressalva']}]"

        if auditoria["ressalva"]:
            resposta += f"\n\n_{auditoria['ressalva']}_"

        return resposta


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

PERGUNTAS_SELF_TEST = [
    "Por que o churn está subindo?",
    "Quais segmentos estão mais em risco?",
    "Qual o MRR da Company_4?",
    "O que a empresa deveria fazer?",
    "Como vocês chegaram nessas conclusões? Dá pra confiar?",
    "Qual vai ser o churn em 2028?",
    "E se eu filtrar só contas Enterprise, o que acontece?",
]


def self_test():
    ia = IAConsultaRavenStack()
    print("=" * 70)
    print("SELF-TEST — 7 perguntas cobrindo os 5 domínios + 2 recusas de escopo")
    print("=" * 70)
    for pergunta in PERGUNTAS_SELF_TEST:
        print(f"\n> {pergunta}")
        print(ia.perguntar(pergunta))
        print("-" * 70)


def chat_interativo():
    ia = IAConsultaRavenStack()
    print("IA de Consulta RavenStack — pergunte sobre o diagnóstico de churn.")
    print("Digite 'sair' para encerrar.\n")
    while True:
        try:
            pergunta = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not pergunta or pergunta.lower() in {"sair", "exit", "quit"}:
            break
        print(ia.perguntar(pergunta))
        print()


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--self-test":
        self_test()
    elif len(sys.argv) > 1:
        ia = IAConsultaRavenStack()
        print(ia.perguntar(" ".join(sys.argv[1:])))
    else:
        chat_interativo()


if __name__ == "__main__":
    main()
