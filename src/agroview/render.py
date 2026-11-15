"""Renderizador em CPU do AgroView-SC (D42).

Só NumPy, sem janela e sem Qt. Cada passo produz uma imagem e informa:
- carga: número determinístico de operações por pixel (usado nos testes);
- tempo_ms: tempo de parede medido com perf_counter (calibração/medição).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter

import numpy as np

SOLOS = ("agua", "varzea", "cultivavel", "encosta", "rocha")
LIMIARES = np.array([0.20, 0.35, 0.65, 0.85])
PALETA = np.array(
    [[40, 90, 160], [90, 140, 90], [150, 120, 70], [120, 100, 80], [170, 170, 170]],
    dtype=np.float64,
)
COR_CULTURA = np.array([30, 160, 40], dtype=np.uint8)
TAM_CULTURA = 3
PASSOS = ("TerrainPass", "CropInstancesPass", "SuitabilityPass")


def resolucao(base: int, escala: float) -> int:
    """Lado da superfície depois da escala (custo ∝ escala²)."""
    if escala <= 0:
        raise ValueError("escala deve ser positiva")
    return max(1, round(base * escala))


# --- Mapa procedural -------------------------------------------------------

def _bilinear(grade: np.ndarray, lado: int) -> np.ndarray:
    g = grade.shape[0] - 1
    c = np.linspace(0.0, g, lado)
    i = np.minimum(c.astype(int), g - 1)
    t = c - i
    a = grade[np.ix_(i, i)]
    b = grade[np.ix_(i, i + 1)]
    c_ = grade[np.ix_(i + 1, i)]
    d = grade[np.ix_(i + 1, i + 1)]
    ty, tx = t[:, None], t[None, :]
    return (a * (1 - tx) + b * tx) * (1 - ty) + (c_ * (1 - tx) + d * tx) * ty


def mapa_altura(semente: int, lado: int = 256, oitavas: int = 5) -> np.ndarray:
    """Mapa de altura em [0, 1], determinístico pela semente (value noise)."""
    rng = np.random.default_rng(semente)
    h = np.zeros((lado, lado))
    amp, total = 1.0, 0.0
    for o in range(oitavas):
        g = 2 ** (o + 2)
        h += amp * _bilinear(rng.random((g + 1, g + 1)), lado)
        total += amp
        amp *= 0.5
    h /= total
    amplitude = h.max() - h.min()
    return (h - h.min()) / amplitude if amplitude > 0 else np.zeros_like(h)


def solo_em(mapa: np.ndarray, x: float, y: float) -> str:
    """Tipo de solo em (x, y) ∈ [0, 1]². Fonte futura de terrain.below."""
    if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
        raise ValueError("posição fora do mapa")
    lado = mapa.shape[0]
    i = min(int(y * lado), lado - 1)
    j = min(int(x * lado), lado - 1)
    return SOLOS[int(np.digitize(mapa[i, j], LIMIARES))]


def _reamostrar(mapa: np.ndarray, altura: int, largura: int) -> np.ndarray:
    iy = (np.arange(altura) * mapa.shape[0]) // altura
    ix = (np.arange(largura) * mapa.shape[1]) // largura
    return mapa[np.ix_(iy, ix)]


def _gradiente(alt: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    if min(alt.shape) < 2:
        z = np.zeros_like(alt)
        return z, z
    return np.gradient(alt)


# --- Passos ----------------------------------------------------------------

def terreno(mapa: np.ndarray, altura: int, largura: int) -> np.ndarray:
    alt = _reamostrar(mapa, altura, largura)
    cor = PALETA[np.digitize(alt, LIMIARES)]
    gy, gx = _gradiente(alt)
    g = gx + gy
    m = np.abs(g).max()
    luz = 1.0 - 0.3 * g / m if m > 0 else np.ones_like(alt)
    return np.clip(cor * luz[..., None], 0, 255).astype(np.uint8)


def culturas(img: np.ndarray, n: int, semente: int) -> np.ndarray:
    """Desenha n instâncias (quadrados TAM×TAM). Não altera a entrada."""
    out = img.copy()
    h, w = out.shape[:2]
    if n <= 0 or h < TAM_CULTURA or w < TAM_CULTURA:
        return out
    rng = np.random.default_rng(semente + 1)
    ys = rng.integers(0, h - TAM_CULTURA + 1, n)
    xs = rng.integers(0, w - TAM_CULTURA + 1, n)
    d = np.arange(TAM_CULTURA)
    dy, dx = np.meshgrid(d, d, indexing="ij")
    out[ys[:, None] + dy.ravel(), xs[:, None] + dx.ravel()] = COR_CULTURA
    return out


def aptidao(mapa: np.ndarray, altura: int, largura: int, raio: int) -> np.ndarray:
    """Campo de aptidão em [0, 1]: altitude média e terreno plano, suavizado
    por média móvel (2·raio+1)². Custo ∝ altura·largura·(2·raio+1)²."""
    alt = _reamostrar(mapa, altura, largura)
    base = 1.0 - np.abs(alt - 0.5) * 2.0
    gy, gx = _gradiente(alt)
    decl = np.hypot(gx, gy)
    m = decl.max()
    plano = 1.0 - decl / m if m > 0 else np.ones_like(alt)
    bruto = base * plano
    if raio <= 0:
        return bruto
    k = 2 * raio + 1
    janelas = np.lib.stride_tricks.sliding_window_view(
        np.pad(bruto, raio, mode="edge"), (k, k)
    )
    return janelas.mean(axis=(-2, -1))


def colorir(campo: np.ndarray) -> np.ndarray:
    c = np.clip(campo, 0.0, 1.0)[..., None]
    ruim = np.array([200.0, 40.0, 40.0])
    bom = np.array([40.0, 200.0, 60.0])
    return (ruim * (1 - c) + bom * c).astype(np.uint8)


def sobrepor(img: np.ndarray, campo: np.ndarray, alfa: float = 0.5) -> np.ndarray:
    """MAP.mode = SUITABILITY: mistura o campo sobre a imagem existente."""
    if img.shape[:2] != campo.shape:
        raise ValueError(f"resoluções diferentes: {img.shape[:2]} vs {campo.shape}")
    return (img * (1 - alfa) + colorir(campo) * alfa).astype(np.uint8)


# --- Execução de um quadro -------------------------------------------------

@dataclass(frozen=True)
class Passo:
    nome: str
    superficie: str
    altura: int
    largura: int
    instancias: int = 0
    raio: int = 4
    sobrepor: bool = False

    def __post_init__(self) -> None:
        if self.nome not in PASSOS:
            raise ValueError(f"passo desconhecido: {self.nome}")
        if self.altura < 1 or self.largura < 1:
            raise ValueError("resolução inválida")


@dataclass(frozen=True)
class Execucao:
    nome: str
    superficie: str
    carga: int
    tempo_ms: float


@dataclass
class Quadro:
    imagens: dict[str, np.ndarray] = field(default_factory=dict)
    execucoes: list[Execucao] = field(default_factory=list)

    @property
    def ordem(self) -> list[tuple[str, str]]:
        return [(e.nome, e.superficie) for e in self.execucoes]

    @property
    def carga_total(self) -> int:
        return sum(e.carga for e in self.execucoes)

    @property
    def tempo_total_ms(self) -> float:
        return sum(e.tempo_ms for e in self.execucoes)


class Renderizador:
    """Executa os passos na ordem recebida. A ordem, a supressão e a injeção
    são decididas por quem monta a lista (HospedeiroAgroView, no Passo B2)."""

    def __init__(self, semente: int = 0, lado_mapa: int = 256) -> None:
        self.semente = semente
        self.mapa = mapa_altura(semente, lado_mapa)

    def quadro(self, passos: list[Passo]) -> Quadro:
        q = Quadro()
        for p in passos:
            t0 = perf_counter()
            carga = self._executar(p, q.imagens)
            dt = (perf_counter() - t0) * 1000.0
            q.execucoes.append(Execucao(p.nome, p.superficie, carga, dt))
        return q

    def _executar(self, p: Passo, imagens: dict[str, np.ndarray]) -> int:
        h, w = p.altura, p.largura
        if p.nome == "TerrainPass":
            imagens[p.superficie] = terreno(self.mapa, h, w)
            return h * w
        if p.nome == "CropInstancesPass":
            base = imagens.get(p.superficie)
            if base is None:
                base = np.zeros((h, w, 3), np.uint8)
            imagens[p.superficie] = culturas(base, p.instancias, self.semente)
            return max(p.instancias, 0) * TAM_CULTURA**2
        # SuitabilityPass
        campo = aptidao(self.mapa, h, w, p.raio)
        base = imagens.get(p.superficie)
        imagens[p.superficie] = (
            sobrepor(base, campo) if p.sobrepor and base is not None else colorir(campo)
        )
        k = 2 * max(p.raio, 0) + 1
        return h * w * k * k