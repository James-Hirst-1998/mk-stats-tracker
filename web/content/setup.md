# Get set up

Mario Kart Wii in Dolphin, from your own disc, with your own Mii, and every
race tracked.

## What you need

- A Wii, and an SD card of 8 GB or more. The disc copy alone is 4.7 GB.
- **Mario Kart Wii, PAL** — game ID `RMCP01`. The tracker reads memory
  addresses found on that disc. Other regions will not work.
- A Mac with **Dolphin**. Linux works too.
- **Python 3** for the tracker.

## How the Wii part works

The SD card carries everything between the Mac and the Wii.

- **Homebrew Channel** is a channel on the Wii Menu that runs apps from the SD
  card. You install it once.
- **CleanRip** is an app that copies your disc onto the SD card.
- **SaveGame Manager GX** is an app that copies your Mii onto the SD card.

You download the two apps on the Mac and copy them to the SD card. The Homebrew
Channel then lists them on the Wii.

## 1. Install the Homebrew Channel

Already see a Homebrew Channel on the Wii Menu? Skip to step 2.

1. Put the SD card in the Mac and format it: **Disk Utility → Erase → MS-DOS
   (FAT)**. This wipes it.
2. On the Wii, **Wii Settings**: note the version in the top right, e.g.
   `4.3E`. Then **Internet → Console Information**: note the MAC address.
3. On the Mac, go to [wilbrand.donut.eu.org](https://wilbrand.donut.eu.org/).
   Enter the MAC, version and region, leave **Bundle the HackMii Installer**
   ticked, and download the zip.
4. Copy the `private` folder and `boot.elf` from the zip to the top level of
   the SD card. Put the card in the Wii's front slot.
5. On the Wii, open the **Wii Message Board** and the green letter with a bomb
   on it. Not there? Check yesterday and tomorrow.
6. In the HackMii Installer, wait for **Press 1 to continue**, then **Install
   the Homebrew Channel**. Install **BootMii** too if it offers; it backs up
   the Wii.
7. **Exit**. You are in the Homebrew Channel. It is empty until step 2.

This works on Wii Menu 3.0 to 4.3. For a Wii mini, a Wii U, or no SD card, see
the [Wii hacks guide](https://wii.hacks.guide/get-started).

## 2. Put the apps on the SD card

1. Turn the Wii off and put the SD card in the Mac.
2. Download both apps with the **Download** button on their pages:
   [CleanRip](https://oscwii.org/library/app/cleanrip) and
   [SaveGame Manager GX](https://oscwii.org/library/app/savegame_manager_gx).
3. Unzip each one. Inside is an `apps` folder. Copy it to the top level of the
   SD card, and merge if the Mac asks.
4. The SD card now has an `apps` folder with a folder for each app in it.
5. Put the card back in the Wii and open the **Homebrew Channel**. Both apps
   are listed.

## 3. Rip the disc

1. In the Homebrew Channel, open **CleanRip**.
2. Answer its questions: checksums **Yes**, device **SD**, filesystem **FAT**,
   download the redump.org files **Yes**. If it crashes there, restart the Wii
   and answer **No** instead.
3. Put Mario Kart Wii in the Wii. Datel disc: **No**. Set the dump settings
   as the [Wii hacks guide](https://wii.hacks.guide/dump-games) shows them, then
   press **A**.
4. Wait while it copies the whole 4.7 GB. At the end it shows an **MD5**
   checksum, and saves it in a text file next to the copy.
5. Turn the Wii off and put the SD card in the Mac. Copy the files ending
   `.part0.iso`, `.part1.iso` and so on into one folder. The card is FAT, which
   cannot hold a file that big, so CleanRip split it.
6. Open Terminal in that folder and join them:

   ```bash
   cat *.part?.iso > mario-kart-wii.iso
   ```

7. Check the copy. This should print the same MD5 CleanRip showed:

   ```bash
   md5 mario-kart-wii.iso
   ```

8. In Dolphin: **Config → Paths → Add** that folder. Right-click the game →
   **Properties → Info**. The game ID should read `RMCP01`.

## 4. Bring your Mii over

1. SD card back in the Wii. **Homebrew Channel → SaveGame Manager GX → Mii
   section**, and export your Mii. It saves a `.miigx` file to the SD card.
2. SD card back in the Mac. In Dolphin: **Config → Wii**, tick **Automatically
   Sync with Folder**, and open the **SD Sync Folder**. Copy the `.miigx` file
   into it. This folder is Dolphin's pretend SD card.
3. **File → Open**, and pick the `boot.dol` inside SaveGame Manager GX's folder
   in `apps` on the real SD card. Go to the Mii section, pick the `.miigx` file,
   **Install**.
4. Start Mario Kart Wii. Your Mii is on the character select.

Guides: [Wii hacks guide](https://wii.hacks.guide/) ·
[Dolphin ripping guide](https://dolphin-emu.org/docs/guides/ripping-games/) ·
[Dolphin Mii guide](https://wiki.dolphin-emu.org/forum/Mii%20Channel/embed)

## 5. Set Dolphin up for four players

Under **Config → Controllers**:

- **Wii Remote 1–4 → Real Wii Remote**, with **Continuous Scanning** ticked.
  Press the red sync button on each remote while Dolphin is scanning.
- **GameCube Port 1–4 → GameCube Adapter for Wii U**, for anyone on a
  GameCube pad.

Optional, only for going looking for new addresses: **Config → Interface →
Show Debugging UI** adds a Memory tab.

Everything else is left at Dolphin's defaults. The tracker reads the game's
memory from outside Dolphin, so it needs no other setting.

## 6. Install the tracker

In the tracker's folder:

```bash
python3 -m venv mk && mk/bin/pip install dolphin-memory-engine numpy zstandard
```

## 7. Track a night

Start Dolphin and load Mario Kart Wii first, then:

```bash
sudo mk/bin/python3 -m tools.track versus-night
```

- `sudo` because it reads another program's memory.
- Leave it running for the whole VS session. It spots each race starting and
  ending, and saves each one as it finishes.
- **ctrl-c** when you are done. The most you lose is the race in progress.
- Each night lands in `races/<date>-versus-night/`, about 119 kB a race.

## 8. See the stats

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
