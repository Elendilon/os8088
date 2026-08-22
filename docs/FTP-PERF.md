# FTP throughput — where it stands, and what is left

The state of the FTP server's speed after one long session on it, written so
the next round starts from evidence instead of from scratch. Every number here
came off **the 5150** unless it says otherwise; QEMU numbers are labelled and
are never times (PERFORMANCE.md Part 3).

---

## 1. The number, and how it moved

| build | B/s | what changed |
|---|---|---|
| first field run | **7,062** | — (with a 6 s dead gap at the start) |
| `3969745` | **8,720** | the TIME-WAIT reap: the gap became 0 s |
| `0c12f31` | ~12,600 | `rep movsb` for the ring copies |
| `04fa06c`+ | **~15,000** | the field's own figure |

**7 KB/s to 15 KB/s, a bit over 2×.** A 297 KB upload went from never
finishing inside the client's 28-second timeout to finishing in 24 s.

## 2. What actually fixed it, in order of size

1. **`rep movsb` for the ring copies (§72.16).** `sk_rxput`, `sk_rxget`,
   `ring_in`, `ring_out`, `ring_move` were hand loops at ~83 clocks a byte;
   `rep movsb` is 9+17n, about 17. Measured **8,670 ms off the driver** on a
   297 KB transfer, against nine seconds predicted.
2. **`sk_rxput`'s restructure (§72.15.4).** It read `[bx+SKO_RXH]` *twice per
   byte* and bracketed every store with `push di`/`pop di` — fifteen
   instructions and four memory operands per byte. It was 71% of every
   received frame. §72.13.1 had fixed its sibling and left it.
3. **The TIME-WAIT reap (§72.14).** Not throughput — it removed a **6-second
   hole** at the start of every transfer that followed another one. Four
   sockets, and one FTP session uses all four, so the data socket a `LIST`
   just closed held the fourth for `TCP_TWTMO`. Measured 6.15 s → 0.39 s.
4. **The ring size (§72.13).** The window *was* the constraint at 1024 bytes
   (window ÷ turnaround = 7.1 KB/s, and the field measured 7.3). Making the
   rings a heap claim removed that ceiling — **and on its own bought nothing
   measurable**, because the per-byte cost immediately became the constraint
   instead. Both facts matter.

## 3. What did NOT work, and is written down so it is not tried again

- **A bigger staging buffer in the FTP server.** `FD_STGSZ` 8192 → 32768:
  the field measured no change, twice. The staging buffer was never the
  constraint.
- **Fewer, larger disk appends.** The same change made the *gap* worse — the
  worker stops reading while the UI task writes, so the chunk size IS the
  length of the silence on the data connection (§77.24). The number that made
  the fewest appends made the worst gaps.
- **Blaming the disk seek count.** Measured: no change.
- **Blaming retransmits.** A packet capture showed 126 segments, **zero**
  retransmissions, 129,671 bytes on the wire for a 129,430-byte file. The wire
  was already perfect.

## 4. Where the time goes NOW

The last full field profile (`netbench`, §72.15), a 297 KB upload,
`ACTIVE` 23,781 ms:

| | ms | % |
|---|---|---|
| **OUTSIDE the driver — the FTP server, the disk, the scheduler** | **13,499** | **57%** |
| `card` — `ne_ring_read`, the NIC's ring into our frame buffer | 2,942 | 12% |
| `verb` overhead — `eth_pkg` minus `pump` and `rxget` | 2,004 | 8% |
| `rxput` + `rxget` — the two ring copies | 2,641 | 11% |
| `pump` overhead — the timers, per call | 1,001 | 4% |
| `frame`, `cksum`, `tx` | 2,503 | 10% |

**The whole driver is 43%.** Making it infinitely fast wins at most that.

## 5. The next things to try, in the order the evidence ranks them

1. **Find out what the 57% is.** `ftpd` now times itself (§77.32) and prints a
   second line after the rate: `disk NNN net NNN draw NNN` in ms, on the same
   clock `netbench` uses. **Take that reading first.** Everything below is
   guesswork until it exists.
2. **`card`, 12%.** `ne_dma_read`'s loop is `in al,dx / stosb / loop` — about
   10.9 µs a byte, and the field's card is an 8-bit NE1000 so word reads are
   not available. Unrolling ×8 removes seven eighths of the `loop` (17 clocks)
   and its fetch. Worth maybe 600–900 ms.
