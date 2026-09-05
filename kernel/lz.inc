; =============================================================================
; lz.inc - decompression (docs/O88-COMPRESSION-PLAN.md, SPEC.md 20.13)
;
; ONE routine, two formats, and which one a file uses is a bit in its header.
; `tools/os88lz.py` is the REFERENCE implementation and this is the copy: a
; disagreement between them is a bug in one of them and never a judgement
; call, which is what tests/unit/t_lzfmt.py and the `lzdec` row exist to keep
; true.
;
;   LZ4  byte-oriented, min match 4. 50.6 cycles an output byte, measured on a
;        4.77 MHz 8088, against a `rep movsw` floor of 13.09. The default,
;        because it is the only candidate whose ratio pays for its own decode
;        time on the target machine (plan 1).
;   LZB  bit-oriented, aPLib-family: a tag BYTE carried in DL behind a guard
;        bit, byte-aligned literals and low offset byte, interlaced Elias
;        gamma for the length and the high offset byte. ~10 points better on
;        ratio and 207 cycles a byte - four times the floor. Built because the
;        360KB disk's RUNWAY may be worth that, and only a field A/B can say
;        (plan 12.7).
;
; **BOTH ARE BOUNDS-CHECKED AND THAT IS NOT OPTIONAL** (plan 7.3). Every byte
; off a disk is hostile (SPEC.md 19) and os88pkg.py is not a gate on a foreign
; file. What the bounds buy back is an invariant this loader already has for
; free: SPEC.md 21 step 6 writes `ceil(image/512)*512 <= need` bytes, "never a
; neighbour's region", because the COUNT is arithmetic the loader did before
; the read. A decompressor breaks exactly that - the count becomes whatever
; the stream says - so the invariant stops being structural and has to become
; a runtime check. It cost LZ4 39 bytes and 19% of its time, LZB 16 bytes and
; 25% of its.
;
; **This module is `.cold` (SPEC.md 2.6)** and its three in-kernel callers -
; loader.inc, driver.inc, diskw.inc - are cold too, so they reach it with a
; near call. mod.inc and the API cell come in through the resident thunk.
;
; **IT TOUCHES NO KERNEL DATA AT ALL**, which is unusual enough to be the
; reason the API cell is a plain OSAPI_SLOT rather than an X cell: every other
; cell needs DS = KERNEL_SEG for its own variables and therefore needs a stub
; to get at the caller's segment, where this one wants BOTH segments to be the
; caller's and has nothing of its own to address. Its two locals live in a
; stack frame, which SS addresses whatever DS is doing.
; =============================================================================

; What a region must have ABOVE image+bss so a decoder reading its own source
; from the top of that region never overtakes its write pointer (SPEC.md 20.13,
; docs/O88-COMPRESSION-PLAN.md 7.2). Every shipped package measures 2 and
; incompressible data measures 17 - LZ4 EXPANDS what does not compress - so 64
; is a ceiling and not an estimate. **MIRRORED by os88pkg.py's
; PKG_COMP_MARGIN**, which is the side that refuses a file needing more.
LZ_MARGIN   equ 64

; --- THE SLIDING SOURCE WINDOW (SPEC.md 20.14.2.4), LZB only -----------------
; A caller whose buffer is exactly the unpacked size cannot hold the in-place
; layout: the writer chases the reader and overtakes it by up to LZ_MARGIN at
; the peak of its lead, clobbering source bytes before they are read. The
; window is what makes that survivable - the decoder reads through a copy that
; is always refilled from bytes the writer has not reached yet.
;
; **THE TWO SIZES ARE A PROOF, NOT A PREFERENCE.** At a refill the writer is
; at most LZ_MARGIN past the reader's source position, so bytes from
; `p + LZ_MARGIN` on are certainly intact - which means the window must still
; HOLD `[p, p + LZ_MARGIN)` when it refills. The check runs once per sequence
; and one LZB sequence consumes at most ~10 bytes (two gammas of 4 and an
; offset byte), so refilling below LZ_WLOW leaves at least
; `LZ_WLOW - 64 = LZ_MARGIN` in hand. Lower LZ_WLOW and the proof fails
; silently, on data that depends on where the peak fell.
LZ_WIN      equ 256             ; the window
LZ_WLOW     equ 128             ; ...and when to top it up: LZ_MARGIN, plus 64
                                ; for the most one sequence can consume
