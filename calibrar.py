# -*- coding: utf-8 -*-
"""
ETAPA 1 — Calibração (v2).

Descobre onde a barra de pesca fica na SUA tela e salva:
  - config.json  -> coordenadas da região do minigame

Só isso: a detecção da barra e do peixe é por COR (ver deteccao.py), então
não existe mais template pra recortar.

COMO FUNCIONA (v2):
  Nada é mostrado na tela enquanto captura — isso evita o "efeito espelho"
  (janela mostrando a tela que contém a própria janela) e não rouba o foco
  do jogo enquanto você pesca.

  1. Você aperta ENTER aqui no terminal;
  2. Tem DURACAO segundos pra voltar ao jogo, jogar a vara e fisgar;
  3. O script tira vários prints silenciosos nesse tempo;
  4. Só DEPOIS abre uma janelinha pra você escolher o print que pegou
     o minigame e marcar a trilha.

Como usar:
  1. Abra o Stardew Valley em MODO JANELA (zoom e escala de UI em 100%).
  2. Rode: python calibrar.py
  3. Siga as instruções do terminal.
"""
import json
import time
from pathlib import Path

import cv2
import numpy as np
import mss


try:
    import winsound

    def bipe(freq, ms):
        winsound.Beep(freq, ms)
except Exception:  # não-Windows: ignora
    def bipe(freq, ms):
        pass


PASTA = Path(__file__).parent

DURACAO = 25       # segundos capturando (tempo pra você fisgar)
FPS = 2            # prints por segundo
MAX_W, MAX_H = 1500, 800   # p/ a janela de seleção caber na tela


def capturar_frames(sct, monitor):
    """Tira prints silenciosos por DURACAO segundos. Nada aparece na tela.

    Os prints são guardados em PNG na memória (sem perda). Em monitor
    ultrawide um print cru pesa ~8 MB; em PNG cai pra menos de 1 MB.
    """
    frames = []
    intervalo = 1.0 / FPS
    fim = time.time() + DURACAO
    prox = 0.0
    while time.time() < fim:
        agora = time.time()
        if agora >= prox:
            bruto = np.array(sct.grab(monitor))[:, :, :3]
            ok, buf = cv2.imencode(".png", bruto)
            if ok:
                frames.append(buf)
            prox = agora + intervalo
            print(f"  capturando... faltam {int(fim - agora):2d}s  |  prints: {len(frames)}", end="\r")
        time.sleep(0.02)
    mb = sum(f.nbytes for f in frames) / 1e6
    print(f"\n  {len(frames)} prints capturados ({mb:.0f} MB).\n")
    return frames


def decodificar(buf):
    return cv2.imdecode(buf, cv2.IMREAD_COLOR)


def _encaixar(img):
    """Escala p/ caber na tela. Devolve (imagem_escalada, fator)."""
    f = min(1.0, MAX_W / img.shape[1], MAX_H / img.shape[0])
    if f < 1.0:
        return cv2.resize(img, None, fx=f, fy=f, interpolation=cv2.INTER_AREA), f
    return img.copy(), 1.0


def escolher_frame(frames):
    """Deixa você navegar pelos prints e escolher o que pegou o minigame."""
    i = 0
    cv2.namedWindow("escolha o print", cv2.WINDOW_AUTOSIZE)
    while True:
        vis, _ = _encaixar(decodificar(frames[i]))
        cv2.rectangle(vis, (0, 0), (vis.shape[1], 28), (0, 0, 0), -1)
        txt = f"print {i+1}/{len(frames)}  |  A e D = navegar  |  ENTER = usar este  |  Q = cancelar"
        cv2.putText(vis, txt, (8, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 1)
        cv2.imshow("escolha o print", vis)

        k = cv2.waitKey(0) & 0xFF
        if k == ord("d"):
            i = min(i + 1, len(frames) - 1)
        elif k == ord("a"):
            i = max(i - 1, 0)
        elif k in (13, 10):  # ENTER
            cv2.destroyAllWindows()
            return decodificar(frames[i])
        elif k == ord("q"):
            cv2.destroyAllWindows()
            return None


def selecionar(img, titulo):
    """selectROI numa versão escalada, devolvendo coords no tamanho original."""
    vis, f = _encaixar(img)
    r = cv2.selectROI(titulo, vis, showCrosshair=True)
    cv2.destroyAllWindows()
    x, y, w, h = (int(round(v / f)) for v in r)
    return x, y, w, h


def main():
    with mss.mss() as sct:
        monitor = sct.monitors[1]  # monitor principal

        print("=" * 62)
        print(" CALIBRAÇÃO DO STARDEW CASTMASTER")
        print("=" * 62)
        print(f" Ao apertar ENTER, você terá {DURACAO} segundos para:")
        print("   1. Voltar para a janela do jogo (alt+tab);")
        print("   2. Jogar a vara e fisgar um peixe;")
        print("   3. Deixar o minigame na tela.")
        print(" Não precisa clicar em nada — eu tiro os prints sozinho.")
        print()
        print(" AVISOS SONOROS:")
        print("   1 bipe agudo   = começou a capturar (pode pescar)")
        print("   3 bipes graves = acabou (volte aqui para escolher o print)")
        print("=" * 62)
        input(" Aperte ENTER para começar a contagem... ")

        print("\n Volte pro jogo! Capturando em 3 segundos...\n")
        time.sleep(3)
        bipe(880, 150)  # 1 bipe agudo = começou
        frames = capturar_frames(sct, monitor)
        for _ in range(3):  # 3 bipes graves = acabou
            bipe(440, 180)
            time.sleep(0.06)

        if not frames:
            print("Nenhum print capturado. Cancelado.")
            return

        print(" Agora escolha o print em que o minigame aparece (A/D para navegar, ENTER para usar).")
        frame = escolher_frame(frames)
        if frame is None:
            print("Cancelado.")
            return

        print(" Marque a TRILHA INTEIRA do minigame (de cima até embaixo!) e aperte ENTER.")
        print(" ATENÇÃO: a trilha é bem mais alta do que parece — pegue tudo.")
        x, y, w, h = selecionar(frame, "marque a TRILHA INTEIRA do minigame")
        if w == 0 or h == 0:
            print("Nenhuma região selecionada. Cancelado.")
            return

        config = {
            "left": monitor["left"] + x,
            "top": monitor["top"] + y,
            "width": w,
            "height": h,
        }
        with open(PASTA / "config.json", "w") as f:
            json.dump(config, f, indent=2)

        print()
        print(f" OK! Região salva em config.json: {config}")
        print(" Pode fechar esta janela e voltar para o CastMaster.")


if __name__ == "__main__":
    main()
