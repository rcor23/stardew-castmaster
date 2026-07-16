# -*- coding: utf-8 -*-
"""
Stardewbot — Interface gráfica.

Rode com: python app.py

Tudo em um lugar só:
  - Botão Calibrar (abre o fluxo de calibração)
  - Botão Iniciar/Parar
  - Switch "Controlar o mouse" (desligado = só observa, modo detecção)
  - Preview ao vivo do que o bot enxerga
  - Slider de ajuste fino (zona morta)
  - REGISTRO ESTATÍSTICO por peixe (tentativas, taxa de sucesso,
    tempo médio e "controle %"), salvo em estatisticas.json

Kill switches: botão Parar, fechar a janela, ou mouse no canto da tela.
"""
import json
import queue
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import mss
import pyautogui
import pydirectinput
import customtkinter as ctk
from PIL import Image

from deteccao import detectar, detectar_mordida, detectar_barra_forca
from imgio import imwrite_u

try:
    import keyboard  # hotkey global: liga/desliga sem sair do jogo
except Exception:
    keyboard = None

try:
    import winsound

    def bipe(freq, ms):
        winsound.Beep(freq, ms)
except Exception:
    def bipe(freq, ms):
        pass

# --- fases do ciclo automático ---
F_ARREMESSAR = "arremessando"
F_BOIA = "esperando a boia"
F_MORDIDA = "esperando a mordida"
F_FISGADO = "fisgou!"
F_MINIGAME = "MINIGAME"
F_GUARDANDO = "guardando o peixe"

ESPERA_INICIO = 5.0     # s após clicar em Iniciar, p/ você voltar o foco ao jogo
# O Stardew lê o estado do botão a cada tick (~16ms). Um pydirectinput.click()
# faz down+up em menos de 1ms e cai ENTRE os ticks — o jogo simplesmente não vê.
# Foi por isso que a fisgada falhava mas o arremesso (que segura 0.65s) pegava.
DUR_CLIQUE = 0.10       # s segurando o botão num clique "normal"
TEMPO_CARGA = 0.65      # s segurando o clique p/ arremessar (define a distância)
ESPERA_BOIA = 1.8       # s até a boia cair na água
TIMEOUT_MORDIDA = 45    # s sem morder -> arremessa de novo
# 2.5s era curto: o log mostrou ~2 falhas de arremesso depois de CADA peixe,
# porque a animação de guardar o peixe ainda estava rolando.
ESPERA_POS = 4.0        # s depois do minigame (animação do peixe) antes de arremessar
TIMEOUT_FISGADO = 6.0   # s esperando o minigame abrir depois de fisgar
VEL_MAX = 600.0         # px/s; acima disso e glitch de deteccao (real vai ate ~450)
# Popups que precisam de clique (baú/tesouro, peixe novo, recorde) somem em 1-2
# retentativas do arremesso. Mas se o arremesso falhar MUITAS vezes seguidas,
# tem algo travando que o bot não resolve sozinho — o caso clássico é o
# INVENTÁRIO CHEIO. Aí ele para e avisa em vez de ficar clicando à toa.
MAX_FALHAS_ARREMESSO = 12   # ~1 minuto de tentativas
HOTKEY_PADRAO = "f8"

PASTA = Path(__file__).parent
ARQ_STATS = PASTA / "estatisticas.json"
ARQ_LOG = PASTA / "debug.log"
ARQ_PREFS = PASTA / "preferencias.json"
# A trilha do minigame é estreita e alta (~53x575), então a caixa acompanha
# essa proporção — uma caixa larga só renderiza preto dos lados.
PREVIEW_MAX = (110, 430)  # tamanho máximo da preview (largura, altura)

pyautogui.FAILSAFE = True

# Sem um AppUserModelID próprio, o Windows agrupa a janela sob o python.exe e
# mostra o logo do Python na barra de tarefas, ignorando o iconbitmap(). Precisa
# ser declarado ANTES da janela existir.
try:
    import ctypes

    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("rcor23.stardew.castmaster")
except Exception:
    pass

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

# Cor padrão do botão. Precisa ser explícita: configure(fg_color=None) lança
# ValueError no customtkinter, o que deixava o botão preso em "Parar".
COR_BOTAO = ctk.ThemeManager.theme["CTkButton"]["fg_color"]

# --- paleta ---
COR_CARTAO = "#212936"
COR_CARTAO_ALT = "#1a212c"
COR_BORDA = "#3a4557"
COR_FRACA = "#7d8ba1"
COR_OK = "#2b7a2b"
COR_ERRO = "#a33"
COR_PARADO = "#4a5568"
COR_ATIVA = "#2b7a2b"
COR_ESPERA = "#3B8ED0"

# cor do selo de status conforme a fase
CORES_FASE = {
    "parado": COR_PARADO,
    F_MINIGAME: COR_ATIVA,
    "SEGURANDO": COR_ATIVA,
    "soltando": COR_ATIVA,
    "observando": COR_ESPERA,
    F_ARREMESSAR: COR_ESPERA,
    F_BOIA: COR_ESPERA,
    F_MORDIDA: COR_ESPERA,
    F_FISGADO: COR_ATIVA,
    F_GUARDANDO: COR_ESPERA,
}


