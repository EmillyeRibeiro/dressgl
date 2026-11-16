"""Resumo pareado da varredura D56: diferença de ativações (sem_cooldown - dsl) por semente.
Uso: python tools\\resumo_varredura.py [results\\varredura_ruido.csv]"""
import csv
import statistics as st
import sys
from collections import defaultdict
from math import comb

arq = sys.argv[1] if len(sys.argv) > 1 else r"results\varredura_ruido.csv"
with open(arq, encoding="utf-8") as f:
    L = list(csv.DictReader(f))

precisa = {"erro_pos_m", "semente", "programa", "ativacoes", "retencoes"}
falta = precisa - set(L[0].keys())
if falta:
    sys.exit(f"colunas ausentes: {sorted(falta)}\ncabeçalho do CSV: {list(L[0].keys())}")

por = defaultdict(dict)
for l in L:
    por[(float(l["erro_pos_m"]), int(l["semente"]))][l["programa"]] = l

print("| σ (m) | Δ ativ. min | mediana | max | sem>dsl | = | sem<dsl | p sinal (unilateral) | retenções dsl min–max |")
print("|---|---|---|---|---|---|---|---|---|")
for e in sorted({k[0] for k in por}):
    g = [v for k, v in sorted(por.items()) if k[0] == e]
    d = [int(v["dsl_sem_cooldown"]["ativacoes"]) - int(v["dsl"]["ativacoes"]) for v in g]
    r = [int(v["dsl"]["retencoes"]) for v in g]
    pos, neg = sum(x > 0 for x in d), sum(x < 0 for x in d)
    n = pos + neg
    p = sum(comb(n, i) for i in range(pos, n + 1)) / 2 ** n if n else float("nan")
    print(f"| {e:.2f} | {min(d)} | {st.median(d):.1f} | {max(d)} | {pos} | {len(d) - n} | {neg} "
          f"| {p:.3f} | {min(r)}–{max(r)} |")