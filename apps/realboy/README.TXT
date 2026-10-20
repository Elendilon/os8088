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
File > Open. A cartridge is 32K to 256K (MBC1, MBC2, MBC3 or MBC5), or up
to 8MB on a machine with extended memory: there the cartridge is kept above
1MB and its banks come down as the game switches to them. A 256K game on a
640K machine goes there too when that is what leaves room for the
recompiler.

KEYS
----
Arrows      the D-pad
X           A
Z           B
Enter       Start
Space       Select
F1          the speed line
F2          Machine > Interlace's next setting
F3          Machine > Recompiler's next setting
F4          Machine > Speed's next setting
Alt+Enter   full screen, and back
Esc         leave full screen

The speed line is the game's speed (100% is the Game Boy's own 59.7 frames
a second) and the frames drawn a second. They are separate on purpose: the
game keeps its speed first, and the picture gets what is left.

MENUS
-----
Machine > Reset          start the cartridge again
Machine > Pause          stop the clock
Machine > Full Screen    the game on the whole screen
Machine > Recompiler     On, Static, Off or Auto (286 or later).
                         On translates the game as it runs. Static
                         translates it before it runs, then never
                         again, so play never slows for it: play
                         with On and Profile on first, and what On
                         translated is kept beside the game as
                         NAME.RBP for Static to use. Auto times On
                         against Off when the game's code outgrows
                         the recompiler
Machine > Interlace      Off, On, Scrolling or Doubled: less to draw
                         when the picture moves. On draws half the
                         lines each time; Scrolling only while it
                         scrolls; Doubled while it scrolls draws the
                         even lines and repeats each one below it,
                         without the comb Scrolling leaves on a
                         moving edge (the status bar stays whole)
Machine > Speed          100%, 90%, 75%, 60% or 50% of the Game Boy's
                         speed, held steady: what the game does not
                         use goes to the picture. A game too slow for
                         its machine is smoother a little slower
Machine > Sound          On, At 100% only, or Off. A slowed game plays
                         its tune slower too; At 100% only is silent
                         below full speed
                         (Speed and Sound are kept for each game, in
                         SYSTEM\APPDATA on this program's own disk)
Machine > Log            a record a second, to a file
Machine > Profile        On keeps what the recompiler translated as
                         NAME.RBP beside the game, for Static. Off by
                         default; on by itself for a game that has a
                         NAME.RBP, and while Static is chosen
Machine > Cache          64K or 128K for the recompiler's code. 128K
                         stops a big game (Kirby's Dream Land) from
                         slowing while its code is translated again,
                         for 64K of memory. Kept for every game after

The log is written beside REALBOY.O88 when you turn it off or close the
window, under a new name each time: the game's first six letters and a
number (SUPER-00.LOG, SUPER-01.LOG, ...). It names the game and the machine,
then gives a line a second: the speed, the frames run and drawn, how long
the drawing took, and anything you did (Reset, Pause, Full Screen, the
Recompiler). It is what to send back after a test run.

Full screen is VGA's 320x200 at 1x, a Hercules card's page at 2x2, or
CGA's 320x200 in four colours.

SAVES
-----
A cartridge with a battery is saved when you close its window, to
<game>.SAV beside the game. It is read back the next time the game opens. The file is the usual .SAV format, with VBA's clock
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
