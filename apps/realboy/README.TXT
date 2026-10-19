REALBOY - a Game Boy for os8088
===============================

REALBOY.O88 runs original Game Boy (DMG) cartridges, in a window or full
screen. The CPU, the picture, the timers, the square channels on the
speaker, battery saves and the MBC3 clock are all here. Bring your own
games: no game ships with it, and the only ROM on this disk is our own demo.

ON THIS DISK
------------
REALBOY.O88 the program. The Game Boy's CPU core is inside it, and so is
            the recompiler that a 286 or later uses.
GBDEMO.GB   RealBoy's demo, written for an IBM PC 5150: a bouncing ball,
            a clock and a blip on every landing. It is ours, and it runs
            on a real Game Boy too.
README.TXT  this file (REALBOY.TXT when it came from The Wire).

Put your own .GB files anywhere and double-click one: .GB is RealBoy's
document, so the program opens with the game. Or open REALBOY.O88 and use
File > Open. A cartridge must be 32K to 256K (MBC1, MBC2, MBC3 or MBC5).

KEYS
----
Arrows      the D-pad
X           A
Z           B
Enter       Start
Space       Select
F1          the speed line
Esc         leave full screen

The speed line is the game's speed (100% is the Game Boy's own 59.7 frames
a second) and the frames drawn a second. They are separate on purpose: the
game keeps its speed first, and the picture gets what is left.

MENUS
-----
Machine > Reset          start the cartridge again
Machine > Pause          stop the clock
Machine > Full Screen    the game on the whole screen
Machine > Recompiler     on or off (286 or later)

Full screen is VGA's 320x200 at 1x, a Hercules card's page at 2x2, or
CGA's 320x200 in four colours.

SAVES
-----
A cartridge with a battery is saved when you close its window, to
SYSTEM\APPDATA\<game>.SAV on the game's own disk. It is read back the next
time the game opens. The file is the usual .SAV format, with VBA's clock
block for an MBC3, so it moves to and from other emulators. The MBC3 clock
counts while the game runs, and catches up when a save opens on the time
the save was put away.

WHAT TO EXPECT
--------------
On a 286 at 12MHz most games run near full speed, faster with the
recompiler. On a 4.77MHz 8088 a busy game runs slowly. GBDEMO.GB runs at
full speed there, drawing about four frames a second, because the demo was
written to need very little.

Sound is the louder of the two square channels, on the PC speaker. The
wave and noise channels are silent.
