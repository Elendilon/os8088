# BZROLL=1 (Makefile; wave 11, story 11.16): the pathway with FIRST ROLL, the shipped course 1 in the making,
# in FIRST's place - applied to path.bbc at build time, so the knob's pathway is the shipped one with this line
# changed and nothing else (two lines and a route).  Pad 0 becomes ROLL (a new game rests on it: title, Play Game, Enter); ROLL has one
# finish, so its exit 0 goes to TRIAL as FIRST's did, and FIRST's icon stays on the pad.
s/^pad 0 FIRST  22 26$/pad 0 ROLL   22 26/
# ISLAND HOP (course 2, docs/plans/bonanza-courses/HOP.md) on pad 1 in TRIAL's place.  HOP has one finish, so
# its exit 0 takes TRIAL's exit-1 route, to PLAY, and TRIAL's exit-0 route to MILL goes: MILL is reached through
# PLAY (route 3 2), so every pad stays reachable
s/^pad 1 TRIAL  22 21$/pad 1 HOP    22 21/
/^route 1 2 exit 0 /d
s/^route 1 3 exit 1 /route 1 3 exit 0 /
