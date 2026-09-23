; =============================================================================
; os8088 - apps/tithe/ticl.inc
;
; THE MELEE CLASH (SPEC.md 97.4.7, TITHE-PLAN 3.9.2).
;
; The reference lets its melee figures OVERLAP when they trade. This board's
; sheared grid gives every cell a rectangle of its own and the renderer blits
; one opaque band an actor, so each fighter swings in its own rectangle - its
; four attack frames out of the attack claim, one band apiece. A composed
; overlap (tier B) was built beside it to be LOOKED at, and was dropped on the
; look: it flashed what was around it and cost ~70 ms a frame.
; =============================================================================

TI_CLFRAMES equ 16                 ; how long a clash runs
TI_CLSTEP   equ 8                  ; how far a fighter steps toward the line -
                                   ; A MULTIPLE OF 8, so tier A stays two
                                   ; ordinary bands with no composition at all

; -----------------------------------------------------------------------------
; ti_cl_fire - start a clash in lane [ti_pjlane], front columns 1 and 2
; Preserves every register.
; -----------------------------------------------------------------------------
ti_cl_fire:
    call ti_rv_atk_flush            ; a played cell swings with every frame
    mov byte [ti_clash], TI_CLFRAMES
    ret

; ti_cl_frame - AX = which of the four ATTACK frames the clash is on: the
; swing spread evenly over TI_CLFRAMES, so it lands in the middle of the lean.
; Preserves every other register.
ti_cl_frame:
    push dx
    mov al, TI_CLFRAMES
    sub al, [ti_clash]
    xor ah, ah
    shl ax, 1
    shl ax, 1                       ; x the four frames
    mov dl, TI_CLFRAMES
    div dl
    xor ah, ah
    cmp ax, TI_POSES - 1
    jbe .ok
    mov ax, TI_POSES - 1
.ok:
    pop dx
    ret

; ti_cl_lunge - [ti_cdx] = how far attack frame AX steps toward the enemy:
; TI_CLSTEP on the strike and the follow-through, nothing on the wind-up and
; the recovery. Preserves every register.
;
; THE LUNGE IS IN THE FRAME, NOT IN THE BAND. It moved the BAND eight pixels,
; which left the trailing eight columns of the last frame on the glass - on a
; mirrored P2 fighter, a slice of the figure standing beside it. Moving the
; character INSIDE its band keeps the band self-erasing (SPEC.md 97.4), and a
; mirrored cell mirrors the step with everything else, so P2 lunges left.
ti_cl_lunge:
    push ax
    mov word [ti_cdx], 0
    cmp ax, 1
    je .step
    cmp ax, 2
    jne .out
.step:
    mov word [ti_cdx], TI_CLSTEP / 8
.out:
    pop ax
    ret

; ti_cl_mine - CF=1 if cell AX is one of the two fighters in the clash now
; running (columns 1 and 2 of the lane). Preserves every register.
ti_cl_mine:
    push ax
    push cx
    push dx
    cmp byte [ti_clash], 0
    je .no
    xor dx, dx
    mov cx, TI_ROWS
    div cx                          ; AX = column, DX = row
    cmp dl, [ti_pjlane]
    jne .no
    cmp al, 1
    je .yes
    cmp al, 2
    je .yes
.no:
    clc
    jmp short .out
.yes:
    stc
.out:
    pop dx
    pop cx
    pop ax
    ret

; ti_cl_tiera - TIER A's frame: both fighters, from their ATTACK slots, every
; frame of the clash - they lean and swing in their own rectangles, two
; ordinary bands and no composition (SPEC.md 97.4.7). Preserves registers.
ti_cl_tiera:
    push ax
    mov al, [ti_pjlane]
    xor ah, ah
    add ax, TI_ROWS                 ; cell (1, lane)
    call ti_feature
    add ax, TI_ROWS                 ; ...and (2, lane)
    call ti_feature
    pop ax
    ret