LZ_LZ4      equ 0               ; format ids, as stored in a header's format
LZ_LZB      equ 1               ; field. Mirrored by os88lz.py's LZ4/LZB and
                                ; guarded by tests/unit/t_mirror.py

; Which decoders this kernel carries (SPEC.md 20.13.6). **BOTH IS THE DEFAULT
; AND SHIPS**, and it needs no -D at all: `make COMPRESS=lz4` and
; `COMPRESS=lzb` are the single-format A/Bs and are the ones that name a
; symbol. That direction is deliberate and not a preference - a tool that
; re-assembles this kernel for a symbol map (tools/os88sym.py) passes no
; defines, so whatever the source does with NONE has to be what `make` builds,
; or every symbol lookup in the tree refuses a kernel that is perfectly fine.
;
; The DISKS are still LZ4. Carrying the other decoder is what lets the machine
; READ a format it does not WRITE - which is what makes the file manager's
; Compress verb a package-side change, and an LZB disk something a user can be
; handed rather than something that needs a matching kernel.
%ifndef LZ_HAVE_LZ4
  %ifndef LZ_HAVE_LZB
    %define LZ_HAVE_LZ4         ; neither asked for: BOTH, and the dispatch
    %define LZ_HAVE_LZB         ; between them, which is what ships
  %endif
%endif

section .cold

; -----------------------------------------------------------------------------
; lz_decomp_x - expand one compressed block
;
; in:  DS:SI = the compressed bytes
;      ES:0  = the destination, and DI = 0. **DI MUST BE ZERO**: the offset
;              bound below reads "no match may reach back further than we have
;              produced" only when production started at 0. Every caller in the
;              tree hands over a claim's base, so this costs nothing and saves
;              an instruction in the hottest test in the routine.
;      CX    = compressed bytes. **UNDER 64KB, and SI + CX may not wrap** -
;              refused, see below
;      BX:DX = the EXACT expected output length, 32 bits (not a capacity:
;              every caller knows it - the loader from `image`, a part from its
;              table row, a file from its own header - and a stream that
;              produces a different number is a corrupt one)
;      AL    = LZ_LZ4 or LZ_LZB
; out: CF=0 and ES:DI is one past the last byte written. CF=1 = refused, and
;      nothing past the declared length was written.
; clobbers: AX BX CX DX SI DI and the flags. DS and ES come back the caller's.
; -----------------------------------------------------------------------------
; **THE OUTPUT CROSSES 64KB AND THE INPUT DOES NOT**, and the asymmetry is
; deliberate rather than an omission (SPEC.md 20.14.5). The output has to:
; BEVERLY.MOD is 116,085 bytes and compressing it is the single biggest win in
; the tree - 42,169 bytes, 36.3%, which is 145 sectors of a floppy. Splitting
; the stream into segment-sized blocks instead would have cost 18,766 of those
; bytes, 44% of the whole win, because a MOD's sample data matches back tens of
; KB into itself and a block boundary throws that history away.
;
; The input does not, because it does not have to and the check is free: a
; stream over 64KB means a file that compressed BADLY, which os88lz.py stores
; plain instead. `add cx, si / jc` is the whole enforcement, and what it buys
; is that [LZ_F_SEND] stays a plain 16-bit offset in one segment - the source
; bound is tested twice per sequence and is the hottest compare here.
;
; What the output crossing costs the fast path is THREE instructions per copy
; (the source-wrap test, and a 32-bit remaining counter in place of a 16-bit
; end compare), and every actual crossing is out of line in lz_cross. What it
; buys is measured above in seconds.
;
; The locals are PUSHED rather than carved with `sub sp`, and the frame is
; unwound with `pop` rather than `mov sp, bp`, so the routine is push/pop
; balanced on every path and tools/stkbalance.py can walk it. It caught the
; first version, which was not.
LZ_F_REM    equ 0               ; the frame, once BP is set: output bytes still
LZ_F_REMH   equ 2               ; to produce, 32 bits...
LZ_F_SEND   equ 4               ; ...the source end, an offset in ONE segment...
LZ_F_WIN    equ 8               ; ...1 when the source is read through the
                                ; sliding window (SPEC.md 20.14.2.4)...
