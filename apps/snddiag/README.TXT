os8088 DIAGNOSTIC DISK
======================

This is a boot disk for finding out why something does not work on your
machine. It is not a system disk to use every day: the system disk has
the full set of programs.

Leave it in the drive and NOT write-protected. It boots straight into its
own check and saves the report to this disk as text files.

  SNDDEBUG.TXT  on the sound debug disk: what it does, what to send
  INPDEBUG.TXT  on the input debug disk: the same, for keyboard and mouse

The APPS folder holds every diagnostic, so whichever disk you have runs
all of them by hand:

  SNDDIAG.O88   Sound Debug: the sound card, step by step
  INPUTCHK.O88  Input Check: the keyboard and the mouse
  REDLINE.O88   the benchmark; its Inspect page lists the hardware
  NOTEPAD.O88   to read these files

The reports are ordinary text files on an ordinary FAT floppy: copy them
off on any PC and send them with your machine's name.
