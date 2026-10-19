#!/usr/bin/env python3
"""Write RealBoy's SM83 core: build/realboy/rbcore.asm, a 64KB threaded core.

    python3 apps/realboy/rbgen.py build/realboy/rbcore.asm

docs/REALBOY-SPEC.md is the contract (section 4 the layout below),
docs/plans/REALBOY-PLAN.md section 4.1 the design and
apps/realboy/rbdefs.inc the numbers. The core is ONE segment of 256 slots of
256 bytes: opcode X's handler sits at X*256 and the handler for CB X at
X*256+128, so dispatching is three instructions with no table -

    mov dh,[si] / inc si / jmp dx          (DL is always 0 here)

- and each handler ends with its own copy of them. The register map is
rbdefs.inc's: AL = A, AH = F as LAHF lays it out (bit 5 = N), CX = BC,
DI = DE, BX = HL, SI = PC with DS its segment, SP = SP with SS = the view,
BP = M-cycles to the next event.

Why a generator and not NASM macros: 512 handlers fall into a dozen families
whose bodies differ by which 8086 register a Game Boy register lives in, and
D and E live in DI, which has no byte halves. Writing that out by hand is
where a transcription error hides; generating it keeps one rule per family.
The output is assembled by apps/realboy/build.sh and is never committed.

Every handler charges its M-cycles to BP. Only control transfers and HALT
test BP's sign and leave for rbsys's event entry; straight-line code never
does, so an interrupt can be a few instructions late and is never early.
"""
import sys

R8 = ["B", "C", "D", "E", "H", "L", "(HL)", "A"]
X86 = {"B": "ch", "C": "cl", "H": "bh", "L": "bl", "A": "al"}
INVALID = {0xD3, 0xDB, 0xDD, 0xE3, 0xE4, 0xEB, 0xEC, 0xED, 0xF4, 0xFC, 0xFD}


class Slot:
    """One handler's code: an inline body plus out-of-line stubs."""

    def __init__(self):
        self.body = []
        self.tail = []
        self.n = 0
        self.ev = False

    def tag(self):
        self.n += 1
        return "t%d" % self.n

    def a(self, text):
        for line in text.strip("\n").split("\n"):
            self.body.append(line if line.endswith(":") or line.startswith(".")
                             else "    " + line.strip())

    def t(self, text):
        for line in text.strip("\n").split("\n"):
            self.tail.append(line if line.endswith(":") or line.startswith(".")
                             else "    " + line.strip())

    # --- memory ---------------------------------------------------------
    def read8(self, at=0):
        """[BX] -> DH, with ROMX and I/O off the fast path. `at` is the
        M-cycle of the instruction the hardware reads in, counted from 0: a
        register read is answered as of then (REALBOY-SPEC section 6.2)."""
        g = self.tag()
        self.a(f"""
cmp bh,40h
jb .{g}v
cmp bh,80h
jb .{g}s
cmp bh,0FFh
jne .{g}v
cmp bl,80h
jb .{g}s
.{g}v:
mov dh,[ss:bx]
.{g}k:
""")
        if at:
            self.t(f"""
.{g}s:
sub bp,{at}
mov word [ss:S_RET],.{g}r
jmp rd_slow
.{g}r:
add bp,{at}
jmp .{g}k
""")
        else:
            self.t(f"""
.{g}s:
mov word [ss:S_RET],.{g}k
jmp rd_slow
""")

    def write8(self, src, at=0):
        """src -> [BX]; the cartridge and I/O off the fast path. `at` as
        read8's."""
        g = self.tag()
        self.a(f"""
test bh,bh
jns .{g}s
cmp bh,0FFh
jne .{g}v
cmp bl,80h
jb .{g}s
cmp bl,0FFh
je .{g}s
.{g}v:
mov [ss:bx],{src}
.{g}k:
""")
        if at:
            self.t(f"""
.{g}s:
mov [ss:S_WVAL],{src}
sub bp,{at}
mov word [ss:S_RET],.{g}r
jmp wr_slow
.{g}r:
add bp,{at}
jmp .{g}k
""")
        else:
            self.t(f"""
.{g}s:
mov [ss:S_WVAL],{src}
mov word [ss:S_RET],.{g}k
jmp wr_slow
""")

    def setds(self):
        """DS = the segment SI's region lives in (ROMX for 4000-7FFF)."""
        g = self.tag()
        self.a(f"""
mov ds,[ss:S_VIEW]
mov dx,si
and dx,0C000h
cmp dh,40h
jne .{g}d
mov ds,[ss:S_ROMX]
.{g}d:
""")

    def cyc(self, n):
        self.a("sub bp,%d" % n)

    def check(self):
        self.a("js .ev")
        self.ev = True

    def disp(self):
        self.a("DISPATCH")

    def text(self):
        out = list(self.body)
        out += self.tail
        if self.ev:
            out += [".ev:", "    jmp far [ss:S_EVVEC]"]
        return out


