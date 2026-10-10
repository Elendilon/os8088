; =============================================================================
; os8088 - apps/skies/csset.inc
;
; THE SETTINGS, KEPT (SPEC.md 88.13.9): the five bytes the Settings page edits,
; a file in SYSTEM\APPDATA, read once in the ENTRY PROC and written when the
; page is left.
;
; The shape is apps/tank's tkhs.inc (SPEC.md 85.9), which is apps/cyclone's
; (SPEC.md 67.20), and its two hard-won rules are repeated here because
; getting either wrong fails QUIETLY:
;
;  - **The file lives in SYSTEM\APPDATA on OUR OWN volume** (SPEC.md 19.9),
;    not beside the package. The file browser is the whole of how a user
;    reaches an application here, so a data file in an app folder is a
;    misclick waiting to happen.
;  - **The folder is reached through apps/os88data.inc**, which walks with
;    OSAPI_FILE_GOTO_QM - the quiet stand that MOVES THE INSTANCE, so the
;    file cell after it resolves there - banks APPDATA's cluster, and
;    rewrites a file of unchanged length with one sector.
;
; This file was the FOURTH copy of an eighty-line walker built out of
; OSAPI_FILE_GOTO, a remount for DISPLAY at every step, and it named the
; shared include as the obvious next step. That step is taken: five packages
; include os88data.inc now (docs/plans/NAV-COST-PLAN.md).
;
; WHEN IT SAVES is the choice this file makes differently to tank's. Tank
; banks a score the moment the initials are typed, inside the fsx bracket,
; because a player expects a score to be theirs as soon as they finish typing
; it. A setting is not like that: the HOTKEYS are deliberately temporary - F1
; to F5 are for trying the next rung while flying and a machine switched off
; mid-flight should not have inherited whatever was being tried - so what is
; written is the SETTINGS PAGE's answer, at the moment the page is left, and
; the file is the considered choice rather than the last experiment.
; =============================================================================

CS_SETFSZ  equ 4 + 5                ; the magic and the five bytes
cs_set_file:  db 'CSSET.DAT', 0
cs_set_magic: db 'CS8', 1           ; so a stale or foreign file is refused
                                    ; rather than decoded
cs_set_ip:    db 0                  ; os88data.inc's in-place stamp, CSSET.DAT

; What each byte is, and the largest value it may hold. A file that matches
; the magic and holds nonsense anyway is CLAMPED and not refused: the magic is
; what tells a foreign file apart, and a rung out of range is one byte of a
; file this program wrote, so the honest answer is the nearest rung rather
; than throwing five good settings away.
cs_set_at:  dw cs_setbld, cs_setlod, cs_setsize, cs_modepref, cs_setfill
cs_set_max: db CSBL_HIGH, CSL_ULTRA, CSZ_FULL, 1, CSFL_ALL
; ...and what a 286 or better starts on with no file at all (SPEC.md 88.13.9).
; NOT cs_set_max: that is a CEILING for the clamp, and the Mode byte's ceiling
; is 1, which is CGA - a machine given the best of everything else would have
; been given the worse of two displays.
cs_set_best: db CSBL_HIGH, CSL_ULTRA, CSZ_FULL, 0, CSFL_ALL
CS_SETN     equ 5

%include "os88data.inc"

