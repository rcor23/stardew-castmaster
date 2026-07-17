# -*- coding: utf-8 -*-
"""
Wiki de peixes — janela com todos os peixes do Stardew Valley.

Os dados vêm de peixes.json, extraído da tabela oficial do wiki. Cada campo de
texto guarda os dois idiomas em [pt, en]; qual aparece depende de idiomas.py.

O que faz essa wiki valer mais que abrir o site: além de local/estação/hora/
clima, ela mostra a DIFICULDADE e o TIPO DE MOVIMENTO de cada peixe — que é
exatamente o que determina o quanto o bot vai suar — e cruza com o SEU
histórico (estatisticas.json), mostrando como o bot foi de fato naquele peixe.
"""
import json
from pathlib import Path

import customtkinter as ctk
from PIL import Image

from idiomas import t, idx

PASTA = Path(__file__).parent
SPRITES = PASTA / "sprites"

# cores por tipo de movimento — cada um exige uma resposta diferente do bot
COR_MOV = {
    "smooth": "#4a9eda",   # previsível
    "mixed": "#5aab5a",    # padrão
    "floater": "#c9a227",  # tende a subir
    "sinker": "#c97f27",   # tende a afundar
    "dart": "#c9453f",     # arisco: o mais difícil
}

# selo de estação: emoji não renderiza no Tk (vira borrão), então usa letra
# colorida — a cor é o que identifica de relance.
COR_ESTACAO = {
    "spring": "#5aab5a",   # verde: brotos
    "summer": "#e0a92c",   # amarelo: sol
    "fall": "#c96a27",     # laranja: folhas
    "winter": "#5b9bd5",   # azul: gelo
}
ORDEM_ESTACOES = ["spring", "summer", "fall", "winter"]


def slug(nome):
    """Nome do peixe -> nome do arquivo do sprite."""
    return nome.lower().replace(" ", "_").replace(".", "").replace("'", "")


def cor_dificuldade(d):
    if d is None:
        return "#7d8ba1"
    if d <= 35:
        return "#5aab5a"
    if d <= 65:
        return "#c9a227"
    if d <= 85:
        return "#c97f27"
    return "#c9453f"


