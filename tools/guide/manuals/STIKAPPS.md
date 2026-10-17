# Sticky Apps

`STIKAPPS` holds the Sticky Apps: small programs that belong to the desktop
itself rather than to a window. A Sticky App sits on the desktop under every
window, stays where you put it, and comes back by itself every time the
machine starts, until you close it. The Desk Calendar is the Sticky App that
comes with os8088.

![The Sticky Apps menu on a fresh start, with the Desk Calendar ready to add.](shot:stikapps-menu)

## Where it is

The folder is at the top level of the system disk, in every size, and on the
emulator system disk and the live USB image and CD. It holds
`DESKCAL.O88`, the Desk Calendar. Sticky Apps always come from the disk the
machine started from, so no software disk carries this folder.

## Using Sticky Apps

The menu bar has a **Sticky Apps** menu beside **File** when no window is
in front, and after **Disk** when a Disk window is in front. It lists every Sticky App found in this folder, with its picture, its
name and a line about what it does.

- Click **Add** beside one to start it. You can also double-click its file
  in the folder.
- A running one is ticked and marked **On**. Pick it again to close it.
- **Arrange Sticky Apps...** lines the open ones up down the right of the
  screen. **Hide All Sticky Apps** hides them without closing them, and the
  same item then reads **Show All Sticky Apps**.
- **More Sticky Apps...** opens The Wire, the online software library.

Drag a Sticky App by its name tag to move it. It remembers the spot.

## Coming back at every start

While a Sticky App is open, the desktop remembers it. At the next start the
system opens it again, from the same place, after the desktop appears.
Restarting the machine does not close it. Only closing it yourself, with
the close box on its name tag or from the menu, stops it coming back.

If a remembered Sticky App cannot be found at the next start, for instance
because its file was deleted or it was started from a disk that is not in
the drive, the desktop says `Shortcut not found (A:)` and leaves an icon in
its place. Double-click the icon to try again, or delete it.

## Good to know

- Only programs made as Sticky Apps work this way. An ordinary program
  copied into this folder does not appear in the menu, and runs as an
  ordinary window.
- A Sticky App saves its own state, such as the calendar's appointments, in
  `SYSTEM/APPDATA` on the system disk, so keep that disk writable.
- Leave `DESKCAL.O88` here. Moved somewhere else, it is no longer listed in
  the Sticky Apps menu.
