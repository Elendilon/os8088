; =============================================================================
; os8088 - apps/os88gfx.inc
;
; THE EMBEDDABLE GRAPHICS LIBRARY (docs/plans/GFX-EMBEDDABLE-PLAN.md): drawing
; code that lives in the PACKAGE rather than in the kernel, taken capability by
; capability, so a program pays for what it draws and a machine that runs none
; of those programs pays nothing at all.
;
; The premise is the owner's: duplicate code only used by apps that monopolise
; the machine anyway, instead of permanently spending kernel RAM on them. Two
; measured facts turn that from a size trade into a straight win - an app-side
; rasteriser is FASTER than the slot (24.6 us a pixel against gfx_line's 31.6
; with the arrival removed), and kern_small has never had gfx_line_fast at all
; (SPEC.md 5.6.4.1 is %ifdef KERN_BIG), so in a library the floor machine can
; BUY a capability the kernel never gave it.
;
; --- THE LATTICE RULE, as set -----------------------------------------------
;
;   wanting one capability should not drag in unused others. So walk drags in
;   "how to draw a line", but "how to draw a line" does not drag in the walk.
;
; So every capability is a %define before the %include, an implication is a
; %define at the top of this file (the way os88ui.inc's OS88UI_BARONLY already
; defines OS88UI_NOBTN), and an arm nobody asked for emits NOTHING.
;
;   %define GFXE_BAND_W   128            ; a multiple of 8
;   %define GFXE_BAND_H   128
;   %define GFXE_BAND_BUF my_mask        ; GFXE_BAND_SZ bytes, yours
;   %define GFXE_LINE                    ; implies GFXE_BAND
;   %include "os88gfx.inc"
;
; --- WHERE IT GOES ----------------------------------------------------------
; AT THE END OF YOUR CODE, just before OS88_BSS - os88ui.inc's rule and for
; os88ui.inc's reason: the header and any OS88_ICON16 block are at FIXED
; OFFSETS in the image (SPEC.md 20.2), and code emitted between them fails the
; icon macro's own offset assertion.
;
; This file's own state is a handful of words IN THE IMAGE, not in bss. A
; package image is copied into the instance's own region and is writable, so
; an image word is per-instance exactly as a bss word is; what it saves is the
; caller having to find offsets for it. The BAND ITSELF is the caller's,
; because only the caller knows how big it can afford to be and only the
; caller can put it in bss.
;
; --- CAPABILITIES -----------------------------------------------------------
;
;   GFXE_BAND     compose into your own 1bpp band and commit it with one
;                 OSAPI_GFX_BLIT1. The PIXEL primitive lives here - a bit-set,
;                 not a slot - and so does the running-bounds bookkeeping that
;                 turns a figure into the smallest band that covers it.
;   GFXE_LINE     Bresenham, whole line, into the band. Implies GFXE_BAND.
;
; Later waves add GFXE_LINE_FAST (SPEC.md 5.6.4.1's interval walk, 4.9x),
; GFXE_WIDE (5.6.5's dilation), GFXE_WALK (the resumable recurrence, plotting
; through OSAPI_GFX_POINTS) and GFXE_POINTS (the point-array sink). The plan's
; 4.1 is the table and 4.1.1 the sub-dial inside GFXE_LINE_FAST, which is
; already priced against what dropping each piece costs in speed.
;
; --- THE INK POLARITY, and the one that is DELIBERATELY NOT HERE ------------
; A band is composed on LIT paper and inked by CLEARING bits: 1 = a lit pixel
; is OSAPI_GFX_BLIT1's own convention and SPEC.md 42.23 measured it the right
; way round to store (it agrees with the BMP palette AND takes rep stosw's
; 12.5 clocks a byte for the ground instead of a complementing loop's 17 - the
; intuitive polarity costs 36% of every clear for ever).
;
; THE OPPOSITE POLARITY - ink that SETS bits, for a program composing white on
; a black ground - is six lines under a %if and is NOT in this file, because
; an untested arm in a shared library is worse than an absent one. What it
; needs is written down rather than guessed at: BL walks a ONE instead of a
; zero (`mov bl, 080h` in place of `07Fh`), the combine is `or` instead of
; `and`, and the two wrap branches invert sense because the carry out of the
; rotate is then the bit that just left. gfxe_bclear already takes the paper
; word in AX, so THAT half needs nothing.
;
; --- REGISTERS --------------------------------------------------------------
; Every routine documents what it clobbers rather than preserving everything:
; gfxe_line is an inner loop and a pair of pushes a line is a real cost on the
; machine this targets. Nothing here touches a segment register except
; gfxe_bput, which restores it.
; =============================================================================

%ifdef GFXE_LINE
  %define GFXE_BAND                     ; the lattice, downward only: a line
%endif                                  ; needs somewhere to land, a band does
                                        ; not need a line

%ifdef GFXE_BAND

  %ifndef GFXE_BAND_W
    %error "os88gfx.inc: GFXE_BAND wants GFXE_BAND_W (a multiple of 8)"
  %endif
  %ifndef GFXE_BAND_H
    %error "os88gfx.inc: GFXE_BAND wants GFXE_BAND_H"
  %endif
  %ifndef GFXE_BAND_BUF
    %error "os88gfx.inc: GFXE_BAND wants GFXE_BAND_BUF - GFXE_BAND_SZ bytes"
  %endif
  %if (GFXE_BAND_W & 7) != 0
    %error "os88gfx.inc: GFXE_BAND_W must be a multiple of 8"
  %endif

%assign GFXE_BAND_ST GFXE_BAND_W / 8    ; the stride, in bytes a row
%assign GFXE_BAND_SZ GFXE_BAND_ST * GFXE_BAND_H

; The row step. A power-of-two stride is a shift and anything else is a mul -
; decided HERE, at assembly time, so a caller who sizes a band conveniently
; gets the cheap arm and one who does not still gets a correct one. It is once
; a line, not once a pixel, so even the mul is noise against the walk.
%assign GFXE_BAND_SH 0
%assign gfxe_t GFXE_BAND_ST
%rep 16
  %if gfxe_t > 1
    %assign gfxe_t gfxe_t / 2
    %assign GFXE_BAND_SH GFXE_BAND_SH + 1
  %endif
%endrep
%if (1 << GFXE_BAND_SH) == GFXE_BAND_ST
  %define GFXE_BAND_POW2
%endif

; AX = y -> AX = the row's byte offset; clobbers CL (and DX, BX on the mul arm)
%macro GFXE_ROWOFF 0
  %ifdef GFXE_BAND_POW2
    mov cl, GFXE_BAND_SH
    shl ax, cl
  %else
    mov bx, GFXE_BAND_ST
    mul bx
  %endif
%endmacro

; -----------------------------------------------------------------------------
; gfxe_bnew - start a band: seed the running bounds from one point
; in:  AX = x, DX = y (in the caller's own drawing space, whatever that is)
; out: nothing; clobbers nothing
;
; The bounds are SIGNED throughout (gfxe_bfold's compares are jge/jle, not
; jae/jbe): a figure can put a vertex off the left of its area for a frame,
; and an unsigned minimum takes -3 for 65533 and sizes the band to the screen.
; -----------------------------------------------------------------------------
gfxe_bnew:
    mov [gfxe_mnx], ax
    mov [gfxe_mxx], ax
    mov [gfxe_mny], dx
    mov [gfxe_mxy], dx
    ret

; -----------------------------------------------------------------------------
; gfxe_bfold - widen the running bounds to include a whole vertex array
; in:  SI = the x array, DI = the y array, CX = how many (>= 1)
; out: nothing; clobbers AX, BX, CX, flags
;
; Call it once per FIGURE, and once more for the figure already on the glass:
; a band erases by COVERING, so anything still down has to be inside it.
; -----------------------------------------------------------------------------
gfxe_bfold:
    xor bx, bx
.v:
    mov ax, [si + bx]
    cmp ax, [gfxe_mnx]
    jge .nx
    mov [gfxe_mnx], ax
.nx:
    cmp ax, [gfxe_mxx]
    jle .xx
    mov [gfxe_mxx], ax
.xx:
    mov ax, [di + bx]
    cmp ax, [gfxe_mny]
    jge .ny
    mov [gfxe_mny], ax
.ny:
    cmp ax, [gfxe_mxy]
    jle .xy
    mov [gfxe_mxy], ax
.xy:
    add bx, 2
    dec cx
    jnz .v
    ret

; -----------------------------------------------------------------------------
; gfxe_bsize - close the bounds into a band the buffer can hold
; in:  the running bounds
; out: CF = 1 the band does not fit - draw this frame some other way;
;      CF = 0 and [gfxe_bx0]/[gfxe_by0]/[gfxe_bw]/[gfxe_bh] are the band
;      clobbers AX, flags
;
; One pixel of margin all round, then x0 and the width onto the BYTE GRID that
; OSAPI_GFX_BLIT1's fast path insists on (SPEC.md 5.4.2.5 takes any width, but
; x must be a multiple of 8). y needs no grid.
;
; REFUSING IS A NORMAL PATH and it is why this is separate from gfxe_bput: the
; caller has to find out that the band will not fit BEFORE it has spent a blit
; on it, and refusing is a lot cheaper than clipping.
; -----------------------------------------------------------------------------
gfxe_bsize:
    mov ax, [gfxe_mnx]
    dec ax
    and ax, 0FFF8h
    mov [gfxe_bx0], ax
    mov ax, [gfxe_mxx]
    add ax, 8                       ; +1 of margin, then rounded UP to the byte
    and ax, 0FFF8h
    sub ax, [gfxe_bx0]
    cmp ax, GFXE_BAND_W
    ja .no
    mov [gfxe_bw], ax
    mov ax, [gfxe_mny]
    dec ax
    mov [gfxe_by0], ax
    mov ax, [gfxe_mxy]
    add ax, 2                       ; +1 of margin, +1 to make it a COUNT
    sub ax, [gfxe_by0]
    cmp ax, GFXE_BAND_H
    ja .no
    mov [gfxe_bh], ax
    clc
    ret
.no:
    stc
    ret

; -----------------------------------------------------------------------------
; gfxe_bclear - paper the band's rows
; in:  AX = the paper word (0FFFFh = lit, the usual; 0 = a black ground)
; out: nothing; clobbers AX, CX, DI, ES, flags
;
; Only the rows this band HAS. The buffer is sized for GFXE_BAND_H and a real
; frame rarely wants them all, so clearing the lot would be most of the cost
; of a small band.
; -----------------------------------------------------------------------------
gfxe_bclear:
    push es
    push ax
    push ds
    pop es
    mov di, GFXE_BAND_BUF
    mov ax, [gfxe_bh]
%ifdef GFXE_BAND_POW2
    mov cl, GFXE_BAND_SH - 1        ; bh * stride bytes = bh * stride/2 words
    shl ax, cl
%else
    mov cx, GFXE_BAND_ST / 2
    mul cx
%endif
    mov cx, ax
    pop ax
    cld
    rep stosw
    pop es
    ret

; -----------------------------------------------------------------------------
; gfxe_bpix - one pixel into the band, in BAND coordinates
; in:  AX = x, DX = y; both inside the band - THIS DOES NOT CLIP
; out: nothing; clobbers AX, BX, CX, DX, DI, flags
;
; The pixel primitive is a bit-set and not a slot, which is the whole of why a
; band composer is worth having: a plotted pixel here is a read-modify-write,
; against OSAPI_GFX_PIXEL's 640.87 us on the field machine.
; -----------------------------------------------------------------------------
gfxe_bpix:
    push ax
    mov ax, dx
    GFXE_ROWOFF
    mov di, ax
    pop ax
    mov bx, ax
    mov cl, 3
    shr bx, cl
    add di, bx
    and al, 7
    mov cl, al
    mov bl, 07Fh
    ror bl, cl
    and [GFXE_BAND_BUF + di], bl
    ret

; -----------------------------------------------------------------------------
; gfxe_bput - the band onto the glass, ONE arrival (SPEC.md 5.4.2)
; in:  the gfx lock held, the clip armed, the band composed
; out: CF = 1 REFUSED - a kern_small kernel before SPEC.md 5.4.2.5.1 carries
;      the slot and not the body, so a package that can be run on one has to
;      have a second way to draw; clobbers AX, BX, CX, DX, SI, BP, flags
;
; The STRIDE stays the buffer's whatever the band's width is, so gfxe_line's
; row step never has to change - only the COLUMNS committed shrink.
; -----------------------------------------------------------------------------
gfxe_bput:
    push es
    push ds
    pop es
    mov si, GFXE_BAND_BUF
    mov bp, GFXE_BAND_ST
    mov ax, [gfxe_bx0]
    mov bx, [gfxe_by0]
    mov cx, [gfxe_bw]
    mov dx, [gfxe_bh]
    call OSAPI_GFX_BLIT1
    pop es                          ; `pop` writes no flag, so BLIT1's CF is
    ret                             ; still the caller's answer

%endif ; GFXE_BAND

%ifdef GFXE_LINE
; -----------------------------------------------------------------------------
; gfxe_line - one line into the band, in BAND coordinates
; in:  AX = x1, BX = y1, CX = x2, DX = y2; all inside the band - NO CLIPPING
; out: nothing; clobbers AX, BX, CX, DX, SI, DI, BP, flags
;
; Ordered left to right first, so the x step is always +1 and only the y step
; carries a sign - which halves the octant count for free and is why there are
; two loop bodies here rather than eight.
;
; The bit is an AND MASK and not a set bit (see the polarity note in the header
; at the top of this file), so it walks by rotating a ZERO along with stc/rcr,
; and the carry OUT of that rotate is the wrap into the next byte. That is one
; instruction for the advance and one branch for the wrap, which is the whole
; reason this is worth having over a per-pixel slot.
;
; ~24.6 us a pixel on a 4.77MHz 8088 against OSAPI_GFX_LINE's 31.6 with the
; arrival removed and 37.1 with it (PERFORMANCE.md Set 132) - so the library
; is FASTER than the slot it replaces as well as cheaper on the kernel.
; -----------------------------------------------------------------------------
gfxe_line:
    cmp ax, cx
    jle .ord
    xchg ax, cx                     ; left to right, both ends
    xchg bx, dx
.ord:
    mov [gfxe_lx1], ax
    mov [gfxe_ly1], bx
    sub cx, ax
    mov [gfxe_ldx], cx
    mov ax, dx
    sub ax, bx
    mov word [gfxe_lsy], GFXE_BAND_ST
    jns .dy
    neg ax
    mov word [gfxe_lsy], -GFXE_BAND_ST
.dy:
    mov [gfxe_ldy], ax

    mov ax, [gfxe_ly1]              ; the first byte, and the bit in it
    GFXE_ROWOFF
    mov di, ax
    mov ax, [gfxe_lx1]
    mov bx, ax
    mov cl, 3
    shr bx, cl
    add di, bx
    and al, 7
    mov cl, al
    mov bl, 07Fh
    ror bl, cl                      ; the ZERO walks, not the one

    mov ax, [gfxe_ldx]
    cmp ax, [gfxe_ldy]
    jl .majy

    mov si, ax                      ; --- x is the major axis
    inc si
    mov bp, [gfxe_ldy]
    add bp, bp
    mov [gfxe_le1], bp
    sub bp, ax
    add ax, ax
    mov [gfxe_le2], ax
.mx:
    and [GFXE_BAND_BUF + di], bl
    stc
    rcr bl, 1
    jc .mx1
    mov bl, 07Fh
    inc di
.mx1:
    add bp, [gfxe_le1]
    jle .mx2
    sub bp, [gfxe_le2]
    add di, [gfxe_lsy]
.mx2:
    dec si
    jnz .mx
    ret

.majy:                              ; --- ...or y is
    mov si, [gfxe_ldy]
    inc si
    mov bp, [gfxe_ldx]
    add bp, bp
    mov [gfxe_le1], bp
    sub bp, [gfxe_ldy]
    mov ax, [gfxe_ldy]
    add ax, ax
    mov [gfxe_le2], ax
.my:
    and [GFXE_BAND_BUF + di], bl
    add di, [gfxe_lsy]
    add bp, [gfxe_le1]
    jle .my2
    sub bp, [gfxe_le2]
    stc
    rcr bl, 1
    jc .my2
    mov bl, 07Fh
    inc di
.my2:
    dec si
    jnz .my
    ret
%endif ; GFXE_LINE

; --- the library's own state, in the IMAGE (see the header) ------------------
%ifdef GFXE_BAND
gfxe_mnx:   dw 0                    ; the running bounds gfxe_bfold widens
gfxe_mxx:   dw 0
gfxe_mny:   dw 0
gfxe_mxy:   dw 0
gfxe_bx0:   dw 0                    ; ...closed by gfxe_bsize into the band
gfxe_by0:   dw 0
gfxe_bw:    dw 0
gfxe_bh:    dw 0
%endif
%ifdef GFXE_LINE
gfxe_lx1:   dw 0                    ; gfxe_line's working set
gfxe_ly1:   dw 0
gfxe_ldx:   dw 0
gfxe_ldy:   dw 0
gfxe_lsy:   dw 0
gfxe_le1:   dw 0
gfxe_le2:   dw 0
%endif
