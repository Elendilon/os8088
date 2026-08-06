; =============================================================================
; assoc.inc - file type associations (SPEC.md 54)
;
; An extension names a PROGRAM, and the program owns the glyph. Two tables
; rather than one flat row, because BMP and GIF both mean Paint and a flat
; table would cache Paint's glyph twice:
;
;   assoc_stem[i]   8 bytes   the app's 8.3 stem, space-padded ('.O88' implied)
;   assoc_glyph[i]  8 bytes   its icon reduced to 8x8, one byte a row
;   assoc_ext[j]    4 bytes   3 extension bytes + the app index it names
;
; Every stride is a power of two on purpose: an 8086 has no `shl reg, imm`
; past 1, so a shift through CL is far cheaper than the `mul` an odd stride
; would force - and the harvest does this lookup once per listed file.
;
; NO TABLE CARRIES A FLAGS BYTE. "Slot free" is stem[0] / ext[0] == 0 - a
; sanitized display name's bytes are 0x21..0x7E and can never be 0 (SPEC.md
; 19.1) - and "glyph unresolved" is the eight bytes ORing to zero, which is
; exactly the all-zero sentinel fm_draw_icon16 already reads on disk_icons.
;
; ALL OF IT LIVES IN .text, not .bss: -f bin zeroes nothing, so initialised
; data is in the image and is writable at runtime (the ui_tm_cwd / dsk_fatw0 /
; fdlg_win idiom). The build-time defaults ARE the table, and a runtime
; registration writes over a row - one copy of the data, no init code, and
; "take over an existing one" needs no special case.
; =============================================================================

ASSOC_NAPP   equ 12             ; app slots
ASSOC_NEXT   equ 24             ; extension slots
ASSOC_STICKY equ 0x80           ; ext slot bit 7: claimed by a RUNTIME
                                ; registration, so a header declaration
                                ; (SPEC.md 54.5) may not take it back
ASSOC_IX     equ 0x7F           ; ...and the index under it
ASSOC_DECLMAX equ 5             ; extensions one header block can declare
                                ; (SPEC.md 54.6) - the block is 16 bytes: a
                                ; count and five 3-byte extensions

; The document page: the 16x16 body every document icon is built on, and the
; second icon in this kernel that is not harvested off a disk (dsk_folder_ico
; is the other). A dog-eared page with its top-right corner cut, whose white
; interior holds an 8x8 inset at x=4..11, y=5..12 - one pixel clear of the
; border on every side. 16 mask words (the white underlay, so the page reads
; on the desktop dither) then 16 data words, bit 15 = leftmost.
assoc_page:
    dw 0x3FE0, 0x3FF0, 0x3FF8, 0x3FFC, 0x3FFC, 0x3FFC, 0x3FFC, 0x3FFC
    dw 0x3FFC, 0x3FFC, 0x3FFC, 0x3FFC, 0x3FFC, 0x3FFC, 0x3FFC, 0x3FFC
    dw 0x3FE0, 0x2030, 0x2028, 0x203C, 0x2004, 0x2004, 0x2004, 0x2004
    dw 0x2004, 0x2004, 0x2004, 0x2004, 0x2004, 0x2004, 0x2004, 0x3FFC

ASSOC_INSET  equ 32 + 2*5       ; the first inset row's word in the body:
                                ; past the 16 mask words, then data row 5
ASSOC_INSHL  equ 4              ; ...and x=4 is bit 11, so a glyph byte's
                                ; bit 7 lands there with one shift by 4

; --- the app slots: stems, then glyphs -------------------------------------
assoc_stem:
    db 'PAINT   '
    db 'NOTEPAD '
    db 'TRACKER '
    db 'ARTFUL  '
    times (ASSOC_NAPP - 4) * 8 db 0

; The four defaults' glyphs are BAKED AT BUILD TIME by tools/os88mini.py out
; of each package's own .o88, so the kernel ships knowing what its own
; applications look like and a document icon costs no disk read on the first
; boot of any machine. Generated and never hand-pasted: pasted bytes go stale
; in silence when an app's icon changes, and make check-images cannot see
; that - the make dependency can.
assoc_glyph:
%include "associco.inc"
    times (ASSOC_NAPP - 4) * 8 db 0

