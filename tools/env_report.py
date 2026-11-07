"""Registra o ambiente de execucao (SO, CPU, Python, cliente ZMQ).

Uso: python tools/env_report.py
Gera results/ambiente.json, citado na secao de Metodologia do artigo.
"""
from __future__ import annotations

import datetime
import json
import os
import platform
import sys


def coletar() -> dict:
    info = {
        "data_coleta": datetime.datetime.now().isoformat(timespec="seconds"),
        "python_versao": sys.version.split()[0],
        "python_implementacao": platform.python_implementation(),
        "python_executavel": sys.executable,
        "so": platform.system(),
        "so_release": platform.release(),
        "so_versao": platform.version(),
        "plataforma": platform.platform(),
        "arquitetura": platform.machine(),
        "processador": platform.processor() or "nao informado pelo SO",
        "nucleos_logicos": os.cpu_count(),
    }
    if info["so"] == "Darwin":
        info["macos_versao"] = platform.mac_ver()[0]
    try:
        import coppeliasim_zmqremoteapi_client  # noqa: F401
        info["cliente_zmq_coppeliasim"] = "instalado"
    except ImportError:
        info["cliente_zmq_coppeliasim"] = "nao instalado"
    return info


def main() -> int:
    info = coletar()
    texto = json.dumps(info, indent=2, ensure_ascii=False)
    print(texto)
    os.makedirs("results", exist_ok=True)
    with open(os.path.join("results", "ambiente.json"), "w", encoding="utf-8") as fh:
        fh.write(texto + "\n")
    print("\nGravado em results/ambiente.json")
    if sys.version_info < (3, 11):
        print("ATENCAO: o projeto exige Python >= 3.11.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())