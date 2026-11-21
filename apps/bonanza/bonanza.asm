; BONANZA - Bounce Bonanza, an isometric rolling-ball game for os8088.
; Contract: SPEC.md 130 (the plan: docs/plans/BOUNCE-BONANZA-PLAN.md).
;
; WAVE 0 IS THE ENGINE SPIKE (SPEC.md 130): a ball rolled over a generated
; isometric test course that HARDWARE-SCROLLS IN BOTH DIRECTIONS on the CGA
; (FSXM_CGA320) and the Hercules (FSXM_HERC with Excitebike's 200-line
; pair-pixel field, SPEC.md 102.7.1), the 64-frame phase-torus ball, and the
; instruments that price a frame.  No heightfield physics, obstacles, sound or
; game rules yet.
;
; This file is the header, the window and its desktop face (SPEC.md 130.1,
; 130.6, 130.14.3): the title, the keys, the adapter line, the held log's
; line, and after a benchmark the RESULTS page - and the
; game's books: the best times and BONANZA.DAT (130.14.21).  bzvideo.inc is the bracket, the mode, the retrace wait, the ring
; writers and the boxes (130.2, 130.4); bzgame.inc is the frame loop, the
; simulation, the camera, the autopilot and the instruments (130.4 - 130.6).
; Nothing here is a reference game's: the ball is tools/bonanza_assets.py's
; (130.3) and the courses are text compiled by tools/bbcourse.py (130.10.4),
; generated into build/bonanza-art/ and carried as 3 + BZ_NCRS PARTS: three
; balls and one part a course, every one the CGA's (SPEC.md 130.11.3.1).
%include "os88api.inc"
OS88_HEADER 'BONANZA', bz_entry, OS88_F_ICON | OS88_F_ASSOC | OS88_F_GLYPH | OS88_F_PARTS, OS88_STACK_256 | OS88_HIGH | OS88_HIGHMEM
OS88_ICON16
    dw 0x07e0,0x1ff8,0x3ffc,0x7ffe,0x7ffe,0xffff,0xffff,0xffff
    dw 0xffff,0xffff,0xffff,0x7ffe,0x7ffe,0x3ffc,0x1ff8,0x07e0
    dw 0x07e0,0x1818,0x2004,0x4002,0x4c02,0x8c01,0x8001,0x8061
    dw 0x8061,0x8001,0x8c03,0x4c06,0x400e,0x203c,0x1ff8,0x07e0
OS88_ICON16_END
; a recorded demo, *.BZR, is BONANZA's document (SPEC.md 130.14.7.5, 54.6): a
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
; The art files are PARTS of this file (SPEC.md 130.11.3.1, 20.12), every one
; lazy and compressed: only the play's course and ball are ever read, on the
; DESKTOP before the bracket (so op_fetch's refusal toast can be drawn), the
; course's stored form is expanded in place there (bz_cexp, SPEC.md
; 130.15.4.5), the Hercules translates both in place after it (bz_hxlat), and
; both are dropped when the bracket returns (SPEC.md 130.7, 130.11.3).
%define OP_NO_LAZYOK            ; (the fetch itself asks; no pre-check is used)
%define OP_WANT_CSEG            ; op_cseg: the shell part is FAR-CALLED (SPEC.md 130.19.2)
%define OP_SAYGATE bz_fs        ; a fetch refused inside the bracket, after its
                                ; mode set, says nothing (SPEC.md 53.7, 130.19.5)
%define OP_WANT_ARENA           ; a play's SMALL parts - the balls, the sound part,
                                ; the songs - share ONE claim (SPEC.md 130.25.4)
%include "os88parts.inc"
%include "bzconst.inc"          ; the ball part's layout (tools/bonanza_assets.py)
%include "bzcourse.inc"         ; the courses and their part rows (tools/bbcourse.py)
%include "bzsnd.inc"            ; the songs and the events (tools/bbmusic.py)
%include "bzshell.inc"          ; the shell part's vectors (SPEC.md 130.19.2)
%include "bzvga.inc"            ; the VGA part's vectors (SPEC.md 130.46.6)
%include "bzwin.inc"            ; the window's art: its sizes (the part draws it, 130.26.2)
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

; --- the part rows: the Makefile's BZ_PARTS order (SPEC.md 130.11.3.1) ---------
                                ; course K: BZ_P_CRS + K, bzcourse.inc's rows -
                                ; the first: the balls have no row of their own,
                                ; they ride the RESIDENT BUNDLE (130.25.5.2)
BZ_BALPS    equ BZ_BAL_SIZER / 16 ; steel's paragraph in the bundle (rubber's 0)
BZ_BALPG    equ BZ_BALPS + BZ_BAL_SIZE / 16 ; glass's
BZ_BALB     equ BZ_BAL_SIZER + BZ_BAL_SIZE + BZ_BAL_SIZEG ; the families' first byte
%if BZ_SNDP * 16 != BZ_BALB || BZ_FAMB < BZ_BALB || BZ_FAMB & 15
 %error "the bundle's SOUND starts where the balls end and the families after it (SPEC.md 130.50.2)"
%endif
%if (BZ_BAL_SIZER | BZ_BAL_SIZE | BZ_BAL_SIZEG) & 15 || BZ_BALB > 65535 - 4096
 %error "the bundle's balls are whole paragraphs, the families after them in one segment (130.25.5.2)"
%endif

; --- the course part's header (BZC2: SPEC.md 130.15.4.1, 130.10.5.2) -----------
; Byte offsets from the part's first byte; the grid's from GRIDOFF.  Nothing
; here is checked on the guest: tools/bbcourse.py checked every one of them at
; build time (SPEC.md 130.10.6.2).  BZC1's fields keep their offsets; the map
; moved from +32 to +48 behind BZC2's own (130.15.4.1).
BZC_COLS    equ 4               ; word columns: 64, 128 or 160
BZC_BROWS   equ 6               ; block rows
BZC_NBLK    equ 8               ; N, blocks (bz_hxlat)
BZC_MAPSH   equ 10              ; 4 for 64 columns, 5 for 128, 0 any other
                                ; width: not read (bz_mrow, 130.10.4.2)
BZC_BLKOFF  equ 12              ; block 0's offset (bz_hxlat, bz_cexp)
BZC_OCCIDX  equ 14              ; OCCIDX: BROWS + 1 words, each the offset of
                                ; the block row's first occluder record
