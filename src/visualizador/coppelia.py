"""Reprodução 3D de uma gravação no CoppeliaSim (complemento da janela B1).

Usa a mesma fábrica de quadros da Janela Tk. As coordenadas já estão em
metros de -2,5 a 2,5 com y para cima, iguais às do Floor padrão do CoppeliaSim.
Rodar com a simulação PARADA no CoppeliaSim.
"""
from __future__ import annotations

import json
import math
import tempfile
import time
from pathlib import Path

from coppeliasim_zmqremoteapi_client import RemoteAPIClient

ALTURA_PADRAO = 0.5          # m, usada se pos_real não tiver z
ALTURA_CAMERA = 9.0          # m, --vista-topo na vista principal (tela larga)
ALTURA_CAMERA_JANELA = 8.0   # m, topo na meia tela (um pouco mais alta que larga)
ALTURA_SOMBRA = 0.02         # m, logo acima das placas das zonas
ORIENTACAO_TOPO = [0.0, math.pi, 0.0]   # conferida: +x à direita, +y para cima
LADO_ORTO = 6.4              # m no lado MAIOR da vista ortográfica (campo de 5 m + folga)

NOME_CAM_TOPO = "DressGL_CamTopo"
ESTADO = Path(tempfile.gettempdir()) / "dressgl_coppelia.json"

# Janelas flutuantes lado a lado cobrindo a vista principal inteira.
# (centro x, centro y, largura, altura), frações da vista principal, origem embaixo à esquerda.
JANELA_3D = (0.25, 0.5, 0.5, 1.0)
JANELA_TOPO = (0.75, 0.5, 0.5, 1.0)
# Câmera 3D: alvo, distância, azimute (de onde ela olha) e elevação, em graus
PANORAMA = dict(alvo=(0.9, 0.0, 0.3), dist=4.0, azimute=-100.0, elevacao=50.0)
SEGUIR = dict(dist=4.0, azimute=-100.0, elevacao=30.0)
SUAVIZACAO = 0.15            # 0..1; menor = câmera mais "preguiçosa" ao seguir

CORES_SOLO = {"BARE_SOIL": [0.79, 0.65, 0.47],
              "STANDING_CROP": [0.42, 0.66, 0.31],
              "WATER": [0.24, 0.52, 0.78]}


