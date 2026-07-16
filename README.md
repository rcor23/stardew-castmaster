# Stardew CastMaster 🎣

An external fishing bot for Stardew Valley. It reads the screen with OpenCV and
drives the mouse from outside the game — no mods, no SMAPI, nothing injected
into the game.

*[Leia em português »](README.pt-BR.md)*

It runs the whole fishing loop on its own: **cast → wait for the bobber →
spot the `!` bite → hook → play the minigame → stow the fish → repeat.**

Measured on a real session: **92% average control** (the fish stayed inside the
green bar the whole time in 13 of 15 minigames), **94% hook rate**, and 17
successful casts against 1 failure.

---

## Install

```bash
pip install -r requirements.txt
python app.py
```

Requires Python 3.9+ on Windows (the beeps and the global hotkey are
Windows-specific; everything else is portable).

## Game setup — this part matters

- Run the game in **windowed mode** (not exclusive fullscreen);
- **Zoom 100%** and **UI scale 100%**;
- Don't move or resize the window after calibrating.

## Quick start

1. **Open the game** and stand next to the water where you want to fish;
2. Run `python app.py`;
3. Click **🎯 Calibrate** — a terminal opens and explains the rest:
   press ENTER, alt+tab back to the game, hook a fish, and it silently takes
   ~50 screenshots (a beep tells you when it starts and stops). Then pick the
   screenshot where the minigame is visible and drag a box around the **whole
   fishing track** — top to bottom, it's taller than it looks;
4. Turn on **Fish by itself**, put the mouse cursor over the game aimed at your
   fishing spot, and press **F8**.

That's it. Press **F8** again to stop.

## Fishing by itself

| Switch | What it does |
|---|---|
| **Control the mouse** | Off = the bot only *watches* and draws what it sees. Great for checking the detection before letting it play. |
| **Fish by itself** | The full loop: cast, hook, play, repeat. Off = you cast and hook, the bot only plays the minigame. |

**Use the F8 hotkey**, not the Start button. The bot clicks wherever the cursor
already is — it never moves the mouse. Pressing F8 from inside the game means
the cursor and focus are already in the right place, so it starts immediately.
(Starting from the button leaves focus on the bot window, so it waits 5 seconds
for you to click back into the game.) You can rebind the key with **change**.

**While it runs:** don't touch the mouse and don't walk the character. The `!`
region is pinned above your character's head, and the minigame track appears
near the bobber — moving either one blinds the bot. Also keep an eye on
**energy**: fishing drains stamina and the bot doesn't know that.

**Popups and jams:** popups that need a click (treasure chest, new fish, record
size) get dismissed automatically and it carries on. But if a cast fails 12
times in a row, something it can't solve is in the way — usually a **full
inventory** — so it **stops, sounds an alarm** (6 sharp beeps), and saves a
screenshot to `falha_arremesso.png` so you can see what blocked it.

**Kill switches:** F8, the Stop button, closing the window, or throwing the
**mouse into a screen corner** (pyautogui failsafe).

## Per-fish stats

Type the fish name in **Peixe atual**, let the bot play, then click **✔ Peguei**
(caught) or **✖ Escapou** (escaped) when the status asks. The table tracks, per
fish: attempts, success rate, average duration, and **control %** — the share of
the minigame the fish spent inside the green bar.

The bot measures duration and control on its own; the outcome is yours to mark,
because reading it off the screen would mean calibrating the progress meter too.
Success rate is computed **only over the ones you marked** — unmarked runs show
`—`, not `0%`. Saved to `estatisticas.json` and kept between sessions.

## How it works

Everything below was derived from measuring real captured frames, not guessed.

**Finding things by colour.** The bar and the fish sit in well-separated hue
bands, so plain HSV thresholds beat template matching (which failed exactly when
the fish left the bar — the crop had the bar's green baked into its background):

| | hue | note |
|---|---|---|
| player's bar | 40–70 | yellow-green, saturated |
| fish | 80–100 | cyan |
| track water | 110–125 | blue |

**Stitching the bar back together.** The fish's dark outline cuts diagonally
across the green bar, splitting it into two contours. Taking "the largest" made
the bar's centre jump by up to 114px — precisely when the fish was *inside* the
bar, the state we're aiming for. The bar's height gives it away: it's a constant
164px, but detection was reading a median of 113px, and **59% of frames came
back split**. A vertical morphological close fixes it (59% → 0%). This one
change took average control from 16% to 85%.

**Predictive control, not bang-bang.** The bar carries heavy inertia — measured
from the logs, it took 1.6s to stop falling even while held. Reacting only once
the fish crosses the bar is always too late: the bar sails past and then plunges.
So the bot aims at where the bar *will be*:

```
predicted = bar_y + velocity × lookahead     # lookahead ≈ 0.45s
```

**Telling the `!` from the cast meter.** Both are yellow and both appear above
the character's head. They separate by shape — the `!` is 5×20 px (h/w ≈ 4.0),
the cast power meter is ~50×25 (h/w ≈ 0.5). Validated across 296 frames: 6/6
real bites, zero false positives.

**Clicks have to be held.** Stardew samples the mouse button once per tick
(~16ms). `pydirectinput.click()` presses and releases in under 1ms and falls
*between* ticks — the game never sees it. Every click holds for 100ms (~6 ticks).
This was found by accident in a log: hooks kept failing, but the *cast* (which
holds the button 0.65s) hooked a fish by mistake.

**Closed-loop casting.** The bot holds the button and confirms the cast power
meter actually appeared before believing it cast. Blind-clicking to "dismiss a
popup" used to fire a weak cast when no popup was there, which jammed the cycle.

## Files

| File | Role |
|---|---|
| `app.py` | The GUI and the bot loop |
| `deteccao.py` | Finds the bar, the fish, the `!`, and the cast meter |
| `calibrar.py` | Locates the fishing track on *your* screen → `config.json` |
| `amostra.py` | Diagnostic: records full-screen frames while you fish |
| `imgio.py` | Unicode-safe image I/O (see below) |
| `bot.py` | Headless version, minigame only |

## Gotchas worth knowing

**OpenCV silently fails on non-ASCII paths.** On Windows, `cv2.imread` /
`cv2.imwrite` use ANSI paths, so any accented character in the path makes them
return `None` / `False` **without raising**. This project lives under
`Área de Trabalho`, which broke template loading and made the app claim it wasn't
calibrated when it was. `imgio.py` routes I/O through numpy instead.

**Tkinter is not thread-safe.** The hotkey callback runs on the keyboard
library's thread; calling `after()` from there raises *"main thread is not in
main loop"*. That thread only drops a request on a queue — the UI refresh acts on
it from the Tk thread.

**The track region is fixed.** Stardew draws the minigame near the bobber, so
casting from a different spot or with a very different power puts the track
somewhere else and the bot goes blind. Cast from the same place. Auto-locating
the track each time is the natural next step.

## Roadmap

- Auto-locate the minigame track instead of relying on a fixed region;
- Read the catch progress meter, so the bot knows whether it won without you
  marking it;
- Grab the treasure chest when it shows up (the second bar in the minigame);
- Detect the full-inventory dialog specifically, rather than inferring a jam
  from repeated cast failures.