; --- the extension slots ---------------------------------------------------
assoc_ext:
    db 'BMP', 0                 ; -> PAINT
    db 'GIF', 0                 ; -> PAINT
    db 'TXT', 1                 ; -> NOTEPAD
    db 'MOD', 2                 ; -> TRACKER
    db 'MD ', 3                 ; -> ARTFUL
    times (ASSOC_NEXT - 5) * 4 db 0

; --- per-app side arrays ---------------------------------------------------
; Parallel rather than inside the slot, so the 8-byte strides survive. The
; hint is a place to LOOK and never an answer: a cluster means nothing on a
; disk that has been swapped, so the open path re-checks the name on arrival.
assoc_clus:  times ASSOC_NAPP dw 0     ; the directory it was last SEEN in
assoc_drv:   times ASSOC_NAPP db 0xFF  ; ...on which volume (0xFF = never seen)
assoc_dfold: db 1, 1, 1, 1             ; build-time folder: 0 root, 1 APPS,
             times ASSOC_NAPP - 4 db 0 ; 2 GAMES. The one part of a default
                                       ; that cannot be a cluster, because no
                                       ; cluster is knowable at build time

; -----------------------------------------------------------------------------
; assoc_ext_of - the extension of a staged display name (SPEC.md 54.2)
; in:  SI -> a NUL-padded 16-byte display name (the SPEC.md 19.1 staged shape)
; out: CF=0 and DI -> 3 space-padded extension bytes in assoc_extb;
;      CF=1 = the name carries no extension
; clobbers: DI (the output), CF
;
; Uppercase-exact throughout, matching SPEC.md 19.1's own "O88" rule and for
; the same reason: foreign OSes uppercase short names on write, and a name
; that reaches here has already been sanitized to 0x21..0x7E.
; -----------------------------------------------------------------------------
assoc_ext_of:
    push ax
    push cx
    push dx
    push si
    mov di, assoc_extb
    mov byte [di], ' '          ; a short extension pads itself, so a two-
    mov byte [di+1], ' '        ; letter 'MD' matches a declared 'MD '
    mov byte [di+2], ' '
    xor ax, ax                  ; AX = the byte after the dot, 0 = none seen
    mov cx, 16
.scan:
    mov dl, [si]                ; DL, never AH: AX is holding the offset of
    or dl, dl                   ; the dot and a byte load into AH would eat
    jz .dot                     ; its high half on the very next pass
    cmp dl, '.'
    jne .next
    mov ax, si
    inc ax
.next:
    inc si
    loop .scan
.dot:
    or ax, ax
    jz .none
    mov si, ax
    mov cx, 3
.copy:
    mov al, [si]
    or al, al
    jz .done
    mov [di], al
    inc si
    inc di
    loop .copy
.done:
    mov di, assoc_extb
    pop si
    pop dx
    pop cx
    pop ax
    clc
    ret
.none:
    pop si
    pop dx
    pop cx
    pop ax
    stc
    ret

; -----------------------------------------------------------------------------
; assoc_stem_of - the 8.3 STEM of a staged display name (SPEC.md 54.2)
; in:  SI -> the NUL-padded display name
; out: DI -> 8 space-padded bytes in assoc_stemb (always succeeds)
; clobbers: DI (the output), flags
; -----------------------------------------------------------------------------
assoc_stem_of:
    push ax
    push cx
    push si
    push di
    mov di, assoc_stemb
    mov cx, 8
.pad:
    mov byte [di], ' '
    inc di
    loop .pad
    mov di, assoc_stemb
    mov cx, 8
.copy:
    mov al, [si]
    or al, al
    jz .done
    cmp al, '.'
    je .done
    mov [di], al
    inc si
    inc di
    loop .copy
.done:
    pop di
    pop si
    pop cx
    pop ax
    mov di, assoc_stemb
    ret

; -----------------------------------------------------------------------------
; assoc_find - the app an extension names (SPEC.md 54.2)
; in:  SI -> 3 extension bytes
; out: CF=0 and AL = app slot index; CF=1 = no association
; clobbers: AX (output), CF
; -----------------------------------------------------------------------------
assoc_find:
    push bx
    push cx
    push di
    mov bx, assoc_ext
    mov cx, ASSOC_NEXT
.row:
    cmp byte [bx], 0
    je .next                    ; a free slot never matches
    mov di, si
    mov al, [bx]
    cmp al, [di]
    jne .next
    mov al, [bx+1]
    cmp al, [di+1]
    jne .next
    mov al, [bx+2]
    cmp al, [di+2]
    je .hit
