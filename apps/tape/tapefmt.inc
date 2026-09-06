; =============================================================================
; os8088 - apps/tape/tapefmt.inc - the tape format, and the 29 checks
;
; SPEC.md 88.4 is the contract and `tools/os88tape.py` is the second
; implementation of it: that file is the HOST reference codec, written from
; the contract rather than from this assembly, and what it buys is that the
; bytes can be checked BYTE FOR BYTE instead of by eye. It matters more here
; than anywhere else in the tree, because no instrument in this project can
; execute a cassette read at all (SPEC.md 88.11) - so the format is settled by
; two independent readers agreeing, or it is not settled.
;
; **EVERY BYTE OFF A TAPE IS HOSTILE, AND WORSE THAN A DISK'S IN THREE WAYS**
; (SPEC.md 88.9): nobody but us has ever written one, there is no mount to
; validate it, and a mis-synced read delivers somebody else's data with a
; VALID CRC. The 29 checks are the contract; each has a numbered comment here
; naming its row in 88.9, so deleting one is visible in a diff.
;
; WHAT IS IN HERE:
;   tp_crc16      CRC-16/CCITT, bit-serial - the BIOS's own algorithm, and
;                 `ckfile`'s
;   tp_geom       nrec and lastblk, DERIVED - the reader recomputes both from
;                 the header alone and refuses a tape that disagrees with its
;                 own arithmetic (rows 6 and 7)
;   tp_hdr_lay    lay the 256-byte header record
;   tp_body_lay   lay body record N
;   tp_hdr_parse  rows 1-11, and derive the geometry
;   tp_body_parse rows 12-18, and copy the payload in
;   tp_pay_check  rows 19-21 and 29, over the assembled payload, BEFORE a byte
;                 reaches the disk
;
; A 256-ENTRY CRC TABLE IS REFUSED (SPEC.md 88.4.2): 512 bytes of a package to
; save 0.7 s of a 309-second transfer.
; =============================================================================

; --- the record layout (SPEC.md 88.4.1, 88.4.2) ------------------------------
TP_BLOCK      equ 256           ; the BIOS's data block, and its CRC unit
TP_HDR_M0     equ 0x384F        ; 'O8' - os8088's own family word (SPEC.md 20.2)
TP_HDR_M1     equ 0x5054        ; 'TP' - and four bytes, not two: this reader
                                ; is handed hundreds of blocks over a tape's
                                ; life and 16 bits of magic is one false header
                                ; in 65,536
TP_BODY_MAG   equ 0x544F        ; 'OT' - DELIBERATELY a different word from the
                                ; header's first, so neither kind can be parsed
                                ; as the other
TP_VER        equ 1
TP_KIND_FILE  equ 0
TP_MAXFILE    equ 32768         ; the format's payload bound
TP_RECBLK     equ 4             ; 256-byte blocks per FULL body record
TP_BODY_PRE   equ 8             ; 'OT', seq, nrec, paylen, ckfile

TP_F_CZ       equ 0x01          ; the payload is a 'CZ' container THIS writer made
TP_F_PRECOMP  equ 0x02          ; the payload was already compressed on disk
TP_F_LZB      equ 0x04          ; when bit 0: 0 = LZ4, 1 = LZB
TP_F_KNOWN    equ TP_F_CZ | TP_F_PRECOMP | TP_F_LZB

; the header record's fields
TPH_MAGIC     equ 0
TPH_VER       equ 4
TPH_KIND      equ 5
TPH_FLAGS     equ 6
TPH_RECBLK    equ 7
TPH_LASTBLK   equ 8
TPH_NREC      equ 9
TPH_CKFILE    equ 10
TPH_NAME      equ 12
TPH_NAMELEN   equ 16            ; SIXTEEN and not twelve: a maximal 8.3 name is
                                ; TWELVE characters ('ABCDEFGH.IJK') and needs
                                ; a thirteenth byte for the NUL, so a 12-byte
                                ; field cannot hold one and would refuse
                                ; TAPEDATA.TXT. Sixteen keeps TPH_SIZE word-
                                ; aligned and costs nothing - the header is
                                ; padded to 256 either way (SPEC.md 88.4.1)
