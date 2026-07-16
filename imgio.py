# -*- coding: utf-8 -*-
"""
Leitura/escrita de imagem à prova de acento.

Por que existe: no Windows o OpenCV usa caminhos ANSI internamente, então
cv2.imread/cv2.imwrite FALHAM EM SILÊNCIO quando o caminho tem caractere
não-ASCII — e o caminho deste projeto tem: "...\\Área de Trabalho\\...".

    cv2.imwrite("C:/.../Área de Trabalho/x.png", img)  -> False (sem erro!)
    cv2.imread("C:/.../Área de Trabalho/x.png")        -> None  (sem erro!)

A solução é fazer o I/O pelo numpy (que lida com Unicode) e deixar o OpenCV
só codificar/decodificar os bytes.
"""
from pathlib import Path

import cv2
import numpy as np


def imread_u(caminho, flags=cv2.IMREAD_COLOR):
    """Igual cv2.imread, mas funciona com acento no caminho. None se falhar."""
    caminho = Path(caminho)
    if not caminho.exists():
        return None
    dados = np.fromfile(str(caminho), dtype=np.uint8)
    if dados.size == 0:
        return None
    return cv2.imdecode(dados, flags)


def imwrite_u(caminho, img):
    """Igual cv2.imwrite, mas funciona com acento no caminho. True se deu certo."""
    caminho = Path(caminho)
    ok, buf = cv2.imencode(caminho.suffix, img)
    if not ok:
        return False
    buf.tofile(str(caminho))
    return True
