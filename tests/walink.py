#!/usr/bin/env python3
"""WireArena over a null modem: two QEMUs on a socket cable, the shipped
package, real UART bytes (docs/plans/WIREARENA-LINK-PLAN.md, wave L1).

Uses WireBall's owned-QEMU bridge (tests/wireball.py), as wirefleetlink
does: MartyPC cannot link two instances, so this is the instrument for two
OS instances talking. It checks behaviour and bytes, not speed.

  - THE LOBBY: each window finds the other by itself (Automatic), binds it,
    agrees who hosts (the lower identity), and Space on both starts the
    host's arena on both;
  - SNAP: a player put somewhere on one machine is figure 0 on the other,
    within a SNAP of the place;
  - A KILL: three pistol shots from one machine kill the other's player
    there - its death on its own machine, credited to figure 0, and once a
    SCORE has crossed both scoreboards agree (1 kill, 1 death, the right
    rows);
  - A ROCKET: fired on one, it flies on both (FIRE), owned by figure 0 on
    the victim's, and kills there;
  - A PICKUP: taken on the host, gone on the guest too (TAKE), and back on
    both when the host says (ROLL);
  - FAULTS: garbage on the cable changes nothing and is counted; the cable
    pulled says LINK LOST and the match resumes when it is back;
  - ESC: one leaves, the other says OPPONENT LEFT.
  - THE WIRE: every byte either way, parsed by an independent decoder
    (binascii's CRC, never the game's), is a valid frame of a known type
    and length.

Registered as walink in soak; make wirearenadisk first.
"""
import binascii
from pathlib import Path
import struct
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'tests')]
import wireball as W                                            # noqa: E402
import os88qemu as Q                                            # noqa: E402
import dispapps                                                 # noqa: E402
from walift import amap                                         # noqa: E402
from waweapons import anims                                     # noqa: E402
import arenagen                                                 # noqa: E402

# The package's symbols: walift's map, assembled and held to the build
# (dispapps cannot unwrap a parted image whose part 0 is OP_ZFILL)
_map = dispapps._map
dispapps._map = lambda app, defines=(): (amap() if app == 'wirearena'
                                         else _map(app, defines))

LENS = {1: 20, 2: 15, 3: 8, 4: 19, 5: 24, 6: 17, 7: 12}
ANIM = {}
FS = 56
fails = []


def check(ok, what):
    print('  %s %s' % ('ok  ' if ok else 'FAIL', what), flush=True)
    if not ok:
        fails.append(what)


def frames(wire):
    """(type, body) of each frame on the wire; bad ones as (None, raw)"""
    parts = bytes(wire).split(b'\x7e')
    for raw in parts[1:-1]:             # (the ends: cut by the capture)
        if not raw:
            continue
        out, esc = bytearray(), False
        for b in raw:
            if esc:
                out.append(b ^ 0x20)
                esc = False
            elif b == 0x7d:
                esc = True
            else:
                out.append(b)
        if (not esc and out and LENS.get(out[0]) == len(out) and
                binascii.crc_hqx(bytes(out[:-2]), 0xffff) ==
                int.from_bytes(out[-2:], 'little')):
            yield out[0], bytes(out)
        else:
            yield None, bytes(raw)