LZ_F_BUMP   equ 6               ; ...and 1 once the destination has crossed a
                                ; 64KB boundary, which is exactly the moment
                                ; "produced" passes what a 16-bit match offset
                                ; can reach - so the offset bound stops being a
                                ; compare at all (SPEC.md 20.14.5)

; -----------------------------------------------------------------------------
; lz_win_x - the same decode, reading the source through a WINDOW
;            (SPEC.md 20.14.2.4)
; in:  as lz_decomp_x, and AL must be LZ_LZB
; out: as lz_decomp_x
;
; **LZB ONLY, AND THAT IS THE WHOLE POINT OF DOING IT HERE.** LZB touches its
; source at three places and every one of them is a SINGLE BYTE - the tag
; refill in LZ_GETBIT, the offset's low byte, and a literal's `movsb` - so the
; window costs one compare per SEQUENCE, on a branch the direct path already
; had. LZ4's literals are `rep movsb` RUNS that would have to be split at the
; window's edge, which is the hot path of every package launch; it does not get
; one, and the build refuses to write an LZ4 file that would need it
; (SPEC.md 20.14.2.3).
;
; The window and its cursor are kernel `.bss` rather than frame words, so the
; fast path's stack is untouched. That is safe on dsk_op's terms and only
; those: this entry is reached from dskw_czexp and nowhere else, and a
; transfer holds sch_lock, so nothing can be inside it twice - the same
; argument dskw_read_at's banked arguments already run on.
; -----------------------------------------------------------------------------
lz_win_x:
    cmp al, LZ_LZB
    jne .wno                    ; the window is LZB's; LZ4 never asks
    push ds                     ; the CALLER's, for the shared unwind below
    push bp
    push ax                     ; ...and the format, wanted after the setup
    mov ax, ds                  ; the real source's segment, banked while DS
    mov bp, KERNEL_SEG          ; becomes the WINDOW's - `.cold` runs at
    mov ds, bp                  ; COLD_SEG, so `cs:` reaches none of this
    mov [lz_wsseg], ax
    mov [lz_wsoff], si          ; ...and where in it we have got to
    mov [lz_wleft], cx
    mov si, lz_wbuf             ; the window starts EMPTY
    mov [lz_wend], si
    call lz_wfill               ; the first fill reads bytes nothing has
    mov si, lz_wbuf             ; written over: the output is untouched, so
    mov cx, [lz_wsend]          ; there is no safety question to ask yet
    sub cx, si                  ; SI + CX is the frame's source end, which
    pop ax                      ; here is the REFILL TRIGGER and not the
    mov bp, 1                   ; stream's end
    jmp short lz_body
.wno:
    stc
    ret

