; =============================================================================
; tapelend - THE GATE ON OSAPI_PIT_LEND (SPEC.md 88.5, and 34.1's exception)
;
; docs/plans/CASSETTE-PLAN.md makes this wave 3's gate and says why it exists
; before any tape code does: the cell amends a rule SPEC.md 34.1 wrote down so
; the argument would stop recurring - "PIT channel 0 is never written" - and
; every claim made for the amendment is a behaviour nothing had exercised.
;
; **THE POSITIVE CONTROLS ARE THE POINT.** A cell that refused everything would
; pass every negative case here, so the claim is TAKEN first and the tone is
; checked working again AFTER the release. Without those two this file would
; rubber-stamp an `stc / ret`.
;
; What it pins down, one results byte each:
;
;   * a CLAIM is granted on a stock kernel, and REFUSED with AH=1 on a
;     QUANTUM= one, where [sch_fast] has moved the divisor and the restore
;     could not be a constant. That arm is the whole reason the refusal exists
;     and the driver builds a second kernel to reach it.
;   * a SECOND claim is refused with AH=3 - which is what stops two Tape
;     windows interleaving their blocks onto one tape (SPEC.md 88.5).
;   * the speaker is REFUSED while the claim is held and WORKS again after the
;     release, which is 34.1's one-owner rule working in both directions.
;   * ENTER without a claim is refused: the claim is what licenses the write.
;   * LEAVE PRESERVES AX, BX, DX AND THE FLAGS. A package calls it as the very
;     first thing after `int 15h`, so the ROM's answer has to survive it -
;     that promise is in the contract and this is what holds it to it.
;   * RELEASE is IDEMPOTENT, so a refusal path may call it blind.
;   * [ticks] still advances after a bracket, which is the whole of "nothing
;     can observe the mode change".
;
; It does NOT call `int 15h` and needs no cassette: the cell is a kernel
; contract and this tests the kernel. The transport's own gate is tapehw.
;
; NEVER SHIPPED. Its own scratch image, the lzfence precedent:
;   make tapelendtest && python3 tests/tapelend.py
; =============================================================================

%include "os88api.inc"

    OS88_HEADER 'TAPELEND', tl_entry

; The results block. The driver finds TL_MAGIC in the package's image and
; reads the bytes after it, so the layout here IS the ABI with tests/tapelend.py.
TL_MAGIC    equ 0x4C54          ; 'TL'

; -----------------------------------------------------------------------------
tl_entry:
    ; --- 1. ENTER before any claim: the claim is what licenses the write ----
    mov al, OSAPI_PL_ENTER
    call OSAPI_PIT_LEND
    sbb al, al                  ; CF -> 0x00 / 0xFF without a branch
    mov [tl_r_entnc], al

    ; --- 2. the CLAIM itself, and WHY if it refused -------------------------
    mov al, OSAPI_PL_CLAIM
    call OSAPI_PIT_LEND
    mov [tl_r_clah], ah         ; AH is only meaningful on CF=1, and the driver
    sbb al, al                  ; knows that
    mov [tl_r_claim], al
    cmp al, 0
    jne .refused                ; a QUANTUM= kernel: the rest cannot be run,
                                ; and the driver asserts exactly that

    ; --- 3. a SECOND claim must refuse with AH = 3 --------------------------
    mov al, OSAPI_PL_CLAIM
    call OSAPI_PIT_LEND
    mov [tl_r_cl2h], ah
    sbb al, al
    mov [tl_r_claim2], al

    ; --- 4. the speaker is refused while we hold it -------------------------
    mov ax, 1000                ; a legal tone: 1 kHz for 1 tick
    mov cx, 1
    mov dl, 0x40
    call OSAPI_SND_TONE
    sbb al, al
    mov [tl_r_tone1], al

    ; --- 5. ENTER, now that the claim is held -------------------------------
    mov al, OSAPI_PL_ENTER
    call OSAPI_PIT_LEND
    sbb al, al
    mov [tl_r_enter], al

    ; --- 6. LEAVE preserves AX, BX, DX and the FLAGS ------------------------
    ; The register set is the ROM's answer to `int 15h AH=02`: AH a status, AL
    ; whatever it left, BX one past the last byte stored, DX the byte count.
    ; Poison all three, set CF, and require every bit back.
    mov ax, 0x1234              ; AL is the verb, so AH is the witness: the
    mov bx, 0x5678              ; contract promises AX back and the caller's
    mov dx, 0x9ABC              ; own AL went in as the verb
    stc
    mov al, OSAPI_PL_LEAVE
    call OSAPI_PIT_LEND
    pushf                       ; the flags FIRST: everything below writes them
    pop si
    mov cl, 0                   ; assume the worst
    cmp ah, 0x12                ; AH untouched
    jne .lvbad
    cmp bx, 0x5678              ; BX untouched - the ROM's end-of-output pointer
    jne .lvbad
    cmp dx, 0x9ABC              ; DX untouched - the ROM's byte count
    jne .lvbad
    test si, 1                  ; ...and CF is still the ROM's
    jz .lvbad
    mov cl, 1
.lvbad:
    mov [tl_r_leave], cl

    ; --- 7. [ticks] still advances: nothing observed the mode change --------
    ; A BOUNDED SPIN AND NOT OSAPI_TASK_SLEEP: the entry proc is UI-task
    ; context and the gfx lock MAY BE HELD (apps/os88api.inc:1425), so
    ; sleeping here would park the task that is holding it. IRQ0 is not
    ; masked, so [ticks] advances while we spin.
    call OSAPI_GET_TICKS
    mov bx, ax
    mov cl, 0
    mov di, 0                   ; the cap: ~65k passes is far more than a tick
.tkspin:
    call OSAPI_GET_TICKS
    cmp ax, bx
    jne .tkmoved
    dec di
    jnz .tkspin
    jmp short .tkbad            ; the clock never moved at all
.tkmoved:
    sub ax, bx
    cmp ax, 200                 ; ...or it ran away, which is what a mode-3
    ja .tkbad                   ; counter read through mode-2 arithmetic
    mov cl, 1                   ; would look like
.tkbad:
    mov [tl_r_ticks], cl

    ; --- 8. RELEASE, twice: the second is a no-op ---------------------------
    mov al, OSAPI_PL_RELEASE
    call OSAPI_PIT_LEND
    sbb al, al
    mov [tl_r_rel1], al
    mov al, OSAPI_PL_RELEASE
    call OSAPI_PIT_LEND
    sbb al, al
    mov [tl_r_rel2], al

    ; --- 9. ...and the speaker is ours again --------------------------------
    mov ax, 1000
    mov cx, 1
    mov dl, 0x40
    call OSAPI_SND_TONE
    sbb al, al
    mov [tl_r_tone2], al
    xor ax, ax                  ; and silence it again immediately
    call OSAPI_SND_TONE

.refused:
    ; The package opens no window: there is nothing to look at and a window
    ; would only be a thing the driver had to close. Refusing the launch is
    ; the established way for a test package to run and stop (fmtest's shape).
    stc
    retf

; -----------------------------------------------------------------------------
; THE DRIVER'S ABI. Every byte is 0x00 = the check passed, 0xFF = CF came back
; set, or 0/1 where the comment says so. 0x3F ('?') is "never reached", which
; is what the QUANTUM= arm leaves behind everything after the claim.
            dw TL_MAGIC
tl_r_entnc:  db 0x3F            ; ENTER with no claim   -> want 0xFF (refused)
tl_r_claim:  db 0x3F            ; CLAIM                 -> want 0x00 (stock)
tl_r_clah:   db 0x3F            ;   ...its AH           -> want 1 on QUANTUM=
tl_r_claim2: db 0x3F            ; the second CLAIM      -> want 0xFF
tl_r_cl2h:   db 0x3F            ;   ...its AH           -> want 3
tl_r_tone1:  db 0x3F            ; tone while claimed    -> want 0xFF
tl_r_enter:  db 0x3F            ; ENTER while claimed   -> want 0x00
tl_r_leave:  db 0x3F            ; LEAVE preserved all   -> want 1
tl_r_ticks:  db 0x3F            ; [ticks] advanced      -> want 1
tl_r_rel1:   db 0x3F            ; RELEASE               -> want 0x00
tl_r_rel2:   db 0x3F            ; RELEASE again         -> want 0x00
tl_r_tone2:  db 0x3F            ; tone after release    -> want 0x00

    OS88_IMAGE_END
