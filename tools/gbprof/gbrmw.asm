; gbrmw - the read-modify-writes of (HL), each run on an address the
; recompiler's form of them takes directly (WRAM) and on one it hands to the
; interpreter (TMA, FF06), for RealBoy's gbcpu row (docs/REALBOY-SPEC.md
; section 16.6, apps/realboy/rbgen.py rmw_lines).
;
; Assembled with rgbds by tools/gbours.py (tools/gbclock.py's pinned build).
; It ships nowhere; it is ours, so it may go on any disk.
;
; Ops runs INC, DEC, every rotate and shift, SWAP, SET and RES on [HL], and
; folds the flags after each into a running sum; the next RL/RR takes the
; op's own carry, flipped. The two addresses start equal and must stay
; equal, and so must their sums: run 300 times, so that Ops is translated (a
; PC is on its 64th entry, RB_JITHOT) and then runs translated. It prints
; "Passed" or "Failed" on the link port, as Blargg's ROMs do. Irq does the
; same for a store through (HL) that requests an interrupt, which a store
; that guards itself (rbgen.self_guard) must leave its block for.

SECTION "timer", ROM0[$50]
    push af                                 ; the timer interrupt: counts
    ld a, [$C020]
    inc a
    ld [$C020], a
    pop af
    reti

SECTION "header", ROM0[$100]
    nop
    jp Start
    ds $150 - @, 0

SECTION "main", ROM0[$150]
Start:
    di
    ld sp, $FFFE
    ld a, $5A
    ld [$C000], a
    ldh [$FF06], a                            ; TMA: an I/O register, 8 bits
    xor a
    ld [$C010], a                           ; the WRAM side's flag sum
    ld [$C011], a                           ; ...and TMA's
    ld [$C020], a                           ; timer interrupts taken
    ld [$C022], a                           ; ...and not taken at once
    ld bc, 300
.loop:
    push bc
    call Irq
    ld hl, $C000
    ld de, $C010
    call Ops
    ld hl, $FF06
    ld de, $C011
    call Ops
    pop bc
    dec bc
    ld a, b
    or c
    jr nz, .loop
    ld a, [$C000]
    ld b, a
    ldh a, [$FF06]
    cp b
    ld hl, FailValue
    jr nz, .print
    ld a, [$C010]
    ld b, a
    ld a, [$C011]
    cp b
    ld hl, FailFlags
    jr nz, .print
    ld a, [$C022]
    or a
    ld hl, FailLate
    jr nz, .print
    ld a, [$C020]
    cp 300 & $FF
    ld hl, FailCount
    jr nz, .print
    ld hl, Passed
.print:
    ld a, [hl+]
    or a
    jr z, .done
    ldh [$FF01], a
    ld a, $81
    ldh [$FF02], a
    jr .print
.done:
    jr .done

; [HL] through every read-modify-write, the flags into [DE] after each
Ops:
    inc [hl]
    call Fold
    dec [hl]
    dec [hl]
    call Fold
    rlc [hl]
    call Fold
    rrc [hl]
    call Fold
    rl [hl]
    call Fold
    rr [hl]
    call Fold
    sla [hl]
    call Fold
    sra [hl]
    call Fold
    swap [hl]
    call Fold
    srl [hl]
    call Fold
    set 6, [hl]
    res 1, [hl]
    set 0, [hl]
    call Fold
    inc [hl]
    inc [hl]
    swap [hl]
    dec [hl]
    ret

; A store through (HL) to IF that requests the timer interrupt must take it
; before the next instruction: the store's slow path leaves the block for it
Irq:
    ld hl, $FFFF
    ld [hl], $04                            ; IE: the timer
    ld a, [$C020]
    ld d, a
    ei
    ld hl, $FF0F
    ld [hl], $04                            ; IF: the timer - taken here
    ld a, [$C020]
    di
    sub d
    dec a
    ret z
    ld a, 1
    ld [$C022], a
    ret

; F into the sum at [DE], with the carry of the add left for the next op
Fold:
    push af
    push hl
    push af
    pop hl                                  ; L = F
    ld a, [de]
    add a, l
    ld [de], a
    pop hl
    pop af
    ccf                                     ; (the carry the next RL/RR takes
    ret                                     ;   is still the op's own, flipped)

Passed:
    db "Passed", 10, 0
FailValue:
    db "Failed: the two values parted", 10, 0
FailFlags:
    db "Failed: the two flag sums parted", 10, 0
FailLate:
    db "Failed: an interrupt was taken late", 10, 0
FailCount:
    db "Failed: interrupts lost", 10, 0