; -----------------------------------------------------------------------------
; lz_wfill - slide the window's unconsumed tail down and top it up
;            (module internal)
; in:  DS = KERNEL_SEG, SI = the read cursor inside lz_wbuf
; out: [lz_wend] and [lz_wsend] updated, DS still KERNEL_SEG; the caller resets
;      SI to lz_wbuf
; clobbers: flags
;
; THE TOP-UP IS THE SAFE HALF and the reason LZ_WIN and LZ_WLOW are what they
; are: it reads from `lz_wsoff`, which is `unconsumed` bytes past the reader's
; own position, and the writer is never more than LZ_MARGIN past that - so as
; long as `unconsumed >= LZ_MARGIN` every byte it copies is one the writer has
; not reached.
;
; When the real source runs out the trigger becomes the window's true END, so
; the caller's `ja` goes back to meaning "the stream ran out mid-symbol" and
; the loop cannot spin: a refill either advances lz_wsoff or retires itself.
; -----------------------------------------------------------------------------
lz_wfill:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    push ds
    pop es                      ; both the window's, for the slide
    mov cx, [lz_wend]
    sub cx, si
    mov bx, cx                  ; ...the unconsumed tail, banked
    mov di, lz_wbuf
    jcxz .noslide
    rep movsb
.noslide:
    mov di, lz_wbuf
    add di, bx                  ; ...where the top-up lands
    mov cx, LZ_WIN
    sub cx, bx                  ; ...and the room for it
    cmp cx, [lz_wleft]
    jbe .have
    mov cx, [lz_wleft]
.have:
    mov dx, cx                  ; the count, banked past the copy
    mov si, [lz_wsoff]
    mov ds, [lz_wsseg]
    jcxz .none
    rep movsb
.none:
    push es
    pop ds                      ; ...KERNEL_SEG again
    add [lz_wsoff], dx
    sub [lz_wleft], dx
    add bx, dx
    mov ax, lz_wbuf
    add ax, bx
    mov [lz_wend], ax
    cmp word [lz_wleft], 0
    je .spent                   ; nothing more out there: the trigger IS the
    sub ax, LZ_WLOW             ; end, and `ja` means what it always meant
.spent:
    mov [lz_wsend], ax
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

lz_decomp_x:
    push ds                     ; both segments are the caller's and both come
    push bp                     ; back: the match copies below swap DS to ES
    xor bp, bp                  ; ...and this is the DIRECT path
lz_body:
    cld
    or di, di
    jnz .early                  ; the precondition, checked rather than assumed
    add cx, si                  ; the source end
    jc .early                   ; SI + CX wrapped: not a source this routine
                                ; will read, and a bound that wrapped is a
                                ; bound that silently means nothing
    push bp                     ; LZ_F_WIN - 1 only from lz_win_x above
    xor bp, bp
    push bp                     ; LZ_F_BUMP = 0 - nothing has crossed yet
    push cx                     ; the source end...
    push bx                     ; ...the expected output, high word...
    push dx                     ; ...and low
    mov bp, sp                  ; SS, not DS - which is the point of a frame
    ; EVERY ARM CHECKS AL, including the single-format builds. The cell exists
    ; in both kernels and is never %ifdef'd - SPEC.md 20.8 rule 4: a slot that
    ; is present in one build and absent in another is an ABI that depends on a
    ; knob - so a build that does not carry a format must REFUSE it rather than
    ; run the one it does have on it. The first version fell through.
%ifdef LZ_HAVE_LZ4
    cmp al, LZ_LZ4
    jne .try_lzb
    call lz_lz4
    jmp short .out
%endif
.try_lzb:
%ifdef LZ_HAVE_LZB
    cmp al, LZ_LZB
    jne .refuse
    call lz_lzb
    jmp short .out
%endif
.refuse:
    stc
.out:
    pop cx                      ; drop the five locals. `pop` and not `add sp`,
    pop dx                      ; and none of them touches the flags, so the CF
    pop bx                      ; the caller reads survives the unwind
    pop si
    pop di
    pop bp
    pop ds
    ret
.early:                         ; refused before the frame was built, so the
    stc                         ; unwind is the shorter one
    pop bp
    pop ds
    ret

