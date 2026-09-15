"""
Funções auxiliares de carga/parsing compartilhadas por `analise.py`,
`gerar_excel.py` e `gerar_dashboard.py`.

Nome `io_comum.py`, não `_io.py`: `_io` colide com um módulo interno do
próprio Python (o backend em C de `io`), e `from _io import ...` falha com
`ImportError: cannot import name ... from '_io' (unknown location)` porque
o interpretador resolve o nome para o módulo embutido antes do arquivo local.

Existia antes como 3 cópias idênticas (uma por arquivo) — funcionava porque
nenhuma divergiu na prática, mas a garantia de "os três formatos nunca podem
divergir" não era estrutural, só disciplina de copiar com cuidado. Fatorado
aqui para que a garantia seja imposta pelo import, não por atenção.
"""

import csv
from datetime import datetime


def load(fname, pasta_data):
    with open(f"{pasta_data}/{fname}", encoding="utf-8") as fh:
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