TPH_SIZE      equ 28
TPH_USIZE     equ 32

; the body record's
TPB_MAGIC     equ 0
TPB_SEQ       equ 2
TPB_NREC      equ 3
TPB_PAYLEN    equ 4
TPB_CKFILE    equ 6

; the 'CZ' container (SPEC.md 20.14) - checked, never decoded (row 20)
TP_CZ_MAG     equ 0x5A43
TP_CZ_HDR     equ 8
TP_LZ_MAX     equ 1             ; the highest format byte any decoder in this
                                ; kernel has - and dskw_czstamp's own test

; --- refusal codes: one per SENTENCE, and tp_emsg is the table ---------------
TPE_OK        equ 0
TPE_MAGIC     equ 1             ; row 1
TPE_VER       equ 2             ; row 2
TPE_KIND      equ 3             ; row 3
TPE_FLAGS     equ 4             ; row 4
TPE_RECBLK    equ 5             ; row 5
TPE_NREC      equ 6             ; row 6
TPE_LASTBLK   equ 7             ; row 7
TPE_NAME      equ 8             ; row 8
TPE_SIZE      equ 9             ; row 9
TPE_BMAGIC    equ 10            ; row 12
TPE_SEQ       equ 11            ; row 13
TPE_BNREC     equ 12            ; row 14
TPE_BCK       equ 13            ; row 15
TPE_PAYLEN    equ 14            ; row 16
TPE_OVER      equ 15            ; row 17
TPE_SHORT     equ 16            ; row 18
TPE_CKFILE    equ 17            ; row 19
TPE_CZ        equ 18            ; rows 20 and 29
TPE_BASIC     equ 19            ; an IBM Cassette BASIC record (SPEC.md 88.4.3)

; -----------------------------------------------------------------------------
; tp_crc16 - CRC-16/CCITT, MSB-first, bit-serial (SPEC.md 88.4)
; in:  ES:SI = the bytes, CX = how many (0 is legal), DX = the running register
;      (TP_CRC_PRE to start)
; out: DX = the register; every other register preserved
;
; ONE algorithm, two uses, and the difference is only what happens at the end:
; the BIOS transmits it one's-complemented high byte first and a reader lands
; on residue 0x1D0F, while `ckfile` is the same register over the payload, NOT
; complemented. The block half is the ROM's and never ours - `int 15h` lays
; the two CRC bytes down itself - so this file only ever wants the second.
;
; Bit-serial on purpose (SPEC.md 88.4.2): ~100 clocks a byte is 0.7 s over
; 32 KB against a 309-second transfer, and a 256-entry table would spend 512
; bytes of a package to save half a second of a five-minute wait.
; -----------------------------------------------------------------------------
TP_CRC_PRE  equ 0xFFFF
TP_CRC_POLY equ 0x1021

tp_crc16:
    push ax
    push bx
    push cx
    push si
    jcxz .done
.byte:
    mov al, [es:si]
    inc si
    xor dh, al                  ; crc ^= byte << 8
    mov bx, 8
.bit:
    shl dx, 1                   ; CF = the bit that left bit 15
    jnc .nopoly
    xor dx, TP_CRC_POLY
.nopoly:
    dec bx
    jnz .bit
    loop .byte
.done:
    pop si
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tp_crcpay - the whole staged payload's CRC
; in:  [tp_pseg] = the payload claim, [tp_size] = its length (<= TP_MAXFILE)
; out: DX = ckfile; every other register preserved
;
; The payload is one claim at offset 0 and at most 32,768 bytes, so this never
; crosses a segment and needs no chunking.
; -----------------------------------------------------------------------------
tp_crcpay:
    push cx
    push si
    push es
    mov es, [tp_pseg]
    xor si, si
    mov cx, [tp_size]
    mov dx, TP_CRC_PRE
    call tp_crc16
    pop es
    pop si
    pop cx
    ret


