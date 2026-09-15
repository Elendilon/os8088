; =============================================================================
; tests/fcpapi/fcpapi.asm - OSAPI_FILE_COPY and OSAPI_FILE_MOVE, the published
; file-manager engine (SPEC.md 22.24, 22.25)
;
; Not shipped software: a gate in tests/filetest's sense, answering pass/fail
; against a capability. It rides its own scratch image:
;
;   make fcpapi && python3 tests/fcpapi.py
;
; EVERY ANSWER IS A FILE, and that is the point. A copy engine that goes wrong
; stands clusters up, cross-links two chains or writes a directory entry
; pointing at nothing, and all three look perfectly fine from inside the guest
; - the listing is drawn from the same structures that are wrong. So this
; package writes what it found into RESULT.TXT and stops, and the host walks
; the volume afterwards with an independent FAT12 reader: the COPIES it checks
; are files, and so is the verdict.
;
; What it proves:
;   1  a plain copy, same folder, NEW NAME - which is the arm Paste never
;      took, fcp_fname having been both ends until 22.24
;   2  the bytes arrived: the copy is compared with the source, not just
;      counted
;   3  WHERE WE WERE STANDING is unchanged afterwards. fcp_goto moves the
;      current directory and a package that called a copy and then found
;      itself in another folder would read the wrong disk with no way to know
;   4  a source that does not exist is REFUSED, and with FERR_NOENT rather
;      than a carry and a stale AX
;   5  ...and no destination was created for it (fcp_undo), which is the half
;      a hand-rolled copy gets wrong
;   6  a MOVE into a subfolder of the same volume is taken
;   7  ...and the file is no longer in the folder it came from - which also
;      says the move put us back where we were standing, since that read
;      resolves wherever the machine now is
;   8  a move ACROSS VOLUMES answers AX = 0 and not a FERR_*, because "not
;      attempted" is the one answer a caller must be able to tell from a
;      failure: it is what says to copy and delete instead
;   9  ...and left the source exactly where it was
;
; THE CLAIM CHECK 6 IS REALLY MAKING IS THE HOST'S, not this package's. A move
; that silently copied would pass every row here; what proves the re-link is
; that the file's FIRST CLUSTER is the same number before and after, and only
; something reading both images can see that.
; =============================================================================

%include "os88api.inc"

    OS88_HEADER 'FCPAPI', fa_entry, 0

FA_NCHK     equ 9

fa_entry:
    push si
    push di
    push es

    ; THE WINDOW FIRST, and that is not cosmetic: OSAPI_FILE_HERE, _COPY and
    ; _READ all answer for the CALLING INSTANCE (SPEC.md 19.2.1), and before
    ; WM_CREATE there is no instance for them to answer for. Done the other
    ; way round this package launched, opened its window, and wrote nothing
    ; at all.
    mov si, fa_tpl
    call OSAPI_WM_CREATE
    jc .out
    mov [fa_win], bx

    mov di, fa_res                  ; every row starts as a FAILURE, so a
    mov cx, FA_NCHK                 ; check that never runs cannot read as one
    mov al, '-'                     ; that passed
    push ds
    pop es
    cld
    rep stosb
    mov byte [fa_res+FA_NCHK], 13
    mov byte [fa_res+FA_NCHK+1], 10

    call OSAPI_FILE_HERE            ; DX = our folder, BL = our drive
    mov [fa_clus], dx
    mov [fa_drv], bl
    call OSAPI_FILE_GOTO            ; ...AND STAND THERE. HERE answers where
                                    ; the instance belongs; until a GOTO the
                                    ; machine may be standing somewhere else
                                    ; entirely, and every name below resolves
                                    ; against wherever that is

    call fa_say                     ; a CANARY: the verdict file as it stands
                                    ; before a single check has run, so "the
                                    ; package wrote nothing" and "the package
                                    ; died half way" are different findings

    ; --- 1. a plain copy under a NEW name --------------------------------
    mov bl, [fa_drv]                ; RELOADED, not carried: fa_say above
    mov bh, bl                      ; spends BX, CX, DX and SI, and a copy
    mov dx, [fa_clus]               ; handed the leftovers names a folder on a
    mov cx, dx                      ; drive that does not exist
    mov si, fa_src
    mov di, fa_dst
    push ds
    pop es
    call OSAPI_FILE_COPY
    jnc .c1ok
    call fa_hex                     ; ...and WHICH FERR, as a digit: "it was
    mov [fa_res+0], al              ; refused" is not a finding
    jmp short .c1done