.next:
    add bx, 4
    loop .row
.miss:
    pop di
    pop cx
    pop bx
    stc
    ret
.hit:
    mov al, [bx+3]
    and al, ASSOC_IX
    cmp al, ASSOC_NAPP
    jae .miss                   ; a corrupt index names no app
    pop di
    pop cx
    pop bx
    clc
    ret

; -----------------------------------------------------------------------------
; assoc_app_of - the app slot a stem names
; in:  SI -> 8 stem bytes
; out: CF=0 and AL = slot index; CF=1 = this stem is in no slot
; clobbers: AX (output), CF
; -----------------------------------------------------------------------------
assoc_app_of:
    push bx
    push cx
    push dx
    push si
    push di
    mov bx, assoc_stem
    xor dh, dh
.row:
    cmp dh, ASSOC_NAPP
    jae .miss
    cmp byte [bx], 0
    je .next                    ; a free slot never matches
    mov di, bx
    mov cx, 8
    push si
.cmp:
    mov al, [si]
    cmp al, [di]
    jne .nomatch
    inc si
    inc di
    loop .cmp
    pop si
    mov al, dh                  ; all eight matched
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    clc
    ret
.nomatch:
    pop si
.next:
    add bx, 8
    inc dh
    jmp .row
.miss:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    stc
    ret

; -----------------------------------------------------------------------------
; assoc_reduce - a 16x16 icon's DATA plane -> the 8x8 glyph (SPEC.md 54.3)
; in:  ES:SI -> 16 data words (bit 15 = leftmost), DI -> 8 bytes in the
;      kernel segment
; out: nothing (all registers preserved)
;
; MAJORITY of each 2x2 block: it lights if two or more of its four source
; pixels are ink. OR-of-4 turns a typical 40%-ink icon into a near-solid blob
; and point-sampling drops every one-pixel stroke; majority is the one that
; keeps a silhouette at 8x8 on a 1bpp adapter. Byte-identical to reduce8() in
; tools/os88mini.py, which bakes the shipped glyphs - the two MUST agree, or a
; default and a harvested icon for the same program would not match.
;
; ES rather than DS because the source is usually LOW_SEG (the harvest's
; sector buffer), which SPEC.md 2.1 forbids reaching through DS.
; -----------------------------------------------------------------------------
assoc_reduce:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov ch, 8                   ; output rows left
.row:
    mov ax, [es:si]             ; the two source rows this one reduces
    mov dx, [es:si+2]
    xor bl, bl                  ; the output byte, built MSB first
    mov cl, 8                   ; output columns left
.col:
    shl bl, 1
    xor bh, bh                  ; how many of the four are ink
    shl ax, 1
    adc bh, 0
    shl ax, 1
    adc bh, 0
    shl dx, 1
    adc bh, 0
    shl dx, 1
    adc bh, 0
    cmp bh, 2
    jb .dark
    or bl, 1
