"""
Guard de entrada — valida os 5 CSVs em data/ ANTES de qualquer script
processar (analise.py, gerar_excel.py, gerar_dashboard.py, ia_consulta.py).

Objetivo: pegar três classes de erro de usuário na hora que ele carrega
uma base nova, não depois de já ter gerado README/Excel/dashboard errados
a partir dela:

  1. Base diferente/incompatível — schema errado (coluna faltando, coluna
     a mais, nome de coluna diferente) indica que a pessoa apontou para
     um CSV de outra fonte, não o dataset RavenStack esperado.
  2. Valores traduzidos/em idioma errado — as colunas categóricas deste
     dataset são todas em inglês (plan_tier=Basic/Pro/Enterprise,
     referral_source=ads/event/organic/other/partner, etc.). Se um valor
     aparecer traduzido ("Básico", "Empresarial") ou em outro idioma, é
     sinal de que a base foi editada/mesclada com outra fonte.
  3. Terminologia do domínio incorreta — reason_code, priority e outras
     colunas de vocabulário fechado têm um conjunto finito de valores
     válidos; qualquer valor fora desse conjunto pode ser erro de
     digitação, versão desatualizada do dataset, ou confusão de termos
     (ex.: usar "cancelled" quando o valor esperado é "unknown"/"pricing"/
     "support"/"competitor"/"features"/"budget").

Cada verificação tem uma mensagem de erro específica — "está errado" não
basta, precisa dizer QUAL coluna, QUAL valor inesperado, e (quando possível)
qual é o valor mais próximo esperado, para o usuário corrigir rápido.

Uso:
  python guard_entrada_dados.py           # valida data/ e imprime relatório
  from guard_entrada_dados import validar_entrada  # uso programático
"""

import csv
import re
import sys
from collections import defaultdict

DATA = "../data"

# Schema esperado: nome do arquivo -> conjunto de colunas obrigatórias.
# Fonte: cabeçalho real dos 5 CSVs do dataset RavenStack (Kaggle,
# "SaaS Subscription & Churn Analytics"), conferido linha a linha antes de
# escrever esta lista — não presumido.
SCHEMA_ESPERADO = {
    "ravenstack_accounts.csv": {
        "account_id", "account_name", "industry", "country", "signup_date",
        "referral_source", "plan_tier", "seats", "is_trial", "churn_flag",
    },
    "ravenstack_subscriptions.csv": {
        "subscription_id", "account_id", "start_date", "end_date", "plan_tier",
        "seats", "mrr_amount", "arr_amount", "is_trial", "upgrade_flag",
        "downgrade_flag", "churn_flag", "billing_frequency", "auto_renew_flag",
    },
    "ravenstack_feature_usage.csv": {
        "usage_id", "subscription_id", "usage_date", "feature_name",
        "usage_count", "usage_duration_secs", "error_count", "is_beta_feature",
    },
    "ravenstack_support_tickets.csv": {
        "ticket_id", "account_id", "submitted_at", "closed_at",
        "resolution_time_hours", "priority", "first_response_time_minutes",
        "satisfaction_score", "escalation_flag",
    },
    "ravenstack_churn_events.csv": {
        "churn_event_id", "account_id", "churn_date", "reason_code",
        "refund_amount_usd", "preceding_upgrade_flag", "preceding_downgrade_flag",
        "is_reactivation", "feedback_text",
    },
}

# Vocabulário fechado esperado por coluna — todos em inglês no dataset
# original. Qualquer valor fora desta lista (incluindo traduções) é
# sinalizado.
VOCABULARIO_FECHADO = {
    "ravenstack_accounts.csv": {
        "industry": {"Cybersecurity", "DevTools", "EdTech", "FinTech", "HealthTech"},
        "referral_source": {"ads", "event", "organic", "other", "partner"},
        "plan_tier": {"Basic", "Enterprise", "Pro"},
        "is_trial": {"True", "False"},
        "churn_flag": {"True", "False"},
    },
    "ravenstack_subscriptions.csv": {
        "plan_tier": {"Basic", "Enterprise", "Pro"},
        "billing_frequency": {"annual", "monthly"},
        "is_trial": {"True", "False"},
        "upgrade_flag": {"True", "False"},
        "downgrade_flag": {"True", "False"},
        "churn_flag": {"True", "False"},
        "auto_renew_flag": {"True", "False"},
    },
    "ravenstack_support_tickets.csv": {
        "priority": {"low", "medium", "high", "urgent"},
        "escalation_flag": {"True", "False"},
    },
    "ravenstack_churn_events.csv": {
        "reason_code": {"budget", "competitor", "features", "pricing", "support", "unknown"},
        "preceding_upgrade_flag": {"True", "False"},
        "preceding_downgrade_flag": {"True", "False"},
        "is_reactivation": {"True", "False"},
    },
}

