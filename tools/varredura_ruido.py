"""D56: varredura erro x semente, offline (sem CoppeliaSim, sem subprocessos).

Uso: python tools\\varredura_ruido.py examples\\missoes\\margem_ruido.toml
Lê results\\gravacao_<gravacao_base>.jsonl, grava as percebidas em results\\percepcao\\
(fora do glob da matriz C4) e roda dsl e dsl_sem_cooldown no hospedeiro simulado.
Saída: results\\varredura_ruido.csv e um resumo em Markdown.
"""
import argparse
import csv
import dataclasses
import hashlib
import statistics as st
import sys
import tomllib
from pathlib import Path

from dressgl import trace
from dressgl.experimentos import carregar_programa
from dressgl.modelo import MODELO_PADRAO, carregar
from dressgl.simulador import executar
from ponte_coppelia.fonte import carregar_gravacao
from ponte_coppelia.percepcao import (aplicar, contar_trocas, escrever_jsonl, ler_jsonl,
                                      percepcao_da_missao, zonas_da_missao)

# Fixados antes de rodar (D56). Não mudar depois de ver os resultados.
ERROS = (0.0, 0.02, 0.05, 0.10)
SEMENTES = tuple(range(1, 11))
PROGRAMAS = ("dsl", "dsl_sem_cooldown")
METRICAS = ("ativacoes", "desativacoes", "retencoes", "violacoes_assert", "conflitos")
RAIZ = Path(__file__).resolve().parents[1]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("missao", type=Path)
    a = ap.parse_args(argv)

    missao = tomllib.loads(a.missao.read_text(encoding="utf-8"))
    zonas = zonas_da_missao(missao)
    p0, base = percepcao_da_missao(missao)
    arq_base = RAIZ / "results" / f"gravacao_{base}.jsonl"
    R = ler_jsonl(arq_base)
    trocas_reais = contar_trocas(R)
    pasta = RAIZ / "results" / "percepcao"
    pasta.mkdir(parents=True, exist_ok=True)

    modelo = carregar(MODELO_PADRAO)
    progs = {n: carregar_programa(n, modelo) for n in PROGRAMAS}

    linhas = []
    for erro in ERROS:
        for s in SEMENTES:
            p = dataclasses.replace(p0, erro_pos_m=erro, semente=s)
            S = aplicar(R, zonas, p)
            n_dif = sum(r["terrain.below"] != x["terrain.below"] for r, x in zip(R, S))
            if erro == 0 and n_dif:
                sys.exit(f"erro=0, mas {n_dif} quadros divergem: as zonas do TOML não "
                         "reproduzem a gravação. Rode aplicar_percepcao.py --verificar.")
            arq = pasta / f"gravacao_{base}__e{erro:.2f}_s{s:02d}.jsonl"
            escrever_jsonl(arq, S)
            cenario = carregar_gravacao(arq)
            comum = {"erro_pos_m": erro, "semente": s, "quadros_divergentes": n_dif,
                     "trocas_reais": trocas_reais, "trocas_percebidas": contar_trocas(S)}
            for n, prog in progs.items():
                orc = prog.politica.budget_ms if prog.politica else None
                m = trace.metricas(executar(prog, cenario), orc)
                linhas.append({**comum, "programa": n, **{k: m.get(k) for k in METRICAS}})
        print(f"erro={erro:.2f} pronto", file=sys.stderr)

    saida = RAIZ / "results" / "varredura_ruido.csv"
    campos = ["erro_pos_m", "semente", "programa", "quadros_divergentes",
              "trocas_reais", "trocas_percebidas", *METRICAS]
    with open(saida, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(linhas)

    h = hashlib.sha256(arq_base.read_bytes()).hexdigest()[:12]
    print(f"gravacao_base {arq_base.name} sha256={h} quadros={len(R)} trocas_reais={trocas_reais}")
    print(f"percepcao tau={p0.tau_s} s sensor={p0.hz_sensor} Hz sementes={SEMENTES[0]}-{SEMENTES[-1]}\n")
    print("| erro_pos_m | programa | trocas_percebidas | ativacoes | retencoes |")
    print("|---|---|---|---|---|")
    for erro in ERROS:
        for n in PROGRAMAS:
            g = [l for l in linhas if l["erro_pos_m"] == erro and l["programa"] == n]
            med = lambda k: st.median(l[k] for l in g)
            print(f"| {erro:.2f} | {n} | {med('trocas_percebidas'):.1f} | "
                  f"{med('ativacoes'):.1f} | {med('retencoes'):.1f} |")
    print()
    pa, pb = PROGRAMAS
    for erro in ERROS:
        A = {l["semente"]: l for l in linhas if l["erro_pos_m"] == erro and l["programa"] == pa}
        B = {l["semente"]: l for l in linhas if l["erro_pos_m"] == erro and l["programa"] == pb}
        mais = sum(B[s]["ativacoes"] > A[s]["ativacoes"] for s in SEMENTES)
        igual = sum(B[s]["ativacoes"] == A[s]["ativacoes"] for s in SEMENTES)
        print(f"erro={erro:.2f}: {pb} ativou mais que {pa} em {mais}/{len(SEMENTES)}, "
              f"igual em {igual}/{len(SEMENTES)}")
    print(f"\ncsv: {saida.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())