; -----------------------------------------------------------------------------
; tp_geom - nrec and lastblk, DERIVED (SPEC.md 88.4.2)
; in:  AX = the payload size (1..TP_MAXFILE), BL = recblk (1..16)
; out: CF=0 and CH = nrec, CL = lastblk, DX = cap (recblk*256 - 8)
;      CF=1 the file needs more than 255 body records; CX and DX are then junk
;      AX, BX, SI, DI, BP, DS and ES preserved
;
; BOTH ARE COMPUTED AND NEITHER IS CHOSEN. The reader recomputes them from the
; header alone and compares (rows 6 and 7), so a tape that lies about its own
; shape cannot send the reader hunting for records that do not exist - which
; is minutes of frozen machine per phantom record.
;
; The arithmetic is 16-bit throughout and that is not luck: size <= 32,768 and
; cap <= 4,088, so `size + cap - 1` is at most 36,855 and `(nrec-1) * cap` is
; less than size by construction.
; -----------------------------------------------------------------------------
tp_geom:
    push ax
    push bx
    mov bh, bl
    mov bl, 0                   ; BX = recblk * 256
    sub bx, TP_BODY_PRE         ; BX = cap, a full record's payload
    mov dx, ax                  ; bank the size
    add ax, bx
    dec ax                      ; AX = size + cap - 1
    push dx
    xor dx, dx
    div bx                      ; AX = ceil(size / cap) = nrec
    pop dx
    cmp ax, 255
    ja .toomany
    mov ch, al                  ; CH = nrec
    dec ax
    push dx
    mul bx                      ; AX = (nrec-1) * cap; DX is the high half and
    pop dx                      ; is zero by the note above
    sub dx, ax                  ; DX = the last record's payload
    add dx, TP_BODY_PRE + TP_BLOCK - 1
    mov cl, 8
    shr dx, cl                  ; ...in blocks, rounded up (shift by CL: the
    mov cl, dl                  ; 8086 has no shr by an immediate but 1)
    mov dx, bx                  ; DX = cap
    pop bx
    pop ax
    clc
    ret
.toomany:
    pop bx
    pop ax
    stc
    ret

; -----------------------------------------------------------------------------
; tp_blocks - how many 256-byte blocks does body record AL carry?
; in:  AL = seq (1..[tp_nrec])
; out: AX = blocks, CX = that record's CAPACITY in payload bytes
;      every other register preserved
; -----------------------------------------------------------------------------
tp_blocks:
    push dx
    mov ah, [tp_recblk]
    cmp al, [tp_nrec]
    jb .full
    mov ah, [tp_lastblk]        ; the LAST record is short, and lastblk is what
.full:                          ; saves up to 3 blocks = 4.61 s per file over
    mov al, ah                  ; padding the tail
    mov ah, 0                   ; AX = blocks
    mov dx, ax
    mov cl, 8
    shl dx, cl                  ; DX = blocks * 256
    sub dx, TP_BODY_PRE         ; ...minus the preamble
    mov cx, dx                  ; CX = this record's capacity
    pop dx
    ret

; -----------------------------------------------------------------------------
; tp_hdr_lay - lay the 256-byte header record into the record buffer
; in:  the parsed state ([tp_name], [tp_size], [tp_usize], [tp_flags],
;      [tp_recblk], [tp_lastblk], [tp_nrec], [tp_ckfile]); [tp_rseg] = where
; out: nothing; every register preserved
;
; ALL 256 BYTES ARE WRITTEN BY US rather than padded by the ROM (SPEC.md
; 88.4.1). That makes the record deterministic and host-reproducible on both
; ROMs, and it means the pad cannot contain the 32-consecutive-FF run that
; would false-trigger a leader search. The 224 pad bytes are written ZERO and
; NEVER READ (row 11): reading them is how a future writer's field becomes an
; old reader's bug.
; -----------------------------------------------------------------------------
tp_hdr_lay:
    push ax
    push cx
    push si
    push di
    push es
    mov es, [tp_rseg]
    cld
    xor di, di
    xor ax, ax
    mov cx, TP_BLOCK / 2
    rep stosw                   ; ...including the pad
    mov word [es:TPH_MAGIC], TP_HDR_M0
    mov word [es:TPH_MAGIC+2], TP_HDR_M1
    mov byte [es:TPH_VER], TP_VER
    mov byte [es:TPH_KIND], TP_KIND_FILE
    mov al, [tp_flags]
    mov [es:TPH_FLAGS], al
    mov al, [tp_recblk]
    mov [es:TPH_RECBLK], al
    mov al, [tp_lastblk]
    mov [es:TPH_LASTBLK], al
    mov al, [tp_nrec]
    mov [es:TPH_NREC], al
    mov ax, [tp_ckfile]
    mov [es:TPH_CKFILE], ax
    mov ax, [tp_size]
    mov [es:TPH_SIZE], ax       ; the high word stays zero: TP_MAXFILE is
    mov ax, [tp_usize]          ; 32,768 and row 9 has already refused more
    mov [es:TPH_USIZE], ax
    mov si, tp_name             ; TPH_NAMELEN bytes, NUL-terminated inside
    mov di, TPH_NAME
    mov cx, TPH_NAMELEN
    rep movsb
    pop es
    pop di
    pop si
    pop cx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tp_body_lay - lay body record AL into the record buffer
