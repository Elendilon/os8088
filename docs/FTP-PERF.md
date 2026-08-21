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
