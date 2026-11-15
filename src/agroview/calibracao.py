"""Leitura de results/calibracao.toml (D48)."""

from __future__ import annotations

import tomllib
from pathlib import Path

CALIBRACAO_PADRAO = Path("results/calibracao.toml")


def carregar_calibracao(caminho: str | Path = CALIBRACAO_PADRAO) -> dict[str, float]:
    with open(caminho, "rb") as f:
        dados = tomllib.load(f)
    if "ms_por_carga" not in dados:
        raise ValueError(f"{caminho}: falta a tabela [ms_por_carga] (D48)")
    return dict(dados["ms_por_carga"])