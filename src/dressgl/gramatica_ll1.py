"""Gramática da DRESS-GL em BNF (Listagem 2 sem as construções EBNF)
e verificação da propriedade LL(1) por conjuntos FIRST, FOLLOW e SELECT."""

EPS, FIM = "ε", "$"

# Chave = não terminal; qualquer símbolo que não é chave é terminal.
# Classes de token do lexer: IDENT, NUM (com unidade opcional), STRING, ENUM, BOOL.
G = {
    "programa":    [["decls"]],
    "decls":       [["declaracao", "decls"], []],
    "declaracao":  [["politica"], ["regra"]],
    "politica":    [["POLICY", "IDENT", "{", "atribs", "}"]],
    "atribs":      [["atrib", "atribs"], []],
    "atrib":       [["param", "=", "literal", ";"]],
    "param":       [["budget"], ["reserve"], ["cooldown"]],
    "regra":       [["RULE", "IDENT", "prio", "GIVEN", "expr", "WHEN", "juncao",
                     "THEN", "acoes", "assert_opt", "END"]],
    "prio":        [["PRIORITY", "NUM"], []],
    "assert_opt":  [["ASSERT", "expr"], []],
    "expr":        [["conj", "expr_r"]],
    "expr_r":      [["OR", "conj", "expr_r"], []],
    "conj":        [["neg", "conj_r"]],
    "conj_r":      [["AND", "neg", "conj_r"], []],
    "neg":         [["NOT", "atomo"], ["atomo"]],
    "atomo":       [["(", "expr", ")"], ["referencia", "resto"]],
    "resto":       [["op_rel", "literal"], ["IN", "conjunto"]],
    "op_rel":      [["<"], ["<="], [">"], [">="], ["=="], ["!="]],
    "conjunto":    [["{", "ENUM", "enums", "}"]],
    "enums":       [[",", "ENUM", "enums"], []],
    "referencia":  [["IDENT", "campo"], ["alvo", ".", "IDENT"]],
    "campo":       [[".", "IDENT"], []],
    "alvo":        [["view", "STRING"], ["pass", "STRING"]],
    "juncao":      [["fase", "pass", "STRING"]],
    "fase":        [["BEFORE"], ["AFTER"], ["AROUND"]],
    "acoes":       [["acao", ";", "acoes_r"]],
    "acoes_r":     [["acao", ";", "acoes_r"], []],
    "acao":        [["SET", "alvo", ".", "IDENT", "=", "literal"],
                    ["SCALE", "recurso", "STRING", "BY", "NUM"],
                    ["INJECT", "pass", "STRING", "fase_rel", "STRING"],
                    ["SUPPRESS", "pass", "STRING"],
                    ["HIGHLIGHT", "extremo", "referencia", "within"],
                    ["MARK", "alvo", "STALE"]],
    "within":      [["WITHIN", "literal"], []],
    "recurso":     [["instances"], ["resolution"]],
    "fase_rel":    [["BEFORE"], ["AFTER"]],
    "extremo":     [["ARGMAX"], ["ARGMIN"]],
    "literal":     [["NUM"], ["ENUM"], ["BOOL"], ["STRING"]],
}
INICIAL = "programa"


def first_seq(seq, FIRST):
    out = set()
    for s in seq:
        f = FIRST[s] if s in G else {s}
        out |= f - {EPS}
        if EPS not in f:
            return out
    return out | {EPS}


def calcular_first():
    FIRST = {A: set() for A in G}
    mudou = True
    while mudou:
        mudou = False
        for A, prods in G.items():
            for p in prods:
                f = first_seq(p, FIRST)
                if not f <= FIRST[A]:
                    FIRST[A] |= f
                    mudou = True
    return FIRST


def calcular_follow(FIRST):
    FOLLOW = {A: set() for A in G}
    FOLLOW[INICIAL].add(FIM)
    mudou = True
    while mudou:
        mudou = False
        for A, prods in G.items():
            for p in prods:
                for i, B in enumerate(p):
                    if B not in G:
                        continue
                    f = first_seq(p[i + 1:], FIRST)
                    novo = (f - {EPS}) | (FOLLOW[A] if EPS in f else set())
                    if not novo <= FOLLOW[B]:
                        FOLLOW[B] |= novo
                        mudou = True
    return FOLLOW


def select(A, p, FIRST, FOLLOW):
    f = first_seq(p, FIRST)
    return (f - {EPS}) | (FOLLOW[A] if EPS in f else set())


def conflitos_ll1():
    FIRST = calcular_first()
    FOLLOW = calcular_follow(FIRST)
    out = []
    for A, prods in G.items():
        sel = [(p, select(A, p, FIRST, FOLLOW)) for p in prods]
        for i in range(len(sel)):
            for j in range(i + 1, len(sel)):
                inter = sel[i][1] & sel[j][1]
                if inter:
                    out.append((A, sel[i][0], sel[j][0], inter))
    return out


def nao_alcancaveis():
    vistos, pilha = {INICIAL}, [INICIAL]
    while pilha:
        for p in G[pilha.pop()]:
            for s in p:
                if s in G and s not in vistos:
                    vistos.add(s)
                    pilha.append(s)
    return set(G) - vistos


if __name__ == "__main__":
    FIRST = calcular_first()
    FOLLOW = calcular_follow(FIRST)
    fmt = lambda s: "{" + ", ".join(sorted(s)) + "}"
    print(f"{'Não terminal':<12} | FIRST | FOLLOW")
    for A in G:
        print(f"{A:<12} | {fmt(FIRST[A])} | {fmt(FOLLOW[A])}")
    terminais = sorted({s for ps in G.values() for p in ps for s in p if s not in G})
    print("\nTerminais:", " ".join(terminais))
    print("Não alcançáveis:", nao_alcancaveis() or "nenhum")
    c = conflitos_ll1()
    print("Conflitos LL(1):", c or "nenhum, a gramática é LL(1)")
    raise SystemExit(1 if c else 0)