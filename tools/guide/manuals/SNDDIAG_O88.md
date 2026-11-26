# Sound Debug

Sound Debug is a report on your sound card, written for sending to the
os8088 project when sound does not work the way it should. It shows where
the sound driver found each card, what it learned about them, what happens
when it plays a tone for ten seconds, and what the card and its DMA channel
do when they are driven sixteen different ways. It saves all of it as text
files on the disk it was started from, ready to send.

## Starting Sound Debug

Sound Debug comes on the sound debug disk, in the `DEBUG` folder of the
release. Boot that disk in drive **A:** and Sound Debug opens by itself as
soon as the machine has started, runs every test and saves its report. It
needs nothing else: the disk switches the sound driver on even when the
machine would not have done so on its own. Its own page, `SNDDEBUG.TXT`, is
at the top of the disk.

The detail comes from the sound driver on that disk. Started from another
disk, Sound Debug says the driver is not the debug one and shows only what
any sound driver reports.

## What to send

1. Leave the disk in the drive, not write-protected, boot it, and wait about
   a minute and a half. Two seconds after Sound Debug opens it plays a tone
   for ten seconds, then runs the DMA lab, whose sixteen runs each play the
   tone for about two and a half seconds.
2. Listen. Note whether the ten-second tone played all the way through, and
   which lab runs (the number shows at the top right of page 4) played their
   whole time and which went quiet early.
3. When page 4 says **Done.**, the report is on the disk: `SOUNDA1.TXT`,
   saved after the tone, and `SOUNDB1.TXT`, saved after the lab. Each boot
   saves the next number, so nothing is overwritten.
4. Copy the `SOUND*.TXT` files off the disk on any PC and send them, with
   what you heard and the name of your card.

## The pages

| Page | Key | What it shows |
|---|---|---|
| Detect | 1 | the processor and display, whether the sound driver is loaded, what it can play, where the Sound Blaster answered and its version, how its interrupt was found, whether the DMA controller can repeat a transfer by itself (`auto`), the mixer, an ESS chip's own name, the FM chip, MIDI port, Covox and PicoMEM, a `BLASTER=` line, and a one-line verdict |
| Play | 2 | the tone, one line a second: the bytes the card played, its interrupts, whether the card's own output switch is on (`D8h`: `FF` on, `00` off), the mixer settings that can silence it, the DMA controller's count, and the playback state, then a verdict naming the first thing that stopped |
| Regs | 3 | the mixer's registers, the last commands sent to the card, and the playback and interrupt-controller state |
| Lab | 4 | the first thirteen lab runs, a line each: what the run changed, its interrupts, the bytes the DMA controller moved, and whether it **ran** or **FROZE** (and where, and when) |
| More | 5 | the other three runs, where the lab's buffers sat in memory, an ESS chip's control registers, the DMA controller after the tone, which runs played on and which froze, and the report files |

## Keys

| Key | What it does |
|---|---|
| 1 to 5 | show that page |
| P | play the tone again |
| A | play the tone, then run the lab |
| L | run the lab alone |
| S | save a report now, as `SOUNDS1.TXT` (the next free number) |
| R | change the tone's rate: 22,050, 11,025, 8,000 or 44,100 Hz |
| V | stop or start reading the card's output switch during the tone |
| Esc | close Sound Debug |

While a test is playing, only **V** and the page keys do anything.

## Good to know

- `na` in the `D8h` column means the card did not answer that question;
  some cards never do. `--` means it was not asked.
- `auto no (8237 no wrap)` on page 1 means the machine's DMA controller
  cannot repeat a transfer by itself, so the sound driver plays one block at
  a time instead. Sound works; rates above 22,050 Hz, stereo and recording
  are not offered on that machine.
- On a card that cannot do it (no high-speed mode, not an ESS chip), a lab
  run says **skipped**.
- 44,100 Hz needs a Sound Blaster Pro, an SB16 or a compatible; on another
  card the tone test says it was refused.
- The 360KB disk has room for one boot's two reports.
