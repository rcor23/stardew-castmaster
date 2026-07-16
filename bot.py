# -*- coding: utf-8 -*-
"""
ETAPA 3 — O bot de verdade (controla o mouse!).

Versão 1: VOCÊ joga a vara e fisga o peixe; quando o minigame abrir,
o bot assume e joga a barra verde sozinho até o fim.

Lógica: se o peixe está ACIMA do centro da barra -> segura o clique (barra sobe);
        se está ABAIXO -> solta (barra desce). Com uma pequena zona morta
        para não ficar tremendo.

Segurança (kill switches):
  - Aperte Q na janela "bot" para encerrar.
  - Jogue o mouse num canto da tela: o pyautogui aborta tudo (failsafe).

Antes de rodar este, confirme que deteccao.py está detectando bem!
"""
import json
import time
import cv2
import numpy as np
import mss
import pyautogui
import pydirectinput

from deteccao import detectar

pyautogui.FAILSAFE = True  # mouse no canto da tela = aborta

ZONA_MORTA = 6  # pixels de tolerância em volta do centro da barra


def main():
    with open("config.json") as f:
        região = json.load(f)
    template = cv2.imread("peixe.png", cv2.IMREAD_GRAYSCALE)
    if template is None:
        print("peixe.png não encontrado — rode calibrar.py primeiro.")
        return

    print("Bot rodando. Jogue a vara e fisgue — eu cuido do minigame.")
    print("Q na janela 'bot' encerra | mouse no canto da tela aborta.")

    segurando = False
    capturas = 0
    minigame_ativo = False

    try:
        with mss.mss() as sct:
            while True:
                frame = np.array(sct.grab(região))[:, :, :3].copy()
                barra_y, barra_rect, peixe_y, peixe_rect = detectar(frame, template)

                ativo = barra_y is not None and peixe_y is not None

                if ativo:
                    if not minigame_ativo:
                        minigame_ativo = True
                        print("Minigame detectado — assumindo o controle!")
                    # peixe acima do centro da barra -> precisa subir -> segurar
                    if peixe_y < barra_y - ZONA_MORTA and not segurando:
                        pydirectinput.mouseDown()
                        segurando = True
                    elif peixe_y > barra_y + ZONA_MORTA and segurando:
                        pydirectinput.mouseUp()
                        segurando = False
                else:
                    if minigame_ativo:
                        minigame_ativo = False
                        capturas += 1
                        print(f"Minigame encerrado (tentativa #{capturas}).")
                    if segurando:
                        pydirectinput.mouseUp()
                        segurando = False

                # janela de debug
                if barra_rect:
                    bx, by, bw, bh = barra_rect
                    cv2.rectangle(frame, (bx, by), (bx + bw, by + bh), (0, 255, 0), 2)
                if peixe_rect:
                    px, py, pw, ph = peixe_rect
                    cv2.rectangle(frame, (px, py), (px + pw, py + ph), (0, 0, 255), 2)
                estado = "SEGURANDO" if segurando else ("ativo" if ativo else "esperando...")
                cv2.putText(frame, estado, (5, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
                cv2.imshow("bot", frame)

                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
    finally:
        if segurando:
            pydirectinput.mouseUp()
        cv2.destroyAllWindows()
        print(f"Encerrado. Minigames jogados: {capturas}")


if __name__ == "__main__":
    main()
