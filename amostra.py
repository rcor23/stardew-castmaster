# -*- coding: utf-8 -*-
"""
Ferramenta de diagnóstico — grava uma amostra do minigame.

Captura a TELA INTEIRA por DURACAO segundos e salva os frames em amostras/.
Tela inteira (e não só a região calibrada) porque é assim que dá pra medir
o tamanho real da trilha do minigame e achar a região correta.

Nada é exibido na tela enquanto grava (sem efeito espelho, sem roubar foco).
Avisa por BIPE quando começa e quando termina — você está no jogo e não vê
este terminal.

Uso:
  python amostra.py
  -> aperte ENTER, volte pro jogo e fisgue um peixe.
"""
import shutil
import time
from pathlib import Path

import numpy as np
import mss

from imgio import imwrite_u

try:
    import winsound

    def bipe(freq, ms):
        winsound.Beep(freq, ms)
except Exception:  # não-Windows: ignora
    def bipe(freq, ms):
        pass


PASTA = Path(__file__).parent
SAIDA = PASTA / "amostras"
DURACAO = 60   # segundos gravando (ciclo completo: arremesso -> mordida -> minigame)
FPS = 5        # frames por segundo (tela inteira pesa mais)


def bipe_inicio():
    bipe(880, 150)      # "vai!"


def bipe_fim():
    for _ in range(3):  # três bipes graves = acabou
        bipe(440, 180)
        time.sleep(0.06)


def main():
    if SAIDA.exists():
        shutil.rmtree(SAIDA)
    SAIDA.mkdir()

    print("=" * 60)
    print(" AMOSTRA DO MINIGAME — TELA INTEIRA (diagnóstico)")
    print("=" * 60)
    print(f" Ao apertar ENTER você terá {DURACAO}s para gravar um CICLO COMPLETO:")
    print("   1. Jogue a vara (segure e solte o clique);")
    print("   2. Espere a mordida (o '!' aparecer);")
    print("   3. Fisgue e jogue o minigame normalmente;")
    print("   4. Se der tempo, repita mais uma vez.")
    print()
    print(" AVISOS SONOROS:")
    print("   1 bipe agudo  = começou a gravar (pode pescar)")
    print("   3 bipes graves = acabou (pode voltar aqui)")
    print("=" * 60)
    input(" ENTER para começar... ")
    print("\n Volte pro jogo! Gravando em 3 segundos...\n")
    time.sleep(3)
    bipe_inicio()

    n = 0
    intervalo = 1.0 / FPS
    fim = time.time() + DURACAO
    prox = 0.0
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        while time.time() < fim:
            agora = time.time()
            if agora >= prox:
                frame = np.array(sct.grab(monitor))[:, :, :3]
                if not imwrite_u(SAIDA / f"f{n:04d}.png", frame):
                    print("\n ERRO: falha ao salvar o frame.")
                    return
                n += 1
                prox = agora + intervalo
                print(f"  gravando... faltam {int(fim - agora):2d}s  |  frames: {n}", end="\r")
            time.sleep(0.005)

    bipe_fim()
    mb = sum(f.stat().st_size for f in SAIDA.glob("*.png")) / 1e6
    print(f"\n\n Pronto! {n} frames salvos ({mb:.0f} MB) em: {SAIDA}")
    print(" Pode fechar esta janela e avisar o Claude.")


if __name__ == "__main__":
    main()
