"""Janela de reprodução das gravações (extra gui, D61-D64)."""
from __future__ import annotations

import time
import tkinter as tk
from tkinter import ttk

from .imagem import ajustar, para_ppm

ORCAMENTO_MS = 16.67
# Tamanho de exibição (largura, altura), independente da resolução do render (2× a nominal).
SUPERFICIES = {"FPV": (640, 360), "MAP": (256, 256), "AGRO": (192, 192)}
# (linha, coluna, rowspan): MAP e AGRO empilhados ao lado do FPV para caber em 1920 px a 125 %.
POSICOES = {"FPV": (0, 0, 2), "MAP": (0, 1, 1), "AGRO": (1, 1, 1)}
LARG_GRAF, ALT_GRAF, ESCALA_MS = 900, 140, 20.0
CAMPO_PX, CAMPO_M = 250, 5.0          # campo de 5 × 5 m, de -2,5 a 2,5
CORES_SOLO = {"BARE_SOIL": "#c9a678", "STANDING_CROP": "#6aa84f", "WATER": "#3d85c6"}
RAIO_PT = 4
FORA = (-20, -20, -20, -20)


class Janela:
    def __init__(self, raiz: tk.Tk, fabrica_fonte, total_quadros: int, titulo: str,
                 zonas=(), waypoints=()):
        self.raiz, self.fabrica, self.total = raiz, fabrica_fonte, total_quadros
        self.zonas, self.waypoints = list(zonas), list(waypoints)
        raiz.title(titulo)
        self._montar()
        self._reiniciar()
        self._id_tique = self.raiz.after(16, self._tique)

    def fechar(self):
        self.raiz.after_cancel(self._id_tique)
        self.raiz.destroy()

    # ---------- montagem ----------
    def _montar(self):
        topo = ttk.Frame(self.raiz)
        topo.grid(row=0, column=0, sticky="nw", padx=6, pady=6)
        self.fotos, self.telas = {}, {}
        for nome, (w, h) in SUPERFICIES.items():
            lin, col, span = POSICOES[nome]
            quadro = ttk.LabelFrame(topo, text=nome)
            quadro.grid(row=lin, column=col, rowspan=span, padx=4, pady=(0, 4), sticky="nw")
            tela = tk.Canvas(quadro, width=w, height=h, bg="black", highlightthickness=0)
            tela.pack()
            self.fotos[nome] = tk.PhotoImage(width=w, height=h)
            tela.create_image(0, 0, anchor="nw", image=self.fotos[nome])
            self.telas[nome] = tela

        lateral = ttk.Frame(self.raiz)
        lateral.grid(row=0, column=1, sticky="n", padx=6, pady=6)

        painel = ttk.LabelFrame(lateral, text="Motor")
        painel.pack(fill="x")
        campos = [("quadro", "Quadro"), ("bateria", "Bateria"), ("solo", "Solo"),
                  ("budget", "frame_budget"), ("pior", "Pior quadro"),
                  ("acima", "% acima"), ("ativas", "Ativas"), ("retidas", "Retidas (total)"),
                  ("conflitos", "Conflitos (total)"), ("violacoes", "Violações (total)"),
                  ("fps", "Quadros/s reais")]
        self.v = {k: tk.StringVar(value="–") for k, _ in campos}
        for i, (k, rotulo) in enumerate(campos):
            ttk.Label(painel, text=rotulo).grid(row=i, column=0, sticky="nw", padx=4)
            ttk.Label(painel, textvariable=self.v[k], font=("Consolas", 11),
                      wraplength=200 if k == "ativas" else 0, justify="left"
                      ).grid(row=i, column=1, sticky="w", padx=4)

        caixa = ttk.LabelFrame(lateral, text="Campo 5 × 5 m")
        caixa.pack(fill="x", pady=(6, 0))
        self.campo = tk.Canvas(caixa, width=CAMPO_PX, height=CAMPO_PX, bg="#eeeeee",
                               highlightthickness=0)
        self.campo.pack()
        ttk.Label(caixa, text="preto: real    laranja: percebida").pack()
        self._desenhar_campo()

        self.graf = tk.Canvas(self.raiz, width=LARG_GRAF, height=ALT_GRAF, bg="white")
        self.graf.grid(row=1, column=0, columnspan=2, padx=6, pady=4)

        ctl = ttk.Frame(self.raiz)
        ctl.grid(row=2, column=0, columnspan=2, pady=6)
        self.btn = ttk.Button(ctl, text="▶ tocar", command=self._alternar)
        self.btn.pack(side="left", padx=4)
        ttk.Button(ctl, text="passo", command=self._passo).pack(side="left", padx=4)
        ttk.Button(ctl, text="reiniciar", command=self._reiniciar).pack(side="left", padx=4)
        ttk.Label(ctl, text="quadros por tique").pack(side="left", padx=(16, 4))
        self.vel = tk.DoubleVar(value=1.0)
        ttk.Scale(ctl, from_=0.25, to=8.0, variable=self.vel, length=200
                  ).pack(side="left")
        self.raiz.bind("<space>", lambda e: self._alternar())
        self.raiz.bind("<Right>", lambda e: self._passo())

    # ---------- campo ----------
    def _m(self, x, y):
        """Metros -> pixels do mapa (y para cima)."""
        s = CAMPO_PX / CAMPO_M
        return (x + CAMPO_M / 2) * s, (CAMPO_M / 2 - y) * s

    def _desenhar_campo(self):
        c = self.campo
        # Desenhadas na ordem do TOML: a zona posterior fica por cima.
        # ADAPTAR: confirmar com ponte_coppelia/missao.py (solo_em) que a precedência é a mesma.
        for z in self.zonas:
            x0, y0 = self._m(z["x"][0], z["y"][1])
            x1, y1 = self._m(z["x"][1], z["y"][0])
            c.create_rectangle(x0, y0, x1, y1, outline="",
                               fill=CORES_SOLO.get(z["solo"], "#999999"))
        pts = [v for w in self.waypoints for v in self._m(w["pos"][0], w["pos"][1])]
        if len(pts) >= 4:
            c.create_line(*pts, dash=(2, 2), fill="white")
        self.pt_real = c.create_oval(*FORA, fill="black", outline="white", tags="ponto")
        self.pt_perc = c.create_oval(*FORA, fill="orange", outline="black", tags="ponto")

    def _mover(self, item, pos):
        if pos is None:
            self.campo.coords(item, *FORA)
            return
        x, y = self._m(pos[0], pos[1])
        self.campo.coords(item, x - RAIO_PT, y - RAIO_PT, x + RAIO_PT, y + RAIO_PT)

    # ---------- gráfico ----------
    def _x(self, q):
        return 10 + q / max(1, self.total - 1) * (LARG_GRAF - 20)

    def _y(self, ms):
        return ALT_GRAF - 10 - min(ms, ESCALA_MS) / ESCALA_MS * (ALT_GRAF - 20)

    def _eixos(self):
        g = self.graf
        g.delete("all")
        y = self._y(ORCAMENTO_MS)
        g.create_line(10, y, LARG_GRAF - 10, y, dash=(4, 3), fill="red")
        g.create_text(LARG_GRAF - 12, y - 8, text="16,67 ms", anchor="e", fill="red")
        self.cursor = g.create_line(10, 5, 10, ALT_GRAF - 5, fill="gray")

    # ---------- execução ----------
    def _reiniciar(self):
        self.fonte = iter(self.fabrica())
        self.tocando, self.acum, self.anterior, self.ant_real = False, 0.0, None, None
        self.n = self.n_acima = self.retidas = self.conflitos = self.violacoes = 0
        self.pior, self.ultima_img, self.ultimo = 0.0, {}, None
        self.t0, self.n0 = time.perf_counter(), 0
        self.btn.configure(text="▶ tocar")
        self._eixos()
        self.campo.delete("rastro")
        self._mover(self.pt_real, None)
        self._mover(self.pt_perc, None)
        for nome, (w, h) in SUPERFICIES.items():
            self.fotos[nome].blank()
            t = self.telas[nome]
            t.delete("aviso")
            t.create_text(w // 2, h // 2, text="sem imagem", fill="gray60", tags="aviso")

    def _alternar(self):
        self.tocando = not self.tocando
        self.btn.configure(text="⏸ pausar" if self.tocando else "▶ tocar")
        self.t0, self.n0 = time.perf_counter(), self.n

    def _avancar(self, n: int) -> bool:
        for _ in range(n):
            q = next(self.fonte, None)
            if q is None:
                if self.tocando:
                    self._alternar()
                return False
            self._registrar(q)
        return True

    def _passo(self):
        self._avancar(1)
        self._mostrar()

    def _tique(self):
        if self.tocando:
            self.acum += self.vel.get()
            n, self.acum = int(self.acum), self.acum - int(self.acum)
            self._avancar(n)
            self._mostrar()
        self._id_tique = self.raiz.after(16, self._tique)

    def _registrar(self, q):
        """Chamado em todo quadro simulado, mesmo nos que não são exibidos."""
        b = float(q.leituras["frame_budget"])
        self.n += 1
        self.n_acima += b > ORCAMENTO_MS
        self.pior = max(self.pior, b)
        self.retidas += len(q.retidas)
        self.conflitos += q.conflitos
        self.violacoes += q.violacoes
        self.ultima_img.update(q.imagens)   # superfície decimada mantém a última imagem
        x, y = self._x(q.indice), self._y(b)
        if self.anterior:
            self.graf.create_line(*self.anterior, x, y,
                                  fill="red" if b > ORCAMENTO_MS else "navy")
        self.anterior, self.ultimo = (x, y), q
        if q.pos_real is not None:
            p = self._m(q.pos_real[0], q.pos_real[1])
            if self.ant_real:
                self.campo.create_line(*self.ant_real, *p, fill="black", tags="rastro")
            self.ant_real = p

    def _mostrar(self):
        q = self.ultimo
        if q is None:
            return
        for nome, img in self.ultima_img.items():
            w, h = SUPERFICIES[nome]
            self.fotos[nome].configure(data=para_ppm(ajustar(img, h, w)), format="PPM")
            self.telas[nome].delete("aviso")
        self.ultima_img = {}
        L = q.leituras
        bat = L.get("drone.battery")
        self.v["quadro"].set(f"{q.indice} / {self.total - 1}")
        self.v["bateria"].set("–" if bat is None else f"{float(bat):.2f} %")
        self.v["solo"].set(str(L.get("terrain.below", "–")))
        self.v["budget"].set(f"{float(L['frame_budget']):.2f} ms")
        self.v["pior"].set(f"{self.pior:.2f} ms")
        self.v["acima"].set(f"{100 * self.n_acima / self.n:.2f} %")
        self.v["ativas"].set(", ".join(q.ativas) or "nenhuma")
        self.v["retidas"].set(str(self.retidas))
        self.v["conflitos"].set(str(self.conflitos))
        self.v["violacoes"].set(str(self.violacoes))
        dt = time.perf_counter() - self.t0
        if dt > 0.5:
            self.v["fps"].set(f"{(self.n - self.n0) / dt:.0f}")
        x = self._x(q.indice)
        self.graf.coords(self.cursor, x, 5, x, ALT_GRAF - 5)
        self._mover(self.pt_real, q.pos_real)
        self._mover(self.pt_perc, q.pos_percebida)
        self.campo.tag_raise("ponto")