; -----------------------------------------------------------------------------
; lz_take - claim CX bytes of the declared output (module-internal)
; out: CF=1 = there are not that many left, and nothing has been written
; clobbers: the flags only
;
; The 32-bit form of what used to be `DI + CX against the end`, and it replaces
; that test rather than adding to it: the end cannot be an offset once the
; output crosses a segment, so what is tracked is what is LEFT. Two memory
; operands where there were two register ones, and one instruction fewer.
; -----------------------------------------------------------------------------
lz_take:
    sub [bp+LZ_F_REM], cx
    sbb word [bp+LZ_F_REMH], 0
    ret                         ; CF is the answer, and `ret` leaves it alone

; -----------------------------------------------------------------------------
; lz_cross - CX bytes from DS:SI to ES:DI when either pointer is about to leave
;            its segment (module-internal)
; in:  CX != 0, and lz_take has already claimed the bytes
; out: CX = 0, SI/DI/DS/ES advanced past the copy
; clobbers: AX, CX, SI, DI, DS, ES, flags
;
; **ONCE PER 64KB OF OUTPUT**, which is why it is a call and not inline: a
; whole segment of literals and matches pays for it once. It moves as much as
; fits below whichever boundary comes first, bumps that side by 4,096
; paragraphs, and goes round - so the copy stays one `rep movsb` per chunk and
; the byte-at-a-time overlap a match depends on is untouched.
;
; `neg` of a zero offset answers zero, which has to be read as "a whole 64KB
; is available" - and at that point CX cannot be the binding constraint, since
; CX is 16 bits. That is the one case in here that is not arithmetic.
; -----------------------------------------------------------------------------
lz_cross:
    push dx
.chunk:
    mov ax, di
    neg ax                      ; bytes to the destination's boundary...
    jnz .dst
    mov ax, cx                  ; ...or a whole segment, which CX cannot fill
.dst:
    mov dx, si
    neg dx                      ; ...and the source's
    jnz .src
    mov dx, cx
.src:
    cmp ax, dx
    jbe .amin
    mov ax, dx                  ; whichever boundary comes first
.amin:
    cmp ax, cx
    jbe .take
    mov ax, cx                  ; ...and never more than is left
.take:
    sub cx, ax                  ; CX = what will be left after this chunk
    xchg ax, cx                 ; ...and CX = the chunk
    push ax
    rep movsb
    pop cx
    or di, di
    jnz .nodst                  ; the destination landed exactly on the
    mov ax, es                  ; boundary: 64KB on is 4,096 paragraphs
    add ax, 0x1000
    mov es, ax
    mov word [bp+LZ_F_BUMP], 1  ; ...and the match-offset bound stops being a
.nodst:                         ; compare from here on (LZ_F_BUMP)
    or si, si
    jnz .nosrc
    mov ax, ds
    add ax, 0x1000
    mov ds, ax
.nosrc:
    jcxz .done
    jmp short .chunk
.done:
    pop dx
    ret

%ifdef LZ_HAVE_LZ4
; -----------------------------------------------------------------------------
; lz_lz4 - the LZ4 block format, bounded on both pointers.
; -----------------------------------------------------------------------------
lz_lz4:
.seq:
    cmp si, [bp+LZ_F_SEND]      ; A WELL-FORMED STREAM NEVER REACHES THIS with
    jae .bad                    ; nothing left - its last sequence is literals
                                ; only, and the test below `.nolit` takes that
                                ; one to `.done`. A HOSTILE one can end on a
                                ; match, and without this the token read below
                                ; is one byte past the source. It still could
                                ; not write out of bounds, but it read out of
                                ; them, and "refuses eventually" is not the
                                ; same as "does not read what it was not given"
    lodsb                       ; the token: literal length in the high nibble,
    mov dl, al                  ; match length - 4 in the low one
    mov cl, 4
    shr al, cl
    mov ch, 0
    mov cl, al
    cmp cl, 15
    jne .lits
    xor ah, ah                  ; AH must be 0 for the accumulate, and a later
