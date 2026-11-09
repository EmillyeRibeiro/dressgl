import subprocess
import sys

CODIGO = """
import importlib, pkgutil, sys
import dressgl
for m in pkgutil.walk_packages(dressgl.__path__, "dressgl."):
    if not m.name.endswith("__main__"):
        importlib.import_module(m.name)
print(",".join(sorted({"numpy", "PySide6", "agroview"} & set(sys.modules))))
"""


def test_nucleo_nao_importa_numpy_pyside_nem_agroview():
    saida = subprocess.run(
        [sys.executable, "-c", CODIGO], capture_output=True, text=True, check=True
    )
    assert saida.stdout.strip() == ""