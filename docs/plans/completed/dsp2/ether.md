# Driver size pass 2: ether (ETHER.DRV, PCIETHER.DRV, NET.DRV, OS88NET.COM)

Agent **ether**, branch `dsp2-ether`, from `1b01907f1`. Owns `drivers/ether/`,
`drivers/pciether/`, `drivers/wirezone.inc` and `drivers/net/`. The target was
Wire Arena's UDP verbs (SPEC.md 72.24, `ethsock.inc` +212 lines), merged into
driver size pass 1's branch after its ether agent had finished and so never
sized, and the `ethdrv.inc`/`inet.inc`/`tcp.inc` deltas beside them; then a
sweep of the rest, starting from dsp1's NOT REACHED list. This pass is also a
SPEED pass (BRIEF 0.2), and every hot path it touched is faster - section 3.

**Read CROSS-FILE item 1 first.** `PCIETHER.DRV` now fits a 512-byte granule
fewer (35 -> 34), so the fast tier's `drvmem` fails at this tip until
`DRVM_IMG_PCIETH` moves in `kernel/driver.inc` - the coordinator's.

## 1. BASE AND TIP

Image is what RAM pays (the assembled image, bss included); file is the lz4
`.drv` on the disk; the claim is the image rounded up to the heap's 512-byte
granule. Measured from this worktree's own builds at `1b01907f1` and at the tip.

| product | image base -> tip | file base -> tip | claim (granules) |
|---|---:|---:|---:|
| ETHER.DRV | 17,799 -> **17,569 (-230)** | 11,147 -> **10,989 (-158)** | 35 -> 35 (161 bytes above the 34-granule step) |
| PCIETHER.DRV | 17,460 -> **17,233 (-227)** | 10,919 -> **10,752 (-167)** | **35 -> 34** (175 bytes under that step, 337 above the next) |
| NET.DRV | 4,167 -> 4,167 | 3,471 -> 3,471 | byte-identical image (`cmp`) |
| OS88NET.COM (shares inet, tcp, dns, ethsock, ethusr, ethstate) | raw 13,872 -> **13,756 (-116)** | 10,318 -> **10,244 (-74)** | |
| **total** | **-457 of driver image, -116 raw** | **-399** | |

The same `.drv` files ride every kernel's disks: kern_big, kern_emu and
kern_mega (`build/emu.img`, `build/mega.img` carry ETHER.DRV 10,989 and
PCIETHER.DRV 10,752, NET.DRV 3,471). **kern_small ships none of the four**
(`small360.img` has no network driver): its figures are 0.

Clusters (`tools/os88diskuse.py`): `os8088-360.img` (512-byte clusters)
ETHER.DRV 22 -> 22 - it would need 237 more file bytes for 21. PCIETHER.DRV,
not on the 360KB disk (`SYS360OMITDRV`), is **22 -> 21 clusters** on the
1.44MB and 1.2MB system disks, 11 -> 11 on 720KB. OS88NET.COM 11 -> 11 on
`network360`/`util360`.

## 2. TAKEN

Seven commits, each with its harness run. "Hot" is the per-packet, per-verb
and per-pump paths; every hot item is faster, with the counts in section 3.

**2.1 The UDP verbs (`ethsock.inc`, `inet.inc`, `ethstate.inc`, `tcp.inc`) -
ETHER -94 image / -68 file, PCIETHER -93 / -61, OS88NET -7.** Hot.

- **NETV_UDPRX moved all seven slots behind the one it took** - 504 bytes of
  `rep movsb`, ~8,600 clocks on the XT, for every datagram, and a game polling
  once a frame takes them one at a time. `[eth_uqe]` is now where the queue
  ENDS in bytes (UQ_SZ a datagram, slot 0 still the oldest), so the move is
  exactly the queued slots behind the one taken: none for the commonest case.
  The store's slot address is that word, where it was a `mul` (118+ clocks).
  Memory past the queued slots is never read (a slot is written whole before
  it is read), so only unreachable bytes differ.
