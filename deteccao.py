# -*- coding: utf-8 -*-
"""
Detecção da barra e do peixe — por COR (HSV).

Por que por cor e não por template matching:
  medimos os pixels reais do minigame (ver amostra.py) e descobrimos que a
  barra do jogador e o peixe ocupam faixas de matiz BEM separadas:

      barra do jogador : hue 40-70   (verde-amarelado, bem saturado)
      peixe            : hue 80-100  (ciano, muito saturado)
      água da trilha   : hue 110-125 (azul)
      alga do fundo    : verde escuro (barrada pelo brilho mínimo)

  Medido em 20 frames reais de minigame: peixe 100%, barra 95%.

  O template matching foi abandonado porque o recorte do peixe levava junto
  o fundo verde da barra, e aí a confiança despencava justo quando o peixe
  saía da barra — que é quando o bot mais precisa enxergar.

Teste visual (não clica em nada):
  python deteccao.py
"""
import json
import time
from pathlib import Path

import cv2
import numpy as np
import mss

PASTA = Path(__file__).parent

# --- barra verde do jogador ---
BARRA_MIN = np.array([40, 100, 150])
BARRA_MAX = np.array([70, 255, 255])
AREA_MIN_BARRA = 300     # px; abaixo disso não é a barra (é alga/ruído)
LARGURA_MIN_BARRA = 20   # a barra ocupa quase toda a largura da trilha

# --- peixe (ciano) ---
PEIXE_MIN = np.array([80, 120, 120])
PEIXE_MAX = np.array([100, 255, 255])
AREA_MIN_PEIXE = 40

# --- "!" da mordida (amarelo, acima da cabeça do personagem) ---
# Cuidado: a BARRA DE FORÇA do arremesso também é amarela e aparece na mesma
# área. Medido nos frames reais, as duas se separam pela forma:
#     barra de força : ~50 x 25 px  -> proporção altura/largura ~0.5
#     "!" da mordida :   5 x 20 px  -> proporção altura/largura ~4.0
MORDIDA_MIN = np.array([20, 150, 180])
MORDIDA_MAX = np.array([35, 255, 255])
AREA_MIN_MORDIDA = 40        # menos que isso é ruído
LARGURA_MAX_MORDIDA = 15     # mais largo que isso é a barra de força (~50px)
PROPORCAO_MIN_MORDIDA = 2.0  # "!" tem h/w ~4.0; a barra de força ~0.5


def detectar_mordida(frame):
    """True se o "!" da mordida está na tela (e não a barra de força)."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, MORDIDA_MIN, MORDIDA_MAX)
    contornos, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in contornos:
        x, y, w, h = cv2.boundingRect(c)
        if w == 0 or w > LARGURA_MAX_MORDIDA:
            continue
        if h / w < PROPORCAO_MIN_MORDIDA:
            continue
        if cv2.contourArea(c) < AREA_MIN_MORDIDA:
            continue
        return True
    return False


def _maior_blob(mask, area_min):
    """Devolve (x, y, w, h) do maior contorno acima de area_min, ou None."""
    contornos, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contornos = [c for c in contornos if cv2.contourArea(c) >= area_min]
    if not contornos:
        return None
    return cv2.boundingRect(max(contornos, key=cv2.contourArea))


def detectar(frame):
    """Acha a barra e o peixe no recorte da trilha.

    Retorna (barra_y, barra_rect, peixe_y, peixe_rect); cada um é None se
    não foi encontrado. Os *_y são o centro vertical, em px do recorte.
    """
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    barra_y = barra_rect = None
    r = _maior_blob(cv2.inRange(hsv, BARRA_MIN, BARRA_MAX), AREA_MIN_BARRA)
    if r is not None and r[2] >= LARGURA_MIN_BARRA:
        x, y, w, h = r
        barra_y = y + h // 2
        barra_rect = r

    peixe_y = peixe_rect = None
    r = _maior_blob(cv2.inRange(hsv, PEIXE_MIN, PEIXE_MAX), AREA_MIN_PEIXE)
    if r is not None:
        x, y, w, h = r
        peixe_y = y + h // 2
        peixe_rect = r

    return barra_y, barra_rect, peixe_y, peixe_rect


def main():
    with open(PASTA / "config.json") as f:
        região = json.load(f)

    print("Teste de detecção (não clica em nada). Q na janela para sair.")
    with mss.mss() as sct:
        t0, frames, fps = time.time(), 0, 0
        while True:
            frame = np.array(sct.grab(região))[:, :, :3].copy()
            barra_y, barra_rect, peixe_y, peixe_rect = detectar(frame)

            if barra_rect:
                x, y, w, h = barra_rect
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            if peixe_rect:
                x, y, w, h = peixe_rect
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 255), 2)

            frames += 1
            if time.time() - t0 >= 1.0:
                fps, frames, t0 = frames, 0, time.time()
            txt = f"{fps}fps b:{'OK' if barra_y else '--'} p:{'OK' if peixe_y else '--'}"
            cv2.putText(frame, txt, (3, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 0), 1)

            cv2.imshow("deteccao", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
