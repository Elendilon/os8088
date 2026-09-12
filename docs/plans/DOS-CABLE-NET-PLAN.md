# DOS-CABLE-NET-PLAN.md — a DOS program on the wire, over a parallel cable

**A machine with a parallel port and no network card is the machine `NET.DRV`
exists for.** SPEC.md §96.23 gave the DOS box a packet driver over
`ETHER.DRV`'s raw verbs, which is a *card* feature: on a cable-only machine a
DOS program gets nothing, because mTCP speaks packet driver and nothing else.

This is how it gets something better than nothing — and the design's whole
claim is that "better than nothing" undersells it by a factor of three.

SPEC.md §96.23 is the contract for the DOS-facing half and §72.22 for the
driver half; this file is the design record for the middle.

---

## 1. The obvious answer is a raw relay, and the arithmetic refuses it

The cable already carries a private protocol (`nwire.inc`) and the far end
already has a real packet driver against a real card (`drivers/net/pktdrv.inc`
— "a packet driver where the NE2000 was"). So the obvious design is two new
wire commands, `NW_RAWTX` and `NW_RAWRX`, and frames cross the cable.

**It does not work, and the reason is latency rather than bandwidth.**

| | |
|---|---|
| cable throughput (PERFORMANCE.md Set 39) | **3,741 B/s** |
| a 1,514-byte frame, one way | **0.405 s** |
| protocol frames per data frame (FTP-PERF, measured) | **2.32** |
| so: seconds per 1.5KB of payload | ~1.34 → **~1.1 KB/s** |
| a single round trip (SYN out, SYN\|ACK back) | **0.81 s** |

That last row is the one that kills it. mTCP's initial retransmit timeout is
about a second, so **every round trip sits on the edge of its RTO**; the first
queue behind a data frame pushes it over, the retransmit adds two more frames,
and the link spends its capacity re-sending things. It is not slow, it is a
collapse mode.

**Translating to sockets fixes the latency, not just the volume.** Only
*payload* crosses the cable — every acknowledgement the client's TCP needs is
generated locally, in microseconds. mTCP measures an RTT of about zero, its
timers never fire, and the cable runs at its full 3,741 B/s.

**~3.4× the throughput, and the difference between "slow" and "thrashes".**

---

## 2. Where it lives, and the two places it must not

The translation is **an `OP_SEG | OP_LAZY | OP_COMP` part of `DOS.O88`**
(SPEC.md §20.12): code reached by far call, fetched on demand, compressed on
the disk.

**Not in `NET.DRV`.** A driver is resident while mounted, so ~2KB there is
paid by every user of the cable — for a feature only the DOS box can reach.
That is the objection that decided this file, and it is `XMEM.DRV`'s argument
word for word (SPEC.md §41.12): *a machine with no XMS was reserving about
1.2KB of kernel image forever for a feature it can never reach.*

**Not a new driver either.** A `DOSNET.DRV` publishing the raw verbs in
`DRVC_NET` would need to call `NET.DRV` for its sockets, and **no driver in
this tree calls another** — `OSAPI_DRV_CALL` is published as *"a PACKAGE calls
a DRIVER"*. The alternative, its own copy of `lplink.inc`, makes two drivers
owners of one parallel port. Either way it is a new precedent bought for
nothing: the code is DOS-only, so it belongs to the DOS package.