def cor_do_status(txt):
    """Verde = agindo, azul = esperando, cinza = parado, vermelho = problema."""
    if not txt:
        return COR_PARADO
    if "TRAVADO" in txt or "⚠" in txt or "ABORTADO" in txt:
        return COR_ERRO
    if "marque" in txt or "clique no JOGO" in txt:
        return "#b8860b"
    for chave, cor in CORES_FASE.items():
        if txt.startswith(chave):
            return cor
    return COR_PARADO


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Stardew CastMaster")
        # Medido: o conteúdo pede 519x870. Antes a janela era mais baixa e a
        # tabela de estatísticas ficava cortada.
        self.geometry("640x890")
        self.resizable(False, False)

        # estado compartilhado com a thread do bot
        self.rodando = False
        self.thread = None
        self.frame_lock = threading.Lock()
        self.ultimo_frame = None
        self.estado = "parado"
        self.fps = 0
        self.capturas = 0
        self.prefs = self._carregar_prefs()
        self.zona_morta = 6
        # segundos de antecipação do controle preditivo. A barra leva ~1.6s p/
        # reverter a queda (medido), então ~0.45s à frente evita o overshoot.
        self.antecipacao = 0.45
        self.proc_calib = None  # processo da calibração (evita abrir vários)
        self.falhas_arremesso = 0
        self.motivo_parada = None   # texto do alarme quando o bot para sozinho
        self.hotkey_atual = None
        self.via_hotkey = False
        # ponte entre a thread do keyboard e a thread do Tk
        self.fila_hotkey = queue.SimpleQueue()

        # tolerância a falhas de detecção: só encerra o minigame depois de
        # MISSES_P_ENCERRAR frames seguidos sem ver barra+peixe. Sem isso, um
        # único frame perdido vira "minigame acabou" e conta um jogo falso.
        self.misses_p_encerrar = 20
        # minigame mais curto que isso é ruído, não conta
        self.duracao_minima = 1.5

        # estatísticas
        self.stats_lock = threading.Lock()
        self.pendente = None          # dict {duracao, controle} de um minigame ainda sem resultado
        self.log = self._carregar_log()  # lista de registros finalizados
        self.tabela_suja = True       # sinaliza que a tabela precisa ser redesenhada

        self._montar_ui()
        self._aplicar_prefs()
        self._atualizar_ui()
        self._por_icone()

    def _por_icone(self):
        """Ícone da janela e da barra de tarefas.

        O customtkinter aplica um ícone próprio ~200ms depois de abrir, então
        aplicar o nosso agora seria sobrescrito. Por isso o atraso.
        """
        ico = PASTA / "icone.ico"
        if not ico.exists():
            return
        self.after(300, lambda: self._tentar_icone(ico))

    def _tentar_icone(self, ico):
        try:
            self.iconbitmap(str(ico))            # esta janela
            self.iconbitmap(default=str(ico))    # e as filhas (diálogos)
        except Exception as e:
            self._dbg(f"não consegui aplicar o ícone: {e}")

    # ---------- diário de bordo (diagnóstico) ----------
    def _dbg(self, msg):
        """Registra em debug.log. É o que permite saber o que o bot fez de fato."""
        try:
            with open(ARQ_LOG, "a", encoding="utf-8") as f:
                f.write(f"{datetime.now().strftime('%H:%M:%S.%f')[:-3]}  {msg}\n")
        except Exception:
            pass

    # ---------- preferências (lembra os switches entre sessões) ----------
    def _carregar_prefs(self):
        try:
            with open(ARQ_PREFS, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _aplicar_prefs(self):
        p = self.prefs
        self._registrar_hotkey(p.get("hotkey", HOTKEY_PADRAO))
        if p.get("auto"):
            self.sw_auto.select()
        if not p.get("mouse", True):
            self.sw_mouse.deselect()
        if "peixe" in p:
            self.ent_peixe.insert(0, p["peixe"])
        if "antecipacao" in p:
            self.antecipacao = float(p["antecipacao"])
            self.sl_ant.set(self.antecipacao)
            self.lbl_ant.configure(text=f"{self.antecipacao:.2f} s")
        if "zona_morta" in p:
            self.zona_morta = int(p["zona_morta"])
            self.sl_zona.set(self.zona_morta)
            self.lbl_zona.configure(text=f"{self.zona_morta} px")

    def _salvar_prefs(self):
        try:
            with open(ARQ_PREFS, "w", encoding="utf-8") as f:
                json.dump({
                    "auto": bool(self.sw_auto.get()),
                    "mouse": bool(self.sw_mouse.get()),
                    "peixe": self.ent_peixe.get().strip(),
                    "antecipacao": self.antecipacao,
                    "zona_morta": self.zona_morta,
                    "hotkey": self.prefs.get("hotkey", HOTKEY_PADRAO),
                }, f, indent=2)
        except Exception:
            pass

    # ---------- persistência ----------
    def _carregar_log(self):
        try:
            with open(ARQ_STATS, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def _salvar_log(self):
        try:
            with open(ARQ_STATS, "w", encoding="utf-8") as f:
                json.dump(self.log, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print("Falha ao salvar estatísticas:", e)

    # ---------- UI ----------
    def _cartao(self, pai, titulo):
        """Um bloco visual com título — agrupa controles relacionados."""
        card = ctk.CTkFrame(pai, corner_radius=10, fg_color=COR_CARTAO)
        card.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(card, text=titulo.upper(), font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=COR_FRACA).pack(anchor="w", padx=14, pady=(10, 2))
        return card

    def _slider(self, pai, nome, unidade, lo, hi, valor, callback, ajuda, passos=None):
        """Slider com nome, valor e uma linha explicando o que ele faz."""
        topo = ctk.CTkFrame(pai, fg_color="transparent")
        topo.pack(fill="x", padx=14, pady=(6, 0))
        ctk.CTkLabel(topo, text=nome, font=ctk.CTkFont(size=12)).pack(side="left")
        lbl = ctk.CTkLabel(topo, text=f"{valor:g} {unidade}",
                           font=ctk.CTkFont(size=12, weight="bold"))
        lbl.pack(side="right")
        sl = ctk.CTkSlider(pai, from_=lo, to=hi, number_of_steps=passos,
                           command=callback, height=16)
        sl.set(valor)
        sl.pack(fill="x", padx=14, pady=(2, 0))
        ctk.CTkLabel(pai, text=ajuda, font=ctk.CTkFont(size=10), text_color=COR_FRACA,
                     wraplength=260, justify="left").pack(anchor="w", padx=14, pady=(1, 8))
        return sl, lbl

    def _tile(self, pai, titulo):
        """Um quadradinho de número (minigames, fps)."""
        t = ctk.CTkFrame(pai, corner_radius=8, fg_color=COR_CARTAO)
        t.pack(side="left", expand=True, fill="x", padx=3)
        valor = ctk.CTkLabel(t, text="0", font=ctk.CTkFont(size=20, weight="bold"))
        valor.pack(pady=(8, 0))
        ctk.CTkLabel(t, text=titulo, font=ctk.CTkFont(size=10),
                     text_color=COR_FRACA).pack(pady=(0, 8))
        return valor

    def _montar_ui(self):
        # ===== cabeçalho =====
        cab = ctk.CTkFrame(self, height=56, corner_radius=0, fg_color=COR_CARTAO)
        cab.pack(side="top", fill="x")
        cab.pack_propagate(False)
        ctk.CTkLabel(cab, text="🎣  Stardew CastMaster",
                     font=ctk.CTkFont(size=19, weight="bold")).pack(side="left", padx=18)
        self.lbl_status = ctk.CTkLabel(cab, text="parado", font=ctk.CTkFont(size=12, weight="bold"),
                                       corner_radius=12, fg_color=COR_PARADO,
                                       text_color="#ffffff", padx=14, pady=5)
        self.lbl_status.pack(side="right", padx=18)

        corpo = ctk.CTkFrame(self, fg_color="transparent")
        corpo.pack(side="top", fill="both", expand=True, padx=14, pady=14)

        # ===== coluna esquerda: o que o bot enxerga =====
        esq = ctk.CTkFrame(corpo, corner_radius=10, fg_color=COR_CARTAO)
        esq.pack(side="left", fill="y")
        ctk.CTkLabel(esq, text="VISÃO DO BOT", font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=COR_FRACA).pack(pady=(12, 2))
        moldura = ctk.CTkFrame(esq, corner_radius=6, fg_color="#000000")
        moldura.pack(padx=12, pady=(4, 6))
        self.lbl_preview = ctk.CTkLabel(moldura, text="inicie para ver", text_color=COR_FRACA,
                                        width=PREVIEW_MAX[0], height=PREVIEW_MAX[1])
        self.lbl_preview.pack(padx=4, pady=4)
        ctk.CTkLabel(esq, text="🟩 barra    🟥 peixe", font=ctk.CTkFont(size=10),
                     text_color=COR_FRACA).pack(pady=(0, 12))

        # ===== coluna direita: controles =====
        dir_ = ctk.CTkFrame(corpo, fg_color="transparent")
        dir_.pack(side="right", fill="both", expand=True, padx=(14, 0))

        c1 = self._cartao(dir_, "controle")
        self.btn_iniciar = ctk.CTkButton(c1, text="▶   Iniciar", height=42, corner_radius=8,
                                         font=ctk.CTkFont(size=14, weight="bold"),
                                         command=self.alternar)
        self.btn_iniciar.pack(fill="x", padx=14, pady=(4, 6))
        self.btn_calibrar = ctk.CTkButton(c1, text="🎯   Calibrar", height=30, corner_radius=8,
                                          fg_color="transparent", border_width=1,
                                          border_color=COR_BORDA, text_color=COR_FRACA,
                                          hover_color=COR_CARTAO_ALT, command=self.abrir_calibracao)
        self.btn_calibrar.pack(fill="x", padx=14, pady=(0, 10))

        self.sw_mouse = ctk.CTkSwitch(c1, text="Controlar o mouse", font=ctk.CTkFont(size=12))
        self.sw_mouse.select()
        self.sw_mouse.pack(padx=14, pady=(0, 6), anchor="w")
        self.sw_auto = ctk.CTkSwitch(c1, text="Pescar sozinho (arremessa e fisga)",
                                     font=ctk.CTkFont(size=12))
        self.sw_auto.pack(padx=14, pady=(0, 10), anchor="w")

        # atalho global: liga/desliga de dentro do jogo
        lh = ctk.CTkFrame(c1, fg_color="transparent")
        lh.pack(fill="x", padx=14, pady=(0, 12))
        ctk.CTkLabel(lh, text="Atalho (funciona dentro do jogo)",
                     font=ctk.CTkFont(size=11), text_color=COR_FRACA).pack(side="left")
        self.btn_hotkey = ctk.CTkButton(lh, text="trocar", width=58, height=24,
                                        corner_radius=6, fg_color="transparent",
                                        border_width=1, border_color=COR_BORDA,
                                        text_color=COR_FRACA, font=ctk.CTkFont(size=11),
                                        hover_color=COR_CARTAO_ALT, command=self._trocar_hotkey)
        self.btn_hotkey.pack(side="right")
        self.lbl_hotkey = ctk.CTkLabel(lh, text=HOTKEY_PADRAO.upper(),
                                       font=ctk.CTkFont(size=12, weight="bold"),
                                       text_color=COR_FRACA)
        self.lbl_hotkey.pack(side="right", padx=(0, 8))

        c2 = self._cartao(dir_, "ajuste fino")
        self.sl_zona, self.lbl_zona = self._slider(
            c2, "Zona morta", "px", 0, 20, self.zona_morta, self._mudou_zona,
            "tolerância em volta do alvo", passos=20)
        self.sl_ant, self.lbl_ant = self._slider(
            c2, "Antecipação", "s", 0.0, 1.0, self.antecipacao, self._mudou_ant,
            "mira onde a barra VAI estar — evita o efeito sanfona")

        tiles = ctk.CTkFrame(dir_, fg_color="transparent")
        tiles.pack(fill="x")
        self.tile_mg = self._tile(tiles, "minigames")
        self.tile_fps = self._tile(tiles, "fps")
        self.lbl_stats = ctk.CTkLabel(self, text="")   # compat: atualizado via tiles

        # ===== rodapé: registro estatístico =====
        baixo = ctk.CTkFrame(self, corner_radius=10, fg_color=COR_CARTAO)
        baixo.pack(side="bottom", fill="both", expand=True, padx=14, pady=(0, 10))

        linha = ctk.CTkFrame(baixo, fg_color="transparent")
        linha.pack(fill="x", padx=14, pady=(12, 6))
        ctk.CTkLabel(linha, text="Peixe atual", font=ctk.CTkFont(size=11),
                     text_color=COR_FRACA).pack(side="left", padx=(0, 8))
        self.ent_peixe = ctk.CTkEntry(linha, placeholder_text="ex.: Peixe-gato", width=150,
                                      height=30, corner_radius=8, border_color=COR_BORDA)
        self.ent_peixe.pack(side="left", padx=(0, 14))
        self.btn_peguei = ctk.CTkButton(linha, text="✔   Peguei", width=95, height=30,
                                        corner_radius=8, fg_color=COR_OK, hover_color="#246324",
                                        command=lambda: self.marcar(True))
        self.btn_peguei.pack(side="left", padx=3)
        self.btn_escapou = ctk.CTkButton(linha, text="✖   Escapou", width=95, height=30,
                                         corner_radius=8, fg_color=COR_ERRO, hover_color="#822",
                                         command=lambda: self.marcar(False))
        self.btn_escapou.pack(side="left", padx=3)
        self.btn_limpar = ctk.CTkButton(linha, text="🗑", width=34, height=30, corner_radius=8,
                                        fg_color="transparent", border_width=1,
                                        border_color=COR_BORDA, text_color=COR_FRACA,
                                        hover_color=COR_CARTAO_ALT, command=self.limpar_stats)
        self.btn_limpar.pack(side="right")

        self.txt_tabela = ctk.CTkTextbox(baixo, font=ctk.CTkFont(family="Consolas", size=14),
                                         height=170, corner_radius=8, fg_color=COR_CARTAO_ALT,
                                         border_width=0, text_color="#e8ecf3",
                                         activate_scrollbars=False)
        self.txt_tabela.pack(fill="both", expand=True, padx=14, pady=(0, 12))
        self.txt_tabela.configure(state="disabled")

        ctk.CTkLabel(self, text="Marque ✔/✖ ao fim de cada peixe · Failsafe: mouse no canto aborta",
                     font=ctk.CTkFont(size=11), text_color="gray60").pack(side="bottom", pady=(0, 8))

        self.protocol("WM_DELETE_WINDOW", self._fechar)

    def _mudou_zona(self, v):
        self.zona_morta = int(v)
        self.lbl_zona.configure(text=f"{self.zona_morta} px")

    def _mudou_ant(self, v):
        self.antecipacao = float(v)
        self.lbl_ant.configure(text=f"{self.antecipacao:.2f} s")

    # ---------- hotkey global ----------
    def _registrar_hotkey(self, tecla):
        """Liga/desliga o bot de dentro do jogo, sem alt+tab.

        Bônus: quando o start vem daqui, o cursor e o foco já estão no jogo —
        então não precisa da espera de 5s que existe pro start pelo botão.
        """
        if keyboard is None:
            self.lbl_hotkey.configure(text="(indisponível)", text_color=COR_ERRO)
            return
        try:
            if self.hotkey_atual:
                keyboard.remove_hotkey(self.hotkey_atual)
        except Exception:
            pass
        try:
            # O callback roda na thread do keyboard, e o Tkinter NÃO é
            # thread-safe: mexer nele de fora (mesmo via after()) dá
            # "main thread is not in main loop". Então a thread só deposita um
            # pedido na fila, e quem age é o refresh da UI, na thread do Tk.
            self.hotkey_atual = keyboard.add_hotkey(
                tecla, lambda: self.fila_hotkey.put(True))
            self.prefs["hotkey"] = tecla
            self.lbl_hotkey.configure(text=tecla.upper(), text_color=COR_FRACA)
            self._dbg(f"hotkey registrada: {tecla}")
        except Exception as e:
            self.hotkey_atual = None
            self.lbl_hotkey.configure(text="tecla inválida", text_color=COR_ERRO)
            self._dbg(f"falha ao registrar hotkey {tecla!r}: {e}")

    def _toggle_hotkey(self):
        if self.rodando:
            self.parar()
        else:
            self.iniciar(via_hotkey=True)   # já está no jogo: não espera

    def _trocar_hotkey(self):
        """Captura a próxima tecla que você apertar e usa como hotkey."""
        if keyboard is None:
            return
        self.btn_hotkey.configure(text="aperte uma tecla…")
        self.update_idletasks()

        def capturar():
            try:
                ev = keyboard.read_event(suppress=False)
                while ev.event_type != "down":
                    ev = keyboard.read_event(suppress=False)
                self.after(0, lambda: self._aplicar_hotkey(ev.name))
            except Exception:
                self.after(0, lambda: self.btn_hotkey.configure(text="trocar"))

        threading.Thread(target=capturar, daemon=True).start()

    def _aplicar_hotkey(self, tecla):
        self.btn_hotkey.configure(text="trocar")
        self._registrar_hotkey(tecla)
        self._salvar_prefs()

    # ---------- ações ----------
    def abrir_calibracao(self):
        # já tem uma calibração aberta? não abre outra.
        if self.proc_calib is not None and self.proc_calib.poll() is None:
            self.lbl_status.configure(text="calibração já está aberta")
            return
        if self.rodando:
            self.parar()
        # console próprio, senão você não vê as instruções da calibração
        flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
        self.proc_calib = subprocess.Popen(
            [sys.executable, str(PASTA / "calibrar.py")], cwd=PASTA, creationflags=flags
        )
        self.lbl_status.configure(text="calibrando (siga o terminal)...")

    def alternar(self):
        if self.rodando:
            self.parar()
        else:
            self.iniciar()

    def iniciar(self, via_hotkey=False):
        # trava contra thread duplicada (dois cliques rápidos criavam 2 bots)
        if self.rodando or (self.thread is not None and self.thread.is_alive()):
            return
        try:
            with open(PASTA / "config.json") as f:
                self.região = json.load(f)
            # região do "!" é opcional: sem ela, só o modo manual funciona
            self.reg_mordida = self.região.get("mordida")
            self.altura_trilha = self.região["height"]
        except Exception:
            self.lbl_status.configure(text="⚠ calibre primeiro!")
            return
        if self.sw_auto.get() and not self.reg_mordida:
            self.lbl_status.configure(text="⚠ sem região do '!' — auto indisponível")
            self.sw_auto.deselect()
        self.rodando = True
        self.via_hotkey = via_hotkey
        self.motivo_parada = None
        self.falhas_arremesso = 0
        self.estado = "esperando..."
        self.btn_iniciar.configure(text="⏸   Parar", fg_color=COR_ERRO, hover_color="#822")
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def parar(self):
        self.rodando = False
        self.estado = "parado"
        self._dbg("--- PARADO pelo usuário ---")
        # solta o mouse: se o bot estava segurando o clique, sem isso o botão
        # fica preso do ponto de vista do Windows
        try:
            pydirectinput.mouseUp()
        except Exception:
            pass
        self.btn_iniciar.configure(text="▶   Iniciar", fg_color=COR_BOTAO,
                                   hover_color=ctk.ThemeManager.theme["CTkButton"]["hover_color"])

    def _fechar(self):
        self._salvar_prefs()
        # solta a hotkey: sem isso o hook global sobrevive ao fechar a janela
        if keyboard is not None and self.hotkey_atual:
            try:
                keyboard.remove_hotkey(self.hotkey_atual)
            except Exception:
                pass
        self.rodando = False
        time.sleep(0.1)
        self.destroy()

    # ---------- estatísticas ----------
    def marcar(self, sucesso):
        """Finaliza o último minigame com o resultado informado pelo usuário."""
        with self.stats_lock:
            p = self.pendente
            self.pendente = None
        if p is None:
            self.lbl_status.configure(text="(nenhum minigame p/ marcar)")
            return
        peixe = self.ent_peixe.get().strip() or "?"
        self.log.append({
            "peixe": peixe,
            "sucesso": bool(sucesso),
            "duracao": round(p["duracao"], 1),
            "controle": round(p["controle"], 3),
            "quando": datetime.now().isoformat(timespec="seconds"),
        })
        self._salvar_log()
        self.tabela_suja = True

    def limpar_stats(self):
        self.log = []
        with self.stats_lock:
            self.pendente = None
        self._salvar_log()
        self.tabela_suja = True

    def _resumo_por_peixe(self):
        """Agrupa o log por peixe e devolve linhas prontas + total."""
        grupos = {}
        for r in self.log:
            grupos.setdefault(r["peixe"], []).append(r)

        linhas = []
        tot_n = tot_ok = tot_marcados = 0
        tot_dur = tot_ctrl = 0.0
        for peixe, rs in sorted(grupos.items()):
            n = len(rs)
            # A taxa de sucesso só vale sobre os que VOCÊ marcou. Antes eu
            # dividia pelo total, então minigames não marcados (sucesso=None)
            # apareciam como fracasso e a tabela mostrava "0%" para peixes que
            # simplesmente não tinham resultado informado.
            marcados = [r for r in rs if r["sucesso"] is not None]
            ok = sum(1 for r in marcados if r["sucesso"])
            taxa = (ok / len(marcados)) if marcados else None
            dur = sum(r["duracao"] for r in rs) / n
            ctrl = sum(r["controle"] for r in rs) / n
            linhas.append((peixe, n, taxa, dur, ctrl))
            tot_n += n
            tot_ok += ok
            tot_marcados += len(marcados)
            tot_dur += sum(r["duracao"] for r in rs)
            tot_ctrl += sum(r["controle"] for r in rs)

        total = None
        if tot_n:
            taxa_tot = (tot_ok / tot_marcados) if tot_marcados else None
            total = ("TOTAL", tot_n, taxa_tot, tot_dur / tot_n, tot_ctrl / tot_n)
        return linhas, total

    def _redesenhar_tabela(self):
        linhas, total = self._resumo_por_peixe()

        def fmt(nome, n, taxa, dur, ctrl, marca=""):
            # taxa None = nenhum marcado ainda; mostra "—" em vez de fingir 0%
            txt_taxa = "—" if taxa is None else f"{taxa*100:.0f}%"
            return (f"  {nome:<15}{n:>5}{txt_taxa:>9}{dur:>8.1f}s"
                    f"{ctrl*100:>10.0f}%   {marca}\n")

        if not linhas:   # sem cabeçalho vazio pairando sobre nada
            texto = ("\n   Nenhum peixe registrado ainda.\n\n"
                     "   Escreva o nome do peixe acima, deixe o bot jogar,\n"
                     "   e marque ✔ Peguei ou ✖ Escapou no fim de cada um.\n")
        else:
            cab = f"  {'PEIXE':<15}{'TENT':>5}{'SUCESSO':>9}{'TEMPO':>9}{'CONTROLE':>10}\n"
            sep = "  " + "─" * 52 + "\n"
            corpo = ""
            for peixe, n, taxa, dur, ctrl in linhas:
                nome = (peixe[:14]) if len(peixe) > 14 else peixe
                # medidor pelo CONTROLE (que o bot mede sozinho e sempre existe),
                # não pela taxa de sucesso, que depende de você marcar
                marca = "●" if ctrl >= 0.8 else ("◐" if ctrl >= 0.5 else "○")
                corpo += fmt(nome, n, taxa, dur, ctrl, marca)
            if total:
                _, n, taxa, dur, ctrl = total
                corpo += sep + fmt("TOTAL", n, taxa, dur, ctrl)
            texto = cab + sep + corpo

        self.txt_tabela.configure(state="normal")
        self.txt_tabela.delete("1.0", "end")
        self.txt_tabela.insert("1.0", texto)
        self.txt_tabela.configure(state="disabled")

    # ---------- lógica do bot (rodam na thread) ----------
    def _print_diagnostico(self, sct):
        """Salva a tela quando o arremesso falha em série.

        É a única forma de descobrir o que está na frente travando o ciclo
        (popup de peixe novo? recorde? energia acabou?) sem adivinhar.
        """
        try:
            tela = np.array(sct.grab(sct.monitors[1]))[:, :, :3]
            imwrite_u(PASTA / "falha_arremesso.png", tela)
            self._dbg("  -> print da tela salvo em falha_arremesso.png")
        except Exception as e:
            self._dbg(f"  -> falhou ao salvar print: {e}")

    def _alarmar_travado(self, sct):
        """Para o bot e chama você: tem algo travando que ele não resolve.

        O suspeito nº1 é o INVENTÁRIO CHEIO — o peixe não entra na mochila e o
        jogo não deixa arremessar. Também pode ser um popup que o clique não
        dispensa. O print salvo mostra o que era.
        """
        self._print_diagnostico(sct)
        self._dbg(f"!!! TRAVADO: {self.falhas_arremesso} arremessos falharam seguidos. "
                  f"Provável INVENTÁRIO CHEIO. Parando e avisando.")
        self.motivo_parada = "⚠ TRAVADO — inventário cheio? · veja falha_arremesso.png"
        self.rodando = False           # encerra o loop
        for _ in range(6):             # alarme: você está no jogo, não vê a tela do bot
            bipe(1200, 200)
            time.sleep(0.08)

    def _clicar(self, dur=DUR_CLIQUE):
        """Clique que o jogo enxerga: segura o botão por alguns ticks.

        pydirectinput.click() faz down+up instantâneo e o Stardew não registra
        (comprovado no debug.log: a fisgada por click() falhava sempre, mas o
        arremesso, que segura 0.65s, hookava o peixe sem querer).
        """
        pydirectinput.mouseDown()
        time.sleep(dur)
        pydirectinput.mouseUp()

    def _jogar_minigame(self, barra_y, peixe_y, vel, segurando):
        """Segura/solta o clique pra levar a barra verde até o peixe.

        Controle PREDITIVO, não liga/desliga. A barra do Stardew tem inércia
        pesada: medido no debug.log, mesmo segurando ela levou 1.6s para parar
        de cair. Um controle que só reage quando o peixe cruza a barra chega
        sempre tarde e faz a barra passar voando (efeito sanfona: controle 7-12%).

        Então miramos onde a barra VAI ESTAR daqui a `antecipacao` segundos:

            prevista = barra_y + velocidade * antecipacao

        e comparamos o peixe com essa posição prevista. Assim ele solta ANTES
        de chegar, deixando a inércia terminar o trabalho.
        """
        if not self.sw_mouse.get():
            self.estado = "observando"
            return segurando

        # Um frame de detecção ruim gera velocidade absurda (o log real teve
        # +1946px/s, prevendo a barra em 1406 numa trilha de 575px). Limita a
        # previsão à trilha para que um glitch não vire uma decisão maluca.
        prevista = barra_y + vel * self.antecipacao
        prevista = max(0.0, min(float(self.altura_trilha), prevista))
        if peixe_y < prevista - self.zona_morta and not segurando:
            pydirectinput.mouseDown()   # vai parar abaixo do peixe -> sobe mais
            segurando = True
        elif peixe_y > prevista + self.zona_morta and segurando:
            pydirectinput.mouseUp()     # vai parar acima do peixe -> deixa cair
            segurando = False
        self.estado = "SEGURANDO" if segurando else "soltando"
        return segurando

    def _registrar_minigame(self, dur, ctrl):
        """Guarda o minigame que acabou. Ignora se foi curto demais (ruído)."""
        if dur < self.duracao_minima:
            return
        self.capturas += 1
        with self.stats_lock:
            if self.pendente is not None:  # não marcado: fica como "?"
                self.log.append({
                    "peixe": self.ent_peixe.get().strip() or "?",
                    "sucesso": None,
                    "duracao": round(self.pendente["duracao"], 1),
                    "controle": round(self.pendente["controle"], 3),
                    "quando": datetime.now().isoformat(timespec="seconds"),
                })
            self.pendente = {"duracao": dur, "controle": ctrl}
        self._salvar_log()
        self.tabela_suja = True

    def _passo_auto(self, sct, fase, t_fase):
        """Um passo do ciclo automático. Devolve (nova_fase, novo_t_fase)."""
        agora = time.time()

        if fase is None or fase == F_MINIGAME:
            return F_ARREMESSAR, agora

        if fase == F_GUARDANDO:
            if agora - t_fase >= ESPERA_POS:
                return F_ARREMESSAR, time.time()

        elif fase == F_ARREMESSAR:
            # Arremesso em malha fechada. Segura o botão e CONFERE se a barra de
            # força apareceu. Se não apareceu, o clique foi parar num popup (peixe
            # novo / recorde de tamanho) em vez de virar arremesso — nesse caso o
            # próprio clique já dispensou o popup e a gente tenta de novo.
            # Antes eu clicava no escuro pra "dispensar popup": quando não havia
            # popup, esse clique virava um arremesso curto e emperrava o ciclo.
            pydirectinput.mouseDown()
            # Fica de olho durante TODO o carregamento, não só num instante: a
            # barra de força demora a aparecer, e conferir cedo demais fazia o
            # bot desistir e soltar o botão — o que dava um arremesso fraco e
            # deixava a linha na água, emperrando as tentativas seguintes.
            carregando = False
            t0_carga = time.time()
            while time.time() - t0_carga < TEMPO_CARGA:
                if detectar_barra_forca(np.array(sct.grab(self.reg_mordida))[:, :, :3]):
                    carregando = True
                    break
                time.sleep(0.03)
            if not carregando:
                pydirectinput.mouseUp()
                self.falhas_arremesso += 1
                self._dbg(f"arremesso NAO iniciou em {TEMPO_CARGA}s (sem barra de força) — "
                          f"popup ou linha já na água. falhas seguidas: {self.falhas_arremesso}")
                # o clique acima já serve p/ dispensar popup de baú/peixe novo;
                # normalmente resolve em 1-2 tentativas
                if self.falhas_arremesso == 4:   # tira um print p/ diagnóstico
                    self._print_diagnostico(sct)
                if self.falhas_arremesso >= MAX_FALHAS_ARREMESSO:
                    self._alarmar_travado(sct)
                    return F_ARREMESSAR, agora
                return F_GUARDANDO, agora   # espera e tenta de novo
            # confirmou que está carregando: completa a força e solta
            time.sleep(max(0.0, TEMPO_CARGA - (time.time() - t0_carga)))
            pydirectinput.mouseUp()         # solta = arremessa
            self.falhas_arremesso = 0
            self._dbg(f"ARREMESSO confirmado (barra de força vista) "
                      f"cursor={pyautogui.position()}")
            return F_BOIA, time.time()

        elif fase == F_BOIA:
            if agora - t_fase >= ESPERA_BOIA:
                self._dbg("boia caiu -> vigiando o '!'")
                return F_MORDIDA, agora

        elif fase == F_MORDIDA:
            fm = np.array(sct.grab(self.reg_mordida))[:, :, :3]
            if detectar_mordida(fm):
                self._dbg(f"'!' DETECTADO -> fisgando (segura {DUR_CLIQUE}s)")
                self._clicar()             # fisga!
                return F_FISGADO, agora
            if agora - t_fase >= TIMEOUT_MORDIDA:
                self._dbg(f"timeout: {TIMEOUT_MORDIDA}s sem mordida -> rearremessa")
                return F_ARREMESSAR, agora  # não mordeu: joga de novo

        elif fase == F_FISGADO:
            if agora - t_fase >= TIMEOUT_FISGADO:
                self._dbg(f"timeout: minigame nao abriu em {TIMEOUT_FISGADO}s -> rearremessa")
                return F_ARREMESSAR, agora  # minigame não abriu: tenta de novo

        return fase, t_fase

    # ---------- thread do bot ----------
    def _loop(self):
        segurando = False
        minigame_ativo = False
        frames, t0 = 0, time.time()
        mg_inicio = 0.0
        mg_frames = mg_dentro = 0   # p/ medir "controle %"
        misses = 0                  # frames seguidos sem ver barra+peixe
        fase, t_fase = None, time.time()
        barra_ant, t_ant, vel = None, time.time(), 0.0   # p/ estimar a velocidade

        # Dá tempo de você clicar de volta no JOGO. Sem isso o foco e o cursor
        # ficam na janela do bot, e os cliques dele iriam para ela mesma.
        auto_inicial = bool(self.sw_auto.get())
        if auto_inicial and self.via_hotkey:
            self._dbg(f"--- INICIANDO (auto, via atalho). cursor em {pyautogui.position()} ---")
            bipe(880, 120)
        elif auto_inicial:
            self._dbg(f"--- INICIANDO (auto). Esperando {ESPERA_INICIO}s p/ voce focar o jogo ---")
            fim_espera = time.time() + ESPERA_INICIO
            while self.rodando and time.time() < fim_espera:
                self.estado = f"clique no JOGO! {fim_espera - time.time():.0f}s"
                time.sleep(0.1)
            if not self.rodando:      # parou durante a espera: não anuncia início
                self._dbg("--- cancelado durante a espera ---")
                return
            bipe(880, 120)  # começou pra valer
            self._dbg(f"--- COMECOU. cursor em {pyautogui.position()} ---")

        try:
            with mss.mss() as sct:
                while self.rodando:
                    frame = np.array(sct.grab(self.região))[:, :, :3].copy()
                    barra_y, barra_rect, peixe_y, peixe_rect = detectar(frame)
                    ativo = barra_y is not None and peixe_y is not None
                    auto = bool(self.sw_auto.get()) and self.reg_mordida is not None

                    if ativo:
                        misses = 0
                        agora = time.time()
                        if not minigame_ativo:      # começou um minigame
                            minigame_ativo = True
                            fase = F_MINIGAME
                            mg_inicio = agora
                            mg_frames = mg_dentro = 0
                            barra_ant, t_ant, vel = None, agora, 0.0
                            self._dbg("=== MINIGAME ABRIU ===")

                        # velocidade da barra (px/s), suavizada p/ tirar ruído.
                        # Limitada porque a barra real não passa de ~450 px/s:
                        # valores acima disso são glitch de detecção, não física.
                        if barra_ant is not None and agora > t_ant:
                            v_inst = (barra_y - barra_ant) / (agora - t_ant)
                            v_inst = max(-VEL_MAX, min(VEL_MAX, v_inst))
                            vel = 0.6 * vel + 0.4 * v_inst
                        barra_ant, t_ant = barra_y, agora

                        mg_frames += 1
                        by, bh = barra_rect[1], barra_rect[3]
                        if by <= peixe_y <= by + bh:   # peixe dentro da barra
                            mg_dentro += 1
                        segurando = self._jogar_minigame(barra_y, peixe_y, vel, segurando)
                        if mg_frames % 15 == 0:  # amostra periódica, não polui o log
                            prev = barra_y + vel * self.antecipacao
                            self._dbg(f"  minigame: barra={barra_y} peixe={peixe_y} "
                                      f"vel={vel:+.0f}px/s prevista={prev:.0f} "
                                      f"{'SEGURA' if segurando else 'solta'}")
                    else:
                        misses += 1
                        if segurando:
                            pydirectinput.mouseUp()
                            segurando = False

                        if minigame_ativo and misses >= self.misses_p_encerrar:
                            minigame_ativo = False
                            dur = time.time() - mg_inicio
                            ctrl = (mg_dentro / mg_frames) if mg_frames else 0.0
                            self._dbg(f"=== MINIGAME FECHOU === dur={dur:.1f}s "
                                      f"controle={ctrl*100:.0f}% frames={mg_frames} "
                                      f"{'(descartado: curto)' if dur < self.duracao_minima else ''}")
                            self._registrar_minigame(dur, ctrl)
                            fase, t_fase = (F_GUARDANDO, time.time()) if auto else (None, t_fase)
                        elif not minigame_ativo:
                            if auto:
                                fase, t_fase = self._passo_auto(sct, fase, t_fase)
                                # mostra o tempo na fase: sem isso "esperando a
                                # mordida" por 40s parece que o bot travou
                                self.estado = f"{fase} ({int(time.time()-t_fase)}s)" 
                            else:
                                fase = None
                                self.estado = "marque ✔/✖" if self.pendente else "esperando..."

                    # overlay
                    if barra_rect:
                        bx, by, bw, bh = barra_rect
                        cv2.rectangle(frame, (bx, by), (bx + bw, by + bh), (0, 255, 0), 2)
                    if peixe_rect:
                        px, py, pw, ph = peixe_rect
                        cv2.rectangle(frame, (px, py), (px + pw, py + ph), (0, 0, 255), 2)
                    with self.frame_lock:
                        self.ultimo_frame = frame

                    frames += 1
                    if time.time() - t0 >= 1.0:
                        self.fps, frames, t0 = frames, 0, time.time()
        except pyautogui.FailSafeException:
            self.estado = "ABORTADO (failsafe)"
        finally:
            if segurando:
                pydirectinput.mouseUp()
            self.rodando = False

    # ---------- refresh da UI (thread principal) ----------
    def _atualizar_ui(self):
        # try/finally: se algo aqui lançar, o after() no finally garante que o
        # refresh continue. Sem isso um erro isolado mata a UI inteira — foi o
        # que aconteceu quando parar() lançava e a janela travava.
        try:
            # atende pedidos da hotkey aqui, onde é seguro mexer no Tk
            while not self.fila_hotkey.empty():
                self.fila_hotkey.get_nowait()
                self._toggle_hotkey()

            txt = self.motivo_parada or self.estado
            self.lbl_status.configure(text=txt, fg_color=cor_do_status(txt))
            self.tile_mg.configure(text=str(self.capturas))
            self.tile_fps.configure(text=str(self.fps))
            if not self.rodando and self.btn_iniciar.cget("text").startswith("⏸"):
                self.parar()

            if self.tabela_suja:
                self.tabela_suja = False
                self._redesenhar_tabela()

            with self.frame_lock:
                frame = None if self.ultimo_frame is None else self.ultimo_frame.copy()
            if frame is not None:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w = rgb.shape[:2]
                escala = min(PREVIEW_MAX[0] / w, PREVIEW_MAX[1] / h)
                tam = (max(1, int(w * escala)), max(1, int(h * escala)))
                img = ctk.CTkImage(light_image=Image.fromarray(rgb), size=tam)
                self.lbl_preview.configure(image=img, text="")
                self.lbl_preview._image = img  # evita coleta pelo garbage collector
        except Exception as e:
            self._dbg(f"erro no refresh da UI: {type(e).__name__}: {e}")
        finally:
            self.after(66, self._atualizar_ui)  # ~15 fps de preview


if __name__ == "__main__":
    App().mainloop()
