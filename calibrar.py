# -*- coding: utf-8 -*-
"""
ETAPA 1 — Calibração.

Descobre onde a barra de pesca fica na SUA tela e salva:
  - config.json  -> coordenadas da região do minigame
  - peixe.png    -> template (recorte) do ícone do peixe

Como usar:
  1. Abra o Stardew Valley em MODO JANELA (zoom e escala de UI em 100%).
  2. Rode: python calibrar.py
  3. Vai abrir uma janela com a visão da sua tela ao vivo.
  4. No jogo, jogue a vara e fisgue um peixe (o minigame precisa estar na tela).
  5. Com o minigame visível, clique na janela de preview e aperte ESPAÇO para congelar.
  6. Desenhe um retângulo em volta da BARRA INTEIRA do minigame (a régua
     vertical onde o peixe e a barra verde se movem) e aperte ENTER.
  7. Vai abrir um zoom dessa região: desenhe um retângulo apertado em volta
     do ÍCONE DO PEIXE e aperte ENTER.
"""
import json
import cv2
import numpy as np
import mss

ZOOM = 2  # ampliação na hora de recortar o peixe


def main():
    with mss.mss() as sct:
        monitor = sct.monitors[1]  # monitor principal

        print("Preview ao vivo. Deixe o minigame de pesca visível e aperte ESPAÇO para congelar. (Q sai)")
        frozen = None
        cv2.namedWindow("preview", cv2.WINDOW_NORMAL)
        while True:
            frame = np.array(sct.grab(monitor))[:, :, :3]
            cv2.imshow("preview", frame)
            key = cv2.waitKey(16) & 0xFF
            if key == ord(" "):
                frozen = frame.copy()
                break
            if key == ord("q"):
                print("Cancelado.")
                return
        cv2.destroyAllWindows()

        print("Selecione a REGIÃO DA BARRA do minigame e aperte ENTER.")
        x, y, w, h = map(int, cv2.selectROI("selecione a barra", frozen, showCrosshair=True))
        cv2.destroyAllWindows()
        if w == 0 or h == 0:
            print("Nenhuma região selecionada. Cancelado.")
            return

        região = frozen[y : y + h, x : x + w]
        ampliada = cv2.resize(região, None, fx=ZOOM, fy=ZOOM, interpolation=cv2.INTER_NEAREST)

        print("Agora selecione só o ÍCONE DO PEIXE e aperte ENTER.")
        fx, fy, fw, fh = map(int, cv2.selectROI("selecione o peixe", ampliada, showCrosshair=True))
        cv2.destroyAllWindows()
        if fw == 0 or fh == 0:
            print("Nenhum peixe selecionado. Cancelado.")
            return

        peixe = região[fy // ZOOM : (fy + fh) // ZOOM, fx // ZOOM : (fx + fw) // ZOOM]
        cv2.imwrite("peixe.png", peixe)

        config = {
            "left": monitor["left"] + x,
            "top": monitor["top"] + y,
            "width": w,
            "height": h,
        }
        with open("config.json", "w") as f:
            json.dump(config, f, indent=2)

        print(f"OK! Região salva em config.json: {config}")
        print(f"Template do peixe salvo em peixe.png ({peixe.shape[1]}x{peixe.shape[0]} px)")
        print("Próximo passo: python deteccao.py")


if __name__ == "__main__":
    main()