# Traduções comuns que indicariam mistura de idioma/base — usadas só para
# dar uma mensagem de erro mais útil ("parece ser uma tradução de X"),
# não como lista exaustiva.
TRADUCOES_CONHECIDAS = {
    "básico": "Basic", "basico": "Basic",
    "empresarial": "Enterprise", "corporativo": "Enterprise",
    "profissional": "Pro",
    "mensal": "monthly", "anual": "annual",
    "verdadeiro": "True", "falso": "False", "sim": "True", "não": "False", "nao": "False",
    "baixa": "low", "média": "medium", "media": "medium", "alta": "high", "urgente": "urgent",
    "orçamento": "budget", "orcamento": "budget",
    "concorrente": "competitor", "funcionalidades": "features", "recursos": "features",
    "preço": "pricing", "preco": "pricing", "suporte": "support", "desconhecido": "unknown",
}

# Padrão esperado de identificador por tabela — pega account_id/subscription_id
# de formato claramente diferente (ex.: UUID de outro sistema, inteiro puro).
PADRAO_ID = {
    "ravenstack_accounts.csv": ("account_id", re.compile(r"^A-[0-9a-f]{6}$")),
    "ravenstack_subscriptions.csv": ("subscription_id", re.compile(r"^S-[0-9a-f]{6}$")),
    "ravenstack_support_tickets.csv": ("ticket_id", re.compile(r"^T-[0-9a-f]{6}$")),
    "ravenstack_churn_events.csv": ("churn_event_id", re.compile(r"^C-[0-9a-f]{6}$")),
    "ravenstack_feature_usage.csv": ("usage_id", re.compile(r"^U-[0-9a-f]{6}$")),
}


class ErroValidacao:
    def __init__(self, arquivo, categoria, mensagem):
        self.arquivo = arquivo
        self.categoria = categoria
        self.mensagem = mensagem

    def __str__(self):
        return f"[{self.arquivo}] ({self.categoria}) {self.mensagem}"


def _carregar_csv(caminho):
    with open(caminho, encoding="utf-8") as f:
        linhas = list(csv.DictReader(f))
    return linhas


def validar_schema(nome_arquivo, linhas, erros):
    """Classe 1: base diferente/incompatível — colunas faltando ou extras."""
    if not linhas:
        erros.append(ErroValidacao(nome_arquivo, "schema", "arquivo vazio ou sem cabeçalho"))
        return
    colunas_reais = set(linhas[0].keys())
    esperado = SCHEMA_ESPERADO[nome_arquivo]

    faltando = esperado - colunas_reais
    extras = colunas_reais - esperado

    if faltando:
        erros.append(ErroValidacao(
            nome_arquivo, "schema",
            f"colunas esperadas ausentes: {sorted(faltando)} — isto costuma indicar que o "
            f"arquivo carregado é de uma base/versão diferente do dataset RavenStack, não o "
            f"esperado pelo Challenge 001"
        ))
    if extras:
        erros.append(ErroValidacao(
            nome_arquivo, "schema",
            f"colunas inesperadas encontradas: {sorted(extras)} — confira se este é de fato "
            f"o CSV '{nome_arquivo}' do dataset Kaggle 'SaaS Subscription & Churn Analytics', "
            f"e não um export de outra fonte com nome de arquivo parecido"
        ))


