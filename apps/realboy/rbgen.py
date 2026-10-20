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
import re
import sys

R8 = ["B", "C", "D", "E", "H", "L", "(HL)", "A"]
X86 = {"B": "ch", "C": "cl", "H": "bh", "L": "bl", "A": "al"}
INVALID = {0xD3, 0xDB, 0xDD, 0xE3, 0xE4, 0xEB, 0xEC, 0xED, 0xF4, 0xFC, 0xFD}


JIT = False     # template_lines() sets it: memory accesses laid out for a
                # TEMPLATE, where nothing jumps away at the end - the slow
                # stub first and the fast access last, so the fast path takes
                # one jump and none over the stub (REALBOY-SPEC section 16.6)


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
        if JIT:
            self.a(f"""
cmp bh,40h
jb .{g}v
cmp bh,80h
jb .{g}s
cmp bh,0FFh
jne .{g}v
cmp bl,80h
jae .{g}v
.{g}s:
""")
            if at:                              # (rd_sw takes BP back by
                self.a(f"""
mov word [ss:S_RET],.{g}k
jmp rd_s{at}
""")                                            #   at around rd_slow)
            else:
                self.a(f"""
mov word [ss:S_RET],.{g}k
jmp rd_slow
""")
            self.a(f"""
.{g}v:
mov dh,[ss:bx]
.{g}k:
""")
            return
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
        if JIT:
            self.a(f"""
test bh,bh
jns .{g}s
cmp bh,0FFh
jne .{g}v
cmp bl,80h
jb .{g}s
cmp bl,0FFh
jne .{g}v
.{g}s:
mov [ss:S_WVAL],{src}
""")
            if at:                              # (wr_sw, as rd_sw)
                self.a(f"""
mov word [ss:S_RET],.{g}k
jmp wr_s{at}
""")
            else:
                self.a(f"""
mov word [ss:S_RET],.{g}k
jmp wr_slow
""")
            self.a(f"""
.{g}v:
mov [ss:bx],{src}
.{g}k:
""")
            return
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
    if src in ("dh", "dl"):                         # DX is not D:E here: the
        if src != half:                             #   other half of DI kept,
            s.a("mov %s,%s" % (half, src))          #   in registers (ten bytes,
        s.a("and di,%s" % ("00FFh" if r == "D" else "0FF00h"))  # not fifteen
        s.a("mov dl,0" if r == "D" else "xor dh,dh")    # through S_TMP; not
        s.a("or di,dx")                             #   xor dl,dl, which a
                                                    #   template drops)
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
        s.a("mov [ss:S_TMP2],bx\nmov bx,[si]\nadd si,2\nmov dx,sp\nmov [ss:S_TMP4],dh")
        s.write8("dl", 3)
        s.a("inc bx\nmov dh,[ss:S_TMP4]")
        s.write8("dh", 4)
        s.a("mov bx,[ss:S_TMP2]"); zdl(s); s.cyc(5); s.disp()
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
    elif op == 0xE2 and JIT:                        # LD (C),A, translated:
        s.a("""
cmp cl,80h                  ; HRAM is one store through SS; I/O and IE the
jb .s                       ;   general path, which guards itself as the
cmp cl,0FFh                 ;   rest of SELFGUARD's do (and cannot reach the
jne .v                      ;   MBC, so SI alone says whether to leave)
.s:
mov [ss:S_TMP],bx
mov bh,0FFh
mov bl,cl
mov si,IMM16
mov [ss:S_WVAL],al
mov word [ss:S_RET],.r
jmp wr_s1
.r:
mov bx,[ss:S_TMP]
cmp si,IMM16
je .k
sub bp,2
jmp tr_enter
.v:
mov si,cx
and si,00FFh
mov [ss:si+0FF00h],al
.k:
sub bp,2""")
    elif op == 0xE2:                                # LD (C),A
        s.a("mov [ss:S_TMP],bx\nmov bh,0FFh\nmov bl,cl")
        s.write8("al", 1)
        s.a("mov bx,[ss:S_TMP]"); zdl(s); s.cyc(2); s.disp()
    elif op == 0xF2 and JIT:                        # LD A,(C), translated:
        s.a("""
cmp cl,80h                  ; HRAM (and IE) is one load through SS; I/O
jae .v                      ;   the general path
mov [ss:S_TMP],bx
mov bh,0FFh
mov bl,cl
mov word [ss:S_RET],.r
jmp rd_s1
.r:
mov al,dh
mov bx,[ss:S_TMP]
jmp short .k
.v:
mov si,cx
and si,00FFh
mov al,[ss:si+0FF00h]
.k:
sub bp,2""")
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
ja .cnt
cmp si,[ss:S_IDLENO]
je .fw
mov word [ss:S_RET],.fw
jmp idle_chk
.cnt:
cmp dx,0FFFDh               ; -3: DEC r / JR NZ, a countdown (cnt_ff)?
jne .fw
cmp byte [si+1],20h
jne .fw
mov dl,[si]
mov word [ss:S_RET],.fw
jmp cnt_ff
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
    0x40: """
; tr_enter: the translated block for SI (REALBOY-SPEC section 16.3), or the
; interpreter where there is none - RAM, the translator off or refusing. In:
; SI = PC, DS = its segment, AH = F, every register live. A block is keyed
; by its PC and, in 4000-7FFF, its bank; the table is direct-mapped, 2,048
; of 8 bytes at JIT_HASH in a segment of its own: PC, bank (FF for the rest),
; -, the block's offset there. This tail is copied into that segment too (blocks jump
; to it there), so it leaves by far jumps only.
tr_enter:
    cmp byte [ss:S_JITON],0     ; no translator: the interpreter's own
    jne .on                     ;   dispatch, DS already its (only the
    mov dh,[si]                 ;   core's copy runs with it off)
    inc si
    jmp dx
.on:
    cmp si,8000h                ; RAM: tr_hram
    jae tr_hram
    mov [ss:S_SAVBX],bx
    mov bx,si
    mov dl,0FFh
    cmp bh,40h
    jb tr_ekey
    mov dl,[ss:S_BANK]
    and dl,[ss:S_BMASK]
tr_ekey:
    mov dh,dl
    xor bl,dl
    mov dl,bh                   ; (PC >> 11 folded in: blocks 2KB
    shr dl,1                    ;   apart share no slot)
    shr dl,1
    shr dl,1
    xor bl,dl
    and bh,7
    shl bx,1
    shl bx,1
    shl bx,1
    mov es,[ss:S_JITHSEG]       ; the table (ES is every helper's to load)
    cmp [es:bx+JIT_HASH],si
    jne tr_new
    cmp [es:bx+JIT_HASH+2],dh
    jne tr_new
    mov dx,[es:bx+JIT_HASH+4]   ; the block, in the cache's segment
    or dx,dx
    jz tr_count                 ; ...or not yet: still counting
    mov [ss:S_JITOUT],dx        ;   (S_JITOUT+2), wherever this copy of
    mov bx,[ss:S_SAVBX]         ;   tr_enter is running
    jmp far [ss:S_JITOUT]
""",
    0x41: """
; tr_enter's other half. A PC is TRANSLATED only once it has been entered
; RB_JITHOT times, so code that runs a few times - start-up, a level's
; set-up - is interpreted and never takes the cache's room: its entry counts
; with the offset 0. A new key takes the slot over, counting from 1.
tr_count:
    inc byte [es:bx+JIT_HASH+3]
    cmp byte [es:bx+JIT_HASH+3],RB_JITHOT
    jae tr_miss
    mov bx,[ss:S_SAVBX]
    jmp tr_int
tr_new:
    jmp tr_new2                 ; (slot 48's: it did not fit here)
tr_miss:
    mov dl,[es:bx+JIT_HASH+2]   ; the key this entry counted under (the
    mov [ss:S_JITBK],dl         ;   block's offset has taken DX), and the
    mov [ss:S_JITSLOT],bx       ;   slot it counted in, a neighbour or not
    mov bx,[ss:S_SAVBX]
    mov word [ss:S_RET],tr_back
    mov [ss:S_RETFAR+2],cs       ; rbsys comes back to THIS copy
    jmp far [ss:S_JITVEC]
""",
    0x42: """
; tr_link: tr_enter for an exit that may be CHAINED (REALBOY-SPEC 16.4). DX =
; the exit's `mov dx,SITE / jmp tr_link`: once the target is translated
; those bytes become `jmp near` the block, and the exit never comes here
; again - six of them for a target in bank 0, and eleven for one in
; 4000-7FFF, which checks the bank first and falls onto the exit's own `jmp
; tr_enter` (after the eleven) when it is another.
tr_link:
    mov [ss:S_LINK],dx
    mov [ss:S_SAVBX],bx
    mov bx,si
    mov dl,0FFh
    cmp bh,40h
    jb .k
    mov dl,[ss:S_BANK]
    and dl,[ss:S_BMASK]
.k:
    mov dh,dl
    xor bl,dl
    mov dl,bh                   ; (PC >> 11 folded in: blocks 2KB
    shr dl,1                    ;   apart share no slot)
    shr dl,1
    shr dl,1
    xor bl,dl
    and bh,7
    shl bx,1
    shl bx,1
    shl bx,1
    mov es,[ss:S_JITHSEG]
    cmp [es:bx+JIT_HASH],si
    jne .nb
    cmp [es:bx+JIT_HASH+2],dh
    je .hit
.nb:
    xor bx,8                    ; ...or its neighbour's (16.3)
    cmp [es:bx+JIT_HASH],si
    jne tr_lno
    cmp [es:bx+JIT_HASH+2],dh
    jne tr_lno
.hit:
    mov dx,[es:bx+JIT_HASH+4]
    or dx,dx
    jz tr_lno
    mov [ss:S_JITOUT],dx
    jmp tr_lpatch
tr_lno:
    mov bx,[ss:S_SAVBX]
    jmp tr_enter
""",
    0x44: """
; tr_enter's last part: back from the translator, and the interpreter
tr_back:
    cmp word [ss:S_JITOUT],0
    je tr_int
    jmp far [ss:S_JITOUT]
tr_int:                         ; the interpreter's dispatch, in the CORE
    mov ds,[ss:S_VIEW]          ;   (this may be the cache's copy, 16.2),
    mov dx,si                   ;   with DS for SI: translated code does
    and dh,0C0h                 ;   not keep DS, so its exits do not load
    cmp dh,40h                  ;   it - this is the one place it is needed
    jne .d
    mov ds,[ss:S_ROMX]
.d:
    xor dl,dl
    jmp far [ss:S_DISP]
""",
    0x45: """
; tr_link's patch: six bytes for bank 0, eleven for 4000-7FFF (16.4)
tr_lpatch:
    mov bx,[ss:S_LINK]
    cmp byte [cs:bx],81h        ; a RET's site: cmp si,PC (rt_ret)
    je tr_rpatch
    cmp si,4000h
    jae .bank
    mov byte [cs:bx],0E9h       ; bank 0: the six bytes, jmp near the block
    sub dx,bx
    sub dx,3
    mov [cs:bx+1],dx
.go:
    mov bx,[ss:S_SAVBX]
    jmp far [ss:S_JITOUT]
.bank:                          ; a bank: ELEVEN bytes, cmp byte [ss:S_BANK],
    mov word [cs:bx],8036h      ;   B / jne +3 (onto the exit's own jmp
    mov byte [cs:bx+2],3Eh      ;   tr_enter) / jmp near the block
    mov word [cs:bx+3],S_BANK
    mov dl,[ss:S_BANK]          ; (DX is the block: rebuilt below)
    mov [cs:bx+5],dl
    mov word [cs:bx+6],0375h
    mov byte [cs:bx+8],0E9h
    mov dx,[ss:S_JITOUT]
    sub dx,bx
    sub dx,11
    mov [cs:bx+9],dx
    jmp short .go
""",
    0x49: """
; tr_link for an exit (16.4): T is not in SI - a block's exit sets it only on
; the event's way - but in the exit's own code, the mov si,T after the jmp
; here: SITE + 7, or SITE + 12 after the five spare bytes of one into
; 4000-7FFF
tr_lsite:
    mov si,dx
    cmp byte [cs:si+6],0BEh
    mov si,[cs:si+7]
    je tr_link
    mov si,dx
    mov si,[cs:si+12]
    jmp tr_link
; tr_hram: tr_enter for RAM. HRAM (FF80-FFFE) is translated, its blocks
; guarded (16.3), keyed as bank 0's; the rest of RAM never is
tr_hram:
    cmp si,0FF80h
    jb tr_int
    mov [ss:S_SAVBX],bx
    mov bx,si
    mov dl,0FFh
    jmp tr_ekey
; tr_stale: an HRAM block's guard found its bytes changed (16.3): the
; table's entry for SI counts again from nothing, and the interpreter runs
; the code as it is now
tr_stale:
    mov [ss:S_SAVBX],bx
    mov bx,si
    mov dl,bh
    shr dl,1
    shr dl,1
    shr dl,1
    xor bl,0FFh
    xor bl,dl
    and bh,7
    shl bx,1
    shl bx,1
    shl bx,1
    mov es,[ss:S_JITHSEG]
    cmp [es:bx+JIT_HASH],si
    je .z
    xor bx,8
.z:
    mov word [es:bx+JIT_HASH+2],00FFh
    mov word [es:bx+JIT_HASH+4],0
    mov bx,[ss:S_SAVBX]
    jmp tr_int
""",
    0xEB: """
; A translated access's slow path at M-cycle n of its instruction (rbgen's
; read8 and write8; the interpreter's own calls rd_slow and wr_slow). ROMX
; and the MBC are answered whenever; an I/O register as of M-cycle n, so BP
; goes back by n around io_rd and io_wr and forward by n after - not
; restored, since an I/O write may reschedule it (rb_sched). Shared here,
; the template's slow path is two instructions.
rd_s1:
    cmp bh,80h
    jae .io
    mov es,[ss:S_ROMX]
    mov dh,[es:bx]
    jmp word [ss:S_RET]
.io:
    mov word [ss:S_ATN],1
    jmp short rd_io
rd_s2:
    cmp bh,80h
    jae .io
    mov es,[ss:S_ROMX]
    mov dh,[es:bx]
    jmp word [ss:S_RET]
.io:
    mov word [ss:S_ATN],2
    jmp short rd_io
rd_s3:
    cmp bh,80h
    jae .io
    mov es,[ss:S_ROMX]
    mov dh,[es:bx]
    jmp word [ss:S_RET]
.io:
    mov word [ss:S_ATN],3
rd_io:
    mov word [ss:S_RET2],io_rd
    jmp rw_io
""",
    0x52: """
; wr_s1-4: rd_s1-3's other half (slot EB's), and what they share
wr_s1:
    mov word [ss:S_ATN],1
    jmp short wr_sw
wr_s2:
    mov word [ss:S_ATN],2
    jmp short wr_sw
wr_s3:
    mov word [ss:S_ATN],3
    jmp short wr_sw
wr_s4:
    mov word [ss:S_ATN],4
wr_sw:
    test bh,bh
    js .io
    jmp mbc_wr
.io:
    mov word [ss:S_RET2],io_wr
rw_io:                          ; on to [S_RET2], and back through rw_back
    sub bp,[ss:S_ATN]
    mov [ss:S_DX2],dx
    mov dx,[ss:S_RET]           ; the template's way on, for rw_back
    xchg dx,[ss:S_RET2]
    mov word [ss:S_RET],rw_back
    xchg dx,[ss:S_DX2]          ; DX as it was; S_DX2 = io_rd or io_wr
    jmp word [ss:S_DX2]
rw_back:
    add bp,[ss:S_ATN]
    jmp word [ss:S_RET2]
""",
    0x48: """
; tr_new's half that did not fit slot 41: the neighbour slot (16.3)
tr_new2:
    xor bx,8                    ; the slot's NEIGHBOUR (16.3): two hot PCs
    cmp [es:bx+JIT_HASH],si     ;   in one slot took it from each other
    jne .both                   ;   before either was counted to RB_JITHOT,
    cmp [es:bx+JIT_HASH+2],dh   ;   and both ran interpreted for ever
    jne .both
    mov dx,[es:bx+JIT_HASH+4]   ; it is there
    or dx,dx
    jz tr_count
    mov [ss:S_JITOUT],dx
    mov bx,[ss:S_SAVBX]
    jmp far [ss:S_JITOUT]
.both:                          ; in neither: the one to give way is a
    cmp word [es:bx+JIT_HASH+4],0   ; counting entry before a translated
    jne .tn                     ;   one, and of two counting the colder
    mov dl,[es:bx+JIT_HASH+3]   ; the neighbour is counting
    xor bx,8
    cmp word [es:bx+JIT_HASH+4],0
    jne .nb                     ; ...and the slot is translated: the
    cmp dl,[es:bx+JIT_HASH+3]   ;   neighbour; or of two, the colder
    jae .take
.nb:
    xor bx,8
    jmp short .take
.tn:
    xor bx,8                    ; the neighbour is translated: the slot,
    cmp word [es:bx+JIT_HASH+4],0   ;   if it is counting
    je .take
    dec byte [es:bx+JIT_HASH+3] ; both translated: the slot gives way only
    jnz .keep                   ;   after RB_JITHOT other PCs asked for it
.take:
    mov [es:bx+JIT_HASH],si
    mov [es:bx+JIT_HASH+2],dh
    mov byte [es:bx+JIT_HASH+3],1
    mov word [es:bx+JIT_HASH+4],0
.keep:
    mov bx,[ss:S_SAVBX]
    jmp tr_int
""",
    0x7F: """
; add_ff: ADD HL,DE / DEC r / JR NZ,-4 - a row of a background map stepped
; through r times (Super Mario Land's 3EF9, B = 32) - in one step when the
; budget covers it, as cnt_ff does a countdown (REALBOY-SPEC section 16.6).
; SI = the loop's head, DL = its DEC (05h B, 0Dh C), the JR NZ about to be
; taken and its 3 M-cycles not charged. From here r more passes: 3 + 3r +
; 3(r - 1) + 2 = 6r + 2 M-cycles; HL += DE x r, r = 0, and the flags the
; last pass leaves - DEC's for 1 -> 0 (Z, N; H clear) and the last ADD's
; carry. Anything else, or a budget that runs out inside, goes on at [S_RET].
add_ff:
    mov dh,ch
    cmp dl,05h
    je .go
    mov dh,cl
    cmp dl,0Dh
    je .go
    jmp word [ss:S_RET]
.go:
    mov [ss:S_TMP],dl           ; (the DEC, for the register to zero)
    mov dl,dh
    xor dh,dh
    mov [ss:S_TMP2],dx          ; r
    shl dx,1
    mov [ss:S_TMP4],dx
    shl dx,1
    add dx,[ss:S_TMP4]
    add dx,2                    ; 6r + 2
    cmp bp,dx
    jl .no
    sub bp,dx
    mov [ss:S_TMP4],ax          ; (A and F: MUL takes AX)
    mov ax,[ss:S_TMP2]
    dec ax
    mul di                      ; HL += DE x (r - 1), then the last pass's
    add bx,ax                   ;   ADD, for its carry
    mov ax,[ss:S_TMP4]
    add bx,di
    sbb ah,ah
    and ah,RBF_C
    or ah,RBF_Z|RBF_N
    add si,4
    xor dl,dl                   ; (tr_enter may dispatch on DX)
    cmp byte [ss:S_TMP],05h
    jne .c
    xor ch,ch
    jmp tr_enter
.c:
    xor cl,cl
    jmp tr_enter
.no:
    jmp word [ss:S_RET]
""",
    0x6D: """
; cpy_ff: LD A,(HL+) / LD (DE),A / INC DE / DEC B / JR NZ,-6, or LD A,(DE)
; / LD (HL+),A / ..., a copy - Super Mario Land's 2CF0 and 2D02 move an
; enemy's 13-byte slot between WRAM and HRAM and back - in one step when the
; budget covers it and both ranges lie wholly where translated loads and
; stores take memory directly, 8000-FEFF and FF80-FFFE (REALBOY-SPEC 16.6).
; SI = the loop's head, DL = its first opcode (2Ah HL to DE, 1Ah DE to HL),
; the JR NZ about to be taken and its 3 M-cycles not charged. From here r =
; B more passes, 3 + 7r + 3(r - 1) + 2 = 10r + 2 M-cycles; HL and DE += r, B
; = 0, A the last byte, and DEC's flags for 1 -> 0 (Z, N; H clear; C kept).
; A byte at a time forward, as REP MOVSB copies, so an overlap is the
; loop's. Anything else goes on at [S_RET].
cpy_ff:
    mov [ss:S_TMP],dl
    mov dl,ch
    xor dh,dh                   ; r (not 0: the JR is taken)
    mov [ss:S_TMP2],dx
    shl dx,1
    mov [ss:S_TMP4],dx
    shl dx,1
    shl dx,1
    add dx,[ss:S_TMP4]
    add dx,2                    ; 10r + 2
    cmp bp,dx
    jl .no
    mov [ss:S_TMP4],dx
    mov dx,bx                   ; HL's range...
    cmp dh,80h
    jb .no
    cmp dx,0FF80h
    jae .h1
    add dx,[ss:S_TMP2]
    jc .no
    cmp dx,0FF00h
    ja .no
    jmp cpy_de
.h1:
    add dx,[ss:S_TMP2]
    jnc cpy_de
.no:
    jmp word [ss:S_RET]
""",
    0x64: """
; cpy_ff's other half (slot 6D's): DE's range, then the copy
cpy_de:
    mov dx,di
    cmp dh,80h
    jb .no
    cmp dx,0FF80h
    jae .h2
    add dx,[ss:S_TMP2]
    jc .no
    cmp dx,0FF00h
    jna .go
.no:
    jmp word [ss:S_RET]
.h2:
    add dx,[ss:S_TMP2]
    jc .no
.go:
    sub bp,[ss:S_TMP4]
    mov [ss:S_TMP4],si          ; (the loop's head)
    mov dx,ss                   ; DS and ES the view: translated code keeps
    mov ds,dx                   ;   neither (tr_int loads DS)
    mov es,dx
    mov dl,cl
    mov cl,ch
    xor ch,ch                   ; CX = r, and B = 0 after
    mov si,bx
    cmp byte [ss:S_TMP],2Ah
    je .cp
    xchg si,di                  ; DE to HL
.cp:
    rep movsb
    mov cl,dl
    mov al,[si-1]               ; A, the last byte
    cmp byte [ss:S_TMP],2Ah
    je .hl
    xchg si,di
.hl:
    mov bx,si
    and ah,RBF_C
    or ah,RBF_Z|RBF_N
    mov si,[ss:S_TMP4]
    add si,6
    xor dl,dl
    jmp tr_enter
""",
    0x7D: """
; stat_ff: a wait on the PPU - LDH A,(41h) / AND 3 or BIT 1,A / JR NZ,-6
; (HBlank, or HBlank or VBlank: Super Mario Land's ~20 a frame before a VRAM
; write) or LDH A,(44h) / CP n / JR NZ,-6 (line n) - with whole passes of
; its 8 M-cycles taken off BP that are certain to read "not yet" (REALBOY-
; SPEC 16.6): LY and STAT are S_TNF - BP's, so the wait is known. A pass
; short of it, and never past the next event (BP stays 8 or more): the loop
; reads the change itself, and A and F are its own. SI = the head, DL = 3
; (mode 0), 2 (mode 0 or 1) or 44h (line DH); the JR NZ about to be taken,
; its 3 M-cycles not charged. Always on at [S_RET].
stat_ff:
    cmp byte [ss:S_LCDON],0
    je stat_out
    mov [ss:S_TMP2],ax
    mov [ss:S_TMP6],dx
    mov ax,[ss:S_TNF]
    sub ax,bp
.wrap:
    cmp ax,RB_FRAME
    jb .in
    sub ax,RB_FRAME
    jmp short .wrap
.in:
    mov [ss:S_TMP4],ax
    mov dh,RB_LINE
    div dh                      ; AL = LY, AH = M-cycles into the line
    cmp dl,44h
    je stat_ly
    cmp al,144
    jae .vbl
    sub ah,RB_HBL               ; to mode 0, this line
    jae stat_none
    neg ah
    mov al,ah
    xor ah,ah
    jmp short stat_t
.vbl:
    cmp dl,2                    ; (mode 1 will do)
    je stat_none
    mov ax,RB_FRAME+RB_HBL      ; to line 0's mode 0
    sub ax,[ss:S_TMP4]
stat_t:
    sub ax,8                    ; a pass short (0 is exact, gbrmw's
    jbe stat_none               ;   Waits; 8 over is not)
    and al,0F8h
    mov dx,bp
    sub dx,8
    jle stat_none
    cmp ax,dx
    jbe .ok
    mov ax,dx
    and al,0F8h
.ok:
    sub bp,ax
stat_none:
    mov ax,[ss:S_TMP2]
stat_out:
    jmp word [ss:S_RET]
""",
    0x7C: """
; stat_ff's other half (slot 7D's): line n's wait, n - LY lines on (mod
; 154; a line that never comes is never read, so any skip is the loop's)
stat_ly:
    mov dl,[ss:S_TMP6+1]
    sub dl,al
    je stat_none                ; on it now
    jnc .l
    add dl,154
.l:
    mov dh,ah
    mov al,RB_LINE
    mul dl
    sub al,dh
    sbb ah,0
    jmp stat_t
""",
    0x47: """
; cnt_ff: a COUNTDOWN, DEC r / JR NZ,-3, run to its end in one step when the
; budget covers it (REALBOY-SPEC section 8.1) - the OAM DMA routine every
; game copies to HRAM waits on one, as do delay loops. SI = the loop's head,
; DL = its DEC, the JR NZ about to be taken and its 3 M-cycles not charged.
; From here r more DECs: 3 + r + 3(r - 1) + 2 = 4r + 2 M-cycles, and r = 0
; with DEC's flags for 1 -> 0 (Z, N; H clear; C kept). A, B and C; anything
; else, or a budget that runs out inside the loop, goes on at [S_RET].
cnt_ff:
    mov dh,al
    cmp dl,3Dh
    je .go
    mov dh,ch
    cmp dl,05h
    je .go
    mov dh,cl
    cmp dl,0Dh
    je .go
    jmp word [ss:S_RET]
.go:
    mov [ss:S_TMP],dl           ; (the DEC, for the register to zero)
    mov dl,dh
    xor dh,dh
    shl dx,1
    shl dx,1
    add dx,2
    cmp bp,dx
    jl .no
    sub bp,dx
    and ah,RBF_C
    or ah,RBF_Z|RBF_N
    add si,3
    xor dl,dl                   ; (tr_enter may dispatch on DX)
    cmp byte [ss:S_TMP],3Dh
    jne .b
    xor al,al
    jmp tr_enter
.b:
    cmp byte [ss:S_TMP],05h
    jne .c
    xor ch,ch
    jmp tr_enter
.c:
    xor cl,cl
    jmp tr_enter
.no:
    jmp word [ss:S_RET]
""",
    0x43: """
; tr_lpatch for a RET's inline cache (16.4), the SITE's first byte 81h: the
; last return moves to the second entry (SITE + 17, its jmp's displacement
; 17 less), and PC and BLOCK become the first's, its bank check this
; block's bank - or a jmp short over it, for a block in bank 0
tr_rpatch:
    mov dx,[cs:bx+2]
    mov [cs:bx+19],dx
    mov dx,[cs:bx+6]
    mov [cs:bx+23],dx
    mov dl,[cs:bx+11]
    mov [cs:bx+28],dl
    mov dx,[cs:bx+15]
    sub dx,17
    mov [cs:bx+32],dx
    mov [cs:bx+2],si            ; cmp si,PC
    cmp si,4000h
    jae .bank
    mov word [cs:bx+6],06EBh    ; jmp short +6, over the bank check
    jmp short .blk
.bank:
    mov word [cs:bx+6],8036h    ; cmp byte [ss:S_BANK],B
    mov dl,[ss:S_BANK]
    mov [cs:bx+11],dl
.blk:
    mov dx,[ss:S_JITOUT]
    sub dx,bx
    sub dx,17
    mov [cs:bx+15],dx           ; jmp near BLOCK
    mov bx,[ss:S_SAVBX]
    jmp far [ss:S_JITOUT]
""",
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
    mov [ss:S_RETFAR+2],cs       ; rbsys comes back to THIS copy
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
    mov [ss:S_RETFAR+2],cs       ; rbsys comes back to THIS copy
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
    cmp bl,12h                  ; the square channels' volume and trigger
    je .host                    ;   registers and NR52 are rbsys's: it
    cmp bl,14h                  ;   keeps their envelopes and lengths for
    je .host                    ;   the speaker (REALBOY-SPEC section 17)
    cmp bl,17h
    je .host
    cmp bl,19h
    je .host
    cmp bl,26h
    je .host
    cmp bl,40h
    jb .st
    cmp bl,4Ch
    jb .lcd
    cmp bl,0FFh
    je .host
    jmp short .z                ; FF4C-FF7F: nothing on a DMG, reads FF
