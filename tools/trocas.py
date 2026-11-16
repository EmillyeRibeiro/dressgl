"""Trocas de solo sob o alvo e sob o drone, pareadas, com atraso físico.
Uso: python tools\\trocas.py results\\gravacao_pouso_agua.jsonl [...]"""
import json
import statistics as st
import sys

HZ = 60


def trocas(R, campo):
    return [(b["quadro"], a[campo], b[campo])
            for a, b in zip(R, R[1:]) if a[campo] != b[campo]]


def parear(alvo, drone):
    """Para cada troca do drone, pega a última troca do alvo ainda não usada,
    anterior a ela e com o mesmo destino. As trocas do alvo puladas são
    excursões que a dinâmica 'engoliu'."""
    pares, nao_seguidas, i = [], [], 0
    for d in drone:
        cand = [j for j in range(i, len(alvo))
                if alvo[j][0] <= d[0] and alvo[j][2] == d[2]]
        if not cand:
            pares.append((None, d))
            continue
        j = cand[-1]
        nao_seguidas += alvo[i:j]
        pares.append((alvo[j], d))
        i = j + 1
    return pares, nao_seguidas + alvo[i:]


for g in sys.argv[1:]:
    R = [json.loads(s) for s in open(g, encoding="utf-8") if s.strip()]
    ta, td = trocas(R, "solo_alvo"), trocas(R, "terrain.below")
    pares, nao = parear(ta, td)
    print(f"{g}: alvo {len(ta)} trocas, drone {len(td)} trocas")
    atrasos = []
    for a, d in pares:
        if a is None:
            print(f"   drone {d[0]:>5}  {d[1]}->{d[2]}  (sem troca do alvo)")
            continue
        q = d[0] - a[0]
        atrasos.append(q)
        print(f"   alvo {a[0]:>5} -> drone {d[0]:>5}  {d[1]}->{d[2]}  "
              f"atraso {q} q ({q / HZ:.2f} s)")
    for e in nao:
        print(f"   alvo {e[0]:>5}  {e[1]}->{e[2]}  NÃO seguida pelo drone")
    if atrasos:
        print(f"   atraso: mediana {st.median(atrasos)} q "
              f"({st.median(atrasos) / HZ:.2f} s), min {min(atrasos)}, max {max(atrasos)}")
    iv = [b[0] - a[0] for a, b in zip(td, td[1:])]
    if iv:
        print(f"   menor intervalo entre trocas do drone: {min(iv)} q ({min(iv) / HZ:.2f} s)")