.c1ok:
    mov byte [fa_res+0], 'P'
.c1done:

    ; --- 2. ...and the bytes arrived -------------------------------------
    mov si, fa_dst
    mov di, fa_buf
    push ds
    pop es
    mov bx, fa_buf
    mov cx, FA_BUFSZ
    xor dx, dx
    call OSAPI_FILE_READ            ; DX:AX = bytes read
    jc .c2done
    cmp ax, FA_SRCLEN
    jne .c2done
    mov si, fa_buf
    mov di, fa_want
    mov cx, FA_SRCLEN
    push ds
    pop es
    cld
    repe cmpsb
    jne .c2done
    mov byte [fa_res+1], 'P'
.c2done:

    ; --- 3. where we were standing ---------------------------------------
    call OSAPI_FILE_HERE
    cmp dx, [fa_clus]
    jne .c3done
    cmp bl, [fa_drv]
    jne .c3done
    mov byte [fa_res+2], 'P'
.c3done:

    ; --- 4. a source that is not there ------------------------------------
    mov bl, [fa_drv]
    mov bh, bl
    mov dx, [fa_clus]
    mov cx, dx
    mov si, fa_none
    mov di, fa_ndst
    push ds
    pop es
    call OSAPI_FILE_COPY
    jnc .c4done                     ; it must REFUSE, and with the right code
    cmp ax, FERR_NOENT
    jne .c4done
    mov byte [fa_res+3], 'P'
.c4done:

    ; --- 5b. the subfolder's cluster --------------------------------------
    ; Hoisted above check 5 for one reason: OSAPI_FILE_FIND is the only way a
    ; package learns a cluster, and doing the walk here keeps checks 6 to 9
    ; reading as four uses of the slot rather than a walk and three.
    ; The disk has exactly ONE folder, so the first entry whose type is
    ; OSAPI_FT_DIR is it - a name compare would only be a second way to get
    ; the same answer wrong.
    mov word [fa_sub], 0            ; explicitly, not on the loader's word:
    xor cx, cx                      ; check 6 reads this to decide whether
.fsub:                              ; there was a folder at all
    mov di, fa_fnd
    push ds
    pop es
    call OSAPI_FILE_FIND            ; out CX = the NEXT ordinal, so the loop
    jc .fsubend                     ; needs nothing of its own
    cmp word [fa_fnd+14], OSAPI_FT_DIR
    jne .fsub
    mov ax, [fa_fnd+16]
    mov [fa_sub], ax
.fsubend:

    ; --- 5. ...and left nothing behind ------------------------------------
    ; Check 4's destination must not exist. OSAPI_FILE_READ refusing it is the
    ; question asked the cheapest way there is.
    mov si, fa_ndst
    mov bx, fa_buf
    mov cx, FA_BUFSZ
    xor dx, dx
    push ds
    pop es
    call OSAPI_FILE_READ
    jc .c5ok
    jmp short .c5done
.c5ok:
    mov byte [fa_res+4], 'P'
.c5done:

    ; --- 6. a MOVE into that folder ---------------------------------------
    cmp word [fa_sub], 0            ; no folder found = nothing to move into,
    je .c6done                      ; and the row stays '-' rather than
                                    ; passing on a move to the root
    mov bl, [fa_drv]
    mov bh, bl                      ; ONE volume, which is the whole precondition
    mov dx, [fa_clus]
    mov cx, [fa_sub]
    mov si, fa_mv
    push ds
    pop es
    call OSAPI_FILE_MOVE
    jnc .c6ok
    call fa_hex                     ; and WHICH answer: a 0 here is "not
    mov [fa_res+5], al              ; attempted" and any other digit a FERR_*
    jmp short .c6done
.c6ok:
    mov byte [fa_res+5], 'P'
