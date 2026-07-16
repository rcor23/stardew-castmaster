# Stardew CastMaster 🎣

Bot de pesca externo para Stardew Valley — lê a tela com OpenCV e controla o mouse por fora do jogo.

## Instalação

```
pip install -r requirements.txt
```

## Configuração do jogo (importante!)

- Jogo em **modo janela** (não fullscreen exclusivo);
- **Zoom 100%** e **escala de UI 100%** nas opções;
- Não mova nem redimensione a janela depois de calibrar (senão recalibre).

## Interface gráfica (jeito recomendado)

```
python app.py
```

Janela com botão **Calibrar**, **Iniciar/Parar**, preview ao vivo da visão do bot,
switch "Controlar o mouse" (desligado = só observa, ótimo pra testar a detecção),
sliders de ajuste fino e contador de minigames.

### Registro estatístico

Na parte de baixo da janela há uma tabela de desempenho **por peixe**:

1. Digite o nome do peixe que está testando no campo **"Peixe atual"** (ex.: `Peixe-gato`);
2. Deixe o bot jogar o minigame;
3. Ao terminar, o status mostra **"marque ✓/✗"** — clique **✓ Peguei** ou **✗ Escapou**.

A tabela acumula, por peixe: nº de tentativas, **taxa de sucesso**, **tempo médio** e
**controle %** (quanto do tempo o peixe ficou dentro da barra — medido automaticamente
pelo bot). Assim você vê em quais tipos de peixe o bot vai bem e em quais precisa ajustar
a zona morta / limiar. Tudo é salvo em `estatisticas.json` e persiste entre sessões.
O botão **🗑 Limpar** zera o registro.

> O bot mede sozinho a duração e o controle; o resultado (peguei/escapou) é você quem
> marca, porque detectar isso na tela exigiria calibrar a barrinha de progresso — fica pra v2.

## Passo a passo (scripts avulsos, alternativa à interface)

| Etapa | Comando | O que faz | Como saber que passou |
|---|---|---|---|
| 1. Calibrar | `python calibrar.py` | Marca a região da barra e recorta o ícone do peixe | Gera `config.json` e `peixe.png` |
| 2. Detectar | `python deteccao.py` | Só observa — desenha retângulos no que ele vê | Pescando manualmente, os retângulos seguem a barra (verde) e o peixe (vermelho) sem falhar |
| 3. Bot | `python bot.py` | Joga o minigame sozinho (você joga a vara e fisga) | Ele vence o minigame consistentemente |

## Kill switches (parar o bot)

- Aperte **Q** na janela de debug;
- Jogue o **mouse num canto da tela** (failsafe do pyautogui).

## Dicas de teste

- Comece com a **Vara de Treino** (Willy vende) — os peixes são lentos e fáceis;
- Teste no lago da fazenda ou no oceano da praia;
- Anote a taxa de sucesso: peixes capturados ÷ minigames jogados;
- Depois teste com peixes difíceis (rio na chuva, mineração) e ajuste `ZONA_MORTA` em `bot.py`;
- Se o peixe "sumir" da detecção, diminua `LIMIAR_PEIXE` em `deteccao.py` (ex.: 0.45).

## Próximos passos (v2)

- Arremesso e fisgada automáticos (detectar o balão de "!" na tela);
- Loop completo: pescar -> capturar -> arremessar de novo;
- Pegar o baú de tesouro quando aparecer (segunda barra no minigame);
- Trocar o controle liga/desliga por um controle PID (movimento mais suave).
