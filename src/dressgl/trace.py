"""Trace em JSON Lines e métricas (P7; D30, D31)."""

from __future__ import annotations

import dataclasses
import enum
import json
from pathlib import Path


def para_json(v):
    """Converte para tipos JSON: tuplas viram listas, chaves-tupla viram
    "A.b", conjuntos viram listas ordenadas (D30)."""
    if dataclasses.is_dataclass(v) and not isinstance(v, type):
        return {f.name: para_json(getattr(v, f.name)) for f in dataclasses.fields(v)}
    if isinstance(v, enum.Enum):
        return v.name
    if isinstance(v, dict):
        return {".".join(map(str, k)) if isinstance(k, tuple) else str(k): para_json(x)
                for k, x in v.items()}
    if isinstance(v, (set, frozenset)):
        return sorted(para_json(x) for x in v)
    if isinstance(v, (tuple, list)):
        return [para_json(x) for x in v]
    return v


def linha(registro, leituras, condicoes) -> dict:
    d = para_json(registro)
    d["condicoes"] = dict(condicoes)
    d["leituras"] = para_json(leituras)
    return d


def gravar(caminho, linhas) -> None:
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8", newline="\n") as f:
        for l in linhas:
            f.write(json.dumps(l, ensure_ascii=False, allow_nan=False) + "\n")


def ler(caminho) -> list[dict]:
    with open(caminho, encoding="utf-8") as f:
        return [json.loads(s) for s in f if s.strip()]


def metricas(linhas, orcamento_ms=None, chave_tempo="frame_budget") -> dict:
    m = {
        "quadros": len(linhas),
        "ativacoes": sum(len(l["ativadas"]) for l in linhas),
        "desativacoes": sum(len(l["desativadas"]) for l in linhas),
        "retencoes": sum(len(l["retidas"]) for l in linhas),
        "violacoes_assert": sum(len(l["violacoes"]) for l in linhas),
        "conflitos": sum(len(l["conflitos"]) for l in linhas),
    }
    tempos = [l["leituras"][chave_tempo] for l in linhas if chave_tempo in l["leituras"]]
    if tempos:
        m["pior_quadro_ms"] = max(tempos)
        if orcamento_ms is not None:
            m["acima_orcamento_pct"] = 100.0 * sum(t > orcamento_ms for t in tempos) / len(tempos)
    # Atraso: quadros entre a condição ficar verdadeira e a regra ativar.
    atrasos, desde = [], {}
    for l in linhas:
        for nome, cond in l["condicoes"].items():
            if not cond:
                desde.pop(nome, None)
            else:
                desde.setdefault(nome, l["quadro"])
        for nome in l["ativadas"]:
            if nome in desde:
                atrasos.append(l["quadro"] - desde.pop(nome))
    if atrasos:
        m["atraso_ativacao_medio"] = sum(atrasos) / len(atrasos)
        m["atraso_ativacao_max"] = max(atrasos)
    return m