3. **`verb` overhead, 8%.** 2,004 ms over 583 calls is **3.4 ms a call** and
   nothing explains it — `eth_claim` is a test-and-set and the dispatch is a
   table call. This is the most suspicious number in the table. It needs a
   finer stage inside `eth_pkg` before anything is changed.
4. **`rep movsw`, 11% → ~8%.** 25 clocks a word against `movsb`'s 17 a byte —
   12.5 vs 17. It needs odd-count and odd-alignment handling on both pointers,
   and a wrong tail byte in a ring copy is a corrupted transfer rather than a
   slow one. Do it after 1–3, measured.
5. **`pump` overhead, 4%.** 1.7 ms per pump even when the ring is empty:
   `tcp_timers` walks four sockets, then `dns_timer` and `dhcp_timer`. 582
   pumps for 234 frames — most find nothing. A cheap "has a tick passed"
   guard in front of the three timers would remove most of it.

## 6. The instruments, and how to take a reading

- **`make netbench`** — `NETBENCH.O88` beside `FTPD.O88` on one disk, three
  geometries. Open both, press **S**, run the transfer, press **X**, then
  **R**. **W** writes `NETBENCH.TXT` to the floppy. §72.15.
  - `wall` is S-to-X and **has your hands in it**; `ACTIVE` is the first
    payload byte to the last and is what the percentages divide by (§72.17).
  - `ACTIVE 0` with a `NO PAYLOAD MOVED` line means an idle machine, priced
    against the wall — which is a real measurement: the poll loop costs
    **3.0% of an idle 8088** (§72.18.1).
  - A save takes seconds and says `WRITING THE REPORT` while it does.
- **The FTP window's own second line** — `disk N net N draw N`, per transfer,
  in ms (§77.32). Same clock, so the two reports add.
- **`python3 tools/os88disk.py --verify-hdd IMG`** — an independent fsck for a
  partitioned image, including one behind an ST-11M-style reserved area.

### 6.1 The ETHPUMP A/B, on the 5150 — and why it reads backwards

Same 304552-byte `banana split.mod` STOR from WinSCP, two runs each way, over
the same session; `gap 0s` on all four.

| build | wall | rate | disk | net | draw |
|---|---|---|---|---|---|
| A — verbs pump (shipping) | 19s | **16029 B/s** | 3579 | 7649 | 33 |
| A — again | 19s | **16029 B/s** | 3586 | 7636 | 33 |
| B — worker pumps instead | 22s | **13843 B/s** | 3613 | 2497 | 33 |
| B — again | 22s | **13843 B/s** | 3621 | 2398 | 32 |

Repeatable to the byte per second, which is itself worth noting: the transfer
is deterministic enough that a 13.6% difference is not noise.

**The `net` column is the trap.** It is ftpd's own timer for time inside
`OSAPI_DRV_CALL` (§77.32), and it falls by 68% — the app really is spending a
third of the time in the driver that it used to. That is the redesign working
exactly as drawn, and it is not a win: the pumping did not get cheaper, it
moved into a task ftpd's split cannot see, and the wall clock is the only
column that counts the whole machine. **A self-timer that stops covering the
work is not the work stopping.**

Where it went: during a transfer the app calls verbs many times a tick, so
there is no gap for a worker to fill, and it becomes a third contender for the
card's mutex. `eth_claim` is answered `NETE_BUSY` and never waited on, and
`fd_recv_stage` abandons its whole drain on a `NETE_BUSY` (§77.30) — so one
collision costs the app a pass, not an instruction. SPEC.md §72.19.5 is the
fix: the worker test-and-clears a beat the verbs set, and pumps only after a
full turn in which nobody did. Busy stack: the A build. Idle stack, or one
whose package is inside a 400ms disk commit: pumped anyway.

**And it is worse than slow: on B the drag KILLED the transfer.** The field,
same session: *"Dragging the window during the write was smooth on B, but it
also killed the transfer — the file progress stops popping up, the writes stop,
and the client eventually times out on a control connection error."* On A the
same drag is choppier and the transfer survives it.

Both halves of that are the same cause and neither is a win:

- **The smoothness came from ftpd doing less per turn, not from the worker
  doing more.** A verb that pumps drains up to `ETH_BUDGET` = 8 frames, and 8
  frames is up to eighty milliseconds of byte-at-a-time DMA on whichever task
  called the verb. On B the verbs skipped that, so ftpd's worker turns got
  short and the drag loop got the CPU. **That points the latency work at
  `ETH_BUDGET`, not at where the pump runs** — a smaller or adaptive budget
  buys the same smoothness without moving anything to another task, and is the
  cheaper experiment of the two.