.st:
    mov [ss:bx],dl
.z:
    xor dl,dl
    jmp word [ss:S_RET]
.lcd:                           ; FF40-FF4B: a write of what is there
    cmp bl,46h                  ;   already changes nothing and is no
    je .host                    ;   raster write (rb_rlog would log it,
    cmp dl,[ss:bx]              ;   and a logged write can end the
    je .z                       ;   composer's FAST frame); DMA always runs
.host:
    mov [ss:S_RETFAR+2],cs       ; rbsys comes back to THIS copy
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
    xor dh,dh                   ; ROMX = the bank table's (REALBOY-SPEC 10.3)
    shl dx,1
    xchg dx,bx                  ; (BX, the address written, borrowed)
    inc word [ss:bx+RB_BUSE]
    mov bx,[ss:bx+RB_BTAB]
    xchg dx,bx
    or dx,dx
    jz mbc_set.miss             ; not in memory: rbsys fetches it
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
mbc_set.miss:
    mov [ss:S_RETFAR+2],cs
    jmp far [ss:S_MBCVEC]
""",
}


# --- the recompiler's templates (REALBOY-SPEC section 16) ---------------------
# A TEMPLATE is a handler's own body with the dispatch taken off and its
# operands patched in as immediates: translated code is the interpreter's
# code, instruction for instruction, so every gate on the interpreter is a
# gate on the translator too. These are the opcodes that do NOT translate to a
# template - control flow, and what leaves the core - and the translator
# writes its own code for them (apps/realboy/rbjit.inc).
NOTMPL = {0x10, 0x18, 0x20, 0x28, 0x30, 0x38, 0x76, 0xC0, 0xC2, 0xC3, 0xC4,
          0xC7, 0xC8, 0xC9, 0xCA, 0xCB, 0xCC, 0xCD, 0xCF, 0xD0, 0xD2, 0xD4,
          0xD7, 0xD8, 0xD9, 0xDA, 0xDC, 0xDF, 0xE7, 0xE9, 0xEF, 0xF7, 0xFF} | INVALID
# the control transfers whose interpreted form re-enters translated code
CONTROL = {0x18, 0x20, 0x28, 0x30, 0x38, 0xC0, 0xC2, 0xC3, 0xC4, 0xC7, 0xC8,
           0xC9, 0xCA, 0xCC, 0xCD, 0xCF, 0xD0, 0xD2, 0xD4, 0xD7, 0xD8, 0xDA,
           0xDC, 0xDF, 0xE7, 0xE9, 0xEF, 0xF7, 0xFF}
# operand bytes after the opcode, for the templated opcodes that have any
IMM16_OPS = {0x01, 0x11, 0x21, 0x31, 0x08, 0xEA, 0xFA}
IMM8_OPS = {0x06, 0x0E, 0x16, 0x1E, 0x26, 0x2E, 0x36, 0x3E, 0xC6, 0xCE, 0xD6,
            0xDE, 0xE6, 0xEE, 0xF6, 0xFE, 0xE0, 0xF0, 0xE8, 0xF8}
EXTERN = re.compile(r"^(\s*)jmp\s+([A-Za-z_][A-Za-z0-9_]*)\s*(;.*)?$")


def template_lines(op, cb):
    """The template for opcode op (CB op if cb), as assembler lines that
    reference IMM8/IMM16 for the operands, or None when op has none. The
    body runs into the next instruction's template; an out-of-line tail is
    jumped over."""
    if not cb and (op in NOTMPL):
        return None
    if not cb and op == 0x00:
        return ["    sub bp,1"]
    global JIT
    JIT = True
    try:
        sl = gen_cb(op) if cb else gen_main(op)
    finally:
        JIT = False
    body, tail = list(sl.body), list(sl.tail)
    if sl.ev:
        return None                                 # it checks: not a template
    out = []
    word = op in IMM16_OPS and not cb
    for part in (body, tail):
        for ln in part:
            t = ln.strip()
            if t in ("DISPATCH", "inc si", "add si,2", "xor dl,dl"):
                continue                        # (DL = 0 is the dispatch's
                                                #   invariant: tr_int keeps it)
            if "[si]" in t:
                if word or re.match(r"mov (cx|di|bx|sp|dx),\[si\]", t):
                    ln = ln.replace("[si]", "IMM16")
                else:
                    ln = ln.replace("byte [si]", "IMM8").replace("[si]", "IMM8")
            m = EXTERN.match(ln)
            if m and m.group(2) not in ("short", "near", "far", "word", "dx"):
                ln = "%sjmp near %s" % (m.group(1), m.group(2))
            if "si" in re.sub(r";.*", "", ln).replace("IMM", "").split():
                raise SystemExit("rbgen: template %s%02X still names SI: %s"
                                 % ("CB " if cb else "", op, ln))
            (out if part is body else out).append(ln)
        if part is body and tail:
            out.append("    jmp short .Jend")
    if tail:
        out.append(".Jend:")
    if not cb and op in SELFGUARD and op != 0xE2:   # (LD (C),A's is its own)
        out = self_guard(out)
    return out


# The stores that may reach anywhere (REALBOY-SPEC section 16.5) GUARD
# THEMSELVES, in the slow path, the only one that can take an interrupt or
# move the bank: SI = NEXT (IMM16, flag 16 in rbtmpl.py) before wr_slow, and
# after it the block is left through tr_enter when SI moved (IF, IE) or the
# write was the MBC's. The fast path, a write to RAM, carries no guard at all.
SELFGUARD = {0x02, 0x12, 0x22, 0x32, 0x36, 0x70, 0x71, 0x72, 0x73, 0x74, 0x75,
             0x77, 0xE2}


def self_guard(t):
    s = [k for k, ln in enumerate(t) if re.match(r"\.t\ds:$", ln.strip())]
    assert len(s) == 1, t
    n = t[s[0]].strip()[2]
    r = t.index("    mov word [ss:S_RET],.t%sk" % n, s[0])
    j = r + 1
    assert re.match(r"    jmp near wr_s\d$", t[j]), t
    k = t.index(".t%sk:" % n)
    assert re.match(r"    sub bp,\d+$", t[-1]), t
    post = t[k + 1:-1]
    return (t[:s[0] + 1] + ["    mov si,IMM16"] + t[s[0] + 1:r] +
            ["    mov word [ss:S_RET],.t%sr" % n, t[j],
             ".t%sr:" % n,
             "    cmp si,IMM16",
             "    jne .t%sx" % n,
             "    test bh,bh",
             "    js .t%sk" % n,
             ".t%sx:" % n] + post + [t[-1], "    jmp near tr_enter"] + t[j + 1:])


# Templates the translator CHOOSES by an operand it knows: a constant address
# that the interpreter's own fast path would take - HRAM, WRAM, VRAM, bank 0
# - is one MOV through SS (REALBOY-SPEC section 16.6). Record 512 + index;
# IMM16 is the whole address (FF00h + n for LDH).
EXTRA = [
    ("LDH A,(n) of HRAM", ["    mov al,[ss:IMM16]", "    sub bp,3"], 2),
    ("LDH (n),A of HRAM", ["    mov [ss:IMM16],al", "    sub bp,3"], 2),
    ("LD A,(nn) direct", ["    mov al,[ss:IMM16]", "    sub bp,4"], 3),
    ("LD (nn),A direct", ["    mov [ss:IMM16],al", "    sub bp,4"], 3),
]


def template_glen(op, cb):
    if cb:
        return 2
    return 3 if op in IMM16_OPS else 2 if op in IMM8_OPS else 1


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "build/realboy/rbcore.asm"
    L = []
    L.append("; GENERATED by apps/realboy/rbgen.py - do not edit, regenerate.")
    L.append("cpu 8086")
    L.append("bits 16")
    L.append("org 0")
    L.append("[map symbols %s.map]" % (out[:-4] if out.endswith(".asm") else out))
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
    L.append("%assign JDN 0")
    L.append("%macro JDISPATCH 0")         # a control transfer's: the
    L.append("%ifdef RB_TRACE")            #   translated code at the target
    L.append("    jmp far [ss:S_TRACEVEC]")  # if there is any (tr_enter) -
    L.append("%else")                      #   but never in RAM, which runs
    L.append("..@jd_%+JDN:")               #   on here: DS is this handler's
    L.append("%assign JDN JDN+1")          #   own (REALBOY-SPEC 16.3). Each
    L.append("    cmp si,8000h")           #   site is LABELLED: with no
    L.append("    jae %%d")                #   recompiler its first five bytes
    L.append("    jmp tr_enter")           #   become the plain dispatch
    L.append("%%d:")
    L.append("    mov dh,[si]")
    L.append("    inc si")
    L.append("    jmp dx")
    L.append("%endif")
    L.append("%endmacro")
    for op in range(256):
        L.append("    times %d-($-$$) db 0CCh" % (op * 256))
        L.append("op_%02X:" % op)
        lines = gen_main(op).text()
        if op in CONTROL:                       # REALBOY-SPEC section 16.4
            lines = [ln.replace("DISPATCH", "JDISPATCH") if ln.strip() == "DISPATCH"
                     else ln for ln in lines]
        L += lines
        if op in TAILS:
            L += TAILS[op].strip("\n").split("\n")
        L.append("    times %d-($-$$) db 0CCh" % (op * 256 + 128))
        L.append("cb_%02X:" % op)
        L += gen_cb(op).text()
    L.append("    times 65536-($-$$) db 0CCh")
    with open(out, "w") as f:
        f.write("\n".join(L) + "\n")



# The read-modify-writes of (HL) - INC/DEC (HL) and the CB group on (HL)
# but BIT - as chosen-by-operand templates too (REALBOY-SPEC section 16.6):
# their own templates carry the read's and the write's slow paths both and
# are over rbtmpl.py's TMAX, so they ended a block. Here the address is
# checked once for what both paths take directly, 8000-FEFF and FF80-FFFE,
# and anything else - ROM, the MBC, I/O, IE - goes to the interpreter at the
# instruction itself (IMM16 = its PC; BP is exact at a template that is not
# pure). The operation is the handler's own, cut out of its template.
RMW_CB = list(range(0x06, 0x40, 8)) + list(range(0x86, 0x100, 8))   # 518 + k


def rmw_lines(op, cb):
    t = template_lines(op, cb)
    i = t.index(".t1k:")
    j = t.index("    test bh,bh", i)
    body = t[i + 1:j]
    assert not {".s:", ".v:"} & {ln.strip() for ln in body}, (op, cb)
    assert re.match(r"    sub bp,\d+$", t[-1]), (op, cb)
    return ["    test bh,bh",
            "    jns .s",
            "    cmp bh,0FFh",
            "    jne .v",
            "    cmp bl,80h",
            "    jb .s",
            "    cmp bl,0FFh",
            "    jne .v",
            ".s:",
            "    mov si,IMM16",
            "    jmp near tr_int",
            ".v:",
            "    mov dh,[ss:bx]"] + body + ["    mov [ss:bx],dh", t[-1]]


EXTRA += [("INC (HL) of RAM", rmw_lines(0x34, False), 1),
          ("DEC (HL) of RAM", rmw_lines(0x35, False), 1)]
EXTRA += [("CB %02X of RAM" % b, rmw_lines(b, True), 2) for b in RMW_CB]


if __name__ == "__main__":
    main()