; in:  AL = seq (1..[tp_nrec]); [tp_pseg] = the staged payload, [tp_rseg] = the
;      record buffer
; out: CX = the record's length in BYTES (blocks * 256), which is the CX the
;      transfer wants; every other register preserved
;
; The tail past `paylen` is written ZERO and read as nothing (SPEC.md 88.4.2),
; so the record is whole blocks and no `CX` this package ever issues is
; anything but a multiple of 256 - which is what keeps both ROMs' pad loops
; out of the picture entirely (row 24).
; -----------------------------------------------------------------------------
tp_body_lay:
    push ax
    push bx
    push dx
    push si
    push di
    push ds
    push es
    push ax                     ; bank the seq
    call tp_blocks              ; AX = blocks, CX = this record's capacity
    mov bx, cx                  ; BX = capacity
    mov cl, 8
    shl ax, cl                  ; AX = the record's byte length
    mov [tp_reclen], ax
    mov es, [tp_rseg]
    cld
    xor di, di
    mov cx, ax
    shr cx, 1
    xor ax, ax
    rep stosw                   ; zero the WHOLE record first: the tail is not
    pop ax                      ; the previous record's bytes
    push ax
    ; --- where in the payload does this record start, and how much is left? --
    mov ah, 0
    dec ax                      ; AX = seq - 1
    mul word [tp_cap]           ; AX = the offset of this record's payload
    mov si, ax                  ; (never over 32,768, so DX is zero)
    mov dx, [tp_size]
    sub dx, si                  ; DX = what is left of the file
    cmp dx, bx
    jbe .tail
    mov dx, bx                  ; a FULL record carries exactly `cap`
.tail:
    ; --- the preamble (SPEC.md 88.4.2) --------------------------------------
    mov word [es:TPB_MAGIC], TP_BODY_MAG
    pop ax
    push ax
    mov [es:TPB_SEQ], al
    mov al, [tp_nrec]
    mov [es:TPB_NREC], al       ; repeated, so a body found WITHOUT its header
    mov [es:TPB_PAYLEN], dx     ; still names the file's shape at once
    mov ax, [tp_ckfile]
    mov [es:TPB_CKFILE], ax     ; ...and this is what rejects a record spliced
                                ; in from a DIFFERENT file on ARRIVAL
    ; --- the payload ---------------------------------------------------------
    mov cx, dx
    mov di, TP_BODY_PRE
    mov ax, [tp_pseg]           ; BOTH segments are read out of OUR ds before
    mov bx, [tp_rseg]           ; either is loaded: `mov ds, [x]` followed by
    mov ds, ax                  ; `mov es, [y]` reads y out of the NEW ds
    mov es, bx
    rep movsb
    pop ax                      ; the seq we banked
    pop es
    pop ds
    mov cx, [tp_reclen]
    pop di
    pop si
    pop dx
    pop bx
    pop ax
    ret

; =============================================================================
; READING: every field a tape can lie about (SPEC.md 88.9)
; =============================================================================

