# Input Check

Input Check is a report on your keyboard and mouse, written for sending to
the os8088 project when either does not work the way it should: a PS/2
keyboard that is sometimes not recognised, a mouse that is not found, or one
mouse that works where another does not. It shows what the system found at
start-up, checks the keyboard controller itself, and saves what it saw as
text files on the disk it was started from.

## Starting Input Check

Input Check comes on the input debug disk, in the `DEBUG` folder of the
release. Boot that disk in drive **A:** and Input Check opens by itself as
soon as the machine has started. The disk's system is the same as on the
system disk; nothing on it is a special build. Its own page, `INPDEBUG.TXT`,
is at the top of the disk. The other debug disks carry it in their `APPS`
folder, to start by hand.

## What happens when it starts

1. It asks you to **press some keys** for about 20 seconds: letters, Num
   Lock, Caps Lock. If the keyboard does not work, leave it; the report
   says so.
2. It saves a first report, `INPUT01A.TXT` (the next free number on a later
   boot), before anything touches the keyboard controller.
3. It checks the keyboard controller - the keyboard switches off for about a
   third of a second - and, when no PS/2 mouse was found at start-up, tries
   the PS/2 mouse port again.
4. It asks for keys again for about 10 seconds, then saves `INPUT01B.TXT`
   beside the first, and the window says **Done**.

Q and Esc do nothing while it runs, so pressing keys cannot close it.

## What to send

Boot the disk several times, ideally until you have one boot where the
keyboard works and one where it does not. Each boot saves its own pair of
files. Copy every `INPUT*.TXT` off the disk on any PC and send them, with
which mouse was plugged in where and whether the keyboard worked on each
boot.

## Keys

After the automatic run:

| Key | What it does |
|---|---|
| K | check the keyboard controller again |
| P | probe the PS/2 mouse port |
| R | refresh |
| S | save a report, anywhere you choose |
| C | copy the report to the clipboard |
| Q | close Input Check |

## Good to know

- If the keyboard is dead on a boot, a serial mouse still works the window
  after the run: Save Report writes another copy.
- Started by hand, Input Check runs no automatic script and saves only when
  you ask.
