"""D56: gera a gravação percebida (posição com ruído) a partir de uma gravação física.
A saída vai para results\\percepcao\\, fora do glob da matriz C4.
Uso:
  python tools\\aplicar_percepcao.py examples\\missoes\\margem_ruido.toml
  python tools\\aplicar_percepcao.py examples\\missoes\\margem_ruido.toml --erro 0.10 --semente 7
  python tools\\aplicar_percepcao.py examples\\missoes\\borda_agua.toml --verificar
"""
import argparse
import dataclasses
import hashlib
import sys
import tomllib
from pathlib import Path

from ponte_coppelia.percepcao import (aplicar, classificar, contar_trocas, escrever_jsonl,
                                      ler_jsonl, percepcao_da_missao, zonas_da_missao)

RAIZ = Path(__file__).resolve().parents[1]


def nome_base(missao: dict, arq: Path) -> str:
    """Gravação física de referência: [percepcao].gravacao_base, senão o nome da missão."""
    b = missao.get("percepcao")
    if isinstance(b, dict) and "gravacao_base" in b:
        return str(b["gravacao_base"])
    return str(missao.get("nome", arq.stem))


def sha(caminho: Path) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest()[:12]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("missao", type=Path)
    ap.add_argument("--erro", type=float)
    ap.add_argument("--semente", type=int)
    ap.add_argument("--tau", type=float)
    ap.add_argument("--verificar", action="store_true",
                    help="só confere se as zonas reproduzem terrain.below da gravação base")
    a = ap.parse_args(argv)

    missao = tomllib.loads(a.missao.read_text(encoding="utf-8"))
    zonas = zonas_da_missao(missao)
    base = nome_base(missao, a.missao)
    arq_base = RAIZ / "results" / f"gravacao_{base}.jsonl"
    if not arq_base.exists():
        print(f"gravação base não encontrada: {arq_base.relative_to(RAIZ)}", file=sys.stderr)
        return 2

    if a.verificar:
        R = ler_jsonl(arq_base)
        dif = [r for r in R if classificar(r["pos"][0], r["pos"][1], zonas) != r["terrain.below"]]
        print(f"{arq_base.name} sha256={sha(arq_base)}: {len(R)} quadros, "
              f"{len(zonas)} zonas, {len(dif)} divergências")
        for r in dif[:5]:
            print(f"   quadro {r['quadro']} pos {r['pos'][:2]} gravado {r['terrain.below']} "
                  f"calculado {classificar(r['pos'][0], r['pos'][1], zonas)}")
        return 1 if dif else 0

    p, _ = percepcao_da_missao(missao)
    trocas = {"erro_pos_m": a.erro, "semente": a.semente, "tau_s": a.tau}
    p = dataclasses.replace(p, **{k: v for k, v in trocas.items() if v is not None})

    sufixo = ""
    if a.erro is not None or a.semente is not None:
        sufixo += f"__e{p.erro_pos_m:.2f}_s{p.semente:02d}"
    if a.tau is not None:
        sufixo += f"_t{p.tau_s:g}"
    destino = RAIZ / "results" / "percepcao" / f"gravacao_{a.missao.stem}{sufixo}.jsonl"
    destino.parent.mkdir(parents=True, exist_ok=True)

    R = ler_jsonl(arq_base)
    S = aplicar(R, zonas, p)
    escrever_jsonl(destino, S)

    n_dif = sum(r["terrain.below"] != s["terrain.below"] for r, s in zip(R, S))
    print(f"gravacao_base            {arq_base.name} sha256={sha(arq_base)} ({len(R)} quadros)")
    print(f"percepcao                erro={p.erro_pos_m} m tau={p.tau_s} s "
          f"sensor={p.hz_sensor} Hz semente={p.semente}")
    print(f"quadros_divergentes      {n_dif} ({100 * n_dif / len(R):.1f} %)")
    print(f"trocas_reais             {contar_trocas(R)}")
    print(f"trocas_percebidas        {contar_trocas(S)}")
    print(f"saida: {destino.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())