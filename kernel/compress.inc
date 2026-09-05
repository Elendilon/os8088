; =============================================================================
; compress.inc - THE LZB COMPRESSOR (SPEC.md 20.15), an on-demand module
; =============================================================================
; The one thing in this tree that COMPRESSES on the 8088. Everything else here
; decodes: the loader, the file read, the boot blob. This is the file manager's
; Compress verb (SPEC.md 22.22) and nothing else calls it.
;
; **IT IS A MODULE FOR THE REASON EVERY MODULE IS ONE** (SPEC.md 2.8): the verb
; is a deliberate act somebody waits for, and a machine that never uses it
; should carry none of it. `mod_need` claims the image, the verb runs, and
; `mod_drop` gives the whole of it back. The resident half is a `mod_tab` row,
; a file name and one `mod_fp` block - 45 bytes.
;
; **IT IS A HASH-CHAIN MATCHER, DEPTH 16, OVER A 16,384-BYTE WINDOW**, and that
; is a correction to docs/plans/completed/O88-COMPRESSION-PLAN.md 13.11.0 rather than what it
; recommended. That measurement rejected chains because a `prev` array is two
; bytes per input byte - 128KB for a 64KB file - which is true of a chain over
; the WHOLE file and not of one over a window: 13.11.0's own 12.3.1 had already
; said so, and the arithmetic is 2 x 16,384 = 32KB whatever the file is. What
; the two parses actually measure at, over the seven files of 13.11.0:
;
;   one candidate per slot, lazy    74.5%      (13.11.0's recommendation)
;   chains, depth 16, no lookahead  68.9%      (this)
;   the host's shortest-path parse  63.9%      (os88lz.lzb_compress)
;
; and against the LZ4 those files ship as, this is **3.9 to 10.3 points
; better** where 13.11.0's parse was 0.8 to 6.9. THE LOOKAHEAD IS GONE WITH IT:
; at equal work a deeper chain beats a shallower one with a lookahead on every
; budget measured, so `lazy` is dominated rather than merely marginal.
;
; **THE TABLES ARE THE CALLER'S BLOCK**, 8KB of `head` and 2 x window of
; `prev`, and that is not a register trick - it is where the memory belongs. A
; module's image is its FILE (mod_check: `the image IS the file`), so a table
; inside it would be 8KB of zeros on the system disk, written by the build and
; read off the floppy at every use, to be overwritten by `rep stosw` before the
; first byte is hashed. The verb claims one block and slices it, and the WINDOW
; is its dial: it drops until the claim fits, so a 128KB machine runs the same
; encoder over less history rather than a different one.

CMZ_HBITS   equ 12              ; head[] - 4,096 entries, 8KB, at the block's
CMZ_HSIZE   equ 1 << CMZ_HBITS  ; offset 0
CMZ_PREV    equ CMZ_HSIZE * 2   ; ...and prev[] immediately after it, two bytes
                                ; per WINDOW position (not per input byte -
                                ; that is the whole correction above)
CMZ_NIL     equ 0xFFFF          ; an empty head slot

CMZ_DEPTH   equ 16              ; chain candidates tried per position. The
                                ; curve flattens here: depth 8 is 0.29 points
                                ; worse for 23% less work and depth 24 is 0.07
                                ; better for 12% more

CMZ_MIN     equ 3               ; the shortest match this encoder will take.
                                ; LZB's FORMAT minimum is 2 (LZB_MIN in
                                ; os88lz.py) and the host's parse uses it, but
                                ; a two-byte match needs a two-byte hash
CMZ_SLACK   equ 16              ; how far past [cmz_lim] one pass can write.
                                ; The worst pass is a match: one tag bit, two
                                ; gammas of at most 30 and 16 bits, and one raw
                                ; byte - 47 tag bits is 7 tag bytes, plus the
                                ; raw one is 8. Sixteen is that doubled, and it
                                ; is what lets `.next` bound the WRITE once a
                                ; pass instead of at every store

CMZ_PSTEP   equ 512             ; source bytes between progress reports - the
                                ; widget's own unit (SPEC.md 12.8.1), so a
                                ; report is a compare until the bar's pixel
                                ; extent actually moves
CMZ_XPROG   equ 0x03C8          ; OSAPI_FS_PROG. The cloner's idiom (SPEC.md
                                ; 18.99.4): an OSAPI_SLOT is
                                ; `push ds / push cs / pop ds / call <body> /
                                ; pop ds / retf`, which is a far-callable
                                ; wrapper around a near proc that fixes DS
                                ; ITSELF - so this module can report progress
                                ; with the SOURCE in DS and needs neither a
                                ; cw_ shim nor a callback in its own ABI