class Arena(W.Machine):
    def __init__(self, d, i):
        super().__init__(d, i, app='wirearena', filename='WARENA.O88',
                         disk=W.artifact('warena.img'), prefix='wa_')

    def v(self, name, n=1, signed=False):
        return int.from_bytes(self.readseg(self.seg, self.sy[name], n),
                              'little', signed=signed)

    def fig(self, i):
        d = self.readseg(self.seg, self.sy['wa_figs'] + i * FS, FS)
        w = lambda o: struct.unpack_from('<h', d, o)[0]
        return dict(x=w(0), y=w(2), ang=w(4) & 1023, anim=d[11], nfr=d[12],
                    flash=d[16], dead=d[17], z=w(18), sh=d[10])

    def at(self, x, y, ang=0):
        """the player put at (x, y), facing ang (0..1023), nothing held"""
        self.put([('px', x, 2), ('py', y, 2), ('pxf', 0, 2), ('pyf', 0, 2),
                  ('ang', ang << 6, 2), ('pitch', 0, 2), ('jz', 0, 2),
                  ('jv', 0, 2), ('hp', 30000, 2)])

    def wait_for(self, cond, what, secs=10):
        ok = Q.acted(self, cond, secs=secs, what=what)
        check(ok, what)
        return ok

    def setf(self, i, off, value, n=1):
        """figure i's byte (or word) at off"""
        name = 'wa_f%d_%d' % (i, off)
        self.sy[name] = self.sy['wa_figs'] + i * FS + off
        self.put([(name[3:], value, n)])

    def freeze(self, i, x, y):
        """bot i stood at (x, y): a step of nothing (its cached velocity 0
        for the heading it has) and a leg too long to end - so it walks
        nowhere however long the poke takes (QEMU's sim runs fast, and a
        flinch held it ~12 ticks)"""
        head = struct.unpack('<H', self.readseg(
            self.seg, self.sy['wa_figs'] + i * FS + 20, 2))[0]
        self.setf(i, 0, x | (y << 16), 4)
        self.setf(i, 8, 30000, 2)
        self.setf(i, 36, (head | 0x8000) | 0, 2)
        self.setf(i, 38, 0, 4)

    def fire(self):
        self.key_state('ctrl', True)
        Q.pace(self, .15)
        self.key_state('ctrl', False)
        Q.pace(self, .25)


def main():
    ANIM.update(anims())
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        a, b = Arena(d, 0), Arena(d, 1)
        cable = W.Cable([a, b])
        try:
            run(a, b, cable)
        finally:
            cable.close()
            a.cleanup()
            b.cleanup()
    if fails:
        print('walink: FAIL - %d of the link\'s checks:' % len(fails))
        for f in fails:
            print('  ' + f)
        sys.exit(1)
    print('walink: ok - two machines, one arena, the cable')


def run(a, b, cable):
    # THE LOBBY
    for m in (a, b):
        m.wait_for(lambda m=m: m.v('wa_lkpeer', 4) != 0 and
                   m.v('lk_blk') == 1, 'THE LOBBY: %s finds its peer'
                   % ('A' if m is a else 'B'), secs=20)
    ida, idb = a.v('wa_lkid', 4), b.v('wa_lkid', 4)
    check(a.v('wa_lkpeer', 4) == idb and b.v('wa_lkpeer', 4) == ida,
          'THE LOBBY: each bound to the other (%08x, %08x)' % (ida, idb))
    host, guest = (a, b) if ida < idb else (b, a)
    host.put([('lkarena', 2, 1), ('lkbots', 0, 1)])  # (the heights; L1:
                                                       # no bots)
    for m in (a, b):
        m.key('spc')
    for m in (a, b):
        m.wait_for(lambda m=m: m.v('wa_lkon') == 1,
                   'THE LOBBY: Space on both - %s in the match'
                   % ('the host' if m is host else 'the guest'), secs=15)
    check(a.v('wa_arena') == b.v('wa_arena') == 2 and
          a.v('wa_lktag') == b.v('wa_lktag') != 0,
          'THE LOBBY: the same arena (%d, %d) and tag (%d, %d)'
          % (a.v('wa_arena'), b.v('wa_arena'), a.v('wa_lktag'),
             b.v('wa_lktag')))

    def rate(m, secs):
        """bytes each way a SIM second (30 of the game's ticks): each
        direction counted on the wire against its SENDER's own clock - the
        line has to carry them at the rate the sender's sim makes them, and
        on the iron each sim keeps real time. Under QEMU on a loaded host
        neither does, and the two run apart (37 to 42 ticks a 'second'; one
        machine sent 66 SNAPs to the other's 56 in the same window)"""
        c0 = list(cable.counts)
        k0 = [a.v('wa_tkn', 2), b.v('wa_tkn', 2)]
        Q.pace(m, secs)
        k1 = [a.v('wa_tkn', 2), b.v('wa_tkn', 2)]
        return [(c - c0[j]) * 30.0 / ((k1[j] - k0[j]) & 0xFFFF)
                for j, c in enumerate(cable.counts)]


    # SNAP: B somewhere; A's figure 0 there
    b.at(1100, 300, 512)
    a.at(1000, 300, 0)

    def near(m, x, y):
        f = m.fig(0)
        return not f['dead'] and abs(f['x'] - x) <= 6 and abs(f['y'] - y) <= 6
    a.wait_for(lambda: near(a, 1100, 300), 'SNAP: B at (1100, 300) is A\'s '
               'figure 0 there (%r)' % a.fig(0))
    b.wait_for(lambda: near(b, 1000, 300), 'SNAP: A at (1000, 300) is B\'s '
               'figure 0 there')
    check(a.fig(0)['ang'] == 512 & 1020, 'SNAP: facing as B does (%d)'
          % a.fig(0)['ang'])

    # A KILL: A's pistol, three shots, B at 100 health
    b.put([('hp', 100, 2), ('sh', 0, 2)])
    Q.pace(a, .3)
    for _ in range(3):
        a.fire()
        if b.v('wa_pdead'):
            break
    b.wait_for(lambda: b.v('wa_pdead') != 0, 'A KILL: A\'s pistol kills B '
               'on B\'s machine', secs=5)
    check(b.v('wa_kills', 4) & 0xFF00 == 0x100 and b.v('wa_deaths') == 1,
          'A KILL: B\'s death, figure 0\'s kill (kills %08x, deaths %d)'
          % (b.v('wa_kills', 4), b.v('wa_deaths')))
    a.wait_for(lambda: a.v('wa_kills') == 1 and a.v('wa_deaths', 2) == 0x100,
               'A KILL: A\'s board after a SCORE - YOU 1 kill, the other '
               '1 death', secs=4)
    a.wait_for(lambda: a.fig(0)['dead'] != 0, 'A KILL: B down on A\'s '
               'screen too', secs=3)

    # A ROCKET: B back, at 50; A's launcher at it. Its splash (128 less
    # the distance: WEAPONS-PLAN) is judged on B's machine, owned there by
    # figure 0, whose kill it is
    b.wait_for(lambda: b.v('wa_pdead') == 0, 'B respawns', secs=6)
    b.at(1100, 300, 512)
    b.put([('hp', 50, 2), ('sh', 0, 2)])
    a.at(1000, 300, 0)
    a.wait_for(lambda: near(a, 1100, 300), 'A ROCKET: B where A sees it')
    k0 = b.v('wa_kills', 2) >> 8
    a.sy['wa_mag4'] = a.sy['wa_mag'] + 4    # (the launcher's magazine)
    a.put([('own', 1 | 16, 1), ('wpn', 4, 1), ('rld', 0, 1), ('cool', 0, 1),
           ('mag4', 3, 1)])
    a.fire()
    b.wait_for(lambda: b.v('wa_pdead') != 0, 'A ROCKET: FIRE flies it on '
               'B\'s machine, and its splash kills B there', secs=5)
    rk = struct.unpack_from('<hh', b.readseg(b.seg, b.sy['wa_rks'], 4))
    check(b.v('wa_hurtby') == 1 and (b.v('wa_kills', 2) >> 8) == k0 + 1
          and abs(rk[0] - 1100) < 30 and rk[1] == 300,
          'A ROCKET: figure 0\'s kill (hurt by %d), the rocket burst at B '
          '(%d, %d)' % (b.v('wa_hurtby'), rk[0], rk[1]))
    b.wait_for(lambda: b.v('wa_pdead') == 0, 'B respawns', secs=6)

    # A PICKUP: the host walks onto the health pack
    npk = host.v('wa_npk', 2)
    pks = host.readseg(host.seg, host.sy['wa_pks'], npk * 8)
    hp = [i for i in range(npk) if pks[i * 8 + 6] == 5]
    if hp:
        i = hp[0]
        x, y, z = struct.unpack_from('<hhh', pks, i * 8)
        bit = 1 << i
        guest.wait_for(lambda: guest.v('wa_pkon') & bit, 'A PICKUP: the '
                       'health pack there on the guest (the host\'s ROLL)')
        host.put([('hp', 50, 2), ('feet', max(0, z), 2), ('px', x, 2),
                  ('py', y, 2)])
        host.wait_for(lambda: not host.v('wa_pkon') & bit,
                      'A PICKUP: the host takes it', secs=3)
        guest.wait_for(lambda: not guest.v('wa_pkon') & bit,
                       'A PICKUP: gone on the guest too (TAKE)', secs=3)
        host.at(1000, 300, 0)               # (away, then its time all but up)
        host.sy['wa_pkti'] = host.sy['wa_pkt'] + 2 * i
        host.put([('pkti', 2, 2)])
        guest.wait_for(lambda: guest.v('wa_pkon') & bit,
                       'A PICKUP: back on the guest when the host rolls it',
                       secs=4)
    else:
        check(False, 'A PICKUP: no health pack in the arena')

    r = rate(a, 4)
    k = 0 if host is a else 1
    check(max(r) <= 230, 'THE BUDGET, no bots: the host %d, the guest %d '
          'bytes a sim second (2400 baud: 240)' % (r[k], r[1 - k]))

    # FAULTS: garbage, then the cable pulled for three seconds
    stbad = b.sy['lk_blk'] + 28
    before = int.from_bytes(b.readseg(b.seg, stbad, 2), 'little')
    hp0 = b.v('wa_hp', 2)
    cable.inject(1, b'\x7e\x02\x00garbage!!\x7e\x7e\x04\x7d\x5e\x01\x7e')
    Q.pace(b, .5)
    after = int.from_bytes(b.readseg(b.seg, stbad, 2), 'little')
    check(after > before and b.v('wa_hp', 2) == hp0 and b.v('wa_lkon') == 1,
          'FAULTS: garbage dropped and counted (%d -> %d), nothing changed'
          % (before, after))
    cable.enabled = False
    a.wait_for(lambda: a.v('wa_lklost') == 1, 'FAULTS: the cable pulled - '
               'LINK LOST', secs=4)
    cable.enabled = True
    a.wait_for(lambda: a.v('wa_lklost') == 0, 'FAULTS: back - the match '
               'resumes', secs=4)

    # AN OLDER SERIAL.DRV: B told its module has no block verbs - a byte a
    # call, the link the same (SPEC.md 115.1.2's fallback)
    b.sy['wa_lkold'] = b.sy['lk_blk'] + 9
    b.put([('lkold', 1, 1)])
    b.at(1200, 300, 256)
    a.wait_for(lambda: near(a, 1200, 300), 'AN OLDER SERIAL.DRV: B a byte '
               'a call, and A still sees it move', secs=4)
    check(b.v('lk_blk', 10) >> 72 & 0xFF == 1, 'AN OLDER SERIAL.DRV: B '
          'stayed on the fallback')
    b.put([('lkold', 0, 1)])

    # ESC: B leaves; A says so
    b.key('esc')
    b.wait_for(lambda: b.v('wa_lkon') == 0, 'ESC: B back in its window',
               secs=5)
    a.wait_for(lambda: a.v('wa_lkgone') == 1, 'ESC: A says OPPONENT LEFT',
               secs=5)

    # L2: THE HOST'S BOTS - A back in its window too, two bots, again
    a.key('esc')
    a.wait_for(lambda: a.v('wa_lkon') == 0, 'L2: A back in its window too',
               secs=5)
    host.put([('lkbots', 2, 1)])
    for m in (a, b):
        m.wait_for(lambda m=m: m.v('wa_lkps') == 0 and m.v('wa_lkst') == 0,
                   'L2: %s sees the other back in the lobby'
                   % ('A' if m is a else 'B'), secs=6)
    for m in (a, b):
        m.key('spc')
    for m in (a, b):
        m.wait_for(lambda m=m: m.v('wa_lkon') == 1 and m.v('wa_lknb') == 2,
                   'L2: %s in a match with two bots'
                   % ('the host' if m is host else 'the guest'), secs=15)

    def botsmatch():
        hb = [host.fig(i) for i in (1, 2)]
        gb = [guest.fig(i) for i in (1, 2)]
        return all(not g['dead'] and not h['dead'] and
                   abs(g['x'] - h['x']) <= 48 and abs(g['y'] - h['y']) <= 48
                   for g, h in zip(gb, hb)), hb, gb
    guest.wait_for(lambda: botsmatch()[0], 'L2: the host\'s two bots on the '
                   'guest, where the host has them', secs=6)
    _, hb, gb = botsmatch()

    print('   (host %r, guest %r)' % ([(f['x'], f['y']) for f in hb],
                                       [(f['x'], f['y']) for f in gb]))
    # THE GUEST KILLS A BOT: the host's bot 1 stood still before the guest
    host.put([('bdet', 1, 1)])              # (the host's bots on their loops,
    guest.at(1000, 300, 0)                  # not thinking)
    host.at(64, 1024, 0)
    host.setf(1, 16, 0, 2)                  # (alive: the bots fight each
    host.setf(1, 12, 6)                     # other, and it may be down)
    host.setf(1, 10, 0)                     # (no shield)
    host.setf(1, 42, 100)
    for _ in range(12):
        host.freeze(1, 1100, 300)
        host.freeze(2, 64, 1024)            # (bot 2 out of the line of fire)
        Q.pace(host, .25)
        f = guest.fig(1)
        if not f['dead'] and f['x'] in range(1090, 1111):
            break
    kills0 = host.v('wa_kills', 4)
    for _ in range(6):
        host.freeze(1, 1100, 300)
        host.freeze(2, 64, 1024)
        guest.fire()
        if host.fig(1)['dead']:
            break
    if not host.wait_for(lambda: host.fig(1)['dead'] != 0, 'L2: the guest\'s '
                         'pistol kills the host\'s bot 1 (its hits on the '
                         'wire)', secs=3):
        print('   (guest bd %04x hits %d fig1 %r; host bdin %04x fig1 %r '
              'hp %d; guest at %d,%d ang %d)' % (
                  guest.v('wa_lkbd', 2), guest.v('wa_hits', 2), guest.fig(1),
                  host.v('wa_lkbdin', 2), host.fig(1),
                  host.readseg(host.seg, host.sy['wa_figs'] + FS + 42, 1)[0],
                  guest.v('wa_px', 2), guest.v('wa_py', 2),
                  guest.v('wa_ang', 2) >> 6))
    host.wait_for(lambda: host.v('wa_kills', 4) & 0xFF00 == 0x100 and
                  (host.v('wa_deaths', 4) >> 16) & 0xFF == 1,
                  'L2: the host\'s board - the guest\'s kill, bot 1\'s death '
                  '(kills %08x)' % host.v('wa_kills', 4), secs=2)
    guest.wait_for(lambda: guest.v('wa_kills') == 1 and
                   (guest.v('wa_deaths', 4) >> 16) & 0xFF == 1,
                   'L2: the guest\'s board after BSCORE - its kill, bot 1\'s '
                   'death', secs=4)
    # A BOT SHOOTS THE GUEST: the host's bot 2, engaged on figure 0
    host.put([('bdet', 0, 1)])
    guest.at(1000, 300, 0)
    hp0 = guest.v('wa_hp', 2)
    hurt = None
    for _ in range(30):
        host.freeze(2, 1300, 300)
        host.setf(2, 46, 1 | (0 << 8), 3)   # (engaged, no reaction, no gap)
        host.setf(2, 55, 1)                 # (its target: figure 0)
        host.setf(2, 50, 0)                 # (the pistol)
        Q.pace(host, .2)
        if guest.v('wa_hp', 2) < hp0:
            hurt = guest.v('wa_hurtby')
            break
    check(hurt == 3, 'L2: the host\'s bot 2 shoots the guest - hurt on the '
          'guest\'s machine, by bot 2 (hurt by %r)' % hurt)
    # HEARING: the guest's shot, heard by the host's bot 1 roaming 300 off
    # and facing away (it cannot see the guest) - four shots, each heard:
    # the latch, not the muzzle flash a SNAP may or may not land in
    heard = 0
    for _ in range(4):
        host.setf(1, 20, 0, 2)              # (heading east - it turns to
        host.freeze(1, 1300, 300)           # face its heading - and facing
        host.setf(1, 4, 0, 2)               # east: away from the guest)
        host.setf(1, 16, 0, 2)
        host.setf(1, 46, 0)                 # (roaming)
        host.freeze(2, 64, 1024)
        guest.at(1000, 300, 256)            # (firing north, at nothing)
        guest.put([('cool', 0, 1), ('rld', 0, 1), ('wpn', 0, 1),
                   ('mag', 6, 1)])          # (the pistol, loaded)
        guest.key_state('ctrl', True)
        Q.pace(guest, .05)
        guest.key_state('ctrl', False)
        if Q.acted(host, lambda: host.readseg(     # (hunting: it cannot
                host.seg, host.sy['wa_figs'] + FS + 46, 1)[0] == 2,  # see)
                secs=1.5, what='heard'):
            heard += 1
    check(heard == 4, 'HEARING: each of the guest\'s four shots sends the '
          'host\'s bot hunting the guest (%d of 4)' % heard)

    # THE LIFT: the guest on it; the host's lift rises, the guest rides up
    lift = [arenagen.bx(x) for x in arenagen.HEIGHTS_BOXES
            if arenagen.bx(x).kind == arenagen.LIFT][0]
    lx, ly = (lift[0] + lift[2]) // 2, (lift[1] + lift[3]) // 2
    lrest, ltop = host.v('wa_lrest', 2), host.v('wa_ltop', 2)
    hl = lambda m: m.v('wa_bxh', 2) if False else struct.unpack(
        '<h', m.readseg(m.seg, m.sy['wa_bxh'] + m.v('wa_lift', 2), 2))[0]
    host.put([('bdet', 1, 1)])              # (the host's bots off the lift)
    host.at(64, 1024, 0)
    guest.at(lx, ly, 0)
    guest.put([('feet', lrest, 2), ('fpx', 0xFFFF, 2)])
    host.wait_for(lambda: hl(host) == ltop, 'THE LIFT: the guest stands on '
                  'it - the host\'s lift rises to the top (%d)' % ltop,
                  secs=6)
    guest.wait_for(lambda: hl(guest) == ltop and
                   guest.v('wa_feet', 2) >= ltop - 4,
                   'THE LIFT: the guest\'s lift follows, and the guest rides '
                   'it up', secs=4)
    host.put([('bdet', 0, 1)])

    r = rate(a, 4)
    check(max(r) <= 230, 'THE BUDGET, two bots: the host %d, the guest %d '
          'bytes a sim second (2400 baud: 240)' % (r[k], r[1 - k]))


    # THE WIRE
    every = set()
    for k in (0, 1):
        got = list(frames(cable.observed[k]))
        badf = [r for t, r in got if t is None]
        kinds = sorted(set(t for t, _ in got if t))
        every |= set(kinds)
        check(not badf and {1, 3} <= set(kinds),
              'THE WIRE (%s): %d frames, every one valid, of types %r '
              '(bad: %r)' % ('A' if k == 0 else 'B', len(got), kinds,
                             badf[:2]))
    check(every == {1, 2, 3, 4, 5, 6, 7}, 'THE WIRE: HELLO, SNAP, SCORE, '
          'EVENT, HSNAP, GSNAP and BSCORE all crossed (%r)' % sorted(every))


if __name__ == '__main__':
    main()