# --- register access ---------------------------------------------------------
# D and E live in DI. To read one, copy DI to DX and use DH/DL; to write one,
# do the same and copy back. Either way DL must be 0 again before DISPATCH.

def get8(s, r):
    """Return an 8086 byte register holding Game Boy register r."""
    if r in X86:
        return X86[r]
    s.a("mov dx,di")
    return "dh" if r == "D" else "dl"


def put8(s, r, src):
    """Game Boy register r = src (an 8086 byte register or [si])."""
    if r in X86:
        s.a("mov %s,%s" % (X86[r], src))
        return
    half = "dh" if r == "D" else "dl"
    if src in ("dh", "dl"):                         # DX is not D:E here
        s.a("mov [ss:S_TMP],di")
        s.a("mov [ss:S_TMP+%d],%s" % (1 if r == "D" else 0, src))
        s.a("mov di,[ss:S_TMP]")
        return
    s.a("mov dx,di")
    s.a("mov %s,%s" % (half, src))
    s.a("mov di,dx")


def zdl(s):
    s.a("xor dl,dl")


# --- the ALU -----------------------------------------------------------------
def alu(s, op, src):
    """A = A op src, with F. src is an 8086 operand."""
    if op == 0:
        s.a(f"add al,{src}\nlahf")
    elif op == 1:
        s.a(f"sahf\nadc al,{src}\nlahf")
    elif op == 2:
        s.a(f"sub al,{src}\nlahf\nor ah,20h")
    elif op == 3:
        s.a(f"sahf\nsbb al,{src}\nlahf\nor ah,20h")
    elif op == 4:
        s.a(f"and al,{src}\nlahf\nand ah,40h\nor ah,10h")
    elif op == 5:
        s.a(f"xor al,{src}\nlahf\nand ah,40h")
    elif op == 6:
        s.a(f"or al,{src}\nlahf\nand ah,40h")
    elif op == 7:
        s.a(f"cmp al,{src}\nlahf\nor ah,20h")


def incdec8(s, reg, dec):
    s.a(f"sahf\n{'dec' if dec else 'inc'} {reg}\nlahf")
    if dec:
        s.a("or ah,20h")


COND = {0: ("jz", "jnz"), 1: ("jnz", "jz"), 2: ("jc", "jnc"), 3: ("jnc", "jc")}
# COND[cc] = (skip-if, take-if) after SAHF: NZ Z NC C