.dark:
    dec cl
    jnz .col
    mov [di], bl
    inc di
    add si, 4                   ; two source rows per output row
    dec ch
    jnz .row
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; assoc_compose - a document icon for one app slot (SPEC.md 54.3)
; in:  AL = app slot index, DI -> 64 bytes in the kernel segment
; out: the composed 16x16 body (icon_draw16's layout)
; clobbers: nothing (all registers preserved)
;
; The page frame, then the app's glyph OR'd into the interior the frame has
; already cleared to white. An UNRESOLVED glyph is eight zero bytes and
; composes to the bare page, which is a correct document icon and not a
; placeholder - the SPEC.md 50 degradation rule, applied to an icon.
; -----------------------------------------------------------------------------
assoc_compose:
    push ax
    push bx
    push cx
    push si
    push di
    push es
    push ds
    pop es                      ; ES = DS = KERNEL_SEG for the frame copy
    mov bl, al
    xor bh, bh
    mov cl, 3
    shl bx, cl                  ; slot * 8
    push di
    mov si, assoc_page
    mov cx, 32
    cld
    rep movsw
    pop di
    mov si, assoc_glyph
    add si, bx
    add di, ASSOC_INSET
    mov cx, 8
.inset:
    mov al, [si]
    xor ah, ah
    push cx
    mov cl, ASSOC_INSHL
    shl ax, cl
    pop cx
    or [di], ax
    inc si
    inc di
    inc di
    loop .inset
    pop es
    pop di
    pop si
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; assoc_docicon - compose a document icon for one directory entry
; in:  SI -> a staged 32-byte entry (SPEC.md 19.1)
; out: CF=0 and dsk_ico holds the 64-byte body; CF=1 = no association
; clobbers: CF (everything else preserved)
;
; dsk_ico is dsk_get_icon's staging buffer, borrowed here to save 64 bytes of
; footprint. Safe because nothing calls dsk_get_icon during a mount, which is
; the only place this runs - state the invariant if either ever moves.
; -----------------------------------------------------------------------------
assoc_docicon:
    push ax
    push si
    push di
    call assoc_ext_of           ; DI -> assoc_extb
    jc .no
    mov si, di
    call assoc_find             ; AL = the app slot
    jc .no
    mov di, dsk_ico
    call assoc_compose
    pop di
    pop si
    pop ax
    clc
    ret
.no:
    pop di
    pop si
    pop ax
    stc
    ret

; -----------------------------------------------------------------------------
; assoc_declare - take the extensions a package's header declares (SPEC.md 54.6)
; in:  AL = its app slot; ES = LOW_SEG with dsk_secbuf holding its first
;      sector, header validated as a v3 .o88 whose flags bit 1 is set
; out: nothing (all registers preserved)
;
; The block is a count byte and up to five 3-byte extensions, and the harvest
; ALREADY READ this sector - so a folder holding a program and its documents
; teaches the OS the extension, the glyph and the location in one existing
; read. The program still has to be SEEN; it no longer has to be run.
;
; A declaration may NOT take an extension a runtime registration claimed
; (ASSOC_STICKY). It arrives on every mount of the folder, so without that
; guard it would silently undo the user's own choice every time they browsed.
; -----------------------------------------------------------------------------
assoc_declare:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov dl, al                  ; DL = the app slot
    mov si, dsk_secbuf + 32     ; the block: after the header, and after the
    test byte [assoc_hflags], 1 ; icon when there is one
    jz .based
    add si, 64
.based:
    mov cl, [es:si]             ; the count
    cmp cl, ASSOC_DECLMAX
    ja .out                     ; a corrupt count declares nothing
    or cl, cl
    jz .out
    xor ch, ch
    inc si
.one:
    push cx
    mov di, assoc_extb          ; stage it: everything below reads through DS
    mov al, [es:si]
    mov [di], al
    mov al, [es:si+1]
    mov [di+1], al
    mov al, [es:si+2]
    mov [di+2], al
    add si, 3
    push si
    mov si, assoc_extb
    cmp byte [si], ' '          ; a blank extension names nothing
    jbe .next
    call assoc_find             ; already claimed?
    jc .fresh
    call assoc_ext_row          ; BX = that row
    test byte [bx+3], ASSOC_STICKY
    jnz .next                   ; a runtime claim outranks a declaration
    jmp short .point
.fresh:
    call assoc_ext_new
    jc .next                    ; the table is full: the rest are dropped
.point:
    mov [bx+3], dl              ; ...pointed here, sticky bit CLEAR
.next:
    pop si
    pop cx
    loop .one
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; assoc_note_app - record where a program is, and what it looks like
; in:  SI -> its staged 32-byte entry; ES = LOW_SEG with dsk_secbuf holding
;      its first sector, header validated as a v3 .o88 WITH an icon
; out: nothing (all registers preserved)
;
; Called from the harvest for every package it reads, so browsing the folder
; a program lives in teaches the OS its location and its glyph at no extra
; I/O - the read already happened.
; -----------------------------------------------------------------------------
assoc_note_app:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    call assoc_stem_of          ; DI -> assoc_stemb; SI untouched
    mov dx, si                  ; bank the entry
    mov si, di
    call assoc_app_of
    mov si, dx
    jnc .haveslot
    test byte [assoc_hflags], 2 ; no slot yet - but a package that DECLARES
    jz .out                     ; extensions is asking for one (SPEC.md 54.6)
    call assoc_app_new          ; (assoc_stemb still holds its stem)
    jc .out                     ; the table is full: nothing to record
.haveslot:
    push ax
    test byte [assoc_hflags], 2
    jz .nodecl
    call assoc_declare          ; AL = the slot
.nodecl:
    pop ax
    mov bl, al
    xor bh, bh
    mov cl, [disk_drive]
    mov [assoc_drv+bx], cl      ; where it was seen...
    push bx
    shl bx, 1
    mov ax, [dsk_cwd]
    mov [assoc_clus+bx], ax
    pop bx
    test byte [assoc_hflags], 1 ; ...and what it looks like, IF it ships an
    jz .out                     ; icon at all - an iconless package leaves
    mov cl, 3                   ; the glyph unresolved and its documents draw
    shl bx, cl                  ; the bare page, which is honest
    mov di, assoc_glyph
    add di, bx
    mov si, dsk_secbuf+64       ; the DATA plane of the embedded icon
    call assoc_reduce           ; ES = LOW_SEG, per SPEC.md 2.1
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

section .bss
assoc_hflags: resb 1            ; the header flags of the package the harvest
                                ; is looking at, banked because dsk_get_dir
                                ; re-stages the directory entry over dsk_ent
assoc_extb:  resb 3             ; one staged extension (assoc_ext_of)
assoc_stemb: resb 8             ; one staged stem (assoc_stem_of)
section .text

; The pending document open. In .text with a real initialiser, not .bss: -f
; bin zeroes nothing and ui.inc reads this on the machine's very first idle
; pass, before anything has written it (the fdlg_win precedent).
assoc_dapp:  db 0xFF            ; the app slot to open it with, 0xFF = none
assoc_argp:  db 0               ; 1 = a document is waiting to be claimed by
                                ; the next OSAPI_ARG_FILE (SPEC.md 54.5)

; =============================================================================
; The open path (SPEC.md 54.4) - double-clicking a document
; =============================================================================

; -----------------------------------------------------------------------------
; assoc_post - a document double-click, from under the gfx lock
; in:  SI -> the staged type-0 entry, DI = the poster's state block
; out: CF=0 = posted (ui.inc will run it once the lock drops); CF=1 = this
;      extension has no association, so the caller does what it always did
; clobbers: CF (everything else preserved)
;
; The document's LOCATION is deliberately not banked here. [dsk_cwd] is one
; global shared by every Disk window, and the window that posted this may not
; be the one currently mounted - so assoc_run syncs to the poster FIRST and
; reads the location on the other side of that, exactly as loader_run does
; with its index (SPEC.md 22.1).
; -----------------------------------------------------------------------------
assoc_post:
    push ax
    push cx
    push si
    push di
    push si                     ; the entry, for the name copy below
    call assoc_ext_of
    jc .no
    push si
    mov si, di
    call assoc_find             ; AL = the app slot
    pop si
    jc .no
    mov [assoc_dapp], al
    pop si                      ; the entry again
    push si
    mov di, assoc_doc           ; stage the document's own name
    mov cx, 12
.copy:
    mov al, [si]
    mov [di], al
    or al, al
    jz .named
    inc si
    inc di
    loop .copy
    mov byte [di], 0
.named:
    pop si
    pop di
    mov [assoc_pwin], di
    pop si
    pop cx
    pop ax
    clc
    ret
.no:
    pop si
    pop di
    pop si
    pop cx
    pop ax
    stc
    ret

; -----------------------------------------------------------------------------
; assoc_fname - build '<STEM>.O88' for the app slot in AL
; in:  AL = app slot
; out: assoc_fnb holds the NUL name; all registers preserved
; -----------------------------------------------------------------------------
assoc_fname:
    push ax
    push bx
    push cx
    push si
    push di
    mov bl, al
    xor bh, bh
    mov cl, 3
    shl bx, cl
    mov si, assoc_stem
    add si, bx
    mov di, assoc_fnb
    mov cx, 8
.stem:
    mov al, [si]
    cmp al, ' '                 ; the stem is space-padded; the name is not
    je .ext
    mov [di], al
    inc si
    inc di
    loop .stem
.ext:
    mov word [di], '.O'
    mov word [di+2], '88'
    mov byte [di+4], 0
    pop di
    pop si
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; assoc_try - is the program in THIS directory? (one rung of SPEC.md 54.4)
; in:  DL = volume, AX = directory cluster (0 = the root)
; out: CF=0 and AX = its directory index, with that volume+directory CURRENT;
;      CF=1 = not here (and the mount may have failed, which is the same
;      answer to the caller)
; clobbers: AX (the output), CF
;
; The name is re-checked on arrival every single time, which is what makes a
; cluster HINT safe: a cluster means nothing on a disk that has been swapped,
; so the hint is only ever a place to look.
; -----------------------------------------------------------------------------
assoc_try:
    push si
    call dsk_chdir
    jc .no
    mov si, assoc_fnb
    call dsk_find_name
    jc .no
    pop si
    clc
    ret
.no:
    pop si
    stc
    ret

; -----------------------------------------------------------------------------
; assoc_tryfold - the same, one folder down from a volume's root
; in:  DL = volume, BL = 1 = APPS, 2 = GAMES (0 = nothing to try)
; out: as assoc_try
; -----------------------------------------------------------------------------
assoc_tryfold:
    push si
    push di
    or bl, bl
    jz .no
    mov si, assoc_s_apps
    cmp bl, 1
    je .named
    mov si, assoc_s_games
.named:
    push si
    xor ax, ax                  ; the volume's root first
    call dsk_chdir
    pop si
    jc .no
    call dsk_find_name          ; AX = the FOLDER's index
    jc .no
    call dsk_get_dir            ; SI -> its staged entry
    cmp word [si+16], 2         ; ...and it must actually be a folder
    jne .no
    mov ax, [si+18]
    call assoc_try              ; DL is still the volume
    jc .no
    pop di
    pop si
    clc
    ret
.no:
    pop di
    pop si
    stc
    ret

; -----------------------------------------------------------------------------
; assoc_locate - find the program, four rungs (SPEC.md 54.4)
; in:  AL = app slot; [assoc_ddrv]/[assoc_dclus] = where the document lives
; out: CF=0 and AX = the program's directory index, its volume+directory
;      CURRENT; CF=1 = not found on any volume that would mount
; clobbers: AX (the output), CF
; -----------------------------------------------------------------------------
assoc_locate:
    push bx
    push cx
    push dx
    push si
    push di
    call assoc_fname            ; assoc_fnb = '<STEM>.O88'
    mov bl, al
    xor bh, bh
    mov di, bx                  ; DI = the slot, wanted after the shifts

    ; --- rung 1: the hint, if this program has ever been seen -------------
    mov dl, [assoc_drv+bx]
    cmp dl, 0xFF
    je .rung2
    shl bx, 1
    mov ax, [assoc_clus+bx]
    call assoc_try
    jnc .found

    ; --- rung 2: the document's own directory -----------------------------
.rung2:
    mov dl, [assoc_ddrv]
    mov ax, [assoc_dclus]
    call assoc_try
    jnc .found

    ; --- rungs 3 and 4: the root, then the folder a default names, on the
    ; document's volume and then the other floppy --------------------------
    mov cl, 2                   ; two volumes to try
    mov dl, [assoc_ddrv]
.vol:
    push dx
    xor ax, ax
    call assoc_try              ; the root
    pop dx
    jnc .found
    push dx
    mov bx, di
    mov bl, [assoc_dfold+bx]
    call assoc_tryfold
    pop dx
    jnc .found
    xor dl, 1                   ; A: <-> B:, the only other floppy there is
    dec cl
    jnz .vol
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    stc
    ret
.found:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    clc
    ret

; -----------------------------------------------------------------------------
; assoc_run - open the pending document (SPEC.md 54.4)
; in:  [assoc_dapp] != 0xFF; UI task, NO lock held
; out: nothing (all registers preserved)
;
; Structured like loader_run and ui_tm_open together: sync to the poster so
; the globals ARE its listing, bank where that is, go and find the program,
; load it, and put the volume back where the user was. The document is handed
; to the package by PULL - it asks with OSAPI_ARG_FILE - so nothing here has
; to be standing in the document's directory when the entry proc runs.
; -----------------------------------------------------------------------------
assoc_run:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    push es

    mov al, [assoc_dapp]
    mov byte [assoc_dapp], 0xFF ; consume before running, not after
    push ax

    mov di, [assoc_pwin]
    or di, di
    jz .located
    call fmv_sync               ; ...the globals become the poster's listing
.located:
    mov ax, [dsk_cwd]           ; and only NOW is the document's home known
    mov [assoc_dclus], ax
    mov al, [disk_drive]
    mov [assoc_ddrv], al

    pop ax
    push ax
    call assoc_locate           ; AX = the program's index, and we are in its
    jc .nofile                  ; directory

    mov bx, [assoc_pwin]
    mov [ld_pwin], bx
    mov byte [ld_painted], 0
    mov byte [assoc_argp], 1    ; armed ACROSS the load and disarmed after,
    call ld_run_body            ; so exactly one entry proc can claim it -
    mov byte [assoc_argp], 0    ; a package launched later, by any route,
    mov [ld_status], al         ; must never inherit this document
    push ds
    pop es                      ; ld_run_body's failure exits leave ES adrift
    call assoc_back             ; the user's volume FIRST, then the window
    cmp byte [ld_painted], 0
    jne .painted
    call files_refresh
    jmp short .out
.painted:
    call files_poster
    jmp short .out

.nofile:
    call assoc_back
    mov si, assoc_s_nofile
    call ui_note                ; "<PROGRAM> is not on either disk - insert
    call files_refresh          ; the disk it is on and try again"
.out:
    pop ax
    pop es
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; assoc_back - put the user's volume back where the document is. A failed
; remount leaves that volume mount-failed at its root with the write gate
; shut, which is survivable and is exactly ui_tm_back's contract.
assoc_back:
    push ax
    push dx
    mov ax, [assoc_dclus]
    mov dl, [assoc_ddrv]
    call dsk_chdir
    pop dx
    pop ax
    ret

assoc_s_apps:   db 'APPS', 0
assoc_s_games:  db 'GAMES', 0
assoc_s_nofile: db 'Program not found - insert the disk it is on', 0

section .bss
assoc_doc:   resb 13            ; the pending document's 8.3 name
assoc_fnb:   resb 13            ; '<STEM>.O88', built by assoc_fname
assoc_dclus: resw 1             ; ...and where it lives: directory cluster
assoc_ddrv:  resb 1             ; ...and volume
assoc_pwin:  resw 1             ; the Disk window that posted it
section .text

; =============================================================================
; The API surface (SPEC.md 54.5)
; =============================================================================

; -----------------------------------------------------------------------------
; osapi_arg_file - the document this instance was launched to open (0x02E8)
; in:  nothing
; out: CF=1 = no document; CF=0 with SI -> its NUL 8.3 name IN THE KERNEL
;      SEGMENT (ES is already KERNEL_SEG on entry to a package proc, SPEC.md
;      20.2), DX = the directory cluster it lives in and BL = its volume -
;      the same pair OSAPI_FILE_HERE answers and OSAPI_FILE_GOTO takes
; clobbers: SI, DX, BL (the outputs), CF
;
; READ-AND-CLEAR, and that is the whole of why a second instance cannot
; inherit a document: the first proc to ask gets it and the word is spent.
;
; PULL rather than push, because ld_run_body reads the program's image out of
; the PROGRAM's directory and far-calls its entry as one unit - so the kernel
; cannot be standing in the document's directory when that entry runs. Handing
; over the locator instead moves the one dsk_chdir to where it can happen, and
; the app spends it with slots it already had.
; -----------------------------------------------------------------------------
osapi_arg_file:
    cmp byte [assoc_argp], 0
    je .none
    mov byte [assoc_argp], 0    ; spent
    mov si, assoc_doc
    mov dx, [assoc_dclus]
    mov bl, [assoc_ddrv]
    clc
    ret
.none:
    stc
    ret

; -----------------------------------------------------------------------------
; osapi_assoc_set - claim an extension for a program (0x02F0, an X stub)
; in:  ES:SI -> 3 extension bytes then 8 stem bytes, both space-padded
; out: CF=1 = the tables are full and nothing was stored
; clobbers: CF
;
; The caller supplies its own file stem because the kernel cannot: I_NAME
; holds the 16-byte HEADER name ('SOLITAIRE'), not the 8.3 file name
; ('SOLITAIR'), and nothing in the instance record says where a package was
; loaded from. OS88_ASSOC in the SDK makes it one line.
;
; There is deliberately NO ownership model - "take over an existing one" was
; the ask, so a matching extension is repointed. Registering grants nothing:
; the worst outcome is that the wrong program opens a file.
;
; It sets the STICKY bit, which is what stops a package's header declaration
; (SPEC.md 54.6) quietly taking the extension back on the next mount of its
; folder.
; -----------------------------------------------------------------------------
osapi_assoc_set:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov di, assoc_extb          ; stage both halves into the kernel, the
    mov cx, 3                   ; dsk_get_dir idiom - everything below reads
.cext:                          ; through DS
    mov al, [es:si]
    mov [di], al
    inc si
    inc di
    loop .cext
    mov di, assoc_stemb
    mov cx, 8
.cstem:
    mov al, [es:si]
    mov [di], al
    inc si
    inc di
    loop .cstem

    mov si, assoc_stemb         ; the app slot: reuse this program's own if
    call assoc_app_of           ; it already has one, so a program claiming
    jnc .haveapp                ; four extensions takes one slot and not four
    call assoc_app_new
    jc .full
.haveapp:
    mov dl, al                  ; DL = the app slot from here down
    mov si, assoc_extb
    call assoc_find             ; already claimed by someone?
    jc .newext
    call assoc_ext_row          ; BX = that row
    jmp short .point
.newext:
    call assoc_ext_new          ; BX = a free row, with the extension in it
    jc .full
.point:
    mov al, dl
    or al, ASSOC_STICKY         ; a runtime claim outranks a declaration
    mov [bx+3], al
    call assoc_self_glyph       ; DL = slot; take the caller's own icon
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    clc
    ret
.full:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    stc
    ret

; assoc_ext_row - the row assoc_find just matched. in: SI -> 3 ext bytes;
; out: BX = its row (the caller has already had CF=0 from assoc_find)
assoc_ext_row:
    push ax
    push cx
    push di
    mov bx, assoc_ext
    mov cx, ASSOC_NEXT
.row:
    mov di, si
    mov al, [bx]
    cmp al, [di]
    jne .next
    mov al, [bx+1]
    cmp al, [di+1]
    jne .next
    mov al, [bx+2]
    cmp al, [di+2]
    je .out
.next:
    add bx, 4
    loop .row
.out:
    pop di
    pop cx
    pop ax
    ret

; assoc_ext_new - claim a free extension row. in: SI -> 3 ext bytes;
; out: CF=0 and BX = the row with the extension written in; CF=1 = full
assoc_ext_new:
    push ax
    push cx
    mov bx, assoc_ext
    mov cx, ASSOC_NEXT
.row:
    cmp byte [bx], 0
    je .take
    add bx, 4
    loop .row
    pop cx
    pop ax
    stc
    ret
.take:
    mov al, [si]
    mov [bx], al
    mov al, [si+1]
    mov [bx+1], al
    mov al, [si+2]
    mov [bx+2], al
    pop cx
    pop ax
    clc
    ret

; assoc_app_new - claim a free app slot for the stem in assoc_stemb.
; out: CF=0 and AL = the slot, its stem written and its glyph cleared;
;      CF=1 = every slot is taken
assoc_app_new:
    push bx
    push cx
    push dx
    push si
    push di
    mov bx, assoc_stem
    xor dh, dh
.row:
    cmp dh, ASSOC_NAPP
    jae .full
    cmp byte [bx], 0
    je .take
    add bx, 8
    inc dh
    jmp .row
.take:
    mov si, assoc_stemb
    mov di, bx
    mov cx, 8
.copy:
    mov al, [si]
    mov [di], al
    inc si
    inc di
    loop .copy
    mov bl, dh                  ; clear the side state: a slot reused for a
    xor bh, bh                  ; different program must not inherit the
    mov byte [assoc_drv+bx], 0xFF   ; last one's hint, folder or glyph
    mov byte [assoc_dfold+bx], 0
    push bx
    shl bx, 1
    mov word [assoc_clus+bx], 0
    pop bx
    mov cl, 3
    shl bx, cl
    mov di, assoc_glyph
    add di, bx
    mov cx, 8
.zap:
    mov byte [di], 0
    inc di
    loop .zap
    mov al, dh
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    clc
    ret
.full:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    stc
    ret

; assoc_self_glyph - reduce the CALLING package's own embedded icon into an
; app slot. in: DL = the slot, ES = the caller's segment (the X stub put it
; there). Does nothing if the caller ships no icon - the document then draws
; the bare page, which is honest.
assoc_self_glyph:
    push ax
    push bx
    push cx
    push si
    push di
    cmp word [es:0], 0x384F     ; 'O','8' - a package header, not a stray
    jne .out
    test byte [es:3], 1         ; the embedded-icon flag (SPEC.md 20.2)
    jz .out
    mov bl, dl
    xor bh, bh
    mov cl, 3
    shl bx, cl
    mov di, assoc_glyph
    add di, bx
    mov si, 64                  ; the DATA plane of the embedded icon
    call assoc_reduce
.out:
    pop di
    pop si
    pop cx
    pop bx
    pop ax
    ret
