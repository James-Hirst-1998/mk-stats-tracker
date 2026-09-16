# Get set up

Mario Kart Wii in Dolphin, from your own disc, with your own Mii, and every
race tracked.

## What you need

- A Wii and an SD card.
- **Mario Kart Wii, PAL** — game ID `RMCP01`. The tracker reads memory
  addresses found on that disc. Other regions will not work.
- A Mac with **Dolphin**. Linux works too.
- **Python 3** for the tracker.

## The apps

| App | What it does |
| --- | --- |
| Homebrew Channel | Runs apps that are not from Nintendo |
| [CleanRip](https://oscwii.org/library/app/cleanrip) | Copies the disc to the SD card |
| [SaveGame Manager GX](https://oscwii.org/library/app/savegame_manager_gx) | Exports your Mii as a `.miigx` file |

## 1. Get the Homebrew Channel

Already see a Homebrew Channel on the Wii Menu? Skip to step 2.

1. Format the SD card as FAT32. On a Mac: **Disk Utility → Erase → MS-DOS
   (FAT)**.
2. On the Wii, **Wii Settings**: note the version in the top right, e.g.
   `4.3E`. Then **Internet → Console Information**: note the MAC address.
3. On the computer, go to [wilbrand.donut.eu.org](https://wilbrand.donut.eu.org/).
   Enter the MAC, version and region, leave **Bundle the HackMii Installer**
   ticked, and download the zip.
4. Copy the `private` folder and `boot.elf` from the zip to the root of the SD
   card. Put the card in the Wii's front slot.
5. On the Wii, open the **Wii Message Board** and the green letter with a bomb
   on it. Not there? Check yesterday and tomorrow.
6. In the HackMii Installer, wait for **Press 1 to continue**, then **Install
   the Homebrew Channel**. Install **BootMii** too if it offers; it backs up
   the Wii.
7. **Exit**. You are in the Homebrew Channel.

To add an app, unzip it into `apps/` on the SD card. CleanRip and SaveGame
Manager GX are both linked in the table above.

This works on Wii Menu 3.0 to 4.3. For a Wii mini, a Wii U, or no SD card, see
the [Wii hacks guide](https://wii.hacks.guide/get-started).

## 2. Rip the disc

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

## 3. Bring your Mii over

1. On the Wii: **Homebrew Channel → SaveGame Manager GX → Mii section**.
   Export your Mii to the SD card. You get a `.miigx` file.
2. In Dolphin: **Config → Wii**, tick **Automatically Sync with Folder**, and
   open the **SD Sync Folder**. Copy the `.miigx` file into it.
3. **File → Open** the `boot.dol` in SaveGame Manager GX's folder. Go to the
   Mii section, pick the `.miigx` file, **Install**.
4. Start Mario Kart Wii. Your Mii is on the character select.

Guides: [Wii hacks guide](https://wii.hacks.guide/) ·
[Dolphin ripping guide](https://dolphin-emu.org/docs/guides/ripping-games/) ·
[Dolphin Mii guide](https://wiki.dolphin-emu.org/forum/Mii%20Channel/embed)

## 4. Set Dolphin up for four players

Under **Config → Controllers**:

- **Wii Remote 1–4 → Real Wii Remote**, with **Continuous Scanning** ticked.
  Press the red sync button on each remote while Dolphin is scanning.
- **GameCube Port 1–4 → GameCube Adapter for Wii U**, for anyone on a
  GameCube pad.

Optional, only for going looking for new addresses: **Config → Interface →
Show Debugging UI** adds a Memory tab.

Everything else is left at Dolphin's defaults. The tracker reads the game's
memory from outside Dolphin, so it needs no other setting.

## 5. Install the tracker

In the tracker's folder:

```bash
python3 -m venv mk && mk/bin/pip install dolphin-memory-engine numpy zstandard
```

## 6. Track a night

Start Dolphin and load Mario Kart Wii first, then:

```bash
sudo mk/bin/python3 -m tools.track versus-night
```

- `sudo` because it reads another program's memory.
- Leave it running for the whole VS session. It spots each race starting and
  ending, and saves each one as it finishes.
- **ctrl-c** when you are done. The most you lose is the race in progress.
- Each night lands in `races/<date>-versus-night/`, about 119 kB a race.

## 7. See the stats

**Here:** open [Stats](#/stats), **Load races**, and pick that night's folder.
The files are read in your browser. Nothing is uploaded. No races yet? The
same page has an example night to look around.

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