.lx:                            ; `lodsw` dirties it - so it is cleared per
    lodsb                       ; extension loop and not once at entry
    add cx, ax
    cmp al, 255
    je .lx
.lits:
    jcxz .nolit
    call lz_take                ; the literals may not run past what was
    jc .bad                     ; declared, and this is where that is decided
    mov ax, di
    add ax, cx
    jc .lcross                  ; ...and either pointer may be about to leave
    mov ax, si                  ; its segment, which is out of line because it
    add ax, cx                  ; happens once per 64KB and not once per
    jc .lcross                  ; sequence
    rep movsb
.nolit:
    cmp si, [bp+LZ_F_SEND]
    jae .done
    lodsw                       ; the match offset
    mov bx, ax
    or bx, bx
    jz .bad                     ; offset 0 would copy from itself for ever
    cmp bx, di
    ja .offhi                   ; ...and one past what we have produced would
                                ; read BELOW the region base, which
                                ; mem_claim_hi makes a resident package's code
                                ; (SPEC.md 50.3). Once the output has crossed
.offok:                         ; 64KB, DI is no longer that count and the
    mov cl, dl                  ; flag is - which is also why the branch is
    and cl, 0x0F                ; the RARE way round: `ja` not taken is the
                                ; fast path and costs 4 cycles
    mov ch, 0
    cmp cl, 15
    jne .mat
    xor ah, ah
.mx:
    lodsb
    add cx, ax
    cmp al, 255
    je .mx
.mat:
    add cx, 4
    call lz_take
    jc .bad
    push si
    push ds
    mov si, di
    sub si, bx                  ; a match reads what we have already written -
    push es                     ; and the borrow says it reaches into the
    pop ds                      ; segment BELOW, where SI has already wrapped
    jc .mlow                    ; to exactly the right offset
.mgo:
    mov ax, di
    add ax, cx
    jc .mcross
    mov ax, si
    add ax, cx
    jc .mcross
    rep movsb
.mdone:
    pop ds
    pop si
    jmp .seq
.mlow:
    mov ax, ds                  ; 64KB back is exactly 4,096 paragraphs, so
    sub ax, 0x1000              ; the wrapped SI needs no arithmetic of its own
    mov ds, ax
    jmp short .mgo
.mcross:
    call lz_cross
    jmp short .mdone
.lcross:
    call lz_cross
    jmp short .nolit
.offhi:
    cmp word [bp+LZ_F_BUMP], 0  ; the output has passed 64KB, so every 16-bit
    jne .offok                  ; offset is inside it by construction
    jmp short .bad
.done:
    mov ax, [bp+LZ_F_REM]       ; a stream that ends short of the image is a
    or ax, [bp+LZ_F_REMH]       ; truncated file, not a package
    jnz .bad
    clc
    ret
.bad:
    stc
    ret
%endif

%ifdef LZ_HAVE_LZB
; -----------------------------------------------------------------------------
; lz_lzb - the bit-oriented format, bounded on both pointers.
;
; The tag byte lives in DL with a GUARD bit below it, so DL reaching zero is
; the refill signal and no register is spent on a counter - which matters,
; because every register a bit reader holds is one `rep movsb` wants.
; -----------------------------------------------------------------------------
%macro LZ_GETBIT 0
    add dl, dl
    jnz %%ok
    mov dl, [si]
    inc si                      ; `inc` leaves CF alone, by design, so the
    adc dl, dl                  ; guard shifted out above becomes the new low
%%ok:                           ; bit and CF is the byte's top bit
%endmacro

lz_lzb:
    mov dl, 0x80                ; the guard alone: the first read refills
.loop:
    cmp si, [bp+LZ_F_SEND]
    jbe .seq
    cmp word [bp+LZ_F_WIN], 0   ; ...OR the window wants topping up
    je .bad                     ; (SPEC.md 20.14.2.4). The direct path reaches
    push dx                     ; this compare only when its stream really HAS
    call lz_wfill               ; run out, so the window costs it nothing - and
    pop dx                      ; DS is KERNEL_SEG here, which is what makes
    mov si, lz_wbuf             ; the window addressable from `.cold` at all
    mov ax, [lz_wsend]
    mov [bp+LZ_F_SEND], ax
    cmp si, ax
    ja .bad                     ; ...and an empty window at the trigger is the
