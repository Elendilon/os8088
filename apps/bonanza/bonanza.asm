; BONANZA - Bounce Bonanza, an isometric rolling-ball game for os8088.
; Contract: SPEC.md 128 (the plan: docs/plans/BOUNCE-BONANZA-PLAN.md).
;
; WAVE 0 IS THE ENGINE SPIKE (SPEC.md 128): a ball rolled over a generated
; isometric test course that HARDWARE-SCROLLS IN BOTH DIRECTIONS on the CGA
; (FSXM_CGA320) and the Hercules (FSXM_HERC with Excitebike's 200-line
; pair-pixel field, SPEC.md 102.7.1), the 64-frame phase-torus ball, and the
; instruments that price a frame.  No heightfield physics, obstacles, sound or
; game rules yet.
;
; This file is the header, the window and its desktop face (SPEC.md 128.1,
; 128.6): the title, the keys, the adapter line, and after a benchmark the
; RESULTS.  bzvideo.inc is the bracket, the mode, the retrace wait, the ring
; writers and the boxes (128.2, 128.4); bzgame.inc is the frame loop, the
; simulation, the camera, the autopilot and the instruments (128.4 - 128.6).
; Nothing here is a reference game's: the ball is tools/bonanza_assets.py's
; (128.3) and the courses are text compiled by tools/bbcourse.py (128.10.4),
; generated into build/bonanza-art/ and carried as 3 + BZ_NCRS PARTS: three
; balls and one part a course, every one the CGA's (SPEC.md 128.11.3.1).
%include "os88api.inc"
OS88_HEADER 'BONANZA', bz_entry, 1 | OS88_F_PARTS, OS88_STACK_256 | OS88_HIGH | OS88_HIGHMEM
OS88_ICON16
    dw 0x07e0,0x1ff8,0x3ffc,0x7ffe,0x7ffe,0xffff,0xffff,0xffff
    dw 0xffff,0xffff,0xffff,0x7ffe,0x7ffe,0x3ffc,0x1ff8,0x07e0
    dw 0x07e0,0x1818,0x2004,0x4002,0x4c02,0x8c01,0x8001,0x8061
    dw 0x8061,0x8001,0x8c03,0x4c06,0x400e,0x203c,0x1ff8,0x07e0
OS88_ICON16_END
; The art files are PARTS of this file (SPEC.md 128.11.3.1, 20.12), every one
; lazy and compressed: only the play's course and ball are ever read, on the
; DESKTOP before the bracket (so op_fetch's refusal toast can be drawn), the
; Hercules translates both in place there (bz_hxlat), and both are dropped
; when the bracket returns (SPEC.md 128.7, 128.11.3).
%define OP_NO_LAZYOK            ; (the fetch itself asks; no pre-check is used)
%include "os88parts.inc"
%include "bzconst.inc"          ; the ball part's layout (tools/bonanza_assets.py)
%include "bzcourse.inc"         ; the courses and their part rows (tools/bbcourse.py)
%include "bzsnd.inc"            ; the songs and the events (tools/bbmusic.py)
%include "drivers/sound/sndpkg.inc" ; SOUND.DRV's FM door (bzsound.inc), from the root
                                ; as every bonanza row assembles it

%macro SAVE 0
 push ax
 push bx
 push cx
 push dx
 push si
 push di
 push bp
 push es
%endmacro
%macro RESTORE 0
 pop es
 pop bp
 pop di
 pop si
 pop dx
 pop cx
 pop bx
 pop ax
%endmacro

BZ_LH       equ 10              ; the face's line pitch: an 8px cell and 2px of air
BZ_LMAX     equ 88              ; the longest padded line (a 720px Hercules content box)

; --- the part rows: the Makefile's BZ_PARTS order (SPEC.md 128.11.3.1) ---------
BZ_P_BALR   equ 0               ; BZBALR.BIN  the rubber ball: a material's row
BZ_P_BALS   equ 1               ; BZBALS.BIN  is BZ_P_BALR + the material
BZ_P_BALG   equ 2               ; BZBALG.BIN
                                ; course K: BZ_P_CRS + K, bzcourse.inc's rows

; --- the course part's header (SPEC.md 128.10.5.1, 128.10.5.2) ------------------
; Byte offsets from the part's first byte; the grid's from GRIDOFF.  Nothing
; here is checked on the guest: tools/bbcourse.py checked every one of them at
; build time (SPEC.md 128.10.6.2).
BZC_COLS    equ 4               ; word columns: 64 or 128
BZC_BROWS   equ 6               ; block rows
BZC_NBLK    equ 8               ; N, blocks (bz_hxlat)
BZC_MAPSH   equ 10              ; 4 for 64 columns, 5 for 128
BZC_BLKOFF  equ 12              ; block 0's offset (bz_hxlat)
BZC_OCCIDX  equ 14              ; OCCIDX: BROWS + 1 words, each the offset of
                                ; the block row's first occluder record
BZC_ROWB    equ 24              ; 2 COLS: the map row's byte stride, READ by the
                                ; column writer through DS = the part (128.10.6.4)
BZC_GRID    equ 26              ; GRIDOFF
BZC_PROPOFF equ 28              ; the prop table (SPEC.md 128.12.3.1): its first
BZC_NPROP   equ 30              ; record, and the records (0: none)
BZC_MAP     equ 32              ; the map: COLS x BROWS words, absolute offsets
BZG_NROWS   equ 4               ; (at GRIDOFF +) the rows
BZG_SMIN    equ 6               ; row 0's s = wx + wy
BZG_AMIN    equ 8               ; signed, even: the first cell's a = wx - wy
BZG_KW      equ 10              ; cells a row
BZG_ROWTAB  equ 12              ; ROWTAB's offset: a row's first cell
BZG_X0      equ 14              ; px
BZG_Y0      equ 16              ; signed px
BZG_ID      equ 18              ; the course's IDENTITY (SPEC.md 128.12.8)
BZG_WX      equ 20              ; the start tile
BZG_WY      equ 22
BZG_NWAY    equ 24              ; the route: NWAY pairs of words, the ball's
BZG_ROUTE   equ 26              ; picture top-left (px), at this offset
; --- the ball part's header (BZB2, SPEC.md 128.11.9.1); its layout is
; bzconst.inc's BZ_BAL_* -------------------------------------------------------
BZB_NSHA    equ 12              ; byte: shatter frames, 4 for glass, else 0
; --- the replay log's header (SPEC.md 128.11.12.1), in [bz_rlog] ---------------
BZR_CRS     equ 4               ; byte: the course K
BZR_MAT     equ 5               ; byte: the material
BZR_FLAGS   equ 6               ; byte: bit 0 COMPLETE, bit 1 TRUNCATED
BZR_STEPS   equ 8               ; DWORD: the steps recorded
BZR_NRUN    equ 12              ; word: the runs recorded
BZR_ID      equ 14              ; word: the course's identity (128.12.8)
BZR_RUNS    equ 16              ; the runs: (key byte, count 1 - 255) pairs
BZR_SIZE    equ 4096            ; the log, bz_rlog: at most 2,040 runs
BZR_DONE    equ 1
BZR_TRUNC   equ 2

bz_entry:
    push es                     ; op_load spends ES, which arrives KERNEL_SEG
    call op_load                ; SI is still the kernel's name: FIRST. Every
    pop es                      ; row is lazy, so this copies the name and
    jc .out                     ; claims nothing
    mov si, bz_tpl
    call OSAPI_WM_CREATE        ; ...and AL = the class slots this kernel
    jc .out                     ; dispatches (SPEC.md 11.104): no timer slot
    cmp al, WC_ONTIMER + 1      ; is kern_small, the 128KB machine, which
    sbb al, al                  ; refuses the bracket (SPEC.md 128.1)
    neg al
    mov [bz_small], al
    mov [bz_win], bx
    mov byte [bz_crsel], BZ_CRS_FIRST ; the course Enter plays, and its ball
    mov al, [bz_cballs + BZ_CRS_FIRST] ; (N and M change them, SPEC.md
    mov [bz_matsel], al         ; 128.11.5.4)
    OS88_REGION_MOVABLE
    OS88_ALTENTER_ARM
    call bzs_dstart             ; the title's music (SPEC.md 128.20.6)           ; (also the ask 128.11.11.2 owes at the open:
                                ; asking arms SPEC.md 9.7's map, so the held-
                                ; key guard sees every key pressed after it)
    mov bx, [bz_win]
    clc
