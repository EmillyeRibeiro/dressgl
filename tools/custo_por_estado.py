"""Custo e violações por quadro com a SafeSetdownAssist ativa e inativa.
Procura em qualquer nível do trace campos numéricos com cara de custo
(..._ms, custo, cost, tempo, duracao). Campos dentro de listas são somados.
Para cada campo, imprime também a diferença das medianas (ativa - inativa).
Uso: python tools\\custo_por_estado.py TRACE.jsonl [...]
     python tools\\custo_por_estado.py "results\\trace_coppelia_*__borda_agua.jsonl"
"""
import glob
import json
import re
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

REGRA = "SafeSetdownAssist"
CAMPOS_ATIVAS = ("ativas", "regras_ativas", "active", "ativos")
CUSTO = re.compile(r"(_ms$|^ms$|custo|cost|tempo|durac|budget)", re.I)


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
    if isinstance(v, (list, dict)):
        return len(v)
    if isinstance(v, str):
        return 1 if v.strip() else 0
    return int(v or 0)


def resumo(x):
    return f"mediana {st.median(x):7.2f}  max {max(x):7.2f}  n={len(x)}" if x else "-"


def ler(caminho):
    with open(caminho, encoding="utf-8") as f:
        return [json.loads(s) for s in f if s.strip()]


def expandir(args):
    """O cmd do Windows não expande curingas; fazemos isso aqui."""
    saida = []
    for a in args:
        achados = sorted(glob.glob(a))
        if achados:
            saida.extend(achados)
        elif Path(a).exists():
            saida.append(a)
        else:
            print(f"AVISO: {a} não existe (nem como padrão)", file=sys.stderr)
    return saida


def campo_ativas(L):
    for c in CAMPOS_ATIVAS:
        if any(c in l for l in L):
            return c
    return None


def analisar(t):
    L = ler(t)
    print(t)
    if not L:
        print("  trace vazio")
        return
    campo = campo_ativas(L)
    if campo is None:
        print(f"  AVISO: nenhum campo de regras ativas ({', '.join(CAMPOS_ATIVAS)}); "
              f"chaves do quadro 0: {list(L[0])}")

    def ativa(l):  # serve para lista de nomes ou de objetos
        return campo is not None and REGRA in json.dumps(l.get(campo), ensure_ascii=False)

    por = defaultdict(lambda: {True: [], False: []})
    viol = {True: [], False: []}
    for l in L:
        on = ativa(l)
        viol[on].append(n_viol(l.get("violacoes")))
        for c, v in custos(l).items():
            por[c][on].append(v)

    print(f"  campo de regras ativas: {campo}; quadros com {REGRA}: "
          f"{len(viol[True])}/{len(L)}")
    if campo is not None and not viol[True]:
        print(f"  AVISO: {REGRA} não aparece em '{campo}' em nenhum quadro")
    print(f"  violações/quadro  inativa: {resumo(viol[False])}")
    print(f"                    ativa  : {resumo(viol[True])}")

    if not por:
        q = next((l for l in L if ativa(l)), L[0])
        print(f"  nenhum campo de custo; estrutura do quadro {q.get('quadro', '?')}:")
        for c, v in list(achatar(q))[:60]:
            print(f"    {c} = {str(v)[:60]}")
        return

    for c, d in sorted(por.items()):
        print(f"  [{c}]\n    inativa: {resumo(d[False])}\n    ativa  : {resumo(d[True])}")
        if d[True] and d[False]:
            delta = st.median(d[True]) - st.median(d[False])
            print(f"    delta mediana (ativa - inativa): {delta:+7.2f}")


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print(__doc__, file=sys.stderr)
        return 2
    traces = expandir(argv)
    if not traces:
        return 2
    for t in traces:
        analisar(t)
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())