def gen_main(op):
    s = Slot()
    hi, lo = op >> 4, op & 15
    if op == 0xDD:                                  # the dispatch stub's slot
        return s
    if op in INVALID:
        s.a(f"""
mov byte [ss:S_BADOP],{op}
mov byte [ss:S_EXIT],RBX_BADOP
dec si
jmp far [ss:S_EVVEC]
""")
        return s
    if op == 0x00:                                  # NOP
        # NOP checks for events though it is not a branch: a game that has
        # crashed runs off into zeroed memory, and a core that never checks
        # never gives the host its machine back (REALBOY-SPEC section 6).
        s.cyc(1); s.check(); s.disp()
    elif op in (0x01, 0x11, 0x21, 0x31):            # LD rr,nn
        rr = {0x01: "cx", 0x11: "di", 0x21: "bx", 0x31: "sp"}[op]
        s.a(f"mov {rr},[si]\nadd si,2"); s.cyc(3); s.disp()
    elif op in (0x02, 0x12, 0x0A, 0x1A):            # LD (BC/DE),A / A,(BC/DE)
        rr = "cx" if op in (0x02, 0x0A) else "di"
        s.a(f"xchg bx,{rr}")
        if op in (0x02, 0x12):
            s.write8("al", 1)
        else:
            s.read8(1); s.a("mov al,dh")
        s.a(f"xchg bx,{rr}"); s.cyc(2); s.disp()
    elif op in (0x22, 0x32, 0x2A, 0x3A):            # (HL+/-)
        if op in (0x22, 0x32):
            s.write8("al", 1)
        else:
            s.read8(1); s.a("mov al,dh")
        s.a("inc bx" if op in (0x22, 0x2A) else "dec bx")
        s.cyc(2); s.disp()
    elif op in (0x03, 0x13, 0x23, 0x33, 0x0B, 0x1B, 0x2B, 0x3B):
        rr = {0: "cx", 1: "di", 2: "bx", 3: "sp"}[hi]
        s.a(("inc " if lo == 3 else "dec ") + rr); s.cyc(2); s.disp()
    elif lo in (4, 5, 0xC, 0xD) and hi < 4:         # INC/DEC r
        r = R8[hi * 2 + (1 if lo >= 0xC else 0)]
        dec = lo in (5, 0xD)
        if r == "(HL)":
            s.read8(1)
            incdec8(s, "dh", dec)
            s.write8("dh", 2)
            s.cyc(3); zdl(s); s.disp()
        elif r in X86:
            incdec8(s, X86[r], dec); s.cyc(1); s.disp()
        else:
            s.a("mov dx,di")
            incdec8(s, "dh" if r == "D" else "dl", dec)
            s.a("mov di,dx"); zdl(s); s.cyc(1); s.disp()
    elif lo in (6, 0xE) and hi < 4:                 # LD r,n
        r = R8[hi * 2 + (1 if lo == 0xE else 0)]
        if r == "(HL)":
            s.a("mov dh,[si]\ninc si")
            s.write8("dh", 2); zdl(s); s.cyc(3); s.disp()
        elif r in X86:
            s.a(f"mov {X86[r]},[si]\ninc si"); s.cyc(2); s.disp()
        else:
            s.a("mov dx,di")
            s.a(f"mov {'dh' if r == 'D' else 'dl'},[si]")
            s.a("mov di,dx\ninc si"); zdl(s); s.cyc(2); s.disp()
    elif op == 0x07:                                # RLCA
        s.a("rol al,1\nsbb ah,ah\nand ah,1"); s.cyc(1); s.disp()
    elif op == 0x0F:                                # RRCA
        s.a("ror al,1\nsbb ah,ah\nand ah,1"); s.cyc(1); s.disp()
    elif op == 0x17:                                # RLA
        s.a("sahf\nrcl al,1\nsbb ah,ah\nand ah,1"); s.cyc(1); s.disp()
    elif op == 0x1F:                                # RRA
        s.a("sahf\nrcr al,1\nsbb ah,ah\nand ah,1"); s.cyc(1); s.disp()
    elif op == 0x08:                                # LD (nn),SP
        s.a("mov [ss:S_TMP+2],bx\nmov bx,[si]\nadd si,2\nmov dx,sp\nmov [ss:S_TMP+4],dh")
        s.write8("dl", 3)
        s.a("inc bx\nmov dh,[ss:S_TMP+4]")
        s.write8("dh", 4)
        s.a("mov bx,[ss:S_TMP+2]"); zdl(s); s.cyc(5); s.disp()
    elif op in (0x09, 0x19, 0x29, 0x39):            # ADD HL,rr
        if op == 0x09:
            s.a("mov dh,ah\nadd bl,cl\nadc bh,ch")
        elif op == 0x29:
            s.a("mov dh,ah\nadd bl,bl\nadc bh,bh")
        else:
            s.a("mov dx,%s\nadd bl,dl\nadc bh,dh\nmov dh,ah" % ("di" if op == 0x19 else "sp"))
        s.a("lahf\nand ah,11h\nand dh,40h\nor ah,dh"); zdl(s); s.cyc(2); s.disp()
    elif op == 0x10:                                # STOP
        s.a("inc si\nmov byte [ss:S_EXIT],RBX_STOP"); s.cyc(1)
        s.a("jmp far [ss:S_EVVEC]")
    elif op == 0x18:                                # JR e
        jr_taken(s)
    elif op in (0x20, 0x28, 0x30, 0x38):            # JR cc,e
        skip, _ = COND[(op >> 3) & 3]
        s.a(f"sahf\n{skip} .nt")
        jr_taken(s)
        s.t(".nt:\ninc si")
        s.t("    sub bp,2")
        s.tail.append("    js .ev")
        s.tail.append("    DISPATCH")
    elif op == 0x27:                                # DAA
        s.a("mov word [ss:S_RET],.k\njmp daa_tail\n.k:"); s.cyc(1); s.disp()
    elif op == 0x2F:                                # CPL
        s.a("not al\nor ah,30h"); s.cyc(1); s.disp()
    elif op == 0x37:                                # SCF
        s.a("and ah,40h\nor ah,1"); s.cyc(1); s.disp()
    elif op == 0x3F:                                # CCF
        s.a("xor ah,1\nand ah,41h"); s.cyc(1); s.disp()
    elif op == 0x76:                                # HALT
        s.cyc(1)
        # THE HALT BUG: with IME clear and an interrupt already pending, HALT
        # does not halt, and the byte after it is read twice - the next
        # opcode runs with PC still on itself (REALBOY-SPEC section 7).
        s.a("""cmp byte [ss:S_IME],0
jne .h
mov dl,[ss:0FFFFh]
and dl,[ss:0FF0Fh]
and dl,1Fh
jz .h
xor dl,dl
mov dh,[si]
jmp dx
.h:
mov byte [ss:S_HALT],1
jmp far [ss:S_EVVEC]""")
    elif 0x40 <= op < 0x80:                         # LD r,r'
        d, r = R8[(op >> 3) & 7], R8[op & 7]
        if r == "(HL)":
            s.read8(1); put8(s, d, "dh"); zdl(s); s.cyc(2); s.disp()
        elif d == "(HL)":
            src = get8(s, r)
            s.write8(src, 1); zdl(s); s.cyc(2); s.disp()
        else:
            if d == r:
                pass
            elif r in X86 and d in X86:
                s.a(f"mov {X86[d]},{X86[r]}")
            elif r in X86:
                put8(s, d, X86[r])
            elif d in X86:
                src = get8(s, r)
                s.a(f"mov {X86[d]},{src}")
            else:                                   # D <-> E
                s.a("mov dx,di")
                s.a("mov dh,dl" if d == "D" else "mov dl,dh")
                s.a("mov di,dx")
            if "D" in (d, r) or "E" in (d, r):
                zdl(s)
            s.cyc(1); s.disp()
    elif 0x80 <= op < 0xC0:                         # ALU A,r
        aop, r = (op >> 3) & 7, R8[op & 7]
        if r == "(HL)":
            s.read8(1); alu(s, aop, "dh"); zdl(s); s.cyc(2)
        else:
            src = get8(s, r)
            alu(s, aop, src)
            if r in ("D", "E"):
                zdl(s)
            s.cyc(1)
        s.disp()
    elif lo in (6, 0xE) and hi >= 0xC:              # ALU A,n
        aop = (hi - 0xC) * 2 + (1 if lo == 0xE else 0)
        alu(s, aop, "byte [si]")
        s.a("inc si"); s.cyc(2); s.disp()
    elif op in (0xC1, 0xD1, 0xE1):                  # POP rr
        s.a("pop " + {0xC1: "cx", 0xD1: "di", 0xE1: "bx"}[op]); s.cyc(3); s.disp()
    elif op == 0xF1:                                # POP AF
        s.a(f"""
pop dx
mov al,dh
mov [ss:S_TMP],bx
mov bh,RB_F2AH>>8
mov bl,dl
mov ah,[ss:bx]
mov bx,[ss:S_TMP]
""")
        zdl(s); s.cyc(3); s.disp()
    elif op in (0xC5, 0xD5, 0xE5):                  # PUSH rr
        s.a("push " + {0xC5: "cx", 0xD5: "di", 0xE5: "bx"}[op]); s.cyc(4); s.disp()
    elif op == 0xF5:                                # PUSH AF
        s.a(f"""
mov dx,bx
mov bh,RB_AH2F>>8
mov bl,ah
mov bl,[ss:bx]
mov bh,al
push bx
mov bx,dx
""")
        zdl(s); s.cyc(4); s.disp()
    elif op in (0xC3, 0xC2, 0xCA, 0xD2, 0xDA):      # JP (cc,)nn
        if op != 0xC3:
            skip, _ = COND[(op >> 3) & 3]
            s.a(f"sahf\n{skip} .nt")
            s.t(".nt:\nadd si,2")
            s.t("    sub bp,3")
            s.tail.append("    js .ev")
            s.tail.append("    DISPATCH")
        s.a("mov si,[si]"); s.setds(); s.cyc(4); s.check(); s.disp()
    elif op == 0xE9:                                # JP HL
        s.a("mov si,bx"); s.setds(); s.cyc(1); s.check(); s.disp()
    elif op in (0xCD, 0xC4, 0xCC, 0xD4, 0xDC):      # CALL (cc,)nn
        if op != 0xCD:
            skip, _ = COND[(op >> 3) & 3]
            s.a(f"sahf\n{skip} .nt")
            s.t(".nt:\nadd si,2")
            s.t("    sub bp,3")
            s.tail.append("    js .ev")
            s.tail.append("    DISPATCH")
        s.a("mov dx,[si]\nadd si,2\npush si\nmov si,dx")
        s.setds(); s.cyc(6); s.check(); s.disp()
    elif op in (0xC9, 0xC0, 0xC8, 0xD0, 0xD8):      # RET (cc)
        if op != 0xC9:
            skip, _ = COND[(op >> 3) & 3]
            s.a(f"sahf\n{skip} .nt")
            s.t(".nt:\nsub bp,2")
            s.tail.append("    js .ev")
            s.tail.append("    DISPATCH")
        s.a("pop si"); s.setds(); s.cyc(4 if op == 0xC9 else 5); s.check(); s.disp()
    elif op == 0xD9:                                # RETI
        s.a("pop si"); s.setds()
        s.a("mov byte [ss:S_IME],1"); s.cyc(4)
        s.a("jmp far [ss:S_EVVEC]")
    elif lo in (7, 0xF) and hi >= 0xC:              # RST
        vec = (hi - 0xC) * 0x10 + (8 if lo == 0xF else 0)
        s.a(f"push si\nmov si,{vec}\nmov ds,[ss:S_VIEW]"); s.cyc(4); s.check(); s.disp()
    elif op == 0xCB:                                # the CB page
        s.a("mov dh,[si]\ninc si\nmov dl,80h\njmp dx")
    elif op == 0xE0:                                # LDH (n),A
        s.a(f"""
mov dl,[si]
inc si
cmp dl,80h
jb .io
cmp dl,0FFh
je .io
mov dh,0FFh
xchg bx,dx
mov [ss:bx],al
xchg bx,dx
""")
        zdl(s); s.cyc(3); s.disp()
        s.t(f"""
.io:
mov [ss:S_TMP],bx
mov bh,0FFh
mov bl,dl
mov [ss:S_WVAL],al
sub bp,2                    ; the write is the third M-cycle's
mov word [ss:S_RET],.k
jmp io_wr
.k:
mov bx,[ss:S_TMP]
xor dl,dl
sub bp,1
""")
        s.tail.append("    DISPATCH")
    elif op == 0xF0:                                # LDH A,(n)
        s.a(f"""
mov dl,[si]
inc si
cmp dl,80h
jb .io
mov dh,0FFh
xchg bx,dx
mov al,[ss:bx]
xchg bx,dx
""")
        zdl(s); s.cyc(3); s.disp()
        s.t(f"""
.io:
mov [ss:S_TMP],bx
mov bh,0FFh
mov bl,dl
sub bp,2                    ; the read is the third M-cycle's
mov word [ss:S_RET],.k
jmp io_rd
.k:
mov al,dh
mov bx,[ss:S_TMP]
xor dl,dl
sub bp,1
""")
        s.tail.append("    DISPATCH")
    elif op == 0xE2:                                # LD (C),A
        s.a("mov [ss:S_TMP],bx\nmov bh,0FFh\nmov bl,cl")
        s.write8("al", 1)
        s.a("mov bx,[ss:S_TMP]"); zdl(s); s.cyc(2); s.disp()
    elif op == 0xF2:                                # LD A,(C)
        s.a("mov [ss:S_TMP],bx\nmov bh,0FFh\nmov bl,cl")
        s.read8(1)
        s.a("mov al,dh\nmov bx,[ss:S_TMP]"); zdl(s); s.cyc(2); s.disp()
    elif op == 0xEA:                                # LD (nn),A
        s.a("mov [ss:S_TMP],bx\nmov bx,[si]\nadd si,2")
        s.write8("al", 3)
        s.a("mov bx,[ss:S_TMP]"); zdl(s); s.cyc(4); s.disp()
    elif op == 0xFA:                                # LD A,(nn)
        s.a("mov [ss:S_TMP],bx\nmov bx,[si]\nadd si,2")
        s.read8(3)
        s.a("mov al,dh\nmov bx,[ss:S_TMP]"); zdl(s); s.cyc(4); s.disp()
    elif op in (0xE8, 0xF8):                        # ADD SP,e / LD HL,SP+e
        s.a("mov dl,[si]\ninc si\ncmp dl,80h\ncmc\nsbb dh,dh")
        if op == 0xE8:
            s.a("mov [ss:S_TMP],bx")
        s.a("mov bx,sp\nadd bl,dl\nlahf\nand ah,11h\nmov bx,sp\nadd bx,dx")
        if op == 0xE8:
            s.a("mov sp,bx\nmov bx,[ss:S_TMP]"); zdl(s); s.cyc(4)
        else:
            zdl(s); s.cyc(3)
        s.disp()
    elif op == 0xF9:                                # LD SP,HL
        s.a("mov sp,bx"); s.cyc(2); s.disp()
    elif op == 0xF3:                                # DI
        s.a("mov byte [ss:S_IME],0"); s.cyc(1); s.disp()
    elif op == 0xFB:                                # EI
        s.a("mov byte [ss:S_IME],1\nmov word [ss:S_RET],.k\njmp force_ev\n.k:")
        s.cyc(1); s.disp()
    else:
        raise SystemExit("rbgen: no handler for opcode %02X" % op)
    return s


