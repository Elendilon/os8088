# WireArena over a null modem: plan

Two machines, one arena, a serial cable. This is wave 4 of
[MULTIPLAYER-FPS-PLAN.md](MULTIPLAYER-FPS-PLAN.md) section 15 ("the serial
link, with the owner-authority model"), and its section 8.1 and 8.3 are
where the model was first proposed. What is written here is the contract;
section 9 records what was built against it, wave by wave.

## 0. The owner's rulings (2026-11-14)

- **Wave L1 is players only**: two people, no bots. **Wave L2 follows at
  once**: bots owned by one machine (the host). A link match holds at most
  **four participants: two players and two bots**.
- **A lobby screen**, in the window, before the match. It is where match
  setup grows later (modes, Capture the Flag).
- **Keyboard aim is fine** on a machine whose only serial port has the
  mouse on it (the arrows turn and pitch). Better keyboard aiming, or the
  PicoMEM's mouse, is separate work on the roadmap.

## 1. What the OS already gives

- **The serial lease, SPEC.md 115.** `OSAPI_SERIAL` Open/Close/Read/Write,
  the kernel's IRQ3/IRQ4 service feeding two 255-byte rings in the
  package's own pinned region. 2400 baud is divisor 48. The lease survives
  §53 entry, and **Read and Write on a lease opened before entry are legal
  inside the bracket** (§53.7). Open and Close are not on that list, so
  **the port is found and opened in the window, never in the arena**.
- **The mouse is refused for us**: the lease never hands out the winning
  mouse's port (refusal 3), and before the contest settles it decides per
  port (115.1.1).
- **WireFleet's automatic link, SPEC.md 114.9**: both ports searched, the
  lease MOVED between them after a dwell of 40 to 71 ticks drawn afresh, the
  first valid frame from another identity ends the search. Its refusal
  lines say what the user can do about each refusal.
- **WireFleet's framing, SPEC.md 114.6**: 7Eh delimiters, 7Dh escapes (byte
  XOR 20h), CRC-16/CCITT-FALSE. Frames that fail are dropped whole and the
  framer resynchronizes at the next delimiter.
- **Why 2400**: an original 8250 holds one received byte; two 86Box XTs at
  9600 lost ~9% of bytes (SPEC.md 114.3). At 2400 a byte is 4.17 ms.
- **What is missing: a shared link include.** WireFleet's search, framer
  and CRC are `wf_`-prefixed inside `apps/wirefleet/wflink.inc`, written
  around its 64-byte frame. They are written once more here as
  `apps/os88link.inc` (`lk_` prefix): the search, a framer for frames of
  any length up to 32 bytes, and the CRC. WireArena is its first user.
  Moving WireFleet onto it is story L3.1, so the copy does not stay two.

## 2. The budget: 240 bytes a second each way

2400 baud 8N1 is 240 bytes a second, each way. Each frame costs its body,
two CRC bytes and two delimiters; escapes are rare (a 7Dh or 7Eh in a
coordinate).

| traffic | bytes framed | rate | bytes/s |
|---|---|---|---|
| SNAP: my player | 17 | 10 Hz (every 3rd sim tick) | 170 |
| SCORE: my deaths, and how many by you | 8 | 1 Hz | 8 |
| EVENT: a projectile fired, a pickup taken or rolled | 16 | a few a second at most | ~30 |
| total, in a match | | | ~210 of 240 |

