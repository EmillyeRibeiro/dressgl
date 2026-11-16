"""Compara duas gravações .jsonl quadro a quadro e reporta a maior diferença por campo."""
import json, re, sys
from collections import Counter
from pathlib import Path

def folhas(x, pre=""):
    if isinstance(x, dict):
        for k, v in x.items():
            yield from folhas(v, f"{pre}.{k}" if pre else k)
    elif isinstance(x, list):
        for i, v in enumerate(x):
            yield from folhas(v, f"{pre}[{i}]")
    else:
        yield pre, x

def ler(p):
    return [json.loads(l) for l in Path(p).read_text(encoding="utf-8-sig").splitlines() if l.strip()]

def main():
    a, b = ler(sys.argv[1]), ler(sys.argv[2])
    print(f"quadros                  {len(a)} / {len(b)}")
    if len(a) != len(b):
        return 1
    dif, outros, quadros_dif = {}, Counter(), 0
    for ra, rb in zip(a, b):
        fa, fb = dict(folhas(ra)), dict(folhas(rb))
        mudou = False
        for k in fa.keys() | fb.keys():
            va, vb = fa.get(k), fb.get(k)
            if va == vb:
                continue
            mudou = True
            campo = re.sub(r"\[\d+\]", "[]", k)
            num = (int, float)
            if isinstance(va, num) and isinstance(vb, num) and not isinstance(va, bool):
                dif[campo] = max(dif.get(campo, 0.0), abs(va - vb))
            else:
                outros[campo] += 1
        quadros_dif += mudou
    print(f"quadros_divergentes      {quadros_dif}")
    for k, v in sorted(dif.items(), key=lambda kv: -kv[1]):
        print(f"  {k:<30} dif_max={v:.6g}")
    for k, n in outros.items():
        print(f"  {k:<30} {n} quadros com valor não numérico diferente")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())