# ---------------------------------------------------------------- estado em disco
def _ler_estado() -> dict:
    try:
        return json.loads(ESTADO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _gravar_estado(estado: dict):
    ESTADO.write_text(json.dumps(estado), encoding="utf-8")


# ---------------------------------------------------------------- geometria
def _olhar_para(olho, alvo):
    """Matriz 3x4 de uma câmera em `olho` olhando para `alvo`, com o céu para cima.
    A câmera olha ao longo do próprio +z, com +y para cima na tela e x = y × z."""
    z = [a - o for a, o in zip(alvo, olho)]
    n = math.sqrt(sum(c * c for c in z))
    z = [c / n for c in z]
    x = [-z[1], z[0], 0.0]                       # (0, 0, 1) × z
    n = math.hypot(x[0], x[1]) or 1.0
    x = [c / n for c in x]
    y = [z[1] * x[2] - z[2] * x[1], z[2] * x[0] - z[0] * x[2], z[0] * x[1] - z[1] * x[0]]
    return [x[0], y[0], z[0], olho[0],
            x[1], y[1], z[1], olho[1],
            x[2], y[2], z[2], olho[2]]


def _orbita(alvo, dist, azimute, elevacao):
    az, el = math.radians(azimute), math.radians(elevacao)
    olho = [alvo[0] + dist * math.cos(el) * math.cos(az),
            alvo[1] + dist * math.cos(el) * math.sin(az),
            alvo[2] + dist * math.sin(el)]
    return _olhar_para(olho, alvo)


# ---------------------------------------------------------------- cena
def montar_campo(sim, zonas):
    """Cria uma placa fina por zona do TOML (a zona posterior fica por cima)."""
    for i, z in enumerate(zonas):
        nome = f"Zona{i}_{z['solo']}"
        antigo = sim.getObject(f"/{nome}", {"noError": True})
        if antigo != -1:
            sim.removeObjects([antigo])
        (x0, x1), (y0, y1) = z["x"], z["y"]
        h = sim.createPrimitiveShape(sim.primitiveshape_cuboid,
                                     [x1 - x0, y1 - y0, 0.002], 0)
        sim.setObjectAlias(h, nome)
        sim.setObjectPosition(h, [(x0 + x1) / 2, (y0 + y1) / 2, 0.001 + 0.002 * i],
                              sim.handle_world)
        sim.setShapeColor(h, None, sim.colorcomponent_ambient_diffuse,
                          CORES_SOLO.get(z["solo"], [0.6, 0.6, 0.6]))
        sim.setObjectInt32Param(h, sim.shapeintparam_static, 1)
        sim.setObjectInt32Param(h, sim.shapeintparam_respondable, 0)


def _ortografica(sim, cam, ligar: bool):
    try:
        sim.setObjectInt32Param(cam, sim.cameraintparam_perspective_operation,
                                0 if ligar else 1)
        if ligar:
            sim.setObjectFloatParam(cam, sim.camerafloatparam_ortho_size, LADO_ORTO)
    except Exception as e:
        if ligar:
            print(f"aviso: não consegui ativar a projeção ortográfica ({e}); "
                  "seguindo em perspectiva")


def _limpar_restos(sim, estado: dict):
    """Remove rastros, janelas flutuantes e câmera de topo de execuções anteriores."""
    try:
        sim.removeDrawingObject(sim.handle_all)
    except Exception:
        pass
    janelas = list(estado.pop("janelas", []))
    if "janela" in estado:                      # formato da versão anterior
        janelas.append(estado.pop("janela"))
    for j in janelas:
        try:
            sim.floatingViewRemove(j)
        except Exception:                       # já fechada à mão pelo X
            pass
    h = sim.getObject("/" + NOME_CAM_TOPO, {"noError": True})
    if h != -1:
        sim.removeObjects([h])


def _restaurar_poses(sim, cam, drone, estado: dict):
    if "pose_camera" in estado:
        sim.setObjectPose(cam, estado["pose_camera"], sim.handle_world)
    _ortografica(sim, cam, False)
    if "pos_drone" in estado:
        sim.setObjectPosition(drone, estado["pos_drone"], sim.handle_world)


def _criar_cam_topo(sim, cam, altura, ortografica):
    h = sim.copyPasteObjects([cam], 0)[0]
    sim.setObjectAlias(h, NOME_CAM_TOPO)
    sim.setObjectParent(h, -1, True)
    sim.setObjectPosition(h, [0.0, 0.0, altura], sim.handle_world)
    sim.setObjectOrientation(h, ORIENTACAO_TOPO, sim.handle_world)
    _ortografica(sim, h, ortografica)
    return h


def _janela(sim, geometria, camera, rotulo):
    j = sim.floatingViewAdd(*geometria, 0)
    sim.adjustView(j, camera, 0, rotulo)
    return j


def _conectar():
    sim = RemoteAPIClient().require("sim")
    if sim.getSimulationState() != sim.simulation_stopped:
        raise SystemExit("Pare a simulação no CoppeliaSim antes do replay.")
    return sim


def restaurar_cena():
    """Apaga tudo o que o replay criou e devolve câmera e drone às poses originais."""
    sim = _conectar()
    estado = _ler_estado()
    _limpar_restos(sim, estado)
    _restaurar_poses(sim, sim.getObject("/DefaultCamera"), sim.getObject("/Quadcopter"),
                     estado)
    ESTADO.unlink(missing_ok=True)
    print("Cena restaurada.")


# ---------------------------------------------------------------- replay
def reproduzir(fabrica_fonte, zonas=(), fps: float = 30.0, vista_topo: bool = False,
               manter_rastro: bool = False, altura_camera: float | None = None,
               duas_vistas: bool = False, seguir_drone: bool = False,
               ortografica: bool = False):
    sim = _conectar()
    estado = _ler_estado()
    _limpar_restos(sim, estado)
    montar_campo(sim, list(zonas))

    drone = sim.getObject("/Quadcopter")
    cam = sim.getObject("/DefaultCamera")
    # guarda as poses ORIGINAIS só na primeira vez (sobrevive a --manter-rastro)
    estado.setdefault("pose_camera", sim.getObjectPose(cam, sim.handle_world))
    estado.setdefault("pos_drone", sim.getObjectPosition(drone, sim.handle_world))

    if vista_topo:
        sim.setObjectPosition(cam, [0.0, 0.0, altura_camera or ALTURA_CAMERA],
                              sim.handle_world)
        sim.setObjectOrientation(cam, ORIENTACAO_TOPO, sim.handle_world)
        if ortografica:
            _ortografica(sim, cam, True)
    elif duas_vistas:
        if not seguir_drone:
            sim.setObjectMatrix(cam, _orbita(**PANORAMA), sim.handle_world)
        cam_topo = _criar_cam_topo(sim, cam, altura_camera or ALTURA_CAMERA_JANELA,
                                   ortografica)
        # 3D à esquerda (DefaultCamera), topo à direita: lado a lado, sem sobrepor
        estado["janelas"] = [_janela(sim, JANELA_3D, cam, "3D"),
                             _janela(sim, JANELA_TOPO, cam_topo, "Topo")]
    _gravar_estado(estado)

    # rastro preto = nenhuma regra ativa; vermelho = alguma regra da DSL ativa
    nominal = sim.addDrawingObject(sim.drawing_lines, 3, 0, -1, 100000, [0, 0, 0])
    ativo = sim.addDrawingObject(sim.drawing_lines, 4, 0, -1, 100000, [0.9, 0.1, 0.1])
    # sombra no chão = projeção (x, y), a mesma linha preta do painel Campo da janela Tk
    sombra = sim.addDrawingObject(sim.drawing_lines, 2, 0, -1, 100000, [0.2, 0.2, 0.2])

    anterior = None
    alvo = None                       # alvo suavizado da câmera que segue o drone
    try:
        for q in fabrica_fonte():
            t = time.perf_counter()
            if q.pos_real is None:
                continue
            pos = [float(v) for v in q.pos_real]
            p = [pos[0], pos[1], pos[2] if len(pos) > 2 else ALTURA_PADRAO]
            sim.setObjectPosition(drone, p, sim.handle_world)
            if anterior:
                sim.addDrawingObjectItem(ativo if q.ativas else nominal, anterior + p)
                sim.addDrawingObjectItem(sombra, [anterior[0], anterior[1], ALTURA_SOMBRA,
                                                  p[0], p[1], ALTURA_SOMBRA])
            if seguir_drone:
                alvo = p[:] if alvo is None else [a + SUAVIZACAO * (b - a)
                                                  for a, b in zip(alvo, p)]
                sim.setObjectMatrix(cam, _orbita(alvo, **SEGUIR), sim.handle_world)
            anterior = p
            print(f"\rquadro {q.indice:4d}  ativas: "
                  f"{', '.join(q.ativas) or 'nenhuma':30s}", end="", flush=True)
            espera = 1 / fps - (time.perf_counter() - t)
            if espera > 0:
                time.sleep(espera)
    except KeyboardInterrupt:
        print("\ninterrompido")
    finally:
        print()
        if manter_rastro:
            print("Rastro e vistas mantidos. Para limpar tudo:\n"
                  "  python -m visualizador --coppelia --restaurar-cena\n"
                  "Não salve a cena antes disso.")
        else:
            input("Enter para limpar o rastro e restaurar drone e câmera...")
            _limpar_restos(sim, estado)
            _restaurar_poses(sim, cam, drone, estado)
            ESTADO.unlink(missing_ok=True)