.seq:                           ; stream running out after all
    LZ_GETBIT
    jnc .lit
    call .gamma                 ; the match length
    mov bx, ax
    call .gamma                 ; (offset >> 8) + 2
    dec ax
    dec ax
    mov ah, al
    lodsb                       ; ...and its low byte: AX is the offset
    or ax, ax
    jz .bad
    cmp ax, di
    ja .offhi                   ; ...unless the output has already crossed
.offok:                         ; 64KB, past which every 16-bit offset is
    push ax                     ; inside it by construction (LZ_F_BUMP)
    mov cx, bx
    call lz_take
    jc .badp
    pop ax
    push si
    push ds
    mov si, di
    sub si, ax                  ; the borrow says the match reaches into the
    push es                     ; segment below, where SI has already wrapped
    pop ds                      ; to exactly the right offset
    jc .mlow
.mgo:
    mov ax, di
    add ax, cx
    jc .mcross
    mov ax, si
    add ax, cx
    jc .mcross
    rep movsb
.mdone:
    pop ds
    pop si
    jmp short .chk
.mlow:
    mov ax, ds                  ; 64KB back is exactly 4,096 paragraphs
    sub ax, 0x1000
    mov ds, ax
    jmp short .mgo
.mcross:
    call lz_cross
    jmp short .mdone
.badp:
    pop ax
    jmp short .bad
.offhi:
    cmp word [bp+LZ_F_BUMP], 0
    jne .offok
    jmp short .bad
.lit:
    sub word [bp+LZ_F_REM], 1   ; lz_take's body, for the one byte a literal
    sbb word [bp+LZ_F_REMH], 0  ; is here - LZB has no literal RUNS
    jc .bad
    movsb
    or di, di
    jnz .chk                    ; ...and one byte can land on the boundary too
    mov ax, es
    add ax, 0x1000
    mov es, ax
    mov word [bp+LZ_F_BUMP], 1
.chk:
    mov ax, [bp+LZ_F_REM]
    or ax, [bp+LZ_F_REMH]
    jnz .loop
    clc
    ret
.bad:
    stc
    ret

.gamma:                         ; AX = the value, which is always >= 2
    mov ax, 1
.g:
    LZ_GETBIT
    adc ax, ax
    LZ_GETBIT
    jc .g
    ret
%endif

; -----------------------------------------------------------------------------
; lzf_decomp - the FAR entry, for the API cell and for mod.inc (SPEC.md 2.6.1:
; a far entry ends in `retf` and is never near-called, so the two forms are two
; symbols). Everything in `.cold` reaches lz_decomp_x with a near call instead.
; `retf` leaves the flags alone, so the CF below is the answer.
; -----------------------------------------------------------------------------
lzf_decomp:             call lz_decomp_x
                    retf

; --- the sliding window's state (SPEC.md 20.14.2.4) --------------------------
; .bss and not the frame, so the direct path's stack is byte for byte what it
; was. Safe on dsk_op's terms and only those: lz_win_x is reached from
; dskw_czexp and nowhere else, and a transfer holds sch_lock - the same
; argument dskw_read_at's banked arguments already run on.
section .bss
lz_wbuf:    resb LZ_WIN         ; the window itself
lz_wend:    resw 1              ; ...one past its last valid byte
lz_wsend:   resw 1              ; ...and the refill trigger, LZ_WLOW below that
lz_wsseg:   resw 1              ; the REAL source: segment...
lz_wsoff:   resw 1              ; ...the next byte not yet copied in...
lz_wleft:   resw 1              ; ...and how many of those are left

section .text