.out: ret

; -----------------------------------------------------------------------------
; the window's callbacks.  ES = KERNEL_SEG on entry to every one of them.
; -----------------------------------------------------------------------------
bz_paint:
    SAVE
    call bz_face
    cmp byte [bz_abon], 0
    je .done
    mov bx, [bz_win]
    mov si, bz_credits
    call os88ui_about_d
.done:
    RESTORE
    ret

bz_about:
    SAVE
    mov byte [bz_abon], 1
    mov bx, [bz_win]
    mov si, bz_credits
    call os88ui_about
    RESTORE
    ret

bz_click:
    SAVE
    cmp byte [bz_abon], 0
    je .done
    mov byte [bz_abon], 0
    call bz_repaint
.done:
    RESTORE
    ret

bz_onkey:
    SAVE
    cmp byte [bz_abon], 0
    je .key
    mov byte [bz_abon], 0
    call bz_repaint
    jmp .done
.key:
    cmp ax, KEY_ALTENTER
    je .play
    cmp al, 13
    je .play
    or al, 20h
    cmp al, 'f'
    je .play
    cmp al, 'b'
    je .bench
    cmp al, 'r'
    je .replay
    mov bx, bz_camkey           ; C, M, N: one press however long it is held
    cmp al, 'c'                 ; (SPEC.md 128.11.11.2)
    je .held
    mov bx, bz_ballkey
    cmp al, 'm'
    je .held
    mov bx, bzs_skey            ; S: the sound (SPEC.md 128.20.4)
    cmp al, 's'
    je .held
    mov bx, bz_crskey
    cmp al, 'n'
    jne .done
.held:
    call bz_dkey                ; AH = the make code: CF = 1 a repeat, swallowed
    jc .done
    call bx
    jmp .done
.replay:
    call bz_rhave               ; R: offered only when there is a log
    jne .done                   ; (SPEC.md 128.11.12.2): its course, and
    mov ah, [bz_rlog + BZR_CRS] ; bz_launch takes its ball
    mov al, 2
    jmp .go
.bench:
    mov ax, 1 | (BZ_CRS_BENCH << 8) ; B: the benchmark, on BENCH (SPEC.md
    jmp .go                     ; 128.10.11.1)
.play:
    mov al, 0                   ; Enter, F, Alt+Enter: play the selected
    mov ah, [bz_crsel]          ; course (SPEC.md 128.11.11.3)
.go:
    mov [bz_mode], al
    mov [bz_crs], ah
    call bz_launch
.done:
    RESTORE
    ret

; bz_dkey - the held-key guard (SPEC.md 128.11.11.2), AH = a typed key's make
; code.  The key's typematic repeats arrive as typed keys too, and an interval
; test cannot see the typematic DELAY, so the fact asked is whether the key
; came UP: while [bz_dkk] is this key's code it has not, and the key is
; SWALLOWED (CF = 1).  Else it is a press (CF = 0): [bz_dkk] takes its code and
; the window's timer is armed for a tick, whose handler (bz_ontimer) asks
; OSAPI_KEY_DOWN.  With no timer (kern_small answers CF = 1) there is no guard.
; Preserves all but AX and the flags.
bz_dkey:
    cmp ah, [bz_dkk]
    stc
    je .out
    mov [bz_dkk], ah
    push bx
    mov bx, [bz_win]
    mov ax, 1
    call OSAPI_WM_TIMER
    pop bx
    jnc .out
    mov byte [bz_dkk], 0
    clc                         ; a press
.out:
    ret

; the window's timer (WC_ONTIMER, SPEC.md 13.9): is [bz_dkk] still down?
; Down, ask again in a tick; up, the next typed key of it is a press
bz_ontimer:
    SAVE
    call bzs_dtick              ; the title (re-arms the timer while it plays)
    mov al, [bz_dkk]
    or al, al
    jz .done
    call OSAPI_KEY_DOWN
    jnc .up
    mov bx, [bz_win]
    mov ax, 1
    call OSAPI_WM_TIMER
    jmp .done
.up:
    mov byte [bz_dkk], 0
.done:
    RESTORE
    ret

; ZF = 1 when [bz_rlog] holds a log (the recorder's signature, SPEC.md
; 128.11.12.1).  The log is the package's own bss, written by the package:
; trusted, not checked (128.11.12.2).  Preserves all but the flags.
bz_rhave:
    cmp word [bz_rlog], 'BZ'
    jne .out
    cmp word [bz_rlog + 2], 'R1'
.out:
    ret

; the window repainted outside a paint: arm the clip first (SPEC.md 11.3)
bz_repaint:
    mov bx, [bz_win]
    call OSAPI_WM_CLIP_SET
    jc .out
    call bz_paint
.out:
    ret

; -----------------------------------------------------------------------------
; bz_adapter - what this window's display is: AL = 1 CGA, 2 Hercules, 0 neither
; (or no FSX mode for it).  Preserves all but AX and the flags.
; -----------------------------------------------------------------------------
bz_adapter:
    push bx
    push dx
    mov bx, [bz_win]
    call OSAPI_FSX_CAPS
    jc .none
    cmp dl, VID_CGA
    jne .herc
    test ax, 1 << FSXM_CGA320
    jz .none
    mov al, 1
    jmp .out
