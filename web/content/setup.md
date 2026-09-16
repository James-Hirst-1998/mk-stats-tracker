# Get set up

Mario Kart Wii in Dolphin, from your own disc, with your own Mii, and every
race tracked. About an hour, most of it waiting for the disc to copy.

## What you need

- A Wii with the **Homebrew Channel**, and an SD card.
- **Mario Kart Wii, PAL** — game ID `RMCP01`. The tracker reads memory
  addresses found on that disc. Other regions will not work.
- A Mac with **Dolphin**. Linux works too.
- **Python 3** for the tracker.

## The apps

| App | What it does |
| --- | --- |
| Homebrew Channel | Launches the other two on the Wii |
| CleanRip | Copies the disc to the SD card |
| SaveGame Manager GX | Exports your Mii as a `.miigx` file |

## 1. Rip the disc

1. On the Wii: **Homebrew Channel → CleanRip**.
2. Choose **SD** and dump the disc.
3. Copy the ISO parts onto the Mac and join them into one file, in order.
   Use the part names CleanRip gave them:

   ```bash
   cat part0.iso part1.iso > mario-kart-wii.iso
   ```

4. In Dolphin: **Config → Paths → Add** the folder with the ISO in it.
5. Right-click the game → **Properties → Info**. The game ID should read
   `RMCP01`.

## 2. Bring your Mii over

1. On the Wii: **Homebrew Channel → SaveGame Manager GX → Mii section**.
   Export your Mii to the SD card. You get a `.miigx` file.
2. Put that file on Dolphin's virtual SD card. **Config → Wii → SD Card
   Settings** shows where it lives.
3. In Dolphin: **File → Open** SaveGame Manager GX's `boot.dol`. Go to the Mii
   section, pick the `.miigx` file, **Install**.
4. Start Mario Kart Wii. Your Mii is on the character select.

Guides: [Dolphin ripping guide](https://dolphin-emu.org/docs/guides/ripping-games/) ·
[Dolphin Mii guide](https://wiki.dolphin-emu.org/forum/Mii%20Channel/embed)

## 3. Set Dolphin up for four players

Under **Config → Controllers**:

- **Wii Remote 1–4 → Real Wii Remote**, with **Continuous Scanning** ticked.
  Press the red sync button on each remote while Dolphin is scanning.
- **GameCube Port 1–4 → GameCube Adapter for Wii U**, for anyone on a
  GameCube pad.

Optional, only for going looking for new addresses: **Config → Interface →
Show Debugging UI** adds a Memory tab.

Everything else is left at Dolphin's defaults. The tracker reads the game's
memory from outside Dolphin, so it needs no other setting.

## 4. Install the tracker

In the tracker's folder:

```bash
python3 -m venv mk && mk/bin/pip install dolphin-memory-engine numpy zstandard
```

## 5. Track a night

Start Dolphin and load Mario Kart Wii first, then:

```bash
sudo mk/bin/python3 -m tools.track versus-night
```

- `sudo` because it reads another program's memory.
- Leave it running for the whole VS session. It spots each race starting and
  ending, and saves each one as it finishes.
- **ctrl-c** when you are done. The most you lose is the race in progress.
- Each night lands in `races/<date>-versus-night/`, about 119 kB a race.

## 6. See the stats

**Here:** open [Stats](#/stats), **Load races**, and pick that night's folder.
The files are read in your browser. Nothing is uploaded.

**On your own machine, live while you play:**

```bash
npm --prefix web install
```

```bash
npm --prefix web run dev
```

Then open `http://localhost:8125`. It updates as each race finishes.

Either way, **Who is who** puts people's names against the characters, so the
page can say who actually threw that shell.
