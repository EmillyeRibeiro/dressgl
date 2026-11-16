"""Custo da injeção e economia das compensações por hospedeiro (D56).
frame_budget lido no quadro i+1 = custo do plano do quadro i."""
import json
import statistics as st
from pathlib import Path

REGRA = {"baseline": "SafeSetdownSemCompensacao", "dsl": "SafeSetdownAssist"}

for m in ("pouso_agua", "borda_agua"):
    for h in ("simulado", "agroview"):
        res = {}
        for prog, regra in REGRA.items():
            arq = Path("results") / f"trace_coppelia_{h}__{prog}__{m}.jsonl"
            L = [json.loads(x) for x in arq.open(encoding="utf-8") if x.strip()]
            A = [L[i + 1]["leituras"]["frame_budget"] for i in range(len(L) - 1) if L[i]["condicoes"].get(regra)]
            B = [L[i + 1]["leituras"]["frame_budget"] for i in range(len(L) - 1) if not L[i]["condicoes"].get(regra)]
            res[prog] = (st.median(A), max(A), st.median(B), len(A))
        b, d = res["baseline"], res["dsl"]
        print(f"{m:10} {h:8} n={b[3]:4} nominal={b[2]:6.3f} injecao={b[0] - b[2]:6.3f} "
              f"economia_mediana={b[0] - d[0]:6.3f} economia_pior={b[1] - d[1]:6.3f} "
              f"liquido={d[0] - d[2]:6.3f} pior_dsl={d[1]:6.3f}")