def validar_vocabulario(nome_arquivo, linhas, erros):
    """Classes 2 e 3: valor traduzido/idioma errado, ou termo do domínio incorreto."""
    vocab = VOCABULARIO_FECHADO.get(nome_arquivo, {})
    if not vocab or not linhas:
        return

    valores_inesperados = defaultdict(set)
    for linha in linhas:
        for coluna, valores_validos in vocab.items():
            valor = linha.get(coluna, "").strip()
            if valor and valor not in valores_validos:
                valores_inesperados[coluna].add(valor)

    for coluna, valores in valores_inesperados.items():
        for valor in sorted(valores):
            sugestao = TRADUCOES_CONHECIDAS.get(valor.lower())
            if sugestao:
                erros.append(ErroValidacao(
                    nome_arquivo, "idioma/tradução",
                    f"coluna '{coluna}' tem o valor '{valor}', que parece ser uma tradução de "
                    f"'{sugestao}' — este dataset usa vocabulário em inglês; verifique se a "
                    f"base não foi editada/mesclada com uma versão traduzida"
                ))
            else:
                validos = ", ".join(sorted(vocab[coluna]))
                erros.append(ErroValidacao(
                    nome_arquivo, "terminologia",
                    f"coluna '{coluna}' tem o valor '{valor}', fora do vocabulário esperado "
                    f"({validos}) — pode ser erro de digitação, versão desatualizada do "
                    f"dataset, ou confusão de termo do domínio"
                ))


def validar_formato_id(nome_arquivo, linhas, erros):
    """Classe 1 (reforço): formato de identificador indica base incompatível."""
    if nome_arquivo not in PADRAO_ID or not linhas:
        return
    coluna, padrao = PADRAO_ID[nome_arquivo]
    amostra_invalida = []
    for linha in linhas[:50]:  # amostra — não precisa varrer tudo pra detectar padrão errado
        valor = linha.get(coluna, "")
        if valor and not padrao.match(valor):
            amostra_invalida.append(valor)
    if amostra_invalida:
        erros.append(ErroValidacao(
            nome_arquivo, "schema",
            f"coluna '{coluna}' tem valores fora do padrão esperado ({padrao.pattern}), "
            f"ex.: {amostra_invalida[:3]} — sinal forte de que os dados vêm de uma fonte "
            f"diferente do dataset RavenStack original"
        ))


def validar_entrada(pasta_data=DATA, verbose=True):
    """
    Valida os 5 CSVs. Retorna (ok: bool, erros: list[ErroValidacao]).
    Uso programático: outros scripts podem chamar isto antes de processar,
    e abortar cedo se ok=False, em vez de gerar artefatos a partir de dado
    incompatível.
    """
    erros = []
    for nome_arquivo in SCHEMA_ESPERADO:
        caminho = f"{pasta_data}/{nome_arquivo}"
        try:
            linhas = _carregar_csv(caminho)
        except FileNotFoundError:
            erros.append(ErroValidacao(nome_arquivo, "ausente", f"arquivo não encontrado em {caminho}"))
            continue
        except UnicodeDecodeError:
            erros.append(ErroValidacao(nome_arquivo, "encoding", "arquivo não está em UTF-8 — provável base de outra origem/exportação"))
            continue

        validar_schema(nome_arquivo, linhas, erros)
        if not any(e.arquivo == nome_arquivo and e.categoria == "schema" for e in erros):
            # só valida vocabulário/formato se o schema básico já bateu —
            # não faz sentido checar valor de coluna que nem existe
            validar_vocabulario(nome_arquivo, linhas, erros)
            validar_formato_id(nome_arquivo, linhas, erros)

    ok = len(erros) == 0
    if verbose:
        _imprimir_relatorio(erros, ok)
    return ok, erros


def _imprimir_relatorio(erros, ok):
    print("=" * 70)
    print("GUARD DE ENTRADA — validação dos 5 CSVs antes de processar")
    print("=" * 70)
    print()
    if ok:
        print("✅ Todos os 5 arquivos batem com o schema, vocabulário e formato de ID esperados.")
        print("   Seguro prosseguir para analise.py / gerar_excel.py / gerar_dashboard.py.")
    else:
        por_categoria = defaultdict(list)
        for e in erros:
            por_categoria[e.categoria].append(e)
        for categoria, lista in por_categoria.items():
            print(f"❌ {len(lista)} problema(s) de '{categoria}':")
            for e in lista:
                print(f"   [{e.arquivo}] {e.mensagem}")
            print()
        print(f"VEREDITO: {len(erros)} problema(s) encontrado(s) — corrigir a base antes de "
              f"rodar os scripts de análise, senão os artefatos gerados refletirão dado incorreto.")
    print("=" * 70)


if __name__ == "__main__":
    ok, _ = validar_entrada()
    sys.exit(0 if ok else 1)