; -----------------------------------------------------------------------------
; tp_hdr_parse - rows 1 to 11, over the 256 bytes a classify read delivered
; in:  ES = the classify buffer's segment, the record at offset 0
; out: CF=0 and [tp_flags], [tp_recblk], [tp_lastblk], [tp_nrec], [tp_ckfile],
;      [tp_name], [tp_size], [tp_usize] and [tp_cap] are filled
;      CF=1 and AL = a TPE_* code; nothing is claimed and nothing is written
;      Every register but AX preserved
;
; Row 5's "and 5 x recblk x 256 must fit the claim" and row 9's memory and disk
; halves are the CALLER's - they are questions about this machine rather than
; about the tape, and the caller is the one that knows what it asked the heap
; for. Everything that is a question about the BYTES is here.
; -----------------------------------------------------------------------------
tp_hdr_parse:
    push bx
    push cx
    push dx
    push si
    push di
    ; --- row 1: the magic, and the ONE foreign record we recognise ----------
    cmp byte [es:0], 0xA5       ; IBM Cassette BASIC's header magic - recognised
    jne .notbasic               ; and NEVER written (SPEC.md 88.4.3). Naming it
    mov al, TPE_BASIC           ; turns "this tape is unreadable" into "this
    jmp .bad                    ; tape has BASIC programs on it and none of
.notbasic:                      ; ours"
    cmp word [es:TPH_MAGIC], TP_HDR_M0
    jne .badmagic
    cmp word [es:TPH_MAGIC+2], TP_HDR_M1
    je .magok
.badmagic:
    mov al, TPE_MAGIC
    jmp .bad
.magok:
    ; --- row 2: the version is EXACT. Refuse, never guess -------------------
    cmp byte [es:TPH_VER], TP_VER
    je .verok
    mov al, TPE_VER
    jmp .bad
.verok:
    ; --- row 3: kind ---------------------------------------------------------
    cmp byte [es:TPH_KIND], TP_KIND_FILE
    je .kindok
    mov al, TPE_KIND
    jmp .bad
.kindok:
    ; --- row 4: bits 3..7 MUST be zero. An unknown format bit refuses BEFORE
    ; a file nothing on the machine can open is created -----------------------
    mov al, [es:TPH_FLAGS]
    test al, ~TP_F_KNOWN & 0xFF
    jz .flagok
    mov al, TPE_FLAGS
    jmp .bad
.flagok:
    mov [tp_flags], al
    ; --- row 5: 1 <= recblk <= 16 -------------------------------------------
    mov al, [es:TPH_RECBLK]
    or al, al
    jz .badrb
    cmp al, 16
    jbe .rbok
.badrb:
    mov al, TPE_RECBLK
    jmp .bad
.rbok:
    mov [tp_recblk], al
    ; --- row 9: size. 1..TP_MAXFILE, and the HIGH WORD must be zero ---------
    cmp word [es:TPH_SIZE+2], 0
    jne .badsize
    mov ax, [es:TPH_SIZE]
    or ax, ax
    jz .badsize
    cmp ax, TP_MAXFILE
    jbe .szok
.badsize:
    mov al, TPE_SIZE
    jmp .bad
.szok:
    mov [tp_size], ax
    ; --- rows 6 and 7: the geometry is DERIVED and COMPARED -----------------
    mov bl, [tp_recblk]
    call tp_geom                ; CH = nrec, CL = lastblk, DX = cap
    jc .badnrec                 ; over 255 records: the size and recblk this
    mov [tp_cap], dx            ; header declares cannot be laid down at all
    mov al, [es:TPH_NREC]
    or al, al
    jz .badnrec
    cmp al, ch
    je .nrecok
.badnrec:
    mov al, TPE_NREC
    jmp .bad
.nrecok:
    mov [tp_nrec], al
    mov al, [es:TPH_LASTBLK]
    or al, al
    jz .badlast
    cmp al, [tp_recblk]
    ja .badlast
    cmp al, cl
    je .lastok
.badlast:
    mov al, TPE_LASTBLK
    jmp .bad