CMZ_NENT    equ 1               ; one entry, like the cloner's
CMZFP       equ mod_fp + MOD_CMPR * MODFP_STRIDE

section .modz                   ; the on-demand image (SPEC.md 2.8)
modz_hdr:
    dw 0x384F                   ; MOD_H_MAGIC
    db MOD_VER                  ; MOD_H_VER
    db MOD_CMPR                 ; MOD_H_ID
    dw BUILD_NUM                ; MOD_H_BUILD
    dw MOD_STAMP                ; MOD_H_STAMP
    dw modz_end                 ; MOD_H_IMG
    dw CMZ_NENT                 ; MOD_H_NENT
    dw modz_e_pack
    times MOD_NENT - CMZ_NENT dw 0

modz_e_pack:    call cmz_pack
            retf                ; CF is the answer and `retf` does not touch it

; -----------------------------------------------------------------------------
; cmz_pack - LZB-compress one buffer (SPEC.md 20.15.1)
; in:  AX = the SOURCE segment, the source at AX:0000
;      DX = the OUTPUT segment, the output at DX:0000, CX bytes of room
;      BX = a scratch segment: CMZ_PREV + 2*(DI+1) bytes at BX:0000
;      DI = the window's MASK - a power of two less one, 1,023 to 16,383
;      CX = the source's length, 1..0xFFFF
; out: CF=0, AX = the packed length (which is < CX) and DX = the stream's
;         IN-PLACE MARGIN (SPEC.md 20.15.2)
;      CF=1 = it did not get smaller, and the output is undefined
; clobbers: AX BX CX DX SI DI, flags. DS, ES and BP come back.
;
; SEGMENTS RATHER THAN POINTERS, because the far pointer this is reached
; through lives in `mod_fp` - kernel `.bss` - so a caller whose DS was already
; the source could not have made the call at all.
;
; THE BAIL IS THE ONLY BOUND THE OUTPUT NEEDS. A stream that reaches CX bytes
; has already lost - the caller would store the file plain - so the write
; pointer is tested against the input's length and nothing else, and the
; caller's buffer is exactly that big.
; -----------------------------------------------------------------------------
cmz_pack:
    push ds
    push es
    push bp
    mov bp, ax                  ; the source segment, out of AX's way: the
    cld                         ; head clear below wants AX for the fill
    mov [cs:cmz_mask], di

    cmp cx, CMZ_SLACK
    jbe .no                     ; nothing this short compresses, and the limit
                                ; below would wrap
    mov [cs:cmz_n], cx
    sub cx, CMZ_SLACK
    mov [cs:cmz_lim], cx
    mov [cs:cmz_tseg], bx

    ; --- head[] starts EMPTY, and prev[] DOES NOT NEED TO -------------------
    ; A head slot left from the last file names a position in a buffer that is
    ; not this one, and nothing below would reject it - the match is verified
    ; byte for byte, so the stream stays correct, but the parse is worse for no
    ; reason. Clearing costs 4,096 stores once.
    ;
    ; prev[] is a different question and the answer is that it is SAFE stale.
    ; An entry is only read for a candidate the window test has already
    ; accepted, and prev[p] can only have been overwritten by a position
    ; p + k*window - which, being below SI, puts p itself outside the window.
    ; So every entry this walk reads was written by an insert of its own
    ; position, and 32KB of stores are not made.
    mov es, bx
    xor di, di
    mov cx, CMZ_HSIZE
    mov ax, CMZ_NIL
    rep stosw

    mov ds, bp                  ; the source...
    mov es, dx                  ; ...and the output
    mov byte [cs:cmz_tbit], 0   ; no tag byte open yet
    mov word [cs:cmz_mx], 0
    mov word [cs:cmz_nextp], CMZ_PSTEP
    xor si, si                  ; the read cursor...
    xor di, di                  ; ...and the write cursor

.next:
    ; --- THE IN-PLACE MARGIN, measured as it is written (SPEC.md 20.15.2) ---
    ; A decoder expanding in place reads from R and writes from 0, so it needs
    ; R >= (produced - consumed) at every instant. THIS is every instant that
    ; matters: inside a symbol the decoder consumes its bytes and only then
    ; produces, so (produced - consumed) peaks at the symbol's END - which is
    ; here, with SI what the decoder will have produced and DI what it will
    ; have consumed. Six instructions, and without them a package could only be
    ; compressed by simulating the decode.
    mov ax, si
    sub ax, di
    jc .nomx                    ; still behind: the first tag byte precedes the
    cmp ax, [cs:cmz_mx]         ; first literal, so this is negative early on
    jbe .nomx
    mov [cs:cmz_mx], ax
