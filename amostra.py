# -*- coding: utf-8 -*-
"""
Ferramenta de diagnóstico — grava uma amostra do minigame.

Captura a região calibrada (config.json) por DURACAO segundos e salva os
frames em amostras/. Serve pra analisar as cores REAIS da barra e do peixe
em vez de chutar valores de HSV.

Nada é exibido na tela enquanto grava (sem efeito espelho, sem roubar foco).

Uso:
  python amostra.py
  -> aperte ENTER, volte pro jogo e fisgue um peixe.
"""
import json
import shutil
import time
from pathlib import Path

import cv2
import numpy as np
import mss

from imgio import imwrite_u

PASTA = Path(__file__).parent
SAIDA = PASTA / "amostras"
DURACAO = 25   # segundos gravando
FPS = 10       # frames por segundo


def main():
    with open(PASTA / "config.json") as f:
        região = json.load(f)

    if SAIDA.exists():
        shutil.rmtree(SAIDA)
    SAIDA.mkdir()

    print("=" * 60)
    print(" AMOSTRA DO MINIGAME (diagnóstico)")
    print("=" * 60)
    print(f" Região calibrada: {região}")
    print(f" Ao apertar ENTER você terá {DURACAO}s para voltar ao jogo,")
    print(" jogar a vara e fisgar. Não precisa clicar em nada.")
    print("=" * 60)
    input(" ENTER para começar... ")
    print("\n Vai! Fisga um peixe!\n")
    time.sleep(1.5)

    n = 0
    intervalo = 1.0 / FPS
    fim = time.time() + DURACAO
    prox = 0.0
    with mss.mss() as sct:
        while time.time() < fim:
            agora = time.time()
            if agora >= prox:
                frame = np.array(sct.grab(região))[:, :, :3]
                if not imwrite_u(SAIDA / f"f{n:04d}.png", frame):
                    print("\n ERRO: falha ao salvar o frame.")
                    return
                n += 1
                prox = agora + intervalo
                print(f"  gravando... faltam {int(fim - agora):2d}s  |  frames: {n}", end="\r")
            time.sleep(0.005)

    print(f"\n\n Pronto! {n} frames salvos em: {SAIDA}")
    print(" Pode fechar esta janela e avisar o Claude.")


if __name__ == "__main__":
    main()
