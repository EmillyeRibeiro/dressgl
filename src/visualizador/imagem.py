"""Conversão de buffers NumPy para o PhotoImage do Tk, sem Pillow (D61)."""
import numpy as np


def ampliar(arr: np.ndarray, k: int) -> np.ndarray:
    """Ampliação inteira por vizinho mais próximo."""
    return arr if k == 1 else arr.repeat(k, axis=0).repeat(k, axis=1)


def ajustar(arr: np.ndarray, altura: int, largura: int) -> np.ndarray:
    """Vizinho mais próximo até o tamanho de exibição. Uma superfície reduzida por
    SCALE resolution aparece pixelizada, sem mudar o tamanho na janela."""
    h, w = arr.shape[:2]
    if (h, w) == (altura, largura):
        return arr
    iy = np.arange(altura) * h // altura
    ix = np.arange(largura) * w // largura
    return arr[iy[:, None], ix[None, :]]


def para_ppm(arr: np.ndarray) -> bytes:
    """Converte H×W×3 (ou H×W) uint8 em PPM binário (P6).
    O render do agroview sempre produz uint8 (render.py). O ramo float, em [0, 1],
    é só por conveniência."""
    if arr.ndim == 2:
        arr = np.stack([arr] * 3, axis=-1)
    if arr.dtype != np.uint8:
        arr = np.clip(arr * 255.0, 0, 255).astype(np.uint8)
    h, w, _ = arr.shape
    return b"P6 %d %d 255\n" % (w, h) + np.ascontiguousarray(arr).tobytes()