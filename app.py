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

from deteccao import detectar, detectar_mordida

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
TEMPO_CARGA = 0.65      # s segurando o clique p/ arremessar (define a distância)
ESPERA_BOIA = 1.8       # s até a boia cair na água
TIMEOUT_MORDIDA = 45    # s sem morder -> arremessa de novo
ESPERA_POS = 3.0        # s depois do minigame antes do próximo arremesso
TIMEOUT_FISGADO = 6.0   # s esperando o minigame abrir depois de fisgar

PASTA = Path(__file__).parent
ARQ_STATS = PASTA / "estatisticas.json"
ARQ_LOG = PASTA / "debug.log"
PREVIEW_MAX = (300, 420)  # tamanho máximo da preview (largura, altura)

pyautogui.FAILSAFE = True

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

# Cor padrão do botão. Precisa ser explícita: configure(fg_color=None) lança
# ValueError no customtkinter, o que deixava o botão preso em "Parar".
COR_BOTAO = ctk.ThemeManager.theme["CTkButton"]["fg_color"]


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Stardewbot 🎣")
        self.geometry("780x660")
        self.resizable(False, False)

        # estado compartilhado com a thread do bot
        self.rodando = False
        self.thread = None
        self.frame_lock = threading.Lock()
        self.ultimo_frame = None
        self.estado = "parado"
        self.fps = 0
        self.capturas = 0
        self.zona_morta = 6
        self.proc_calib = None  # processo da calibração (evita abrir vários)

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
        self._atualizar_ui()

    # ---------- diário de bordo (diagnóstico) ----------
    def _dbg(self, msg):
        """Registra em debug.log. É o que permite saber o que o bot fez de fato."""
        try:
            with open(ARQ_LOG, "a", encoding="utf-8") as f:
                f.write(f"{datetime.now().strftime('%H:%M:%S.%f')[:-3]}  {msg}\n")
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
    def _montar_ui(self):
        # ===== parte de cima: preview + controles =====
        topo = ctk.CTkFrame(self, fg_color="transparent")
        topo.pack(side="top", fill="x", padx=12, pady=(12, 6))

        esq = ctk.CTkFrame(topo)
        esq.pack(side="left", fill="both")
        ctk.CTkLabel(esq, text="Visão do bot").pack(pady=(8, 4))
        self.lbl_preview = ctk.CTkLabel(esq, text="(inicie para ver)", width=PREVIEW_MAX[0], height=PREVIEW_MAX[1])
        self.lbl_preview.pack(padx=10, pady=(0, 10))

        dir_ = ctk.CTkFrame(topo)
        dir_.pack(side="right", fill="both", expand=True, padx=(12, 0))

        ctk.CTkLabel(dir_, text="Stardewbot", font=ctk.CTkFont(size=22, weight="bold")).pack(pady=(14, 2))
        self.lbl_status = ctk.CTkLabel(dir_, text="parado", font=ctk.CTkFont(size=14))
        self.lbl_status.pack(pady=(0, 10))

        self.btn_iniciar = ctk.CTkButton(dir_, text="▶  Iniciar", height=40, command=self.alternar)
        self.btn_iniciar.pack(fill="x", padx=16, pady=4)

        self.btn_calibrar = ctk.CTkButton(dir_, text="🎯  Calibrar", height=32, fg_color="gray30",
                                          hover_color="gray25", command=self.abrir_calibracao)
        self.btn_calibrar.pack(fill="x", padx=16, pady=4)

        self.sw_mouse = ctk.CTkSwitch(dir_, text="Controlar o mouse (bot joga)")
        self.sw_mouse.select()
        self.sw_mouse.pack(padx=16, pady=(14, 2), anchor="w")

        self.sw_auto = ctk.CTkSwitch(dir_, text="Pescar sozinho (arremessa e fisga)")
        self.sw_auto.pack(padx=16, pady=(2, 4), anchor="w")

        ctk.CTkLabel(dir_, text="Zona morta (px)").pack(padx=16, pady=(12, 0), anchor="w")
        self.sl_zona = ctk.CTkSlider(dir_, from_=0, to=20, number_of_steps=20, command=self._mudou_zona)
        self.sl_zona.set(self.zona_morta)
        self.sl_zona.pack(fill="x", padx=16)
        self.lbl_zona = ctk.CTkLabel(dir_, text=f"{self.zona_morta}")
        self.lbl_zona.pack(padx=16, anchor="e")

        self.lbl_stats = ctk.CTkLabel(dir_, text="minigames: 0   |   0 fps")
        self.lbl_stats.pack(pady=(16, 4))

        # ===== parte de baixo: registro estatístico =====
        baixo = ctk.CTkFrame(self)
        baixo.pack(side="top", fill="both", expand=True, padx=12, pady=(6, 6))

        linha = ctk.CTkFrame(baixo, fg_color="transparent")
        linha.pack(fill="x", padx=10, pady=(10, 4))
        ctk.CTkLabel(linha, text="Peixe atual:").pack(side="left")
        self.ent_peixe = ctk.CTkEntry(linha, placeholder_text="ex.: Peixe-gato", width=150)
        self.ent_peixe.pack(side="left", padx=(6, 12))
        self.btn_peguei = ctk.CTkButton(linha, text="✓ Peguei", width=90, fg_color="#2b7a2b",
                                        hover_color="#246324", command=lambda: self.marcar(True))
        self.btn_peguei.pack(side="left", padx=3)
        self.btn_escapou = ctk.CTkButton(linha, text="✗ Escapou", width=90, fg_color="#a33",
                                        hover_color="#822", command=lambda: self.marcar(False))
        self.btn_escapou.pack(side="left", padx=3)
        self.btn_limpar = ctk.CTkButton(linha, text="🗑 Limpar", width=80, fg_color="gray30",
                                       hover_color="gray25", command=self.limpar_stats)
        self.btn_limpar.pack(side="right")

        self.txt_tabela = ctk.CTkTextbox(baixo, font=ctk.CTkFont(family="Consolas", size=13), height=180)
        self.txt_tabela.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.txt_tabela.configure(state="disabled")

        ctk.CTkLabel(self, text="Marque ✓/✗ ao fim de cada peixe · Failsafe: mouse no canto aborta",
                     font=ctk.CTkFont(size=11), text_color="gray60").pack(side="bottom", pady=(0, 8))

        self.protocol("WM_DELETE_WINDOW", self._fechar)

    def _mudou_zona(self, v):
        self.zona_morta = int(v)
        self.lbl_zona.configure(text=f"{self.zona_morta}")

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

    def iniciar(self):
        try:
            with open(PASTA / "config.json") as f:
                self.região = json.load(f)
            # região do "!" é opcional: sem ela, só o modo manual funciona
            self.reg_mordida = self.região.get("mordida")
        except Exception:
            self.lbl_status.configure(text="⚠ calibre primeiro!")
            return
        if self.sw_auto.get() and not self.reg_mordida:
            self.lbl_status.configure(text="⚠ sem região do '!' — auto indisponível")
            self.sw_auto.deselect()
        self.rodando = True
        self.estado = "esperando..."
        self.btn_iniciar.configure(text="⏸  Parar", fg_color="#a33")
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
        self.btn_iniciar.configure(text="▶  Iniciar", fg_color=COR_BOTAO)

    def _fechar(self):
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
        tot_n = tot_ok = 0
        tot_dur = tot_ctrl = 0.0
        for peixe, rs in sorted(grupos.items()):
            n = len(rs)
            ok = sum(1 for r in rs if r["sucesso"])
            dur = sum(r["duracao"] for r in rs) / n
            ctrl = sum(r["controle"] for r in rs) / n
            linhas.append((peixe, n, ok / n, dur, ctrl))
            tot_n += n
            tot_ok += ok
            tot_dur += sum(r["duracao"] for r in rs)
            tot_ctrl += sum(r["controle"] for r in rs)

        total = None
        if tot_n:
            total = ("TOTAL", tot_n, tot_ok / tot_n, tot_dur / tot_n, tot_ctrl / tot_n)
        return linhas, total

    def _redesenhar_tabela(self):
        linhas, total = self._resumo_por_peixe()
        cab = f"{'Peixe':<16}{'Tent':>5}{'Sucesso':>9}{'Tempo':>8}{'Controle':>10}\n"
        sep = "─" * 48 + "\n"
        corpo = ""
        for peixe, n, taxa, dur, ctrl in linhas:
            nome = (peixe[:15]) if len(peixe) > 15 else peixe
            corpo += f"{nome:<16}{n:>5}{taxa*100:>8.0f}%{dur:>7.1f}s{ctrl*100:>9.0f}%\n"
        if total:
            _, n, taxa, dur, ctrl = total
            corpo += sep
            corpo += f"{'TOTAL':<16}{n:>5}{taxa*100:>8.0f}%{dur:>7.1f}s{ctrl*100:>9.0f}%\n"
        if not linhas:
            corpo = "(sem dados ainda — jogue um minigame e marque ✓ ou ✗)\n"

        self.txt_tabela.configure(state="normal")
        self.txt_tabela.delete("1.0", "end")
        self.txt_tabela.insert("1.0", cab + sep + corpo)
        self.txt_tabela.configure(state="disabled")

    # ---------- lógica do bot (rodam na thread) ----------
    def _jogar_minigame(self, barra_y, peixe_y, segurando):
        """Segura/solta o clique pra levar a barra verde até o peixe."""
        if not self.sw_mouse.get():
            self.estado = "observando"
            return segurando
        if peixe_y < barra_y - self.zona_morta and not segurando:
            pydirectinput.mouseDown()   # peixe acima -> barra sobe
            segurando = True
        elif peixe_y > barra_y + self.zona_morta and segurando:
            pydirectinput.mouseUp()     # peixe abaixo -> barra desce
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
                self._dbg("click p/ dispensar popup do peixe")
                pydirectinput.click()      # dispensa o popup do peixe pescado
                time.sleep(0.3)
                return F_ARREMESSAR, time.time()

        elif fase == F_ARREMESSAR:
            self._dbg(f"ARREMESSO: mouseDown, segura {TEMPO_CARGA}s, mouseUp "
                      f"(cursor em {pyautogui.position()})")
            pydirectinput.mouseDown()
            time.sleep(TEMPO_CARGA)        # segura = carrega a força
            pydirectinput.mouseUp()        # solta = arremessa
            return F_BOIA, time.time()

        elif fase == F_BOIA:
            if agora - t_fase >= ESPERA_BOIA:
                self._dbg("boia caiu -> vigiando o '!'")
                return F_MORDIDA, agora

        elif fase == F_MORDIDA:
            fm = np.array(sct.grab(self.reg_mordida))[:, :, :3]
            if detectar_mordida(fm):
                self._dbg("'!' DETECTADO -> click p/ fisgar")
                pydirectinput.click()      # fisga!
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

        # Dá tempo de você clicar de volta no JOGO. Sem isso o foco e o cursor
        # ficam na janela do bot, e os cliques dele iriam para ela mesma.
        auto_inicial = bool(self.sw_auto.get())
        if auto_inicial:
            self._dbg(f"--- INICIANDO (auto). Esperando {ESPERA_INICIO}s p/ voce focar o jogo ---")
            fim_espera = time.time() + ESPERA_INICIO
            while self.rodando and time.time() < fim_espera:
                self.estado = f"clique no JOGO! {fim_espera - time.time():.0f}s"
                time.sleep(0.1)
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
                        if not minigame_ativo:      # começou um minigame
                            minigame_ativo = True
                            fase = F_MINIGAME
                            mg_inicio = time.time()
                            mg_frames = mg_dentro = 0
                            self._dbg("=== MINIGAME ABRIU ===")
                        mg_frames += 1
                        by, bh = barra_rect[1], barra_rect[3]
                        if by <= peixe_y <= by + bh:   # peixe dentro da barra
                            mg_dentro += 1
                        segurando = self._jogar_minigame(barra_y, peixe_y, segurando)
                        if mg_frames % 15 == 0:  # amostra periódica, não polui o log
                            self._dbg(f"  minigame: barra_y={barra_y} peixe_y={peixe_y} "
                                      f"delta={peixe_y-barra_y:+d} {'SEGURA' if segurando else 'solta'}")
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
                                self.estado = fase
                            else:
                                fase = None
                                self.estado = "marque ✓/✗" if self.pendente else "esperando..."

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
            self.lbl_status.configure(text=self.estado)
            self.lbl_stats.configure(text=f"minigames: {self.capturas}   |   {self.fps} fps")
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
