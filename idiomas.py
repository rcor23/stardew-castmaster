# -*- coding: utf-8 -*-
"""Textos da interface em português e inglês.

Uso:
    from idiomas import t, set_idioma
    set_idioma("en")
    t("iniciar")      -> "Start"

Os dados dos peixes (local, estação, horário) vêm do peixes.json, que guarda
os dois idiomas em campos [pt, en] — ver wiki.py.
"""

IDIOMA = "pt"

TEXTOS = {
    # ---- cabeçalho / status ----
    "visao_bot": ("VISÃO DO BOT", "BOT'S VIEW"),
    "inicie_para_ver": ("inicie para ver", "start to see"),
    "legenda_cores": ("🟩 barra    🟥 peixe", "🟩 bar    🟥 fish"),
    "parado": ("parado", "stopped"),
    "esperando": ("esperando...", "waiting..."),
    "observando": ("observando", "watching"),
    "segurando": ("SEGURANDO", "HOLDING"),
    "soltando": ("soltando", "releasing"),
    "minigame": ("MINIGAME", "MINIGAME"),
    "arremessando": ("arremessando", "casting"),
    "esperando_boia": ("esperando a boia", "waiting for the bobber"),
    "esperando_mordida": ("esperando a mordida", "waiting for a bite"),
    "fisgou": ("fisgou!", "hooked!"),
    "guardando": ("guardando o peixe", "stowing the fish"),
    "pegou": ("PEGOU ✔", "CAUGHT ✔"),
    "escapou_status": ("ESCAPOU ✖", "ESCAPED ✖"),
    "marque": ("marque ✔/✖", "mark ✔/✖"),
    "clique_no_jogo": ("clique no JOGO! {s}s", "click the GAME! {s}s"),
    "travado": ("⚠ TRAVADO — inventário cheio? · veja falha_arremesso.png",
                "⚠ JAMMED — full inventory? · see falha_arremesso.png"),
    "abortado": ("ABORTADO (failsafe)", "ABORTED (failsafe)"),
    "calibrando": ("calibrando (siga o terminal)...", "calibrating (follow the terminal)..."),
    "calib_aberta": ("calibração já está aberta", "calibration already open"),
    "calibre_primeiro": ("⚠ calibre primeiro!", "⚠ calibrate first!"),
    "sem_regiao_mordida": ("⚠ sem região do '!' — auto indisponível",
                           "⚠ no '!' region — auto unavailable"),
    "nada_p_marcar": ("(nenhum minigame p/ marcar)", "(no minigame to mark)"),

    # ---- cartões / controles ----
    "controle": ("CONTROLE", "CONTROL"),
    "ajuste_fino": ("AJUSTE FINO", "FINE TUNING"),
    "iniciar": ("▶   Iniciar", "▶   Start"),
    "parar": ("⏸   Parar", "⏸   Stop"),
    "calibrar": ("⛶   Calibrar", "⛶   Calibrate"),
    "peixes_btn": ("≡   Peixes", "≡   Fish"),
    "sw_mouse": ("Controlar o mouse", "Control the mouse"),
    "sw_auto": ("Pescar sozinho (arremessa e fisga)", "Fish by itself (casts and hooks)"),
    "atalho": ("Atalho (funciona dentro do jogo)", "Hotkey (works inside the game)"),
    "trocar": ("trocar", "change"),
    "aperte_tecla": ("aperte uma tecla…", "press a key…"),
    "hotkey_indisp": ("(indisponível)", "(unavailable)"),
    "tecla_invalida": ("tecla inválida", "invalid key"),

    # ---- sliders ----
    "zona_morta": ("Zona morta", "Dead zone"),
    "zona_morta_ajuda": ("tolerância em volta do alvo", "tolerance around the target"),
    "antecipacao": ("Antecipação", "Lookahead"),
    "antecipacao_ajuda": ("mira onde a barra VAI estar — evita o efeito sanfona",
                          "aims where the bar WILL be — avoids the yo-yo effect"),
    "forca": ("Força do arremesso", "Cast power"),
    "forca_ajuda": ("100% arremessa na distância máxima: +1 nível na zona de pesca",
                    "100% casts at max distance: +1 level to the fishing zone"),

    # ---- tiles / estatísticas ----
    "minigames": ("minigames", "minigames"),
    "fps": ("fps", "fps"),
    "peixe_opcional": ("Peixe (opcional)", "Fish (optional)"),
    "so_se_souber": ("só se souber", "only if you know"),
    "peguei": ("✔  Peguei", "✔  Caught"),
    "escapou": ("✖  Escapou", "✖  Escaped"),
    "rodape": ("Marque ✔/✖ ao fim de cada peixe · Failsafe: mouse no canto aborta",
               "Mark ✔/✖ after each fish · Failsafe: mouse to a corner aborts"),
    "col_comportamento": ("COMPORTAMENTO", "BEHAVIOUR"),
    "col_jogos": ("JOGOS", "GAMES"),
    "col_sucesso": ("SUCESSO", "SUCCESS"),
    "col_tempo": ("TEMPO", "TIME"),
    "col_controle": ("CONTROLE", "CONTROL"),
    "total": ("TOTAL", "TOTAL"),
    "sem_dados": ("\n   Nenhum minigame registrado ainda.\n\n"
                  "   O bot classifica o peixe sozinho pelo movimento\n"
                  "   (calmo / médio / arisco) — não precisa digitar nada.\n",
                  "\n   No minigames recorded yet.\n\n"
                  "   The bot classifies the fish on its own by movement\n"
                  "   (calm / medium / skittish) — no typing needed.\n"),

    # ---- comportamento do peixe ----
    "calmo": ("calmo", "calm"),
    "medio": ("médio", "medium"),
    "arisco": ("arisco", "skittish"),

    # ---- wiki ----
    "wiki_titulo": ("Peixes do Stardew Valley", "Stardew Valley Fish"),
    "wiki_buscar": ("buscar peixe, local, estação…", "search fish, location, season…"),
    "wiki_todos": ("todos", "all"),
    "wiki_conta": ("{n} de {tot} peixes", "{n} of {tot} fish"),
    "wiki_nada": ("nada encontrado", "nothing found"),
    "wiki_onde": ("Onde", "Where"),
    "wiki_estacao": ("Estação", "Season"),
    "wiki_horario": ("Horário", "Time"),
    "wiki_clima": ("Clima", "Weather"),
    "wiki_para_bot": ("PARA O BOT", "FOR THE BOT"),
    "wiki_dificuldade": ("dificuldade {d}", "difficulty {d}"),
    "wiki_historico": ("SEU HISTÓRICO", "YOUR HISTORY"),
    "wiki_sem_hist": ("Você ainda não registrou nenhuma tentativa neste peixe.",
                      "You haven't recorded any attempt on this fish yet."),
    "wiki_hist": ("{n} tentativa(s)  ·  sucesso {taxa}  ·  controle médio {ctrl}%",
                  "{n} attempt(s)  ·  success {taxa}  ·  average control {ctrl}%"),

    # ---- movimentos ----
    "mov_smooth": ("Movimento suave e previsível. O mais fácil pro bot.",
                   "Smooth, predictable movement. The easiest for the bot."),
    "mov_mixed": ("Mistura de movimentos. Comportamento padrão.",
                  "Mixed movement. The default behaviour."),
    "mov_floater": ("Tende a ficar na parte de cima da trilha.",
                    "Tends to stay near the top of the track."),
    "mov_sinker": ("Tende a afundar para a parte de baixo.",
                   "Tends to sink towards the bottom."),
    "mov_dart": ("Arranca de repente. O mais difícil pro bot acompanhar.",
                 "Darts suddenly. The hardest for the bot to follow."),

    # ---- estações (nome curto p/ o selo) ----
    "spring": ("Primavera", "Spring"),
    "summer": ("Verão", "Summer"),
    "fall": ("Outono", "Fall"),
    "winter": ("Inverno", "Winter"),
    "spring_letra": ("P", "Sp"),
    "summer_letra": ("V", "Su"),
    "fall_letra": ("O", "Fa"),
    "winter_letra": ("I", "Wi"),
}


def set_idioma(codigo):
    global IDIOMA
    IDIOMA = "en" if codigo == "en" else "pt"


def t(chave, **fmt):
    """Texto na língua atual. Aceita formatação: t('wiki_conta', n=5, tot=61)."""
    par = TEXTOS.get(chave)
    if par is None:
        return chave
    txt = par[1] if IDIOMA == "en" else par[0]
    return txt.format(**fmt) if fmt else txt


def idx():
    """Índice do idioma nos campos [pt, en] do peixes.json."""
    return 1 if IDIOMA == "en" else 0