.lastok:
    mov [tp_lastblk], al
    ; --- row 8: a NUL inside 12 bytes, every byte before it 0x21..0x7E ------
    ; dskw_name83 is the SINGLE validator of what the name MEANS (SPEC.md
    ; 88.9 row 8): this is only the character fence, and there is deliberately
    ; NO '_' substitution - substituting on a WRITE silently targets a
    ; different file, which is exactly what SPEC.md 19.1's display path may do
    ; and a write path may not.
    mov si, TPH_NAME
    mov di, tp_name
    mov cx, TPH_NAMELEN
.nchar:
    mov al, [es:si]
    mov [di], al
    or al, al
    jz .nameok
    cmp al, 0x21
    jb .badname
    cmp al, 0x7E
    ja .badname
    inc si
    inc di
    loop .nchar
.badname:                       ; ran out of the field with no NUL, or a byte
    mov al, TPE_NAME            ; outside the printable range
    jmp .bad
.nameok:
    cmp di, tp_name             ; ...and an EMPTY name is not a name
    je .badname
    ; --- row 10: usize is DISPLAY ONLY and may never size anything ----------
    mov ax, [es:TPH_USIZE]
    mov [tp_usize], ax
    ; --- row 11: the 224 pad bytes are NOT READ -----------------------------
    xor ax, ax
    clc
    jmp short .out
.bad:
    mov ah, 0
    stc
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    ret

; -----------------------------------------------------------------------------
; tp_body_parse - rows 12 to 18, then the copy
; in:  ES = the record buffer's segment, the record at offset 0
;      AL = the seq this reader is expecting (1..[tp_nrec])
; out: CF=0 and [tp_total] advanced by this record's paylen, the payload copied
;      into [tp_pseg] at the running offset
;      CF=1 and AL = a TPE_* code; NOTHING is copied
;      Every register but AX preserved
; -----------------------------------------------------------------------------
tp_body_parse:
    push bx
    push cx
    push dx
    push si
    push di
    push ds
    push es
    mov bl, al                  ; BL = the seq we are expecting, held in a
                                ; register for the whole routine rather than
                                ; banked on the stack: every refusal path
                                ; below would otherwise have to unwind it
    ; --- row 12: the two magics differ by construction; test BOTH ways ------
    cmp word [es:TPB_MAGIC], TP_BODY_MAG
    jne .badmag
    cmp word [es:TPH_MAGIC], TP_HDR_M0
    jne .magok
.badmag:
    mov al, TPE_BMAGIC
    jmp .bad
.magok:
    ; --- row 13: seq is EXACT, not "in range". This is also the read side's
    ; guard against a second Tape window (SPEC.md 88.5) ----------------------
    cmp [es:TPB_SEQ], bl
    je .seqok
    mov al, TPE_SEQ
    jmp .bad
.seqok:
    ; --- row 14: nrec repeated, exactly -------------------------------------
    mov al, [tp_nrec]
    cmp [es:TPB_NREC], al
    je .nrok
    mov al, TPE_BNREC
    jmp .bad
.nrok:
    ; --- row 15: ckfile repeated - what rejects a record spliced in from a
    ; DIFFERENT file on ARRIVAL rather than at the end of the file -----------
    mov ax, [tp_ckfile]
    cmp [es:TPB_CKFILE], ax
    je .ckok
    mov al, TPE_BCK
    jmp .bad
.ckok:
    ; --- row 16: 1 <= paylen <= THIS record's capacity ----------------------
    mov al, bl
    call tp_blocks              ; CX = the capacity, from the header's own
    mov dx, [es:TPB_PAYLEN]     ; recblk/lastblk and never from the tape
    or dx, dx
    jz .badlen
    cmp dx, cx
    jbe .lenok
.badlen:
    mov al, TPE_PAYLEN
    jmp .bad
.lenok:
    ; --- row 17: the running total may never EXCEED size, checked BEFORE the
    ; copy that would exceed it ----------------------------------------------
    mov si, [tp_total]
    mov di, si
    add di, dx                  ; DI = what the total WOULD become
    jc .badover                 ; a carry is past 65,535 and so past size
    cmp di, [tp_size]
    jbe .overok