.c6done:

    ; --- 7. ...and it has left the folder it was in -----------------------
    ; This also says the move put us BACK where we were standing: the name
    ; below resolves against wherever the machine is now, so if fcp_goto had
    ; not run we would be reading the subfolder and would find the file.
    mov si, fa_mv
    mov bx, fa_buf
    mov cx, FA_BUFSZ
    xor dx, dx
    push ds
    pop es
    call OSAPI_FILE_READ
    jc .c7ok                        ; gone, which is what a move means
    jmp short .c7done
.c7ok:
    mov byte [fa_res+6], 'P'
.c7done:

    ; --- 8. a move ACROSS VOLUMES is NOT ATTEMPTED ------------------------
    ; AX = 0 with CF, and neither a FERR_* nor a CF=0. A code would read as
    ; "it failed" to a caller that should fall back and copy; a CF=0 would
    ; read as "it moved" to one that is about to delete the source.
    mov bl, [fa_drv]
    mov bh, bl
    xor bh, 1                       ; the OTHER drive, whichever we booted on
    mov dx, [fa_clus]               ; - and the XOR is on the drive NUMBER,
    xor cx, cx                      ; which is the trap tests/dostrap/renref
    mov si, fa_src                  ; paid for by XORing a letter
    push ds
    pop es
    call OSAPI_FILE_MOVE
    jnc .c8done                     ; it moved?! across two FATs
    or ax, ax
    jnz .c8done                     ; a FERR_*: refused, but not declinably
    mov byte [fa_res+7], 'P'
.c8done:

    ; --- 9. ...and left the source exactly where it was -------------------
    mov si, fa_src
    mov bx, fa_buf
    mov cx, FA_BUFSZ
    xor dx, dx
    push ds
    pop es
    call OSAPI_FILE_READ
    jc .c9done
    cmp ax, FA_SRCLEN
    jne .c9done
    mov byte [fa_res+8], 'P'
.c9done:

    call fa_say                     ; ...and the verdict itself, over it

    mov bx, [fa_win]                ; the loader wants the window back in BX,
    clc                             ; and every call above has spent it
.out:
    pop es
    pop di
    pop si
    ret

; fa_hex - AL (0..15) as one printable digit.  clobbers: AL, flags
fa_hex:
    and al, 0x0F
    add al, '0'
    cmp al, '9'
    jbe .o
    add al, 7
.o:
    ret

; fa_say - publish the result row as RESULT.TXT.  clobbers: AX, BX, CX, DX, SI
fa_say:
    push es
    push ds
    pop es
    mov si, fa_rname
    mov bx, fa_res
    mov cx, FA_NCHK + 2
    xor dx, dx
    call OSAPI_FILE_WRITE
    pop es
    ret

FA_SRCLEN   equ 11
FA_BUFSZ    equ 64

fa_src:     db 'SRC.DAT', 0
fa_dst:     db 'COPY1.DAT', 0
fa_none:    db 'NOSUCH.DAT', 0
fa_mv:      db 'MOVE.DAT', 0
fa_ndst:    db 'NEVER.DAT', 0
fa_rname:   db 'RESULT.TXT', 0
fa_tpl:     dw 90, 90, 220, 60
            dw fa_ttl, 0, 0, 0
fa_ttl:     db 'Copy API', 0
fa_want:    db 'os8088 copy'

FA_B_WIN    equ 0
FA_B_CLUS   equ 2
FA_B_DRV    equ 4
FA_B_RES    equ 6
FA_B_SUB    equ FA_B_RES + FA_NCHK + 2
FA_B_FND    equ FA_B_SUB + 2
FA_B_BUF    equ FA_B_FND + OSAPI_FIND_SZ
FA_BSS      equ FA_B_BUF + FA_BUFSZ

    OS88_BSS FA_BSS
    OS88_IMAGE_END

fa_win      equ os88_image_end + FA_B_WIN
fa_clus     equ os88_image_end + FA_B_CLUS
fa_drv      equ os88_image_end + FA_B_DRV
fa_res      equ os88_image_end + FA_B_RES
fa_sub      equ os88_image_end + FA_B_SUB
fa_fnd      equ os88_image_end + FA_B_FND
fa_buf      equ os88_image_end + FA_B_BUF
