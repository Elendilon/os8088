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
; 128.6, 128.14.3): the title, the keys, the adapter line, the held log's
; line, the tour's SCORECARD, and after a benchmark the RESULTS page - and the
; game's books: the tour, the best times and BONANZA.DAT (128.14.21).  bzvideo.inc is the bracket, the mode, the retrace wait, the ring
; writers and the boxes (128.2, 128.4); bzgame.inc is the frame loop, the
; simulation, the camera, the autopilot and the instruments (128.4 - 128.6).
; Nothing here is a reference game's: the ball is tools/bonanza_assets.py's
; (128.3) and the courses are text compiled by tools/bbcourse.py (128.10.4),
; generated into build/bonanza-art/ and carried as 3 + BZ_NCRS PARTS: three
; balls and one part a course, every one the CGA's (SPEC.md 128.11.3.1).
%include "os88api.inc"
OS88_HEADER 'BONANZA', bz_entry, OS88_F_ICON | OS88_F_ASSOC | OS88_F_GLYPH | OS88_F_PARTS, OS88_STACK_256 | OS88_HIGH | OS88_HIGHMEM
OS88_ICON16
    dw 0x07e0,0x1ff8,0x3ffc,0x7ffe,0x7ffe,0xffff,0xffff,0xffff
    dw 0xffff,0xffff,0xffff,0x7ffe,0x7ffe,0x3ffc,0x1ff8,0x07e0
    dw 0x07e0,0x1818,0x2004,0x4002,0x4c02,0x8c01,0x8001,0x8061
    dw 0x8061,0x8001,0x8c03,0x4c06,0x400e,0x203c,0x1ff8,0x07e0
OS88_ICON16_END
; a recorded demo, *.BZR, is BONANZA's document (SPEC.md 128.14.7.5, 54.6): a
; double-click launches BONANZA with it, and its page wears a ball and its
; bounce (54.3.2)
OS88_ASSOC16
    db 1
    OS88_ASSOC_EXT 'BZR'
OS88_ASSOC16_END
OS88_DOCGLYPH8
    db 00000110b
    db 00001111b
    db 01001111b
    db 00000110b
    db 10000000b
    db 00100000b
    db 01010101b
    db 00000000b
OS88_DOCGLYPH8_END
; The art files are PARTS of this file (SPEC.md 128.11.3.1, 20.12), every one
; lazy and compressed: only the play's course and ball are ever read, on the
; DESKTOP before the bracket (so op_fetch's refusal toast can be drawn), the
; course's stored form is expanded in place there (bz_cexp, SPEC.md
; 128.15.4.5), the Hercules translates both in place after it (bz_hxlat), and
; both are dropped when the bracket returns (SPEC.md 128.7, 128.11.3).
%define OP_NO_LAZYOK            ; (the fetch itself asks; no pre-check is used)
%define OP_WANT_CSEG            ; op_cseg: the shell part is FAR-CALLED (SPEC.md 128.19.2)
%define OP_SAYGATE bz_fs        ; a fetch refused inside the bracket, after its
                                ; mode set, says nothing (SPEC.md 53.7, 128.19.5)
%include "os88parts.inc"
%include "bzconst.inc"          ; the ball part's layout (tools/bonanza_assets.py)
%include "bzcourse.inc"         ; the courses and their part rows (tools/bbcourse.py)
%include "bzsnd.inc"            ; the songs and the events (tools/bbmusic.py)
%include "bzshell.inc"          ; the shell part's vectors (SPEC.md 128.19.2)
%include "bzwin.inc"            ; the window's art: its sizes (the part draws it, 128.26.2)
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

; --- the course part's header (BZC2: SPEC.md 128.15.4.1, 128.10.5.2) -----------
; Byte offsets from the part's first byte; the grid's from GRIDOFF.  Nothing
; here is checked on the guest: tools/bbcourse.py checked every one of them at
; build time (SPEC.md 128.10.6.2).  BZC1's fields keep their offsets; the map
; moved from +32 to +48 behind BZC2's own (128.15.4.1).
BZC_COLS    equ 4               ; word columns: 64 or 128
BZC_BROWS   equ 6               ; block rows
BZC_NBLK    equ 8               ; N, blocks (bz_hxlat)
BZC_MAPSH   equ 10              ; 4 for 64 columns, 5 for 128
BZC_BLKOFF  equ 12              ; block 0's offset (bz_hxlat, bz_cexp)
BZC_OCCIDX  equ 14              ; OCCIDX: BROWS + 1 words, each the offset of
                                ; the block row's first occluder record
BZC_OCCREC  equ 16              ; the first record (bz_cexp's COUNTS)
BZC_MASKOFF equ 20              ; mask 0 (bz_cexp's MASKTAB)
BZC_NMASK   equ 22              ; the masks
BZC_ROWB    equ 24              ; 2 COLS: the map row's byte stride, READ by the
                                ; column writer through DS = the part (128.10.6.4)
BZC_GRID    equ 26              ; GRIDOFF
BZC_PROPOFF equ 28              ; the prop table (SPEC.md 128.12.3.1): its first
BZC_NPROP   equ 30              ; record, and the records (0: none)
BZC_RECB    equ 32              ; byte: the record's size in RAM, 4 or 8
BZC_SB      equ 33              ; signed byte: the s bias (0 when RECB is 8)
BZC_TB      equ 34              ; the top bias, signed px (0 when RECB is 8)
BZC_MTAB    equ 36              ; the mask table (0 when RECB is 8)
BZC_DIROFF  equ 38              ; the section directory (SPEC.md 128.15.4.2):
BZC_NSEC    equ 40              ; its offset and its 8-byte entries
BZ_OSROWS   equ 160             ; block rows bz_osum summarises (bz_osmake): PEAK has 135
BZC_MAP     equ 48              ; the map: COLS x BROWS words, absolute offsets
BZX_FORM    equ 1               ; (a directory entry's) byte: its stored form
BZX_OFF     equ 2               ; its RAM offset
BZX_LEN     equ 4               ; its RAM length
BZX_DLEN    equ 6               ; its STORED length, at the end of its slot
BZX_ENTB    equ 8               ; an entry's size (BZX_: not BONANZA.DAT's BZD_)
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
BZB_NSTR    equ 14              ; byte: stretch frames, 1 for rubber, else 0
%if BZ_BAL_STROFF != BZ_BAL_SHAOFF
 %error "bz_hxball translates the shatter and stretch entries as one table"
%endif
; --- the replay log's header (SPEC.md 128.11.12.1), in [bz_rlog] ---------------
BZR_CRS     equ 4               ; byte: the course K
BZR_MAT     equ 5               ; byte: the material
BZR_FLAGS   equ 6               ; byte: bit 0 COMPLETE, bit 1 TRUNCATED, bit 2
                                ; TILT (runs of three bytes, SPEC.md 128.14.8.3)
BZR_PHYS    equ 7               ; byte: the PHYSICS identity BZ_PHYSV (128.14.7.2)
BZR_STEPS   equ 8               ; DWORD: the steps recorded
BZR_NRUN    equ 12              ; word: the runs recorded
BZR_ID      equ 14              ; word: the course's identity (128.12.8)
BZR_RUNS    equ 16              ; the runs: (key byte, count 1 - 255) pairs, or
                                ; with TILT (key byte, tilt byte, count) triples
BZR_SIZE    equ 4096            ; the log, bz_rlog: at most 2,040 runs (1,360 TILT)
BZR_DONE    equ 1
BZR_TRUNC   equ 2
BZR_TILT    equ 4               ; (bzcourse.inc's BZ_RL_TILT, the tool's)
%if BZR_TILT != BZ_RL_TILT || (BZR_SIZE - BZR_RUNS) % 6
 %error "the log's TILT flag is +6 bit 2, and both run widths fill bz_rlog exactly"
%endif
BZ_P_DEMO   equ BZ_P_SONG + BZS_NSONG ; shipped demo K (1 - 6): BZ_P_DEMO + K - 1
BZ_P_SHELL  equ BZ_P_DEMO + BZ_NDEMO ; the SHELL PART, BZSHELL.BIN (SPEC.md 128.19.2)
BZ_P_PATH   equ BZ_P_SHELL + 1  ; THE PATHWAY, BZPATH.BIN (128.19.5)
BZ_P_TITLE  equ BZ_P_PATH + 1   ; THE TITLE, BZTITLE.BIN, and its demos, BZTDEMO.BIN,
BZ_P_TDEMO  equ BZ_P_PATH + 2   ; the last two rows (SPEC.md 128.23)
BZ_LIVES    equ 5               ; a new game's lives (8b.5)
; --- the game (SPEC.md 128.14.3) ------------------------------------------------
BZ_NTOUR    equ BZ_NCRS - 1     ; the TOUR: courses 1 .. BZ_NCRS - 1, in order
BZ_TOURMAX  equ BZ_NTOUR * 65534 ; a tour's total a file may hold: each under
                                ; the 65,535-step clamp (128.14.3.3)
; --- BONANZA.DAT (SPEC.md 128.14.3.3, 128.22.5): SYSTEM\APPDATA, ONE sector, in [bz_dat] -
; `BZS4` (wave 8R round 2, item 8R.14): 494 bytes laid out for BZ_CRS_MAX = 23 courses
BZD_ENT     equ 8               ; 23 entries, K 0 - 22 (BENCH's unused): +0 the
BZD_ENTB    equ 6               ; course's IDENTITY, +2 its best in STEPS (0
BZD_NENT    equ BZ_CRS_MAX      ; none), +4 that best's falls
BZD_TOUR    equ BZD_ENT + BZD_NENT * BZD_ENTB ; the tour: +0 the XOR of its courses' identities,
                                ; +2 its best total in steps, DWORD (6 bytes, no zeros)
BZD_SLOT    equ BZD_TOUR + 6    ; three game SLOTS after the bests: +0 lives, +1
BZD_SLOTB   equ 22 + 4 * BZ_CRS_MAX ; the MODE (bit 0), +2 the PAD, +3 zero,
BZD_NSLOT   equ 3               ; +4 the OPEN pads and +8 the DONE ones
BZD_FILE    equ BZD_SLOT + BZD_NSLOT * BZD_SLOTB ; (a dword each, a bit a pad), +12 the routes
BZD_SPAD    equ 2               ; OPENED and +16 TAKEN (a dword each), +20 the
BZD_SOPEN   equ 4               ; pathway's identity, +22 the exits found (a
BZD_SDONE   equ 8               ; word a course, 23 courses, +22 - +67), +68 the
BZD_SROPN   equ 12              ; best a course (steps, a word a course, 23
BZD_SRTAK   equ 16              ; courses, +68 - +113): 114 bytes a slot.
BZD_SID     equ 20
BZD_SEXIT   equ 22
BZD_SBEST   equ BZD_SEXIT + 2 * BZ_CRS_MAX
; UNDER one sector, never a WHOLE one: od_write takes its in-place arm (one
; sector, no FAT, no entry) only for a count that is not a multiple of 512
; (os88data.inc), and the slot is written at a course's ENTRY inside the
; bracket (128.19.6) - at 512 bytes every save would be a full replace
%if BZD_FILE >= 512 || BZD_SBEST + 2 * BZ_CRS_MAX != BZD_SLOTB || BZD_SID - BZD_SOPEN != 16 || BZ_NCRS > BZ_CRS_MAX
 %error "save v4 is under ONE sector, a word a course in both tables (SPEC.md 128.22.5)"
%endif
BZD_NPAD    equ BZ_PATH_NPAD    ; the pads a slot's +2 may name (128.22.3)
%if BZD_NPAD > 32
 %error "the save keeps a bit a pad in a dword (SPEC.md 128.22.5)"
%endif

bz_entry:
    push es                     ; op_load spends ES, which arrives KERNEL_SEG
    call op_load                ; SI is still the kernel's name: FIRST. Every
    pop es                      ; row is lazy, so this copies the name and
    jc .out                     ; claims nothing
    call bz_argget              ; a double-clicked document's name, copied out
                                ; while ES is still the kernel's (128.14.7.5)
    mov si, bz_tpl
    call OSAPI_WM_CREATE        ; ...and AL = the class slots this kernel
    jc .out                     ; dispatches (SPEC.md 11.104): no timer slot
    cmp al, WC_ONTIMER + 1      ; is kern_small, the 128KB machine, which
    sbb al, al                  ; refuses the bracket (SPEC.md 128.1)
    neg al
    mov [bz_small], al
    mov [bz_win], bx
    call OSAPI_FILE_HERE        ; where BONANZA.O88 was launched from (SPEC.md
    mov [bz_homedir], dx        ; 128.14.7.6): BONANZA.DAT's volume, whatever
    mov [bz_homevol], bl        ; a dialog does to the instance later
    call bz_dload               ; the best times (128.14.3.3); kern_small: none
    mov byte [bz_crsel], BZ_CRS_FIRST ; the course Enter plays, and its ball
    mov al, [bz_cballs + BZ_CRS_FIRST] ; (N and M change them, SPEC.md
    mov [bz_matsel], al         ; 128.11.5.4)
    OS88_REGION_MOVABLE
    OS88_ALTENTER_ARM
    mov ax, [bz_win]            ; THE WINDOW (SPEC.md 128.26): the Play Game
    mov bx, bz_btrec            ; button's gesture (the library takes the press
    mov dx, bz_click            ; first and chains our own click work) ...
    call os88ui_btninit
    mov bx, [bz_win]            ; ...the menus ...
    mov si, bz_menus
    call OSAPI_MENU_SET
    mov si, bz_sizes            ; ...its size on each display (it may be
    call OSAPI_WM_PREFER        ; resized at will) ...
    call bz_winmin                ; ...the least the face needs ...
    call bz_mlabels
    mov bx, [bz_win]            ; (a double-clicked .BZR is READ in W_ONWAKE,
    clc                         ; once the window is up: SPEC.md 54.10)
.out: ret

; -----------------------------------------------------------------------------
; the window's callbacks.  ES = KERNEL_SEG on entry to every one of them.
; -----------------------------------------------------------------------------
bz_paint:
    SAVE
    call bz_mlabels             ; (a bracket may have moved the slot or the log)
    call bz_bplace              ; the button's rect, before the face reads it
    call bz_face
    jc .ab
    cmp word [bz_wbn], 0        ; ...and the button, in front of the ledge
    je .ab
    mov bx, bz_btrec
    mov al, 1
    call os88ui_btn
.ab:
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
    mov byte [bz_earm], 0       ; (an armed Erase holds to the next pick or key)
    cmp byte [bz_dev], 0        ; THE WINDOW'S KEYS (SPEC.md 128.26.1): Enter,
    jne .dev                    ; Alt+Enter and F are Play Game, F5 and F6 the
    cmp ax, KEY_ALTENTER        ; replays; everything else is the harness's
    je .pg                      ; (bz_dev, 128.26.6)
    cmp al, 13
    je .pg
    mov bx, bz_rsavedk
    cmp ax, BZ_KSC_F5 << 8
    je .fk
    mov bx, bz_rloaddlg
    cmp ax, BZ_KSC_F6 << 8
    je .fk
    or al, 20h
    cmp al, 'f'
    jne .nk
.pg:
    call bz_playgame
.nk:
    jmp .out
.fk:
    call bz_dkey                ; (one press however long it is held)
    jc .nk
    call bx
    call bz_mlabels
    jmp .out
.dev:
    mov ch, [bz_xarm]           ; (wave 8c: X's first press holds only until
    mov byte [bz_xarm], 0       ; the next key, 128.19.8.3)
    mov cl, [bz_page]           ; a key on the RESULTS page is acted on as on
    mov byte [bz_page], 0       ; MAIN and returns the face to it (SPEC.md
    mov [bz_pgo], cl            ; 128.14.3.2): repainted whole at .done
%if BZ_PATH_NPAD
    cmp ax, KEY_ALTENTER
    je .game
    cmp al, 13
    je .game
%else
    cmp ax, KEY_ALTENTER
    je .play
    cmp al, 13
    je .play
%endif
    cmp al, 27
    je .esc
    or al, 20h
    cmp al, 'f'
    je .play
    call bz_intour              ; A TOUR withholds every key that would replace
    jc .tour                    ; its state or its log (128.14.3.4)
%if BZ_PATH_NPAD
    cmp al, '1'                 ; wave 8c (128.19.8.3): 1 2 3 the SLOT, E its
    jb .ns                      ; MODE, X twice ERASES it
    cmp al, '3'
    ja .ns
    sub al, '1'
    mov [bz_slot], al
    jmp short .slotl
.ns:
    cmp al, 'e'
    jne .nx
    call bz_dslot
    xor byte [si + 1], 1
    jmp short .slotw
.nx:
    cmp al, 'x'
    jne .nslot
    or ch, ch
    jnz .erase
    mov byte [bz_xarm], 1
    jmp short .slotl
.erase:
    call bz_dslot
    mov di, si
    push es
    push ds
    pop es
    mov cx, BZD_SLOTB / 2
    xor ax, ax
    rep stosw
    pop es
.slotw:
    mov byte [bz_gsave], 1      ; the slot to BONANZA.DAT (the merge keeps the
    call bz_home                ; others; at home, as every file is)
    jc .slotl
    call bz_dsave
    call bz_back
.slotl:
    mov si, bz_slotl
    call bz_redraw
    jmp .done
.nslot:
%endif
    mov bx, bz_game
    cmp al, 'g'
    je .held
    cmp al, 'b'
    je .bench
    cmp al, 'r'
    je .replay
    mov bx, bz_ballkey          ; C, M, N, G, D, L, V, W, T: one press however
    cmp al, 'm'                 ; long it is held (SPEC.md 128.11.11.2,
    je .held                    ; 128.14.3.4)
    mov bx, bz_crskey
    cmp al, 'n'
    je .held
    mov bx, bz_dkey_d           ; D: the demo benchmark (128.14.7.3)
    cmp al, 'd'
    je .held
    mov bx, bz_lkey             ; L: load a demo (128.14.7.2)
    cmp al, 'l'
    je .held
    mov bx, bz_vkey             ; V: the next shipped demo (128.14.7.4)
    cmp al, 'v'
    je .held
.tour:
    mov bx, bz_camkey
    cmp al, 'c'
    je .held
    mov bx, bz_wkey             ; W: save the held log (128.14.7.1)
    cmp al, 'w'
    je .held
    mov bx, bz_tkey             ; T: the control, KEYS or MOUSE (128.14.8)
    cmp al, 't'
    je .held
    mov bx, bz_skey             ; S: the sound (SPEC.md 128.20.4), at home
    cmp al, 's'
    jne .done
.held:
    call bz_dkey                ; AH = the make code: CF = 1 a repeat, swallowed
    jc .done
    call bx
    jmp short .done
.esc:
    call bz_intour              ; Esc on the face between two tour courses
    jnc .done                   ; STOPS the tour (otherwise nothing, as before)
    mov byte [bz_tour], BZ_NTOUR + 2
    mov si, bz_stopl
    call bz_redraw
    jmp short .done
.replay:
    call bz_rhave               ; R: offered only when there is a log
    jne .done                   ; (SPEC.md 128.11.12.2): its course, and
    mov ah, [bz_rlog + BZR_CRS] ; bz_launch takes its ball
    mov al, 2
    jmp short .go
.bench:
    mov ax, 1 | (BZ_CRS_BENCH << 8) ; B: the benchmark, on BENCH (SPEC.md
    jmp short .go               ; 128.10.11.1)
.play:
    call bz_intour              ; Enter, F, Alt+Enter: in a tour its next
    jnc .free                   ; course
    call bz_tgo
    jmp short .done
%if BZ_PATH_NPAD
.game:                          ; Enter, Alt+Enter: THE GAME (wave 8b,
    call bz_intour              ; 128.19.5) - in a tour, its next course
    jc .play
%if BZ_TITLE
    call bz_playgame            ; (SPEC.md 128.23.4: the TITLE, P its game;
%else                           ; 128.26.4: or where the window was asked for)
    call bz_game8
%endif
    jmp short .done
%endif
.free:
    mov al, 0                   ; ...otherwise play the selected course
    mov ah, [bz_crsel]          ; freely (SPEC.md 128.11.11.3)
.go:
    call bz_go