**Hits cost no frames.** The shooter judges a hit on its own view of the
other player (MULTIPLAYER-FPS-PLAN 8.1: "the target you saw is the target
you hit"). It adds the damage to a **cumulative damage word** carried in
every SNAP. The victim applies the difference from the last word it saw. A
lost SNAP loses nothing; the next one carries the total. A chaingun's seven
rounds a second would otherwise be seven frames.

**L2's bots must fit in the ~30 left.** The host decides each bot's moves;
the guest walks the bot along the same route graph itself and is only told
the decisions (a new edge, a target, a shot). Section 8 sizes it. If it does
not fit, SNAP drops to 7.5 Hz while bots are on (every 4th tick: 128
bytes/s, leaving ~80).

## 3. Who owns what

- **Each machine owns its own player**: its position, its health, its
  death and respawn. It is simulated locally with no input delay.
- **The shooter judges its hitscan hits** and sends the damage
  (cumulative). The victim applies it, dies on its own machine, and its
  SNAP says so.
- **Projectiles**: the shooter sends FIRE (kind, place, angle, pitch). Both
  machines fly it. **The victim's machine judges a projectile's hit and
  splash on its own player**; the shooter's machine shows the explosion and
  judges nothing.
- **Kills are counted by the victim**: SCORE carries "my deaths" and "my
  deaths by you". So each machine's YOU and OPPONENT rows agree once a
  SCORE has crossed.
- **Pickups**: whoever takes one sends TAKE(i). Two machines taking the same
  one inside a frame's latency both get it, which is accepted. **The host
  rolls a weapon spawn's kind** and sends ROLL(i, kind). A guest's spawn
  that comes back waits for the host's roll.
- **The host is the lower identity**, WireFleet's rule (114.6): no
  election. In L1 the host chooses the arena and the difficulty; in L2 it
  also owns the bots.

## 4. Protocol v1

Every frame is 7Eh, the escaped body, 7Eh. A body's last two bytes are
CRC-16/CCITT-FALSE (initial FFFFh, polynomial 1021h) over the bytes before
them. **Byte 0 is the type, and each type has exactly one length**: a frame
of another length, or of an unknown type, is dropped before its CRC is
checked. Words are little-endian.

### 4.1 In the lobby

**HELLO** (type 1, 20 bytes), every 9 ticks while the window is open and
the port is leased:

| byte | meaning |
|---|---|
| 0 | 1 |
| 1, 2 | `WA` |
| 3 | protocol version, 1 |
| 4..7 | my identity (random, nonzero; lower is the host) |
| 8..11 | the peer I have bound, or 0 |
| 12 | my state: 0 in the lobby, 1 ready, 2 in the match |
| 13 | the arena (the host's choice; a guest echoes the host's) |
| 14 | the difficulty (host's), 15 the bots (L2: 0..2, host's) |
| 16 | the match tag (host's, nonzero once START is sent) |
| 17 | 0 (reserved) |
| 18, 19 | CRC |

- A HELLO from another identity on our port ends the search (114.9's rule).
- The first such identity is **bound**. While bound, a HELLO from a third
  identity is ignored. One whose bound peer has said "0" for us for 55
  ticks is unbound (the other machine restarted WireArena).
- **START**: once both are ready, the host draws a nonzero match tag and
  sends it in byte 16. A guest that sees its own state "ready" and the host
  ready with a tag sets state 2 and enters the arena. The host enters when
  the guest's HELLO says 2 with the same tag. Both enter within a HELLO
  period of each other.
- **Equal identities** (two machines drew the same) are redrawn, as
  WireFleet does.

### 4.2 In the match

Every in-match frame carries the match tag at byte 1. A frame with another
tag is dropped. That is what keeps a stale peer's frames, after a rematch,
out of the new match.

**SNAP** (type 2, 15 bytes), every 3rd sim tick (10 Hz):

| byte | meaning |
|---|---|
| 0, 1 | 2, the tag |
| 2, 3 | x (`wa_px`) |
| 4, 5 | y (`wa_py`) |
| 6 | feet height / 2 (`wa_feet` + jump, 0..510) |
| 7 | yaw, `wa_ang`'s high byte (256 to the turn) |
| 8 | pitch, -128..127 |
| 9 | flags: bit 0 alive, 1 firing, 2 shielded, 3..5 the weapon held, 6..7 the last hit's kill kind (0 pistol fall, 1 shotgun collapse, 2 bits) |
| 10, 11 | cumulative damage dealt TO the receiver, mod 65536 |
| 12 | the last EVENT sequence applied from the receiver |
| 13, 14 | CRC |

**SCORE** (type 3, 6 bytes), once a second: tag, my deaths, my deaths by
you, then CRC.

**EVENT** (type 4, 14 bytes): tag, sequence (1..255, then 1 again), kind,
eight bytes of payload, CRC.

- **FIRE** (kind 1): projectile kind (grenade 1, rocket 2), x, y (words), z
  / 2, yaw, pitch.
- **TAKE** (kind 2): pickup index.
- **ROLL** (kind 3, from the host): pickup index, kind.
- **LEAVE** (kind 4): I am back in the lobby.

An event is resent every 9 ticks until the receiver's SNAP byte 12 reaches
its sequence. A receiver applies only the sequence one past the last it
applied, so a resend that crosses its ack is not applied twice. Up to 8
events wait, and a ninth waits for room.

### 4.3 Silence

- **55 ticks (1.8 s) without a valid frame** in the match: "LINK LOST" in
  the overlay. The other player stands where last seen, drawn as a still
  figure, and nothing hits them. Frames resuming clear it.
- **LEAVE**, or a HELLO with state 0 or 1 from the peer: "OPPONENT LEFT".
  The figure is gone. The match goes on alone until Esc.
- In the lobby, a peer silent for 55 ticks is shown as gone. It stays bound
  until another identity is heard (114.9's turn-0 rebind).

## 5. The lobby

The window's content becomes the lobby whenever the port is leased; with
no link it shows the help text as now.

```
  WireArena  -  linked on COM2
  You          ready       (host)
  RIVET-4F2A   not ready
  Arena: Heights    Bots: normal
  Link > Ready when you are.
```

- **Link menu**: *Automatic* (the default: the search starts when the
  window opens, as WireFleet's does), *Connect COM1*, *Connect COM2*,
  *Disconnect*, and *Ready* (a toggle). Space or Enter in the window also
  toggles Ready.
- **The host's Game menu chooses** the arena and the bots' difficulty while
  linked. Its Play items no longer start a game; they set the arena, and
  the lobby says so. A guest's arena items are greyed with the reason (§47:
  "The host chooses the arena").
- **The width** (40 or 80) stays each player's own. A machine plays the
  width it picked last.
- **The opponent's name** is a robot name from the bots' list plus four hex
  digits of its identity, so two machines' names differ. Entering names is
  later work.
- The lobby redraws only the lines that changed (PERFORMANCE.md rule 1).
  `font_run` draws them (CLAUDE.md: text is `font_run`).

## 6. In the arena

- **The other player is figure 0.** The bots are off in L1: figures 1 and 2
  are parked dead, as the tests park them. The renderer draws figure 0 as
  it draws any figure, so this costs the renderer nothing.
- **Interpolation**: each sim tick, the figure moves a third of the way
  from where it is drawn toward the last SNAP's position, and turns the
  same way. A SNAP every three ticks then lands about when the last one is
  reached. The run animation plays while it moves, the idle animation while
  it stands.
- **Firing**: the firing flag lights the figure's yellow cue (AI-PLAN 4.3,
  `F_FLASH` 86h), so the other player's shots are visible as the bots' are.
- **Its weapon** is not drawn (no figure holds one yet). Its shield flag
  makes its chest yellow, as a shielded bot's is (WEAPONS-PLAN 2.3).
- **Death**: the alive flag falling starts the death animation of the kill
  kind in bits 6..7. The figure lies for 3 s (8.5's rule) and is gone until
  the alive flag rises, at the other player's respawn point.
- **My hit on figure 0** shows the flinch at once (my feedback) but changes
  no health here. The damage goes on the wire.
- **The scoreboard** (Tab) lists YOU and the opponent's name.
- **Esc** sends LEAVE (until acked, up to a second) and returns to the
  window, where the lobby still holds the link.

## 7. Cost

- **The link's work in a frame**: drain the RX ring (at 10 fps about 21
  bytes a frame), queue at most one or two frames' bytes into the TX ring,
  and advance the framer. Each byte is one `OSAPI_SERIAL` far call, about
  47 us of call plus the module's bounded service: ~40 calls a frame, a
  few ms on a 4.77 MHz 8088. **L1 measures it on MartyPC** with the lease
  open and the module serving a port with nothing on the cable. The bytes
  a peer would send are counted from the code (QEMU counts work exactly).
- **The renderer pays nothing new**: figure 0 is a figure.
- **Bytes**: the include and the match code in the game half; the lobby
  text and the menus. Recorded per wave against the byte, not the rung.

## 8. L2: the host's bots

- **Two bots**, figures 1 and 2. They are the host's: the host runs
  `wa_bthink` as now, with **both players as targets**. Figure 0 is the
  guest's player, so the host's bots see and shoot it.
- **The guest does not think for them; it walks them.** Bots walk route
  graph edges at a fixed speed, so an edge and a step on it say where a
  bot is. The host sends **BOT** events on each decision:
  - a new edge (bot, edge, step);
  - a state and target change (bot, state, target);
  - a shot (bot, weapon; its damage to the guest is in the host's
    cumulative damage word, so a hit costs nothing more);
  - a death and a respawn.
  The guest advances each bot along its edge every tick, exactly as the
  host does. A drift is corrected by the next event's step.
- **Engaged bots turn toward their target**. The guest knows both players'
  places, so it turns them itself.
- **Hits on bots**: the guest's hitscan on a bot sends HITBOT (bot,
  damage, kind) as an event, and the host applies it.
- **Estimate**: two bots, about one decision a second each, 16 bytes: ~32
  bytes/s. That is near the margin, so L2 measures it and takes SNAP to
  7.5 Hz if it must.

## 9. Stories

### L1: two players

- [ ] **L1.1 `apps/os88link.inc`**: the lease search (automatic, COM1,
  COM2, disconnect), its refusal lines, a framer for typed fixed-length
  frames up to 32 bytes, the CRC, the RX drain and TX flush. **Verify**:
  `tests/walink.py`'s host parser decodes every frame type the game sends.
- [ ] **L1.2 The lobby**: the Link menu, HELLO exchange and binding, host
  by identity, the host's arena and difficulty, Ready, START, the lobby
  text redrawn by line. **Verify**: two QEMUs on a socket pair reach "in
  the match" with the host's arena on both.
- [ ] **L1.3 SNAP**: sent every 3 ticks; the other player as figure 0,
  interpolated, running, standing, its firing cue, its shield.
  **Verify**: a player walked on one machine is figure 0 on the other,
  within one SNAP of the place, the same arena.
- [ ] **L1.4 Damage, death and score**: the cumulative damage word, death
  by kill kind, respawn, SCORE, the scoreboard with the opponent's name.
  **Verify**: one machine's pistol kills the other's player. Both
  scoreboards then read 1 kill and 1 death on the right rows.
- [ ] **L1.5 Events**: FIRE (both fly it, the victim judges it), TAKE,
  ROLL, LEAVE, the resend and the ack. **Verify**: a rocket fired on one
  machine flies on both and kills on the victim's; a pickup taken on one is
  gone on both; Esc on one says OPPONENT LEFT on the other.
- [ ] **L1.6 Faults**: garbage bytes, a truncated frame, a pulled cable for
  3 s. **Verify**: no state changes on garbage; LINK LOST, then the match
  resumes.
- [ ] **L1.7 Cost**: the link's cycles a frame on MartyPC; the frame rate
  in a linked match against alone.

### L2: the host's bots

- [ ] **L2.1 BOT events**: edge, state and target, shot, death and
  respawn, from the host.
- [ ] **L2.2 The guest walks them**: the same edges, the same speed, turns
  toward their target; corrected by the next event.
- [ ] **L2.3 HITBOT**: the guest's hits on bots, applied by the host.
- [ ] **L2.4 Two bots, both players their targets**; the lobby's Bots item
  (0..2).
- [ ] **L2.5 The budget measured**; SNAP at 7.5 Hz if it must.

### L3: after

- [ ] **L3.1 WireFleet onto `os88link.inc`**: its search and framer
  replaced by the shared include, its rows (`wirefleetlink`,
  `wirefleetsystem`, `wirefleetnomouse`) the check.
- [ ] **L3.2 86Box XT pair** (`tools/wireball-pair.py`'s pattern): 2400
  baud between two emulated 4.77 MHz machines, for the byte loss QEMU's
  fast CPU cannot show.
- [ ] **L3.3 kern_mega**: a linked match on kern_mega, beside kern_big.

## 10. How it is verified

- **Two QEMUs on a socket chardev** (`tests/wireball.py`'s owned-QEMU
  bridge, as `tests/wirefleetlink.py` uses it). MartyPC cannot link two
  instances (MULTIPLAYER-FPS-PLAN 8.3), so it is the one instrument for
  real bytes between two OS instances. It checks behaviour and bytes, not
  speed.
- **An independent host parser** (Python's `binascii.crc_hqx`, never the
  game's decoder) reads the bytes on the wire.
- **MartyPC** measures the link's cost in a frame (L1.7). Its numbers are
  for one machine; a pair's timing is the 86Box pair's (L3.2) or the iron's.
- **The rows are named as each story lands**; the soak union runs once
  after the last batch (CLAUDE.md, Testing).