BZC_OCCREC  equ 16              ; the first record (bz_cexp's COUNTS)
BZC_MASKOFF equ 20              ; mask 0 (bz_cexp's MASKTAB)
BZC_NMASK   equ 22              ; the masks
BZC_ROWB    equ 24              ; 2 COLS: the map row's byte stride, READ by the
                                ; column writer through DS = the part (130.10.6.4)
BZC_GRID    equ 26              ; GRIDOFF
BZC_PROPOFF equ 28              ; the prop table (SPEC.md 130.12.3.1): its first
BZC_NPROP   equ 30              ; record, and the records (0: none)
BZC_RECB    equ 32              ; byte: the record's size in RAM, 4 or 8
BZC_SB      equ 33              ; signed byte: the s bias (0 when RECB is 8)
BZC_TB      equ 34              ; YOFF (SPEC.md 130.51, was TB): the bands' top biases, a signed word a band
BZC_MTAB    equ 36              ; the mask table (0 when RECB is 8)
BZC_DIROFF  equ 38              ; the section directory (SPEC.md 130.15.4.2):
BZC_NSEC    equ 40              ; its offset and its 8-byte entries
BZ_OSROWS   equ 160             ; block rows bz_osum summarises (bz_osmake): PEAK has 135
BZC_MAP     equ 48              ; the map: COLS x BROWS words, absolute offsets
BZX_FORM    equ 1               ; (a directory entry's) byte: its stored form
BZX_OFF     equ 2               ; its RAM offset
BZX_LEN     equ 4               ; its RAM length
BZX_DLEN    equ 6               ; its STORED length, at the end of its slot
BZX_ENTB    equ 8               ; an entry's size (BZX_: not BONANZA.DAT's BZD_)
BZK_ENT     equ 6               ; THE KIT's part, BZK1 (SPEC.md 130.37.2): +4 NCLS,
BZK_ENTB    equ 8               ; +6 an entry a class: tag, 0, a piece's bytes,
                                ; the pieces, their offset in the part
BZG_NROWS   equ 4               ; (at GRIDOFF +) the rows
BZG_SMIN    equ 6               ; row 0's s = wx + wy
BZG_AMIN    equ 8               ; signed, even: the first cell's a = wx - wy
BZG_KW      equ 10              ; cells a row
BZG_ROWTAB  equ 12              ; ROWTAB's offset: a row's first cell
BZG_X0      equ 14              ; px
BZG_Y0      equ 16              ; signed px
BZG_ID      equ 18              ; the course's IDENTITY (SPEC.md 130.12.8)
BZG_WX      equ 20              ; the start tile
BZG_WY      equ 22
BZG_NWAY    equ 24              ; the route: NWAY pairs of words, the ball's
BZG_ROUTE   equ 26              ; picture top-left (px), at this offset
; --- the ball part's header (BZB2, SPEC.md 130.11.9.1); its layout is
; bzconst.inc's BZ_BAL_* -------------------------------------------------------
BZB_NSHA    equ 12              ; byte: shatter frames, 4 for glass, else 0
BZB_NSTR    equ 14              ; byte: stretch frames, 1 for rubber, else 0
%if BZ_BAL_STROFF != BZ_BAL_SHAOFF
 %error "bz_hxball translates the shatter and stretch entries as one table"
%endif
; --- the replay log's header (SPEC.md 130.11.12.1), in [bz_rlog] ---------------
BZR_CRS     equ 4               ; byte: the course K
BZR_MAT     equ 5               ; byte: the material
BZR_FLAGS   equ 6               ; byte: bit 0 COMPLETE, bit 1 TRUNCATED, bit 2
                                ; TILT (runs of three bytes, SPEC.md 130.14.8.3)
BZR_PHYS    equ 7               ; byte: the PHYSICS identity BZ_PHYSV (130.14.7.2)
BZR_STEPS   equ 8               ; DWORD: the steps recorded
BZR_NRUN    equ 12              ; word: the runs recorded
BZR_ID      equ 14              ; word: the course's identity (130.12.8)
BZR_RUNS    equ 16              ; the runs: (key byte, count 1 - 255) pairs, or
                                ; with TILT (key byte, tilt byte, count) triples
BZR_SIZE    equ 4096            ; the log: at most 2,040 runs (1,360 TILT)
BZR_K       equ BZ_KIT_RLOG     ; ...and WHERE it is (SPEC.md 130.11.12.1): its header
                                ; RESIDENT at bz_rlog, its runs in THE KIT's zero tail
                                ; at [bz_kseg]:BZR_K + 16 - log offset X at BZR_K + X.
                                ; The tail's head is the header's copy for a write
%if BZ_KIT_RLOGB != BZR_SIZE
 %error "THE KIT's zero tail is the replay log's whole size (bbcourse.py's RLOG_SIZE)"
%endif
BZR_DONE    equ 1
BZR_TRUNC   equ 2
BZR_TILT    equ 4               ; (bzcourse.inc's BZ_RL_TILT, the tool's)
%if BZR_TILT != BZ_RL_TILT || (BZR_SIZE - BZR_RUNS) % 6
 %error "the log's TILT flag is +6 bit 2, and both run widths fill bz_rlog exactly"
%endif
BZ_P_DEMO   equ BZ_P_CRS + BZ_NCRS + BZ_NCRS2 ; shipped demo row i: BZ_P_DEMO + i, course
                                ; bz_dcrs[i] (130.14.7.4) - after the world parts (a SHEETED course has none: 130.30.12.5)
BZ_P_SHELL  equ BZ_P_DEMO + BZ_NDEMO ; the SHELL PART, BZSHELL.BIN (SPEC.md 130.19.2)
BZ_P_PATH   equ BZ_P_SHELL + 1  ; THE PATHWAY, BZPATH.BIN (130.19.5)
BZ_P_TITLE  equ BZ_P_PATH + 1   ; THE TITLE, BZTITLE.BIN, and its demos, BZTDEMO.BIN,
BZ_P_TDEMO  equ BZ_P_PATH + 2   ; the last two rows (SPEC.md 130.23)
BZ_P_KIT    equ BZ_P_PATH + 1 + 2 * BZ_TITLE ; THE KIT, BZKIT.BIN (SPEC.md 130.37): HELD
BZ_P_FAM    equ BZ_P_KIT + 1    ; wave 9 (SPEC.md 130.25.6.2): the family part
                                ; rows, after every other row: a `fetch` family's own (ID order),
BZ_P_FBUN   equ BZ_P_FAM + BZ_NFFETCH ; then the RESIDENT BUNDLE's (130.25.6.9); bz_ftab maps an ID
BZ_P_VGA    equ BZ_P_FBUN + 1   ; THE VGA's code part, BZVGA.BIN (SPEC.md 130.46.6): the last row
BZ_LIVES    equ 5               ; a new game's lives (8b.5)
; --- BONANZA.DAT (SPEC.md 130.14.3.3, 130.22.5.1): SYSTEM\APPDATA, ONE sector, in [bz_dat] -
; `BZS5`: 488 bytes, keyed by what stays put - a best by its course's SAVE KEY, progress by PAD
BZD_ENT     equ 8               ; 23 best entries IN NO ORDER: +0 the course's
BZD_ENTB    equ 6               ; SAVE KEY (BZ_CRS_KEYS; 0 empty), +2 its best in
BZD_NENT    equ BZ_CRS_MAX      ; STEPS (0 none), +4 that best's falls
BZD_SLOT    equ BZD_ENT + BZD_NENT * BZD_ENTB ; three game SLOTS after the bests: +0 lives,
BZD_SLOTB   equ 22 + 4 * BZ_PAD_MAX ; +1 the MODE (bit 0), +2 the PAD, +3 zero,
BZD_NSLOT   equ 3               ; +4 the OPEN pads and +8 the DONE ones
BZD_FILE    equ BZD_SLOT + BZD_NSLOT * BZD_SLOTB ; (a dword each, a bit a pad), +12 the routes
BZD_SPAD    equ 2               ; OPENED and +16 TAKEN (a dword each), +20 the
BZD_SOPEN   equ 4               ; pathway's VERSION (BZ_PATH_VER), +22 the exits
BZD_SDONE   equ 8               ; found (a word a PAD, 23 pads, +22 - +67), +68
BZD_SROPN   equ 12              ; the best a pad (steps, a word a pad, +68 -
BZD_SRTAK   equ 16              ; +113): 114 bytes a slot.
BZD_SVER    equ 20
BZD_SEXIT   equ 22
BZD_SBEST   equ BZD_SEXIT + 2 * BZ_PAD_MAX
; UNDER one sector, never a WHOLE one: od_write takes its in-place arm (one
; sector, no FAT, no entry) only for a count that is not a multiple of 512
; (os88data.inc), and the slot is written at a course's ENTRY inside the
; bracket (130.19.6) - at 512 bytes every save would be a full replace
%if BZD_FILE >= 512 || BZD_SBEST + 2 * BZ_PAD_MAX != BZD_SLOTB || BZD_SVER - BZD_SOPEN != 16 || BZ_NCRS > BZ_CRS_MAX || BZ_PATH_NPAD > BZ_PAD_MAX
 %error "BZS5 is under ONE sector, a word a pad in both tables (SPEC.md 130.22.5.1)"
%endif
BZD_NPAD    equ BZ_PATH_NPAD    ; the pads a slot's +2 may name (130.22.3)
%if BZD_NPAD > 32
 %error "the save keeps a bit a pad in a dword (SPEC.md 130.22.5)"
%endif

bz_entry:
    push es                     ; op_load spends ES, which arrives KERNEL_SEG
    call op_load                ; SI is still the kernel's name: FIRST. Every
    pop es                      ; row is lazy, so this copies the name and
    jc .out                     ; claims nothing
    push es                     ; THE KIT (SPEC.md 130.37.5), HELD for the instance:
    call bz_kget0               ; under the bundle, so the arena above it grows in
    pop es                      ; place (quiet: a launch tries again and says why)
    push es                     ; story 9.8 (SPEC.md 130.25.6.9): the RESIDENT
    call bz_bget                ; BUNDLE, one read, the arena's floor before anything
    pop es                      ; else enters it - and THE BALLS in it generated, ONCE
                                ; (130.25.5.2; refused, op_fetch said why: the first
                                ; launch tries again)
    call bz_argget              ; a double-clicked document's name, copied out
                                ; while ES is still the kernel's (130.14.7.5)
    mov si, bz_tpl
    call OSAPI_WM_CREATE        ; ...and AL = the class slots this kernel
    jc .out                     ; dispatches (SPEC.md 11.104): no timer slot
    cmp al, WC_ONTIMER + 1      ; is kern_small, the 128KB machine, which
    sbb al, al                  ; refuses the bracket (SPEC.md 130.1)
    neg al
    mov [bz_small], al
    jz .big                     ; kern_small plays nothing (SPEC.md 130.1): the
    mov al, BZ_P_KIT            ; kit is given back (op_drop preserves every
    call op_drop                ; register; ES is still the kernel's)
    mov word [bz_kseg], 0       ; (no kit: no log, 130.11.12.1)
.big:
    mov [bz_win], bx
    call OSAPI_FILE_HERE        ; where BONANZA.O88 was launched from (SPEC.md
    mov [bz_homedir], dx        ; 130.14.7.6): BONANZA.DAT's volume, whatever
    mov [bz_homevol], bl        ; a dialog does to the instance later
    call bz_dload               ; the best times (130.14.3.3); kern_small: none
%ifdef BZDEV
    mov byte [bz_crsel], BZ_CRS_DEFAULT ; the course F plays: pad 0's (a row pokes another)
%endif
    OS88_REGION_MOVABLE
    OS88_ALTENTER_ARM
    mov ax, [bz_win]            ; THE WINDOW (SPEC.md 130.26): the Play Game
    mov bx, bz_btrec            ; button's gesture (the library takes the press
    mov dx, bz_click            ; first and chains our own click work) ...
    call os88ui_btninit
    mov bx, [bz_win]            ; ...the menus ...
    mov si, bz_menus
    call OSAPI_MENU_SET
    mov si, bz_sizes            ; ...its size on each display (fixed: the
    call OSAPI_WM_PREFER        ; art does not scale) ...
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
bz_rret:                        ; (every handler's tail: SAVE's registers back)
    RESTORE
    ret

bz_about:
    SAVE
    mov byte [bz_abon], 1
    mov bx, [bz_win]
    mov si, bz_credits
    call os88ui_about
    jmp bz_rret

bz_click:
    SAVE
    cmp byte [bz_abon], 0
    je .done
    mov byte [bz_abon], 0
    call bz_repaint
.done:
    jmp bz_rret

bz_onkey:
    SAVE
    cmp byte [bz_abon], 0
    je .key
    mov byte [bz_abon], 0
    call bz_repaint
%ifdef BZDEV
    jmp .done
%else
    jmp .out
%endif
.key:
    mov byte [bz_earm], 0       ; (an armed Erase holds to the next pick or key)
%ifdef BZDEV
    cmp byte [bz_dev], 0        ; THE WINDOW'S KEYS (SPEC.md 130.26.1): Enter,
    jne .dev                    ; Alt+Enter and F are Play Game, F5 and F6 the
%endif                          ; replays; everything else is the harness's
    cmp ax, KEY_ALTENTER        ; (bz_dev, a BZDEV build's: 130.26.6.1)
    je .pg
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
%ifdef BZDEV
.dev:
    mov cl, [bz_page]           ; a key on the RESULTS page is acted on as on
    mov byte [bz_page], 0       ; MAIN and returns the face to it (SPEC.md
    mov [bz_pgo], cl            ; 130.14.3.2): repainted whole at .done
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
    je .done                    ; (Esc: nothing on the face)
    or al, 20h
    cmp al, 'f'
    je .play
    cmp al, 'b'
    je .bench
    cmp al, 'r'
    je .replay
    mov si, bz_devk             ; D, L, V, W, T, S: one press however long it
.tk:                            ; is held (SPEC.md 130.11.11.2)
    mov bx, [si + 1]            ; (a key, its handler: bz_devk)
    cmp al, [si]
    je .held
    add si, 3
    cmp byte [si], 0
    jne .tk
    jmp short .done
.held:
    call bz_dkey                ; AH = the make code: CF = 1 a repeat, swallowed
    jc .done
    call bx
    jmp short .done
.replay:
    call bz_rhave               ; R: offered only when there is a log
    jne .done                   ; (SPEC.md 130.11.12.2): its course, and
    mov ah, [bz_rlog + BZR_CRS] ; bz_launch takes its ball
    mov al, 2
    jmp short .go
.bench:
    mov ax, 1 | (BZ_CRS_BENCH << 8) ; B: the benchmark of the course in AH -
    jmp short .go               ; BENCH, which BZDEV=1 alone carries, as
                                ; course 0; a row pokes [bz_crs] at
                                ; bz_launch for another (SPEC.md 130.10.11.1)
%if BZ_PATH_NPAD
.game:                          ; Enter, Alt+Enter: THE GAME (wave 8b, 130.19.5)
%if BZ_TITLE
    call bz_playgame            ; (SPEC.md 130.23.4: the TITLE, P its game;
%else                           ; 130.26.4: or where the window was asked for)
    call bz_game8
%endif
    jmp short .done
%endif
.play:
    mov al, 0                   ; F: a free play of the selected course, its
    mov ah, [bz_crsel]          ; own ball (SPEC.md 130.11.11.3)
.go:
    call bz_go
.done:
    cmp byte [bz_pgo], 0        ; leaving RESULTS: MAIN whole, unless a bracket
    je .out                     ; ran (the kernel's restore painted it)
    mov byte [bz_pgo], 0
    call bz_repaint
%endif
.out:
    jmp bz_rret

; AL = the mode, AH = the course: launched, and a best it set saved
bz_go:
    mov [bz_mode], al
    mov [bz_crs], ah
    call bz_launch
    jmp bz_dsave

; bz_dkey - the held-key guard (SPEC.md 130.11.11.2), AH = a typed key's make
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
    jmp bz_rret

; ZF = 1 when [bz_rlog] holds a log (the recorder's signature, SPEC.md
; 130.11.12.1).  The log is the package's own bss, written by the package:
; trusted, not checked (130.11.12.2).  Preserves all but the flags.
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
; bz_adapter - what this window's display is: AL = 1 CGA, 2 Hercules, 3 VGA
; (SPEC.md 130.46.2), 0 none of them (or no FSX mode for it).  Preserves all
; but AX and the flags.
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
    jne .vga
    test ax, 1 << FSXM_HERC
    jz .none
    mov al, 2
    jmp .out
.vga:
    cmp dl, VID_VGA
    jne .none
    test ax, 1 << FSXM_VGA0D
    jz .none
    mov al, 3
    jmp .out
.none:
    xor al, al
.out:
    pop dx
    pop bx
    ret

; bz_setcard - AL = bz_adapter's 1 - 3: [bz_card] it, [bz_herc] 1 on the
; Hercules alone, [bz_vga] 1 on the VGA alone (SPEC.md 130.46.2: a VGA play
; asks "Hercules?" and hears the CGA's no).  Clobbers AX.
bz_setcard:
    mov [bz_cardk], al
    dec ax
    mov ah, al
    and al, 1
    mov [bz_herc], al
    shr ah, 1
    mov [bz_vga], ah
    ret

; -----------------------------------------------------------------------------
; bz_launch - the desktop side of a play, a benchmark or a replay: every
; refusal is here, where a toast can still be drawn (SPEC.md 130.1, 130.7).
; In: [bz_mode] (0 play, 1 benchmark, 2 replay, 3 the demo benchmark: a
; replay, measured, SPEC.md 130.14.7.3) and [bz_crs].  The MATERIAL is
; chosen here (SPEC.md 130.11.5.4): a play or a benchmark rolls the course's
; own (BENCH's for B, the BZDEV build's; the course a harness poked at this entry otherwise), a
; replay the log's.  Course K's part
; (row BZ_P_CRS + K) is fetched - the same row on both cards - and expanded
; in place at once (bz_cexp, SPEC.md 130.15.4.5); the balls are HELD since the
; open (bz_bget, 130.25.5.2); on the Hercules the course is translated in
; place, and the balls once (bz_hgen, bz_hxlat, SPEC.md 130.11.3); the
; bracket runs, and the course's parts are dropped on every way out.  Every fetch here - the course's, the balls', the
; sound's song and the title's after the bracket - is made at HOME (bz_home,
; SPEC.md 130.14.7.6), and the instance goes back where the user was after.
; -----------------------------------------------------------------------------
bz_launch:
    call bz_unsuscrs            ; (a suspended COURSE given up first: this
                                ; launch's parts take its place, 130.26.3; a
                                ; suspended pathway is only memory, and stays)
    mov byte [bz_towin], 0
    mov byte [bz_newb], 0       ; (only this launch's play may set a best)
    call bz_fsok                ; kern_small (the parts are more heap than the
    jc .ret                     ; 128KB machine has) and EGA, MDA refused
    mov al, [bz_rlog + BZR_MAT] ; the material (above): 2, 3 a replay, the
    cmp byte [bz_mode], 2       ; log's
    jae .mat
    mov bl, [bz_crs]            ; 0, 1: a play or a benchmark, the course's own
    xor bh, bh
    mov al, [bz_cballs + bx]
.mat:
    mov [bz_mat], al
    call bz_shdrop              ; the shell part never shares memory with a
                                ; course (SPEC.md 130.19.2)
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
    mov es, [bz_cseg]           ; (SPEC.md 130.12.8) - and one made under
    mov di, [bz_goff]           ; other PHYSICS (+7, 130.14.7.2)
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
    call bz_vdrop               ; the VGA's part and ball copies (130.46.6)
    call bz_cdrop               ; every part this launch fetched given back
    call bzs_gdrop              ; the song back, and the title (a finish's
    cmp byte [bz_shpend], 0     ; fanfare first, SPEC.md 130.20.6).  The
    je .nopend                  ; restore's paint was put off while the course
    mov byte [bz_shpend], 0     ; was held (bz_shcall): made now, the course
    mov byte [bz_pgo], 0        ; gone and the shell part fetched again
    call bz_repaint             ; (SPEC.md 130.19.2)
.nopend:
    cmp byte [bz_err], 3        ; no bracket
    jb .out                     ; ran: the face repainted with the refusal (3
    mov byte [bz_pgo], 1        ; or 4), by bz_onkey (once, whatever page it
.out:                           ; was on)
    ret

; -----------------------------------------------------------------------------
; bz_cload - course [bz_crs]'s part fetched for the ball [bz_mat] (SPEC.md
; 130.14.4.4): its row - BZ_P_CRS + K, or BZ_P_PATH for the pathway (wave 8b,
; 130.19.5) - expanded in place once (bz_cexp, 130.15.4.5), the three balls
; HELD (bz_bget: nothing to do after the open, 130.25.5.2), its song (bzs_gfetch), its header copied (bz_crshdr) and, on the
; Hercules, translated (bz_hgen, bz_hxlat, 130.11.3).  CF = 1 a fetch was
; refused (op_fetch said why - or, inside the game's bracket, OP_SAYGATE
; held it quiet): what was fetched is bz_cdrop's to give back.  At home.
; Preserves nothing.
; -----------------------------------------------------------------------------
bz_cload:
    mov al, [bz_crs]            ; course K's row: BZ_P_CRS + K (bzcourse.inc)
    add al, BZ_P_CRS
%if BZ_PATH_NPAD
    cmp byte [bz_crs], BZ_CRS_PATH ; ...the pathway's its own (130.19.5)
    jne .row
    mov al, BZ_P_PATH
.row:
%endif
%if BZ_TITLE
    cmp byte [bz_crs], BZ_CRS_TITLE ; ...and the title's (130.23)
    jne .rowt
    mov al, BZ_P_TITLE
.rowt:
%endif
    mov [bz_pc], al
    cmp byte [bz_crs], BZ_NCRS  ; a PLAY course names the KIT's pieces (130.37.5):
    jae .nokit                  ; the kit first, if the open's fetch was refused
    call bz_kget                ; (op_fetch said why: no course without it)
    jc .out
    mov al, [bz_pc]             ; (bz_kget spends AL)
.nokit:
%if BZ_PATH_NPAD
    mov byte [bz_phre], 0       ; the pathway HELD (130.22.7): its part is here,
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
%if BZ_NCRS2 + BZ_NSHC
    mov [bz_mseg], ax           ; (the PICTURE part: SPEC.md 130.30.5)
%endif
%if BZ_NSHC
    mov [bz_shseg], ax          ; (a SHEETED course's ONE part: sheet 0, its base - SPEC.md 130.30.12.5)
%endif
%if BZ_PATH_NPAD
    cmp byte [bz_phre], 0
    jne .exd
    cmp byte [bz_pc], BZ_P_PATH ; a pathway fetched now is HELD while it is
    jne .ex                     ; here (bz_phrel, bz_phfree let it go) - unless
%ifdef BZDEV
    cmp byte [bz_phforce], 0    ; the harness forces the drop-and-refetch way
    jne .ex
%endif
    mov byte [bz_phold], 1
.ex:
%endif
    call bz_cexp                ; the STORED form expanded in place, ONCE: this
                                ; fetch decoded, every exit below dropping the
                                ; part (SPEC.md 130.15.4.5)
%if BZ_PATH_NPAD
.exd:
%endif
%if BZ_NCRS2 + BZ_NSHC
    call bz_cload2              ; a two-part course's WORLD part (130.30.5),
    jc .drop                    ; before anything reads the world
%endif
    call bz_bget                ; THE BALLS (SPEC.md 130.25.5.2): HELD, all three,
    jc .drop                    ; since the open - fetched and generated here only
                                ; if the open's fetch was refused (or a CGA launch
                                ; found them Hercules-translated)
    mov bl, [bz_crs]            ; THE ARENA (SPEC.md 130.25.4.2): ONE regrow
    xor bh, bh                  ; for the whole batch - sound part, song,
    shl bx, 1                   ; fanfare, families - by the course's own figure (the
    mov ax, [bz_carena + bx]    ; tool's BZ_CRS_ARENA: their RAM forms and one
    call op_areserve            ; fetch's room).  Refused, each fetch grows it
    push es                     ; the title off, the course's song fetched
    call bzs_gfetch             ; (none had: a SILENT play, SPEC.md 130.20.6)
    pop es
    call bz_crshdr              ; the course's header, copied into our data
    call bz_ffetch              ; wave 9 (SPEC.md 130.25.6.2): its FAMILIES' parts
    jc .drop                    ; (OP_ARENA code rows, the batch's last fetches)
    call bz_arload              ; THE BATCH'S END (every arena fetch above it -
                                ; the families' too): each word read again
    call bz_ffetch              ; ...and the families' far pointers taken again:
                                ; it fetches nothing now, and a later family's
                                ; fetch can have MOVED the arena under an
                                ; earlier one's (CF: no fetch, so it is 0)
    cmp byte [bz_herc], 0       ; the Hercules's parts are the CGA's through
    je .nherc                   ; BZ_HTAB, made here (SPEC.md 130.11.3)
    push es                     ; (ES as the bracket call found it before:
    call bz_hgen                ; bz_hxlat leaves the ball's there)
    call bz_hxlat
%if BZ_NSHC
    call bz_hxshs               ; (a SHEETED course's other sheets' blocks)
%endif
    pop es
.nherc:
    cmp byte [bz_vga], 0        ; the VGA's: converted ONCE, here, into planar
    je .ok                      ; pairs (SPEC.md 130.46.5) by BZVGA.BIN
    push es
    call bz_vprep
%if BZ_NSHC
    jc .vpd
    call bz_vshs                ; (a SHEETED course's other sheets: blocks, masks)
.vpd:
%endif
    pop es
    jc .drop
.ok:
    clc
.out:
    ret
.drop:
    stc
    ret

%if BZ_NCRS2 + BZ_NSHC
; -----------------------------------------------------------------------------
; bz_cload2 - a TWO-PART course's WORLD part (SPEC.md 130.30.5): when
; BZ_CRS_WROW names one for course [bz_crs], fetched (the picture part's
; segment stays in bz_mseg), its segment stored in bz_cseg and expanded in
; place ONCE (bz_cexp, 130.15.4.5) - after the picture part's, so bz_dfind's
; bounds are the world part's.  A SHEETED course (130.30.12.5) has no world
; row: its sheets past 0 and its world part are SEGMENTS of the ONE part
; bz_cload fetched - each at its BZ_SHTAB entry's paragraphs from the part's
; base (the world part's in entry 0's word, sheet 0's being 0), taken with
; OSAPI_SEG's SEG_SUB (kern_mega: a selector tied to the claim, going with
; it; every real-mode kernel: the sum), stored and expanded in place in
; order, the world part's last.  No fetch, no disk.  The pathway and the
; title are one part.  CF = 1 a fetch, or a selector, was refused (op_fetch
; said why): bz_cdrop gives back what was fetched (it drops every world
; row).  At home.  Preserves nothing.
; -----------------------------------------------------------------------------
bz_cload2:
    mov bl, [bz_crs]
    cmp bl, BZ_NCRS
    jae .one                    ; (CF = 0: the pathway, the title)
    xor bh, bh
%if BZ_NSHC
    mov cl, [bz_cshn + bx]      ; k sheets: k segments past sheet 0 - its
    or cl, cl                   ; sheets' and then the world part's
    jz .nsh
    xor ch, ch
    mov bp, cx                  ; (BP: bz_cexp keeps it)
    shl bx, 1
    mov si, [bz_cshi + bx]
    add si, bz_shtab            ; SI = entry 0
    mov bx, si
    mov di, bz_shseg
.sh:
    add bx, BZ_SHENT            ; sheet j's paragraphs ...
    inc di
    inc di
    mov ax, [bx]
    dec bp
    jnz .sub
    mov ax, [si]                ; ... and the world part's, the last
.sub:
    push bx
    mov dx, [bz_shseg]          ; the part's base + AX paragraphs (a real-mode
    xor cx, cx                  ; kernel's DX + AX; CX 0: 64KB, or to the
    mov bl, SEG_SUB             ; part's end)
    call OSAPI_SEG
    pop bx
    jc .one                     ; (CF = 1: no selector)
    mov [di], dx
    mov [bz_cseg], dx
    push si
    push di
    push bx
    call bz_cexp                ; the STORED form expanded in place, once
    pop bx
    pop di
    pop si
    or bp, bp                   ; (CF = 0)
    jnz .sh
    ret
.nsh:
%endif
%if BZ_NCRS2
    mov al, [bz_cwrow + bx]
    or al, al                   ; (CF = 0)
    jz .one
    push ax
    call op_fetch               ; claim, read, decode - or a toast said why
    pop ax
    jc .one
    call op_seg
    mov [bz_cseg], ax
    call bz_cexp                ; the STORED form expanded in place, once
    clc
%endif
.one:
    ret
%endif

; -----------------------------------------------------------------------------
; bz_arload - THE ARENA BATCH'S END (SPEC.md 130.25.4.2, 20.12.16): the arena
; fitted to its parts (the last fetch's room given back, op_areserve 0) and
; every word BONANZA keeps of an arena part read again from op_seg - a fetch
; that grew the arena may have MOVED it, which shifts the standard's words and
; not ours.  A part not here answers 0, so each word says so too.  bz_cload's,
; after its whole batch (the window has no title song since 130.26.5).  A drop never
; moves the arena, so none follows one.  Preserves nothing.
; -----------------------------------------------------------------------------
bz_arload:
    xor ax, ax
    call op_areserve
    call bz_bsload              ; the balls (130.25.5.2), and the sprite's
    mov bl, [bz_mat]
    xor bh, bh
    shl bx, 1
    mov ax, [bz_bsegs + bx]
    mov [bz_bseg], ax
    ret                         ; (the song is the course part's, which is no
                                ; arena row: it does not move - SPEC.md 130.50.3)

%if BZ_PATH_NPAD
; the pathway's part, HELD (130.22.7): bz_phrel's test is the heap's largest
; claim against the largest course's, bzcourse.inc's BZ_CRS_MAXCLAIM (the
; tool's, 130.22.3): a pad's course's part, balls, song and sound part, each
; its RAM form plus op_lazyp's cluster slack (a compressed row claims R and
; the read of its packed bytes in whole clusters)
%if BZ_TITLE == 0
; -----------------------------------------------------------------------------
; bz_game8 - THE GAME (wave 8b, SPEC.md 130.19.5): Enter on the face - a build
; with no TITLE's only (the title's P plays it, bz_tround).  Its refusals are
; bz_launch's (kern_small, the adapter); a game with no lives left is a NEW
; one (5 lives, pad 0 open, nothing done), else it goes on where it was.  The pathway is fetched here at home, on the desktop, and the bracket
; (bz_fullscreen, [bz_ingame] 1) plays the rounds; whatever is held when it
; ends is given back, and a best a course set is written (bz_dsave).
; -----------------------------------------------------------------------------
bz_game8:
    mov byte [bz_newb], 0
    call bz_fsok
    jc .ret
    call bz_gslot
    call bz_shdrop              ; (never beside a course, 130.19.2)
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
    call bz_vdrop               ; (the VGA's part, 130.46.6)
    call bz_phfree              ; (the held pathway goes with the game, 130.22.7)
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

; bz_gslot - THE SLOT's game (save v3, 130.22.5) into memory: its game when
; it has lives, else a NEW one in it; the pad, the pads open and done, the
; routes; its MODE; no event pending (bz_pwev).  Preserves all but AX and SI.
bz_gslot:
    call bz_dslot               ; THE SLOT (save v3, 130.22.5): its game when
    mov al, [si]                ; it has lives ...
    or al, al
    jnz .on
    mov al, BZ_LIVES            ; ...else a NEW one in it
    call bz_gnew
.on:
    mov [bz_lives], al
    call bz_gload               ; the pad, the pads open and done, the routes
    mov al, [si + 1]            ; the MODE (8c, 130.19.8.3): EXPLORE rests
    and al, 1                   ; on any pad (bz_proute)
    mov [bz_xmode], al
    mov byte [bz_pwev], 0
    ret

; bz_gstore - the game's state into the slot played (130.22.5): AL lives
; (bz_gstorl: AL given), the pad, the open and done pads and the routes
; (bz_nopen ... bz_nrtk, 16 bytes, the slot's order), the pathway's version.
; Preserves all but AX and SI.
bz_gstore:
    mov al, [bz_lives]
bz_gstorl:
    call bz_dslot
    mov [si], al
    mov al, [bz_ppad]
    mov [si + BZD_SPAD], al
    mov word [si + BZD_SVER], BZ_PATH_VER
    push cx
    push di
    push es
    push ds
    pop es
    lea di, [si + BZD_SOPEN]
    mov si, bz_nopen
    mov cx, (BZD_SVER - BZD_SOPEN) / 2
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
    mov cx, (BZD_SVER - BZD_SOPEN) / 2
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
    mov cx, (BZD_SVER - BZD_SOPEN) / 2
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
; THE PATHWAY (wave 8R, SPEC.md 130.22.4): its tables (the part's, at BZC2
; +42, 130.22.3, read through bz_ptho / bz_ptro / bz_ptko), the signs' poses,
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

; bz_medal - pad AL's DONE pose, BL the course it plays (8c.3, 130.19.8.3; a
; pad's sign, 130.22.2): DL = 3 GOLD (the slot's best for the PAD at or under
; the course's G, 130.22.5.1), 2 SILVER (at or under S), 1 else.  Preserves
; all but DX.
bz_medal:
    push ax
    push bx
    push si
    xor bh, bh
    shl bx, 1
    shl bx, 1                   ; BX = 4K, the course's medals
    call bz_dslot
    push bx
    xor ah, ah
    xchg ax, bx
    shl bx, 1                   ; ...and 2 x the pad, its best
    mov ax, [si + bx + BZD_SBEST]
    pop bx
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

; bz_gpath - the PATHWAY entered (130.22.4.4 item 1): fetched unless HELD
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
; pad shown (its icon's poses one more, 130.22.3).  Preserves all else.
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
; grounded) and the event the last course left (bz_pwev, 130.22.4.4 item 1):
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
    call bz_dwset               ; OPENED (the slot's +12, 130.22.5)
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
; bz_pwrest - RESTING on bz_ppad (130.22.4.4 item 2): its icon's animation's
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
; and the first segment's, s = 0 and v = 0 (130.22.4.2); a SECRET route's
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
; bz_follow - a STEP of the pathway's play (wave 8R, SPEC.md 130.22.4.2: the
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
; v + FOL_ACC; then at most the top speed of the segment holding s, FOL_VMAX or
; on a screen-horizontal one FOL_VMAXD, a screen-vertical FOL_VMAXV; s += v, at 256 L ARRIVED; the segment holding s
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
    jge .cap
    mov dx, BZ_FOL_VMIN
    jmp short .cap
.acc:
    add dx, BZ_FOL_ACC
.cap:                           ; v = min(v, the segment's top speed):
    mov si, [bz_pwp]            ; FOL_VMAXD where its two axes move OPPOSITE
    mov di, si                  ; ways (screen-horizontal: px 2 a ground px,
    add di, [bz_pwpd]           ; 1.0 = 2 px a step, a quarter of the art's
    mov ax, [es:di]             ; 8 px period: a roll), FOL_VMAXV the SAME
                                ; way (screen-vertical), else FOL_VMAX
    sub ax, [es:si]
    mov bx, [es:di + 2]
    sub bx, [es:si + 2]
    mov cx, BZ_FOL_VMAX
    or ax, ax
    jz .c
    or bx, bx
    jz .c
    xor ax, bx
    mov cx, BZ_FOL_VMAXV        ; the SAME way: screen-vertical, 2 lines a step
    jns .c
    mov cx, BZ_FOL_VMAXD
.c:
    cmp dx, cx
    jle .v
    mov dx, cx
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
    cmp al, [bz_pwng]           ; passes its distance (130.22.2)
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

; bz_pwpos - the follower's POSITION at s (130.22.4.2): t = s - 256 D_k on the
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

; bz_pwarr - the marble ARRIVES on bz_pwdst (130.22.4.2): the route TAKEN
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
; route (the pad's KEYS, 130.22.4.5) is OPEN rolls it (bz_pwdep); Enter plays
; the pad's course (bz_pwck, bz_pwq 13); Space shows its INFO card (bz_kinfow,
; 130.22.6); Esc leaves (bz_pwq 27: the title).  Clobbers AX, BX, CX, DX, SI,
; DI.
bz_pwkey:
    cmp al, 13
    je .k
    cmp al, 27
    je .k
    cmp al, ' '
    je .k
    mov bh, 'r'                 ; F5, F6 and V (SPEC.md 130.26.3): the play
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
; bz_grounds - inside the bracket, the mode set: the game's ROUNDS (130.22.4.4).
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
    jne .twp                    ; (SPEC.md 130.26.4)
    mov al, [bz_pwq]
    cmp al, 'o'
    je .over
    cmp al, 13
    je .enter
    cmp al, 'r'                 ; F5, F6 and V at a pad (130.26.3)
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
    cmp byte [bz_xmode], 0      ; the disk first (130.19.6: off mid-course
    jne .nolife                 ; refunds nothing; a finish gives it back at
    mov al, [bz_lives]          ; the bracket's end), quietly - never in
    dec ax                      ; EXPLORE (8c)
    call bz_gstorl
    call bz_dwrite
.nolife:
    mov al, [bz_pwck]
    mov [bz_crs], al
    call bz_gcrs                ; (no INTRO card any more, 130.22.6)
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
    mov byte [bz_susp], BZ_SU_CRS ; its log (SPEC.md 130.26.4)
    ret
.ntw:
    cmp byte [bz_goal], 0       ; A COURSE: a finish ... (no RESULT card, 130.22.6)
    je .life
    call bz_dslot               ; the exit FOUND (130.19.6), a word a PAD
    mov bl, [bz_ppad]           ; (130.22.5.1), in either mode
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
    or al, al                   ; wave 8c (130.19.8): a RETRY from the pause
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
    call OSAPI_MEM_P            ; AX = the largest claim there is: it takes the
    sub ax, BZ_CRS_MAXCLAIM + BZ_CRS_ARMAX ; course's AND the arena's (130.25.4.2)
    jb bz_phfree
    xchg ax, bx                 ; ...and THE KIT's, when it is not here yet
    mov al, BZ_P_KIT            ; (SPEC.md 130.37.5: the pathway is the part
    call op_seg                 ; dropped, never the kit or the course)
    or ax, ax
    jnz .out
    cmp bx, BZ_KIT_CLAIM
    jb bz_phfree
.out:
    ret
; bz_kget - THE KIT (SPEC.md 130.37.5): BZKIT.BIN fetched unless it is here
; (op_fetch of a row already fetched does nothing, CF = 0) - and then HELD: no
; way out of BONANZA but the close drops it.  CF = 1 refused (op_fetch said
; why).  bz_kget0: the same with op_fetch QUIET (OP_SAYGATE), bz_entry's,
; whose refusal the next launch's bz_kget repeats aloud.  Clobbers AX - DI, ES.
bz_kget0:
    mov byte [bz_fs], 1
    call bz_kget
    mov byte [bz_fs], 0
    ret
bz_kget:
    mov al, BZ_P_KIT
    call op_fetch
    jc .r
    mov al, BZ_P_KIT            ; (its segment: the claim is pinned and held, so
    call op_seg                 ; the word stays good while the instance runs)
    mov [bz_kseg], ax
.r:
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
; bz_title8 - Enter on the face: THE TITLE (SPEC.md 130.23.4).  Its refusals
; are the game's (kern_small, the adapter); the title's rounds play inside ONE
; bracket (bz_fullscreen, [bz_ingame] 2: bz_tround), and whatever is held when
; it ends is given back; a game played from it is written to its slot.
; -----------------------------------------------------------------------------
bz_title8:
    mov byte [bz_newb], 0
    call bz_fsok
    jc .ret
    call OSAPI_GET_TICKS        ; the title's own LFSR, seeded from the clock
    xor ax, [bz_pitl]           ; (never read by physics: replays stay exact)
    or ax, 1
    mov [bz_tlfsr], ax
    mov byte [bz_tlast], 0ffh
    mov byte [bz_towin], 0
    call bz_shdrop              ; (never beside a course, 130.19.2)
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
    cmp byte [bz_susp], BZ_SU_CRS ; SUSPENDED in a course (130.26.4): its parts,
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
    jmp bz_back                 ; (nothing written: the course's life is, 130.19.6)
.drop:
    call bz_vdrop               ; (the VGA's part, 130.46.6)
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
; bz_tround - inside the bracket, the mode set: THE TITLE'S ROUNDS (130.23.4).
; A title demo (random, never the last one shown) on the title course, its
; keys bz_exitchk's title arm's: P or Enter plays THE GAME (bz_grounds, its end back
; here), S / 1 2 3 the slot, Esc leaves the bracket; its end plays a random
; COURSE DEMO, which any key ends; then the title again.  Each round's parts
; are given back before the next's are fetched.
; -----------------------------------------------------------------------------
bz_tround:
    mov al, [bz_susp]           ; PLAY GAME after the window (SPEC.md 130.26.4):
    or al, al                   ; the pathway, or the course, where it was left
    jz .title
    mov byte [bz_susp], 0
    cmp al, BZ_SU_CRS
    jne .game
    mov byte [bz_tmode], 0
    mov byte [bz_tgame], 1
    mov byte [bz_rsm], 1        ; (bz_play: no bz_pinit, no new log)
    call bz_grounds.crs
    jmp .gout
.title:
    mov byte [bz_tmode], 1
.pick:
    call bz_trand               ; a title demo, never the last one shown
    and al, BZ_TNDEMO - 1
    cmp al, [bz_tlast]
    je .pick
    cmp byte [bz_tnew], 0       ; a FIRST RUN's first: a RUBBER one (SPEC.md
    je .pk                      ; 130.23.3.1, BZ_TRUBBER)
    mov cl, al
    mov ah, 1
    shl ah, cl
    test ah, BZ_TRUBBER
    jz .pick
    mov byte [bz_tnew], 0
.pk:
    mov [bz_tlast], al
    call bz_tdemo               ; its start block and its log (bz_tblk, bz_rlog)
    jc .out
    mov byte [bz_crs], BZ_CRS_TITLE
    call .demo                  ; the log's ball, a replay, fetched
    jc .out
    mov al, [bz_slot]           ; the slot's label (130.23.2): pose 1 + slot
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
    call .play                  ; (any key, its end or a timeout: the title;
    cmp byte [bz_twhy], 27      ; Esc, F or Alt+Enter leave the bracket as
    je .out                     ; on the title, SPEC.md 130.23.4.1)
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
    je .gsus                    ; part held, nothing stored, 130.26.4)
    call bz_phfree              ; (the held pathway goes with the game, 130.22.7:
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
; bz_tblk and its log into the session's (bz_rin), the part given back.  CF = 1
; refused (the kit, the log's home, refused too: bz_rkit).
bz_tdemo:
    call bz_rkit
    jc .out
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
    mov di, bz_tblk             ; (bz_rlog follows bz_tblk: the block and the
    mov dx, BZ_TSTART + BZR_RUNS ; header one copy, then the runs)
    jmp short bz_tcopy

; bz_tlog - part AL (a shipped demo, BZD<K>) into the session's log (bz_rin),
; given back.  CF = 1 refused (or the kit, the log's home: bz_rkit).
bz_tlog:
    call bz_rkit
    jc bz_tdemo.out
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
    mov dx, BZR_RUNS
bz_tcopy:                       ; CX bytes from the part (ES) at SI: DX to DI,
    mov byte [bz_rown], 0       ; the rest the runs (the log no longer a play
    call bz_rin.di              ; the player made)
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
; 1 + slot (a PK_SIGN, 130.23.2; bz_nset marks its lane, 130.22.4.1), so the
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
bz_dcrs:        BZ_DEMO_CRS     ; each shipped demo row's course K (130.14.7.4)
bz_pexits:      BZ_PAD_EXITS    ; each pad's course's exits, a bit each (130.22.5.1)
 %if BZ_PATH_NPAD > 32
  %error "the save keeps a bit a pad in a dword (SPEC.md 130.22.5)"
 %endif
%endif

; bz_cdrop - the course's part and its families' given back (op_drop of a part
; that is not here is a no-op, so all go whichever failed), their words 0 -
; NEVER the balls, held in the bundle for the instance (SPEC.md 130.25.5.2).  The
; song is bzs_gdrop's.  Preserves nothing.
bz_cdrop:
    xor ax, ax                  ; SPEC.md 130.50.3: the song is the course
    mov [bzs_live], al          ; part's - the sequencer lets go of it before
    mov [bzs_mseg], ax          ; the part is given back
    push ds                     ; ES = ours, not whatever the bracket left:
    pop es                      ; op_drop restores its caller's ES after the
                                ; free, and on kern_mega a part's own selector
                                ; there is a #GP once its claim is gone (the
                                ; final pass of wave 1: bonanzamega's fault at
                                ; op_drop's POP ES, the ball's selector in ES)
    call bz_fhz                 ; wave 9 (SPEC.md 130.25.6.2): no hook active
%if BZ_NFFETCH                  ; (bz_fhk, bz_fnf 0, every list empty), the
                                ; FETCHED families' parts
    mov ax, BZ_P_FAM + BZ_NFFETCH ; first, the reverse of the fetch's order (a
.dfam:                          ; row not here is a no-op, so a course with none
    dec ax                      ; drops none; a build with none has no loop) -
    call op_drop                ; never the RESIDENT BUNDLE, the last row (SPEC.md
    cmp al, BZ_P_FAM            ; 130.25.6.9: the arena's floor). (op_drop
    ja .dfam                    ; preserves AX)
%endif
                                ; (NO BALL: held for the instance, 130.25.5.2)
    xor ax, ax                  ; ...and a reservation nothing was fetched
    call op_areserve            ; into given back (a refused first fetch)
    mov al, [bz_pc]
%if BZ_PATH_NPAD
    cmp al, BZ_P_PATH           ; the HELD pathway's part stays (130.22.7)
    jne .dpc
    cmp byte [bz_phold], 0
    jne .held
.dpc:
%endif
    call op_drop
%if BZ_PATH_NPAD
.held:
%endif
%if BZ_NCRS2
    mov al, BZ_P_CRS + BZ_NCRS + BZ_NCRS2 ; every two-part course's WORLD part
.dw:                            ; (SPEC.md 130.30.5): a row not here is a
    dec ax                      ; no-op (op_drop preserves AX)
    call op_drop
    cmp al, BZ_P_CRS + BZ_NCRS
    ja .dw
%endif
    xor ax, ax                  ; (bz_bsegs kept: the balls are)
    mov [bz_cseg], ax
%if BZ_NCRS2 + BZ_NSHC
    mov [bz_mseg], ax
%endif
%if BZ_NSHC
    mov [bz_shn], al            ; (and its sheets with it - segments of its one
                                ; part, their selectors going with its claim:
                                ; SPEC.md 130.30.12.5)
%endif
    mov [bz_bseg], ax
    ret

; -----------------------------------------------------------------------------
; bz_bget - THE BALLS, HELD (SPEC.md 130.25.5.2): the RESIDENT BUNDLE fetched
; if it is not here - the three balls at its head, BZB3, generated in place
; at once (bz_ballgen, each AX its segment), bz_bform 0 - and a CGA launch
; that finds them Hercules-translated (bz_bform 1: no way back, 130.11.3)
; drops the bundle and reads it again.  bz_entry's and bz_cload's: ONCE an
; instance on one card.  bz_bsegs is right after it.  CF = 1 refused
; (op_fetch said why).  Preserves nothing.
; -----------------------------------------------------------------------------
bz_bget:
    mov al, BZ_P_FBUN
    call op_seg
    or ax, ax
    jz .get
    cmp byte [bz_herc], 0       ; here: a Hercules launch translates them
    jne .ok                     ; itself (bz_hxlat), the CGA wants their own
    cmp byte [bz_bform], 0      ; (0: the CGA's already)
    je .ok
    push ds                     ; (op_drop with ES = ours)
    pop es
    mov al, BZ_P_FBUN
    call op_drop
.get:
    mov al, BZ_P_FBUN
    call op_fetch
    jc .r
    call bz_bsload
    mov si, bz_bsegs
.g:
    lodsw
    push si
    call bz_ballgen             ; BZB3 -> BZB2 in place (130.25.5): AX, ES kept
    pop si
    cmp si, bz_bsegs + 2 * BZ_NMAT
    jb .g
    mov byte [bz_bform], 0
.ok:
    clc
.r:
    ret

; bz_bsload - bz_bsegs[m] = ball m's segment inside the bundle (0: not here):
; OSAPI_SEG's SEG_SUB over the bundle's data segment at its paragraph (the
; sum on a real-mode kernel; kern_mega's DATA selector there, the same one
; each time, moving with the arena), rubber's the bundle's own.  Preserves
; ES and BP.
bz_bsload:
    mov al, BZ_P_FBUN
    call op_seg
    mov [bz_bsegs], ax
    xchg ax, dx
    mov ax, BZ_BALPS
    call .sub
    mov [bz_bsegs + 2], ax
    mov ax, BZ_BALPG
    call .sub
    mov [bz_bsegs + 4], ax
    mov ax, BZ_SNDP             ; SPEC.md 130.50.2: and the SOUND after them -
    call .sub                   ; the sound part, VICTORY and TIME'S UP
    mov [bzs_pseg], ax
    mov ax, BZ_VICP
    call .sub
    mov [bzs_vseg], ax
    mov ax, BZ_TUPP
    call .sub
    mov [bzs_tseg], ax
    jmp bzs_ptab                ; (its tables: the header's, copied)
.sub:                           ; AX = DX + AX paragraphs, 0 for none
    or dx, dx
    jz .z
    push dx
    mov bl, SEG_SUB
    xor cx, cx
    call OSAPI_SEG
    xchg ax, dx
    pop dx
    jnc .r
.z:
    xor ax, ax
.r:
    ret

; -----------------------------------------------------------------------------
; bz_crshdr - the fetched course part's header, copied into our data (SPEC.md
; 130.10.6.4, 130.10.8 item 4): the writers' map shift and stride, the camera's
; limits' inputs, the grid's place, X0 and Y0 (and the projection's
; constants physics derives the screen position with), and the route.  The
; start is physics's (bzphys.inc bz_pinit).  Nothing is checked: the part was
; checked when it was built (130.10.6.2).  DS = ours, [bz_cseg] the course.
; Preserves nothing.
; -----------------------------------------------------------------------------
bz_crshdr:
    mov word [bz_acptr], -1     ; (SPEC.md 130.29: the model's cell, emptied,
    mov word [bz_awx], -1       ; its grid cell,
    mov word [bz_axe], bz_axl   ; no extra slot (130.49.3),
    mov word [bz_omp], bz_omsk  ; and bz_olay's mask in our segment)
    push es
    mov es, [bz_cseg]
    call bz_fsbset              ; SPEC.md 130.28.7: the FIELD tables' offsets
    mov ax, [es:BZC_COLS]
    mov [bz_cols], ax
    mov ax, [es:BZC_BROWS]
    mov [bz_brows], ax
    mov ax, [es:BZC_ROWB]
    mov [bz_rowb], ax
    xchg ax, dx                 ; SPEC.md 130.10.4.2: bz_mrow[br] = MAP + br
    mov ax, BZC_MAP             ; ROWB, every row the table holds (BZ_MROWS,
    mov bx, bz_mrow             ; the tool's bound on BROWS): the writers'
.mrow:                          ; block row's map, any COLS (no shift)
    mov [bx], ax
    add ax, dx
    inc bx
    inc bx
    cmp bx, bz_mrow + 2 * BZ_MROWS
    jne .mrow
%if BZ_NSHC
    mov word [bz_shlo], 8000h   ; SPEC.md 130.30.12.3: one picture part - no
    mov word [bz_shhi], 7fffh   ; window leaves it
    mov byte [bz_shn], 0
    mov bl, [bz_crs]
    cmp bl, BZ_NCRS
    jae .nsh
    xor bh, bh
    mov al, [bz_cshn + bx]
    or al, al
    jz .nsh
    mov [bz_shn], al            ; a SHEETED course: sheet 0 shown, its rows
    shl bx, 1                   ; (bz_shmrow over the table above)
    mov si, [bz_cshi + bx]
    add si, bz_shtab
    mov [bz_shent], si
    mov byte [bz_shcur], 0
    call bz_shmrow
    mov word [bz_shlo], 7fffh   ; ...and its bounds EMPTY: the card's bz_lsh may
    mov word [bz_shhi], 8000h   ; not be this launch's yet, so the first window
.nsh:                           ; searches (bz_shfind, on the first frame's cut)
%endif
    mov di, [es:BZC_GRID]
    mov [bz_goff], di
%if BZ_TITLE
    mov byte [bz_fixed], 0      ; SPEC.md 130.23.2: a FIXED window - BZG1 +30
 %if BZ_PATH_NPAD
    mov byte [bz_paged], 0      ; (wave 8R, 130.22.4.3: or PAGED, bit 3, +30
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
    cmp byte [bz_vga], 0        ; (the VGA's rows are lines: x 4, 130.46.3)
    je .vs
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
    cbw                         ; (SPEC.md 130.15.4.1, 130.15.5.2): SB signed
    mov [bz_osbias], ax
    mov ax, [es:BZC_TB]
    mov [bz_otb], ax
    mov ax, [es:BZC_MTAB]
    mov [bz_mtab], ax
%if BZ_NCRS2 + BZ_NSHC
    mov es, [bz_mseg]           ; (the occluders: the PICTURE part, 130.30.5)
%endif
    call bz_osmake              ; ...and its rows' summary (bzvideo.inc bz_occ)
    mov ax, [bz_x0]             ; the projection's constants, 24.8 (130.10.8):
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
; its t' its byte +2 (SPEC.md 130.15.5.1).  DS = ours, ES = the course part
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
; bz_cexp - THE COURSE PART EXPANDED IN PLACE (SPEC.md 130.15.4.4, 130.15.4.5),
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
; length; nothing through CS, no segment arithmetic (130.15.11).
; DS = ours, [bz_cseg] the part.  Preserves BP, DS, ES.
; -----------------------------------------------------------------------------
bz_cexp:
    push bp
    push es
    cld
    mov es, [bz_cseg]           ; ES = the part (the walk reads it with ES:)
    call bz_dfind               ; D3: sections C and D (bz_drec's bounds)
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
    mov dx, [es:bx]             ; DL = the TAG, DH = the FORM (KITREF's class)
    mov bl, dh
    xor bh, bh
    shl bx, 1
    push ds
    call [bx + bz_cxtab]        ; (DS = ours: the table is ours)
    pop ds
    pop bx
    pop cx
    add bx, BZX_ENTB
    loop .ent
    call bz_dval                ; D3: no split cell names records outside D
    pop es
    pop bp
    ret

; -----------------------------------------------------------------------------
; D3 (SPEC.md 130.24.5.2): A PART IS HOSTILE, so a split cell's +0 - +1 - an
; offset IN the part, read through - is BOUNDED before anything reads through
; it: inside section D, 4-aligned from D's start, its 2 (TB, LR) or 4
; (QUARTERED) records within D's length; a kind 7 - 15 is no split this build
; reads.  bz_dfind: bz_dlo, bz_dhi = D's [offset, end) and bz_clo, bz_chi =
; C's (0, 0 when the part has none), off the directory, whose entries the walk
; trusts as it trusts every other entry.  ES = the part.  Clobbers AX, BX,
; CX, DX.
bz_dfind:
    xor ax, ax
    mov [bz_ffo], ax
    mov [bz_ffe], ax
    mov [bz_dlo], ax
    mov [bz_dhi], ax
    mov [bz_clo], ax
    mov [bz_chi], ax
    mov bx, [es:BZC_DIROFF]
    mov cx, [es:BZC_NSEC]
    jcxz .r
.e:
    mov al, [es:bx]             ; the entry's tag
    mov dx, [es:bx + BZX_OFF]
    cmp al, 'D'
    jne .c
    mov [bz_dlo], dx
    add dx, [es:bx + BZX_LEN]
    mov [bz_dhi], dx
    jmp short .n
.c:
    cmp al, 'F'                 ; (SPEC.md 130.28.2: the FIELD tables)
    jne .c2
    mov [bz_ffo], dx
    add dx, [es:bx + BZX_LEN]
    mov [bz_ffe], dx
    jmp short .n
.c2:
    cmp al, 'C'
    jne .n
    mov [bz_clo], dx
    add dx, [es:bx + BZX_LEN]
    mov [bz_chi], dx
.n:
    add bx, BZX_ENTB
    loop .e
.r:
    ret

; bz_fsbset - bz_fsb[i] = section F's offset + 289 i (SPEC.md 130.28.7): the
; tables bz_fhp reads, off the directory (no F: offsets from 0, never read -
; no cell is a FIELD one).  ES = the part.  Clobbers AX, BX, CX.
bz_fsbset:
    xor ax, ax
    mov bx, [es:BZC_DIROFF]
    mov cx, [es:BZC_NSEC]
    jcxz .f
.e:
    cmp byte [es:bx], 'F'
    jne .n
    mov ax, [es:bx + BZX_OFF]
.n:
    add bx, BZX_ENTB
    loop .e
.f:
    mov bx, bz_fsb
    mov cl, BZ_FSHAPE_MAX
.t:
    mov [bx], ax
    add ax, BZ_FIELDTAB
    inc bx
    inc bx
    loop .t
    ret

; bz_drec - ES:SI a cell of kind AL (4 - 15): CF = 0 and SI its records'
; offset when they lie in D as 130.24.5.2 says, else CF = 1.  Preserves all
; but SI and the flags.
bz_drec:
    push ax
    mov ah, BZ_PAIR
    cmp al, BZ_KQ
    ja .bad                     ; (7 - 15: no split this build reads)
    jb .h
    mov ah, BZ_QUAD
.h:
    mov si, [es:si]
    mov al, ah
    cbw
    add ax, si                  ; AX = the records' end
    jc .bad
    cmp ax, [bz_dhi]
    ja .bad
    mov ax, si
    sub ax, [bz_dlo]
    jb .bad
    test al, 3
    jnz .bad
    pop ax
    clc
    ret
.bad:
    pop ax
    stc
    ret

; bz_dval - after the walk: every cell of C whose kind is a split's (4 and
; above) and whose records bz_drec refuses becomes an OPEN cell (z0 -128,
; flat, VOID, no flags), and every record of D a kind 0 - 3 (above: VOID) -
; so the step's window (bz_wsplit) and bz_blocks read only D and only a
; record of 130.24.5.2's kinds.  A part the tool built has neither (its
; read_part checks them).  SPEC.md 130.28.2: a FIELD cell whose shape (its
; +1's bits 0 - 3, bit 7 the fifth) is not inside F becomes OPEN.  ES = the
; part.  Clobbers AX,
; BX, CX, DX, SI.
bz_dval:
    mov bx, [bz_clo]
.c:
    cmp bx, [bz_chi]
    jae .d
    mov al, [es:bx + 2]
    and al, 0fh
    cmp al, BZ_KTB
    jb .cn
    cmp al, BZ_KFIELD           ; a FIELD cell: its shape (five bits)
    je .cf                      ; inside F (else OPEN)
    mov si, bx
    call bz_drec
    jnc .cn
.co:
    mov word [es:bx], BZ_ZOPEN
    mov word [es:bx + 2], 0
.cn:
    add bx, 4
    jmp short .c
.cf:
    mov al, [es:bx + 1]
    cbw                         ; AH = FFh when bit 7, the shape's fifth bit
    and ax, 100fh
    or al, ah
    xor ah, ah                  ; AX = the shape, 0 - 31
    mov si, BZ_FIELDTAB
    mul si                      ; (launch-only: one MUL a FIELD cell)
    add ax, BZ_FIELDTAB
    add ax, [bz_ffo]
    jc .co
    cmp ax, [bz_ffe]
    ja .co
    jmp short .cn
.d:
    mov bx, [bz_dlo]
.r:
    lea ax, [bx + 4]
    cmp ax, [bz_dhi]
    ja .out
    test byte [es:bx + 2], 0ch  ; a record's kind 4 - 15: VOID
    jz .rn
    and byte [es:bx + 2], 0f0h
.rn:
    add bx, 4
    jmp short .r
.out:
    ret

; THE FORMS: SI = the stored bytes, DI = the slot, CX = its RAM length, DL =
; the section's tag, DS = ours, ES = the part.  Each may change DS (bz_cexp
; restores it), and clobbers AX, BX, CX, DX, SI, DI, BP.
bz_cxtab:
    dw bz_cxret                 ; 0 PLAIN: in place already
    dw bz_cxmap                 ; 1 ROWPLANES
    dw bz_cxcnt                 ; 2 COUNTS
    dw bz_cxdif                 ; 3 WDIFF
    dw bz_cxmtb                 ; 4 MASKTAB (the 4-byte record's, D)
BZ_CXFORMS  equ 1FFh
    dw bz_cxrtb                 ; 5 ROWTAB
    dw bz_cxway                 ; 6 WAYS
    dw bz_cxcel                 ; 7 CELLS
    dw bz_cxkit                 ; 8 KITREF (SPEC.md 130.37.4)
%if BZ_FORMS & ~BZ_CXFORMS
 %error "bz_cexp: a course part uses a stored form its dispatch table does not hold"
%endif
%if BZ_REC != 4
 %error "bonanza: the occluder pass reads D's 4-byte records (SPEC.md 130.15.5.4); bzcourse.inc's BZ_REC is not 4"
%endif

; 8 KITREF (SPEC.md 130.37.4): the section's pieces at the head of its slot
; are THE KIT's, named by a bitmap (bit i of byte i >> 3, low bit first: kit
; piece i of the class), stored first and then the course's own pieces, which
; are the slot's tail and in place already.  The kit's class is found by the
; tag (its header's entries: tag, 0, a piece's bytes, the pieces, their
; offset); the bitmap is copied to scratch (bz_boxbuf: the pieces written
; from the slot's start overtake it) and each piece named is copied from the
; kit, in order, from the slot's start.  The walk counts with the kit's own
; count, the copy with its piece size: the tool proves the pieces named fill
; exactly the slot's head.  The kit is read through its own segment (kern_mega:
; its LDT selector, op_seg's, kept in bz_kseg by bz_kget), never through CS.
bz_cxkit:
    mov ds, [bz_kseg]           ; DS = the kit (bz_kget's: fetched before any
                                ; play course, held)
    mov bx, BZK_ENT
.cls:
    cmp [bx], dl                ; the class (the tool: it is there)
    je .got
    add bx, BZK_ENTB
    jmp short .cls
.got:
    mov bp, [bx + 2]            ; BP = a piece's bytes
    mov cx, [bx + 4]
    mov dx, [bx + 6]            ; DX = kit piece 0 of the class
    pop ax                      ; (the return address: our DS under it)
    pop ds                      ; DS = ours, and kept on the stack for
    push ds                     ; the walk's returns from the kit
    push ax
    add cx, 7                   ; CX = the bitmap's bytes
    shr cx, 1
    shr cx, 1
    shr cx, 1
    jcxz .out
    mov bx, bz_boxbuf
    push cx
.cp:
    es lodsb                    ; the bitmap to scratch
    mov [bx], al
    inc bx
    loop .cp
    pop cx
    mov bx, bz_boxbuf
.byte:
    mov al, [bx]                ; DS = ours
    inc bx
    mov ah, 8
.bit:
    shr al, 1
    jnc .next
    push cx
    mov si, dx
    mov cx, bp
    mov ds, [bz_kseg]           ; DS = the kit: one piece to ES:DI
    shr cx, 1
    rep movsw
    adc cx, cx                  ; (an odd size: a table's 289)
    rep movsb
    pop cx
    pop si                      ; DS = ours again, from under the
    pop ds                      ; return address
    push ds
    push si
.next:
    add dx, bp
    dec ah
    jnz .bit
    loop .byte
.out:
    ret

; 1 ROWPLANES: block row r stored as C/4 high bytes (cell j's two high bits at
; bits 2 (j AND 3) of byte j >> 2) and then C low bytes; map word j = BLKOFF +
; 16 (low + 256 high).  The row's high bytes go to scratch (bz_boxbuf, at most
; 32) first, because the words of a late row overrun them.  COLS and BROWS
; count.
bz_cxmap:
    mov bp, [es:BZC_BLKOFF]
%if BZ_NSHC
    xchg ax, cx                 ; SPEC.md 130.30.12.1: its RAM length / ROWB
    xor dx, dx                  ; counts (a SHEET's map is n rows, every other
    div word [es:BZC_ROWB]      ; part's BROWS)
    xchg ax, dx
%else
    mov dx, [es:BZC_BROWS]
%endif
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
; top-left on the tile's centre (the tool's rule, 130.10.4.5):
;   x = 16 a + X0 - 8,  y = 8 s - 2 (z0 + sx + sy) + Y0 - 5 (z0 QUARTER units,
; SPEC.md 130.48),
; s = wx + wy, a = wx - wy, z0, sx and sy the tile's CELL's, found as
; bzphys.inc finds a cell: ROWTAB[s - SMIN] + 4 ((a - AMIN) >> 1).  NWAY
; counts; way w's words end before way w + 1's stored pair.  A way on a FIELD
; cell (SPEC.md 130.28.10) is at GROUND height, y = 8 s + Y0 - 5 (its +1 is a
; shape, not slopes), and MARKED: bit 0 of its x flipped (bz_auto's test).
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
    mov ch, [si]                ; +2: the kind (low nibble)
    pop si
    and ch, 15
    cmp ch, BZ_KFIELD
    je .fld
    mov ch, ah
    sar ch, cl                  ; CH = sy
    shl ah, cl
    sar ah, cl                  ; AH = sx
    add ch, ah                  ; CH = sx + sy
    cbw                         ; AX = z0
    xchg ax, cx
    mov al, ah
    cbw
    add ax, cx
    shl ax, 1                   ; AX = 2 (z0 + sx + sy)
    mov cl, 3
    shl dx, cl
    sub dx, ax
    add dx, [bx + BZG_Y0]
    sub dx, 5
.y:
    xchg ax, dx
    stosw                       ; y
    pop cx
    loop .way
    ret
.fld:                           ; a FIELD way (130.28.10): x marked, y at the
    xor word [di - 2], 1        ; ground's height
    mov cl, 3
    shl dx, cl
    add dx, [bx + BZG_Y0]
    sub dx, 5
    jmp short .y
; 7 CELLS (SPEC.md 130.15.6): each cell as in RAM but two fields, each stored
; as its difference from the RULE: a VOID cell's z0 as z0 - rule_z0 (8 bits),
; and every cell's SAFE bit XOR rule_safe.  The rule, as the tool builds the
; grid (bbcourse.cells_rule is this routine's model):
;   V = a cell's lowest corner + 73h, z0 + 2 min(0, sx) + 2 min(0, sy) + 73h
;       in 8 bits (z0 QUARTER units, SPEC.md 130.48.3), UNSIGNED, for a cell
;       that is not VOID; FFh for a VOID cell and outside the grid
;   rule_z0 = the least V within two tiles (Chebyshev in wx and wy) + 81h:
;       the least corner less 12 (NEAR), or FFh + 81h = -128 (OPEN).  The bias
;       makes OPEN's value the sentinel's and the order the corners' for every
;       corner a NEAR cell can hold (-116 .. 127; -116's NEAR z0 IS -128)
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
; About 0.19 s on PEAK, with bz_cxsafe (priced, 130.15.6).
BZ_CXRW     equ 44              ; an A row's stride: a pad, KW cells, a pad (1,280 px)
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
    test byte [es:si + 2], 0ch  ; D3: a SPLIT cell (kind 4 - 15): its V by its
    jnz .ssp                    ; records (130.24.5.3); 130.28.2: a FIELD's, its z0's
    mov dx, [es:si]             ; DL = z0, DH = sy : sx
    call .v
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
    add al, 81h                 ; the least corner - 12, or FFh + 81h = -128
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
.v:                             ; DL = z0, DH = sy : sx (CL = 4) -> AL = V,
    mov al, 73h                 ; z0 + 2 min(0, sx) + 2 min(0, sy) + 73h, in
    add al, dl                  ; quarter units (SPEC.md 130.48.3).  Clobbers
    test dh, 8                  ; DX
    jz .lx
    mov dl, dh
    or dl, 0F0h                 ; sx < 0
    add al, dl
    add al, dl
.lx:
    sar dh, cl                  ; DH = sy
    jns .lv
    add al, dh
    add al, dh
.lv:
    ret
.ssp:                           ; D3: a split cell's V, the least of its
    mov al, [es:si + 2]         ; records' that are not VOID (FFh: none, or
    and al, 15                  ; records bz_drec refuses) - or a FIELD cell's,
    cmp al, BZ_KFIELD           ; z0 + 73h (SPEC.md 130.28.2: its +1 is not
    jne .ssq                    ; slopes)
    mov dl, [es:si]
    xor dh, dh
    call .v
    jmp .ly
.ssq:
    push si
    push cx
    mov al, [es:si + 2]
    and al, 15
    mov ah, 0ffh
    call bz_drec                ; SI = its records
    jc .sx
    mov ch, 2
    cmp al, BZ_KQ
    jne .sr
    mov ch, 4
.sr:
    test byte [es:si + 2], 15
    jz .sn
    mov dx, [es:si]
    call .v
    cmp al, ah
    jae .sn
    mov ah, al
.sn:
    add si, 4
    dec ch
    jnz .sr
.sx:
    mov al, ah
    pop cx
    pop si
    jmp .ly

; bz_cxcel's SAFE: AL = the cell's surface : kind, AH = its flags, ES:SI =
; the cell, SS:BP bz_cxcel's frame; XORs rule_safe into the cell's flags
; (D3: a split edge neighbour by its record that owns the shared edge).
; Clobbers AX and DX.
bz_cxsafe:
    and al, 15
    cmp al, 1                   ; FLOOR
    jne .no
    test ah, BZ_FL_OBS          ; a prop's cell: never SAFE
    jnz .no
    cmp byte [es:si + 1], 0     ; sx = sy = 0
    jne .no
    mov dx, si
    add si, [bp + BZ_CXF_U]     ; row j - 1: cells k + p - 1 (west) and k + p
    mov al, 3                   ; (north) ...
    call .vd
    jz .nb
    add si, 4
    mov al, 1
    call .vd
    jz .nb
    mov si, dx
    add si, [bp + BZ_CXF_D]     ; ... then row j + 1's: south, east
    mov al, 7
    call .vd
    jz .nb
    add si, 4
    mov al, 5
    call .vd
    jz .nb
    mov si, dx
    xor byte [es:si + 3], BZ_FL_SAFE
.nb:
    mov si, dx
.no:
    ret
.vd:                            ; ES:SI an edge neighbour, AL its window index
    mov ah, [es:si + 2]         ; (bzphys.inc's BZN_*/4) -> ZF = 1 when it is
    and ah, 15                  ; VOID across the shared edge: VOID, or D3, a
    cmp ah, BZ_KTB              ; split one whose record that OWNS the edge is
    jae .vs                     ; (130.24.5.3; BZ_SPLIT_WIN, the model's OWNER).
    or ah, ah                   ; Preserves all but AX
    ret
.vs:
    cmp ah, BZ_KFIELD           ; SPEC.md 130.28.2: a FIELD neighbour is not VOID
    jne .vs2
    or ah, ah                   ; (ZF clear: AH is 7)
    ret
.vs2:
    push bx
    push si
    mov bl, al
    mov al, ah
    call bz_drec                ; SI = its records (refused: VOID)
    jc .vv
    sub al, BZ_KTB
    mov ah, 9
    mul ah
    add bl, al
    xor bh, bh
    mov al, [bz_swin + bx]
    and al, 3
    shl al, 1
    shl al, 1
    cbw
    add si, ax
    test byte [es:si + 2], 15   ; ZF = that record VOID
    pop si
    pop bx
    ret
.vv:
    xor ah, ah                  ; (ZF)
    pop si
    pop bx
    ret
; -----------------------------------------------------------------------------
; THE HERCULES MADE AT THE FETCH (SPEC.md 130.11.3).  A Hercules byte is the
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
; one by its picture (SPEC.md 130.11.17.2).  DS = ours.  Preserves nothing.
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
; BZ_HTAB (SPEC.md 130.11.3), on the Hercules, before the bracket:
;   the course's blocks, BLKOFF .. BLKOFF + 16 N: a block line is ONE WORD, its
;     index in the block the line, so the table changes every two bytes (8
;     lines a block, even: one run of 8 N rows of 2 bytes from table 0);
;   the ball's ROLL frames: frame f's row r through ((f >> 3) + r) & 1, so each
;     run of 8 frames is 128 rows of 5 bytes from table (f >> 3) & 1;
;   the FRAME half of each squash, shatter and stretch entry (frame x shift
;     x parity copy p x (mask 80, frame 80)): 16 rows from table p;
;   a PLATFORM's sprite (wave 3, SPEC.md 130.12.6.4): parity copy p x (mask
;     144, frame 144), the frame's row r through table (p + r) AND 1.
; Every ball part this launch fetched (bz_bsegs, wave 4), each the same way.
; Masks and the shadow are the same bytes on both cards and are not touched.
; XLAT reads DS:BX + AL, so DS = OURS (the table, in our bss) and the part is
; ES (`es lodsb`, `stosb`, SI = DI): on kern_mega ES is the part's own
; selector, written whole at offsets under its length, as op_fetch's expand
; already writes it; nothing through CS (SPEC.md 130.11.14).  DS = ours.
; Preserves nothing; ES is left the ball's (bz_launch saves and restores it).
; -----------------------------------------------------------------------------
bz_hxlat:
    mov bx, bz_boxbuf           ; BX = table 0, BP = the toggle to table 1 and
    lea bp, [bx + 256]          ; back: table 0 ^ table 1, two byte bases 256
    xor bp, bx                  ; apart (any alignment)
%if BZ_PATH_NPAD
    cmp byte [bz_phre], 0       ; a HELD pathway was translated when it was
    jne .noplat                 ; fetched: the balls alone (130.22.7)
%endif
    mov es, [bz_mseg]           ; the course: 8 N rows of 2 bytes (its PICTURE part)
    mov si, [es:BZC_BLKOFF]
    mov cx, [es:BZC_NBLK]
    shl cx, 1
    shl cx, 1
    shl cx, 1
    mov dl, 2
    call bz_hxrows
%if BZ_NCRS2 + BZ_NSHC
    mov es, [bz_cseg]           ; (the sprites: the WORLD part, 130.30.5)
%endif
    mov cx, [es:BZC_NPROP]      ; the PLATFORMS' sprites (SPEC.md 130.12.6.4):
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
    jmp short .noplat           ; (ONE sprite, every lift's: SPEC.md 130.12.4.7)
.pnext:
    add di, BZ_PROPREC
    loop .prec
.noplat:
    cmp byte [bz_bform], 0      ; the three HELD balls (130.25.5.2): translated
    jne .nbr                    ; ONCE, then marked so (bz_bget)
    inc byte [bz_bform]
    mov di, bz_bsegs
.nb:
    push di
    mov es, [di]
    call bz_hxball
    pop di
    inc di
    inc di
    cmp di, bz_bsegs + 2 * BZ_NMAT
    jb .nb
.nbr:
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
; AL = frames of entries at SI: each frame's BZ_BAL_SHIFTS entries, ONE line
; parity copy each (SPEC.md 130.38.10), every frame half 16 rows from table 0
bz_hxents:
    mov ah, BZ_BAL_SHIFTS       ; (one parity copy each, SPEC.md 130.38.10)
    mul ah
    or ax, ax
    jz .out
    mov dh, al                  ; (at most 4 x 8 entries)
    mov bx, bz_boxbuf
.ent:
    add si, BZ_BAL_ENT / 2      ; past the mask half to the frame half
    mov cx, BZ_BAL_ROWS
    call bz_hxrows              ; (even: back on the copy's own table)
    dec dh
    jnz .ent
.out:
    ret

%if BZ_NSHC
; -----------------------------------------------------------------------------
; bz_hxshs - SPEC.md 130.30.12.5: a SHEETED course's sheets past 0, each one's
; blocks through BZ_HTAB as bz_hxlat translates sheet 0's (the lifts' sprites
; are the world part's, translated once; the blocks are the same in every
; sheet, at the same offsets).  None on any other course ([bz_shn] 0).
; bz_vshs - the VGA's: each sheet past 0 converted by BZV_CONV with bz_vcp 1
; (its blocks and masks alone), bz_mseg sheet 0's again after.  Each through
; the sheet's own segment (kern_mega: its selector, op_seg's): nothing
; computed on it.  Preserve nothing.
; -----------------------------------------------------------------------------
bz_hxshs:
    mov cl, [bz_shn]
    mov di, bz_shseg + 2
.s:
    dec cl
    jle .out                    ; (0 or 1 sheets: none past 0)
    push cx
    push di
    mov bx, bz_boxbuf           ; (bz_hxlat's tables, made by bz_hgen)
    lea bp, [bx + 256]
    xor bp, bx
    mov es, [di]
    mov si, [es:BZC_BLKOFF]
    mov cx, [es:BZC_NBLK]
    shl cx, 1
    shl cx, 1
    shl cx, 1
    mov dl, 2
    call bz_hxrows
    pop di
    pop cx
    inc di                      ; (the next sheet's: CL counts them down)
    inc di
    jmp short .s
.out:
    ret
bz_vshs:
    mov cl, [bz_shn]
    mov di, bz_shseg + 2
.s:
    dec cl
    jle .out
    push cx
    push di
    mov ax, [di]
    mov [bz_mseg], ax
    mov byte [bz_vcp], 1
    BZ_VCALL BZV_CONV
    mov byte [bz_vcp], 0
    pop di
    pop cx
    inc di
    inc di
    jmp short .s
.out:
    mov ax, [bz_shseg]
    mov [bz_mseg], ax
    ret
%endif

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
    jne .q                      ; a refusal there says nothing, 130.26.3)
    push es
    push ds
    pop es
    xor cx, cx
    call OSAPI_TOAST
    pop es
.q:
    ret

TOASTSTR bz_t_small, 'Bonanza: too little RAM'
TOASTSTR bz_t_adapt, 'CGA, HERC OR VGA ONLY'
TOASTSTR bz_t_nofs, 'Bonanza: no full screen'

; -----------------------------------------------------------------------------
; THE FACE (SPEC.md 130.14.3.2): two PAGES, [bz_page] 0 MAIN and 1 RESULTS.
; Every line is ONE opaque OSAPI_FONT_RUN padded with spaces to the content's
; width (the padding is the erase, SPEC.md 6.1), and only the 2px gaps between
; lines and the strip under the last one are filled: no pixel is written
; twice.  The lines are built in bz_lbuf.  MAIN's seven are a builder each
; (bz_ftab), so a key redraws exactly the lines it changed (bz_redraw); the
; RESULTS page is drawn whole and left by the next key.  EVERY LINE FITS THE
; CGA's 42 CELLS (130.14.17 item 2): each builder's widest output - its
; strings, which BZS measures, and its fields at their widest - is asserted
; under the strings (BZ_FIT), so a longer string fails the build.
; -----------------------------------------------------------------------------
BZ_NLINE    equ 7               ; MAIN's lines (SPEC.md 130.26.8: no scorecard, so MAIN
                                ; never grows with the courses).  The CGA's content
                                ; holds 13 lines of 42 cells; RESULTS draws all 13
BZ_LHEAD    equ 0               ; line 0: the title, or a refused replay's reason
BZ_FACEW    equ 42
BZ_TIMEW    equ 6               ; a time: `ss.hh`, `ssss.h` (from 100 s) or `20:00+`
BZ_FALLMAX  equ 9999            ; falls are shown, and filed, to four digits

; the face's three entries, each a far call into the SHELL PART (SPEC.md
; 130.19.2, bzshell.inc): bz_face paints it, bz_redraw redraws the 0FFh-ended
; line list at SI (in OUR segment), bz_redraw1 the one line AL
bz_face:
    mov al, BZH_FACE
    jmp short bz_shcall
%ifdef BZDEV
bz_redraw:
    mov al, BZH_REDRAW
    jmp short bz_shcall

bz_line4:                       ; S (bzsound.inc bzs_skey): the sound's line
    mov al, 4
bz_redraw1:
    mov ah, al                  ; the LINE vector's line is AH
    mov al, BZH_LINE
    jmp short bz_shcall

%endif
; -----------------------------------------------------------------------------
; bz_shcall - the SHELL PART's door (SPEC.md 130.19.2): AL = a vector (BZH_*),
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
    je .free                    ; face: the brief's, SPEC.md 130.26.4)
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

TOASTSTR bz_t_shell, 'Bonanza: bad part'   ; (the shell part's and a family part's, bz_ffetch)

; -----------------------------------------------------------------------------
; bz_vprep - THE VGA's ART (SPEC.md 130.46.5, 130.46.6), at the end of every
; bz_cload (at home; the bracket's own rounds included): BZVGA.BIN fetched if
; it is not held (stamped as the shell part is), its code alias taken again -
; every fetch before this one may have moved it - the balls' copies claimed
; once (BZV_PSIZE: one claim, held with the part), and the part's CONV run:
; the course's art in place, the three balls into the claim.  CF = 1 refused
; (toasted).  Preserves nothing.
; -----------------------------------------------------------------------------
bz_vprep:
    mov al, BZ_P_VGA
    call op_seg
    or ax, ax
    jnz .held
    mov al, BZ_P_VGA
    call op_fetch               ; (its refusal toasted)
    jc .out
    mov al, BZ_P_VGA
    call op_seg
    push es
    mov es, ax
    cmp word [es:0], BZV_SIG0
    jne .bad
    cmp word [es:2], BZV_SIG1
    jne .bad
    mov ax, [8]                 ; our image and bss sizes (OS88_HEADER)
    cmp ax, [es:BZV_IMAGE]
    jne .bad
    mov ax, [10]
    cmp ax, [es:BZV_BSSW]
    jne .bad
    pop es
.held:
    mov al, BZ_P_VGA
    call op_cseg
    mov [bz_vfp + 2], ax
    cmp word [bz_vbseg], 0
    jne .conv
    mov bl, MEMP_AVAIL          ; ASKED first (os88api.inc, SPEC.md 38.6): a
    call OSAPI_MEM_P            ; refused claim sheds the disk caches
    mov si, bz_t_nomem
    cmp ax, (BZV_PSIZE + 15) / 16
    jb .toast
    mov ax, (BZV_PSIZE + 15) / 16
    mov bl, MEMP_CLAIM
    call OSAPI_MEM_P            ; DX = the claim (pinned: MC_RLOC 0)
    jc .toast
    mov [bz_vbseg], dx
.conv:
    mov word [bz_vcpal], bz_cpals ; (two of our image's tables the part reads:
    mov word [bz_vspr0], bz_spr0  ;  a label crosses the link only through bss)
    BZ_VCALL BZV_CONV
    clc
.out:
    ret
.bad:
    pop es
    call bz_vdrop
    mov si, bz_t_shell
.toast:
    call bz_toast
    stc
    ret

; bz_vdrop - the VGA's part and the balls' copies given back (after a bracket
; that was not left suspended, and with the suspended course's drop).  Any
; card, any number of times.  Preserves every register.
bz_vdrop:
    push ax
    push dx
    push es
    push ds
    pop es
    mov dx, [bz_vbseg]
    or dx, dx
    jz .p
    call OSAPI_MEM_FREE
    mov word [bz_vbseg], 0
.p:
    mov al, BZ_P_VGA
    call op_drop
    pop es
    pop dx
    pop ax
    ret

; -----------------------------------------------------------------------------
; THE GAME'S BOOKS (SPEC.md 130.14.3.1, 130.14.3.3)
; -----------------------------------------------------------------------------
; bz_post - after the frame loop, IN the bracket (bzvideo.inc), so the face the
; kernel's restore paints is the new one: what the run just did, in memory
; only.  B: its RESULTS page.  A play or a replay: the held log's line (line
; 6).  A PLAY alone: a best, when it finished with the course's own ball
; under the 65,535-step clamp.
; [bz_newb] = 1 when a best was set: bz_dsave writes the file on the desktop.
; Preserves nothing.
bz_post:
%ifdef BZDEV
    mov al, [bz_res]            ; B and D: their results, when they ran to
    test byte [bz_mode], 1      ; their ends (D's line 3 names the demo, and
    jz .snap                    ; whether it measured all of it: bz_dtr)
    mov [bz_page], al
    ret
.snap:
%endif
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
    mov al, 3                   ; TIMEOUT (wave 7, 130.18.4)
.lse:
    mov [bz_lsend], al
    cmp byte [bz_mode], 0       ; a replay posts nothing
    jne .out
.best:
    cmp byte [bz_goal], 0       ; THE COURSE'S BEST: a finish, started with
    je .out                     ; the course's own ball, under the clamp, and
    mov bl, [bz_crs]            ; under the best (or none yet)
    xor bh, bh
    mov al, [bz_cballs + bx]
    cmp al, [bz_rlog + BZR_MAT]
    jne .out
    shl bx, 1                   ; the course's entry, by its SAVE KEY
    mov ax, [bz_ckeys + bx]     ; (130.22.5.1): its own, or an empty one
    mov di, bz_dat + BZD_ENT
    call bz_dbest
    mov ax, [bz_lsn]
    cmp ax, 0ffffh
    je .out
    mov cx, [si + 2]
    jcxz .set
    cmp ax, cx
    jae .out
.set:
    mov [si + 2], ax
    mov ax, [bz_lsf]
    mov [si + 4], ax
    mov ax, [bz_ckeys + bx]
    mov [si], ax
    mov byte [bz_newb], 1
.out:
    ret

; bz_dload - the entry proc's read of BONANZA.DAT (SPEC.md 130.14.3.3), and
; [bz_dat] made this build's whole image whatever it found.  The file is
; HOSTILE (§19): exactly BZD_FILE bytes and `BZS5` (no older layout is read,
; 130.22.5.1), then bz_dchk's whole-file checks
; (130.14.17 item 6) - any failure and it is treated as ABSENT; then
; bz_dnorm keeps an entry only under one of this build's SAVE KEYS, the
; first entry holding it, with a best 1 - 65,534.  A missing file or folder is the first run: silent.  kern_small
; refuses at the launch keys (130.1), so it reads nothing.  Preserves nothing.
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
%if BZ_TITLE
    jnc .rd
    cmp ax, FERR_NOENT          ; NO FILE: a first run (SPEC.md 130.23.3.1) -
    jne bz_dnorm                ; the title's first demo a rubber one
    mov byte [bz_tnew], 1
    jmp bz_dnorm
.rd:
%else
    jc bz_dnorm
%endif
    or dx, dx
    jnz bz_dnorm
    cmp ax, BZD_FILE            ; BZS5 (130.22.5.1): exactly BZD_FILE bytes; any
    jne bz_dnorm                ; other length (an older layout too) is unrecognised
    cmp word [bz_dat + 2], 'S5'
    jne bz_dnorm
    call bz_dchk
; CL = 1: keep what this build can file; 0: nothing (the first run's image).
; A file written under OTHER PHYSICS (+5 not this build's BZ_PHYSV: a 5b
; file's 0 among them, which is never BZ_PHYSV) keeps nothing either: its
; bests were times under other physics (SPEC.md 130.16.9) - the identities
; filed are this build's whatever it held, so that is the first run's image.
%if BZ_PHYSV == 0
 %error "BZ_PHYSV 0 is the unset value a 5b BONANZA.DAT holds (SPEC.md 130.16.9)"
%endif
bz_dnorm:
    or cl, cl                   ; a file refused whole keeps no slot either
    jnz .sl
    call bz_dslz
.sl:
    call bz_dslots              ; save v2 (130.19.6): each slot judged alone,
    cmp byte [bz_dat + 5], BZ_PHYSV ; physics or not (a game is no time)
    je .phys
    xor cl, cl
.phys:
    mov word [bz_dat], 'BZ'     ; `BZS5`, the count and BZ_PHYSV, two zero bytes
    mov word [bz_dat + 2], 'S5'
    mov word [bz_dat + 4], BZ_NCRS | (BZ_PHYSV << 8)
    mov word [bz_dat + 6], 0
    mov di, bz_dat + BZD_ENT    ; THE BESTS (130.22.5.1), in the file's order:
.e:                             ; an entry is kept under one of this build's
    mov ax, [di]                ; SAVE KEYS (never 0), with a best 1 - 65,534,
    or cl, cl                   ; and only the FIRST entry with that key; any
    jz .clr                     ; other is emptied
    mov si, bz_ckeys
    mov bx, BZ_NCRS
.k:
    cmp ax, [si]
    je .kk
    inc si
    inc si
    dec bx
    jnz .k
    jmp short .clr              ; (a foreign key, and 0)
.kk:
    mov dx, [di + 2]
    dec dx
    cmp dx, 0fffdh
    ja .clr
    push di
    mov di, bz_dat + BZD_ENT
    call bz_dbest               ; the first entry holding the key ...
    pop di
    cmp si, di                  ; ...is this one: kept
    je .keep
.clr:
    xor ax, ax
    mov [di], ax
    mov [di + 2], ax
    mov [di + 4], ax
.keep:
    add di, BZD_ENTB
    cmp di, bz_dat + BZD_SLOT
    jb .e
    ret

; bz_dbest - AX = a save key (never 0), DI = a best table's first entry ->
; SI the FIRST entry holding the key, else the first EMPTY one (key 0: one is
; always there in an image bz_dnorm made, its keys distinct and at most
; BZ_NCRS of BZD_NENT).  Preserves all else.
bz_dbest:
    push cx
    push di
    xor si, si
    mov cx, BZD_NENT
.l:
    cmp [di], ax
    je .hit
    or si, si
    jnz .n
    cmp word [di], 0
    jne .n
    mov si, di
.n:
    add di, BZD_ENTB
    loop .l
    jmp short .o
.hit:
    mov si, di
.o:
    pop di
    pop cx
    ret

; bz_dchk - BONANZA.DAT's header and entries in [bz_dat], checked IN FULL
; (SPEC.md 130.14.17 item 6, 130.22.5.1): `BZ` (+2 `S5`: bz_dload matched it
; with the length); the count it was written with 1 - BZD_NENT; +6 - +7 zero
; (+5, the physics, any value: bz_dnorm judges it, 130.16.9); every entry's
; falls at most 9,999; every EMPTY entry (key 0) all zero.  The keys are
; bz_dnorm's, the slots bz_dslots'.  -> CL = 1 it passes, 0 it is refused
; whole.  Clobbers AX, SI.
bz_dchk:
    xor cl, cl
    cmp word [bz_dat], 'BZ'     ; (+2 `S5`: bz_dload matched it with the
    jne .out                    ; length)
    mov al, [bz_dat + 4]
    dec al
    cmp al, BZD_NENT
    jae .out
    cmp word [bz_dat + 6], 0
    jne .out
    mov si, bz_dat + BZD_ENT
.e:
    cmp word [si + 4], BZ_FALLMAX
    ja .out
    cmp word [si], 0
    jne .n
    mov ax, [si + 2]
    or ax, [si + 4]
    jnz .out
.n:
    add si, BZD_ENTB
    cmp si, bz_dat + BZD_SLOT
    jb .e
    inc cx
.out:
    ret

; bz_dsave - on the desktop after a launch: when the play set a best, the
; BZD_FILE bytes to SYSTEM\APPDATA\BONANZA.DAT on the package's own volume (os88data.inc:
; the session's first save a full write, every later one a sector).  A save
; that fails - no folder, write-protected, full - toasts ONCE a session and
; the bests stay in memory (SPEC.md 130.14.3.3).  The save MERGES: the file is
; read again first (bz_dload, as hostile as at the entry) and the smaller best
; of the two kept per course, matched by SAVE KEY (130.22.5.1: each image's
; entries are in no order), so a second instance - a
; double-clicked .BZR opens one - never overwrites the first's bests with its
; older copy.  Preserves nothing.
bz_dsave:
    mov al, [bz_newb]           ; a best, or the game's slot (save v2,
    or al, [bz_gsave]           ; 130.19.6)
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
    mov bx, bz_dmine + BZD_ENT  ; per course: each of our entries (bz_dnorm
    mov cx, BZD_NENT            ; made both images: this build's keys, each
.m:                             ; once, a best 1 - 65,534) against the disk's
    mov ax, [bx]                ; entry for its key, or an empty one there (0 -
    or ax, ax                   ; 1 is the largest, so "none" never wins)
    jz .mn
    mov di, bz_dat + BZD_ENT
    call bz_dbest
    mov di, si
    mov si, bx
    mov ax, [si + 2]
    dec ax
    mov dx, [di + 2]
    dec dx
    cmp ax, dx
    jae .mn
    movsw                       ; the key, the best and its falls
    movsw
    movsw
.mn:
    add bx, BZD_ENTB
    loop .m
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
; 130.19.6).  CF = 1 refused, and [bz_dwf] = 1 until a write is not (the info
; card's NOT SAVED, 130.22.6).  Preserves ES.
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

; bz_dslots - each SLOT judged alone (BZS5, SPEC.md 130.22.5.1): EMPTIED when
; its lives are over BZ_LIVES, +1 has a bit but the mode's, +3 is not zero,
; a route TAKEN is not one OPENED, its exits found or its bests past the
; pathway's PADS (at or past BZ_PATH_NPAD) are not zero, +20 is not this
; build's pathway VERSION, or - it having lives - pad 0 is not open, its pad
; is not one of the pathway's (BZD_NPAD), or - TIMED - its pad is not open
; (EXPLORE rests on any pad: every one is open to it, none in the open set).
; An empty slot (lives 0) keeps its exits found.  Then each pad's exits found
; are masked to the exits of the course it plays (BZ_PAD_EXITS).  Preserves
; all but the flags.
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
    lea di, [si + BZD_SEXIT + 2 * BZ_PATH_NPAD] ; the exits found and the bests
    mov cx, BZ_NPADPAST         ; of pads that are not here are zero
    call bz_dzero
    jnz .bad
    lea di, [si + BZD_SBEST + 2 * BZ_PATH_NPAD]
    mov cx, BZ_NPADPAST
    call bz_dzero
    jnz .bad
    cmp word [si + BZD_SVER], BZ_PATH_VER ; this build's pathway VERSION (an
    jne .bad                    ; all-zero slot's emptying changes nothing)
    cmp byte [si], 0
    je .n
    test byte [si + BZD_SOPEN], 1 ; a game with lives has pad 0 open ...
    jz .bad
    mov al, [si + BZD_SPAD]     ; ...its pad one of the pathway's (the
    cmp al, BZD_NPAD            ; loop indexes the part's tables by it) ...
    jae .bad
    test byte [si + 1], 1       ; ...and, TIMED, an open one (EXPLORE plays
    jnz .n                      ; any pad, 130.19.8: none of them in the set)
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
    push si                     ; each pad's exits found masked to its
    mov di, bz_pexits           ; course's (130.22.5.1: the course on a pad
.x:                             ; can change under its progress)
    mov ax, [di]
    and [si + BZD_SEXIT], ax
    inc si
    inc si
    inc di
    inc di
    cmp di, bz_pexits + 2 * BZ_PATH_NPAD
    jb .x
    pop si
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
BZ_NPADPAST equ BZ_PAD_MAX - BZ_PATH_NPAD ; the words a slot's tables hold past the pads
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
%include "os88data.inc"         ; banked at the entry (130.14.7.6), not where a
                                ; dialog has moved the instance since

; -----------------------------------------------------------------------------
; RECORDED DEMOS ON THE DISK (SPEC.md 130.14.7): W saves the held log, L loads
; one through the Open dialog, a double-clicked .BZR opens with BONANZA, V
; copies a shipped demo part into the log, D benchmarks it - and HOME, where
; every part is read from (130.14.7.6).
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

%ifdef BZDEV
; S on the desktop: the sound's own key (bzsound.inc bzs_skey), whose title is
; fetched - so at home, as bz_launch's fetches are (SPEC.md 130.14.10's two
; sound fetches: bzs_gfetch inside bz_launch's home, bzs_dstart here and in
; the entry proc, which runs at home)
bz_skey:
    call bzs_toggle             ; (on or off since SPEC.md 130.26.5)
    jmp bz_line4

%endif
; CF = 1 on kern_small, its refusal toasted (SPEC.md 130.1, 130.14.3.4).
; Clobbers what bz_toast does.
bz_bigok:
    cmp byte [bz_small], 0
    je .out                     ; (CF = 0)
    mov si, bz_t_small
.t:
    call bz_toast
    stc
.out:
    ret
; bz_fsok - a bracket's refusals (bz_launch, bz_title8, bz_game8): kern_small,
; then an adapter with no mode of ours (EGA, MDA: CGA, HERC OR VGA ONLY), each
; toasted, CF = 1; else the card's bytes set (bz_setcard), CF = 0.
bz_fsok:
    call bz_bigok
    jc .out
    call bz_adapter
    or al, al
    mov si, bz_t_adapt
    jz bz_bigok.t
    call bz_setcard
    clc
.out:
    ret

%ifdef BZDEV
; D (one press): THE DEMO BENCHMARK, bz_mode 3 - the held log replayed and
; measured (SPEC.md 130.14.7.3)
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
; 130.14.7.1); bz_wdone writes it.  A dialog already up refuses, and that dialog is the answer.
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

; L (one press): a log through the OPEN dialog (SPEC.md 130.14.7.2)
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
    call bz_rout                ; ES:BX, CX = the held log, one piece
    mov si, bz_dname
    xor dx, dx
    call OSAPI_FILE_WRITE
    mov si, bz_t_saved
    jnc bz_toast
    jmp short bz_ftoast
%endif
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

; bz_rin - a whole log, CX bytes (16 - 4,096) at ES:SI, into the session's
; (SPEC.md 130.11.12.1): its header into bz_rlog, its runs into THE KIT's
; tail.  bz_rin.di: DX bytes into DI first (bz_tdemo: the start block and the
; header, bz_tblk and bz_rlog adjacent).  The kit is here (bz_rkit); a source
; selector is read from, never added to.  Preserves ES; clobbers AX, CX, DX,
; SI, DI.
bz_rin:
    mov di, bz_rlog
    mov dx, BZR_RUNS
.di:
    push ds
    push es
    mov ax, [bz_kseg]
    push ds
    push es
    pop ds                      ; DS = the source, ES = ours
    pop es
    cld
    sub cx, dx
    xchg cx, dx
    rep movsb                   ; the resident head
    mov cx, dx
    mov es, ax
    mov di, BZR_K + BZR_RUNS
    rep movsb                   ; the runs
    pop es
    pop ds
    ret

; bz_rout - the session's log as ONE piece for a write (130.11.12.1): its
; header copied to the kit's tail, ahead of its runs.  -> ES:BX = the log, CX
; = its bytes.  Clobbers AX, SI, DI.
bz_rout:
    mov es, [bz_kseg]
    mov si, bz_rlog
    mov di, BZR_K
    mov bx, di
    mov cx, BZR_RUNS / 2
    cld
    rep movsw
    mov di, bx
    jmp short bz_esz

; bz_rkit - CF = 1 when a log has no home (130.11.12.1): THE KIT is not here
; and bz_kget is refused (aloud on the desktop; inside the bracket quiet,
; OP_SAYGATE).  Preserves every register but the flags.
bz_rkit:
    cmp word [bz_kseg], 1
    jae .out                    ; (CF = 0)
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    call bz_kget
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
; bz_lfile - a demo FILE, which is HOSTILE (SPEC.md 19, 130.14.7.2): [bz_dname]
; in the instance's folder, CX its size (L: the dialog's, 16 - 4,096, AL = 0)
; or the read's capacity (the double-click: 4,096, AL = 1, 130.14.7.5), read
; into a TRANSIENT claim of exactly CX bytes (pinned, held for this call
; alone) and CHECKED IN FULL (bz_lchk) before a byte reaches bz_rlog, so a
; refused file leaves the session's log as it was and fetches no part.  The
; claim is an LDT selector on kern_mega: read into at ES:0, checked through
; [es:], copied whole - never added to (130.14.13).  CF = 0: the log is the
; file's, [bz_lsv] 2 and [bz_lfn] its name; CF = 1: refused and toasted.
; Preserves nothing.
; -----------------------------------------------------------------------------
bz_lfile:
    call bz_rkit                ; (no kit, no home for its runs: refused, and
    jc bz_rkit.out              ; op_fetch said why)
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
    mov cx, [bz_lfsz]            ; PASSED: the bytes into the log, from the
    xor si, si                  ; claim's own selector at 0
    call bz_rin
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

; bz_lchk - 130.14.7.2's checks 2 - 8 on the log at ES:0, [bz_lfsz] bytes (16 -
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

; a DOUBLE-CLICKED .BZR (SPEC.md 130.14.7.5): no size comes with it, so the
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
    jmp bz_rret

%ifdef BZDEV
; V (one press): the next SHIPPED demo, the rows in turn, into the
; held log (SPEC.md 130.14.7.4) - its part fetched at home, copied whole (a
; PART is trusted: the tool checked it, 130.10.6.2) and dropped.  It replaces
; the session's last log, as a new play does.
bz_vkey:
    call bz_bigok
    jc .out
    call bz_rkit                ; (the log's home, 130.11.12.1)
    jc .out
    call bz_home
    jc .out
    mov al, [bz_vk]
    add al, BZ_P_DEMO
    call bz_tlog                ; fetched, copied whole and dropped with ES =
    jc .back                    ; ours (bz_tcopy: kern_mega's lesson in V)
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

%endif
; a new held log (L, V): the lines that name it and offer its keys - the demo
; keys, the log's line, and line 0's refused-replay reason, now stale
bz_dheld:
    mov byte [bz_err], 0
%ifdef BZDEV
    mov si, bz_heldl
    jmp bz_redraw
bz_heldl:   db 5, 6, BZ_LHEAD, 0ffh
%else
    ret                         ; (the player's face has no line to redraw)
%endif

%ifdef BZDEV
; T (one press): the control, KEYS or MOUSE (SPEC.md 130.14.8)
bz_tkey:
    xor byte [bz_ctl], 1
    mov si, bz_tlines
    jmp bz_redraw
bz_tlines:  db 3, 6, 0ffh

; bz_onkey's one-press instrument keys under bz_dev (SPEC.md 130.26.6): the
; key (lower case), its handler; 0 ends it
bz_devk:    db 'd'
            dw bz_dkey_d        ; the demo benchmark (130.14.7.3)
            db 'l'
            dw bz_lkey          ; load a demo (130.14.7.2)
            db 'v'
            dw bz_vkey          ; the next shipped demo (130.14.7.4)
            db 'w'
            dw bz_wkey          ; save the held log (130.14.7.1)
            db 't'
            dw bz_tkey          ; the control, KEYS or MOUSE (130.14.8)
            db 's'
            dw bz_skey          ; the sound (130.20.4), at home
            db 0
%endif

TOASTSTR bz_t_out, "Bonanza's disk is out"
%ifdef BZDEV
TOASTSTR bz_t_saved, 'Demo saved'
%endif
TOASTSTR bz_t_notbzr, 'Not a Bonanza demo'
TOASTSTR bz_t_dmg, 'Damaged demo file'
TOASTSTR bz_t_phys, 'Demo from other physics'
TOASTSTR bz_t_nomem, 'Bonanza: no memory'

; --- the window -----------------------------------------------------------------
bz_tpl: dw 40, 24, 344, 168, bz_title, bz_cls
; its CLASS (SPEC.md 11.104): every handler; WF_OWNBG, the face paints every pixel
    OS88_CLASS bz_cls, WF_OWNBG, PAINT, bz_paint, ONKEY, bz_onkey, \
               ONCLICK, os88ui_btnclick, ONMOUSEUP, bz_onup, ONDRAG, bz_ondrag, \
               ABOUT, bz_about, ONTIMER, bz_ontimer, ONWAKE, bz_onwake
bz_title: db 'Bounce Bonanza',0
bz_credits: dw bz_title, bz_ck1, bz_ck2, bz_ck3, bz_ck4, bz_ck5, bz_ck6, bz_ck7, bz_ck8, bz_credit1, 0
bz_credit1: db 'Contributed by Elendilon',0
bz_ck1:     db 'Arrows roll, Space hop',0       ; the player's keys no menu carries
bz_ck2:     db 'L.Shift grip, P pause',0        ; (SPEC.md 130.26.7)
bz_ck3:     db 'Bksp back to the flag',0
bz_ck4:     db 'Pad: Enter play, Space info',0
bz_ck5:     db 'Pad: V demo, F6 replay',0
bz_ck6:     db 'F5 save replay',0
bz_ck7:     db 'F or Alt+Enter: window',0
bz_ck8:     db 'Esc: map, or quit',0

bz_cnames:  BZ_CRS_NAMES        ; ...their NAMEs, BZ_CRS_NAMEB bytes each
bz_cballs:  BZ_CRS_BALLS        ; ...their balls, a byte each
bz_clims:   BZ_CRS_LIMS         ; ...their time limits, whole seconds of BZ_SECSTEPS
                                ; steps, a word each (0 none; wave 7, 130.18.3)
bz_cids:    BZ_CRS_IDS          ; ...their identities, a word each
bz_ckeys:   BZ_CRS_KEYS         ; ...their SAVE KEYS, a word each (130.22.5.1)
; (their songs: each course part's own section S since SPEC.md 130.50.3 - no table)
bz_carena:  BZ_CRS_ARENA        ; ...their arena reserves, paragraphs, a word each
%if BZ_NCRS2
bz_cwrow:   BZ_CRS_WROW         ; SPEC.md 130.30.4.4: each course's WORLD part's row (0: one part)
%endif
%if BZ_NSHC
bz_cshn:    BZ_CRS_SHN          ; SPEC.md 130.30.12.5: each course's SHEETS (0: one picture part),
bz_cshi:    BZ_CRS_SHI          ; its first entry's offset in bz_shtab,
bz_shtab:   BZ_SHTAB            ; and an entry a sheet: its paragraphs in the part (entry 0: the
                                ; world part's), m0, hic, tlo, thi
%endif
                                ; (the tool's, SPEC.md 130.25.4.2: bz_cload)
bz_cpals:   BZ_CRS_PALS         ; ...their CGA colour selects, a byte each (3D9h,
                                ; wave 6, SPEC.md 130.16.6: bz_vinit)
bz_clocks:  BZ_CRS_LOCKS        ; ...their horizontal LOCKs, the CGA's c0 then the
                                ; Hercules', FFh FFh none (SPEC.md 130.45: bz_vinit)
bz_cbots:   BZ_CRS_BOTS         ; ...their BOTTOM LINEs, a word each, 0 none
                                ; (SPEC.md 130.45.4: bz_vinit's bottom stop)
bz_s_dat:   db 'BONANZA.DAT', 0
%include "bzvideo.inc"
%include "bzcard.inc"           ; wave 8c (130.19.8): the cards
%include "bzgame.inc"
%include "bzwheel.inc"
%include "bzphys.inc"
%include "bzfam.inc"            ; wave 9 (SPEC.md 130.25.6): the families' dispatch
%include "bzsound.inc"
%include "bzmenu.inc"           ; SPEC.md 130.26: the window's button, menus and replays
%include "bzballgen.inc"        ; the balls generated at fetch (wave 9, 130.25.5)
%if BZ_KIT_BMB > 4 * BZ_BOXB
 %error "bz_cxkit copies a kit class's bitmap to bz_boxbuf (SPEC.md 130.37.4)"
%endif
%if 4 * BZ_BOXB < 512
 %error "bz_hgen: BZ_HTAB's 512 bytes do not fit bz_boxbuf"
%endif
%if BZ_LMAX + 2 > 4 * BZ_BOXB
 %error "bz_lbuf shares bz_boxbuf: the face's longest line does not fit it"
%endif
%if BZD_FILE > 8 * BZC_NGLYPH
 %error "bz_dmine shares bz_font: BONANZA.DAT's image does not fit it"
%endif

; --- the part table (SPEC.md 130.11.3.1, 20.12) --------------------------------
; BZ_NCRS + BZ_NCRS2 + BZ_NDEMO + ... rows (no sound rows since SPEC.md 130.50), in the Makefile's BZ_PARTS
; order, every one OP_LAZY | OP_COMP - and a play's SMALL ones, the balls, the
; sound part, the songs (the fanfare is one) and the families' code parts
; (wave 9, SPEC.md 130.25.6.2), OP_ARENA: ONE claim between
; them (SPEC.md 130.25.4), so a play holds three claims with the pathway held
; and two without.  The three balls, then each course
; (BZ_COURSES's order, bzcourse.inc's rows, every one the CGA's), the sound
; and its songs, and a shipped demo a course (every one but BENCH).  Fetched by bz_launch on the desktop (op_fetch,
; 1942's pattern) and dropped when the bracket returns.
OS88_PARTS_BEGIN BZ_NCRS + BZ_NCRS2 + BZ_NDEMO + 3 + 2 * BZ_TITLE + BZ_NFROW + 1
    BZ_CRS_PARTS                            ; K: BZ<K>.BIN (the balls: the bundle's, 130.25.5.2), then the WORLD parts
    BZ_DEMO_PARTS                           ; BZ_P_DEMO + K - 1: BZD<K>.BIN (130.14.7.4)
    OS88_PART OP_SEG, OP_LAZY | OP_COMP     ; BZ_P_SHELL: BZSHELL.BIN, far-called (130.19.2)
    OS88_PART OP_ASSET, OP_LAZY | OP_COMP   ; BZ_P_PATH: BZPATH.BIN, the pathway (130.19.5)
%if BZ_TITLE
    OS88_PART OP_ASSET, OP_LAZY | OP_COMP   ; BZ_P_TITLE: BZTITLE.BIN, the title (130.23)
    OS88_PART OP_ASSET, OP_LAZY | OP_COMP   ; BZ_P_TDEMO: BZTDEMO.BIN, its demos (130.23.3)
%endif
    OS88_PART OP_ASSET, OP_LAZY | OP_COMP   ; BZ_P_KIT: BZKIT.BIN, the standard kit, HELD (130.37.5)
    BZ_FAM_PARTS                            ; BZ_P_FAM on: the fetch families', then the BUNDLE (130.25.6.9)
    OS88_PART OP_SEG, OP_LAZY | OP_COMP     ; BZ_P_VGA: BZVGA.BIN, the VGA's writers, far-called (130.46.6)
OS88_PARTS_END
%if BZ_P_DEMO != BZ_P_CRS + BZ_NCRS + BZ_NCRS2 || BZ_NDEMO > BZ_NCRS || BZ_P_CRS != 0
 %error "the demo rows follow the courses', at most one a course (SPEC.md 130.14.7.4)"
%endif

%define OS88UI_ABOUT
%define OS88UI_NOGLYPH          ; (the Play Game button alone: no box, no dot)
%define OS88UI_ABFIT            ; (the keys' card on a CGA content box, SPEC.md 130.26.7)
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
VAR bz_page,1                   ; the face's page: 0 MAIN, 1 RESULTS (130.14.3.2)
VAR bz_pgo,1                    ; 1: this key left RESULTS (or a refused replay):
                                ; bz_onkey repaints MAIN whole after it
VAR bz_pc,1                     ; the course's part row (BZ_P_CRS + K)
VAR bz_bform,1                  ; the HELD balls' form: 0 the CGA's, 1 Hercules-
                                ; translated (bz_hxlat, bz_bget; 130.25.5.2)
VAR bz_mat,1                    ; THIS launch's material, 0 rubber, 1 steel,
                                ; 2 glass (bz_launch; bz_pinit copies its
                                ; BZ_MATTAB record, SPEC.md 130.11.5.2)
VAR bz_dkk,1                    ; the held-key guard: the make code of the C, M
                                ; or N not yet seen up, 0 none (130.11.11.2)
VAR bz_fw,2                     ; the face: content width, height, origin
VAR bz_fh,2
VAR bz_ox,2
VAR bz_oy,2
VAR bz_fcells,2
VAR bz_fy,2
bz_lbuf     equ bz_boxbuf       ; the face's line (bzface.inc, bzwface.inc: built and
                                ; drawn at once, on the desktop) SHARES the box
                                ; buffers, which are the bracket's and a fetch's
                                ; scratch only (SPEC.md 130.19.8.1)
VAR bz_shfp,4                   ; the shell part's far pointer (bz_shcall)
VAR bz_dlo,2                    ; D3 (SPEC.md 130.24.5.2): the part's section D,
VAR bz_dhi,2                    ; [bz_dlo, bz_dhi) (0, 0 none), and C, the cells
VAR bz_clo,2                    ; (bz_cexp's, from the directory: every split
VAR bz_chi,2                    ; cell's offset is bounded inside D, bz_drec)
VAR bz_ffo,2                    ; SPEC.md 130.28.2: section F, [bz_ffo, bz_ffe) (0, 0
VAR bz_ffe,2                    ; none: bz_dfind's), and each table's offset in the
VAR bz_fsb,2 * BZ_FSHAPE_MAX    ; part (bz_dval's; bzphys.inc's bz_fhp reads them)
VAR bz_shpend,2                 ; byte 1: a paint put off while a course was held (a word: the run stays even)
; the game (wave 8b, SPEC.md 130.19.5): the pathway's state, held in memory
VAR bz_nopen,4                  ; a bit a pad: OPEN (pad 0 from a new game's start; a dword)
VAR bz_ndone,4                  ; ...and DONE (a finish in time)
VAR bz_nrop,4                   ; ...the routes OPENED (a bit a route)
VAR bz_nrtk,4                   ; ...and TAKEN (a secret's reveal; a subset)
VAR bz_ppad,1                   ; the pad the marble rests on (the slot's +2)
VAR bz_phold,1                  ; 1: the pathway's part is HELD (bz_cload, bz_phrel)
VAR bz_kseg,2                   ; THE KIT's segment (bz_kget's, op_seg's; bz_cxkit reads it, SPEC.md 130.37.4)
VAR bz_phre,1                   ; ...1 while the pathway is re-entered from the hold
%ifdef BZDEV
VAR bz_phforce,1                ; HARNESS: nonzero never holds it (130.22.7); never set by the package
%endif
VAR bz_lives,1                  ; lives left (5 at a new game; 0 the game is over)
VAR bz_pwck,1                   ; wave 8R (130.22.4.4): the course Enter at a pad plays
VAR bz_nst,(BZ_NSIGN + 1) & ~1  ; each SIGN's pose (bz_ltrue's SIGN case, bz_nset; 130.22.4.1), even
VAR bz_ingame,1                 ; 1: inside the game's bracket (bz_fullscreen's rounds)
VAR bz_slot,1                   ; the save's slot played, 0 - 2 (8c chooses; 0 until then)
VAR bz_gsave,1                  ; 1: the game's slot to be written (bz_dsave)
VAR bz_retry,1                  ; wave 8c (130.19.8): 1 R on the game's pause card
VAR bz_xmode,1                  ; ...1 EXPLORE (the slot's mode, while the game plays; 0 else)
%if BZ_TITLE
VAR bz_tmode,1                  ; SPEC.md 130.23.4: 1 a TITLE DEMO plays, 2 a course demo of the title's chain
VAR bz_twhy,1                   ; ...why its play left: 'p' play, 27 Esc, F or Alt+Enter (leave), 1 another key in a course demo
VAR bz_tlast,1                  ; ...the title demo last shown (0FFh none)
VAR bz_tsel,1                   ; ...the one fetched
VAR bz_tgame,1                  ; ...1: a game was played (its slot written at the bracket's end)
VAR bz_tlfsr,2                  ; ...the title's LFSR (bz_trand)
VAR bz_tnew,2                   ; ...1: no BONANZA.DAT at the launch - the first title demo
                                ; is a RUBBER one (130.23.3.1); a word: the title's bytes stay odd
%else
VAR bz_tpad,1                   ; (the VARs stay even: the title's seven bytes
%endif                          ; are odd, and bz_dev evens them)
; THE WINDOW (SPEC.md 130.26): the button, the face's layout, the menus, the
; replays and the suspended bracket
%ifdef BZDEV
VAR bz_dev,1                    ; HARNESS: 1 the instruments' keys and face (130.26.6); never set by the package
%else
VAR bz_dpad,1                   ; (in bz_dev's place: the title's seven bytes are odd)
%endif
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
VAR bz_wkb,2                    ; the face's keys (bzw_keys): their foot, a line's
VAR bz_wrr,2                    ; right fill's last column (bzw_lbline)
VAR bz_wsrc,2
VAR bz_wsw,2
VAR bz_wsb,2
VAR bz_wsc,2
VAR bz_wsr,2
VAR bz_wsn,2
VAR bz_earm,1                   ; the Erase armed, slot 1 - 3 (0 none)
VAR bz_susp,1                   ; BZ_SU_*: the bracket left for the window from (130.26.4)
VAR bz_towin,1                  ; 1: F or Alt+Enter asked for the window (bz_exitchk)
VAR bz_rsm,1                    ; 1: the next bz_play RESUMES a course (no bz_pinit, no new log)
VAR bz_rown,1                   ; 1: the held log is a play the player recorded (Save Replay's)
VAR bz_wpad,1                   ; (the VARs stay even)
VAR bz_rbest,2                  ; bz_rscan: the greatest number, its file's size,
VAR bz_rbsz,4                   ; and the course's name's tail, `NAMES.BZR`
VAR bz_rtail,10
; the pathway's play (wave 8R, SPEC.md 130.22.4: bonanza.asm's THE PATHWAY)
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
; the game (SPEC.md 130.14.3): the held log's line, the bests
VAR bz_homedir,2                ; where BONANZA.O88 was launched from: its
                                ; folder (130.14.7.6) ...
VAR bz_lsn,2                    ; line 6: the last play's or replay's steps
VAR bz_lsf,2                    ; ...its falls (to 9,999)
bz_dmine    equ bz_font         ; bz_dsave's: ours, while the disk's is merged in -
                                ; on the desktop, where bz_font is free (bz_fload
                                ; loads it afresh at every bracket: 130.19.8.1)
VAR bz_dat,BZD_FILE             ; BONANZA.DAT's image, always this build's whole
                                ; file (bz_dnorm): what the face shows and the
                                ; save writes
VAR bz_homevol,1                ; ...and its volume (os88data.inc's OD_TVOL)
%ifdef BZDEV
VAR bz_crsel,1                  ; the course F plays: FIRST, or one a row pokes
%endif                          ; (in bz_tour's place: the VARs after bz_nst stay even)
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
; the demos on the disk and the mouse (SPEC.md 130.14.7, 130.14.8)
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
%ifdef BZDEV
VAR bz_vk,1                     ; V: the next shipped demo, 0 - BZ_NDEMO - 1
%endif
VAR bz_ctl,1                    ; T: the control, 0 KEYS, 1 MOUSE (the session's)
%ifdef BZDEV
VAR bz_dtr,1                    ; D stopped measuring at 65,535 frames (130.14.7.3)
%endif
VAR bz_rw,1                     ; the held log's run width: 2, or 3 with TILT
VAR bz_tilt,1                   ; the frame's TILT BYTE, capx << 4 | capy: 88h a
                                ; keyboard play's (bz_input, SPEC.md 130.14.8.2)
VAR bz_tby,1                    ; the STEP's tilt byte (bz_step: the play's
                                ; frame's, the replay's run's, 88h the autopilot's)
VAR bz_tanc,1                   ; 1: anchor the stick at the next frame
VAR bz_tarm,1                   ; 1: the stick has been in its dead zone
%ifdef BZDEV
VAR bz_apilot,1                 ; a HARNESS byte, never set by the package: a
                                ; play takes its key bytes from the autopilot
                                ; (bzphys.inc bz_step; bonanzagame, 130.14.14)
%endif
VAR bz_tax,BZT_SIZE             ; the stick's x axis (bzgame.inc bz_tmouse) ...
VAR bz_tay,BZT_SIZE             ; ...and its y axis
%if (BZ_BSS & 1)
 %error "the game's VARs stay even"
%endif
; the engine's (bzgame.inc's head documents the ones a harness reads)
BZ_GAME_VARS
BZ_PHYS_VARS
BZ_FAM_VARS
BZ_SND_VARS
VAR bz_osum,2 * BZ_OSROWS        ; the occluder rows' summary (bz_osmake): a row's greatest s', t'
%if BZ_TITLE
VAR bz_tblk,BZ_TSTART           ; SPEC.md 130.23.3: a title demo's START BLOCK (bz_tapply), bz_rlog right
%endif                          ; after it (bz_tdemo copies the two as one)
VAR bz_rlog,BZR_RUNS            ; THE REPLAY LOG's HEADER (SPEC.md 130.11.12.1):
                                ; `BZR1`, the course (+4), the material (+5),
                                ; flags, the steps, the runs' count; the runs
                                ; are in THE KIT's tail (BZR_K).  The recorder
                                ; writes it; R replays it (bz_rhave)
OS88_BSS BZ_BSS
OS88_IMAGE_END