.nomx:
    cmp si, [cs:cmz_nextp]      ; ...and the bar, on the same boundary
    jb .noprog
    call cmz_prog
    add word [cs:cmz_nextp], CMZ_PSTEP
    jnc .noprog
    mov word [cs:cmz_nextp], 0xFFFF ; a 64KB source runs the counter off the
.noprog:                        ; end; parking it here costs one extra report
                                ; where a wrap would report at every position
    cmp si, [cs:cmz_n]
    jae .done
    cmp di, [cs:cmz_lim]
    jae .no                     ; it is not going to get smaller

    call cmz_probe              ; AX = the match length, DX = its offset
    or ax, ax
    jz .lit

    ; --- the match: a 1 bit, gamma(len), gamma((off>>8)+2), off's low byte ---
    push ax                     ; (os88lz.py's lzb_compress, in that order)
    push dx
    stc
    call cmz_bit
    call cmz_gamma              ; AX is still the length
    pop dx
    push dx
    mov ax, dx
    mov cl, 8
    shr ax, cl
    add ax, 2                   ; (off >> 8) + 2, which is >= 2 by
    call cmz_gamma              ; construction - a gamma cannot code 1
    pop dx
    pop ax
    push ax
    mov al, dl                  ; ...and the offset's low byte, raw
    stosb
    pop ax
    call cmz_fill               ; every position the match covers goes in
    add si, ax
    jmp short .next

.lit:
    clc
    call cmz_bit
    mov al, [si]
    stosb
    mov ax, 1                   ; ...and this one position goes in, through
    call cmz_fill               ; the same routine: a literal is a match of
    inc si                      ; length one as far as the table cares
    jmp short .next

.done:
    mov ax, di
    cmp ax, [cs:cmz_n]
    jae .no
    mov dx, [cs:cmz_mx]         ; margin = max(produced - consumed) - (U - P),
    sub dx, [cs:cmz_n]          ; and it cannot borrow: the LAST boundary has
    add dx, ax                  ; SI = U and DI = P, so the max is at least
    pop bp                      ; U - P
    pop es
    pop ds
    clc
    ret
.no:
    pop bp
    pop es
    pop ds
    stc
    ret

; -----------------------------------------------------------------------------
; cmz_prog - one CMZ_PSTEP of the source parsed (module internal)
; clobbers: nothing, flags included - OSAPI_SLOT's push/pop pair writes no
;           flag and fpg_stepb preserves every register and the flags, which
;           is the contract dsk_xfer's per-sector loop already leans on
;
; The widget is the caller's: it armed fpg_begin with the source's length
; before the far call and gives it back afterwards. Unarmed this is a compare
; and a return inside fpg_stepb, so a caller that wants no bar passes nothing
; and pays a far call per 512 bytes of a parse that costs ~1,600 cycles a byte.
; -----------------------------------------------------------------------------
cmz_prog:
    push ax
    mov ax, CMZ_PSTEP
    call KERNEL_SEG:CMZ_XPROG
    pop ax
    ret

; -----------------------------------------------------------------------------
; cmz_probe - the best match at SI, walking the chain (module internal)
; in:  DS = the source, SI = the position
; out: AX = the match length (0 = none, else >= CMZ_MIN), DX = its offset
; clobbers: AX BX CX DX, flags. SI, DI, DS, ES and BP come back.
;
; IT DOES NOT INSERT. The caller does, through cmz_fill, after the symbol is
; emitted - which is what makes a position findable from the NEXT one and
; keeps the chain in strictly decreasing order.
;
; The walk is hand-rolled and not `repe cmpsb`, because BOTH operands are in
; the SOURCE and that instruction compares DS:SI with ES:DI - ES is the table
; here, DI the output's write pointer, and giving either up would cost a
; segment load per candidate. An 8088's `cmpsb` is ~22 cycles an iteration
; anyway, so the trade is small and it is paid where the registers are scarce.
; -----------------------------------------------------------------------------
cmz_probe:
    push si
    push bp
    push es
    mov [cs:cmz_pos], si
    mov ax, [cs:cmz_n]
    sub ax, si
    cmp ax, CMZ_MIN
    jb .none                    ; fewer than three bytes left to match
    mov [cs:cmz_most], ax       ; ...and the most a match here could be

    mov ax, si                  ; lo = SI - mask: the oldest position still in
    sub ax, [cs:cmz_mask]       ; the window. It borrows for the whole of the
    jnc .havelo                 ; first window, where every position qualifies
    xor ax, ax
.havelo:
    mov [cs:cmz_lo], ax
    mov word [cs:cmz_best], 0

    call cmz_hash               ; BX = &head[h], a word into the block
    mov es, [cs:cmz_tseg]
    mov cx, [es:bx]             ; the newest position with this hash
    mov bp, CMZ_DEPTH
.chain:
    cmp cx, CMZ_NIL
    je .fin
    cmp cx, [cs:cmz_lo]
    jb .fin                     ; out of the window, and so is everything
                                ; behind it - the chain descends
    mov bx, cx                  ; DS:BX = the candidate
    xor ax, ax
    mov si, [cs:cmz_pos]
.walk:
    push ax
    mov al, [bx]
    cmp al, [si]
    pop ax                      ; ...which leaves the flags alone, so the Jcc
    jne .stop                   ; below still reads the compare
    inc bx
    inc si
    inc ax
    cmp ax, [cs:cmz_most]
    jb .walk
.stop:
    cmp ax, [cs:cmz_best]
    jbe .nextc
    mov [cs:cmz_best], ax
    mov ax, [cs:cmz_pos]
    sub ax, cx
    mov [cs:cmz_boff], ax
    mov ax, [cs:cmz_best]
    cmp ax, [cs:cmz_most]
    jae .fin                    ; it reached the end of the input: nothing
.nextc:                         ; behind it in the chain can beat that
    dec bp
    jz .fin
    mov bx, cx
    and bx, [cs:cmz_mask]
    add bx, bx
    mov cx, [es:bx+CMZ_PREV]
    jmp short .chain
.fin:
    mov ax, [cs:cmz_best]
    cmp ax, CMZ_MIN
    jb .none
    mov dx, [cs:cmz_boff]
    jmp short .out
.none:
    xor ax, ax
    xor dx, dx
.out:
    pop es
    pop bp
    pop si
    ret

; -----------------------------------------------------------------------------
; cmz_hash - the three-byte hash of the position at SI (module internal)
; in:  DS = the source, SI = the position, at least CMZ_MIN bytes left
; out: BX = &head[h] - the slot's BYTE offset into the caller's block
; clobbers: AX BX CX, flags
; -----------------------------------------------------------------------------
cmz_hash:
    mov al, [si]                ; h = ((b0 << 8) ^ (b1 << 4) ^ b2) & (HSIZE-1)
    xor ah, ah
    mov cl, 8
    shl ax, cl
    mov bl, [si+1]
    xor bh, bh
    mov cl, 4
    shl bx, cl
    xor ax, bx
    mov bl, [si+2]
    xor bh, bh
    xor ax, bx
    and ax, CMZ_HSIZE - 1
    add ax, ax
    mov bx, ax
    ret

; -----------------------------------------------------------------------------
; cmz_ins - record the position at SI in the chain (module internal)
; in:  DS = the source, ES = the table block, SI = a position with at least
;      CMZ_MIN bytes left
; clobbers: AX BX CX, flags
; -----------------------------------------------------------------------------
cmz_ins:
    call cmz_hash
    mov cx, [es:bx]
    mov [es:bx], si             ; head[h] = SI...
    mov ax, si
    and ax, [cs:cmz_mask]
    add ax, ax
    mov bx, ax
    mov [es:bx+CMZ_PREV], cx    ; ...and prev[SI] = what head[h] was
    ret

; -----------------------------------------------------------------------------
; cmz_fill - record AX positions from SI (module internal)
; in:  DS = the source, SI = the first, AX = how many (a match's length, or 1
;      for a literal)
; clobbers: the flags. Every register comes back, ES included.
;
; EVERY POSITION A MATCH COVERS GOES IN, and it is worth 2.5 points of the 5.7
; this encoder beats the build's LZ4 by: nothing else would ever put them
; there, and a later position matching INTO the middle of an earlier match is
; common. It costs a hash and two stores per byte and no walk, so it is paid
; where the parse was already free.
;
; ES is swapped ONCE for the whole run rather than per position, which is the
; only reason this is a routine and not three lines at the call site.
; -----------------------------------------------------------------------------
cmz_fill:
    push ax
    push bx
    push cx
    push dx
    push si
    push bp
    push es
    mov bp, ax
    or bp, bp
    jz .out
    mov dx, [cs:cmz_n]
    sub dx, CMZ_MIN             ; the last position a three-byte hash exists
    mov es, [cs:cmz_tseg]       ; at, and cmz_n is over CMZ_SLACK so this
.one:                           ; cannot borrow
    cmp si, dx
    ja .out                     ; ...the tail, where cmz_probe would refuse too
    call cmz_ins
    inc si
    dec bp
    jnz .one
.out:
    pop es
    pop bp
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; cmz_bit - append one bit to the output, CF = its value (module internal)
; clobbers: the flags, and DI advances when a tag byte is opened
;
; TAG BYTES, MSB FIRST - os88lz.py's _BitOut, which is that way round so the
; 8086 READER can carry the tag in DL behind a guard bit and spend no register
; on a counter (kernel/lz.inc's LZ_GETBIT).
; -----------------------------------------------------------------------------
cmz_bit:
    push ax
    push bx
    push cx
    jc .one
    call cmz_room
    dec byte [cs:cmz_tbit]
    jmp short .store
.one:
    call cmz_room
    dec byte [cs:cmz_tbit]
    mov cl, [cs:cmz_tbit]
    mov al, 1
    shl al, cl
    or [cs:cmz_tag], al
.store:
    mov al, [cs:cmz_tag]
    mov bx, [cs:cmz_tofs]
    mov [es:bx], al             ; ...written back every time, so a stream that
    pop cx                      ; ends mid-tag is still whole
    pop bx
    pop ax
    ret

; cmz_room - make sure a tag byte is open (module internal)
cmz_room:
    cmp byte [cs:cmz_tbit], 0
    jne .have
    mov [cs:cmz_tofs], di
    mov byte [cs:cmz_tag], 0
    mov byte [cs:cmz_tbit], 8
    push ax
    xor al, al
    stosb                       ; ...reserved in the output, filled in above
    pop ax
.have:
    ret

; -----------------------------------------------------------------------------
; cmz_gamma - the interlaced Elias code os88lz.py writes (module internal)
; in:  AX = the value, >= 2
; clobbers: the flags, and DI through cmz_bit
;
; Bits of the value from one below the top down to 0, each followed by a
; continuation bit - 1 while more follow, 0 on the last. The top bit is
; implicit, which is why the value may not be 1.
; -----------------------------------------------------------------------------
cmz_gamma:
    push ax
    push cx
    push dx
    mov dx, ax
    mov cl, 15                  ; find the top bit
.top:
    mov ax, dx
    shr ax, cl
    test ax, 1
    jnz .got
    dec cl
    jnz .top
.got:
    or cl, cl
    jz .out                     ; a value of 1: nothing after the implicit bit
    dec cl
.emit:
    mov ax, dx
    shr ax, cl
    shr ax, 1                   ; CF = bit CL of the value
    call cmz_bit
    or cl, cl
    jz .last
    stc
    call cmz_bit
    dec cl
    jmp short .emit
.last:
    clc
    call cmz_bit
.out:
    pop dx
    pop cx
    pop ax
    ret

; --- the module's own scratch ------------------------------------------------
; A module image is loaded into a heap claim, so it is WRITABLE - which is what
; lets these live here and be reached `cs:`, with DS and ES both spent on the
; caller's buffers. Twenty-two bytes; the 40KB that is NOT here is the
; caller's.
cmz_n:      dw 0                ; the source's length
cmz_lim:    dw 0                ; ...less CMZ_SLACK: where the write bails
cmz_mask:   dw 0                ; the window, less one (the caller's dial)
cmz_tseg:   dw 0                ; the caller's head[]/prev[] block
cmz_pos:    dw 0                ; cmz_probe's position, which its walk moves SI
cmz_most:   dw 0                ; ...the longest match it could return
cmz_lo:     dw 0                ; ...and the oldest position in the window
cmz_best:   dw 0                ; the best length found so far, and
cmz_boff:   dw 0                ; the offset that produced it
cmz_mx:     dw 0                ; the worst (produced - consumed) so far
cmz_nextp:  dw 0                ; the SI the next progress report is owed at
cmz_tofs:   dw 0                ; where the tag byte being filled lives
cmz_tag:    db 0                ; ...its value so far
cmz_tbit:   db 0                ; ...and the bits still free in it

section .text