- **The stall is the contention above, taken to its limit.** A drag is the case
  where ftpd gets the fewest turns and the worker keeps taking the card on
  every one of its own, so a larger share of ftpd's few verb calls come back
  `NETE_BUSY` — and each one throws away a whole `fd_recv_stage` drain. The
  data path goes to nothing, and the control timeout is downstream of that
  rather than a second fault. *(Mechanism inferred, not instrumented: what is
  measured is that it happens on B and not on A.)*

**Round two — the standby, and the bug underneath all of it.** Same transfer,
B2 = `ETHPUMP=1` with the worker standing down whenever a verb had pumped:

| build | wall | rate | disk | net | draw |
|---|---|---|---|---|---|
| A — verbs pump | 19s | 16029 B/s | 3579 | 7649 | 33 |
| B — worker instead of verbs | 22s | 13843 B/s | 3613 | 2497 | 33 |
| B2 — worker on standby | 20s | **15227 B/s** | 3618 | 7140 | 144 |

`net` back to 7140 says the verbs are pumping again, and 5% is a lot better
than 13.6%. But **the drag still killed the transfer, and afterwards the client
could not even reconnect** — which is the finding, because a stalled transfer
is a contention story and a dead listener is not. Every verb was being refused,
including `ACCEPT`.

It was a register-contract bug, in the worker I wrote:

```
    mov cx, ETH_BUDGET
.f: call eth_claim
    call eth_pump1              ; ...which returns ne_rx's LENGTH in CX
    loop .f                     ; ...so this counts down from ~1500
```

`eth_pump1` is documented at its label as "CX is `ne_rx`'s length and
`eth_frame`'s input, so it flows between them and is the caller's to save", and
`eth_pump_i` keeps its budget in **BP** for exactly that reason. The worker's
eight-frame budget was really the last frame's length, so it drained the ring a
thousand frames at a time with no yield in it — and every package verb landing
in that storm got `NETE_BUSY`. A drag is where the package gets the fewest
turns, so it is where all of them landed in it.

Two things came out of the fix (SPEC.md §72.19.5–.6): the budget moved to BP
and the worker re-reads the beat *inside* the drain, and — separately — the
beat moved to `eth_pkg`'s door and is set **before** the claim. Setting it only
where the claim succeeded is a stable livelock: a bounced verb leaves no trace,
so the worker reads an idle stack and pumps again forever. That is the half
that explains "cannot reconnect".

**On "cannot reconnect", and it is inferred rather than proven.** The field
waited 200s and it never cleared; stopping and restarting the server got a
connection and a `PWD` through before it timed out again. A restart does not
touch `[eth_busy]`, and `LISTEN`/`ACCEPT`/`SEND` all worked immediately after
one — so the card's mutex was **not** what was stuck. `NET_SOCKS` is **4**
(netpkg.inc), and a session in flight is already using three of them; a
transfer that dies with its connections stranded leaves nothing for `sk_alloc`
to hand the next `ACCEPT`. Stopping the server is what closes them. So the
starvation is the fault and the dead listener is downstream of it, which is why
the fix is aimed at the starvation and the reconnect is a thing to re-check
rather than a thing separately fixed.

**Neither of these runs measures what the worker is FOR.** A 300KB upload is
the case where the app polls hardest; the worker exists for the windows where
it does not poll at all — an incoming SYN while the UI repaints. That case has
no number yet.

## 7. Rules this exercise re-learned the hard way

- **QEMU cannot see any of this.** It prices instructions at host speed: the
  `rep movsb` change moved its counts not at all. What QEMU proves is that the
  copies are still *exact* — `tests/ftpd.py` round-trips every byte value.
- **A prediction gets written down before the build ships, or it is worthless.**
  §72.16 predicted nine seconds and measured 8,670 ms. §72.13 predicted ~58
  KB/s from an *estimated* per-byte ceiling and was wrong by 8×.
- **Instrument before optimising.** Three rounds went into the part that was
  measurable rather than the part that was large, and a table found the real
  one in a single run.
- **An open bracket is the profiler bug you will write.** Twice: `prof_start`
  and `fd_tzero` both zero their counters from inside a stage that is already
  being timed, and the close then measures from the epoch. Re-stamp every
  open bracket on reset.

## 8. Open, and not throughput

`docs/FIELD-NOTES.md` **27** — the 5150 hard-freezes during an FTP session.
One cause was found and fixed (an unaligned disk buffer, §77.31) and it did
not close the note: the machine still freezes, most recently on a bare `PWD`.
That is the next piece of work and it is a correctness one, not a speed one.