; -----------------------------------------------------------------------------
; cs_set_load - read the five bytes once. Anything wrong with the file leaves
; the built-in defaults standing: a settings file is not worth an error box,
; and the first run has no file at all.  UI TASK ONLY.
;
; CALLED FROM cs_entry AND NOT FROM THE FIRST PAINT, which is where tank puts
; its own. Two reasons, and only the first is a rule: SIZE is the last default
; set and it is set from the ADAPTER, which is not known until the window
; exists - so the read has to come after that line or the card overwrites the
; player's answer. The second is an observation this file did not chase: the
; same read AT THE FIRST PAINT left the buffer untouched with the file sitting
; on the disk, and the same read a moment later filled it. tank and cyclone
; both load at their first paint, so it is worth someone's afternoon.
; -----------------------------------------------------------------------------
cs_set_load:
    cmp byte [cs_setread], 0
    jne .out
    mov byte [cs_setread], 1
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    push ds
    pop es
    ; --- A 286 OR BETTER WITH NO FILE STARTS AT THE TOP (SPEC.md 88.13.9).
    ;     The shipped defaults are an 8088's - the machine this simulator is
    ;     calibrated against - and on anything faster they are a first flight
    ;     spent looking at an empty world and wondering where the buildings
    ;     are. This is BEFORE the read on purpose: a file that exists says
    ;     what the player chose and overwrites every one of these, so the
    ;     tier decides only what a machine with no file has ever been told.
    call OSAPI_CPU_INFO
    cmp al, CPU_8086
    jbe .noboost
    xor bx, bx
.boost:
    mov al, [cs_set_best + bx]
    push bx
    shl bx, 1
    mov di, [cs_set_at + bx]
    mov [di], al
    pop bx
    inc bx
    cmp bx, CS_SETN
    jb .boost
.noboost:
    mov si, cs_set_file
    mov bx, cs_setbuf
    mov cx, CS_SETFSZ
    xor dx, dx
    call od_read                    ; ...and we stand where we started again,
    jc .done                        ; whatever the read answered
    or dx, dx
    jnz .done
    cmp ax, CS_SETFSZ
    jne .done
    mov si, cs_setbuf
    mov di, cs_set_magic
    mov cx, 4
.mag:
    mov al, [si]
    cmp al, [di]
    jne .done
    inc si
    inc di
    loop .mag
    xor bx, bx                      ; SI is the fifth byte of the buffer
.each:
    mov al, [si]
    cmp al, [cs_set_max + bx]       ; ...clamped rather than refused
    jbe .ok
    mov al, [cs_set_max + bx]
.ok:
    push bx
    shl bx, 1
    mov di, [cs_set_at + bx]
    mov [di], al
    pop bx
    inc si
    inc bx
    cmp bx, CS_SETN
    jb .each
.done:
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
.out:
    ret

; -----------------------------------------------------------------------------
; cs_set_save - write them back, when the Settings page is left.  UI TASK ONLY,
; which is where every W_ handler runs.
; -----------------------------------------------------------------------------
cs_set_save:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    push ds
    pop es
    ; --- NOTHING CHANGED, NOTHING WRITTEN. The page is left far more often
    ;     than it is used, and a floppy create is several int 13h calls with
    ;     the gfx lock held (SPEC.md 12.8.3) - a second of frozen machine for
    ;     a file that would come out identical. cs_setbuf holds what was last
    ;     read or written, and the MAGIC being in it is what says so: on a
    ;     first run it is zeros, and five settings that happen to be zero
    ;     would otherwise read as "already saved" and never be.
    mov si, cs_setbuf
    mov di, cs_set_magic
    mov cx, 4
.same:
    mov al, [si]
    cmp al, [di]
    jne .differs
    inc si
    inc di
    loop .same
    xor bx, bx
.sameb:
    push bx
    shl bx, 1
    mov di, [cs_set_at + bx]
    pop bx
    mov al, [di]
    cmp al, [si]
    jne .differs
    inc si
    inc bx
    cmp bx, CS_SETN
    jb .sameb
    jmp .gone                       ; byte for byte what is on the disk
.differs:
    mov si, cs_set_magic
    mov di, cs_setbuf
    mov cx, 4
.mag:
    mov al, [si]
    mov [di], al
    inc si
    inc di
    loop .mag
    xor bx, bx
.each:
    push bx
    shl bx, 1
    mov si, [cs_set_at + bx]
    pop bx
    mov al, [si]
    mov [di], al
    inc di
    inc bx
    cmp bx, CS_SETN
    jb .each
    mov si, cs_set_file
    mov bx, cs_setbuf
    mov cx, CS_SETFSZ
    mov di, cs_set_ip
    call od_write                   ; one sector, after the session's first
.gone:
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret
