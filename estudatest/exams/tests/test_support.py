"""Utilitários compartilhados entre os módulos de teste de exams/."""
from django.http import QueryDict


def make_querydict(data):
    """Constrói um QueryDict mutável a partir de um dict simples.
    Valores em lista/tupla viram múltiplos valores (equivalente a um POST real
    com múltiplos inputs de mesmo name, como data_options[])."""
    qd = QueryDict(mutable=True)
    for key, value in data.items():
        if isinstance(value, (list, tuple)):
            qd.setlist(key, list(value))
        else:
            qd[key] = value
    return qd