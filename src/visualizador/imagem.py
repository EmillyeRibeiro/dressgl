"""Conversão de buffers NumPy para o PhotoImage do Tk, sem Pillow (D61)."""
import numpy as np


def ampliar(arr: np.ndarray, k: int) -> np.ndarray:
    """Ampliação por vizinho mais próximo: mantém os pixels nítidos na projeção."""
    return arr if k == 1 else arr.repeat(k, axis=0).repeat(k, axis=1)


def para_ppm(arr: np.ndarray) -> bytes:
    """Converte H×W×3 (ou H×W) uint8 em PPM binário (P6)."""
    if arr.ndim == 2:
        arr = np.stack([arr] * 3, axis=-1)
    if arr.dtype != np.uint8:
        # ADAPTAR: confirmar a convenção do render (float em [0, 1]?)
        arr = np.clip(arr * 255.0, 0, 255).astype(np.uint8)
    h, w, _ = arr.shape
    return b"P6 %d %d 255\n" % (w, h) + np.ascontiguousarray(arr).tobytes()