.done:
    cmp byte [bz_pgo], 0        ; leaving RESULTS: MAIN whole, unless a bracket
    je .out                     ; ran (the kernel's restore painted it)
    mov byte [bz_pgo], 0
    call bz_repaint
.out:
    RESTORE
    ret

; G (one press, bz_dkey): a NEW TOUR (SPEC.md 128.14.3.1) - its times cleared
; and course 1 launched.  On kern_small nothing changes: bz_launch toasts the
; refusal (128.1).
bz_game:
    cmp byte [bz_small], 0
    jne bz_tgo
    xor ax, ax
    mov bx, bz_ttime
.z:
    mov [bx], ax
    inc bx
    inc bx
    cmp bx, bz_tfall + 2 * BZ_NTOUR
    jb .z
    mov byte [bz_tour], 1
    call bz_tgo
    cmp byte [bz_tour], 1       ; still course 1: its launch was REFUSED (a
    jne .ran                    ; course that ran moved the tour on, or Esc
    mov si, bz_stopl            ; stopped it), so no bracket repainted the face
    jmp bz_redraw               ; and the tour's lines are drawn here
.ran:
    ret
; the tour's next course, played with its own ball (bz_launch); a refused
; launch leaves the tour where it was, so Enter tries it again
bz_tgo:
    mov ah, [bz_tour]
    mov al, 0
; AL = the mode, AH = the course: launched, and a best it set saved
bz_go:
    mov [bz_mode], al
    mov [bz_crs], ah
    call bz_launch
    jmp bz_dsave

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
; In: [bz_mode] (0 play, 1 benchmark, 2 replay, 3 the demo benchmark: a
; replay, measured, SPEC.md 128.14.7.3) and [bz_crs].  The MATERIAL is
; chosen here (SPEC.md 128.11.5.4): a play rolls the session's ball
; ([bz_matsel], M), a benchmark the course's own (BENCH's for B; the course a
; harness poked at this entry otherwise), a replay the log's.  Course K's part
; (row BZ_P_CRS + K) and the material's (BZ_P_BALR + [bz_mat]) are fetched -
; the same rows on both cards - the course's expanded in place at once
; (bz_cexp, SPEC.md 128.15.4.5), and on the Hercules both are translated in
; place (bz_hgen, bz_hxlat, SPEC.md 128.11.3); the bracket runs, and both are
; dropped on every way out.  Every fetch here - the course's, the balls', the
; sound's song and the title's after the bracket - is made at HOME (bz_home,
; SPEC.md 128.14.7.6), and the instance goes back where the user was after.
; -----------------------------------------------------------------------------
bz_launch:
    call bz_unsusp              ; (a suspended game's course given up first:
                                ; this launch's parts take its place, 128.26.3)
    mov byte [bz_towin], 0
    mov byte [bz_newb], 0       ; (only this launch's play may set a best)
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
    jns .nplay
    call bz_intour              ; 0: a play, M's - but a TOUR's course rolls
    jnc .mat                    ; its own (SPEC.md 128.14.3.1)
    jmp short .own
.nplay:
    mov al, [bz_rlog + BZR_MAT]
    jnz .mat                    ; 2, 3: a replay, the log's
.own:
    mov bl, [bz_crs]            ; 1: a benchmark, the course's own
    xor bh, bh
    mov al, [bz_cballs + bx]
.mat:
    mov [bz_mat], al
    call bz_shdrop              ; the shell part never shares memory with a
                                ; course (SPEC.md 128.19.2)
    call bz_home                ; every part is read out of BONANZA.O88 at home
    jc .ret                     ; (its refusal toasted: no fetch at all)
    call .home
    jmp bz_back
.ret:
    ret
.home:
    call bz_cload               ; the course, its balls and its song (CF: a
    jc .drop                    ; refusal, its toast said why)
    cmp byte [bz_mode], 2       ; a REPLAY (R or D) of a log made on another
    jb .idok                    ; course (a re-seeded one: its identity
    push es                     ; differs) is refused, and the face says so
    mov es, [bz_cseg]           ; (SPEC.md 128.12.8) - and one made under
    mov di, [bz_goff]           ; other PHYSICS (+7, 128.14.7.2)
    mov ax, [es:di + BZG_ID]
    pop es
    mov byte [bz_err], 3
    cmp ax, [bz_rlog + BZR_ID]
    jne .drop
    inc byte [bz_err]
    cmp byte [bz_rlog + BZR_PHYS], BZ_PHYSV
    jne .drop
.idok:
    mov byte [bz_err], 0
    mov bx, [bz_win]
    mov ax, bz_fullscreen
    mov cx, FSXF_FASTTICK
    call OSAPI_FSX_RUN
    jc .nofs
    mov byte [bz_pgo], 0        ; the kernel's restore painted the face whole
    jmp short .drop
.nofs:
    mov si, bz_t_nofs
    call bz_toast
.drop:
    call bz_cdrop               ; every part this launch fetched given back
    call bzs_gdrop              ; the song back, and the title (a finish's
    cmp byte [bz_shpend], 0     ; fanfare first, SPEC.md 128.20.6).  The
    je .nopend                  ; restore's paint was put off while the course
    mov byte [bz_shpend], 0     ; was held (bz_shcall): made now, the course
    mov byte [bz_pgo], 0        ; gone and the shell part fetched again
    call bz_repaint             ; (SPEC.md 128.19.2)
.nopend:
    cmp byte [bz_err], 3        ; no bracket
    jb .out                     ; ran: the face repainted with the refusal (3
    mov byte [bz_pgo], 1        ; or 4), by bz_onkey (once, whatever page it
.out:                           ; was on)
    ret

; -----------------------------------------------------------------------------
; bz_cload - course [bz_crs]'s part fetched for the ball [bz_mat] (SPEC.md
; 128.14.4.4): its row - BZ_P_CRS + K, or BZ_P_PATH for the pathway (wave 8b,
; 128.19.5) - expanded in place once (bz_cexp, 128.15.4.5), every ball it can
; need, its song (bzs_gfetch), its header copied (bz_crshdr) and, on the
; Hercules, translated (bz_hgen, bz_hxlat, 128.11.3).  CF = 1 a fetch was
; refused (op_fetch said why - or, inside the game's bracket, OP_SAYGATE
; held it quiet): what was fetched is bz_cdrop's to give back.  At home.
; Preserves nothing.
; -----------------------------------------------------------------------------
bz_cload:
    mov al, [bz_crs]            ; course K's row: BZ_P_CRS + K (bzcourse.inc)
    add al, BZ_P_CRS
%if BZ_PATH_NPAD
    cmp byte [bz_crs], BZ_CRS_PATH ; ...the pathway's its own (128.19.5)
    jne .row
    mov al, BZ_P_PATH
.row:
%endif
%if BZ_TITLE
    cmp byte [bz_crs], BZ_CRS_TITLE ; ...and the title's (128.23)
    jne .rowt
    mov al, BZ_P_TITLE
.rowt:
%endif
    mov [bz_pc], al
%if BZ_PATH_NPAD
    mov byte [bz_phre], 0       ; the pathway HELD (128.22.7): its part is here,
    cmp al, BZ_P_PATH           ; expanded and translated already - no fetch,
    jne .nh                     ; no expand, no translation of the part
    mov al, [bz_phold]
    mov [bz_phre], al
    mov al, BZ_P_PATH
.nh:
%endif
    call op_fetch               ; claim, read, expand - or a toast said why
    jc .out                     ; (a held row: nothing to do, CF = 0)
    mov al, [bz_pc]             ; (each fetch's segment stored before the next
    call op_seg                 ; fetch, so tests/pins.txt keys each claim by
    mov [bz_cseg], ax           ; its own word: bz_cseg, bz_bsegs)
%if BZ_PATH_NPAD
    cmp byte [bz_phre], 0
    jne .exd
    cmp byte [bz_pc], BZ_P_PATH ; a pathway fetched now is HELD while it is
    jne .ex                     ; here (bz_phrel, bz_phfree let it go) - unless
    cmp byte [bz_phforce], 0    ; the harness forces the drop-and-refetch way
    jne .ex
    mov byte [bz_phold], 1
.ex:
%endif
    call bz_cexp                ; the STORED form expanded in place, ONCE: this
                                ; fetch decoded, every exit below dropping the
                                ; part (SPEC.md 128.15.4.5)
%if BZ_PATH_NPAD
.exd:
%endif
    push es                     ; THE BALLS (wave 4, SPEC.md 128.14.4.4): the
    mov es, [bz_cseg]           ; starting one and every one the course's
    mov di, [es:BZC_GRID]       ; PAD MASK names (BZG1 +29), up to three, each
    mov ah, [es:di + BZG_PADS]  ; its own claim - and every FLAG's own ball,
    mov si, [es:BZC_PROPOFF]    ; which a respawn there gets (bz_rflag) whether
    mov dx, [es:BZC_NPROP]      ; or not a pad gives it
.fb:
    dec dx
    js .fb2
    cmp byte [es:si + BZP_KIND], BZ_PK_CKPT
    jne .fb1
    mov cl, [es:si + BZP_CBALL]
    mov al, 1
    shl al, cl
    or ah, al
.fb1:
    add si, BZ_PROPREC
    jmp short .fb
.fb2:
    pop es
    mov cl, [bz_mat]
    mov al, 1
    shl al, cl
    or ah, al
    mov [bz_pbm], ah
    mov byte [bz_pb], BZ_P_BALR
.ball:
    mov cl, [bz_pb]
    sub cl, BZ_P_BALR
    mov al, 1
    shl al, cl
    test al, [bz_pbm]
    jz .nball
    mov al, [bz_pb]
    call op_fetch
    jc .drop
    mov al, [bz_pb]
    call op_seg
    mov bl, [bz_pb]
    sub bl, BZ_P_BALR
    xor bh, bh
    shl bx, 1
    mov [bz_bsegs + bx], ax
.nball:
    inc byte [bz_pb]
    cmp byte [bz_pb], BZ_P_BALR + BZ_NMAT
    jb .ball
    mov bl, [bz_mat]            ; the sprite's: the starting ball's (a pad or
    xor bh, bh                  ; a flag's respawn changes it, bz_setmat)
    lea ax, [bx + BZ_P_BALR]
    mov [bz_pb], al
    shl bx, 1
    mov ax, [bz_bsegs + bx]
    mov [bz_bseg], ax
    push es                     ; the title off, the course's song fetched
    call bzs_gfetch             ; (none had: a SILENT play, SPEC.md 128.20.6)
    pop es
    call bz_crshdr              ; the course's header, copied into our data
    cmp byte [bz_herc], 0       ; the Hercules's parts are the CGA's through
    je .ok                      ; BZ_HTAB, made here (SPEC.md 128.11.3)
    push es                     ; (ES as the bracket call found it before:
    call bz_hgen                ; bz_hxlat leaves the ball's there)
    call bz_hxlat
    pop es
.ok:
    clc
.out:
    ret
.drop:
    stc
    ret

%if BZ_PATH_NPAD
; the pathway's part, HELD (128.22.7): bz_phrel's test is the heap's largest
; claim against the largest course's, bzcourse.inc's BZ_CRS_MAXCLAIM (the
; tool's, 128.22.3): a pad's course's part, balls, song and sound part, each
; its RAM form plus op_lazyp's cluster slack (a compressed row claims R and
; the read of its packed bytes in whole clusters)
%if BZ_TITLE == 0
; -----------------------------------------------------------------------------
; bz_game8 - THE GAME (wave 8b, SPEC.md 128.19.5): Enter on the face - a build
; with no TITLE's only (the title's P plays it, bz_tround).  Its refusals are
; bz_launch's (kern_small, the adapter); a game with no lives left is a NEW
; one (5 lives, pad 0 open, nothing done), else it goes on where it was.  The pathway is fetched here at home, on the desktop, and the bracket
; (bz_fullscreen, [bz_ingame] 1) plays the rounds; whatever is held when it
; ends is given back, and a best a course set is written (bz_dsave).
; -----------------------------------------------------------------------------
bz_game8:
    mov byte [bz_newb], 0
    cmp byte [bz_small], 0
    je .big
    mov si, bz_t_small
    jmp bz_toast
.big:
    call bz_adapter
    or al, al
    jnz .ok
    mov si, bz_t_adapt
    jmp bz_toast
.ok:
    dec al
    mov [bz_herc], al
    call bz_gslot
    call bz_shdrop              ; (never beside a course, 128.19.2)
    call bz_home
    jc .ret
    call bz_gpath               ; the pathway's part, its ball and song
    jc .drop
    mov byte [bz_ingame], 1
    mov byte [bz_err], 0
    mov bx, [bz_win]
    mov ax, bz_fullscreen
    mov cx, FSXF_FASTTICK
    call OSAPI_FSX_RUN
    mov byte [bz_ingame], 0
    mov byte [bz_xmode], 0      ; (no other play explores)
    jnc .ran
    mov si, bz_t_nofs
    call bz_toast
.ran:
    mov byte [bz_pgo], 0
.drop:
    call bz_phfree              ; (the held pathway goes with the game, 128.22.7)
    call bz_cdrop
    call bzs_gdrop              ; (the title back)
    call bz_back
    cmp byte [bz_shpend], 0
    je .sv
    mov byte [bz_shpend], 0
    call bz_repaint
.sv:
    call bz_gstore              ; the game into its slot, and the slot and a
    mov byte [bz_gsave], 1      ; best a course set to BONANZA.DAT
    jmp bz_dsave

.ret:
    ret
%endif

; bz_gslot - THE SLOT's game (save v3, 128.22.5) into memory: its game when
; it has lives, else a NEW one in it; the pad, the pads open and done, the
; routes; its MODE; no event pending (bz_pwev).  Preserves all but AX and SI.
bz_gslot:
    call bz_dslot               ; THE SLOT (save v3, 128.22.5): its game when
    mov al, [si]                ; it has lives ...
    or al, al
    jnz .on
    mov al, BZ_LIVES            ; ...else a NEW one in it
    call bz_gnew
.on:
    mov [bz_lives], al
    call bz_gload               ; the pad, the pads open and done, the routes
    mov al, [si + 1]            ; the MODE (8c, 128.19.8.3): EXPLORE rests
    and al, 1                   ; on any pad (bz_proute)
    mov [bz_xmode], al
    mov byte [bz_pwev], 0
    ret

; bz_gstore - the game's state into the slot played (128.22.5): AL lives
; (bz_gstorl: AL given), the pad, the open and done pads and the routes
; (bz_nopen ... bz_nrtk, 16 bytes, the slot's order), the pathway's identity.
; Preserves all but AX and SI.
bz_gstore:
    mov al, [bz_lives]
bz_gstorl:
    call bz_dslot
    mov [si], al
    mov al, [bz_ppad]
    mov [si + BZD_SPAD], al
    mov ax, [bz_cids + 2 * BZ_CRS_PATH]
    mov [si + BZD_SID], ax
    push cx
    push di
    push es
    push ds
    pop es
    lea di, [si + BZD_SOPEN]
    mov si, bz_nopen
    mov cx, (BZD_SID - BZD_SOPEN) / 2
    rep movsw
    pop es
    pop di
    pop cx
    ret

; bz_gload - the slot's pad and its 16 bytes of pads and routes into
; bz_ppad, bz_nopen ... bz_nrtk.  SI = the slot on the way in (bz_dslot) and
; on the way out.  Preserves all but AX.
bz_gload:
    mov al, [si + BZD_SPAD]
    mov [bz_ppad], al
    push cx
    push si
    push di
    push es
    push ds
    pop es
    add si, BZD_SOPEN
    mov di, bz_nopen
    mov cx, (BZD_SID - BZD_SOPEN) / 2
    rep movsw
    pop es
    pop di
    pop si
    pop cx
    ret

; bz_gnew - a NEW game in the slot at SI: AL lives, pad 0 resting, pad 0
; open, nothing done, no route opened or taken.  Its exits found and its bests
; stay (an empty slot keeps them).  Preserves all but the flags.
bz_gnew:
    push ax
    push cx
    push di
    push es
    push ds
    pop es
    mov [si], al
    mov byte [si + BZD_SPAD], 0
    lea di, [si + BZD_SOPEN]
    xor ax, ax
    mov cx, (BZD_SID - BZD_SOPEN) / 2
    rep stosw
    mov byte [si + BZD_SOPEN], 1
    pop es
    pop di
    pop cx
    pop ax
    ret

; the pads and routes' DWORD BITS (a bit a pad or a route, 0 - 31): AL = the
; bit, SI = the dword's address (DS).  bz_dwbit -> AL the mask, BX the byte
; (clobbers CX); bz_dwset sets the bit, bz_dwtst tests it (ZF = 0 set).
; Preserves all else.  The pathway's loop calls these on bz_nopen, bz_ndone,
; bz_nrop and bz_nrtk.
bz_dwbit:
    mov cl, al
    and cl, 7
    shr al, 1
    shr al, 1
    shr al, 1
    xor ah, ah
    mov bx, ax
    mov al, 1
    shl al, cl
    ret
bz_dwset:
    push ax
    push bx
    push cx
    call bz_dwbit
    or [si + bx], al
    pop cx
    pop bx
    pop ax
    ret
bz_dwtst:
    push ax
    push bx
    push cx
    call bz_dwbit
    test [si + bx], al
    pop cx
    pop bx
    pop ax
    ret

; =============================================================================
; THE PATHWAY (wave 8R, SPEC.md 128.22.4): its tables (the part's, at BZC2
; +42, 128.22.3, read through bz_ptho / bz_ptro / bz_ptko), the signs' poses,
; the FOLLOWER (bz_mode 4, bz_follow) and the rounds (bz_grounds).
; =============================================================================
BZ_PW_REST  equ 0               ; bz_pwst: RESTING on bz_ppad
BZ_PW_ROLL  equ 1               ; ...ROLLING route bz_pwrt (the follower)
BZ_PW_GATE  equ 2               ; ...a GATE opening (poses 1 - 5), then the roll
BZ_PW_OVER  equ 3               ; ...the GAME OVER effect sounding, then its card
BZ_PE_FIN   equ 1               ; bz_pwev: the course FINISHED, by exit bz_pwex
BZ_PE_LIFE  equ 2               ; ...a life lost (a timeout, an Esc, a retry)
BZ_PE_OVER  equ 3               ; ...the last one
BZ_PW_GSTEP equ 6               ; steps a gate pose: 1 - 5, the roll after 30 (0.55 s)
BZ_PW_OSTEP equ 96              ; the GAME OVER effect's steps (82 sub-ticks) before its card

; bz_medal - course BL's DONE pose (8c.3, 128.19.8.3; a pad's sign, 128.22.2):
; DL = 3 GOLD (the slot's best for it at or under G), 2 SILVER (at or under
; S), 1 else.  Preserves all but DX.
bz_medal:
    push ax
    push bx
    push si
    xor bh, bh
    shl bx, 1
    call bz_dslot
    mov ax, [si + bx + BZD_SBEST]
    shl bx, 1
    mov dl, 1
    or ax, ax
    jz .o
    cmp ax, [bz_cmedals + bx + 2] ; S
    ja .o
    inc dx
    cmp ax, [bz_cmedals + bx]   ; G
    ja .o
    inc dx
.o:
    pop si
    pop bx
    pop ax
    ret

; bz_gpath - the PATHWAY entered (128.22.4.4 item 1): fetched unless HELD
; (bz_phfetch), the follower's mode, its tables read and every sign posed
; from the slot (bz_ppose).  CF = 1 refused.  Preserves nothing.
bz_gpath:
    call bz_phfetch
    jc .out
    mov byte [bz_mode], 4
    call bz_ppose
    clc
.out:
    ret

; bz_ppose - the pathway's tables' offsets (bz_ptho the tables, bz_ptro the
; ROUTES, bz_ptko the KEYS) and every SIGN's pose from the slot, into bz_nst
; directly (bz_play's bz_pread then marks every lane): a pad's and its icon's
; (bz_ppad1), a gate's 5 if its route is open (bz_proute: EXPLORE's every route
; that is not secret) else 0, a reveal group's 1 if its route was TAKEN else 0.
; [bz_cseg] the pathway.  Preserves nothing.
bz_ppose:
    push es
    mov es, [bz_cseg]
    mov di, [es:BZC_PTHOFF]
    mov [bz_ptho], di
    mov al, [es:di]             ; npad PADS of 10 bytes from +4 ...
    mov ah, BZ_PTH_PADREC
    mul ah
    add ax, di
    add ax, 4
    mov [bz_ptro], ax
    mov si, ax
    mov al, [es:di + 1]         ; ...then nroute ROUTES of 8, then the KEYS
    mov ah, BZ_PTH_ROUTEREC
    mul ah
    add ax, si
    mov [bz_ptko], ax
    xor cx, cx                  ; CL = the pad
.pad:
    cmp cl, [es:di]
    jae .rts
    mov al, cl
    call bz_ppad1               ; DL its sign's pose, DH its icon's, SI its record
    mov bl, [es:si + 1]
    xor bh, bh
    mov [bz_nst + bx], dl
    mov bl, [es:si + 2]
    cmp bl, 0ffh
    je .ni
    mov [bz_nst + bx], dh
.ni:
    inc cx
    jmp short .pad
.rts:
    xor cx, cx                  ; CL = the route
.rt:
    cmp cl, [es:di + 1]
    jae .out
    mov al, cl
    call bz_proute              ; SI = its record; ZF = 0 open
    mov dl, 0
    jz .g
    mov dl, BZ_GATE_POSES - 1
.g:
    mov bl, [es:si + 4]         ; its gate (FFh: a secret route has none)
    cmp bl, 0ffh
    je .ng
    xor bh, bh
    mov [bz_nst + bx], dl
.ng:
    push si
    mov si, bz_nrtk
    call bz_dwtst               ; ZF = 0 TAKEN
    pop si
    mov dl, 0
    jz .rv
    inc dx
.rv:
    xor ah, ah
    call bz_preveal             ; (direct)
    inc cx
    jmp short .rt
.out:
    pop es
    ret

; bz_ppadr - pad AL's record (ES = the pathway) -> SI.  Preserves all else.
bz_ppadr:
    push ax
    mov ah, BZ_PTH_PADREC
    mul ah
    add ax, [bz_ptho]
    add ax, 4
    xchg ax, si
    pop ax
    ret

; bz_ppad1 - pad AL's poses from the slot (ES = the pathway) -> SI its record,
; DL its sign's: 0 OPEN, 1 + the medal once DONE (bz_medal); a HIDDEN pad's
; 0 (the bare picture) until a secret route at it is TAKEN (bz_psecr), then
; 1 + that; the VISIBLE END of a secret route's + 4 once it is taken (the
; route drawn in its lane) - and DH its icon's rest pose: 0, or 1 on a hidden
; pad shown (its icon's poses one more, 128.22.3).  Preserves all else.
bz_ppad1:
    push ax
    push bx
    call bz_ppadr
    xor dx, dx
    push si
    mov si, bz_ndone
    call bz_dwtst
    pop si
    jz .nd
    mov bl, [es:si]             ; its course: the medal
    call bz_medal
.nd:
    mov ah, [es:si + 3]
    test ah, 0c0h               ; hidden, or the visible end of a secret route
    jz .o
    call bz_psecr               ; ZF = 0: a secret route at pad AL TAKEN
    jz .nt
    test ah, 80h
    jz .ve
    inc dx                      ; HIDDEN, shown: 1 + p, its icon 1 + its frame
    inc dh
    jmp short .o
.ve:
    add dl, 4                   ; the VISIBLE END: 4 + p
    jmp short .o
.nt:
    test ah, 80h                ; hidden, not found: the bare picture
    jz .o
    xor dl, dl
.o:
    pop bx
    pop ax
    ret

; bz_psecr - ZF = 0 when a SECRET route with pad AL at either end is TAKEN
; (bz_nrtk).  ES = the pathway.  Preserves all.
bz_psecr:
    push bx
    push cx
    push si
    mov bx, [bz_ptho]
    mov si, [bz_ptro]
    xor cx, cx
.r:
    cmp cl, [es:bx + 1]
    jae .no
    test byte [es:si + 3], 1
    jz .n
    cmp [es:si], al
    je .y
    cmp [es:si + 1], al
    jne .n
.y:
    push ax
    push si
    mov al, cl
    mov si, bz_nrtk
    call bz_dwtst
    pop si
    pop ax
    jnz .out
.n:
    add si, BZ_PTH_ROUTEREC
    inc cx
    jmp short .r
.no:
    cmp al, al                  ; ZF = 1
.out:
    pop si
    pop cx
    pop bx
    ret

; bz_proute - route AL's record (ES = the pathway) -> SI, and ZF = 0 when it
; is OPEN (bz_nrop) - or, in EXPLORE, not secret (exploration rests on any
; pad: every gate is open but a secret one's, which only its exit opens).
; Preserves all else.
bz_proute:
    push ax
    push bx
    mov bl, al
    mov ah, BZ_PTH_ROUTEREC
    mul ah
    add ax, [bz_ptro]
    xchg ax, si
    mov al, bl
    push si
    mov si, bz_nrop
    call bz_dwtst
    pop si
    jnz .out
    cmp byte [bz_xmode], 0
    je .out                     ; (ZF = 1: closed)
    mov al, [es:si + 3]
    and al, 1
    xor al, 1                   ; ZF = 0: not secret
.out:
    pop bx
    pop ax
    ret

; bz_preveal - route SI's REVEAL groups (ES = the pathway) all to pose DL: AH =
; 0 into bz_nst directly, else through bz_nset (marked).  Preserves all.
bz_preveal:
    push ax
    push bx
    push cx
    push di
    mov bl, [es:si + 5]         ; the first group's sign (FFh none: the groups'
    cmp bl, 0ffh                ; signs are consecutive)
    je .out
    xor bh, bh
    mov di, [bz_ptho]
    add di, [es:si + 6]
    mov cl, [es:di + 1]         ; (POINTS +1: the groups)
    xor ch, ch
    jcxz .out
.g:
    mov al, dl
    or ah, ah
    jz .d
    call bz_nset
    jmp short .n
.d:
    mov [bz_nst + bx], al
.n:
    inc bx
    loop .g
.out:
    pop di
    pop cx
    pop bx
    pop ax
    ret

; bz_pnset - pad AL's sign and icon to their poses (bz_ppad1), marked
; (bz_nset).  ES = the pathway.  Preserves all but DX.
bz_pnset:
    push ax
    push bx
    push si
    call bz_ppad1
    mov al, dl
    mov bl, [es:si + 1]
    call bz_nset
    mov bl, [es:si + 2]
    cmp bl, 0ffh
    je .o
    mov al, dh
    call bz_nset
.o:
    pop si
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; bz_pwinit - the PATHWAY's play begins (bz_play, bz_mode 4, after bz_pinit):
; the marble on bz_ppad's cell (bz_placeat: its centre on its floor,
; grounded) and the event the last course left (bz_pwev, 128.22.4.4 item 1):
; a LIFE lost - its sound; the GAME OVER - its sound, waited for (BZ_PW_OVER),
; then the card; a FINISH by exit bz_pwex - route (pad, exit) OPENED if it was
; closed (TIMED: EXPLORE unlocks nothing), its gate then playing 1 - 5 with
; the GATE sound (BZ_PW_GATE), and the marble AUTO-ROLLS it; else it RESTS.
; The arrows, Enter, Esc and Space held from the course are no press
; (bz_pwek).  The lanes are not read yet (bz_pread follows): poses go into
; bz_nst.  [bz_cseg] the pathway, bz_ppose run.  Preserves nothing.
; -----------------------------------------------------------------------------
bz_pwinit:
    xor ax, ax
    mov [bz_pwq], al
    mov [bz_pwng], al
    mov byte [bz_pwek], 0ffh
    mov byte [bz_pwis], 0ffh
    mov es, [bz_cseg]
    mov al, [bz_ppad]           ; (the slot's pad: bz_dslots judged it one of
    mov si, [bz_ptho]           ; the pathway's; kept in range here all the same)
    cmp al, [es:si]
    jb .pad
    xor al, al
    mov [bz_ppad], al
.pad:
    call bz_ppadr
    mov ax, [es:si + 4]         ; its cell: (gx >> 4, gy >> 4)
    mov dx, [es:si + 6]
    mov cl, 4
    shr ax, cl
    shr dx, cl
    mov ah, dl
    call bz_placeat
    call bz_derive
    call bz_derive              ; (twice: no velocity)
    xor ax, ax
    mov [bz_vx], ax
    mov [bz_vy], ax
    mov es, [bz_cseg]
    xor al, al
    xchg al, [bz_pwev]
    cmp al, BZ_PE_LIFE
    je .life
    cmp al, BZ_PE_OVER
    je .over
    cmp al, BZ_PE_FIN
    jne bz_pwrest
    mov bx, [bz_ptho]           ; A FINISH: the route keyed by (pad, exit)
    mov si, [bz_ptro]
    xor cx, cx
.f:
    cmp cl, [es:bx + 1]
    jae bz_pwrest               ; (none: the pad's course has no route there)
    mov al, [es:si]
    cmp al, [bz_ppad]
    jne .fn
    mov al, [es:si + 2]
    cmp al, [bz_pwex]
    je .fr
.fn:
    add si, BZ_PTH_ROUTEREC
    inc cx
    jmp short .f
.fr:
    mov al, cl
    call bz_proute              ; ZF = 0 open already: it rolls
    jnz .roll
    cmp byte [bz_xmode], 0      ; (EXPLORE: a closed route stays closed)
    jne bz_pwrest
    push si
    mov si, bz_nrop
    call bz_dwset               ; OPENED (the slot's +12, 128.22.5)
    pop si
    mov bl, [es:si + 4]         ; its GATE opens first (a secret route has
    cmp bl, 0ffh                ; none: it rolls at once)
    je .roll
    mov [bz_pwrt], cl
    mov [bz_pwgs], bl
    xor bh, bh
    mov byte [bz_nst + bx], 1
    mov byte [bz_pwst], BZ_PW_GATE
    mov word [bz_pwcn], 0
    mov al, BZS_EV_GATE
    jmp bzs_ev
.roll:
    mov al, cl                  ; A to B (the pad is its A)
    xor ah, ah
    jmp bz_pwdep
.over:
    mov byte [bz_pwst], BZ_PW_OVER
    mov word [bz_pwcn], BZ_PW_OSTEP
    mov al, BZS_EV_OVER         ; (sound's: OVER while the sound is open, before
    jmp bzs_ev                  ; bz_kover, whose wait steps none)
.life:
    mov al, BZS_EV_LIFE
    call bzs_ev
; bz_pwrest - RESTING on bz_ppad (128.22.4.4 item 2): its icon's animation's
; state - the sign, its rest pose (bz_ppad1's DH), the frame 0, the interval
; (PAD +9 steps; FFh in bz_pwis: none, under two frames).  ES = the pathway.
; Preserves nothing.
bz_pwrest:
    mov byte [bz_pwst], BZ_PW_REST
    mov byte [bz_pwis], 0ffh
    mov al, [bz_ppad]
    call bz_ppad1
    mov al, [es:si + 2]
    cmp al, 0ffh
    je .out
    cmp byte [es:si + 8], 2
    jb .out
    mov ah, [es:si + 9]
    or ah, ah
    jz .out
    mov [bz_pwis], al
    mov [bz_pwib], dh
    mov byte [bz_pwic], 0
    mov [bz_pwcn], ah
.out:
    ret

; -----------------------------------------------------------------------------
; bz_pwdep - the marble DEPARTS on route AL (AH = 1 travelled B to A; ES = the
; pathway): the resting pad's icon back to its rest pose, the destination, its
; POINTS walked from the end it leaves (bz_pwp, bz_pwpd), the route's length L
; and the first segment's, s = 0 and v = 0 (128.22.4.2); a SECRET route's
; reveal groups to come (A to B: as s passes each) or all shown at once
; (B to A).  ROLLING, and the arrows must go up before the next press.
; Preserves nothing.
; -----------------------------------------------------------------------------
bz_pwdep:
    push ax
    mov bl, [bz_pwis]           ; the icon at its rest pose (frame 0)
    cmp bl, 0ffh
    je .ni
    mov al, [bz_pwib]
    call bz_nset
    mov byte [bz_pwis], 0ffh
.ni:
    pop ax
    mov [bz_pwrt], al
    mov [bz_pwrv], ah
    call bz_proute              ; SI = its record
    mov bl, [es:si + 1]         ; to B, or to A backwards
    or ah, ah
    jz .b
    mov bl, [es:si]
.b:
    mov [bz_pwdst], bl
    mov di, [bz_ptho]
    add di, [es:si + 6]         ; DI = its POINTS
    mov cl, [es:di]             ; CX = their count
    xor ch, ch
    mov byte [bz_pwng], 0
    test byte [es:si + 3], 1    ; a SECRET route's reveal groups
    jz .nr
    mov bl, [es:si + 5]
    cmp bl, 0ffh
    je .nr
    or ah, ah
    jz .fwd
    mov dl, 1                   ; (B to A: all at once; AH = 1, marked)
    call bz_preveal
    jmp short .nr
.fwd:
    mov [bz_pwrs], bl           ; (A to B: each as s passes its distance)
    mov al, [es:di + 1]
    mov [bz_pwng], al
    mov byte [bz_pwrg], 0
    mov al, 6
    mul cl
    add ax, di
    inc ax
    inc ax
    mov [bz_pwro], ax
.nr:
    mov al, 6
    mul cl
    lea bx, [di + 2]            ; BX = the first point walked, DX its step
    mov dx, 6
    cmp byte [bz_pwrv], 0
    je .fw
    add bx, ax
    sub bx, dx
    neg dx
.fw:
    mov [bz_pwp], bx
    mov [bz_pwpd], dx
    mov si, bx
    dec cx                      ; CX = the segments (at least one)
    mov al, cl
    dec ax
    mov [bz_pwnl], al           ; ...after the first
    xor bx, bx                  ; BX = L
.sum:
    call bz_pwseg
    add bx, ax
    add si, [bz_pwpd]
    loop .sum
    mov [bz_pwL], bx
    mov si, [bz_pwp]
    call bz_pwseg
    mov [bz_pwln], ax
    xor ax, ax
    mov [bz_pws], ax
    mov [bz_pws + 2], ax
    mov [bz_pwv], ax
    mov [bz_pwdk], ax
    mov byte [bz_pwst], BZ_PW_ROLL
    mov byte [bz_pwek], 0ffh    ; (a press moves one route: up first)
    ret

; bz_pwseg - the segment from point SI (ES = the pathway) to the next walked
; (SI + [bz_pwpd]) -> AX = its length, max(|dgx|, |dgy|) ground px.
; Preserves all else.
bz_pwseg:
    push dx
    push di
    mov di, si
    add di, [bz_pwpd]
    mov ax, [es:di]
    sub ax, [es:si]
    jns .x
    neg ax
.x:
    mov dx, [es:di + 2]
    sub dx, [es:si + 2]
    jns .y
    neg dx
.y:
    cmp ax, dx
    jae .o
    xchg ax, dx
.o:
    pop di
    pop dx
    ret

; -----------------------------------------------------------------------------
; bz_follow - a STEP of the pathway's play (wave 8R, SPEC.md 128.22.4.2: the
; frame loop's in bz_step's place in bz_mode 4).  ROLLING, the FOLLOWER
; (bz_pwroll); RESTING, the pad's icon to its next frame every interval steps
; (frames 1 - K-1 in a loop, bz_nset); a GATE opening, its next pose every
; BZ_PW_GSTEP steps and then the roll; the GAME OVER, its wait and the play's
; end (bz_pwq 'o').  bz_nstep counts the steps.  Preserves CX and ES.
; -----------------------------------------------------------------------------
bz_follow:
    push cx
    push es
    mov es, [bz_cseg]
    add word [bz_nstep], 1
    adc word [bz_nstep + 2], 0
    mov al, [bz_pwst]
    cmp al, BZ_PW_ROLL
    je .roll
    cmp al, BZ_PW_GATE
    je .gate
    cmp al, BZ_PW_OVER
    je .over
    mov bl, [bz_pwis]           ; RESTING: the icon
    cmp bl, 0ffh
    je .out
    dec byte [bz_pwcn]
    jnz .out
    mov al, [bz_ppad]
    call bz_ppadr
    mov al, [es:si + 9]
    mov [bz_pwcn], al
    mov al, [bz_pwic]
    inc ax
    cmp al, [es:si + 8]
    jb .if
    mov al, 1
.if:
    mov [bz_pwic], al
    add al, [bz_pwib]
    call bz_nset
    jmp short .out
.over:
    dec word [bz_pwcn]
    jnz .out
    mov byte [bz_pwq], 'o'
    jmp short .out
.gate:
    inc word [bz_pwcn]
    mov ax, [bz_pwcn]
    mov bl, BZ_PW_GSTEP
    div bl
    or ah, ah
    jnz .out
    inc ax                      ; AL = the pose: 2 - 5, then the roll
    cmp al, BZ_GATE_POSES - 1
    ja .go
    mov bl, [bz_pwgs]
    call bz_nset
    jmp short .out
.go:
    mov al, [bz_pwrt]
    xor ah, ah
    call bz_pwdep
    jmp short .out
.roll:
    call bz_pwroll
.out:
    pop es
    pop cx
    ret

; bz_pwroll - THE FOLLOWER's step, bbcourse.Follow's exactly: s a dword of
; 1/256 ground px, v a word of 1/256 a step; left = 256 L - s, D = v v div
; (2 FOL_ACC): BRAKING (v - FOL_ACC, not under FOL_VMIN) when left <= D, else
; v + FOL_ACC up to FOL_VMAX; s += v, at 256 L ARRIVED; the segment holding s
; (bz_pwdk its start, bz_pwln its length) and the position on it (bz_pwpos);
; a secret route's next reveal group as s passes its distance; ARRIVING,
; bz_pwarr.  ES = the pathway.  Preserves nothing.
bz_pwroll:
    mov ax, [bz_pwL]            ; DX:AX = 256 L
    call bz_pw256
    sub ax, [bz_pws]
    sbb dx, [bz_pws + 2]
    mov bx, ax
    mov cx, dx                  ; CX:BX = left
    mov ax, [bz_pwv]
    mul ax
    mov si, 2 * BZ_FOL_ACC
    div si                      ; AX = D (at most 1,536)
    mov dx, [bz_pwv]
    jcxz .lo
    jmp short .acc
.lo:
    cmp bx, ax
    ja .acc
    sub dx, BZ_FOL_ACC          ; braking
    cmp dx, BZ_FOL_VMIN
    jge .v
    mov dx, BZ_FOL_VMIN
    jmp short .v
.acc:
    add dx, BZ_FOL_ACC
    cmp dx, BZ_FOL_VMAX
    jle .v
    mov dx, BZ_FOL_VMAX
.v:
    mov [bz_pwv], dx
    add [bz_pws], dx
    adc word [bz_pws + 2], 0
    mov byte [bz_pwar], 0
    mov ax, [bz_pwL]
    call bz_pw256
    cmp [bz_pws + 2], dx
    jb .adv
    ja .arr
    cmp [bz_pws], ax
    jb .adv
.arr:
    mov [bz_pws], ax            ; on B's cell exactly
    mov [bz_pws + 2], dx
    inc byte [bz_pwar]
.adv:
    cmp byte [bz_pwnl], 0       ; the segment holding s (the last at 256 L)
    je .pos
    mov ax, [bz_pwdk]
    add ax, [bz_pwln]
    call bz_pw256
    cmp [bz_pws + 2], dx
    jb .pos
    ja .nx
    cmp [bz_pws], ax
    jb .pos
.nx:
    mov ax, [bz_pwln]
    add [bz_pwdk], ax
    mov si, [bz_pwp]
    add si, [bz_pwpd]
    mov [bz_pwp], si
    call bz_pwseg
    mov [bz_pwln], ax
    dec byte [bz_pwnl]
    jmp short .adv
.pos:
    call bz_pwpos
    mov al, [bz_pwrg]           ; a secret route's next REVEAL group, as s
    cmp al, [bz_pwng]           ; passes its distance (128.22.2)
    jae .nrv
    xor ah, ah
    shl ax, 1
    mov si, [bz_pwro]
    add si, ax
    mov ax, [es:si]
    cmp ax, [bz_pws + 1]        ; (s's whole px: s < 2^24)
    ja .nrv
    mov bl, [bz_pwrs]
    add bl, [bz_pwrg]
    mov al, 1
    call bz_nset
    inc byte [bz_pwrg]
.nrv:
    cmp byte [bz_pwar], 0
    jne bz_pwarr
    ret

; AX -> DX:AX = 256 AX (unsigned).  Preserves all else.
bz_pw256:
    mov dl, ah
    xor dh, dh
    mov ah, al
    xor al, al
    ret

; bz_pwpos - the follower's POSITION at s (128.22.4.2): t = s - 256 D_k on the
; segment from point P_k (bz_pwp) to the next walked, (sx, sy) its step's
; signs: bz_gx = 256 gx_k + sx t, bz_gy = 256 gy_k + sy t, bz_gz = 256 gz_k +
; ((gz_(k+1) - gz_k) t) idiv len_k, truncated toward zero; grounded, the
; screen state derived (bz_derive).  ES = the pathway.  Preserves nothing.
bz_pwpos:
    mov ax, [bz_pwdk]
    call bz_pw256
    mov cx, [bz_pws]
    mov bx, [bz_pws + 2]
    sub cx, ax
    sbb bx, dx                  ; BX:CX = t
    mov si, [bz_pwp]
    mov di, si
    add di, [bz_pwpd]
    mov ax, [es:si]
    mov dx, [es:di]
    call bz_pwax
    mov [bz_gx], ax
    mov [bz_gx + 2], dx
    mov ax, [es:si + 2]
    mov dx, [es:di + 2]
    call bz_pwax
    mov [bz_gy], ax
    mov [bz_gy + 2], dx
    mov ax, [es:si + 4]         ; gz_k, whole px (signed) ...
    mov bp, [es:di + 4]
    sub bp, ax                  ; ...BP = dz
    push ax
    xor ax, ax                  ; (a level segment: q = 0)
    or bp, bp
    jz .q
    mov ax, bp
    jns .zp
    neg ax
.zp:
    push ax
    mul cx                      ; |dz| t, t = BX:CX
    xchg ax, si                 ; (SI the low word, DI the high)
    mov di, dx
    pop ax
    mul bx
    add ax, di
    xchg ax, dx
    xchg ax, si                 ; DX:AX = |dz| t
    div word [bz_pwln]          ; AX = q
.q:
    xchg ax, cx                 ; CX = q
    pop ax                      ; DX:AX = gz_k << 8, signed
    mov dl, ah
    mov ah, al
    xor al, al
    xchg ax, dx
    cbw
    xchg ax, dx
    or bp, bp
    js .zn
    add ax, cx
    adc dx, 0
    jmp short .zw
.zn:
    sub ax, cx
    sbb dx, 0
.zw:
    mov [bz_gz], ax
    mov [bz_gz + 2], dx
    jmp bz_derive

; AX = a, DX = b (ground px), BX:CX = t -> DX:AX = 256 a + sgn(b - a) t.
; Preserves all else.
bz_pwax:
    push bp
    mov bp, dx
    sub bp, ax
    call bz_pw256
    or bp, bp
    jz .r
    js .n
    add ax, cx
    adc dx, bx
    jmp short .r
.n:
    sub ax, cx
    sbb dx, bx
.r:
    pop bp
    ret

; bz_pwarr - the marble ARRIVES on bz_pwdst (128.22.4.2): the route TAKEN
; (where it is opened: an EXPLORE roll on a route never opened takes none),
; the pad its rest (bz_ppad: the slot's +2, written when the bracket ends) and,
; TIMED, OPEN; a secret route's reveal groups all shown and its two ends
; posed (the hidden pad shown, the visible end with the route); the PAD
; sound; RESTING, its icon to start.  ES = the pathway.  Preserves nothing.
bz_pwarr:
    mov al, [bz_pwrt]
    mov si, bz_nrop
    call bz_dwtst
    jz .nt
    mov si, bz_nrtk
    call bz_dwset
.nt:
    mov al, [bz_pwdst]
    mov [bz_ppad], al
    cmp byte [bz_xmode], 0
    jne .x
    mov si, bz_nopen
    call bz_dwset
.x:
    mov al, [bz_pwrt]
    call bz_proute
    test byte [es:si + 3], 1
    jz .ns
    mov dl, 1
    mov ah, 1
    call bz_preveal
    mov al, [es:si]
    call bz_pnset
    mov al, [es:si + 1]
    call bz_pnset
.ns:
    mov al, BZS_EV_PAD
    call bzs_ev
    jmp bz_pwrest

; -----------------------------------------------------------------------------
; bz_pwheld - a frame of the pathway's play (bz_exitchk, after the key map):
; CF = 1 its end (bz_pwq: Enter's course, the game over's card); the HELD
; guard (bz_pwek) let go once Enter, Esc, Space and every arrow are up.
; Preserves all but the flags.
; -----------------------------------------------------------------------------
bz_pwheld:
    cmp byte [bz_pwq], 0
    jne .lv
    cmp byte [bz_pwek], 0
    je .ok
    KEYMAP_TEST bz_kmap, KSC_ENTER
    jnz .ok
    KEYMAP_TEST bz_kmap, KSC_ESC
    jnz .ok
    KEYMAP_TEST bz_kmap, KSC_SPACE
    jnz .ok
    KEYMAP_TEST bz_kmap, KSC_UP
    jnz .ok
    KEYMAP_TEST bz_kmap, KSC_DOWN
    jnz .ok
    KEYMAP_TEST bz_kmap, KSC_LEFT
    jnz .ok
    KEYMAP_TEST bz_kmap, KSC_RIGHT
    jnz .ok
    mov byte [bz_pwek], 0
.ok:
    clc
    ret
.lv:
    stc
    ret

; bz_pwkey - a TYPED key on the pathway (bz_exitchk, bz_mode 4; AL its
; character, AH its make code): ZF = 1 the pathway's own (taken), CF = 1 the
; play ends.  Only RESTING, and none held from before (bz_pwek): an ARROW whose
; route (the pad's KEYS, 128.22.4.5) is OPEN rolls it (bz_pwdep); Enter plays
; the pad's course (bz_pwck, bz_pwq 13); Space shows its INFO card (bz_kinfow,
; 128.22.6); Esc leaves (bz_pwq 27: the title).  Clobbers AX, BX, CX, DX, SI,
; DI.
bz_pwkey:
    cmp al, 13
    je .k
    cmp al, 27
    je .k
    cmp al, ' '
    je .k
    mov bh, 'r'                 ; F5, F6 and V (SPEC.md 128.26.3): the play
    cmp ax, BZ_KSC_F5 << 8      ; ends with [bz_pwq] BH, the pad's course
    je .kx                      ; in bz_pwck
    mov bh, 'l'
    cmp ax, BZ_KSC_F6 << 8
    je .kx
    mov bh, 'v'
    push ax
    or al, 20h
    cmp al, bh
    pop ax
    je .kx
    xor bl, bl                  ; BL = the arrow: Up, Down, Left, Right
    cmp ah, KSC_UP
    je .k
    inc bx
    cmp ah, KSC_DOWN
    je .k
    inc bx
    cmp ah, KSC_LEFT
    je .k
    inc bx
    cmp ah, KSC_RIGHT
    je .k
    or sp, sp                   ; ZF = 0, CF = 0: not the pathway's
    ret
.kx:
    mov al, 1                   ; (AL 1: one of BH's)
.k:
    cmp byte [bz_pwek], 0
    jne .eat
    cmp byte [bz_pwst], BZ_PW_REST
    jne .eat
    push es
    mov es, [bz_cseg]
    cmp al, 1
    je .fx
    cmp al, 27
    je .esc
    cmp al, 13
    je .ent
    cmp al, ' '
    je .info
    mov al, [bz_ppad]           ; an ARROW: the pad's KEYS, 4 bytes a pad
    shl al, 1
    shl al, 1
    add al, bl
    xor ah, ah
    mov si, [bz_ptko]
    add si, ax
    mov al, [es:si]             ; the route, bit 7 B to A (FFh none)
    cmp al, 0ffh
    je .pe
    mov ah, al
    and al, 7fh
    rol ah, 1
    and ah, 1
    call bz_proute              ; ZF = 0 OPEN
    jz .pe
    call bz_pwdep
.pe:
    pop es
.eat:
    cmp al, al                  ; ZF = 1, CF = 0
    ret
.esc:
    pop es
    mov byte [bz_pwq], 27
    stc
    ret
.ent:
    mov bh, 13
.fx:
    push bx
    mov al, [bz_ppad]
    call bz_ppadr
    mov al, [es:si]
    pop bx
    pop es
    mov [bz_pwck], al
    mov [bz_pwq], bh
    stc
    ret
.info:
    mov al, [bz_ppad]
    call bz_ppadr
    mov al, [es:si]
    pop es
    call bz_kinfow
    mov byte [bz_pwek], 0ffh    ; (the key that took the card down, held, is
    cmp al, al                  ; no press: Space's repeat no second card)
    ret

; bz_phfetch - the PATHWAY's part, its ball, a play (bz_gpath makes it the
; follower's, bz_mode 4): fetched unless it is HELD ([bz_phold]: bz_cload
; then does no fetch, no expand and no translation of the part, only the balls
; and the song and the header).  CF = 1 refused.  Preserves nothing.
bz_phfetch:
    mov byte [bz_crs], BZ_CRS_PATH
; course [bz_crs] made the play: its own ball (8b.9), mode 0, fetched
bz_gcrs:
    mov bl, [bz_crs]
    xor bh, bh
    mov al, [bz_cballs + bx]
    mov [bz_mat], al
    mov byte [bz_mode], 0
    jmp bz_cload

; -----------------------------------------------------------------------------
; bz_grounds - inside the bracket, the mode set: the game's ROUNDS (128.22.4.4).
; The PATHWAY played (bz_mode 4, bz_pwinit / bz_follow / bz_pwkey); Enter at a
; pad plays its course - its LIFE taken on the disk first (TIMED), the
; pathway's part given back unless it stays HELD (bz_phrel); after it, a
; FINISH marks the pad DONE, its exit FOUND and its best, and the pathway is
; entered with the finish's event (bz_pwev: the route (pad, exit) opened and
; rolled); a TIMEOUT or an Esc costs a life (bz_pwev LIFE; a RETRY plays the
; course again, nothing fetched), the last the GAME OVER (its sound on the
; pathway, then bz_kover).  Esc on the pathway, a refused fetch or the game
; over: the bracket's round ends (the title's bz_tround, or the desktop).  The
; palette and the song are each play's own (bz_vinit, bzs_open).
; -----------------------------------------------------------------------------
bz_grounds:
    call bz_vinit
    call bzs_open
    call bz_play
    call bzs_close
    cmp byte [bz_towin], 0      ; F, Alt+Enter: the WINDOW, the game kept
    jne .twp                    ; (SPEC.md 128.26.4)
    mov al, [bz_pwq]
    cmp al, 'o'
    je .over
    cmp al, 13
    je .enter
    cmp al, 'r'                 ; F5, F6 and V at a pad (128.26.3)
    je .fsave
    cmp al, 'l'
    je .fload
    cmp al, 'v'
    je .fload
    jmp .out                    ; (Esc: the title)
.twp:
    mov byte [bz_susp], BZ_SU_PATH
    jmp .out
.fsave:
    call bz_gfsave              ; F5: the held log saved, a card
    jmp bz_grounds              ; (the pathway again, at the same pad)
.fload:
    call bz_gfload              ; F6 or V: the log (none: its card said so)
    jc bz_grounds
    call .swap                  ; ...replayed on its course, its ball and song
    mov al, [bz_rlog + BZR_CRS]
    mov [bz_crs], al
    mov al, [bz_rlog + BZR_MAT]
    mov [bz_mat], al
    mov byte [bz_mode], 2
    call bz_cload
    jc .rback
    call bz_vinit
    call bzs_open
    call bz_play
    call bzs_close
.rback:
    mov byte [bz_retry], 0      ; (a replay's pause card offers no retry to keep)
    cmp byte [bz_towin], 0      ; (F there: the window, from the pathway)
    je .back
    call .swap
    jmp .twp
.enter:
    call .swap                  ; ENTER: the pad's course - its LIFE TAKEN on
    cmp byte [bz_xmode], 0      ; the disk first (128.19.6: off mid-course
    jne .nolife                 ; refunds nothing; a finish gives it back at
    mov al, [bz_lives]          ; the bracket's end), quietly - never in
    dec ax                      ; EXPLORE (8c)
    call bz_gstorl
    call bz_dwrite
.nolife:
    mov al, [bz_pwck]
    mov [bz_crs], al
    call bz_gcrs                ; (no INTRO card any more, 128.22.6)
    jc .out
.crs:
    call bz_vinit
    call bzs_open
    xor al, al                  ; (a RETRY's life: its sound in its own play)
    xchg al, [bz_pwev]
    cmp al, BZ_PE_LIFE
    jne .ncl
    mov al, BZS_EV_LIFE
    call bzs_ev
.ncl:
    call bz_play
    call bzs_close
    cmp byte [bz_towin], 0      ; F, Alt+Enter in a course: the WINDOW, the
    je .ntw                     ; play SUSPENDED whole - its parts, its clock,
    mov byte [bz_susp], BZ_SU_CRS ; its log (SPEC.md 128.26.4)
    ret
.ntw:
    cmp byte [bz_goal], 0       ; A COURSE: a finish ... (no RESULT card, 128.22.6)
    je .life
    call bz_dslot               ; the exit FOUND (128.19.6), a word a course,
    mov bl, [bz_crs]            ; in either mode
    xor bh, bh
    shl bx, 1
    mov cl, [bz_exit]
    mov [bz_pwex], cl
    mov byte [bz_pwev], BZ_PE_FIN
    mov ax, 1
    shl ax, cl
    or [si + bx + BZD_SEXIT], ax
    cmp byte [bz_xmode], 0      ; EXPLORE posts no best and unlocks nothing
    jne .back                   ; (8c.2)
    mov ax, [bz_nstep]          ; the slot's best for the course (8c.3)
    mov dx, [si + bx + BZD_SBEST]
    dec dx                      ; (0 none: the largest)
    dec ax
    cmp ax, dx
    jae .nb
    inc ax
    mov [si + bx + BZD_SBEST], ax
.nb:
    call bz_post                ; (its best, in memory: bz_dsave on the desktop)
    mov al, [bz_ppad]           ; the pad DONE
    mov si, bz_ndone
    call bz_dwset
    jmp short .back
.life:                          ; ...or a timeout or an Esc: a life (none
    xor al, al                  ; in EXPLORE, 8c.2) - R's RETRY taken here
    xchg al, [bz_retry]         ; whatever follows (EXPLORE's R, the last
    cmp byte [bz_xmode], 0      ; life's, would else retry a later game's
    jne .back                   ; first Esc)
    mov byte [bz_pwev], BZ_PE_OVER
    dec byte [bz_lives]
    jz .back
    mov byte [bz_pwev], BZ_PE_LIFE
    or al, al                   ; wave 8c (128.19.8): a RETRY from the pause
    jz .back                    ; card - the same course again, nothing
    mov bl, [bz_crs]            ; re-fetched, the next life taken on the disk
                                ; first; its own ball again
    xor bh, bh
    mov al, [bz_cballs + bx]
    mov [bz_mat], al
    mov al, [bz_lives]
    dec ax
    call bz_gstorl
    call bz_dwrite
    jmp .crs
.back:
    call .swap
    call bz_gpath
    jc .out
    jmp bz_grounds
.over:                          ; THE GAME IS OVER: the next game is a new one
    call bz_kover               ; (8c.4; its sound played on the pathway)
.out:
    ret
.swap:                          ; this round's parts and song given back
    call bz_cdrop               ; (the held pathway's part excepted)
    call bzs_gdrop0
    cmp byte [bz_crs], BZ_CRS_PATH
    je bz_phrel                 ; ...which stays only if a course fits beside it
    ret

; bz_phrel - before a course is fetched, the pathway's balls, song and sound
; part already given back (bz_cdrop, bzs_gdrop0): the pathway's part STAYS if
; the heap's largest free
; run, the part held, still takes the largest course (BZ_CRS_MAXCLAIM, in
; paragraphs, MEMP_AVAIL's unit); else it is dropped here and bz_phfetch reads
; it again afterwards.  Preserves nothing.
bz_phrel:
    cmp byte [bz_phold], 0
    je .out
    mov bl, MEMP_AVAIL
    call OSAPI_MEM_P            ; AX = the largest claim there is
    cmp ax, BZ_CRS_MAXCLAIM
    jb bz_phfree
.out:
    ret
; bz_phfree - the pathway's part let go whatever it holds (the game's end, or
; bz_phrel's answer).  Preserves nothing.
bz_phfree:
    mov byte [bz_phold], 0
    push ds                     ; (ES = ours: op_drop restores its caller's)
    pop es
    mov al, BZ_P_PATH
    jmp op_drop

%if BZ_TITLE
; -----------------------------------------------------------------------------
; bz_title8 - Enter on the face: THE TITLE (SPEC.md 128.23.4).  Its refusals
; are the game's (kern_small, the adapter); the title's rounds play inside ONE
; bracket (bz_fullscreen, [bz_ingame] 2: bz_tround), and whatever is held when
; it ends is given back; a game played from it is written to its slot.
; -----------------------------------------------------------------------------
bz_title8:
    mov byte [bz_newb], 0
    cmp byte [bz_small], 0
    je .big
    mov si, bz_t_small
    jmp bz_toast
.big:
    call bz_adapter
    or al, al
    jnz .ok
    mov si, bz_t_adapt
    jmp bz_toast
.ok:
    dec al
    mov [bz_herc], al
    call OSAPI_GET_TICKS        ; the title's own LFSR, seeded from the clock
    xor ax, [bz_pitl]           ; (never read by physics: replays stay exact)
    or ax, 1
    mov [bz_tlfsr], ax
    mov byte [bz_tlast], 0ffh
    mov byte [bz_towin], 0
    call bz_shdrop              ; (never beside a course, 128.19.2)
    call bz_home
    jc .ret
    mov byte [bz_ingame], 2
    mov byte [bz_err], 0
    mov bx, [bz_win]
    mov ax, bz_fullscreen
    mov cx, FSXF_FASTTICK
    call OSAPI_FSX_RUN
    mov byte [bz_ingame], 0
    mov byte [bz_tmode], 0
    pushf
    cmp byte [bz_susp], BZ_SU_CRS ; SUSPENDED in a course (128.26.4): its parts,
    je .nx                      ; its song and its mode stay for Play Game
    mov byte [bz_xmode], 0
.nx:
    popf
    jnc .ran
    mov si, bz_t_nofs
    call bz_toast
.ran:
    mov byte [bz_pgo], 0
    cmp byte [bz_susp], BZ_SU_CRS
    jne .drop
    jmp bz_back                 ; (nothing written: the course's life is, 128.19.6)
.drop:
    call bz_cdrop
    call bzs_gdrop              ; (the desktop's title song back)
    call bz_back
    cmp byte [bz_shpend], 0
    je .sv
    mov byte [bz_shpend], 0
    call bz_repaint
.sv:
    cmp byte [bz_tgame], 0      ; a game was played: its slot, and a best a
    je .ret                     ; course set, to BONANZA.DAT
    mov byte [bz_tgame], 0
    mov byte [bz_gsave], 1
    jmp bz_dsave
.ret:
    ret

; -----------------------------------------------------------------------------
; bz_tround - inside the bracket, the mode set: THE TITLE'S ROUNDS (128.23.4).
; A title demo (random, never the last one shown) on the title course, its
; keys bz_exitchk's title arm's: P plays THE GAME (bz_grounds, its end back
; here), S / 1 2 3 the slot, Esc leaves the bracket; its end plays a random
; COURSE DEMO, which any key ends; then the title again.  Each round's parts
; are given back before the next's are fetched.
; -----------------------------------------------------------------------------
bz_tround:
    mov al, [bz_susp]           ; PLAY GAME after the window (SPEC.md 128.26.4):
    or al, al                   ; the pathway, or the course, where it was left
    jz .title
    mov byte [bz_susp], 0
    cmp al, BZ_SU_CRS
    jne .game
    mov byte [bz_tmode], 0
    mov byte [bz_tgame], 1
    mov byte [bz_rsm], 1        ; (bz_play: no bz_pinit, no new log)
    call bz_grounds.crs
    jmp short .gout
.title:
    mov byte [bz_tmode], 1
.pick:
    call bz_trand               ; a title demo, never the last one shown
    and al, BZ_TNDEMO - 1
    cmp al, [bz_tlast]
    je .pick
    mov [bz_tlast], al
    call bz_tdemo               ; its start block and its log (bz_tblk, bz_rlog)
    jc .out
    mov byte [bz_crs], BZ_CRS_TITLE
    call .demo                  ; the log's ball, a replay, fetched
    jc .out
    mov al, [bz_slot]           ; the slot's label (128.23.2): pose 1 + slot
    inc ax
    mov [bz_nst], al
    call .play
    mov al, [bz_twhy]
    cmp al, 'p'
    je .game
    cmp al, 27
    je .out
    mov byte [bz_tmode], 2      ; ITS END: a random course's demo (BZD<K>)
    call bz_trand
    xor ah, ah
    mov bl, BZ_NDEMO
    div bl
    mov al, ah
    add al, BZ_P_DEMO
    call bz_tlog
    jc .out
    mov al, [bz_rlog + BZR_CRS]
    mov [bz_crs], al
    call .demo
    jc .out
    call .play                  ; (any key, its end or a timeout: the title)
    jmp bz_tround
.game:                          ; P: THE GAME in the slot shown (bz_game8's,
    mov byte [bz_tmode], 0      ; its rounds bz_grounds's, back here at its end)
    mov byte [bz_tgame], 1
    call bz_gslot
    call bz_gpath
    jc .gout
    call bz_grounds
.gout:
    cmp byte [bz_susp], BZ_SU_CRS ; (the window asked for in a course: every
    je .gsus                    ; part held, nothing stored, 128.26.4)
    call bz_phfree              ; (the held pathway goes with the game, 128.22.7:
    call .swap                  ; bz_cdrop keeps it)
    call bz_gstore              ; (the slot, in memory: bz_dsave on the desktop)
    cmp byte [bz_susp], 0       ; (...or at the pathway: the game stored, and
    jne .gsus                   ; the bracket left)
    mov byte [bz_xmode], 0
    jmp bz_tround
.gsus:
    ret
.out:
    mov byte [bz_tmode], 0
    jmp short .swap
.demo:                          ; the held log replayed on [bz_crs] with its ball
    mov al, [bz_rlog + BZR_MAT]
    mov [bz_mat], al
    mov byte [bz_mode], 2
    jmp bz_cload
.play:
    mov byte [bz_twhy], 0
    call bz_vinit
    call bzs_open
    call bz_play
    call bzs_close
    call bz_blank               ; (the owner: BLACK while the next is fetched -
.swap:                          ; the next play's first frame lights it)                          ; this round's parts and song given back
    call bz_cdrop
    jmp bzs_gdrop0

; bz_tdemo - title demo AL (0 - 3) out of BZTDEMO.BIN: its START BLOCK into
; bz_tblk and its log into bz_rlog, the part given back.  CF = 1 refused.
bz_tdemo:
    mov [bz_tsel], al
    mov al, BZ_P_TDEMO
    mov [bz_pc], al
    call op_fetch
    jc .out
    mov al, [bz_pc]
    call op_seg
    push es
    mov es, ax
    mov bl, [bz_tsel]
    xor bh, bh
    shl bx, 1
    mov si, [es:bx + 8]         ; its offset (+8, a word a demo)
    lea di, [si + BZ_TSTART]
    call bz_esz                 ; CX = its log's bytes
    add cx, BZ_TSTART
    mov di, bz_tblk             ; (bz_rlog follows bz_tblk: one copy)
    jmp short bz_tcopy

; bz_tlog - part AL (a shipped demo, BZD<K>) into bz_rlog, given back.  CF = 1
; refused.
bz_tlog:
    mov [bz_pc], al
    call op_fetch
    jc bz_tdemo.out
    mov al, [bz_pc]
    call op_seg
    push es
    mov es, ax
    xor di, di
    call bz_esz
    xor si, si
    mov di, bz_rlog
bz_tcopy:                       ; CX bytes from the part (ES) at SI to DI
    mov byte [bz_rown], 0       ; (bz_rlog is no longer a play the player made)
    cld
    push ds
    push ds
    push es
    pop ds                      ; DS = the part, ES = ours
    pop es
    rep movsb
    pop ds
    pop es
    push ds                     ; (op_drop with ES = ours: bz_vkey's kern_mega
    pop es                      ; lesson)
    mov al, [bz_pc]
    call op_drop
    clc
bz_tdemo.out:
    ret

; bz_trand - AL, AX = the title's LFSR stepped (a 16-bit Galois, taps B400h).
bz_trand:
    mov ax, [bz_tlfsr]
    shr ax, 1
    jnc .n
    xor ax, 0b400h
.n:
    mov [bz_tlfsr], ax
    ret

; bz_tlabel - the slot changed on the title: its label's pose, sign 0's
; 1 + slot (a PK_SIGN, 128.23.2; bz_nset marks its lane, 128.22.4.1), so the
; one block redraws.  Preserves all but AX and BX.
bz_tlabel:
    mov al, [bz_slot]
    inc ax
    xor bl, bl
    jmp bz_nset
%endif

bz_cmedals:     BZ_CRS_MEDALS   ; each course's G and S, steps (8c.3)
%ifnmacro BZ_CRS_NEXITS 0       ; the exits each course has (bzcourse.inc's, the tool's,
%macro BZ_CRS_NEXITS 0          ; once it emits them; until then the sources':
    db 1, 1, 2, 1, 1, 1, 1, 0   ; only TRIAL has two finishes) - for the info card
%endmacro
%endif
bz_cnex:        BZ_CRS_NEXITS
 %if BZ_PATH_NPAD > 32
  %error "the save keeps a bit a pad in a dword (SPEC.md 128.22.5)"
 %endif
%endif

; bz_cdrop - every ball row and the course's given back (op_drop of a part that
; is not here is a no-op, so all go whichever failed), their words 0.  The
; song is bzs_gdrop's.  Preserves nothing.
bz_cdrop:
    push ds                     ; ES = ours, not whatever the bracket left:
    pop es                      ; op_drop restores its caller's ES after the
                                ; free, and on kern_mega a part's own selector
                                ; there is a #GP once its claim is gone (the
                                ; final pass of wave 1: bonanzamega's fault at
                                ; op_drop's POP ES, the ball's selector in ES)
    mov al, BZ_P_BALR
.dball:
    call op_drop                ; (it preserves AX)
    inc ax
    cmp al, BZ_P_BALR + BZ_NMAT
    jb .dball
    mov al, [bz_pc]
%if BZ_PATH_NPAD
    cmp al, BZ_P_PATH           ; the HELD pathway's part stays (128.22.7)
    jne .dpc
    cmp byte [bz_phold], 0
    jne .held
.dpc:
%endif
    call op_drop
%if BZ_PATH_NPAD
.held:
%endif
    xor ax, ax
    mov [bz_bsegs], ax
    mov [bz_bsegs + 2], ax
    mov [bz_bsegs + 4], ax
    mov [bz_cseg], ax
    mov [bz_bseg], ax
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
%if BZ_TITLE
    mov byte [bz_fixed], 0      ; SPEC.md 128.23.2: a FIXED window - BZG1 +30
 %if BZ_PATH_NPAD
    mov byte [bz_paged], 0      ; (wave 8R, 128.22.4.3: or PAGED, bit 3, +30
    mov al, [es:di + BZG_FLAGS] ; page 0's, BZC2 +44 the pages; a register's
    test al, BZ_GF_PAGED        ; test: tests/unit/t_bits.py cannot read the
    jz .npg                     ; generated bzcourse.inc's values)
    inc byte [bz_paged]
    mov al, [es:BZC_NPAGES]
    mov [bz_paged + 1], al
    jmp short .pgd
.npg:
 %endif
    test byte [es:di + BZG_FLAGS], BZ_GF_VIEW ; its top line / 4, +31 the
    jz .nov                     ; CGA's c0; R0 in this card's card rows (2
    inc byte [bz_fixed]         ; lines the CGA's, 4 the Hercules'), the
.pgd:
    mov al, [es:di + BZG_FLAGS + 2] ; Hercules' c0 BZ_HERC_LEFT words left
    xor ah, ah                  ; of the CGA's
    mov bl, [es:di + BZG_FLAGS + 3]
    xor bh, bh
    cmp byte [bz_herc], 0
    jne .vh
    shl ax, 1
    jmp short .vs
.vh:
    sub bx, BZ_HERC_LEFT
.vs:
    mov [bz_fixr], ax
    mov [bz_fixc], bx
.nov:
%endif
    mov ax, [es:di + BZG_X0]
    mov [bz_x0], ax
    mov ax, [es:di + BZG_Y0]
    mov [bz_y0], ax
    mov ax, [es:di + BZG_NWAY]
    mov [bz_nway], ax
    mov ax, [es:di + BZG_ROUTE]
    mov [bz_wayoff], ax
    mov al, [es:BZC_SB]         ; the occluder pass's biases and mask table
    cbw                         ; (SPEC.md 128.15.4.1, 128.15.5.2): SB signed
    mov [bz_osbias], ax
    mov ax, [es:BZC_TB]
    mov [bz_otb], ax
    mov ax, [es:BZC_MTAB]
    mov [bz_mtab], ax
    call bz_osmake              ; ...and its rows' summary (bzvideo.inc bz_occ)
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
; bz_osmake - THE OCCLUDER ROWS' SUMMARY (the speed pass, round 2), DERIVED at
; the launch from the part's own index - no field of the part, so no course's
; identity and no demo moves: bz_osum[br] = (the greatest s', the greatest t')
; of block row br's records, a word a row, for the first BZ_OSROWS rows.  An
; empty row is 0, 0 (bz_occ leaves it at once); the table's words past BROWS
; are FFFFh, which leave no row.  The 4-byte record's s' is its byte +1 and
; its t' its byte +2 (SPEC.md 128.15.5.1).  DS = ours, ES = the course part
; (a selector on kern_mega: read through, never computed on).  Preserves all
; but AX, BX, CX, DX, SI, DI, BP.
; -----------------------------------------------------------------------------
bz_osmake:
    mov bx, [es:BZC_OCCIDX]
    mov di, bz_osum
    mov bp, [es:BZC_BROWS]
    cmp bp, BZ_OSROWS
    jbe .row
    mov bp, BZ_OSROWS
.row:
    mov si, [es:bx]             ; the row's records [SI, CX)
    mov cx, [es:bx + 2]
    xor ax, ax
.rec:
    cmp si, cx
    jae .put
    mov dx, [es:si + 1]         ; DL = s', DH = t'
    cmp dl, al
    jbe .t
    mov al, dl
.t:
    cmp dh, ah
    jbe .n
    mov ah, dh
.n:
    add si, BZ_REC
    jmp short .rec
.put:
    mov [di], ax
    inc di
    inc di
    inc bx
    inc bx
    dec bp
    jnz .row
    mov ax, 0ffffh
.rest:
    cmp di, bz_osum + 2 * BZ_OSROWS
    jae .out
    mov [di], ax
    inc di
    inc di
    jmp short .rest
.out:
    ret

; -----------------------------------------------------------------------------
; bz_cexp - THE COURSE PART EXPANDED IN PLACE (SPEC.md 128.15.4.4, 128.15.4.5),
; right after the fetch that DECODED it and before anything reads it.  The
; part is BZC2's STORED form: each section's slot [off, off + len) holds a
; zero hole and then its dlen stored bytes; the directory (the part's last
; 8 NSEC bytes) names each section's form.  The walk takes the entries in
; order, which is also the order the forms depend on (ROWTAB reads G, WAYS
; reads G, C and T, all before it).  Each form runs FORWARD through its own
; slot and never reaches a stored byte it has not read (the tool's in-place
; proof, --selfcheck item 10), and every loop counts with a field of the
; header, of BZG1 or of its own entry, never with a byte it is expanding.
; NOT idempotent (WDIFF adds), so it runs exactly once a decoding fetch: the
; caller drops the part on every way out, so every fetch decodes.  The
; Hercules translates AFTER it (bz_hgen's table lives in bz_boxbuf, which
; ROWPLANES and CELLS use as scratch first).  The part is read and written through its
; own segment (kern_mega: its LDT selector) in DS or ES, at offsets inside its
; length; nothing through CS, no segment arithmetic (128.15.11).
; DS = ours, [bz_cseg] the part.  Preserves BP, DS, ES.
; -----------------------------------------------------------------------------
bz_cexp:
    push bp
    push es
    cld
    mov es, [bz_cseg]           ; ES = the part (the walk reads it with ES:)
    mov bx, [es:BZC_DIROFF]
    mov cx, [es:BZC_NSEC]
.ent:
    push cx
    push bx
    mov di, [es:bx + BZX_OFF]   ; DI = S, the slot
    mov cx, [es:bx + BZX_LEN]   ; CX = its RAM length
    mov si, di
    add si, cx
    sub si, [es:bx + BZX_DLEN]  ; SI = S + H: its stored bytes
    mov bl, [es:bx + BZX_FORM]
    xor bh, bh
    shl bx, 1
    push ds
    call [bx + bz_cxtab]        ; (DS = ours: the table is ours)
    pop ds
    pop bx
    pop cx
    add bx, BZX_ENTB
    loop .ent
    pop es
    pop bp
    ret

; THE FORMS: SI = the stored bytes, DI = the slot, CX = its RAM length, DS =
; ours, ES = the part.  Each may change DS (bz_cexp restores it), and
; clobbers AX, BX, CX, DX, SI, DI, BP.
bz_cxtab:
    dw bz_cxret                 ; 0 PLAIN: in place already
    dw bz_cxmap                 ; 1 ROWPLANES
    dw bz_cxcnt                 ; 2 COUNTS
    dw bz_cxdif                 ; 3 WDIFF
    dw bz_cxmtb                 ; 4 MASKTAB (the 4-byte record's, D)
BZ_CXFORMS  equ 0FFh
    dw bz_cxrtb                 ; 5 ROWTAB
    dw bz_cxway                 ; 6 WAYS
    dw bz_cxcel                 ; 7 CELLS
%if BZ_FORMS & ~BZ_CXFORMS
 %error "bz_cexp: a course part uses a stored form its dispatch table does not hold"
%endif
%if BZ_REC != 4
 %error "bonanza: the occluder pass reads D's 4-byte records (SPEC.md 128.15.5.4); bzcourse.inc's BZ_REC is not 4"
%endif

; 1 ROWPLANES: block row r stored as C/4 high bytes (cell j's two high bits at
; bits 2 (j AND 3) of byte j >> 2) and then C low bytes; map word j = BLKOFF +
; 16 (low + 256 high).  The row's high bytes go to scratch (bz_boxbuf, at most
; 32) first, because the words of a late row overrun them.  COLS and BROWS
; count.
bz_cxmap:
    mov bp, [es:BZC_BLKOFF]
    mov dx, [es:BZC_BROWS]
.row:
    push dx                     ; (the rows left)
    mov cx, [es:BZC_COLS]
    shr cx, 1
    shr cx, 1
    mov dx, cx                  ; DL = C/4: the row's high bytes
    mov bx, bz_boxbuf
.hi:
    es lodsb                    ; ...to scratch, before the words overrun them
    mov [bx], al
    inc bx
    loop .hi
    mov ch, dl                  ; CH = the high bytes left
    mov cl, 4
    mov bx, bz_boxbuf
.grp:
    mov dl, [bx]                ; DL = four cells' high bits
    inc bx
    mov dh, 4
.cell:
    es lodsb                    ; AL = the cell's low byte
    mov ah, dl
    and ah, 3
    shl ax, cl
    add ax, bp
    stosw                       ; BLKOFF + 16 (low + 256 high)
    shr dl, 1
    shr dl, 1
    dec dh
    jnz .cell
    dec ch
    jnz .grp
    pop dx
    dec dx
    jnz .row
bz_cxret:
    ret

; 2 COUNTS: a count byte a block row; OCCIDX[br] = OCCREC + RECB x (the
; records before row br), br = 0 .. BROWS.  BROWS counts.
bz_cxcnt:
    mov dx, [es:BZC_OCCREC]
    mov cx, [es:BZC_BROWS]
    mov ax, dx
.w:
    stosw                       ; word br: it ends before count br's byte
    es lodsb
    mul byte [es:BZC_RECB]      ; (a count is a byte: AX = RECB count)
    add dx, ax
    mov ax, dx
    loop .w
    stosw                       ; word BROWS: OCCREC + RECB NOCC
    ret

; 3 WDIFF: the first record as it is, then each word the difference from the
; same word of the record before.  w[i] += w[i - RECB / 2], forward, so it
; reads only what it has already written.  ONE loop for both strides: RECB
; from the header; the entry's length (RECB NOCC) counts.
bz_cxdif:
    push es
    pop ds                      ; DS = the part
    mov bl, [BZC_RECB]
    xor bh, bh
    add si, bx                  ; (SI = S: stored as long as it is in RAM)
    sub cx, bx
    shr cx, 1                   ; the words after the first record
    jcxz .out                   ; (one record)
    neg bx                      ; BX = -RECB
.w:
    mov ax, [bx + si]
    add [si], ax
    inc si
    inc si
    loop .w
.out:
    ret

; 4 MASKTAB: MTAB[m] = MASKOFF + 16 m, NMASK counts
bz_cxmtb:
    mov cx, [es:BZC_NMASK]
    mov ax, [es:BZC_MASKOFF]
    mov dx, 16
    jmp short bz_cxramp

; 5 ROWTAB: ROWTAB[r] = GRIDOFF + 32 + 4 KW r, NROWS counts (BZG1, before it)
bz_cxrtb:
    mov bx, [es:BZC_GRID]
    mov cx, [es:bx + BZG_NROWS]
    mov dx, [es:bx + BZG_KW]
    shl dx, 1
    shl dx, 1
    lea ax, [bx + 32]
bz_cxramp:                      ; CX words from AX, DX apart
    stosw
    add ax, dx
    loop bz_cxramp
    ret

; 6 WAYS: each way's tile (wx, wy), a byte each; written as the ball's picture
; top-left on the tile's centre (the tool's rule, 128.10.4.5):
;   x = 16 a + X0 - 8,  y = 8 s - 2 (2 z0 + sx + sy) + Y0 - 5,
; s = wx + wy, a = wx - wy, z0, sx and sy the tile's CELL's, found as
; bzphys.inc finds a cell: ROWTAB[s - SMIN] + 4 ((a - AMIN) >> 1).  NWAY
; counts; way w's words end before way w + 1's stored pair.
bz_cxway:
    push es
    pop ds                      ; DS = ES = the part
    mov bx, [BZC_GRID]
    mov cx, [bx + BZG_NWAY]
.way:
    push cx
    lodsw                       ; AL = wx, AH = wy
    mov cl, ah
    xor ch, ch
    xor ah, ah
    mov dx, ax
    add dx, cx                  ; DX = s
    sub ax, cx                  ; AX = a
    mov bp, ax
    mov cl, 4
    shl ax, cl
    add ax, [bx + BZG_X0]
    sub ax, 8
    stosw                       ; x
    sub bp, [bx + BZG_AMIN]
    and bp, byte -2
    shl bp, 1                   ; BP = 4 k
    mov ax, dx
    sub ax, [bx + BZG_SMIN]
    shl ax, 1
    add ax, [bx + BZG_ROWTAB]
    push si
    xchg ax, si
    mov si, [si]                ; ROWTAB[r]
    add si, bp
    lodsw                       ; AL = z0, AH = sy : sx (signed nibbles)
    pop si
    mov ch, ah
    sar ch, cl                  ; CH = sy
    shl ah, cl
    sar ah, cl                  ; AH = sx
    add ch, ah                  ; CH = sx + sy
    cbw
    shl ax, 1                   ; AX = 2 z0
    xchg ax, cx
    mov al, ah
    cbw
    add ax, cx
    shl ax, 1                   ; AX = 2 (2 z0 + sx + sy)
    mov cl, 3
    shl dx, cl
    sub dx, ax
    add dx, [bx + BZG_Y0]
    sub dx, 5
    xchg ax, dx
    stosw                       ; y
    pop cx
    loop .way
    ret
; 7 CELLS (SPEC.md 128.15.6): each cell as in RAM but two fields, each stored
; as its difference from the RULE: a VOID cell's z0 as z0 - rule_z0 (8 bits),
; and every cell's SAFE bit XOR rule_safe.  The rule, as the tool builds the
; grid (bbcourse.cells_rule is this routine's model):
;   V = a cell's lowest corner + 79h, z0 + min(0, sx) + min(0, sy) + 79h in
;       8 bits, UNSIGNED, for a cell that is not VOID; FFh for a VOID cell
;       and outside the grid
;   rule_z0 = the least V within two tiles (Chebyshev in wx and wy) + 81h:
;       the least corner less 6 (NEAR), or FFh + 81h = -128 (OPEN).  The bias
;       makes OPEN's value the sentinel's and the order the corners' for every
;       corner a NEAR cell can hold (-122 .. 127; -122's NEAR z0 IS -128)
;   rule_safe = a FLOOR cell with sx = sy = 0, OBS clear and its four edge
;       neighbours not VOID
; The 5 x 5 least is SEPARABLE: A = the least V on the wx diagonal's 5 cells
; through a cell, then the least A on the wy diagonal's.  In the grid's rows
; a wx step is (row + 1, k + p) and a wy step (row + 1, k + p - 1), p the
; row's parity (SMIN + row, AND 1), so each reaches 2 rows and a cell either
; way.  The A rows are scratch in bz_boxbuf, BZ_CXRW bytes a row with a pad
; (FFh) either side of KW cells, in a window that slides down the buffer and
; is copied back to its start at the end.  Iteration j = 0 .. NROWS + 3 holds
; A rows j - 6 .. j + 2: it sets row j + 2 to FFh; lays each non-VOID cell of
; grid row j into A rows j - 2 .. j + 2 and XORs its SAFE; then takes A rows
; j - 6 .. j - 2 for each VOID cell of grid row j - 4.  The rule reads only
; fields the form does not change (a VOID cell's z0 and every SAFE bit are the
; two it never reads), so its order is free.  NROWS and KW count; the A
; writes stay inside the window (one cell either side of KW, the pads), and
; the grid writes inside the slot, whatever the bytes.  The tool keeps every
; non-VOID cell two tiles inside the grid (read_part), so the edge reads stay
; in the grid.  DS = ours (the A rows), ES = the part; the frame is SS:BP.
; About 0.19 s on PEAK, with bz_cxsafe (priced, 128.15.6).
BZ_CXRW     equ 36              ; an A row's stride: a pad, KW cells, a pad
BZ_CXNS     equ 4 * BZ_BOXB / BZ_CXRW   ; the A rows bz_boxbuf holds
%if BZ_CXRW < BZ_KWMAX + 2 || BZ_CXNS < 10 || BZ_CXRW & 1
 %error "bz_cxcel: bz_boxbuf does not hold its window of A rows"
%endif
BZ_CXF_R    equ 0               ; A row j - 6's first byte (its left pad)
BZ_CXF_J    equ 2               ; j
BZ_CXF_P    equ 4               ; row j's parity
BZ_CXF_RS   equ 6               ; 4 KW: a grid row's bytes
BZ_CXF_G    equ 8               ; grid row j
BZ_CXF_N    equ 10              ; NROWS
BZ_CXF_KW   equ 12              ; KW
BZ_CXF_U    equ 14              ; from cell k, row j - 1's cell k + p - 1: 4 p - 4 - 4 KW
BZ_CXF_D    equ 16              ; and row j + 1's: 4 p - 4 + 4 KW
BZ_CXF      equ 18
%if BZ_CXF != 18
 %error "bz_cxcel: .out's add sp is the frame's size"
%endif
bz_cxcel:
    mov bx, [es:BZC_GRID]
    mov cx, [es:bx + BZG_KW]
    mov dx, cx
    shl dx, 1
    shl dx, 1                   ; DX = 4 KW
    mov ax, [es:bx + BZG_SMIN]
    and ax, 1                   ; AX = p, row 0's
    mov si, ax
    shl si, 1
    shl si, 1
    sub si, 4
    add si, dx
    push si                     ; D: 4 p - 4 + 4 KW
    sub si, dx
    sub si, dx
    push si                     ; U: 4 p - 4 - 4 KW
    push cx                     ; KW
    push word [es:bx + BZG_NROWS]       ; N
    push di                     ; G: grid row 0, the slot
    push dx                     ; RS
    push ax                     ; P
    xor ax, ax
    push ax                     ; J
    mov di, bz_boxbuf
    push di                     ; R
    mov bp, sp
    mov cx, 9 * BZ_CXRW / 2     ; A rows -6 .. 2: FFh
.fill:
    push es
    push ds
    pop es
    mov ax, 0FFFFh
    rep stosw
    pop es
    mov bx, [bp + BZ_CXF_P]     ; BX = p, both passes'
; row j: lay each cell that is not VOID into the A rows j - 2 .. j + 2
    mov ax, [bp + BZ_CXF_J]
    cmp ax, [bp + BZ_CXF_N]
    jae .gat                    ; (past the grid: no row j)
    mov si, [bp + BZ_CXF_G]
    mov di, [bp + BZ_CXF_R]
    add di, 6 * BZ_CXRW + 1     ; A row j, cell 0
    mov ch, [bp + BZ_CXF_KW]
    mov cl, 4
.sc:
    mov ax, [es:si + 2]         ; AL = surface : kind, AH = flags
    test al, 15
    jz .scn                     ; VOID: no corner
    call bz_cxsafe
    mov dx, [es:si]             ; DL = z0, DH = sy : sx
    mov al, 79h
    add al, dl
    test dh, 8
    jz .lx
    mov dl, dh
    or dl, 0F0h                 ; sx < 0
    add al, dl
.lx:
    sar dh, cl                  ; DH = sy
    jns .ly
    add al, dh
.ly:                            ; AL = V, what this cell lays
    cmp [di + 2 * BZ_CXRW + 1], al      ; A(j + 2, k + 1)
    jbe .s1
    mov [di + 2 * BZ_CXRW + 1], al
.s1:
    cmp [bx + di + BZ_CXRW], al         ; A(j + 1, k + p)
    jbe .s2
    mov [bx + di + BZ_CXRW], al
.s2:
    cmp [di], al                        ; A(j, k)
    jbe .s3
    mov [di], al
.s3:
    cmp [bx + di - BZ_CXRW - 1], al     ; A(j - 1, k + p - 1)
    jbe .s4
    mov [bx + di - BZ_CXRW - 1], al
.s4:
    cmp [di - 2 * BZ_CXRW - 1], al      ; A(j - 2, k - 1)
    jbe .scn
    mov [di - 2 * BZ_CXRW - 1], al
.scn:
    add si, 4
    inc di
    dec ch
    jnz .sc
; row j - 4: each VOID cell's z0, from the A rows j - 6 .. j - 2
.gat:
    cmp word [bp + BZ_CXF_J], 4
    jb .nx
    mov si, [bp + BZ_CXF_RS]
    shl si, 1
    shl si, 1
    neg si
    add si, [bp + BZ_CXF_G]     ; grid row j - 4 (its parity is row j's)
    mov di, [bp + BZ_CXF_R]
    add di, 2 * BZ_CXRW + 1     ; A row j - 4, cell 0
    mov cx, [bp + BZ_CXF_KW]
.ga:
    test byte [es:si + 2], 15
    jnz .gan                    ; not VOID: its z0 is stored as it is
    mov al, [di - 2 * BZ_CXRW + 1]      ; A(s - 2, k + 1)
    cmp al, [bx + di - BZ_CXRW]         ; A(s - 1, k + p)
    jbe .g1
    mov al, [bx + di - BZ_CXRW]
.g1:
    cmp al, [di]                        ; A(s, k)
    jbe .g2
    mov al, [di]
.g2:
    cmp al, [bx + di + BZ_CXRW - 1]     ; A(s + 1, k + p - 1)
    jbe .g3
    mov al, [bx + di + BZ_CXRW - 1]
.g3:
    cmp al, [di + 2 * BZ_CXRW - 1]      ; A(s + 2, k - 1)
    jbe .g4
    mov al, [di + 2 * BZ_CXRW - 1]
.g4:
    add al, 81h                 ; the least corner - 6, or FFh + 81h = -128
    add [es:si], al             ; z0 = the stored difference + rule_z0
.gan:
    add si, 4
    inc di
    loop .ga
.nx:
    mov ax, [bp + BZ_CXF_RS]
    add [bp + BZ_CXF_G], ax
    mov ax, 4
    xor byte [bp + BZ_CXF_P], 1
    jnz .np
    neg ax
.np:
    add [bp + BZ_CXF_U], ax     ; the edge neighbours' cells move with p
    add [bp + BZ_CXF_D], ax
    mov ax, [bp + BZ_CXF_N]
    add ax, 4
    inc word [bp + BZ_CXF_J]
    cmp [bp + BZ_CXF_J], ax     ; j = 0 .. NROWS + 3
    jae .out
; the window moves down a row; at the buffer's end, rows j - 6 .. j + 1 go
; back to its start
    mov si, [bp + BZ_CXF_R]
    add si, BZ_CXRW
    mov di, si
    cmp si, bz_boxbuf + (BZ_CXNS - 9) * BZ_CXRW
    jbe .fit
    push es
    push ds
    pop es
    mov di, bz_boxbuf
    mov cx, 4 * BZ_CXRW
    rep movsw
    pop es
    mov di, bz_boxbuf
.fit:
    mov [bp + BZ_CXF_R], di
    add di, 8 * BZ_CXRW         ; row j + 2: FFh
    mov cx, BZ_CXRW / 2
    jmp .fill
.out:
    add sp, 18                  ; BZ_CXF: the frame's nine words (spelled as
    ret                         ; a number, which tools/stkbalance.py reads)

; bz_cxcel's SAFE: AL = the cell's surface : kind, AH = its flags, ES:SI =
; the cell, SS:BP bz_cxcel's frame; XORs rule_safe into the cell's flags.
; Clobbers AL and DX.
bz_cxsafe:
    and al, 15
    cmp al, 1                   ; FLOOR
    jne .no
    test ah, BZ_FL_OBS          ; a prop's cell: never SAFE
    jnz .no
    cmp byte [es:si + 1], 0     ; sx = sy = 0
    jne .no
    mov dx, si
    add si, [bp + BZ_CXF_U]     ; row j - 1: cells k + p - 1 and k + p ...
    mov ah, 2
.nbr:
    test byte [es:si + 2], 15
    jz .nb
    test byte [es:si + 6], 15
    jz .nb
    mov si, dx
    add si, [bp + BZ_CXF_D]     ; ... then row j + 1's two
    dec ah
    jnz .nbr
    mov si, dx
    xor byte [es:si + 3], BZ_FL_SAFE
.nb:
    mov si, dx
.no:
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
;   the FRAME half of each squash, shatter and stretch entry (frame x shift
;     x parity copy p x (mask 80, frame 80)): 16 rows from table p;
;   a PLATFORM's sprite (wave 3, SPEC.md 128.12.6.4): parity copy p x (mask
;     144, frame 144), the frame's row r through table (p + r) AND 1.
; Every ball part this launch fetched (bz_bsegs, wave 4), each the same way.
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
%if BZ_PATH_NPAD
    cmp byte [bz_phre], 0       ; a HELD pathway was translated when it was
    jne .noplat                 ; fetched: the balls alone (128.22.7)
%endif
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
    mov di, bz_bsegs            ; each ball fetched (wave 4: up to three)
.nb:
    mov ax, [di]
    or ax, ax
    jz .nbn
    push di
    mov es, ax
    call bz_hxball
    pop di
.nbn:
    inc di
    inc di
    cmp di, bz_bsegs + 2 * BZ_NMAT
    jb .nb
    ret
; ES = a ball part: its roll frames, squash and shatter entries (BP the toggle)
bz_hxball:
    mov bx, bz_boxbuf           ; (table 0 for its first row)
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
    mov si, BZ_BAL_SHAOFF       ; ...and glass's shatter entries or rubber's
    mov al, [es:BZB_NSHA]       ; stretch (wave 6), one table at the same
    add al, [es:BZB_NSTR]       ; offset: +12 and +14 count them, never both
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
    cmp byte [bz_fs], 0         ; (inside the bracket the framebuffer is ours:
    jne .q                      ; a refusal there says nothing, 128.26.3)
    push es
    push ds
    pop es
    xor cx, cx
    call OSAPI_TOAST
    pop es
.q:
    ret

TOASTSTR bz_t_small, 'Bonanza: too little RAM'
TOASTSTR bz_t_adapt, 'CGA OR HERC ONLY'
TOASTSTR bz_t_nofs, 'Bonanza: no full screen'

; -----------------------------------------------------------------------------
; THE FACE (SPEC.md 128.14.3.2): two PAGES, [bz_page] 0 MAIN and 1 RESULTS.
; Every line is ONE opaque OSAPI_FONT_RUN padded with spaces to the content's
; width (the padding is the erase, SPEC.md 6.1), and only the 2px gaps between
; lines and the strip under the last one are filled: no pixel is written
; twice.  The lines are built in bz_lbuf.  MAIN's thirteen are a builder each
; (bz_ftab), so a key redraws exactly the lines it changed (bz_redraw); the
; RESULTS page is drawn whole and left by the next key.  EVERY LINE FITS THE
; CGA's 42 CELLS (128.14.17 item 2): each builder's widest output - its
; strings, which BZS measures, and its fields at their widest - is asserted
; under the strings (BZ_FIT), so a longer string fails the build.
; -----------------------------------------------------------------------------
BZ_NLINE    equ 13              ; the CGA's content holds 13 lines of 42 cells
                                ; (the window sits above the dock): MAIN's are the
                                ; tour's, six, then a scorecard line a tour course
                                ; - six since the PLAYGROUND (SPEC.md 128.16.8),
                                ; which took the title's line: the title bar says it
BZ_LTOUR    equ 0               ; the tour's line
BZ_FACEW    equ 42
BZ_TIMEW    equ 6               ; a time: `ss.hh`, `ssss.h` (from 100 s) or `20:00+`
BZ_FALLMAX  equ 9999            ; falls are shown, and filed, to four digits
BZ_SC_NAME  equ 3               ; the scorecard's columns (bz_lbuf offsets; 0 is
BZ_SC_TIME  equ 9               ; the margin cell): `K NAME  time f<n> lim <l>
BZ_SC_FALL  equ 17              ; best <b>`
BZ_SC_LIM   equ 23
BZ_SC_BEST  equ 31

; the face's three entries, each a far call into the SHELL PART (SPEC.md
; 128.19.2, bzshell.inc): bz_face paints it, bz_redraw redraws the 0FFh-ended
; line list at SI (in OUR segment), bz_redraw1 the one line AL
bz_face:
    mov al, BZH_FACE
    jmp short bz_shcall
bz_redraw:
    mov al, BZH_REDRAW
    jmp short bz_shcall

; C, M and N on the desktop (one press each, bz_dkey): the next camera mode,
; ball or course, and the lines that name them redrawn.  N sets the ball to the
; new course's own (SPEC.md 128.11.5.4).  Every one is the session's.
bz_camkey:
    call bz_cnext
    jmp short bz_line3

bz_ballkey:
    inc byte [bz_matsel]
    cmp byte [bz_matsel], BZ_NMAT
    jb bz_line3
    mov byte [bz_matsel], 0
bz_line3:
    mov al, 3
    jmp short bz_redraw1
bz_line4:                       ; S (bzsound.inc bzs_skey): the sound's line
    mov al, 4
bz_redraw1:
    mov ah, al                  ; the LINE vector's line is AH
    mov al, BZH_LINE
    jmp short bz_shcall

%if BZ_CRS_BENCH != 0
 %error "bz_crskey cycles courses 1 .. BZ_NCRS - 1: BENCH must be course 0"
%endif
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
    mov si, bz_crsl             ; Enter's title (1) and the ball (3)
    jmp bz_redraw
bz_crsl:    db 1, 3, 0ffh
bz_slotl:   db BZ_LTOUR, 1, 0ffh  ; (8c: the slot's keys and Enter's line)
bz_stopl:   db 1, 3, 5, BZ_LTOUR, 0ffh ; a tour stopped on the face: the keys, M,
                                ; the demo keys and the tour's line

; CF = 1 while a tour's course is next or playing ([bz_tour] 1 - 6, SPEC.md
; 128.14.3.1).  Preserves all but the flags.
bz_intour:
    push ax
    mov al, [bz_tour]
    dec al
    cmp al, BZ_NTOUR
    pop ax
    ret


; -> DX:AX = the tour's total steps, the sum of [bz_ttime]'s five; BL = 1 when
; one of them is the 65,535 clamp (such a total is never kept, 128.14.3.1).
; Preserves all else.  (bz_post's; the face's own copy is in bzface.inc)
bz_ttotal:
    push cx
    push si
    xor ax, ax
    cwd
    mov bl, al
    mov si, bz_ttime
    mov cx, BZ_NTOUR
.s:
    cmp word [si], 0ffffh
    jne .a
    mov bl, 1
.a:
    add ax, [si]
    adc dx, 0
    inc si
    inc si
    loop .s
    pop si
    pop cx
    ret

; -----------------------------------------------------------------------------
; bz_shcall - the SHELL PART's door (SPEC.md 128.19.2): AL = a vector (BZH_*),
; every other register passed to it as it stands.  The part is fetched when it
; is not held (at home, as every fetch is) and its head checked once a fetch:
; its signature, and the image and bss sizes it was LINKED against, which must
; be this package's own (our header's +8 and +10) - a part of another build is
; dropped and refused, never called.  Not while a COURSE is held ([bz_cseg]):
; the part never shares memory with one, so a paint the bracket's restore asks
; for is put off (bz_shpend) and made by bz_launch once the course is dropped.
; CF = 1 nothing was called (op_fetch, bz_home or the stamp toasted why).
; Then the far call goes through the part's CODE alias (op_cseg: on kern_mega
; a code selector, on every real-mode kernel the segment itself).
; Preserves nothing the vector does not.
; -----------------------------------------------------------------------------
bz_shcall:
    cmp word [bz_cseg], 0
    je .free
    cmp byte [bz_susp], BZ_SU_CRS ; (a SUSPENDED course shares memory with the
    je .free                    ; face: the brief's, SPEC.md 128.26.4)
    mov byte [bz_shpend], 1     ; a course is held: the paint is bz_launch's
    stc
    ret
.free:
    push ax
    mov al, BZ_P_SHELL
    call op_seg
    or ax, ax
    jnz .held
    push bx                     ; (op_fetch clobbers AX - DI and ES: the
    push cx                     ; vector's inputs are kept round it)
    push dx
    push si
    push di
    push bp
    push es
    call bz_home                ; (its refusal toasted)
    jc .fno
    mov al, BZ_P_SHELL
    call op_fetch               ; (its refusal toasted)
    call bz_back
.fno:
    pop es
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    jc .no
    mov al, BZ_P_SHELL
    call op_seg
    push es
    mov es, ax
    cmp word [es:0], BZH_SIG0
    jne .bad
    cmp word [es:2], BZH_SIG1
    jne .bad
    mov ax, [8]                 ; our image and bss sizes (OS88_HEADER)
    cmp ax, [es:BZH_IMAGE]
    jne .bad
    mov ax, [10]
    cmp ax, [es:BZH_BSSW]
    jne .bad
    pop es
.held:
    mov al, BZ_P_SHELL
    call op_cseg
    mov [bz_shfp + 2], ax
    pop ax
    push bx
    mov bl, al
    xor bh, bh
    mov al, bl                  ; BX = BZH_VEC + 3 x the vector (AH kept)
    shl bx, 1
    add bl, al
    adc bh, 0
    add bx, BZH_VEC
    mov [bz_shfp], bx
    pop bx
.fc:                            ; (a row's breakpoint: the part is held here)
    call far [bz_shfp]
    clc
    ret
.bad:
    pop es
    call bz_shdrop
    mov si, bz_t_shell
    call bz_toast
.no:
    pop ax
    stc
    ret

; bz_shdrop - the shell part given back (before any course fetch, and when its
; stamp refused it).  ES = ours on the way in (op_drop restores ES after the
; free, and on kern_mega a dropped claim's selector there is a #GP).
; Preserves every register.
bz_shdrop:
    push ax
    push es
    push ds
    pop es
    mov al, BZ_P_SHELL
    call op_drop
    pop es
    pop ax
    ret

TOASTSTR bz_t_shell, 'Bonanza: bad shell part'

; -----------------------------------------------------------------------------
; THE GAME'S BOOKS (SPEC.md 128.14.3.1, 128.14.3.3)
; -----------------------------------------------------------------------------
; bz_post - after the frame loop, IN the bracket (bzvideo.inc), so the face the
; kernel's restore paints is the new one: what the run just did, in memory
; only.  B: its RESULTS page.  A play or a replay: the held log's line (line
; 6).  A PLAY alone: in a tour, its time entered (a finish) or the tour
; STOPPED (Esc, F, Alt+Enter); and a best, when it finished with the course's
; own ball under the 65,535-step clamp - and the tour's, at its last (BZ_NTOUR's).
; [bz_newb] = 1 when a best was set: bz_dsave writes the file on the desktop.
; Preserves nothing.
bz_post:
    mov al, [bz_res]            ; B and D: their results, when they ran to
    test byte [bz_mode], 1      ; their ends (D's line 3 names the demo, and
    jz .snap                    ; whether it measured all of it: bz_dtr)
    mov [bz_page], al
    ret
.snap:
    mov byte [bz_lsv], 1        ; THE LINE: the course, its steps (clamped
    mov al, [bz_crs]            ; to a word), its falls (to four digits),
    mov [bz_lsk], al            ; its flags reached and how it ended
    mov ax, [bz_nstep]
    cmp word [bz_nstep + 2], 0
    je .n
    mov ax, 0ffffh
.n:
    mov [bz_lsn], ax
    mov ax, [bz_nfall]          ; (a fall into a pit or a shatter: every
    cmp ax, BZ_FALLMAX          ; respawn but a RETURN)
    jbe .f
    mov ax, BZ_FALLMAX
.f:
    mov [bz_lsf], ax
    xor ax, ax
    mov ah, [bz_cksn]
.c:
    shl ah, 1
    adc al, 0
    or ah, ah
    jnz .c
    mov [bz_lsc], al
    mov al, [bz_goal]           ; 0 stopped, 1 the goal line, 2 holed out (a
    add al, [bz_hid]            ; holed ball has finished): the GOAL STEP, not
    test byte [bz_tout], 1      ; bz_fin - an Esc in the goal's frame is read
    jz .lse                     ; first, and the run still finished; 3 the
    mov al, 3                   ; TIMEOUT (wave 7, 128.18.4)
.lse:
    mov [bz_lsend], al
    cmp byte [bz_mode], 0       ; a replay posts nothing
    jne .out
    call bz_intour
    jnc .best
    cmp byte [bz_goal], 0
    jne .enter
    mov byte [bz_tour], BZ_NTOUR + 2 ; stopped: no total is entered
    ret
.enter:
    mov bl, [bz_tour]           ; (bz_crs is the tour's course k)
    xor bh, bh
    shl bx, 1
    mov ax, [bz_lsn]
    mov [bz_ttime - 2 + bx], ax
    mov ax, [bz_lsf]
    mov [bz_tfall - 2 + bx], ax
    inc byte [bz_tour]
    cmp byte [bz_tour], BZ_NTOUR + 1
    jne .best
    call bz_ttotal              ; the fifth: the total, DX:AX
    or bl, bl
    jnz .best                   ; (one at the clamp: never kept)
    mov cx, [bz_dat + BZD_TOUR + 2]
    mov bx, [bz_dat + BZD_TOUR + 4]
    mov si, cx
    or si, bx
    jz .tset                    ; no best tour yet
    cmp dx, bx
    ja .best
    jb .tset
    cmp ax, cx
    jae .best
.tset:
    mov [bz_dat + BZD_TOUR + 2], ax
    mov [bz_dat + BZD_TOUR + 4], dx
    mov byte [bz_newb], 1
.best:
    cmp byte [bz_goal], 0       ; THE COURSE'S BEST: a finish, started with
    je .out                     ; the course's own ball, under the clamp, and
    mov bl, [bz_crs]            ; under the best (or none yet)
    xor bh, bh
    mov al, [bz_cballs + bx]
    cmp al, [bz_rlog + BZR_MAT]
    jne .out
    mov ax, [bz_lsn]
    cmp ax, 0ffffh
    je .out
    mov si, bx                  ; entry K: bz_dat + BZD_ENT + 6K
    shl si, 1
    add si, bx
    shl si, 1
    mov cx, [bz_dat + BZD_ENT + 2 + si]
    jcxz .set
    cmp ax, cx
    jae .out
.set:
    mov [bz_dat + BZD_ENT + 2 + si], ax
    mov ax, [bz_lsf]
    mov [bz_dat + BZD_ENT + 4 + si], ax
    mov byte [bz_newb], 1
.out:
    ret

; bz_dload - the entry proc's read of BONANZA.DAT (SPEC.md 128.14.3.3), and
; [bz_dat] made this build's whole image whatever it found.  The file is
; HOSTILE (§19): exactly BZD_FILE bytes and `BZS4` (no older layout is read,
; 128.22.5), then bz_dchk's whole-file checks
; (128.14.17 item 6) - any failure and it is treated as ABSENT; then
; bz_dnorm keeps an entry only under this build's identity with a best 1 -
; 65,534.  A missing file or folder is the first run: silent.  kern_small
; refuses at the launch keys (128.1), so it reads nothing.  Preserves nothing.
bz_dload:
    xor cl, cl
    cmp byte [bz_small], 0
    jne bz_dnorm
    push es
    push ds
    pop es
    mov si, bz_s_dat
    mov bx, bz_dat
    mov cx, BZD_FILE
    xor dx, dx
    call od_read                ; (a file over BZD_FILE bytes is FERR_BIG before
    pop es                      ; any data is read: the image is untouched)
    mov cl, 0
    jc bz_dnorm
    or dx, dx
    jnz bz_dnorm
    cmp ax, BZD_FILE            ; save v4 (128.22.5): `BZS4`, exactly one sector; any
    jne bz_dnorm                ; other length (an older layout too) is unrecognised
    cmp word [bz_dat + 2], 'S4'
    jne bz_dnorm
    call bz_dchk
; CL = 1: keep what this build can file; 0: nothing (the first run's image).
; A file written under OTHER PHYSICS (+5 not this build's BZ_PHYSV: a 5b
; file's 0 among them, which is never BZ_PHYSV) keeps nothing either: its
; bests were times under other physics (SPEC.md 128.16.9) - the identities
; filed are this build's whatever it held, so that is the first run's image.
%if BZ_PHYSV == 0
 %error "BZ_PHYSV 0 is the unset value a 5b BONANZA.DAT holds (SPEC.md 128.16.9)"
%endif
bz_dnorm:
    or cl, cl                   ; a file refused whole keeps no slot either
    jnz .sl
    call bz_dslz
.sl:
    call bz_dslots              ; save v2 (128.19.6): each slot judged alone,
    cmp byte [bz_dat + 5], BZ_PHYSV ; physics or not (a game is no time)
    je .phys
    xor cl, cl
.phys:
    mov word [bz_dat], 'BZ'     ; `BZS4`, the count and BZ_PHYSV, two zero bytes
    mov word [bz_dat + 2], 'S4'
    mov word [bz_dat + 4], BZ_NCRS | (BZ_PHYSV << 8)
    mov word [bz_dat + 6], 0
    mov si, bz_dat + BZD_ENT
    xor bx, bx                  ; BX = 2K
.e:
    xor ax, ax                  ; the identity entry K is filed under: 0 for
    cmp bx, 2 * BZ_NCRS         ; BENCH's and past the courses
    jae .id
    or bx, bx
    jz .id
    mov ax, [bz_cids + bx]
.id:
    or ax, ax                   ; BENCH's entry and those past the courses are
    jz .clr                     ; ALWAYS zero, whatever the file filed under
    or cl, cl                   ; identity 0 there (a count-8 file's entry 6
    jz .clr                     ; would otherwise be kept, then written under
                                ; this build's count, and the next read would
                                ; refuse the whole file); a course identity is
                                ; never 0 (bbcourse asserts it)
    cmp ax, [si]                ; a course rebuilt with another identity
    jne .clr                    ; loses its best by itself
    mov dx, [si + 2]
    dec dx                      ; a best 1 - 65,534
    cmp dx, 0fffdh
    jbe .keep
.clr:
    mov word [si + 2], 0
    mov word [si + 4], 0
.keep:
    mov [si], ax
    add si, BZD_ENTB
    inc bx
    inc bx
    cmp bx, 2 * BZD_NENT
    jb .e
    or cl, cl                   ; THE TOUR: this build's XOR and a total 1 -
    jz .tclr                    ; BZ_TOURMAX (393,204)
    cmp word [bz_dat + BZD_TOUR], BZ_CRS_TOURX
    jne .tclr
    mov ax, [bz_dat + BZD_TOUR + 2]
    mov dx, [bz_dat + BZD_TOUR + 4]
    sub ax, 1
    sbb dx, 0
    jc .tclr
    cmp dx, (BZ_TOURMAX - 1) >> 16
    ja .tclr
    jb .tok
    cmp ax, (BZ_TOURMAX - 1) & 0ffffh
    jbe .tok
.tclr:
    xor ax, ax
    mov [bz_dat + BZD_TOUR + 2], ax
    mov [bz_dat + BZD_TOUR + 4], ax
.tok:
    mov word [bz_dat + BZD_TOUR], BZ_CRS_TOURX
    ret

; bz_dchk - BONANZA.DAT's header and entries in [bz_dat], checked IN FULL
; (SPEC.md 128.14.17 item 6, 128.22.5): `BZ` (+2 `S4`: bz_dload matched it
; with the length); the count it was written with 1 - BZD_NENT; +6 - +7 zero
; (+5, the physics, any value: bz_dnorm judges it, 128.16.9); every entry's
; falls at most 9,999; every UNUSED entry (BENCH's, and K at or past the
; count) all zero.  The tour is bz_dnorm's, the slots bz_dslots'.  -> CL = 1
; it passes, 0 it is refused whole.  Clobbers AX, BX, SI.
bz_dchk:
    xor cl, cl
    cmp word [bz_dat], 'BZ'     ; (+2 `S4`: bz_dload matched it with the
    jne .out                    ; length)
    mov al, [bz_dat + 4]
    dec al
    cmp al, BZD_NENT
    jae .out
    inc ax
    cmp word [bz_dat + 6], 0
    jne .out
    mov si, bz_dat + BZD_ENT
    xor bl, bl                  ; K
.e:
    cmp word [si + 4], BZ_FALLMAX
    ja .out
    or bl, bl
    jz .z
    cmp bl, al
    jb .n
.z:
    cmp word [si], 0
    jne .out
    cmp word [si + 2], 0
    jne .out
    cmp word [si + 4], 0
    jne .out
.n:
    add si, BZD_ENTB
    inc bx
    cmp bl, BZD_NENT
    jb .e
    inc cx
.out:
    ret

; bz_dsave - on the desktop after a launch: when the play set a best, the
; BZD_FILE bytes to SYSTEM\APPDATA\BONANZA.DAT on the package's own volume (os88data.inc:
; the session's first save a full write, every later one a sector).  A save
; that fails - no folder, write-protected, full - toasts ONCE a session and
; the bests stay in memory (SPEC.md 128.14.3.3).  The save MERGES: the file is
; read again first (bz_dload, as hostile as at the entry) and the smaller best
; of the two kept per entry and for the tour, so a second instance - a
; double-clicked .BZR opens one - never overwrites the first's bests with its
; older copy.  Preserves nothing.
bz_dsave:
    mov al, [bz_newb]           ; a best, or the game's slot (save v2,
    or al, [bz_gsave]           ; 128.19.6)
    jz .out
    mov byte [bz_gsave], 0
    push es
    push ds
    pop es
    mov si, bz_dat              ; ours aside, the disk's read and made this
    mov di, bz_dmine            ; build's image (any failure: the first run's)
    mov cx, BZD_FILE / 2
    rep movsw
    call bz_dload               ; (preserves ES)
    call bz_dslot               ; THE SLOT PLAYED IS OURS (SI), the other two
    mov di, si                  ; the disk's
    add si, bz_dmine - bz_dat
    mov cx, BZD_SLOTB / 2
    rep movsw
    mov si, bz_dmine + BZD_ENT
    mov di, bz_dat + BZD_ENT
    mov cx, BZD_NENT            ; per entry (both carry this build's identities
.m:                             ; and zeros where no best is: 0 - 1 is the
    mov ax, [si + 2]            ; largest, so "none" never wins)
    dec ax
    mov dx, [di + 2]
    dec dx
    cmp ax, dx
    jae .mn
    mov ax, [si + 2]
    mov [di + 2], ax
    mov ax, [si + 4]
    mov [di + 4], ax
.mn:
    add si, BZD_ENTB
    add di, BZD_ENTB
    loop .m
    mov ax, [bz_dmine + BZD_TOUR + 2] ; the tour's total, 32 bits, the same way
    mov dx, [bz_dmine + BZD_TOUR + 4]
    sub ax, 1
    sbb dx, 0
    mov bx, [bz_dat + BZD_TOUR + 2]
    mov cx, [bz_dat + BZD_TOUR + 4]
    sub bx, 1
    sbb cx, 0
    cmp dx, cx
    ja .tk
    jb .tm
    cmp ax, bx
    jae .tk
.tm:
    add ax, 1
    adc dx, 0
    mov [bz_dat + BZD_TOUR + 2], ax
    mov [bz_dat + BZD_TOUR + 4], dx
.tk:
    call bz_dwrite
    pop es
    jnc .out
    cmp byte [bz_datw], 0
    jne .out
    mov byte [bz_datw], 1
    mov si, bz_t_nosave
    jmp bz_toast
.out:
    ret

; bz_dwrite - the image WHOLE to BONANZA.DAT, one od_write, no merge and no
; toast (the game's life at a course's entry, inside the bracket: SPEC.md
; 128.19.6).  CF = 1 refused, and [bz_dwf] = 1 until a write is not (the info
; card's NOT SAVED, 128.22.6).  Preserves ES.
bz_dwrite:
    push es
    push ds
    pop es
    mov si, bz_s_dat
    mov bx, bz_dat
    mov cx, BZD_FILE
    mov di, bz_datst
    call od_write
    pop es
    mov al, 0                   ; (MOV keeps CF)
    rcl al, 1                   ; AL = CF ...
    mov [bz_dwf], al
    shr al, 1                   ; ...and CF again
    ret

; bz_dslot - SI = the slot played's offset in [bz_dat].  Preserves all else.
bz_dslot:
    push ax
    mov al, [bz_slot]
    mov ah, BZD_SLOTB
    mul ah
    add ax, bz_dat + BZD_SLOT
    xchg ax, si
    pop ax
    ret

; bz_dslz - every slot emptied.  Preserves all but the flags.
bz_dslz:
    push ax
    push cx
    push di
    push es
    push ds
    pop es
    mov di, bz_dat + BZD_SLOT
    mov cx, BZD_NSLOT * BZD_SLOTB / 2
    xor ax, ax
    rep stosw
    pop es
    pop di
    pop cx
    pop ax
    ret

; bz_dslots - each SLOT judged alone (save v4, SPEC.md 128.22.5): EMPTIED when
; its lives are over BZ_LIVES, +1 has a bit but the mode's, +3 is not zero,
; a route TAKEN is not one OPENED, its exits found or its bests past the
; courses (K at or past BZ_NCRS) are not zero, or - it having lives - pad 0
; is not open, it is
; not this build's pathway's, its pad is not one of the pathway's
; (BZD_NPAD), or - TIMED - its pad is not open (EXPLORE rests on any pad:
; every one is open to it, none in the open set).  An empty slot (lives 0)
; keeps its exits found.  Preserves all but the flags.
bz_dslots:
    push ax
    push bx
    push cx
    push di
    push si
    mov si, bz_dat + BZD_SLOT
    mov bl, BZD_NSLOT
.s:
    mov al, [si]                ; lives
    cmp al, BZ_LIVES
    ja .bad
    test byte [si + 1], 0feh    ; (+1: bit 0 the MODE, 8c)
    jnz .bad
    cmp byte [si + 3], 0
    jne .bad
    mov ax, [si + BZD_SROPN]    ; a route taken was opened: TAKEN & ~OPENED
    not ax
    test ax, [si + BZD_SRTAK]
    jnz .bad
    mov ax, [si + BZD_SROPN + 2]
    not ax
    test ax, [si + BZD_SRTAK + 2]
    jnz .bad
    lea di, [si + BZD_SEXIT + 2 * BZ_NCRS] ; the exits found and the bests of
    mov cx, BZ_NEXITPAD         ; courses that are not here are zero
    call bz_dzero
    jnz .bad
    lea di, [si + BZD_SBEST + 2 * BZ_NCRS]
    mov cx, BZ_NEXITPAD
    call bz_dzero
    jnz .bad
    cmp byte [si], 0
    je .n
    test byte [si + BZD_SOPEN], 1 ; a game with lives has pad 0 open ...
    jz .bad
    mov ax, [bz_cids + 2 * BZ_CRS_PATH] ; ...on this build's pathway ...
    cmp ax, [si + BZD_SID]
    jne .bad
    mov al, [si + BZD_SPAD]     ; ...its pad one of the pathway's (the
    cmp al, BZD_NPAD            ; loop indexes the part's tables by it) ...
    jae .bad
    test byte [si + 1], 1       ; ...and, TIMED, an open one (EXPLORE plays
    jnz .n                      ; any pad, 128.19.8: none of them in the set)
    push bx
    call bz_dwbit               ; AL the mask, BX the byte
    test al, [si + bx + BZD_SOPEN]
    pop bx
    jnz .n
.bad:
    mov di, si
    push es
    push ds
    pop es
    mov cx, BZD_SLOTB / 2
    xor ax, ax
    rep stosw
    pop es
.n:
    add si, BZD_SLOTB
    dec bl
    jnz .s
    pop si
    pop di
    pop cx
    pop bx
    pop ax
    ret

; bz_dzero - ZF = 1 when the CX words at DS:DI are all zero (CX 0: they are).
; Preserves all but CX, DI.
BZ_NEXITPAD equ BZ_CRS_MAX - BZ_NCRS ; the words a slot's tables hold past the courses
bz_dzero:
    push ax
    xor ax, ax                  ; (ZF = 1 for CX = 0)
.l:
    jcxz .out
    mov ax, [di]
    inc di
    inc di
    or ax, ax
    jnz .out
    dec cx                      ; (ZF = 1 when it reaches 0)
    jmp short .l
.out:
    pop ax
    ret

TOASTSTR bz_t_nosave, 'Best times not saved'

%define OD_TVOL bz_homevol      ; the volume BONANZA.O88 was launched from,
%include "os88data.inc"         ; banked at the entry (128.14.7.6), not where a
                                ; dialog has moved the instance since

; -----------------------------------------------------------------------------
; RECORDED DEMOS ON THE DISK (SPEC.md 128.14.7): W saves the held log, L loads
; one through the Open dialog, a double-clicked .BZR opens with BONANZA, V
; copies a shipped demo part into the log, D benchmarks it - and HOME, where
; every part is read from (128.14.7.6).
; -----------------------------------------------------------------------------
; bz_home - stand where BONANZA.O88 was launched from before a part is read out
; of it: op_fetch reads the package BY NAME in the instance's folder, which the
; Save and Open dialogs and a double-clicked document MOVE (SPEC.md 38.10).
; OSAPI_FILE_HERE is no I/O, so a fetch from home costs a compare; a move is a
; quiet OSAPI_FILE_GOTO_QM each way (PIXEL's px_pfetch).  CF = 1: home cannot
; be stood in (its disk is out) - toasted, NOTHING moved, nothing is to be
; fetched (a part read out of whatever BONANZA.O88 stands here would be worse).
; [bz_hmov] = 1 when it moved, for bz_back.  Preserves all but AX and the flags.
bz_home:
    push bx
    push cx
    push dx
    push si
    push di
    push es
    mov byte [bz_hmov], 0
    call OSAPI_FILE_HERE
    mov [bz_awdir], dx
    mov [bz_awvol], bl
    cmp dx, [bz_homedir]
    jne .go
    cmp bl, [bz_homevol]
    je .out                     ; (equal: CF = 0)
.go:
    mov dx, [bz_homedir]
    mov bl, [bz_homevol]
    call OSAPI_FILE_GOTO_QM
    jc .refused
    mov byte [bz_hmov], 1
    jmp short .out              ; (CF = 0)
.refused:
    mov si, bz_t_out
    call bz_toast
    stc
.out:
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    ret

; bz_back - back where bz_home found the user, so the next dialog opens in the
; folder last used.  Preserves every register and the flags.
bz_back:
    pushf
    cmp byte [bz_hmov], 0
    je .out
    mov byte [bz_hmov], 0
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    mov dx, [bz_awdir]
    mov bl, [bz_awvol]
    call OSAPI_FILE_GOTO_QM     ; (a failure moved nothing: we stay home)
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
.out:
    popf
    ret

; S on the desktop: the sound's own key (bzsound.inc bzs_skey), whose title is
; fetched - so at home, as bz_launch's fetches are (SPEC.md 128.14.10's two
; sound fetches: bzs_gfetch inside bz_launch's home, bzs_dstart here and in
; the entry proc, which runs at home)
bz_skey:
    call bzs_toggle             ; (on or off since SPEC.md 128.26.5)
    jmp bz_line4

; CF = 1 on kern_small, its refusal toasted (SPEC.md 128.1, 128.14.3.4).
; Clobbers what bz_toast does.
bz_bigok:
    cmp byte [bz_small], 0
    je .out                     ; (CF = 0)
    mov si, bz_t_small
    call bz_toast
    stc
.out:
    ret

; D (one press): THE DEMO BENCHMARK, bz_mode 3 - the held log replayed and
; measured (SPEC.md 128.14.7.3)
bz_dkey_d:
    call bz_bigok
    jc .out
    call bz_rhave
    jne .out
    mov al, 3
    mov ah, [bz_rlog + BZR_CRS]
    jmp bz_go
.out:
    ret

; W (one press): the held log through the SAVE dialog as `<NAME>.BZR` (SPEC.md
; 128.14.7.1); bz_wdone writes it.  A tour's held log is the course just
; played.  A dialog already up refuses, and that dialog is the answer.
bz_wkey:
    call bz_bigok
    jc .out
    call bz_rhave
    jne .out
    mov al, [bz_rlog + BZR_CRS] ; (the session's log: its course is in range)
    mov ah, BZ_CRS_NAMEB
    mul ah
    add ax, bz_cnames
    xchg ax, si
    mov di, bz_dname
.c:
    lodsb
    or al, al
    jz .e
    mov [di], al
    inc di
    jmp .c
.e:
    mov word [di], '.B'
    mov word [di + 2], 'ZR'
    mov byte [di + 4], 0
    mov al, FDLG_SAVE
    mov si, bz_dname
    mov di, bz_wdone
.dlg:
    mov bx, [bz_win]
    call OSAPI_FILE_DLG
.out:
    ret

; L (one press): a log through the OPEN dialog (SPEC.md 128.14.7.2)
bz_lkey:
    call bz_bigok
    jc bz_wkey.out
    mov al, FDLG_OPEN
    xor si, si
    mov di, bz_ldone
    jmp bz_wkey.dlg

; W's completion (SPEC.md 38.6: AL = 1, DI = the name in the kernel's segment,
; ES; the instance stands in the folder chosen): the log's bytes AS THEY ARE -
; the file IS the log, `16 + 2 N` or `16 + 3 N` bytes - and a toast either way
bz_wdone:
    call bz_gname
    push ds
    pop es
    mov di, bz_rlog
    call bz_esz                 ; CX = the held log's bytes
    mov si, bz_dname
    mov bx, bz_rlog
    xor dx, dx
    call OSAPI_FILE_WRITE
    mov si, bz_t_saved
    jnc bz_toast
; AX = a FERR_*: the kernel's own words for it, toasted
bz_ftoast:
    call OSAPI_FERR_TEXT
    xor cx, cx
    call OSAPI_TOAST
    ret

; L's completion (AL = 0, DI = the name, DX:CX its size, which is what the
; read will deliver, 38.6.1).  Refused BEFORE THE DISK IS TOUCHED, in this
; order: not `.BZR`, then a size under 16 or over 4,096 - `Not a Bonanza
; demo`; then bz_lfile claims exactly the size, reads, checks and copies.
bz_ldone:
    push cx
    push dx
    call bz_gname
    pop dx
    pop cx
    call bz_isbzr
    jc .not
    or dx, dx
    jnz .not
    cmp cx, BZR_RUNS
    jb .not
    cmp cx, BZR_SIZE
    ja .not
    xor al, al                  ; the size is the dialog's: exact
    call bz_lfile
    jc .out
    jmp bz_dheld
.not:
    mov si, bz_t_notbzr
    jmp bz_toast
.out:
    ret

; ES:DI = a NUL name of at most 12 characters (the kernel's) -> [bz_dname].
; Clobbers AX, CX, SI, DI.
bz_gname:
    mov si, bz_dname
    mov cx, 12
.c:
    mov al, [es:di]
    inc di
    mov [si], al
    inc si
    or al, al
    jz .out
    loop .c
    mov [si], cl                ; (a 12-character name: its NUL)
.out:
    ret

; CF = 0 when [bz_dname]'s extension is `BZR`.  Clobbers AL, SI.
bz_isbzr:
    mov si, bz_dname
.f:
    lodsb
    or al, al
    jz .no
    cmp al, '.'
    jne .f
    cmp word [si], 'BZ'
    jne .no
    cmp word [si + 2], 'R'      ; `R` and the NUL
    je .out                     ; (equal: CF = 0)
.no:
    stc
.out:
    ret

; ES:DI = a log -> CX = its bytes, `16 + 2 N` or with TILT `16 + 3 N`.
; Clobbers AX.
bz_esz:
    mov cx, [es:di + BZR_NRUN]
    mov ax, cx
    shl cx, 1
    test byte [es:di + BZR_FLAGS], BZR_TILT
    jz .p
    add cx, ax
.p:
    add cx, BZR_RUNS
    ret

; -----------------------------------------------------------------------------
; bz_lfile - a demo FILE, which is HOSTILE (SPEC.md 19, 128.14.7.2): [bz_dname]
; in the instance's folder, CX its size (L: the dialog's, 16 - 4,096, AL = 0)
; or the read's capacity (the double-click: 4,096, AL = 1, 128.14.7.5), read
; into a TRANSIENT claim of exactly CX bytes (pinned, held for this call
; alone) and CHECKED IN FULL (bz_lchk) before a byte reaches bz_rlog, so a
; refused file leaves the session's log as it was and fetches no part.  The
; claim is an LDT selector on kern_mega: read into at ES:0, checked through
; [es:], copied whole - never added to (128.14.13).  CF = 0: the log is the
; file's, [bz_lsv] 2 and [bz_lfn] its name; CF = 1: refused and toasted.
; Preserves nothing.
; -----------------------------------------------------------------------------
bz_lfile:
    mov [bz_lcap], al
    mov [bz_lfsz], cx
    mov ax, cx
    add ax, 15
    mov cl, 4
    shr ax, cl
    push ax                     ; ASKED first (os88api.inc, SPEC.md 38.6): a
    mov bl, MEMP_AVAIL          ; claim that fails SHEDS the disk caches on its
    call OSAPI_MEM_P            ; way down, so a size past the largest run is
    pop dx                      ; refused with nothing claimed, shed or read
    mov si, bz_t_nomem
    cmp ax, dx
    jb .toast
    xchg ax, dx
    mov bl, MEMP_CLAIM          ; EXACTLY the size
    call OSAPI_MEM_P
    jc .toast

    mov [bz_lseg], dx
    push es
    mov es, dx
    xor bx, bx
    mov cx, [bz_lfsz]
    xor dx, dx
    mov si, bz_dname
.read:                          ; (a row's breakpoint: the disk is touched here)
    call OSAPI_FILE_READ        ; DX:AX = the bytes read (at most CX)
    jc .rerr
    mov si, bz_t_dmg
    or dx, dx
    jnz .ref
    cmp byte [bz_lcap], 0
    je .exact
    mov [bz_lfsz], ax            ; the double-click: the size IS the bytes read,
    mov si, bz_t_notbzr         ; refused under 16
    cmp ax, BZR_RUNS
    jb .ref
    jmp short .chk
.exact:
    cmp ax, [bz_lfsz]            ; 1: the bytes the dialog said
    jne .ref
.chk:
    call bz_lchk                ; 2 - 8
    or si, si
    jnz .ref
    mov cx, [bz_lfsz]            ; PASSED: the bytes into the log
    cld
    push ds
    push ds
    push es
    pop ds                      ; DS = the claim, ES = ours
    pop es
    xor si, si
    mov di, bz_rlog
    rep movsb
    pop ds
    call .free
    pop es
    mov byte [bz_rown], 0       ; (a file's log is not the player's to save again)
    mov byte [bz_lsv], 2        ; the face's log line: the file's name
    mov si, bz_dname
    mov di, bz_lfn
    mov cx, 13
.n:
    lodsb
    mov [di], al
    inc di
    loop .n
    clc
    ret
.rerr:
    mov si, bz_t_notbzr         ; FERR_BIG: over the capacity, decided from
    cmp ax, FERR_BIG            ; the directory entry before any data I/O
    je .ref
    call .free
    pop es
    call bz_ftoast              ; a disk's refusal, in the kernel's words
    stc
    ret
.ref:
    call .free
    pop es
.toast:
    call bz_toast
    stc
    ret
.free:
    mov dx, [bz_lseg]
    call OSAPI_MEM_FREE
    mov word [bz_lseg], 0
    ret

; bz_lchk - 128.14.7.2's checks 2 - 8 on the log at ES:0, [bz_lfsz] bytes (16 -
; 4,096: check 1 is the caller's, so the header is inside it).  -> SI = 0 it
; passed, else the toast: `Demo from other physics` (5) or `Damaged demo file`.
; K indexes BZ_CRS_IDS only once bounded, and no run is read before N is tied
; to the length.  Clobbers AX, BX, CX, DX, DI, BP (a register here: no [bp]).
bz_lchk:
    mov si, bz_t_dmg
    cmp word [es:0], 'BZ'       ; 2: the magic
    jne .out
    cmp word [es:2], 'R1'
    jne .out
    mov bl, [es:BZR_CRS]        ; 3: the course, the material, the flags
    cmp bl, BZ_NCRS
    jae .out
    cmp byte [es:BZR_MAT], BZ_NMAT
    jae .out
    test byte [es:BZR_FLAGS], ~(BZR_DONE | BZR_TRUNC | BZR_TILT) & 0ffh
    jnz .out
    xor bh, bh                  ; 4: the course's IDENTITY, this build's
    shl bx, 1
    mov ax, [bz_cids + bx]
    cmp ax, [es:BZR_ID]
    jne .out
    mov si, bz_t_phys           ; 5: the PHYSICS identity
    cmp byte [es:BZR_PHYS], BZ_PHYSV
    jne .out
    mov si, bz_t_dmg
    mov cx, [es:BZR_NRUN]       ; 6: N >= 1, the size exactly 16 + w N
    jcxz .out
    cmp cx, (BZR_SIZE - BZR_RUNS) / 2
    ja .out
    mov ax, cx
    shl ax, 1
    mov dx, 2                   ; DX = w
    test byte [es:BZR_FLAGS], BZR_TILT
    jz .w
    add ax, cx
    inc dx
.w:
    add ax, BZR_RUNS
    cmp ax, [bz_lfsz]
    jne .out
    xor ax, ax                  ; BP:AX = the runs' counts, summed in 32 bits
    xor bp, bp
    mov di, BZR_RUNS
.run:
    test byte [es:di], 80h      ; 8: a key byte's bit 7 clear ...
    jnz .out
    cmp dl, 3
    jne .cnt
    mov bl, [es:di + 1]         ; ...a tilt byte's nibbles each 0 - 8 ...
    cmp bl, (BZ_LVLMAX + 1) << 4
    jae .out
    and bl, 0fh
    cmp bl, BZ_LVLMAX
    ja .out
.cnt:
    add di, dx
    mov bl, [es:di - 1]         ; ...a count 1 - 255
    or bl, bl
    jz .out
    xor bh, bh
    add ax, bx
    adc bp, 0
    loop .run
    cmp ax, [es:BZR_STEPS]      ; 7: the steps, the runs' sum
    jne .out
    cmp bp, [es:BZR_STEPS + 2]
    jne .out
    xor si, si
.out:
    ret

; the entry proc's: the document this instance was launched to open (SPEC.md
; 54.5), READ AND CLEARED and its name copied out while ES is the kernel's -
; RECORDED only: bz_onwake reads it once the window is up (SPEC.md 54.10)
bz_argget:
    call OSAPI_ARG_FILE
    jc .out
    mov [bz_argdir], dx
    mov [bz_argvol], bl
    mov di, si
    call bz_gname
    mov byte [bz_argp], 1
.out:
    ret

; a DOUBLE-CLICKED .BZR (SPEC.md 128.14.7.5): no size comes with it, so the
; read is bounded by its CAPACITY - 4,096, FERR_BIG decided from the directory
; before any data is read - and its bytes are the size.  Not .BZR refused; the
; document's folder stood in; bz_lfile's claim, read, checks and copy; home
; again.  A refusal toasts and the window keeps no log.  kern_small (no
; associations, the game refused) reads nothing.  -> CF = 0 a log was loaded.
bz_argdemo:
    cmp byte [bz_small], 0
    jne .no
    call bz_isbzr
    mov si, bz_t_notbzr
    jc .toast
    mov dx, [bz_argdir]
    mov bl, [bz_argvol]
    call OSAPI_FILE_GOTO_QM
    jc .ftoast
    mov al, 1
    mov cx, BZR_SIZE
    call bz_lfile
    pushf
    mov dx, [bz_homedir]
    mov bl, [bz_homevol]
    call OSAPI_FILE_GOTO_QM
    popf
    ret
.toast:
    call bz_toast
    jmp short .no
.ftoast:
    call bz_ftoast
.no:
    stc
    ret

; W_ONWAKE (SPEC.md 74.1): a document launch's SECOND phase (SPEC.md 54.10) -
; the window is on the glass, the gfx lock is not held, and the file slots
; may be called.  A wake with no document pending is a stale kick: nothing.
; A log loaded is shown on the face's lines 5, 6 and 12 (bz_dheld).
bz_onwake:
    SAVE
    cmp byte [bz_argp], 0
    je .done
    mov byte [bz_argp], 0       ; (spent once, whatever its read does)
    call bz_argdemo
    jc .done
    call bz_dheld
.done:
    RESTORE
    ret

; V (one press, not in a tour): the next SHIPPED demo, 1 - 5 in turn, into the
; held log (SPEC.md 128.14.7.4) - its part fetched at home, copied whole (a
; PART is trusted: the tool checked it, 128.10.6.2) and dropped.  It replaces
; the session's last log, as a new play does.
bz_vkey:
    call bz_bigok
    jc .out
    call bz_home
    jc .out
    mov al, [bz_vk]
    add al, BZ_P_DEMO
    mov [bz_pc], al
    call op_fetch
    jc .back
    mov al, [bz_pc]
    call op_seg
    push es
    mov es, ax
    xor di, di
    call bz_esz
    cld
    push ds
    push ds
    push es
    pop ds                      ; DS = the part, ES = ours
    pop es
    xor si, si
    mov di, bz_rlog
    rep movsb
    pop ds
    pop es                      ; (op_fetch left ES the part's own selector:
    push ds                     ; op_drop restores its caller's ES after the
    pop es                      ; free, a #GP on kern_mega - ES = ours, as
    mov al, [bz_pc]             ; bz_fullscreen's .drop; the final pass of
    call op_drop                ; wave 4: bonanzamega's fault in V)
    mov byte [bz_lsv], 3
    inc byte [bz_vk]
    cmp byte [bz_vk], BZ_NDEMO
    jb .shown
    mov byte [bz_vk], 0
.shown:
    call bz_back
    jmp short bz_dheld
.back:
    jmp bz_back                 ; (op_fetch toasted why)
.out:
    ret

; a new held log (L, V): the lines that name it and offer its keys - the demo
; keys, the log's line, and the tour line's refused-replay reason, now stale
bz_dheld:
    mov byte [bz_err], 0
    mov si, bz_heldl
    jmp bz_redraw
bz_heldl:   db 5, 6, BZ_LTOUR, 0ffh

; T (one press, in a tour too): the control, KEYS or MOUSE (SPEC.md 128.14.8)
bz_tkey:
    xor byte [bz_ctl], 1
    mov si, bz_tlines
    jmp bz_redraw
bz_tlines:  db 3, 6, 0ffh

TOASTSTR bz_t_out, "Bonanza's disk is out"
TOASTSTR bz_t_saved, 'Demo saved'
TOASTSTR bz_t_notbzr, 'Not a Bonanza demo'
TOASTSTR bz_t_dmg, 'Damaged demo file'
TOASTSTR bz_t_phys, 'Demo from other physics'
TOASTSTR bz_t_nomem, 'Bonanza: no memory'

; --- the window -----------------------------------------------------------------
bz_tpl: dw 40, 24, 344, 168, bz_title, bz_cls
; its CLASS (SPEC.md 11.104): every handler; WF_OWNBG, the face paints every pixel
    OS88_CLASS bz_cls, WF_OWNBG | WF_SIZABLE, PAINT, bz_paint, ONKEY, bz_onkey, \
               ONCLICK, os88ui_btnclick, ONMOUSEUP, bz_onup, ONDRAG, bz_ondrag, \
               ABOUT, bz_about, ONTIMER, bz_ontimer, ONWAKE, bz_onwake
bz_title: db 'Bounce Bonanza',0
bz_credits: dw bz_title, bz_credit1, bz_ck1, bz_ck2, bz_ck3, bz_ck4, bz_ck5, bz_ck6, bz_ck7, bz_ck8, 0
bz_credit1: db 'Isometric rolling-ball game',0
bz_ck1:     db 'Arrows roll, Space hop',0       ; the player's keys no menu carries
bz_ck2:     db 'L.Shift grip, P pause',0        ; (SPEC.md 128.26.7)
bz_ck3:     db 'Bksp back to the flag',0
bz_ck4:     db 'Pad: Enter play, Space info',0
bz_ck5:     db 'Pad: V demo, F6 replay',0
bz_ck6:     db 'F5 save replay',0
bz_ck7:     db 'F or Alt+Enter: window',0
bz_ck8:     db 'Esc: map, or quit',0

bz_cnames:  BZ_CRS_NAMES        ; ...their NAMEs, BZ_CRS_NAMEB bytes each
bz_cballs:  BZ_CRS_BALLS        ; ...their balls, a byte each
bz_clims:   BZ_CRS_LIMS         ; ...their time limits, whole seconds of BZ_SECSTEPS
                                ; steps, a word each (0 none; wave 7, 128.18.3)
bz_cids:    BZ_CRS_IDS          ; ...their identities, a word each
bz_csongs:  BZ_CRS_SONGS        ; ...their songs, a byte each (wave 7, 128.18.6)
bz_cpals:   BZ_CRS_PALS         ; ...their CGA colour selects, a byte each (3D9h,
                                ; wave 6, SPEC.md 128.16.6: bz_vinit)
bz_s_dat:   db 'BONANZA.DAT', 0
%include "bzvideo.inc"
%include "bzcard.inc"           ; wave 8c (128.19.8): the cards
%include "bzgame.inc"
%include "bzwheel.inc"
%include "bzphys.inc"
%include "bzsound.inc"
%include "bzmenu.inc"           ; SPEC.md 128.26: the window's button, menus and replays
%if 4 * BZ_BOXB < 512
 %error "bz_hgen: BZ_HTAB's 512 bytes do not fit bz_boxbuf"
%endif

; --- the part table (SPEC.md 128.11.3.1, 20.12) --------------------------------
; 3 + BZ_NCRS + 1 + BZS_NSONG + BZ_NDEMO rows, in the Makefile's BZ_PARTS
; order, every one OP_LAZY | OP_COMP: the three balls, then each course
; (BZ_COURSES's order, bzcourse.inc's rows, every one the CGA's), the sound
; and its songs, and a shipped demo a tour course.  Fetched by bz_launch on the desktop (op_fetch,
; 1942's pattern) and dropped when the bracket returns.
OS88_PARTS_BEGIN 3 + BZ_NCRS + 1 + BZS_NSONG + BZ_NDEMO + 2 + 2 * BZ_TITLE
    OS88_PART OP_ASSET, OP_LAZY | OP_COMP   ; 0  BZBALR.BIN  rubber
    OS88_PART OP_ASSET, OP_LAZY | OP_COMP   ; 1  BZBALS.BIN  steel
    OS88_PART OP_ASSET, OP_LAZY | OP_COMP   ; 2  BZBALG.BIN  glass
    BZ_CRS_PARTS                            ; 3 + K: BZ<K>.BIN
    OS88_PART OP_ASSET, OP_LAZY | OP_COMP   ; BZ_P_SND: BZSND.BIN (128.20.3)
 %rep BZS_NSONG
    OS88_PART OP_ASSET, OP_LAZY | OP_COMP   ; BZ_P_SONG + S: BZM<S>.BIN
 %endrep
    BZ_DEMO_PARTS                           ; BZ_P_DEMO + K - 1: BZD<K>.BIN (128.14.7.4)
    OS88_PART OP_SEG, OP_LAZY | OP_COMP     ; BZ_P_SHELL: BZSHELL.BIN, far-called (128.19.2)
    OS88_PART OP_ASSET, OP_LAZY | OP_COMP   ; BZ_P_PATH: BZPATH.BIN, the pathway (128.19.5)
%if BZ_TITLE
    OS88_PART OP_ASSET, OP_LAZY | OP_COMP   ; BZ_P_TITLE: BZTITLE.BIN, the title (128.23)
    OS88_PART OP_ASSET, OP_LAZY | OP_COMP   ; BZ_P_TDEMO: BZTDEMO.BIN, its demos (128.23.3)
%endif
OS88_PARTS_END
%if BZ_P_DEMO != 3 + BZ_NCRS + 1 + BZS_NSONG || BZ_NDEMO != BZ_NCRS - 1
 %error "the demo rows follow the songs', one a tour course (SPEC.md 128.14.7.4)"
%endif

%define OS88UI_ABOUT
%define OS88UI_NOGLYPH          ; (the Play Game button alone: no box, no dot)
%define OS88UI_ABFIT            ; (the keys' card on a CGA content box, SPEC.md 128.26.7)
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
VAR bz_page,1                   ; the face's page: 0 MAIN, 1 RESULTS (128.14.3.2)
VAR bz_pgo,1                    ; 1: this key left RESULTS (or a refused replay):
                                ; bz_onkey repaints MAIN whole after it
VAR bz_pc,1                     ; the course's part row (BZ_P_CRS + K)
VAR bz_pb,1                     ; ...and the starting ball's (BZ_P_BALR + [bz_mat])
VAR bz_pbm,1                    ; the balls a launch fetches: a bit a material
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
VAR bz_shfp,4                   ; the shell part's far pointer (bz_shcall)
VAR bz_shpend,2                 ; byte 1: a paint put off while a course was held (a word: the run stays even)
; the game (wave 8b, SPEC.md 128.19.5): the pathway's state, held in memory
VAR bz_nopen,4                  ; a bit a pad: OPEN (pad 0 from a new game's start; a dword)
VAR bz_ndone,4                  ; ...and DONE (a finish in time)
VAR bz_nrop,4                   ; ...the routes OPENED (a bit a route)
VAR bz_nrtk,4                   ; ...and TAKEN (a secret's reveal; a subset)
VAR bz_ppad,1                   ; the pad the marble rests on (the slot's +2)
VAR bz_phold,1                  ; 1: the pathway's part is HELD (bz_cload, bz_phrel)
VAR bz_phre,1                   ; ...1 while the pathway is re-entered from the hold
VAR bz_phforce,1                ; HARNESS: nonzero never holds it (128.22.7); never set by the package
VAR bz_lives,1                  ; lives left (5 at a new game; 0 the game is over)
VAR bz_pwck,1                   ; wave 8R (128.22.4.4): the course Enter at a pad plays
VAR bz_nst,(BZ_NSIGN + 1) & ~1  ; each SIGN's pose (bz_ltrue's SIGN case, bz_nset; 128.22.4.1), even
VAR bz_ingame,1                 ; 1: inside the game's bracket (bz_fullscreen's rounds)
VAR bz_slot,1                   ; the save's slot played, 0 - 2 (8c chooses; 0 until then)
VAR bz_gsave,1                  ; 1: the game's slot to be written (bz_dsave)
VAR bz_retry,1                  ; wave 8c (128.19.8): 1 R on the game's pause card
VAR bz_xmode,1                  ; ...1 EXPLORE (the slot's mode, while the game plays; 0 else)
%if BZ_TITLE
VAR bz_tmode,1                  ; SPEC.md 128.23.4: 1 a TITLE DEMO plays, 2 a course demo of the title's chain
VAR bz_twhy,1                   ; ...why its play left: 'p' play, 27 Esc (leave), 1 a key in a course demo
VAR bz_tlast,1                  ; ...the title demo last shown (0FFh none)
VAR bz_tsel,1                   ; ...the one fetched
VAR bz_tgame,1                  ; ...1: a game was played (its slot written at the bracket's end)
VAR bz_tlfsr,2                  ; ...the title's LFSR (bz_trand)
VAR bz_tpad,1                   ; (the VARs stay even)
%endif
VAR bz_xarm,1                   ; ...1: X pressed once (the second erases the slot)
; THE WINDOW (SPEC.md 128.26): the button, the face's layout, the menus, the
; replays and the suspended bracket
VAR bz_dev,1                    ; HARNESS: 1 the instruments' keys and face (128.26.6); never set by the package
VAR bz_wtall,1                  ; 1: the TALL aspect (a display 300 lines or more)
VAR bz_btr,8                    ; the Play Game button: its rect, screen, inclusive
VAR bz_btfl,2                   ; ...its flags (OS88UI_DIS greyed)
VAR bz_wbn,2                    ; ...1 it is shown (0 under the instruments' face)
VAR bz_wty,2                    ; the face's layout (bzwface.inc): the title's top,
VAR bz_wtx,2                    ; its left, the ledge's left and top, the button
VAR bz_wlx,2                    ; content-relative, the band drawn (its first row
VAR bz_wly,2                    ; and rows), a picture row's first byte, and the
VAR bz_wbx0,2                   ; shifted slice's width, bytes, column, row and
VAR bz_wbx1,2                   ; rows to go
VAR bz_wby0,2
VAR bz_wby1,2
VAR bz_wy,2
VAR bz_wh,2
VAR bz_wsrc,2
VAR bz_wsw,2
VAR bz_wsb,2
VAR bz_wsc,2
VAR bz_wsr,2
VAR bz_wsn,2
VAR bz_earm,1                   ; the Erase armed, slot 1 - 3 (0 none)
VAR bz_susp,1                   ; BZ_SU_*: the bracket left for the window from (128.26.4)
VAR bz_towin,1                  ; 1: F or Alt+Enter asked for the window (bz_exitchk)
VAR bz_rsm,1                    ; 1: the next bz_play RESUMES a course (no bz_pinit, no new log)
VAR bz_rown,1                   ; 1: the held log is a play the player recorded (Save Replay's)
VAR bz_wpad,1                   ; (the VARs stay even)
VAR bz_rbest,2                  ; bz_rscan: the greatest number, its file's size,
VAR bz_rbsz,4                   ; and the course's name's tail, `NAMES.BZR`
VAR bz_rtail,10
; the pathway's play (wave 8R, SPEC.md 128.22.4: bonanza.asm's THE PATHWAY)
VAR bz_ptho,2                   ; the part's tables (BZC2 +42) ...
VAR bz_ptro,2                   ; ...their ROUTES ...
VAR bz_ptko,2                   ; ...and KEYS (bz_ppose's)
VAR bz_pws,4                    ; the FOLLOWER: s, 1/256 ground px along the route (24.8)
VAR bz_pwv,2                    ; ...v, 1/256 ground px a step (8.8)
VAR bz_pwL,2                    ; ...the route's length L, ground px
VAR bz_pwdk,2                   ; ...the segment holding s: its start D_k ...
VAR bz_pwln,2                   ; ...its length ...
VAR bz_pwp,2                    ; ...its first point (in the part) ...
VAR bz_pwpd,2                   ; ...and the next's distance (+6, or -6 walked B to A)
VAR bz_pwro,2                   ; ...a secret route's reveal distances (A to B)
VAR bz_pwcn,2                   ; the steps counted: the icon's interval, a gate's, the game over's
VAR bz_pwst,1                   ; BZ_PW_*: resting, rolling, a gate opening, the game over
VAR bz_pwq,1                    ; the play's end: 13 Enter (bz_pwck), 27 Esc, 'o' the game over, 0 else
VAR bz_pwev,1                   ; BZ_PE_*: what the last course left the pathway (0 none) ...
VAR bz_pwex,1                   ; ...a finish's exit
VAR bz_pwek,1                   ; FFh: Enter, Esc, Space or an arrow held since the course, the press or the info card
VAR bz_pwrt,1                   ; the route rolled (or a gate's) ...
VAR bz_pwrv,1                   ; ...1 travelled B to A
VAR bz_pwdst,1                  ; ...the pad it goes to
VAR bz_pwnl,1                   ; ...the segments after the one holding s
VAR bz_pwar,1                   ; ...1: this step ARRIVED
VAR bz_pwng,1                   ; ...the reveal groups to come (A to B), the next ...
VAR bz_pwrg,1
VAR bz_pwrs,1                   ; ...and the first one's sign
VAR bz_pwgs,1                   ; the gate opening's sign
VAR bz_pwis,1                   ; RESTING: the icon's sign (FFh none) ...
VAR bz_pwib,1                   ; ...its rest pose (1 on a hidden pad shown, else 0) ...
VAR bz_pwic,1                   ; ...its frame
VAR bz_pwpad,1                  ; (the VARs stay even)
VAR bz_inpause,1                ; ...1 while the pause card is up
VAR bz_freq,1                   ; ...1: the next frame a full write (a card drawn)
VAR bz_ff,2                     ; the kernel glyph table's first and last codes
VAR bz_font,8 * BZC_NGLYPH      ; the cards' glyphs, 32 - 95 (bzcard.inc)
VAR bz_kbuf,96                  ; a card's lines, built (bzcard.inc)
VAR bz_ikc,1                    ; the info card's course K ...
VAR bz_dwf,1                    ; 1: the last write of BONANZA.DAT was refused (bz_dwrite; the info card)
VAR bz_ibest,2                  ; ...and its best, steps
VAR bz_crdls,2                   ; bz_card's list, lines, widest + 2, first cell,
VAR bz_crdn,2                     ; height, first line, the row's bank and base,
VAR bz_crdw,2                    ; the glyph row
VAR bz_crdc0,2
VAR bz_crdh,2
VAR bz_crdy0,2
VAR bz_crdbk,2
VAR bz_crdbs,2
VAR bz_crdgr,2
; the game (SPEC.md 128.14.3): the tour, the held log's line, the bests
VAR bz_ttime,2 * BZ_NTOUR       ; the tour's steps a course, 0 none (bz_game
VAR bz_tfall,2 * BZ_NTOUR       ; clears both: keep them together) and falls
VAR bz_homedir,2                ; where BONANZA.O88 was launched from: its
                                ; folder (128.14.7.6) ...
VAR bz_lsn,2                    ; line 6: the last play's or replay's steps
VAR bz_lsf,2                    ; ...its falls (to 9,999)
VAR bz_dmine,BZD_FILE           ; bz_dsave's: ours, while the disk's is merged in
VAR bz_dat,BZD_FILE             ; BONANZA.DAT's image, always this build's whole
                                ; file (bz_dnorm): what the face shows and the
                                ; save writes
VAR bz_homevol,1                ; ...and its volume (os88data.inc's OD_TVOL)
VAR bz_tour,1                   ; 0 none, k 1 - BZ_NTOUR course k next or playing,
                                ; BZ_NTOUR + 1 finished, + 2 stopped (128.14.3.1)
VAR bz_lsv,1                    ; line 6: 1 = a play or a replay ran (bz_post)
VAR bz_lsk,1                    ; ...its course
VAR bz_lsc,1                    ; ...the flags it reached
VAR bz_lsend,1                  ; ...0 stopped, 1 the goal line, 2 the cup
VAR bz_newb,1                   ; 1: this launch's play set a best (bz_post)
VAR bz_datst,1                  ; od_write's state byte for BONANZA.DAT
VAR bz_datw,1                   ; 1: the failed save was toasted this session
VAR bz_pkey,1                   ; FFh while P is HELD since its last edge (PAUSE)
VAR bz_ptyp,1                   ; 1: bz_exitchk took a typed P (bz_kedge)
VAR bz_btyp,1                   ; ...and a typed Backspace (RETURN)
; the demos on the disk and the mouse (SPEC.md 128.14.7, 128.14.8)
VAR bz_awdir,2                  ; bz_home: where the user was, to go back to
VAR bz_lseg,2                   ; L's and the double-click's staging claim, 0 none
VAR bz_lfsz,2                    ; ...its size, then the bytes read
VAR bz_argdir,2                 ; the double-clicked document's folder ...
VAR bz_dname,14                 ; a demo file's name: W's default, the dialog's
                                ; answer, the double-click's (12 and a NUL)
VAR bz_lfn,14                   ; ...and the loaded log's, for the face's line 6
VAR bz_awvol,1                  ; ...bz_home's volume to go back to
VAR bz_hmov,1                   ; 1: bz_home moved the instance
VAR bz_argvol,1                 ; ...the document's volume
VAR bz_argp,1                   ; 1: a document came with the launch
VAR bz_lcap,1                   ; bz_lfile: 1 the read is bounded by its capacity
VAR bz_vk,1                     ; V: the next shipped demo, 0 - BZ_NDEMO - 1
VAR bz_ctl,1                    ; T: the control, 0 KEYS, 1 MOUSE (the session's)
VAR bz_dtr,1                    ; D stopped measuring at 65,535 frames (128.14.7.3)
VAR bz_rw,1                     ; the held log's run width: 2, or 3 with TILT
VAR bz_tilt,1                   ; the frame's TILT BYTE, capx << 4 | capy: 88h a
                                ; keyboard play's (bz_input, SPEC.md 128.14.8.2)
VAR bz_tby,1                    ; the STEP's tilt byte (bz_step: the play's
                                ; frame's, the replay's run's, 88h the autopilot's)
VAR bz_tanc,1                   ; 1: anchor the stick at the next frame
VAR bz_tarm,1                   ; 1: the stick has been in its dead zone
VAR bz_apilot,1                 ; a HARNESS byte, never set by the package: a
                                ; play takes its key bytes from the autopilot
                                ; (bzphys.inc bz_step; bonanzagame, 128.14.14)
VAR bz_tax,BZT_SIZE             ; the stick's x axis (bzgame.inc bz_tmouse) ...
VAR bz_tay,BZT_SIZE             ; ...and its y axis
%if bz_tfall != bz_ttime + 2 * BZ_NTOUR || (BZ_BSS & 1)
 %error "bz_game clears bz_ttime and bz_tfall as one run; the game's VARs stay even"
%endif
; the engine's (bzgame.inc's head documents the ones a harness reads)
BZ_GAME_VARS
BZ_PHYS_VARS
BZ_SND_VARS
VAR bz_osum,2 * BZ_OSROWS        ; the occluder rows' summary (bz_osmake): a row's greatest s', t'
%if BZ_TITLE
VAR bz_tblk,BZ_TSTART           ; SPEC.md 128.23.3: a title demo's START BLOCK (bz_tapply), bz_rlog right
%endif                          ; after it (bz_tdemo copies the two as one)
VAR bz_rlog,BZR_SIZE                ; THE REPLAY LOG (SPEC.md 128.11.12.1): `BZR1`,
                                ; the course (+4), the material (+5), flags,
                                ; the steps, the runs.  The recorder writes
                                ; it; R replays it (bz_rhave)
OS88_BSS BZ_BSS
OS88_IMAGE_END