- The source and the payload go out in ONE `usr_write` - they are one run in
  the slot and in the caller's buffer - and `min(capacity, true length + 6,
  70)` is the base's three clamps in one.
- **The verbs bank only what the door does not.** `eth_pkg` pushes BX, SI and
  DI and pops them after every verb, and these three verbs are ETHER.DRV's
  alone (ETH_NORAW keeps them out of the DOS end, whose door is another).
  `eth_pump` gives every register back - eth_pump_i's STKDEPTH-NOSAVE, the
  promise NETV_RECV's DI has always ridden on; the harness checks it directly
  (section 2.8). So NETV_UDPRX banks nothing and NETV_UDPTX banks DX and BP.
  **AX is kept on every success**, because a package reads it
  (`apps/os88udp.inc`: CF = 0 with AX = NETE_BUSY is a busy card).
- NETV_UDPTX reads the destination's six bytes into `eth_dip` and a new
  `eth_dport` after it, where `ip_start` banks a destination anyway (its own
  copy becomes four bytes onto themselves): `eth_udst`'s six bytes are two.
- `udp_queue` is written at its one call, in `udp_in`; `udp_in` banks no DX
  (nothing below it writes DX: `dns_in` and `dhcp_in` give it back) and the
  DOS end's ETH_NORAW arm keeps the `jne` it had (OS88NET -7).
- The refusals share tails: NETE_BUSY is `eth_v_raw`'s own, NETE_ARG is
  `eth_uarg`; the UDP block now sits beside NETV_RAW for the short jumps.
  `and word [x], 0` answers CF = 0 where `mov` + `clc` did.
- **The UDP state is all zero now and sits in the trailing zeros.**
  `eth_uslot` was `0xFF`, which nothing read: `eth_v_gone` tests it only to
  clear `eth_uport`, and that is 0 until a bind writes the two together.
- **`align 2` before `sk_tab`.** Wire Arena's state had moved the socket table
  and both frame buffers to ODD addresses in ETHER.DRV (and the queue in
  PCIETHER.DRV): free on an 8088, two bus cycles a word on an 8086, a V30 and
  every 286 and up - every `lodsw` of every checksum and every record word
  `tcp_match` reads. They are even again, and stay so whatever moves next.

**2.2 `usr_read` / `usr_write` are `rep movsb` (`ethusr.inc`) - ETHER -20
image / +7 file, PCIETHER -22 / -2, OS88NET -12.** Hot. They were byte loops
(~55 clocks a byte), and they are the copy of every raw frame a DOS stack
sends or takes (NETV_RAWTX/RAWRX, up to 1,514 bytes) and every Wire Arena
datagram. ring_in/ring_out made the same move in SPEC.md 72.16. One tail is
shared. ETHER.DRV's file grows 7 bytes (two near-identical byte loops packed
well); RAM, and the copy, are what the change is for.

**2.3 TCP states read once and written as one word (`tcp.inc`, `ethsock.inc`,
`ethdrv.inc`) - ETHER -66 / -40, PCIETHER -66 / -37, OS88NET -19.**
dsp1's NOT REACHED item and the shape beside it.
- `SKO_ST` and `SKO_TS` are the record's first word (a `%if` holds it), so the
  nine places that wrote both as two byte stores write one: `mov word [bx],
  TS << 8 | NSK` (4 bytes for 7), `and word [bx], 0` for FREE/CLOSED (3) -
  `eth_dropall`, `eth_v_close`, `eth_v_listen`, `eth_v_gone`, `tcp_syn`'s and
  `tcp_accept_in`'s refusals, `tcp_seg`'s CLOSE-WAIT, the passive open's
  promotion and SYN-SENT's.
- TS_CLOSED and TS_LISTEN are 0 and 1: one unsigned compare asks for both in
  `tcp_match` (every segment received - one compare fewer for every socket it
  passes, hot) and in `tcp_timers`' walk, where a free slot pays exactly the
  one compare it paid and the rest read TS once into AL; SYN-SENT/SYN-RCVD
  are one `ja`.
- `tcp_seg`'s FIN states, `tcp_finacked` and `eth_v_close` compare TS in AL;
  FIN-WAIT-2 is an `inc`; `tcp_finacked`'s CLOSING arm falls into
  `tcp_timewait`, which now follows it.
- `tcp_out` reloaded CX from `[eth_dlen]` where CX still held it (hot).

**2.4 `dns.inc` - ETHER -30 / -18, PCIETHER -30 / -23, OS88NET -21.** Cold.
`dns_timer`'s three give-ups (no name server, a name that will not encode,
the last retry) are one `call dns_fail`, its two deadlines one tail;
`dns_skip`'s three answers one tail (`db 0xA8` over the `stc`); `dns_drop` and
`dhcp_in`'s ACK clear a word with `and`. dns_timer's every-pump path (the
scan, or the live compare) is untouched.

**2.5 The zero state is one run to the image's end (`ethstate.inc`,
`etherui.inc`, `ethcfg.inc`, `ethdrv.inc`) - ETHER file -25, PCIETHER file
-24, OS88NET -15, image 0.** ethstate.inc's non-zero cells come first, so
four mid-image zero runs (24, 34, 83, 80 bytes) join the trailing zeros; the
Control Panel page's and the Setup window's zero state (50 and 202 bytes) are
macros placed after ethstate.inc. os88drv.inc's OS88_STATE note is the rule:
RAM is unchanged, the file is what moves. Every contiguity the code relies on
moves as a group (`eth_ip..eth_dns`, `eth_dip/eth_dport`, `dhcp_off/dhcp_srv`,
`ec_ip..ec_dns`, `eth_r1..3`).

**2.6 One `xchg`, and cold zero stores as `and` - ETHER -8 / -2, PCIETHER -16
/ -20, OS88NET raw -2.** `sk_release` and `rt_stop` (twice) take a claim and
leave the zero by `xor dx, dx / xchg dx, [x]`, where a load, a test and a
later store were (the zero still lands before the free). `and word [x], 0`
(5 bytes) for `mov word [x], 0` (6) where the path is cold and nothing reads
the flags after: `rt_start`, `tcp_timewait`, a retransmit, `eth_cfg_reap`,
`ec_apply`. The same swap on the per-frame paths (`ip_start`, `ip_finish`,
`udp_send`, `icmp_in`, `tcp_disarm`) was NOT made: `and` is the slower
instruction.

**2.7 The 8390's receive poll (`ne2000.inc`) - ETHER -12 / -12.** Hot.
`ne_rx`'s head runs on EVERY pump - every verb a package calls, a frame
waiting or not - and it was `ne_in` (ISR), `ne_out` (ISR) and `ne_curr` (CR,
CURR, CR): three calls each rebuilding base + register behind a push/pop
pair. DX walks the five ports instead, the same accesses in the same order
with the same values (ISR and CURR are both register 7, on pages 0 and 1);
`ne_curr` had no other caller. `ne_dma_write`'s completion poll reloaded
`[eth_base]` where DX was already base + NE_DATA on every path in.
`tests/picomem/nehx.asm` (ne2000.inc as it ships) assembles.

**2.8 How equivalence was shown.** Three harnesses in the scratch directory,
not the tree, each running the base (`1b01907f1`) and tip images side by side
under unicorn 2.1.4 on the same inputs:

- **`uharn.py` - the stack and every verb, ETHER.DRV and PCIETHER.DRV.** The
  card at the NIC seam (`nic_rx`/`nic_tx` answered by the harness, the 8390's
  zero padding included), the kernel at its cells and its rare door. After
  every step it compares every register a verb returns (BP relative to the
  dispatcher), CF strictly, the frames sent, the kernel calls in order with
  their arguments, the caller's whole segment, the socket pool's whole
  segment and the driver's state BY LABEL (so a moved cell is compared where
  it lives). Random actions over all 21 verbs and NETV_GONE, malformed and
  hostile frames, DHCP and DNS (A, CNAME, NXDOMAIN, junk, names and pointers
  running off the message), a reactive peer, and SCRIPTED TCP flows - active
  and passive opens, data both ways, our close through FIN-WAIT-2 and
  TIME-WAIT, a simultaneous close through CLOSING, the peer's close through
  CLOSE-WAIT and LAST-ACK, RST, abort, the kernel's teardown, a silent peer
  retransmitted out. It also calls `eth_pump` directly with every register
  random and requires all seven back (the promise 2.1 leans on).
  **Result: 0 differences**, ETHER.DRV 6 seeds x 2,000 steps, PCIETHER.DRV 3;
  377 of 391 stack labels reached. **Ten mutations went red** (the UDPRX
  clamp, the queue bound, the port read, the busy tail, a short shift, the
  connect deadline, FIN-WAIT-2's step, CLOSE-WAIT's state, the `tcp_out`
  reload, the no-DNS refusal); two benign ones (shifting MORE bytes than are
  queued, a pointer bound the caller re-checks) did not, as they cannot be
  seen.
- **`neharn.py` - a register-level 8390** (two pages, remote DMA, the ring
  with its four-byte headers, an overrun, a transmit that never completes,
  corrupt headers, NE2000 and NE1000 maps, a PROM) running the real
  `ne_probe`, `ne_init`, `ne_rx`, `ne_tx_i` and `ne_stop` of both images: the
  ordered port log (every in and out with its value), the card's memory, the
  frames sent, the frame received and the 8390 state are identical over 20
  seeds x 300 steps (2,026 frames received, 2,347 sent). Three mutations went
  red.
- **`cyc.py` / `necyc.py` - the clocks** (section 3).

Differences that remain and are intended, each read against its callers:
- **flags other than CF** after NETV_UDPRX (`sub` where `clc` was), and after
  any verb whose last flag-setting instruction reads an address that moved
  (`eth_v_state`'s walk ends on `sk_tab + 1024`). Every verb answers in CF;
  `apps/os88udp.inc`, the UDP verbs' one caller, reads CF and then AX.
- **DF is clear** after NETV_ADDR, NETV_RAW, RAWTX and RAWRX (`usr_*`'s
  `cld`), as it already was after nearly every other verb (ring_in, mem_copy).

`rt_stop` (PCIETHER's detach) is the one changed routine no harness reaches;
it was checked by reading: DX and the flags are what they were and the cell
holds 0 either way.

## 3. SPEED

Counted by `cyc.py`/`necyc.py`: every instruction the DRIVER executes on the
same state in both images is traced (kernel cells and the harness's NIC stubs
excluded) and priced by `tools/x3cyc.py`'s clock-stepped 8088 model (the BIU
queue, the 8-bit bus, refresh), each instruction's length its real encoding.
Clocks at 4.77 MHz, base -> tip; ETHER.DRV and PCIETHER.DRV alike for the
stack.

| path (hot unless named) | base | tip | |
|---|---:|---:|---:|
| NETV_UDPRX, queue empty (a game's every-frame poll) | 3,487 | 3,330 | -157 |
| NETV_UDPRX, one 64-byte datagram queued | 17,400 | 5,127 | **-12,273** |
| ...two queued, taking one | 17,400 | 6,383 | -11,017 |
| ...three taken one after another | 52,200 | 19,167 | **-33,033** |
| ...eight queued (full), taking one | 17,400 | 14,050 | -3,350 |
| a datagram for the port, pumped in (udp_in's store) | 7,936 | 7,576 | -360 |
| a datagram for a FULL queue (dropped) | 6,465 | 6,176 | -289 |
| NETV_UDPTX, 64 bytes to a cached host | 11,998 | 8,841 | -3,157 |
| NETV_UDPTX, 64 bytes, broadcast | 11,307 | 8,151 | -3,156 |
| NETV_RAWTX, a 1,514-byte frame (a DOS stack's every frame) | 95,035 | 28,498 | **-66,537** |
| NETV_RAWRX, a 1,514-byte frame | 92,502 | 28,528 | **-63,974** |
| NETV_RAWTX / RAWRX, a 60-byte frame | 5,311 / 5,268 | 2,719 / 2,758 | -2,592 / -2,510 |
| a 1,024-byte in-order segment in, its ACK out | 35,121 | 35,010 | -111 |
| NETV_SEND 1,024 bytes (one segment out) | 37,652 | 37,507 | -145 |
| a bare ACK in | 9,375 | 9,274 | -101 |
| NETV_RECV, 1,024 bytes waiting | 29,858 | 29,748 | -110 |
| NETV_STATUS / NETV_STATE with one ESTABLISHED socket | 4,178 / 4,594 | 4,106 / 4,520 | -72 / -74 |
| NETV_STATE idle, an ARP request, a ping (stack side) | 4,049 / 9,415 / 12,473 | unchanged | 0 |
| **ETHER.DRV `ne_rx`, ring empty - the head of EVERY pump** | 719 | 349 | **-370** |
| `ne_rx`, a 60-byte / 1,514-byte frame | 4,079 / 30,215 | 3,686 / 29,822 | -393 |
| `ne_tx_i`, any frame | 2,299 (60 B) | 2,279 | -20 |
| NETV_ADDR (cold) | 1,679 | 1,546 | -133 |

So an idle verb on an NE2000 is ~370 clocks (~78 us) cheaper on the XT, a
game's datagram ~2.6 ms, and a DOS program's full frame through the raw verbs
~14 ms each way. No path got slower; no transfer call (a frame, a port
sequence, a kernel claim) was added - the harnesses compare all three.

**The one look** (section 8) put the changed receive, transmit and UDP code
on QEMU's real `ne2k_isa` once.

**Not held: the code's parity.** 308 routines of ETHER.DRV moved by an odd
amount. On the 8088 that is free (a byte bus); on a 16-bit bus a branch
target's parity can cost a fetch cycle either way. The DATA that a 16-bit bus
pays for is held even (2.1's `align 2`).

## 4. REFUSED

- **dsp1's cable transport rewrite (`drivers/net/lplink.inc`)** stays
  refused, as the brief says (dsp1 RECORD 2.1): no harness here holds the real
  cable's timing. `lplink.inc` and `lplslv.inc` were not touched.
- **The UDP queue as a ring** (head and tail offsets, nothing ever moves):
  ~+23 bytes over 2.1's shape for the case where 2+ datagrams wait. 2.1 takes
  the commonest case to zero moves for -1 byte instead.
- **`rep movsw` for the queue's shift** (+2 bytes, ~26% of the shift when two
  or more are queued): the shift is zero in the common case now.
- **`mem_copy` for the queue's shift** (-4 bytes): +~150 clocks a datagram on
  the hot path.
- **`rt_rx`'s registers banked after the empty test** (PCIETHER's every-pump
  head): +5 bytes for ~110 clocks a pump on a kern_mega machine (a 386 or
  better), where that is ~5 us.
- **One remote-DMA setup for `ne_dma_read` and `ne_dma_write`**: ~25 bytes,
  but a call per frame (twice per received frame) on the hottest path.
- **`ne_rx`'s BNRY write direct**: +1 byte and DX is the frame's length there.
- **`ne_curr`'s AX bank through AH**: +2 bytes (moot - it is inlined).
- **`and word` for the per-frame zero stores** (2.6): slower.
- **`eth_cfg_reap` by `xchg`**: it would zero `[ec_win]` before the hide and
  destroy rather than after, and a hide repaints.
- **`ip_parse`'s digit through `aad`**: it loses the >255 test.
- dsp1's refusals stand (the spin loops, `eth_v_status` and `eth_v_rawrx`'s
  shared tails, `eth_v_accept`'s polled tail, `tcp_kick`'s TS test, `dns_id`
  in wire order, a computed `ec_blk`).

## 5. WANTS THE OWNER

1. **Drop the UDP queue's 589 bytes from every image.** The queue (8 x 72
   bytes) and its state are bss, paid by every machine that loads ETHER.DRV or
   PCIETHER.DRV whether or not anything binds a port. As a heap claim taken at
   `NETV_UDP` bind and freed at release and at `NETV_GONE`, it would cost
   ~+40 bytes of code and give back ~576 of image: ETHER.DRV ~17,030 (34
   granules), PCIETHER.DRV ~16,700 (33). The price is a NEW refusal at bind
   (no heap for 576 bytes) that SPEC.md 72.24 does not have, and a claim the
   heap must place while a game is starting. Not built.
2. **The DF difference** (2.8): ADDR, RAW, RAWTX and RAWRX leave DF clear
   where they handed the caller's back. It follows the convention (`cld`
   before a string op) and every other verb's existing behaviour; listed so
   the owner sees it.

No wording, limit or behaviour a package can see otherwise changed.

## 6. WANTS AN ABI BREAK

None. `netpkg.inc`, `tcp.inc`'s socket record, the SKI_* table, every NETV_*
and NETE_* value, the driver header and DRV_VER are as they were.

## 7. CROSS-FILE

1. **`kernel/driver.inc` (the coordinator's): `DRVM_IMG_PCIETH` 35 -> 34.**
   PCIETHER.DRV is 17,233 bytes with its bss, ceil(/512) = 34; t_drvmem
   (fast) fails until it moves. Knock-on, by the `%if`s there:
   `DRVM_PCIETH` 79 -> 78 half-KB, so **`DRVM_CEIL_NET_PCI` 40 -> 39** in
   `kernel/driver.inc` AND its SDK mirror in `apps/os88api.inc` (t_mirror),
   which moves the SDK fingerprint: `tools/abilock.py --update` without a
   `DRV_VER` bump (a caption's ceiling, the dsp1 precedent). And SPEC.md
   125.5's sentence quoting `DRVM_IMG_PCIETH` (35 half-KB, 17,432 bytes),
   79 half-KB, 40 KB and `DRVM_CEIL_NET_PCI` = 40 wants 34, 17,233, 78, 39
   and 39 with it. `DRVM_IMG_ETH` (35) and `DRVM_IMG_NET` (9) do not move.
2. **OS88NET.COM's zero state** (dsp1 netfs CROSS-FILE 3, now this agent's
   file): ~230 bytes of `ethstate.inc`/`dns.inc` zeros are emitted in the
   .COM's image where an `absolute` block could reserve them (NWSLV_ZSTATE's
   shape). Raw image -230 on the DOS machine, file a few bytes. Not reached.
3. **Attach-only code** (dsp1's figure, re-read): `eth_attach`, `eth_bases`,
   `eth_ready`, `eth_cfg_load`, `ec_buf_take`, `ne_memok` and its pattern are
   still ~330 bytes run only at attach, and `ne_probe`/`ne_init` ~320 at
   attach and wake; PCIETHER ~230 and ~265. Giving them back is a loader
   change.
4. `apps/os88ui.inc` and `apps/os88line.inc` are still ~1.5KB of each image
   (dsp1 CROSS-FILE 4, unchanged).

## 8. ROWS TO RUN

- **fast**: `drvmem` (fails until CROSS-FILE 1), `drvverb`, `installabi`.
- **full**: `megapkg`.
- **soak, the stack and both drivers**: `stknosave`, `stknosave-pciether`
  (udp_in no longer banks DX and leans on its callees; tcp_finacked falls into
  tcp_timewait), `ethernet`, `pciether`, `pcibig`, `ethcfg`, `socktest`,
  `b4ether`, `b4ethswap`, `b4lease`, `picomem` (nehx runs ne2000.inc as it
  ships), `dospkt` (the raw verbs through usr_*), `romsock`, `netcoexist`,
  `netinst`, `netinstbad`, `netpromise`, `hmadrv`, `drvup`.
- **soak, Wire Arena's UDP**: `walinkudp`, `walinkip`, `walink4`,
  `walink4ip`, `walinkmegaudp`, `walinkmegaip`, `walinknet`,
  `walinkmeganet` (the raw fallback).
- **soak, the packages over the stack**: `ftpd`, `ftpdflick`, `ftpdfocus`,
  `ftpdpix`, `ftpkeep`, `telnet`, `telnetherc`, `wirechat`, `wcdrawwired`,
  `wire`, `thewire`, `thewirexms`, `wirezone`, `wireflick`, `httpmount`,
  `httpmountname`, `httpinstall`, `httpdrvtool`, `install`,
  `pkgmove-browser`, `pkgmove-ftpd`.
- **soak, OS88NET.COM**: `doscable`, `sfx`, `dosnetarena`.

## 9. LOOKED

One QEMU boot (QEMU is the NIC emulator, CLAUDE.md's closed list) of
`build/ether360.img` at the tip with `ne2k_isa` on slirp: ETHER.DRV attached
at 0300h with the station address 52:54:00:12:34:56, and DHCP bound -
10.0.2.15, mask 255.255.255.0, router 10.0.2.2, name server 10.0.2.3 - in two
frames each way, no drops, no overruns. That exchange runs the changed
`ne_rx` head, `ne_dma_write`'s poll, `udp_in`'s new body and `dhcp_in` on
QEMU's card model. Then stopped. `make -j2`, `make -j2 emu` and
`make -j2 mega` are green at the tip but for `drvmem`.

## 10. DEFECTS FOUND

- **`udp_queue` ran `movsw`/`stosw` before its `cld`** (fixed, 0 bytes): a
  datagram arriving under a caller's DF = 1 was stored backwards over the
  slot before it. Found by reading; the `cld` is first now.
- **The socket table and frame buffers sat at odd addresses** since Wire
  Arena's merge (fixed with `align 2`, 2.1): a speed defect on 16-bit buses.
- Stale comments fixed: `wirezone.inc`'s NETV_MAX (17, now 20), tcp.inc's and
  ether.asm's "four connections" (NET_SOCKS is eight), `udp_in`'s citation of
  SPEC.md 72.23 for the package port (it is 72.24), and `eth_v_udprx`'s claim
  that eth_pump banks only CX and BP (true of its pushes, not of its callees).

## NOT REACHED

- CROSS-FILE 2 (OS88NET.COM's zero state).
- `eth_v_state`'s, `tcp_timers`' and `dns_timer`'s three walks of the eight
  sockets on every pump (~2,600 of the idle verb's 4,049 clocks): a count of
  live sockets would skip them, at the price of keeping the count right.
- `ip_parse`, the Control Panel page and the Setup window (dsp1 went through
  them; a few 1-2 byte tails remain).
- `rt_rx`'s every-pump head beyond REFUSED's note.
