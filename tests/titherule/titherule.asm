; =============================================================================
; os8088 - tests/titherule/titherule.asm
;
; TITHE's RULES ENGINE ON THE MACHINE, against tools/duelsim.py (SPEC.md
; 97.11, TITHE-PLAN 14.1): the "the two agree" half of wave 2's gate.
;
; It carries apps/tithe/tirule.inc and the generated card table exactly as the
; package will, and a set of MATCH FILES that `duelsim.py bake` chose so every
; keyword fires at least once (build/tirmatch.bin). tests/titherules.py pokes
; a match's index into [tt_match] and presses a key; the key handler replays
; that match here - setup, the mulligans, and upkeep / both plans / resolve a
; round - writing the engine's STATE RECORD after setup and after every round
; into [tt_log], and bumps [tt_seq]. The test then reads the records out of
; this segment and compares them with the simulator's, to the byte.
;
; NO FILES AND NO WORKER. One match's records are at most 61 x 376 bytes, which
; fits in the segment, and a key handler is the one place a test can start a
; computation and read its end off a counter - the engine is arithmetic, and a
; match is a fraction of a second of an 8088.
;
;   make titherules && python3 tests/titherules.py
; =============================================================================

%include "os88api.inc"

    OS88_HEADER 'TITHERUL', tt_entry

TT_MAXREC   equ 61                  ; setup + TR_ROUNDMAX rounds

tt_entry:
    push si
    mov si, tt_tpl
    call OSAPI_WM_CREATE
    jc .out
    mov [tt_win], bx
    clc
.out:
    pop si
    ret

; -----------------------------------------------------------------------------
; tt_onkey - replay match [tt_match] of the baked set
; -----------------------------------------------------------------------------
tt_onkey:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    call OSAPI_GET_TICKS
    mov [tt_t0], ax
    mov word [tt_nrec], 0
    mov word [tt_bad], 0
    mov si, tt_matches              ; find it: a count, then (length, bytes)
    mov cl, [si]
    inc si
    mov al, [tt_match]
    cmp al, cl
    jae .none
.find:
    or al, al
    jz .have
    add si, [si]
    add si, 2
    dec al
    jmp short .find
.have:
    add si, 2                       ; SI -> the match file
    cmp word [si], 'TM'
    jne .none
    cmp word [si + 2], 'F1'
    jne .none
    add si, 4
    mov bx, tr_decka                ; the two decks: a count, then the ids
    call .deck
    mov bx, tr_deckb
    call .deck
    mov ax, [si]
    mov [tr_decka + 4], ax
    mov ax, [si + 2]
    mov [tr_deckb + 4], ax
    add si, 4
    mov al, [si]                    ; the two mulligans
    mov [tt_mull], al
    mov al, [si + 1]
    mov [tt_mull + 1], al
    add si, 2
    mov cl, [si]                    ; the rounds
    xor ch, ch
    inc si
    call tr_setup
    cmp byte [tt_mull], 0
    je .ma
    xor al, al
    call tr_mulligan
.ma:
    cmp byte [tt_mull + 1], 0
    je .mb
    mov al, 1
    call tr_mulligan
.mb:
    mov di, tt_log
    call .rec
    jcxz .done
.round:
    call tr_upkeep
    xor al, al
    call tr_apply                   ; SI advances past each plan
    mov al, 1
    call tr_apply
    call tr_resolve
    call .rec
    cmp byte [tr_result], 0
    jne .done
    loop .round
.done:
    mov ax, [tr_err]
    mov [tt_bad], ax
    call OSAPI_GET_TICKS
    sub ax, [tt_t0]
    mov [tt_ticks], ax
    jmp short .out
.none:
    mov word [tt_bad], 0FFFFh
.out:
    inc word [tt_seq]
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret
.deck:                              ; SI -> a count and ids -> [BX] = (ptr, n)
    mov al, [si]
    xor ah, ah
    inc si
    mov [bx], si
    mov [bx + 2], ax
    add si, ax
    ret
.rec:                               ; one record at DI, if there is room
    cmp word [tt_nrec], TT_MAXREC
    jae .rx
    call tr_record
    inc word [tt_nrec]
.rx:
    ret

tt_paint:
    ret

tt_tpl:
    dw 120, 120, 300, 60
    dw tt_ttl, tt_paint, tt_onkey, 0
tt_ttl:     db 'TITHE rules', 0

%include "ticards.inc"
%include "tirule.inc"

tt_matches: incbin "tirmatch.bin"

tt_win:     dw 0
tt_match:   db 0                    ; the test writes which match
tt_seq:     dw 0                    ; ...and waits for this to move
tt_nrec:    dw 0
tt_bad:     dw 0                    ; the engine's illegal actions, or 0FFFFh
tt_ticks:   dw 0                    ; system ticks the replay took
tt_t0:      dw 0
tt_mull:    db 0, 0

    OS88_BSS TT_MAXREC * TR_RECSIZE
    OS88_IMAGE_END

tt_log      equ os88_image_end