def jr_taken(s):
    """SI += signed operand; a JR of -4..-16 may close a spin-wait."""
    s.a(f"""
mov dl,[si]
inc si
cmp dl,80h
cmc
sbb dh,dh
add si,dx
%ifndef RB_TRACE
cmp dx,0FFF0h               ; a trace runs every iteration: no idle skip,
jae .mb                     ; so it can be diffed against a reference
%endif
.fw:
xor dl,dl
""")
    s.cyc(3); s.check(); s.disp()
    s.t("""
.mb:
cmp dx,0FFFCh
ja .fw
cmp si,[ss:S_IDLENO]
je .fw
mov word [ss:S_RET],.fw
jmp idle_chk
""")


def gen_cb(op):
    s = Slot()
    grp, y, r = op >> 6, (op >> 3) & 7, R8[op & 7]
    mem = r == "(HL)"
    if mem:
        s.read8(2)
        reg = "dh"
    elif r in X86:
        reg = X86[r]
    else:
        s.a("mov dx,di")
        reg = "dh" if r == "D" else "dl"
    if grp == 0:                                    # rotates and shifts
        if y == 0:
            s.a(f"rol {reg},1")
        elif y == 1:
            s.a(f"ror {reg},1")
        elif y == 2:
            s.a(f"sahf\nrcl {reg},1")
        elif y == 3:
            s.a(f"sahf\nrcr {reg},1")
        elif y == 4:
            s.a(f"shl {reg},1")
        elif y == 5:
            s.a(f"sar {reg},1")
        elif y == 6:                                # SWAP: four rotates, C = 0
            s.a(f"rol {reg},1\nrol {reg},1\nrol {reg},1\nrol {reg},1\nclc")
        else:
            s.a(f"shr {reg},1")
        s.a(f"sbb ah,ah\nand ah,1\ntest {reg},{reg}\njnz .nz\nor ah,40h\n.nz:")
    elif grp == 1:                                  # BIT y,r
        s.a(f"and ah,1\nor ah,10h\ntest {reg},{1 << y}\njnz .nz\nor ah,40h\n.nz:")
    elif grp == 2:                                  # RES
        s.a(f"and {reg},{(~(1 << y)) & 0xFF}")
    else:                                           # SET
        s.a(f"or {reg},{1 << y}")
    if grp != 1:
        if mem:
            s.write8("dh", 3)
        elif r in ("D", "E"):
            s.a("mov di,dx")
    zdl(s)
    s.cyc((3 if grp == 1 else 4) if mem else 2)
    s.disp()
    return s


# --- the shared tails, placed after a main half with room: an invalid -----
# --- opcode's, or a short handler's (idle_tst follows PUSH HL) --------------
TAILS = {
    0xD3: """
; [BX] for an address the fast path does not take: ROMX or an I/O register.
; Resumes at [S_RET] with the byte in DH.
rd_slow:
    cmp bh,80h
    jae .io
    mov es,[ss:S_ROMX]
    mov dh,[es:bx]
    jmp word [ss:S_RET]
.io:
    jmp io_rd
; [BX] = [S_WVAL] for the cartridge's registers (0000-7FFF) or an I/O one.
wr_slow:
    test bh,bh
    js .io
    jmp mbc_wr
.io:
    jmp io_wr
""",
    0xDB: """
; Make the next event check fire: t_next -= BP (signed), BP = 0. Resumes at
; [S_RET]. EI uses it so a pending interrupt is taken at the next check.
force_ev:
    mov dx,bp
    or dx,dx
    js .neg
    sub [ss:S_TNEXT],dx
    sbb word [ss:S_TNEXT+2],0
    jmp short .z
.neg:
    sub [ss:S_TNEXT],dx
    sbb word [ss:S_TNEXT+2],-1
.z:
    xor bp,bp
    xor dl,dl
    jmp word [ss:S_RET]
""",
    0xDD: """
; The dispatch stub rbsys enters the core through (S_DISP = DD00h). DD is
; not an SM83 opcode; a game that executes one simply runs on.
RB_DISPATCH:
    mov dh,[si]
    inc si
    jmp dx
; A cartridge write, BX = 0000-7FFF. A ROM bank switch on an MBC1, MBC3 or
; MBC5 is done here, exactly as rb_mbcwrite and rb_setbank do it; the core's
; DS moves with the bank when the game runs from 4000-7FFF.
mbc_wr:
    cmp bh,20h
    jb .host
    cmp bh,40h
    jae .host
    cmp byte [ss:S_BANKHI],0    ; the high bits: rbsys's
    jne .host
    mov dl,[ss:S_MBC]
    cmp dl,RBM_MBC1
    je .m1
    cmp dl,RBM_MBC3
    je .m3
    cmp dl,RBM_MBC5
    jne .host
    cmp bh,30h
    jae .host
    mov dl,[ss:S_WVAL]
    jmp short .set
.m3:
    mov dl,[ss:S_WVAL]
    and dl,7Fh
    jmp short .nz
.m1:
    mov dl,[ss:S_WVAL]
    and dl,1Fh
.nz:
    jnz .set
    inc dl
.set:
    jmp mbc_set
.host:
    jmp far [ss:S_MBCVEC]
""",
    0xE3: """
; DAA, the SM83's own rule (it is not the 8086's: after a subtraction the
; SM83 looks at the flags only, never at the value). Resumes at [S_RET].
daa_tail:
    test ah,RBF_N
    jnz .sub
    test ah,RBF_C
    jnz .hi
    cmp al,99h
    jbe .lo
.hi:
    add al,60h
    or ah,RBF_C
.lo:
    test ah,RBF_H
    jnz .six
    mov dh,al
    and dh,0Fh
    cmp dh,9
    jbe .done
.six:
    add al,6
    jmp short .done
.sub:
    test ah,RBF_C
    jz .s1
    sub al,60h
.s1:
    test ah,RBF_H
    jz .done
    sub al,6
.done:
    and ah,RBF_N|RBF_C
    or al,al
    jnz .nz
    or ah,RBF_Z
.nz:
    xor dl,dl
    jmp word [ss:S_RET]
""",
    0xE4: """
; A taken backward JR of -4 to -16 to a loop head not already known to be
; busy. The loop is a SPIN-WAIT, and costs nothing, when its body is one
; read of RAM and then only tests of what it read and conditional JRs - back
; to the head, or forward out of the loop: nothing in it can change what it
; reads until an interrupt does, so every pass takes the same path, and an
; interrupt is an event (docs/plans/REALBOY-PLAN.md 4.1). Kirby's is a read
; and TWO tests, each with its own JR NZ back: LDH A,(8C) / BIT 5,A / JR NZ /
; BIT 6,A / JR NZ,-10. In: SI = the loop head, DX = the displacement. Resumes at [S_RET],
; or leaves for the event entry with S_IDLE set.
idle_chk:
    neg dx
    sub dx,2
    mov dh,dl                   ; DH = the body's length
    mov dl,[si]
    cmp dl,0FAh
    je .fa
    cmp dl,0F0h
    jne idle_hl
    cmp byte [si+1],80h         ; LDH A,(n) of HRAM, never an I/O register
    jb idle_no
    mov dl,2                    ; the tests start after the 2-byte read
    jmp idle_tst
.fa:
    mov dl,[si+2]               ; LD A,(nn) of WRAM or HRAM
    cmp dl,0C0h
    jb idle_no
    cmp dl,0FFh
    jne .fa1
    cmp byte [si+1],80h
    jb idle_no
.fa1:
    mov dl,3                    ; ...the 3-byte one
    jmp idle_tst
""",
    0xED: """
; The two (HL) shapes: LD A,(HL) and a test of A, or BIT b,(HL) alone - Kirby
; waits on BIT 6,(HL) / JR NZ,-4. HL (BX) must be WRAM or HRAM, where
; nothing but the CPU writes; the loop never changes it.
idle_hl:
    cmp bh,0C0h
    jb idle_no
    cmp bh,0FFh
    jne .ram
    cmp bl,80h
    jb idle_no
.ram:
    cmp dl,7Eh                  ; LD A,(HL)
    je .ld
    cmp dl,0CBh                 ; BIT b,(HL), and nothing else
    jne idle_no
    cmp dh,2
    jne idle_no
    mov dl,[si+1]
    and dl,0C7h
    cmp dl,46h
    jne idle_no
    jmp idle_yes
.ld:
    mov dl,1                    ; the tests start after LD A,(HL)
    jmp idle_tst
""",
    0xF4: """
; An I/O register read, BX = FF00-FF7F, answered in DH and resumed at [S_RET].
; The joypad, STAT and LY are answered here, which is most of what a game
; reads (Super Mario Land polls STAT 28 times a frame); everything else is
; rbsys's, on the far side of a stack switch. Each answer is exactly
; rb_ioread's.
io_rd:
    cmp bl,41h
    je io_lcd
    cmp bl,44h
    je io_lcd
    or bl,bl
    jnz .host
    mov dh,[ss:0FF00h]          ; P1: C0 | select | the four lines, 0 = held
    or dh,0CFh                  ;   and selected
    test dh,10h
    jnz .btn
    mov dl,[ss:S_JOY]           ; P14 low: the directions
    not dl
    or dl,0F0h
    and dh,dl
.btn:
    test dh,20h
    jnz .done
    mov dl,[ss:S_JOY]           ; P15 low: the buttons
    shr dl,1
    shr dl,1
    shr dl,1
    shr dl,1
    not dl
    or dl,0F0h
    and dh,dl
.done:
    xor dl,dl
    jmp word [ss:S_RET]
.host:
    jmp far [ss:S_IORVEC]
""",
    0xFC: """
; STAT (BL = 41h) or LY (BL = 44h), from the frame-relative clock rbsys keeps
; in S_TNF: the PPU's place now is S_TNF - BP, modulo a frame. With the LCD
; off, LY is 0 and STAT is its fixed part, mode 0.
io_lcd:
    mov [ss:S_SAVAX],ax
    mov dh,[ss:0FF41h]
    and dh,78h
    or dh,80h
    xor al,al
    cmp byte [ss:S_LCDON],0
    je .done
    mov ax,[ss:S_TNF]
    sub ax,bp
.wrap:
    cmp ax,RB_FRAME
    jb .in
    sub ax,RB_FRAME
    jmp short .wrap
.in:
    mov dl,RB_LINE
    div dl                      ; AL = LY, AH = M-cycles into the line
    cmp al,[ss:0FF45h]
    jne .nc
    or dh,04h
.nc:
    cmp al,144
    jb .vis
    or dh,1                     ; mode 1
    jmp short .done
.vis:
    cmp ah,20
    jae .m3
    or dh,2                     ; mode 2
    jmp short .done
.m3:
    cmp ah,RB_HBL
    jae .done                   ; mode 0
    or dh,3                     ; mode 3
.done:
    cmp bl,44h
    jne .out
    mov dh,al
.out:
    mov ax,[ss:S_SAVAX]
    xor dl,dl
    jmp word [ss:S_RET]
""",
    0xFD: """
; An I/O write, BX = FF00-FF7F or FFFF, [S_WVAL] the byte, resumed at
; [S_RET]. The joypad's select and the sound registers, which have no side
; effect yet, are stored here, and FF4C-FF7F - nothing on a DMG - is ignored;
; the rest is rbsys's.
io_wr:
    mov dl,[ss:S_WVAL]
    or bl,bl
    jnz .snd
    and dl,30h
    or dl,0C0h
    jmp short .st
.snd:
    cmp bl,10h
    jb .host
    cmp bl,40h
    jb .st
    cmp bl,4Ch
    jb .host
    cmp bl,0FFh
    je .host
    jmp short .z                ; FF4C-FF7F: nothing on a DMG, reads FF
.st:
    mov [ss:bx],dl
.z:
    xor dl,dl
    jmp word [ss:S_RET]
.host:
    jmp far [ss:S_IOWVEC]
""",
    0xE5: """
; The tests after the read. DL = where they start (from the head, SI), DH =
; where the closing JR is. Each is AND A, OR A, CP n, AND n or BIT b,A, or a
; JR cc that goes back to the head or forward past the closing JR; they must
; end exactly at it. (BIT and JR are checked in POP HL's slot, idle_tbit.)
idle_tst:
    mov [ss:S_SAVCX],cx
    mov [ss:S_SAVBX],bx
    mov cx,dx                   ; CL = the place, CH = the closing JR's
    xor bh,bh
    cmp cl,ch                   ; a read and no test: not a wait
    jae idle_tno
idle_tn:
    mov bl,cl
    mov dl,[si+bx]
    cmp dl,0A7h                 ; AND A
    je idle_t1
    cmp dl,0B7h                 ; OR A
    je idle_t1
    cmp dl,0FEh                 ; CP n
    je idle_t2
    cmp dl,0E6h                 ; AND n
    je idle_t2
    jmp idle_tbit
idle_t2:
    inc cl
idle_t1:
    inc cl
    cmp cl,ch
    jb idle_tn
    je idle_tyes
idle_tno:
    mov cx,[ss:S_SAVCX]
    mov bx,[ss:S_SAVBX]
    jmp idle_no
idle_tyes:
    mov cx,[ss:S_SAVCX]
    mov bx,[ss:S_SAVBX]
    jmp idle_yes
""",
    0xE1: """
; idle_tst's BIT b,A and JR cc, DL = the byte at the place
idle_tbit:
    cmp dl,0CBh
    jne .jr
    mov dl,[si+bx+1]            ; BIT b,A
    and dl,0C7h
    cmp dl,47h
    je idle_t2
    jmp idle_tno
.jr:
    and dl,0E7h                 ; JR NZ, Z, NC, C
    cmp dl,20h
    jne .no
    mov dl,[si+bx+1]
    add dl,cl
    add dl,2                    ; where it goes, from the head
    jz .ok                      ; the head
    js .no                      ; behind it
    mov dh,ch
    add dh,2
    cmp dl,dh                   ; past the closing JR: out of the loop
    jb .no
.ok:
    jmp idle_t2
.no:
    jmp idle_tno
""",
    0xEC: """
idle_yes:
    mov byte [ss:S_IDLE],1
    mov [ss:S_IDLEPC],si
    xor dl,dl
    sub bp,3
    jmp far [ss:S_EVVEC]
idle_no:
    mov [ss:S_IDLENO],si
    xor dl,dl
    jmp word [ss:S_RET]
; mbc_wr's second half: DL = the bank number written.
mbc_set:
    mov [ss:S_BANK],dl
    and dl,[ss:S_BMASK]
    mov dh,dl                   ; ROMX = ROMSEG + bank * 400h - 400h
    xor dl,dl
    shl dx,1
    shl dx,1
    add dx,[ss:S_ROMSEG]
    sub dx,400h
    mov es,dx
    mov dx,ds
    cmp dx,[ss:S_ROMX]
    mov dx,es
    jne mbc_set.nx
    mov ds,dx
mbc_set.nx:
    mov [ss:S_ROMX],dx
    xor dl,dl
    jmp word [ss:S_RET]
""",
}


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "build/realboy/rbcore.asm"
    L = []
    L.append("; GENERATED by apps/realboy/rbgen.py - do not edit, regenerate.")
    L.append("cpu 8086")
    L.append("bits 16")
    L.append("org 0")
    L.append('%include "rbdefs.inc"')
    L.append("%macro DISPATCH 0")
    L.append("%ifdef RB_TRACE")
    L.append("    jmp far [ss:S_TRACEVEC]")
    L.append("%else")
    L.append("    mov dh,[si]")
    L.append("    inc si")
    L.append("    jmp dx")
    L.append("%endif")
    L.append("%endmacro")
    for op in range(256):
        L.append("    times %d-($-$$) db 0CCh" % (op * 256))
        L.append("op_%02X:" % op)
        L += gen_main(op).text()
        if op in TAILS:
            L += TAILS[op].strip("\n").split("\n")
        L.append("    times %d-($-$$) db 0CCh" % (op * 256 + 128))
        L.append("cb_%02X:" % op)
        L += gen_cb(op).text()
    L.append("    times 65536-($-$$) db 0CCh")
    with open(out, "w") as f:
        f.write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