.badover:
    mov al, TPE_OVER
    jmp .bad
.overok:
    ; --- row 18: at seq == nrec the total must EQUAL size, exactly ----------
    cmp bl, [tp_nrec]
    jne .notlast
    cmp di, [tp_size]
    je .notlast
    mov al, TPE_SHORT
    jmp .bad
.notlast:
    ; --- and only now the copy. SI is the running offset in the claim -------
    mov [tp_total], di
    mov cx, dx
    mov di, si
    mov si, TP_BODY_PRE
    mov ax, [tp_rseg]           ; BOTH segments are read out of OUR ds before
    mov bx, [tp_pseg]           ; either is loaded
    mov ds, ax
    mov es, bx
    cld
    rep movsb
    pop es
    pop ds
    xor ax, ax
    clc
    jmp short .out
.bad:
    mov ah, 0
    pop es                      ; DS and ES are still ours on every refusal
    pop ds                      ; path - the copy is the last thing this does
    stc
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    ret

; -----------------------------------------------------------------------------
; tp_ext_img - does [tp_name] name a package or driver IMAGE?
; out: CF=0 yes (.O88 / .DRV / .OVL / .WSM / .WPV), CF=1 no
;      every register preserved
;
; Two callers, one list. SPEC.md 88.7 step 3 uses it to carry those files
; VERBATIM - wrapping one in 'CZ' would make a file `ld_check_hdr` cannot start
; (SPEC.md 22.22.1) - and SPEC.md 88.9 row 21 uses it on the way BACK, as an
; explicit refusal rather than a consequence of row 20.
; -----------------------------------------------------------------------------
tp_ext_img:
    push ax
    push bx
    push cx
    push si
    push di
    mov si, tp_name
    xor di, di                  ; DI = the '.' we last saw, 0 = none
.scan:
    mov al, [si]
    or al, al
    jz .found
    cmp al, '.'
    jne .next
    mov di, si
.next:
    inc si
    jmp short .scan
.found:
    or di, di
    jz .no
    inc di                      ; DI -> the extension
    mov bx, tp_extlist
.try:
    mov al, [bx]
    or al, al
    jz .no
    mov si, di
    mov cx, 3
.chr:
    mov al, [si]
    cmp al, 'a'
    jb .noup
    cmp al, 'z'
    ja .noup
    sub al, 32                  ; the listing's names are upper case already;
.noup:                          ; a typed one need not be
    cmp al, [bx]
    jne .nextext
    inc si
    inc bx
    loop .chr
    cmp byte [si], 0            ; exactly three characters, and then the end
    jne .nextext
    clc
    jmp short .out
.nextext:
    add bx, cx                  ; skip whatever is left of this entry...
    inc bx                      ; ...and its NUL
    jmp short .try
.no:
    stc
.out:
    pop di
    pop si
    pop cx
    pop bx
    pop ax
    ret

tp_extlist:
    db 'O88', 0
    db 'DRV', 0
    db 'OVL', 0
    db 'WSM', 0
    db 'WPV', 0
    db 0

; -----------------------------------------------------------------------------
; tp_pay_check - rows 19, 20, 21 and 29, over the ASSEMBLED payload
; in:  the payload in [tp_pseg], [tp_size], [tp_flags], [tp_name]
; out: CF=0 the bytes may go to the disk; CF=1 and AL = a TPE_* code
;      Every register but AX preserved
;
; This runs AFTER the last record and BEFORE a byte reaches the disk (SPEC.md
; 88.4.2), which is the whole point of staging the file whole: a corrupt tape
; leaves NOTHING behind rather than a half-written file.
; -----------------------------------------------------------------------------
tp_pay_check:
    push bx
    push cx
    push dx
    push si
    push es
    ; --- row 19: the backstop. The block CRC is the ROM's and covers 256
    ; bytes; this covers the FILE, which is what catches mis-assembly --------
    call tp_crcpay              ; DX = the CRC over all `size` bytes
    cmp dx, [tp_ckfile]
    je .ckok
    mov al, TPE_CKFILE
    jmp .bad
