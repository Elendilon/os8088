; =============================================================================
; os8088 - apps/os88fsxw.inc - which display a FULL SCREEN goes to (SPEC.md
; 53.1.2.1)
;
; The owner's rule: if the content runs on display type A and not on type B,
; going full screen is NOT a refusal wherever the window happens to stand - it
; goes to a screen of the type the content supports, if the machine has one.
;
; So the order is: the display the window is MOSTLY on (OSAPI_FSX_CAPS with
; the window - its CENTRE, SPEC.md 39.17), when that display can set one of
; the modes you can use; else the first display, walked BX = 1, 2, ..., that
; can; else nothing. That is DrMarco's dm_playdisp and the Video Player's
; walk, written once.
;
; IN-WINDOW drawing is a different question with a different answer: a
; straddling window draws for the MORE RESTRICTIVE display (OSAPI_WM_DISPLAY,
; SPEC.md 39.16.4.1), because it cannot be in two modes at once. Never size or
; colour the window off this include; only the full-screen target and the
; full-screen mode menu.
;
; ASK IT WHERE THE ANSWER IS USED - when the bracket is entered, and when the
; mode menu's captions are composed - because a window moves, and a drag that
; leaves the restrictive display unchanged fires no OSAPI_WM_ONRESIZE.
; =============================================================================

; -----------------------------------------------------------------------------
; fsxw_pick - the full-screen target for a set of modes
; in:  BX = your window, DX = the FSXM_* bits your content can use
; out: CF = 0: AX = the modes that display can set, ANDed with DX (non-zero),
;              DL = that display's VID_* kind,
;              CH = the OSAPI_FSX_RUN display: 0 = the window's own (always,
;              when the window's own display answers), n = display n-1
;      CF = 1: no display on the machine can - AX = 0, CH = 0, DL undefined
; preserves BX, CL, SI, DI, BP and every segment register. Any context: it
; is OSAPI_FSX_CAPS and nothing else.
;
; CH = 0 whenever the window's own display answers, and that is load-bearing:
; kern_small's door refuses any CH, and a SAME-MODE bracket (SPEC.md 53.7) may
; not take one at all - such a package passes only its window's own answer to
; the bracket and should not call this.
; -----------------------------------------------------------------------------
fsxw_pick:
    push bx
    push si
    mov si, dx                      ; the modes the content can use
.ask:
    push bx
    call OSAPI_FSX_CAPS             ; AX = settable, DL = kind; CF = 1 past
    pop bx                          ; the last display
    jc .none
    and ax, si
    jnz .got
    cmp bx, 15                      ; a window pointer is far past 15: the
    jbe .next                       ; walk then starts at display 0
    xor bx, bx
.next:
    inc bx
    jmp short .ask
.got:
    mov ch, 0
    cmp bx, 15
    ja .out                         ; the window's own (CF = 0 from the `ja`)
    mov ch, bl                      ; display BX-1
    clc
    jmp short .out
.none:
    xor ax, ax
    mov ch, 0
    stc
.out:
    pop si
    pop bx
    ret
