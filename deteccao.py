# -*- coding: utf-8 -*-
"""
ETAPA 2 — Teste de detecção (NÃO clica em nada!).

Mostra em tempo real o que o bot está "enxergando":
  - retângulo VERDE  = barra verde do jogador
  - retângulo VERMELHO = peixe encontrado por template matching
  - FPS e status no topo

Como testar:
  1. Rode: python deteccao.py
  2. Vá pescar manualmente no jogo.
  3. Observe a janela "deteccao": os dois retângulos devem seguir a barra
     e o peixe o minigame INTEIRO, sem piscar nem pular.
  Se a detecção estiver ruim, ajuste LIMIAR_PEIXE ou refaça a calibração.

Aperte Q na janela para sair.
"""
import json
import time
import cv2
import numpy as np
import mss

# faixa de verde (HSV) da barra do jogador
VERDE_MIN = np.array([35, 80, 80])
VERDE_MAX = np.array([85, 255, 255])

# confiança mínima do template matching do peixe (0 a 1)
LIMIAR_PEIXE = 0.55

# quantos pixels verdes indicam que o minigame está aberto
MIN_PIXELS_VERDES = 200


def detectar(frame, template, limiar=None):
    """Retorna (barra_y, barra_rect, peixe_y, peixe_rect) — None quando não achou."""
    if limiar is None:
        limiar = LIMIAR_PEIXE
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, VERDE_MIN, VERDE_MAX)

    barra_y = barra_rect = None
    if cv2.countNonZero(mask) >= MIN_PIXELS_VERDES:
        contornos, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        maior = max(contornos, key=cv2.contourArea)
        bx, by, bw, bh = cv2.boundingRect(maior)
        barra_y = by + bh // 2
        barra_rect = (bx, by, bw, bh)

    cinza = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    res = cv2.matchTemplate(cinza, template, cv2.TM_CCOEFF_NORMED)
    _, conf, _, loc = cv2.minMaxLoc(res)

    peixe_y = peixe_rect = None
    if conf >= limiar:
        th, tw = template.shape[:2]
        peixe_y = loc[1] + th // 2
        peixe_rect = (loc[0], loc[1], tw, th)

    return barra_y, barra_rect, peixe_y, peixe_rect


def main():
    with open("config.json") as f:
        região = json.load(f)
    template = cv2.imread("peixe.png", cv2.IMREAD_GRAYSCALE)
    if template is None:
        print("peixe.png não encontrado — rode calibrar.py primeiro.")
        return

    with mss.mss() as sct:
        t0, frames, fps = time.time(), 0, 0.0
        while True:
            frame = np.array(sct.grab(região))[:, :, :3].copy()
            barra_y, barra_rect, peixe_y, peixe_rect = detectar(frame, template)

            if barra_rect:
                bx, by, bw, bh = barra_rect
                cv2.rectangle(frame, (bx, by), (bx + bw, by + bh), (0, 255, 0), 2)
            if peixe_rect:
                px, py, pw, ph = peixe_rect
                cv2.rectangle(frame, (px, py), (px + pw, py + ph), (0, 0, 255), 2)

            frames += 1
            if time.time() - t0 >= 1.0:
                fps, frames, t0 = frames, 0, time.time()
            status = f"{fps} fps | barra: {'OK' if barra_y is not None else '--'} | peixe: {'OK' if peixe_y is not None else '--'}"
            cv2.putText(frame, status, (5, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)

            cv2.imshow("deteccao", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