.herc:
    cmp dl, VID_HERC
    jne .none
    test ax, 1 << FSXM_HERC
    jz .none
    mov al, 2
    jmp .out
.none:
    xor al, al
.out:
    pop dx
    pop bx
    ret

; -----------------------------------------------------------------------------
; bz_launch - the desktop side of a play, a benchmark or a replay: every
; refusal is here, where a toast can still be drawn (SPEC.md 128.1, 128.7).
; In: [bz_mode] (0 play, 1 benchmark, 2 replay) and [bz_crs].  The MATERIAL is
; chosen here (SPEC.md 128.11.5.4): a play rolls the session's ball
; ([bz_matsel], M), a benchmark the course's own (BENCH's for B; the course a
; harness poked at this entry otherwise), a replay the log's.  Course K's part
; (row BZ_P_CRS + K) and the material's (BZ_P_BALR + [bz_mat]) are fetched -
; the same rows on both cards - and on the Hercules both are translated in
; place (bz_hgen, bz_hxlat, SPEC.md 128.11.3); the bracket runs, and both are
; dropped on every way out.
; -----------------------------------------------------------------------------
bz_launch:
    cmp byte [bz_small], 0
    je .big
    mov si, bz_t_small          ; kern_small: the parts are more heap than the
    jmp bz_toast                ; 128KB machine has
.big:
    call bz_adapter
    or al, al
    jnz .ok
    mov si, bz_t_adapt          ; VGA, EGA, MDA: CGA OR HERC ONLY
    jmp bz_toast
.ok:
    dec al
    mov [bz_herc], al
    mov al, [bz_matsel]         ; the material (above)
    mov bl, [bz_mode]
    dec bl
    js .mat                     ; 0: a play, M's
    mov al, [bz_rlog + BZR_MAT]
    jnz .mat                    ; 2: a replay, the log's
    mov bl, [bz_crs]            ; 1: a benchmark, the course's own
    xor bh, bh
    mov al, [bz_cballs + bx]
.mat:
    mov [bz_mat], al
    add al, BZ_P_BALR           ; its row (SPEC.md 128.11.3.1)
    mov [bz_pb], al
    mov al, [bz_crs]            ; course K's row: BZ_P_CRS + K (bzcourse.inc)
    add al, BZ_P_CRS
    mov [bz_pc], al
    call op_fetch               ; claim, read, expand - or a toast said why
    jc .out
    mov al, [bz_pc]             ; (each fetch's segment stored before the next
    call op_seg                 ; fetch, so tests/pins.txt keys each claim by
    mov [bz_cseg], ax           ; its own word: bz_cseg, bz_bseg)
    mov al, [bz_pb]
    call op_fetch
    jc .drop
    mov al, [bz_pb]
    call op_seg
    mov [bz_bseg], ax
    push es                     ; the title off, the course's song fetched
    call bzs_gfetch             ; (none had: a SILENT play, SPEC.md 128.20.6)
    pop es
    call bz_crshdr              ; the course's header, copied into our data
    cmp byte [bz_mode], 2       ; a REPLAY of a log made on another course (a
    jne .idok                   ; re-seeded one: its identity differs) is
    push es                     ; refused, and the face says so (SPEC.md
    mov es, [bz_cseg]           ; 128.12.8)
    mov di, [bz_goff]
    mov ax, [es:di + BZG_ID]
    pop es
    cmp ax, [bz_rlog + BZR_ID]
    je .idok
    mov byte [bz_err], 3
    jmp short .drop
.idok:
    cmp byte [bz_herc], 0       ; the Hercules's parts are the CGA's through
    je .run                     ; BZ_HTAB, made here (SPEC.md 128.11.3)
    push es                     ; (ES as the bracket call found it before:
    call bz_hgen                ; bz_hxlat leaves the ball's there)
    call bz_hxlat
    pop es
.run:
    mov byte [bz_err], 0
    mov bx, [bz_win]
    mov ax, bz_fullscreen
    mov cx, FSXF_FASTTICK
    call OSAPI_FSX_RUN
    jnc .drop
    mov si, bz_t_nofs
    call bz_toast
.drop:
    push ds                     ; ES = ours, not whatever the bracket left:
    pop es                      ; op_drop restores its caller's ES after the
                                ; free, and on kern_mega a part's own selector
                                ; there is a #GP once its claim is gone (the
                                ; final pass of wave 1: bonanzamega's fault at
                                ; op_drop's POP ES, the ball's selector in ES)
    mov al, [bz_pb]             ; (op_drop of a part that is not here is a
    call op_drop                ; no-op, so both go whichever failed)
    mov al, [bz_pc]
    call op_drop
    mov word [bz_cseg], 0
    mov word [bz_bseg], 0
    call bzs_gdrop              ; the song back, and the title (a finish's
    cmp byte [bz_err], 3        ; fanfare first, SPEC.md 128.20.6); no bracket
    jne .out                    ; ran: the face repainted with the refusal
    call bz_repaint
.out:
    ret

; -----------------------------------------------------------------------------
; bz_crshdr - the fetched course part's header, copied into our data (SPEC.md
; 128.10.6.4, 128.10.8 item 4): the writers' map shift and stride, the camera's
; limits' inputs, the grid's place, X0 and Y0 (and the projection's
; constants physics derives the screen position with), and the route.  The
; start is physics's (bzphys.inc bz_pinit).  Nothing is checked: the part was
; checked when it was built (128.10.6.2).  DS = ours, [bz_cseg] the course.
; Preserves nothing.
; -----------------------------------------------------------------------------
bz_crshdr:
    push es
    mov es, [bz_cseg]
    mov ax, [es:BZC_COLS]
    mov [bz_cols], ax
    mov ax, [es:BZC_BROWS]
    mov [bz_brows], ax
    mov al, [es:BZC_MAPSH]
    mov [bz_mapsh], al
    mov ax, [es:BZC_ROWB]
    mov [bz_rowb], ax
    mov di, [es:BZC_GRID]
    mov [bz_goff], di
    mov ax, [es:di + BZG_X0]
    mov [bz_x0], ax
    mov ax, [es:di + BZG_Y0]
    mov [bz_y0], ax
    mov ax, [es:di + BZG_NWAY]
    mov [bz_nway], ax
    mov ax, [es:di + BZG_ROUTE]
    mov [bz_wayoff], ax
    mov ax, [bz_x0]             ; the projection's constants, 24.8 (128.10.8):
    sub ax, 8                   ; bz_kx = (X0 - 8) << 8 ...
    call .k
    mov [bz_kx], ax
    mov [bz_kx + 2], dx
    mov ax, [bz_y0]             ; ...bz_ky = (Y0 - 13) << 8, Y0 signed
    sub ax, 13
    call .k
    mov [bz_ky], ax
    mov [bz_ky + 2], dx
    pop es
    ret