**A sidecar `.OVL` was considered and refused.** §73.14's overlays are the C
toolchain's, emitted for `ovl_*` functions, and `DOS.O88` is assembly; and a
separate file beside a `SYSAPPS` package is a file a copy can leave behind,
which is the lesson `apps/c64` already paid for (its ROMs were a sidecar until
§20.12 wave 6, and *"a copy that took the program and left it behind was a
machine that could not start"*).

### 2.1 The part does protocol, and the image does everything ownership-bound

**Rule, and it is load-bearing: the part may call `OSAPI_DRV_CALL` and must
not claim memory or read files.**

A part's segment is a heap claim, not the package's region, and the
ownership-sensitive slots identify their caller *by the segment it runs in*
(`OSAPI_MEM_CLAIM`: "You are identified by the segment you run in"). A claim
made from the part would be owned by the wrong thing. `OSAPI_DRV_CALL` is
safe because the caller's segment is used for exactly one purpose — where the
buffers are (`[net_useg]`, `usr_read`/`usr_write`) — and no fence reads it.

So: claims, files and the part's own fetch are the image's; frames, headers,
sequence numbers and socket verbs are the part's.

---

## 3. The laziness is per SESSION, and §96.3 is why

**Every claim and every fetch must happen before the arena is sized.** §96.3
gives the DOS program `OSAPI_MEM_AVAIL`'s whole answer with no arithmetic
between the two calls, so by the time a client calls `access_type` there is no
heap left — which is already why §96.23.7's frame buffer is claimed in front
of the sizing call.

So the part cannot be fetched when the program asks for it. The question the
box asks instead, at `dos_run` entry, is **"is there a cable and no card?"**,
and `net_find` already answers it: it tries `DRVC_NET` first and falls back to
`DRVC_FILE` (SPEC.md §72, and it prefers the card for this exact reason).

| what `net_find` says | what happens |
|---|---|
| `DRVC_NET` — a card | nothing fetched; §96.23's raw verbs are used directly |
| `DRVC_FILE` — the cable | the part is fetched, pre-bracket |
| nothing | nothing fetched; no packet driver is published (§96.23.5) |

### 3.1 The trade, per machine — MEASURED, and it went the other way

This section was written around SPEC.md §20.12.9's table, which prices one
plain `OP_ASSET` row at **800 bytes** of parts code, and it said wave 1 would
measure ours rather than guess "because a `LAZY|SEG|COMP` row is a different
gate set". **The measurement is the finding, and it inverts the conclusion
this section originally reached.**

Built into `DOS.O88`, image delta against the same tree:

| the row declared | image | S |
|---|---:|---:|
| none (today) | 14,292 | — |
| `OP_ASSET`, or `OP_SEG` — *identical* | 16,124 | **1,832** |
| `OP_SEG, OP_LAZY` | 16,569 | **2,277** |

**`OP_COMP` with `OP_LAZY` is refused outright**, and the standard says why in
as many words: a lazy row's `zkb` word banks the segment it was fetched into
and a compressed row's carries its packed length, and there is one word. So
the part would ship uncompressed — which the owner had already discounted, but
it is a constraint worth knowing before designing around it.

Call the translation **T** (~2,000). Then:

| machine | parted | inline | verdict |
|---|---:|---:|---|
| no network at all | 2,277 | 2,000 | **inline** by 277 |
| a card | 2,277 | 2,000 | **inline** by 277 |
| cable only | 4,277 | 2,000 | **inline** by 2,277 |

**The standard costs more than the thing it defers.** Parting is a loss on
every machine, which is not a close call in the other direction either — so
waves 2–4 build the translation INLINE, and §8's rehome is what makes parting
worth doing at all rather than an optimisation on top of it.

The 1,832 for a plain row against §20.12.9's 800 is not explained here and
should not be guessed at: that table's figures are the *parts code* measured in
the `mseg` test package, and this is a whole-image delta in a package with
its own strings, alignment and bss chain. What is certain is the number that
decides the design, and it is the delta.

### 3.2 What inline actually costs, since it is what ships first

2,000 bytes of `DOS.O88`'s image, so 2,000 fewer bytes of arena for the DOS
program — **0.3% of a 640KB machine**, and none of it resident: a package's
region exists only while its window is open. That is a different quantity from
the one that sent this design away from `NET.DRV` (§2), where the bytes are
resident for as long as the driver is mounted and are paid by every user of
the cable, DOS or not.

---

## 4. What the translation actually does

It is a **slirp in reverse**: the client believes it is on an Ethernet, and
everything it emits is terminated locally and re-issued as socket calls.

- **ARP** — the client ARPs for its configured gateway. We answer every
  request with one synthetic MAC: *we* are the gateway, the router and the
  whole segment. A canned 42-byte reply with two fields poked.
- **IP** — parse the header, check nothing we do not have to, build ours with
  the right checksum. `ip_cksum` is 12 bytes in the ether driver and
  `ip_finish` 46; ours are the same arithmetic.
- **TCP** — the expensive part, and §5 is its own section.
- **UDP port 53** — intercepted, and §6 is why that is an opportunity rather
  than a gap.
- **everything else** — dropped, which is what a packet driver does to a
  frame nobody registered for.

---

## 5. The TCP endpoint, and what it does NOT need

Our whole TCP is **1,943 bytes** (the `tcp_` hull in `ether.bin`). The
endpoint here is a fraction of it, because what is underneath is not a network:

- **no congestion control** — no window scaling, no slow start. The far side
  of a `NETV_SEND` is a reliable in-order local transport.
- **no retransmit queue of our own.** `NETV_SEND` either takes the bytes or
  does not; there is nothing to time out.
- **no reassembly.** In-order only; anything else is dropped and the client
  retransmits, which is a path it already has.
- **no listen side** in this plan (§9).

What it does need, and none of it is optional:

1. **A per-connection state machine** — `SYN` → `SYN|ACK` → established →
   `FIN`/`RST`, plus recognising the client's retransmits idempotently.
2. **32-bit sequence arithmetic on an 8086**, which is the hidden cost and the
   one place to reuse rather than re-derive: `tcp.inc` already does it.
3. **The TCP checksum with its pseudo-header**, both directions.
4. **A fixed advertised window** equal to our staging buffer, so the client
   never sends more than we can hold.

**The mapping is the easy half**: a `SYN` to (IP, port) becomes `NETV_OPEN`;
the client's payload becomes `NETV_SEND` and is acknowledged the moment the
verb takes it; `NETV_RECV`'s bytes become an IP+TCP frame handed up through
§96.23.4's up-call; `NSK_CLOSING` becomes a `FIN`.

---

## 6. The DNS hijack — `NW_OPEN` takes a NAME, and that is the whole trick

There is **no UDP in the socket ABI**, so mTCP's DNS cannot be relayed. That
looks like the feature's hard edge and is instead its best simplification,
because `NETV_OPEN` takes `ES:SI` = **a host name** and `CX` = a port: *the
far side resolves*.

So:

1. the client asks its configured nameserver for `os8088.com`;
2. we answer with a synthetic address out of a private pool, and remember the
   pair;
3. the client connects to that address, and we `NETV_OPEN` **the name**.

**We never need a resolver, a cache or a UDP path.** The synthetic pool is
ours to choose and never reaches the wire; a name we have no mapping for is a
connection we refuse with `RST`, which is what a client understands.

---

## 7. The waves

| wave | what | gate |
|---|---|---|
| 1 | **DONE, and it changed the plan**: measure S. §3.1 is the result — 2,277 for a `SEG\|LAZY` row, against a 2,000-byte translation, so the part is REFUSED for now and waves 2–4 build inline | `S` is a number in §3.1 |
| 2 | ARP, IP, and the DNS hijack | the client's ARP is answered and a DNS query gets a synthetic A record |
| 3 | the TCP endpoint | mTCP's `htget` fetches a page across the cable |
| 4 | the gate's cable arm | `tests/dospkt.py` proves it under MartyPC with no second machine |
| — | *below here is optional and separately revertible* | |
| 8 | `OSAPI_PKG_REHOME` — give **S** back | `kernsize`-style A/B on the region |
| 9 | inbound (`NW_LISTEN`/`NW_ACCEPT` exist) | `ftpsrv` serves across the cable |

### 7.0 The translation is developed on the CARD, and that is not a shortcut

The translation consumes `NETV_OPEN`, `NETV_STATUS`, `NETV_SEND`, `NETV_RECV`
and `NETV_CLOSE` — and **both** drivers answer those verbs. `ETHER.DRV` is one
socket provider and `NET.DRV` is the other; which one a machine has is
`net_find`'s answer and nothing else in the translation cares.

So it is built and tested against the **card** under QEMU, where
`tests/dospkt.py`'s harness, a real network and mTCP already work, and the
cable is then the same code with `[net_cls]` holding a different class.
`DOSNETCARD=1` forces the translation on a machine that has a card, which is
what makes that testable at all — on such a machine §96.23's raw path is
strictly better and would otherwise always win.

That inverts the risk the hard way round on purpose: the protocol logic is the
part most likely to be wrong, and it is the part that can be exercised against
a real host at emulator speed. What is left for §7.1 is only *"do the same
verbs work when the wire under them is a cable"*, which is a much smaller
question than "is this TCP endpoint correct".

### 7.1 Testing needs no second machine, and that was not obvious

`tests/lptlink/partner.py` plays the far end of the cable **from the host**,
over MartyPC's `ParallelController` — `status_register_write` stores what the
debug server writes and `data_register_read` returns what the guest drives, so
the host owns both directions of the wire. It has the transport (nibble, byte,
word, dword) and stops there.

Wave 4 puts the **socket verbs** on top of it and proxies them to real host
sockets. The guest then runs mTCP over the cable and the *host* provides the
network — which is the one arrangement where this is testable in a container:
MartyPC has no NIC, and it does not need one, because the network is on the
far side of the cable by construction.

It is **exact rather than fast** (every nibble is debug-server round trips), so
the gate's payload is measured in hundreds of bytes, not a file.

---

## 8. `OSAPI_PKG_REHOME` — and why it is not wave 1

§20.12.10 is built: a loader tells the kernel *"the program is at DX, not at
me"*, its own region is freed, the carve is re-owned and `ld_start` runs step 8
again against the part. §20.12.9 measured what it is for — **a package that is
nothing but a reader spends 2KB of a 640KB machine on a program that has
finished its job.**

Applied here, `DOS.O88` becomes a thin loader whose part 0 is the DOS box and
part 1 is this translation, and **S is freed after launch**: the resident cost
of the whole feature goes to about zero. The loader fetches part 1
conditionally — the `net_find` question of §3 is answerable before the rehome —
and writes its segment into the head of part 0's bss, which §20.12.10.2 says
needs no mechanism because step 7 is deliberately not re-entered.

**It is a separate wave because it restructures the launch path of the most
complex package in the tree**, and it changes identity, bss handling and build
rules while changing no behaviour. Waves 1–4 add a capability and can be
judged on whether it works; wave 8 is a pure size change and can be judged on
one number. Landing them together would make a failure in either look like a
failure in the other.

§3.1's measurement makes it **the thing that decides whether parting happens
at all**, rather than an optimisation on top of a parted design. Parting
without it is a loss on every machine; parting with it takes the feature's
resident cost to about zero.

### 8.1 The hazard to design for: this package's bss is NOT zeroed after a rehome

§20.12.10.1 is explicit that `ld_start` jumps back to **step 8** and not step
7, because on the rehome path *"the bss arrived inside the part"* and zeroing
it would erase what the loader just wrote there.

**`DOS.O88` relies on a zeroed bss in at least one place that is load-bearing
and silent.** §96.6.1's per-drive current directories are one cluster word
each with *no "has this been initialised" flag*, on the stated grounds that
"a slot nobody has touched is 0 — which `.bss` already is, and which is
exactly right". A rehomed launch that skipped the zeroing would hand a DOS
program a current directory pointing at whatever cluster the heap last held.

So part 0 must **ship its bss as real zero bytes on the disk** (§20.12.10.2's
"§51.1.2's rule, one format along"), which costs the part's file about 1.4KB
and one more `int 13h` at launch — ~400 ms on the target machine
(PERFORMANCE.md). That is the trade wave 8 has to state: the resident bytes
come back, and a launch gets measurably slower. Both numbers, not one.

---

## 9. What will not work, stated plainly

- **`ping` will not work.** There is no raw ICMP over sockets. mTCP's `ping`
  is the one program that will fail on a cable machine and succeed on a card
  machine, which is worth a sentence in the user-facing docs.
- **UDP applications will not work** — `sntp`, `dnstest`. What does work is
  every TCP one: `ftp`, `telnet`, `htget`, `nc`, `ircjr`.
- **Inbound connections are wave 9.** `NW_LISTEN` and `NW_ACCEPT` are already
  on the wire, so `ftpsrv` and `httpserv` are a later wave rather than a
  refusal.
- **`kern_small` gets none of it, and needs none.** It ships no drivers, so
  there is no `NET.DRV` and no cable; and `DOS.O88` is in `SMALLOMIT` already
  (§96.1), so the small disks never carry the package, let alone the part.
  Nothing here needs an `%ifdef`.
