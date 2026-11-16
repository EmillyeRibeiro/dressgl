"""Custo e violações por quadro com a SafeSetdownAssist ativa e inativa.
Procura em qualquer nível do trace campos numéricos com cara de custo
(..._ms, custo, cost, tempo, duracao). Campos dentro de listas são somados.
Uso: python tools\\custo_por_estado.py TRACE.jsonl [...]"""
import json
import re
import statistics as st
import sys
from collections import defaultdict

REGRA = "SafeSetdownAssist"
CUSTO = re.compile(r"(_ms$|^ms$|custo|cost|tempo|durac)", re.I)


def achatar(o, p=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from achatar(v, f"{p}.{k}" if p else str(k))
    elif isinstance(o, list):
        for v in o:
            yield from achatar(v, f"{p}[]")
    else:
        yield p, o


def custos(l):
    soma = defaultdict(float)
    for caminho, v in achatar(l):
        partes = [s for s in re.split(r"[.\[\]]+", caminho) if s]
        if (partes and isinstance(v, (int, float)) and not isinstance(v, bool)
                and CUSTO.search(partes[-1])):
            soma[caminho] += v
    return soma


def n_viol(v):
    return len(v) if isinstance(v, (list, dict)) else int(v or 0)


def resumo(x):
    return f"mediana {st.median(x):7.2f}  max {max(x):7.2f}  n={len(x)}" if x else "-"


for t in sys.argv[1:]:
    L = [json.loads(s) for s in open(t, encoding="utf-8") if s.strip()]
    ativa = lambda l: REGRA in json.dumps(l.get("ativas"))  # serve para lista de nomes ou de objetos
    por = defaultdict(lambda: {True: [], False: []})
    viol = {True: [], False: []}
    for l in L:
        on = ativa(l)
        viol[on].append(n_viol(l.get("violacoes")))
        for c, v in custos(l).items():
            por[c][on].append(v)
    print(t)
    print(f"  violações/quadro  inativa: {resumo(viol[False])}")
    print(f"                    ativa  : {resumo(viol[True])}")
    if not por:
        q = next((l for l in L if ativa(l)), L[0])
        print(f"  nenhum campo de custo; estrutura do quadro {q['quadro']}:")
        for c, v in list(achatar(q))[:60]:
            print(f"    {c} = {str(v)[:60]}")
    for c, d in por.items():
        print(f"  [{c}]\n    inativa: {resumo(d[False])}\n    ativa  : {resumo(d[True])}")