class Wiki(ctk.CTkToplevel):
    def __init__(self, pai, cores, stats=None):
        super().__init__(pai)
        self.c = cores
        self.stats = stats or []
        self.title(t("wiki_titulo"))
        self.geometry("880x620")
        self.configure(fg_color=self.c["fundo"])

        self.peixes = self._carregar()
        self.filtrados = list(self.peixes)
        self.sel = None
        # o CTkImage precisa ficar vivo, senão o garbage collector come o sprite
        # e a imagem some da tela. Guarda por (nome, tamanho).
        self.cache_img = {}

        self._montar()
        if self.filtrados:
            self._escolher(self.filtrados[0])

        # o Toplevel do customtkinter rouba o ícone; reaplica depois
        self.after(250, self._icone)

    def _icone(self):
        ico = PASTA / "icone.ico"
        if ico.exists():
            try:
                self.iconbitmap(str(ico))
            except Exception:
                pass

    def _carregar(self):
        try:
            with open(PASTA / "peixes.json", encoding="utf-8") as f:
                return json.load(f)["peixes"]
        except Exception:
            return []

    def _txt(self, p, campo):
        """Campo [pt, en] do peixe, na língua atual."""
        v = p.get(campo)
        return v[idx()] if isinstance(v, list) else (v or "")

    def _sprite(self, nome, px):
        """CTkImage do peixe no tamanho pedido, ou None se não tiver sprite."""
        chave = (nome, px)
        if chave in self.cache_img:
            return self.cache_img[chave]
        arq = SPRITES / f"{slug(nome)}.png"
        if not arq.exists():
            return None
        try:
            im = Image.open(arq).convert("RGBA")
            # NEAREST: os sprites são pixel art de 48x48; suavizar borra tudo
            im = im.resize((px, px), Image.NEAREST)
            img = ctk.CTkImage(light_image=im, dark_image=im, size=(px, px))
        except Exception:
            return None
        self.cache_img[chave] = img
        return img

    # ---------- UI ----------
    def _montar(self):
        c = self.c
        topo = ctk.CTkFrame(self, height=48, corner_radius=0, fg_color=c["cartao"])
        topo.pack(fill="x")
        topo.pack_propagate(False)
        ctk.CTkLabel(topo, text=t("wiki_titulo"),
                     font=ctk.CTkFont(size=15, weight="bold")).pack(side="left", padx=16)
        self.lbl_conta = ctk.CTkLabel(topo, text="", font=ctk.CTkFont(size=11),
                                      text_color=c["fraca"])
        self.lbl_conta.pack(side="right", padx=16)

        corpo = ctk.CTkFrame(self, fg_color="transparent")
        corpo.pack(fill="both", expand=True, padx=12, pady=12)

        # ----- esquerda: busca + lista -----
        esq = ctk.CTkFrame(corpo, width=310, corner_radius=10, fg_color=c["cartao"])
        esq.pack(side="left", fill="y")
        esq.pack_propagate(False)

        self.ent_busca = ctk.CTkEntry(esq, placeholder_text=t("wiki_buscar"),
                                      height=32, corner_radius=8, border_color=c["borda"])
        self.ent_busca.pack(fill="x", padx=10, pady=(10, 6))
        self.ent_busca.bind("<KeyRelease>", lambda e: self._filtrar())

        filtros = ctk.CTkFrame(esq, fg_color="transparent")
        filtros.pack(fill="x", padx=10, pady=(0, 6))
        self.filtro_mov = ctk.CTkSegmentedButton(
            filtros, values=[t("wiki_todos"), "dart", "sinker", "floater"],
            command=lambda _: self._filtrar(), font=ctk.CTkFont(size=10), height=26)
        self.filtro_mov.set(t("wiki_todos"))
        self.filtro_mov.pack(fill="x")

        # legenda dos selos de estação
        leg = ctk.CTkFrame(esq, fg_color="transparent")
        leg.pack(fill="x", padx=10, pady=(0, 4))
        for e in ORDEM_ESTACOES:
            ctk.CTkLabel(leg, text=t(f"{e}_letra"), width=18, height=14, corner_radius=4,
                         fg_color=COR_ESTACAO[e], text_color="#ffffff",
                         font=ctk.CTkFont(size=8, weight="bold")).pack(side="left", padx=1)
            ctk.CTkLabel(leg, text=t(e), font=ctk.CTkFont(size=8),
                         text_color=c["fraca"]).pack(side="left", padx=(1, 6))

        self.lista = ctk.CTkScrollableFrame(esq, fg_color=c["cartao_alt"], corner_radius=8)
        self.lista.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # ----- direita: detalhes -----
        self.dir = ctk.CTkFrame(corpo, corner_radius=10, fg_color=c["cartao"])
        self.dir.pack(side="right", fill="both", expand=True, padx=(12, 0))

        self._redesenhar_lista()

    def _filtrar(self):
        q = self.ent_busca.get().strip().lower()
        mov = self.filtro_mov.get()
        self.filtrados = [
            p for p in self.peixes
            if (not q or q in p["nome"].lower() or q in self._txt(p, "local").lower()
                or q in self._txt(p, "estacao").lower() or q in self._txt(p, "grupo").lower())
            and (mov == t("wiki_todos") or p["movimento"] == mov)
        ]
        self._redesenhar_lista()

    def _redesenhar_lista(self):
        for w in self.lista.winfo_children():
            w.destroy()
        self.lbl_conta.configure(text=t("wiki_conta", n=len(self.filtrados),
                                        tot=len(self.peixes)))
        for p in self.filtrados:
            self._item(p)
        if not self.filtrados:
            ctk.CTkLabel(self.lista, text=t("wiki_nada"), text_color=self.c["fraca"],
                         font=ctk.CTkFont(size=11)).pack(pady=20)

    def _item(self, p):
        c = self.c
        linha = ctk.CTkFrame(self.lista, fg_color="transparent", height=34)
        linha.pack(fill="x", pady=1)
        b = ctk.CTkButton(
            linha, text=f"  {p['nome']}", anchor="w", height=30, corner_radius=6,
            image=self._sprite(p["nome"], 24), compound="left",
            fg_color="transparent", hover_color=c["cartao"], text_color="#e8ecf3",
            font=ctk.CTkFont(size=12), command=lambda: self._escolher(p))
        b.pack(side="left", fill="x", expand=True)
        # pastilha da dificuldade: dá pra varrer a lista e achar os difíceis
        ctk.CTkLabel(linha, text=str(p["dificuldade"]), width=28, height=20,
                     corner_radius=6, fg_color=cor_dificuldade(p["dificuldade"]),
                     text_color="#ffffff",
                     font=ctk.CTkFont(size=10, weight="bold")).pack(side="right", padx=(2, 4))
        # selos das estações, na ordem do ano
        for e in reversed(ORDEM_ESTACOES):
            if e in p.get("estacoes", []):
                ctk.CTkLabel(linha, text=t(f"{e}_letra"), width=16, height=16,
                             corner_radius=4, fg_color=COR_ESTACAO[e],
                             text_color="#ffffff",
                             font=ctk.CTkFont(size=8, weight="bold")).pack(side="right", padx=1)

    def _escolher(self, p):
        self.sel = p
        c = self.c
        for w in self.dir.winfo_children():
            w.destroy()

        # cabeçalho: sprite grande + nome
        topo = ctk.CTkFrame(self.dir, fg_color="transparent")
        topo.pack(fill="x", padx=20, pady=(16, 12))
        sp = self._sprite(p["nome"], 72)
        if sp:
            moldura = ctk.CTkFrame(topo, corner_radius=8, fg_color=c["cartao_alt"])
            moldura.pack(side="left", padx=(0, 14))
            ctk.CTkLabel(moldura, image=sp, text="").pack(padx=8, pady=8)
        nomes = ctk.CTkFrame(topo, fg_color="transparent")
        nomes.pack(side="left", fill="both", expand=True)
        ctk.CTkLabel(nomes, text=p["nome"], font=ctk.CTkFont(size=24, weight="bold"),
                     anchor="w").pack(fill="x", pady=(8, 0))
        ctk.CTkLabel(nomes, text=self._txt(p, "grupo"), font=ctk.CTkFont(size=11),
                     text_color=c["fraca"], anchor="w").pack(fill="x")
        # selos das estações também no detalhe
        selos = ctk.CTkFrame(nomes, fg_color="transparent")
        selos.pack(fill="x", pady=(6, 0))
        for e in ORDEM_ESTACOES:
            if e in p.get("estacoes", []):
                ctk.CTkLabel(selos, text=f" {t(e)} ", height=20, corner_radius=5,
                             fg_color=COR_ESTACAO[e], text_color="#ffffff",
                             font=ctk.CTkFont(size=10, weight="bold")).pack(side="left", padx=2)

        for rotulo, valor in [(t("wiki_onde"), self._txt(p, "local")),
                              (t("wiki_estacao"), self._txt(p, "estacao")),
                              (t("wiki_horario"), self._txt(p, "tempo")),
                              (t("wiki_clima"), self._txt(p, "clima"))]:
            f = ctk.CTkFrame(self.dir, fg_color="transparent")
            f.pack(fill="x", padx=20, pady=3)
            ctk.CTkLabel(f, text=rotulo, width=70, anchor="w", text_color=c["fraca"],
                         font=ctk.CTkFont(size=11)).pack(side="left")
            ctk.CTkLabel(f, text=valor, anchor="w", justify="left", wraplength=380,
                         font=ctk.CTkFont(size=12)).pack(side="left", fill="x", expand=True)

        # ----- o que isso significa PRO BOT -----
        ctk.CTkFrame(self.dir, height=1, fg_color=c["borda"]).pack(fill="x", padx=20, pady=14)
        ctk.CTkLabel(self.dir, text=t("wiki_para_bot"),
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=c["fraca"], anchor="w").pack(fill="x", padx=20)

        f = ctk.CTkFrame(self.dir, fg_color="transparent")
        f.pack(fill="x", padx=20, pady=(8, 0))
        ctk.CTkLabel(f, text=f"  {t('wiki_dificuldade', d=p['dificuldade'])}  ",
                     height=26, corner_radius=6,
                     fg_color=cor_dificuldade(p["dificuldade"]), text_color="#ffffff",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")
        ctk.CTkLabel(f, text=f"  {p['movimento']}  ", height=26, corner_radius=6,
                     fg_color=COR_MOV.get(p["movimento"], "#4a5568"), text_color="#ffffff",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=8)
        ctk.CTkLabel(f, text=f"{p['xp']} XP", text_color=c["fraca"],
                     font=ctk.CTkFont(size=11)).pack(side="left", padx=6)

        ctk.CTkLabel(self.dir, text=t(f"mov_{p['movimento']}"), anchor="w",
                     text_color=c["fraca"], font=ctk.CTkFont(size=11),
                     wraplength=440, justify="left").pack(fill="x", padx=20, pady=(8, 0))

        # ----- seu histórico com esse peixe -----
        meus = [r for r in self.stats if r.get("peixe", "").lower() == p["nome"].lower()]
        ctk.CTkFrame(self.dir, height=1, fg_color=c["borda"]).pack(fill="x", padx=20, pady=14)
        ctk.CTkLabel(self.dir, text=t("wiki_historico"),
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=c["fraca"], anchor="w").pack(fill="x", padx=20)
        if not meus:
            ctk.CTkLabel(self.dir, text=t("wiki_sem_hist"), anchor="w",
                         text_color=c["fraca"], font=ctk.CTkFont(size=11)).pack(
                             fill="x", padx=20, pady=(8, 0))
        else:
            marcados = [r for r in meus if r.get("sucesso") is not None]
            ok = sum(1 for r in marcados if r["sucesso"])
            ctrl = sum(r["controle"] for r in meus) / len(meus)
            taxa = f"{ok/len(marcados)*100:.0f}%" if marcados else "—"
            ctk.CTkLabel(self.dir, text=t("wiki_hist", n=len(meus), taxa=taxa,
                                          ctrl=f"{ctrl*100:.0f}"),
                         anchor="w", font=ctk.CTkFont(size=12)).pack(
                             fill="x", padx=20, pady=(8, 0))