.ckok:
    mov es, [tp_pseg]
    ; --- row 29: dskw_czstamp derives the compression hint from the first
    ; eight bytes of EVERY whole-file write, unconditionally. So a payload that
    ; merely BEGINS 43 5A xx 00 with flags bit 0 CLEAR would be written, be
    ; stamped compressed on the volume, and answer FERR_IO on every read after
    ; that. One compare. -----------------------------------------------------
    cmp word [tp_size], TP_CZ_HDR
    jbe .nocz                   ; too short to be a container at all
    cmp word [es:0], TP_CZ_MAG
    jne .nocz
    cmp byte [es:2], TP_LZ_MAX  ; ...czstamp's own test is `<= LZ_LZB`
    ja .nocz
    test byte [tp_flags], TP_F_CZ
    jz .badcz                   ; it looks like a container and does not say so
.nocz:
    test byte [tp_flags], TP_F_CZ
    jz .out                     ; not ours to check any further
    ; --- row 21: a .O88 / .DRV / .OVL is NEVER wrapped, on either leg -------
    call tp_ext_img
    jnc .badcz
    ; --- row 20: the container's own fields. TEN BYTES OF CODE, and it is NOT
    ; DECODED to prove it - the whole-file CRC has already proved the bytes are
    ; bit-identical to what was written ---------------------------------------
    cmp word [tp_size], TP_CZ_HDR
    jbe .badcz
    cmp word [es:0], TP_CZ_MAG
    jne .badcz
    cmp byte [es:2], TP_LZ_MAX
    ja .badcz
    cmp byte [es:3], 0
    jne .badcz
    mov dx, [es:6]              ; the unpacked size, high word
    cmp dx, 0x0100              ; <= 16 MB
    ja .badcz
    jb .lowok
    cmp word [es:4], 0
    jne .badcz
.lowok:
    or dx, dx
    jnz .out                    ; a high word at all is bigger than any size
    mov bx, [tp_size]           ; row 20's floor: >= size - 8
    sub bx, TP_CZ_HDR
    cmp [es:4], bx
    jae .out
.badcz:
    mov al, TPE_CZ
.bad:
    mov ah, 0
    stc
    jmp short .done
.out:
    xor ax, ax
    clc
.done:
    pop es
    pop si
    pop dx
    pop cx
    pop bx
    ret

; =============================================================================
; THE PARSED STATE - one copy, written by the layer that read it
;
; It is DATA in the image rather than bss: a package declares its bss as one
; total with equ offsets (OS88_BSS), and two hundred bytes of image is cheaper
; than the convention. Every field here is either laid down by tp_hdr_lay or
; filled by tp_hdr_parse, so the two directions cannot disagree about what a
; field means.
; =============================================================================
tp_name:    times TPH_NAMELEN + 1 db 0
                                ; the 8.3 display form, NUL-terminated.
                                ; TPH_NAMELEN go on the tape; the extra byte is
                                ; ours, so the same bytes are a C string for
                                ; OSAPI_FILE_*.
                                ; SIZED FROM TPH_NAMELEN AND NOT WRITTEN DOWN
                                ; AGAIN: the parse copies the whole field in
                                ; before it decides the name is malformed, so a
                                ; buffer a byte short of it is a write past the
                                ; end on exactly the hostile input SPEC.md 88.9
                                ; exists to refuse. It was `times 13` while the
                                ; field was 12, and widening one without the
                                ; other is the bug this line now cannot have
tp_size:    dw 0                ; the payload's byte count (the header field is
                                ; 32 bits; row 9 refuses a high word)
tp_usize:   dw 0                ; what it EXPANDS to - INFORMATIONAL ONLY, and
                                ; it may never size a claim or a check (row 10)
tp_ckfile:  dw 0
tp_cap:     dw 0                ; recblk * 256 - 8, derived
tp_total:   dw 0                ; the running payload total on a read
tp_reclen:  dw 0                ; the record tp_body_lay just laid down
tp_flags:   db 0
tp_recblk:  db TP_RECBLK
tp_lastblk: db 0
tp_nrec:    db 0