; AX (signed) -> DX:AX = AX << 8
.k:
    mov dl, ah                  ; DL = the high byte
    mov ah, al
    xor al, al                  ; AX = the low word
    xchg ax, dx
    cbw                         ; (AL = that high byte) AX = the high word
    xchg ax, dx
    ret

; -----------------------------------------------------------------------------
; THE HERCULES MADE AT THE FETCH (SPEC.md 128.11.3).  A Hercules byte is the
; CGA byte with each 2-bit pixel c replaced by herc_pair(c, line, column): 00
; for 0, 11 for 3, and for 1 or 2, 10 where line + column is even and 01 where
; it is odd.  Every block, ball row and squash or shatter row starts on a
; 4-pixel world column, so only the PARITY p of a byte's line chooses, and
; BZ_HTAB[256 p + b] is the byte b translated: two 256-byte tables.
;
; bz_hgen - BUILD BZ_HTAB into the first 512 bytes of bz_boxbuf, which nothing
; uses until the bracket starts.  Per byte, bitwise rather than per pixel: a
; field is MID (1 or 2) where its two bits differ, m = those fields' 11s, and
; the byte is b ^ ((b ^ P) & m) with P the parity's mid pattern - 10 01 10 01
; (99h) for p = 0, 01 10 01 10 (66h) for p = 1, which is NOT 99h.  The tool's
; bbcourse.htab() is the same table; bonanzaring's Hercules oracle checks this
; one by its picture (SPEC.md 128.11.17.2).  DS = ours.  Preserves nothing.
; -----------------------------------------------------------------------------
bz_hgen:
    mov di, bz_boxbuf
    mov dl, 99h                 ; P for p = 0
.p:
    xor cx, cx                  ; CL = b, 0 .. 255
.b:
    mov al, cl
    mov ah, al
    shr ah, 1
    xor ah, al
    and ah, 55h                 ; each mid field's low bit
    mov bh, ah
    shl ah, 1
    or ah, bh                   ; AH = m
    mov bh, al
    xor bh, dl
    and bh, ah
    xor al, bh                  ; AL = b ^ ((b ^ P) & m)
    mov [di], al
    inc di
    inc cl
    jnz .b
    not dl                      ; 99h -> 66h: the second table; 66h -> 99h: done
    cmp dl, 66h
    je .p
    ret

; -----------------------------------------------------------------------------
; bz_hxlat - translate the fetched course and ball parts IN PLACE through
; BZ_HTAB (SPEC.md 128.11.3), on the Hercules, before the bracket:
;   the course's blocks, BLKOFF .. BLKOFF + 16 N: a block line is ONE WORD, its
;     index in the block the line, so the table changes every two bytes (8
;     lines a block, even: one run of 8 N rows of 2 bytes from table 0);
;   the ball's ROLL frames: frame f's row r through ((f >> 3) + r) & 1, so each
;     run of 8 frames is 128 rows of 5 bytes from table (f >> 3) & 1;
;   the FRAME half of each squash and shatter entry (frame x shift x parity
;     copy p x (mask 80, frame 80)): 16 rows from table p;
;   a PLATFORM's sprite (wave 3, SPEC.md 128.12.6.4): parity copy p x (mask
;     144, frame 144), the frame's row r through table (p + r) AND 1.
; Masks and the shadow are the same bytes on both cards and are not touched.
; XLAT reads DS:BX + AL, so DS = OURS (the table, in our bss) and the part is
; ES (`es lodsb`, `stosb`, SI = DI): on kern_mega ES is the part's own
; selector, written whole at offsets under its length, as op_fetch's expand
; already writes it; nothing through CS (SPEC.md 128.11.14).  DS = ours.
; Preserves nothing; ES is left the ball's (bz_launch saves and restores it).
; -----------------------------------------------------------------------------
bz_hxlat:
    mov bx, bz_boxbuf           ; BX = table 0, BP = the toggle to table 1 and
    lea bp, [bx + 256]          ; back: table 0 ^ table 1, two byte bases 256
    xor bp, bx                  ; apart (any alignment)
    mov es, [bz_cseg]           ; the course: 8 N rows of 2 bytes
    mov si, [es:BZC_BLKOFF]
    mov cx, [es:BZC_NBLK]
    shl cx, 1
    shl cx, 1
    shl cx, 1
    mov dl, 2
    call bz_hxrows
    mov cx, [es:BZC_NPROP]      ; the PLATFORMS' sprites (SPEC.md 128.12.6.4):
    mov di, [es:BZC_PROPOFF]    ; parity copy p's frame half, row r through
    jcxz .noplat                ; table (p + r) AND 1 (BX is table 0 here: the
.prec:                          ; blocks' run is even)
    cmp byte [es:di + BZP_KIND], BZ_PK_PLATFORM
    jne .pnext
    push cx
    push di
    mov si, [es:di + BZP_PSPR]
    mov dl, BZ_PLW / 4
    add si, BZ_PLH * BZ_PLW / 4 ; past copy 0's mask
    mov cx, BZ_PLH              ; (even: back on table 0)
    call bz_hxrows
    add si, BZ_PLH * BZ_PLW / 4 ; past copy 1's mask
    xor bx, bp                  ; copy 1's first row: table 1
    mov cx, BZ_PLH
    call bz_hxrows
    xor bx, bp                  ; (table 0 again)
    pop di
    pop cx
.pnext:
    add di, BZ_PROPREC
    loop .prec
.noplat:
    mov es, [bz_bseg]           ; the ball's roll frames: 8 runs of 8 frames
    mov si, BZ_BAL_FRMOFF
    mov dl, BZ_BAL_RB
    mov dh, BZ_BAL_FRAMES / 8
.roll:
    mov cx, 8 * BZ_BAL_ROWS     ; (even: the run ends on its first table)
    call bz_hxrows
    xor bx, bp                  ; the next run's first row: the other table
    dec dh
    jnz .roll
    mov si, BZ_BAL_SQOFF        ; the squash entries
    mov al, BZ_BAL_NSQ
    call bz_hxents
    mov si, BZ_BAL_SHAOFF       ; ...and glass's shatter entries: +12 counts
    mov al, [es:BZB_NSHA]       ; them, 0 for rubber and steel
; AL = frames of entries at SI: each frame's BZ_BAL_SHIFTS x 2 parity copies,
; every copy's frame half 16 rows from table p (copies alternate p = 0, 1)
bz_hxents:
    mov ah, BZ_BAL_SHIFTS * 2
    mul ah
    or ax, ax
    jz .out
    mov dh, al                  ; (at most 4 x 8 entries)
    mov bx, bz_boxbuf
.ent:
    add si, BZ_BAL_ENT / 2      ; past the mask half to the frame half
    mov cx, BZ_BAL_ROWS
    call bz_hxrows              ; (even: back on the copy's own table)
    xor bx, bp                  ; the next copy is the other parity
    dec dh
    jnz .ent
.out:
    ret

; ES:SI = the first byte, CX = rows (at least 1) of DL bytes, BX = the first
; row's table, BP = the toggle: each byte through the table, each row then the
; other table.  Out: SI past the last byte, BX the next row's table.  Clobbers
; AX, CX, DI.
bz_hxrows:
    mov di, si
.r:
    mov ah, dl
.b:
    es lodsb
    xlat
    stosb
    dec ah
    jnz .b
    xor bx, bp
    loop .r
    ret

; SI = a TOASTSTR in our segment
bz_toast:
    push es
    push ds
    pop es
    xor cx, cx
    call OSAPI_TOAST
    pop es
    ret

TOASTSTR bz_t_small, 'Bonanza: too little RAM'
TOASTSTR bz_t_adapt, 'CGA OR HERC ONLY'
TOASTSTR bz_t_nofs, 'Bonanza: no full screen'

; -----------------------------------------------------------------------------
; THE FACE.  Every line is ONE opaque OSAPI_FONT_RUN padded with spaces to the
; content's width (the padding is the erase, SPEC.md 6.1), and only the 2px
; gaps between lines and the strip under the last one are filled: no pixel is
; written twice.  The lines are built in bz_lbuf.
; -----------------------------------------------------------------------------
bz_face:
    call bz_fgeom
    jc .out
    mov word [bz_fy], 0
    ; line 0, 1: the title and the keys
    mov si, bz_s_title
    call bz_lstr
    call bz_line
    call bz_playline            ; ENTER <the course's title>  B bench
    ; line 2: the adapter, or the refusal's reason
    mov si, bz_s_small
    cmp byte [bz_small], 0
    jne .adl
    call bz_adapter
    mov si, bz_s_cga
    cmp al, 1
    je .adl
    mov si, bz_s_herc
    cmp al, 2
    je .adl
    mov si, bz_s_noad
.adl:
    call bz_lstr
    call bz_line
    call bz_keyline             ; line 3: the camera, the ball, their keys
    call bz_sndline             ; line 4: the sound and its key (128.20.4)
    cmp byte [bz_err], 3        ; (a refused replay says why, whatever the
    je .nores                   ; lines would hold)
    cmp byte [bz_fin], 0        ; lines 4 and 5 after a play or a replay that
    je .nofin                   ; reached the goal: its time (SPEC.md
    call bz_finline             ; 128.10.6.2) and its mishaps (128.11.11.3),
    call bz_tally               ; IN PLACE OF the last benchmark's results -
    jmp short .nores            ; the CGA's content holds 13 lines and they
.nofin:                         ; are 9 - which come back with the next one
    cmp byte [bz_res], 0
    jne .results
.nores:
    mov al, [bz_err]            ; 1 the mode was refused, 2 the display
    or al, al                   ; changed between the key and the bracket,
    jz .hint                    ; 3 a replay's log is another course's
    mov si, bz_s_err
    cmp al, 1
    je .errl
    mov si, bz_s_err2
    cmp al, 2
    je .errl
    mov si, bz_s_err3
.errl:
    call bz_lstr
    call bz_line
.hint:
    mov si, bz_s_hint
    call bz_lstr
    call bz_line
    mov si, bz_s_hint2
    call bz_lstr
    call bz_line
    jmp .tail
.results:
    call bz_facres
.tail:
    ; the strip under the last line, to the content's foot
    mov bx, [bz_fy]
    mov dx, [bz_fh]
    dec dx
    cmp dx, bx
    jl .right
    call bz_fillrows
.right:
    ; the columns right of the last whole cell (a content width that is not
    ; a multiple of 8), over the lines' height only: the strips above own
    ; the full width already
    mov ax, [bz_fcells]
    mov cl, 3
    shl ax, cl
    cmp ax, [bz_fw]
    jae .out
    mov cx, [bz_fw]
    dec cx
    xor bx, bx
    mov dx, [bz_fh]
    dec dx
    call bz_fillrect
.out:
    ret

; the face's geometry: [bz_fw], [bz_fh], [bz_ox], [bz_oy], [bz_fcells].  CF = 1
; when the window has none.  Clobbers AX, BX, CX, DX.
bz_fgeom:
    mov bx, [bz_win]
    call OSAPI_WM_GEOM
    jc .out
    mov [bz_fw], cx
    mov [bz_fh], dx
    call OSAPI_WM_CONTENT
    mov [bz_ox], ax
    mov [bz_oy], dx
    mov ax, [bz_fw]
    mov cl, 3
    shr ax, cl
    cmp ax, BZ_LMAX
    jbe .cells
    mov ax, BZ_LMAX
.cells:
    mov [bz_fcells], ax
    clc
.out:
    ret

; line 1 at [bz_fy], what Enter plays: `ENTER <title>  B bench` (SPEC.md
; 128.11.11.3), the title the selected course's (N)
bz_playline:
    mov si, bz_s_keys
    call bz_lstr
    mov al, [bz_crsel]
    mov ah, BZ_CRS_TITLEB
    mul ah
    add ax, bz_ctitles
    xchg ax, si
    call bz_lcat
    mov si, bz_s_keyb
    call bz_lcat
    jmp bz_line

; line 3 at [bz_fy], the settings and their keys: `C <camera>  M <ball>  N
; COURSE`, and `R REPLAY` when there is a log (SPEC.md 128.11.11.3).  C, M and N
; on the desktop redraw it (bz_camkey, bz_ballkey, bz_crskey): the same pixels
; the whole face draws there, once.
bz_keyline:
    mov si, bz_s_camk
    call bz_lstr
    mov bl, [bz_cmode]
    xor bh, bh
    shl bx, 1
    mov si, [bz_s_cmodes + bx]
    call bz_lcat
    mov si, bz_s_ballk
    call bz_lcat
    mov bl, [bz_matsel]
    xor bh, bh
    shl bx, 1
    mov si, [bz_s_mats + bx]
    call bz_lcat
    mov si, bz_s_crsk
    call bz_lcat
    call bz_rhave
    jne .line
    mov si, bz_s_repk
    call bz_lcat
.line:
    jmp bz_line

; the FINISHED line at [bz_fy]: "Finished in <s.hh> s", the steps the play took
; in GAME time (bzphys.inc bz_ftime: a cut's discarded sub-ticks are not in it)
bz_finline:
    call bz_ftime               ; DX:AX = hundredths (spends DI: first)
    mov si, bz_s_fin
    call bz_lstr
    mov cx, 100
    div cx                      ; (under 1,200 s: the quotient fits; bz_lstr
                                ; kept DX:AX)
    push dx
    xor dx, dx
    call bz_lnum
    mov al, '.'
    call bz_lch
    pop ax
    aam                         ; AH = tens, AL = units
    xchg al, ah
    add ax, '00'
    call bz_lch
    mov al, ah
    call bz_lch
    mov si, bz_s_secs
    call bz_lcat
    jmp bz_line

; the TALLY line at [bz_fy], under the time: `Falls <n>  stuns <n>  shatters
; <n>` - the play's respawns that were not a shatter's, and its steel stuns and
; glass shatters (SPEC.md 128.11.11.3).  At the goal every shatter has
; respawned (a shattering ball reaches no goal), so the falls are not negative.
bz_tally:
    mov si, bz_s_falls
    call bz_lstr
    mov ax, [bz_nfall]
    sub ax, [bz_nshat]
    mov bx, bz_nstun
    mov cx, 3
.n:
    xor dx, dx
    call bz_lnum
    dec cx
    jz .line
    mov si, [bz_s_tally + bx - bz_nstun]
    call bz_lcat
    mov ax, [bx]
    inc bx
    inc bx
    jmp .n
.line:
    jmp bz_line

; C, M and N on the desktop (one press each, bz_dkey): the next camera mode,
; ball or course, and the lines that name them redrawn - outside a paint, so
; the clip is armed first (SPEC.md 11.3).  N sets the ball to the new course's
; own (SPEC.md 128.11.5.4).  Every one is the session's, not the disk's.
bz_camkey:
    call bz_cnext
    jmp short bz_line3

bz_ballkey:
    inc byte [bz_matsel]
    cmp byte [bz_matsel], BZ_NMAT
    jb bz_line3
    mov byte [bz_matsel], 0
bz_line3:
    call bz_fclip
    jc .out
    mov word [bz_fy], 3 * BZ_LH
    call bz_keyline
.out:
    ret

%if BZ_CRS_BENCH != 0
 %error "bz_crskey cycles courses 1 .. BZ_NCRS - 1: BENCH must be course 0"
%endif
; line 4 at [bz_fy]: `S <the sound>` - the player's choice and, under AUTO,
; the arm it found (SPEC.md 128.20.4).  S redraws it (bzs_skey).
bz_sndline:
    mov si, bz_s_sndk
    call bz_lstr
    mov bl, [bzs_mode]
    xor bh, bh
    shl bx, 1
    mov si, [bz_s_smodes + bx]
    call bz_lcat
    cmp byte [bzs_mode], BZS_M_SPK
    jae .l
    mov si, bz_s_sfm
    cmp byte [bzs_arm], BZS_A_FM
    je .a
    mov si, bz_s_sspk
.a:
    call bz_lcat
.l:
    jmp bz_line
bz_line4:
    call bz_fclip
    jc .out
    mov word [bz_fy], 4 * BZ_LH
    call bz_sndline
.out:
    ret

bz_crskey:
    mov bl, [bz_crsel]          ; every course but BENCH: FIRST, TRIAL, ...
    inc bx
    cmp bl, BZ_NCRS
    jb .k
    mov bl, 1
.k:
    mov [bz_crsel], bl
    xor bh, bh
    mov al, [bz_cballs + bx]
    mov [bz_matsel], al
    call bz_fclip
    jc .out
    mov word [bz_fy], 1 * BZ_LH
    call bz_playline
    mov word [bz_fy], 3 * BZ_LH
    call bz_keyline
.out:
    ret

; the window's clip armed and the face's geometry read: CF = 1 when either
; cannot be had.  Clobbers AX, BX, CX, DX.
bz_fclip:
    mov bx, [bz_win]
    call OSAPI_WM_CLIP_SET
    jc .out
    call bz_fgeom
.out:
    ret

; the RESULTS of the last benchmark (SPEC.md 128.6): the frames and the display
; rate, the refreshes missed and the worst frame, then the mean CPU clocks of
; each part of a frame (PIT counts x 4), then the writer counts
bz_facres:
    mov si, bz_s_frames
    call bz_lstr
    mov ax, [bz_rframes]
    xor dx, dx
    call bz_lnum
    mov si, bz_s_disp
    call bz_lcat
    call bz_hz10                ; AX = the display rate x 10
    xor dx, dx
    mov cx, 10
    div cx
    push dx
    xor dx, dx
    call bz_lnum
    mov al, '.'
    call bz_lch
    pop ax
    add al, '0'
    call bz_lch
    mov si, bz_s_hz             ; and the refreshes missed: a mean rate
    call bz_lcat                ; cannot tell 0 misses from a few
    mov ax, [bz_rmiss]
    xor dx, dx
    call bz_lnum
    call bz_line
    mov si, bz_s_worst          ; the worst frame, and the means' heading
    call bz_lstr
    mov ax, [bz_rfmax]
    mov dx, [bz_rfmax + 2]
    shl ax, 1                   ; PIT counts x 4 = CPU clocks
    rcl dx, 1
    shl ax, 1
    rcl dx, 1
    call bz_lnum
    mov si, bz_s_mean
    call bz_lcat
    call bz_line
    xor bx, bx                  ; BX = the part (0..5)
.part:
    push bx
    mov si, bx
    shl si, 1
    mov si, [bz_s_parts + si]
    call bz_lstr
    pop bx
    push bx
    call bz_meanclk             ; DX:AX = part BX's mean, CPU clocks
    call bz_lnum
    mov si, bz_s_clk
    call bz_lcat
    call bz_line
    pop bx
    inc bx
    cmp bx, BZ_NFACE            ; (the wheel's part is the rows' to read: the
    jb .part                    ; face keeps its 13 lines, SPEC.md 128.12.5.6)
    mov si, bz_s_cols
    call bz_lstr
    mov ax, [bz_rncol]
    xor dx, dx
    call bz_lnum
    mov si, bz_s_rows
    call bz_lcat
    mov ax, [bz_rnrow]
    xor dx, dx
    call bz_lnum
    mov si, bz_s_full
    call bz_lcat
    mov ax, [bz_rnfull]
    xor dx, dx
    call bz_lnum
    mov si, bz_s_late           ; the row-0 boxes the beam overtook (SPEC.md
    call bz_lcat                ; 128.9 item 6), on the same line: the CGA
    mov ax, [bz_rlate]          ; window's 136 content lines hold 13 face
    xor dx, dx                  ; lines and this face is 13
    call bz_lnum
    jmp bz_line

; -> AX = the display rate x 10, from the measured frames' mean period.  1 PIT
; count is 1/1,193,182 s, so rate x 10 = 11,931,820 / mean counts.  0 = none.
bz_hz10:
    push bx
    push cx
    push dx
    call bz_period              ; DX:AX = mean PIT counts a frame (DX = 0 if sane)
    or dx, dx
    jnz .zero
    cmp ax, 183                 ; (the divide's quotient must fit 16 bits)
    jb .zero
    mov cx, ax
    mov dx, 11931820 >> 16
    mov ax, 11931820 & 0ffffh
    div cx
    jmp .out
.zero:
    xor ax, ax
.out:
    pop dx
    pop cx
    pop bx
    ret

; -> DX:AX = the mean PIT counts of one measured frame (the seven parts summed)
bz_period:
    push bx
    push cx
    push si
    xor ax, ax
    xor dx, dx
    mov si, bz_racc
    mov cx, BZ_NPART
.sum:
    add ax, [si]
    adc dx, [si + 2]
    add si, 4
    loop .sum
    call bz_div32
    pop si
    pop cx
    pop bx
    ret

; BX = part -> DX:AX = its mean in CPU clocks (PIT counts x 4)
bz_meanclk:
    push si
    mov si, bx
    shl si, 1
    shl si, 1
    mov ax, [bz_racc + si]
    mov dx, [bz_racc + si + 2]
    call bz_div32
    shl ax, 1
    rcl dx, 1
    shl ax, 1
    rcl dx, 1
    pop si
    ret

; DX:AX / [bz_rmfr] -> DX:AX (32 by 16, in two divides; 0 frames gives 0)
bz_div32:
    push bx
    push cx
    mov cx, [bz_rmfr]
    jcxz .zero
    mov bx, ax
    mov ax, dx
    xor dx, dx
    div cx                      ; the high word
    xchg ax, bx                 ; BX = the high quotient, AX = the low dividend
    div cx                      ; DX = the remainder from the high word
    mov dx, bx
    jmp .out
.zero:
    xor ax, ax
    xor dx, dx
.out:
    pop cx
    pop bx
    ret

; ---- the line builder ---------------------------------------------------------
; bz_lstr: SI = a NUL string -> bz_lbuf holds it (DI = its end)
bz_lstr:
    mov di, bz_lbuf
    mov byte [di], ' '          ; a cell of margin: the padding is the erase
    inc di
; bz_lcat: append SI's NUL string at DI
bz_lcat:
    push ax
.c:
    lodsb
    or al, al
    jz .e
    call bz_lch
    jmp .c
.e:
    pop ax
    ret

; AL = a character, appended at DI unless the line is full
bz_lch:
    cmp di, bz_lbuf + BZ_LMAX
    jae .full
    mov [di], al
    inc di
.full:
    ret

; DX:AX = an unsigned number, appended at DI in decimal
bz_lnum:
    ; STKBALANCE-LOOP: one digit pushed a turn and the second loop pops them down to the SI mark
    push ax
    push bx
    push cx
    push dx
    push si
    mov si, sp                  ; the digits go on the stack, least first
    mov cx, 10
.dig:
    mov bx, ax                  ; DX:AX / 10, in two divides
    mov ax, dx
    xor dx, dx
    div cx
    xchg ax, bx
    div cx
    push dx                     ; the digit
    mov dx, bx
    mov bx, ax
    or bx, dx
    jnz .dig
.out:
    pop ax
    add al, '0'
    call bz_lch
    cmp sp, si
    jne .out
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; the line at DI ends: pad it to the content's cells, draw it at [bz_fy] + 2,
; fill the 2px gap above it, and step [bz_fy]
bz_line:
    push ax
    push bx
    push cx
    push dx
    push si
    mov cx, [bz_fcells]
    add cx, bz_lbuf
.pad:
    cmp di, cx
    jae .padded
    mov byte [di], ' '
    inc di
    jmp .pad
.padded:
    mov di, cx
    mov byte [di], 0
    mov bx, [bz_fy]             ; the gap above the cell row
    mov dx, bx
    inc dx
    call bz_fillrows
    add dx, BZ_LH - 1           ; DX = the cell's foot, exclusive
    cmp dx, [bz_fh]
    jle .fits
    inc bx                      ; a cell past the content's foot is not drawn
    inc bx                      ; (FONT_RUN does not clip to it): its rows
    call bz_fillrows            ; that are inside are filled instead
    jmp .next
.fits:
    mov si, bz_lbuf
    xor cx, cx
    add cx, [bz_ox]
    mov dx, [bz_fy]
    add dx, 2
    add dx, [bz_oy]
    mov ax, CBLACK | (CWHITE << 8)
    call OSAPI_FONT_RUN
.next:
    add word [bz_fy], BZ_LH
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; BX = the first content row, DX = the last: filled white across the cells'
; width (bz_fillrect's x range)
bz_fillrows:
    push ax
    push cx
    xor ax, ax
    mov cx, [bz_fcells]
    shl cx, 1
    shl cx, 1
    shl cx, 1
    dec cx
    call bz_fillrect
    pop cx
    pop ax
    ret

; AX = x1, BX = y1, CX = x2, DX = y2 in content coordinates: a white fill,
; clipped to the content box's foot
bz_fillrect:
    push ax
    push bx
    push cx
    push dx
    cmp dx, [bz_fh]
    jl .h
    mov dx, [bz_fh]
    dec dx
.h:
    cmp dx, bx
    jl .out
    push ax
    mov al, CWHITE
    call OSAPI_SET_COLOR
    pop ax
    add ax, [bz_ox]
    add cx, [bz_ox]
    add bx, [bz_oy]
    add dx, [bz_oy]
    call OSAPI_GFX_FILL
.out:
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; --- the window -----------------------------------------------------------------
bz_tpl: dw 40, 24, 344, 168, bz_title, bz_cls
; its CLASS (SPEC.md 11.104): every handler; WF_OWNBG, the face paints every pixel
    OS88_CLASS bz_cls, WF_OWNBG, PAINT, bz_paint, ONKEY, bz_onkey, \
               ONCLICK, bz_click, ABOUT, bz_about, ONTIMER, bz_ontimer
bz_title: db 'Bounce Bonanza',0
bz_credits: dw bz_title,bz_credit1,bz_credit2,bz_credit3,0
bz_credit1: db 'Isometric rolling-ball game',0
bz_credit2: db 'Wave 3: obstacles and the wheel',0
bz_credit3: db 'Generated art, original design',0

bz_s_title: db 'BOUNCE BONANZA - wave 3',0
bz_s_keys:  db 'ENTER ',0
bz_s_sndk:  db 'S SOUND ',0
bz_s_smodes: dw bz_s_sauto, bz_s_sspkf, bz_s_sfx, bz_s_soff
bz_s_sauto: db 'AUTO',0
bz_s_sspkf: db 'SPEAKER',0
bz_s_sfx:   db 'EFFECTS ONLY',0
bz_s_soff:  db 'OFF',0
bz_s_sfm:   db ': ADLIB',0
bz_s_sspk:  db ': SPEAKER',0
bz_s_keyb:  db '  B bench',0
bz_ctitles: BZ_CRS_TITLES       ; the courses' titles, BZ_CRS_TITLEB bytes each
bz_cballs:  BZ_CRS_BALLS        ; ...and their balls, a byte each
bz_s_cga:   db 'Adapter: CGA, 320x200 four colours',0
bz_s_herc:  db 'Adapter: Hercules, 360x200 pair pixels',0
bz_s_noad:  db 'CGA OR HERC ONLY',0
bz_s_small: db 'NEEDS MORE MEMORY (128KB kernel)',0
bz_s_camk:  db 'C ',0
bz_s_ballk: db '  M ',0
bz_s_crsk:  db '  N COURSE',0
bz_s_repk:  db '  R REPLAY',0
bz_s_mats:  dw bz_s_rubber, bz_s_steel, bz_s_glass
bz_s_rubber: db 'RUBBER',0
bz_s_steel: db 'STEEL',0
bz_s_glass: db 'GLASS',0
bz_s_cmodes: dw bz_s_glide, bz_s_trickle   ; bz_cmode's (SPEC.md 128.11.11.1)
bz_s_glide: db 'GLIDE',0
bz_s_trickle: db 'TRICKLE',0
bz_s_hint:  db 'Arrows roll  Space hop  L.Shift grip',0
bz_s_hint2: db 'Esc, F or Alt+Enter: back',0
bz_s_fin:   db 'Finished in ',0
bz_s_falls: db 'Falls ',0
bz_s_tally: dw bz_s_stuns, bz_s_shats   ; after bz_nstun's and bz_nshat's
bz_s_stuns: db '  stuns ',0
bz_s_shats: db '  shatters ',0
bz_s_secs:  db ' s',0
bz_s_err:   db 'The full screen mode was refused',0
bz_s_err2:  db "The window's display changed",0
bz_s_err3:  db "Another course's log",0
bz_s_frames: db 'Frames ',0
bz_s_disp:  db '  ',0
bz_s_hz:    db ' Hz  misses ',0
bz_s_worst: db 'Worst ',0
bz_s_mean:  db ' clk   means (GLIDE):',0
bz_s_clk:   db ' clk',0
bz_s_cols:  db 'Cols ',0
bz_s_rows:  db '  rows ',0
bz_s_full:  db '  full ',0
bz_s_late:  db '  late ',0
bz_s_parts: dw bz_s_p0, bz_s_p1, bz_s_p2, bz_s_p3, bz_s_p4, bz_s_p5
bz_s_p0:    db '  sim+camera     ',0
bz_s_p1:    db '  box compose    ',0
bz_s_p2:    db '  rows           ',0
bz_s_p3:    db '  retrace (idle) ',0
bz_s_p4:    db '  flip+columns   ',0
bz_s_p5:    db '  box write      ',0

%include "bzvideo.inc"
%include "bzgame.inc"
%include "bzwheel.inc"
%include "bzphys.inc"
%include "bzsound.inc"
%if 4 * BZ_BOXB < 512
 %error "bz_hgen: BZ_HTAB's 512 bytes do not fit bz_boxbuf"
%endif

; --- the part table (SPEC.md 128.11.3.1, 20.12) --------------------------------
; 3 + BZ_NCRS rows, in the Makefile's BZ_PARTS order, every one OP_LAZY |
; OP_COMP: the three balls, then each course (BZ_COURSES's order, bzcourse.inc's
; rows), every one the CGA's.  Fetched by bz_launch on the desktop (op_fetch,
; 1942's pattern) and dropped when the bracket returns.
OS88_PARTS_BEGIN 3 + BZ_NCRS + 1 + BZS_NSONG
    OS88_PART OP_ASSET, OP_LAZY | OP_COMP   ; 0  BZBALR.BIN  rubber
    OS88_PART OP_ASSET, OP_LAZY | OP_COMP   ; 1  BZBALS.BIN  steel
    OS88_PART OP_ASSET, OP_LAZY | OP_COMP   ; 2  BZBALG.BIN  glass
    BZ_CRS_PARTS                            ; 3 + K: BZ<K>.BIN
    OS88_PART OP_ASSET, OP_LAZY | OP_COMP   ; BZ_P_SND: BZSND.BIN (128.20.3)
 %rep BZS_NSONG
    OS88_PART OP_ASSET, OP_LAZY | OP_COMP   ; BZ_P_SONG + S: BZM<S>.BIN
 %endrep
OS88_PARTS_END

%define OS88UI_ABOUT
%define OS88UI_NOBTN
%include "os88ui.inc"
%include "os88alt.inc"

%assign BZ_BSS OP_BSS           ; the parts standard's bss comes first
%macro VAR 2
 %1 equ os88_image_end + BZ_BSS
 %assign BZ_BSS BZ_BSS + %2
%endmacro
; the desktop side
VAR bz_win,2
VAR bz_abon,1
VAR bz_small,1                  ; 1 = kern_small (no timer slot): refused
VAR bz_pc,1                     ; the course's part row (BZ_P_CRS + K)
VAR bz_pb,1                     ; ...and the ball's (BZ_P_BALR + [bz_mat])
VAR bz_crsel,1                  ; the course Enter plays (N): FIRST, TRIAL, ...
VAR bz_matsel,1                 ; the ball a play rolls (M; N sets the course's)
VAR bz_mat,1                    ; THIS launch's material, 0 rubber, 1 steel,
                                ; 2 glass (bz_launch; bz_pinit copies its
                                ; BZ_MATTAB record, SPEC.md 128.11.5.2)
VAR bz_dkk,1                    ; the held-key guard: the make code of the C, M
                                ; or N not yet seen up, 0 none (128.11.11.2)
VAR bz_fw,2                     ; the face: content width, height, origin
VAR bz_fh,2
VAR bz_ox,2
VAR bz_oy,2
VAR bz_fcells,2
VAR bz_fy,2
VAR bz_lbuf,BZ_LMAX + 2
; the engine's (bzgame.inc's head documents the ones a harness reads)
BZ_GAME_VARS
BZ_PHYS_VARS
BZ_SND_VARS
VAR bz_rlog,BZR_SIZE                ; THE REPLAY LOG (SPEC.md 128.11.12.1): `BZR1`,
                                ; the course (+4), the material (+5), flags,
                                ; the steps, the runs.  The recorder writes
                                ; it; R replays it (bz_rhave)
OS88_BSS BZ_BSS
OS88_IMAGE_END
