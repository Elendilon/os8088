; =============================================================================
; os8088 - apps/realboy/realboy.asm
;
; REALBOY: a Game Boy in a window (docs/REALBOY-SPEC.md section 14). The
; core is parts 0 and 1 of this file - 64KB of generated SM83 handlers,
; apps/realboy/rbgen.py's, in two halves one segment apart - and the view the
; Game Boy's memory lives in is part 2, a zeroed 64KB carve; the cartridge is
; a claim of its own size.
; rbsys.inc runs the machine, rbppu.inc composes its frame, and this file is
; the window round them: open a .GB, run it to the wall clock in a worker,
; and put each frame it has time for on the glass.
;
; THE WORKER owns the machine. It counts BIOS ticks into Game Boy frames
; owed (59.7275 Hz against 18.2065: 840/256 of a frame a tick), runs the core
; in budgets of RW_BUDGET M-cycles - the core runs with interrupts off
; (REALBOY-SPEC section 5.2), so the budget is the IRQ latency, and the tick
; pre-empts it between two - and yields once a frame. It composes and blits a
; frame only when it has caught up, or every RW_DRAWTICKS ticks whatever
; happens, so the game keeps its speed and the picture takes what is left
; (docs/plans/REALBOY-PLAN.md section 4.5).
; =============================================================================

%include "os88api.inc"

    OS88_HEADER 'REALBOY', rw_entry, OS88_F_ICON | OS88_F_ASSOC | OS88_F_PARTS, OS88_STACK_384

; --- embedded 16x16 icon: a Game Boy, the screen and the cross --------------
    OS88_ICON16
    dw 0x0000, 0x3FF8, 0x3FF8, 0x3FF8, 0x3FF8, 0x3FF8, 0x3FF8, 0x3FF8
    dw 0x3FF8, 0x3FF8, 0x3FF8, 0x3FF8, 0x3FF8, 0x3FF8, 0x3FF8, 0x0000
    dw 0x0000, 0x3FF8, 0x2008, 0x2FE8, 0x2FE8, 0x2FE8, 0x2FE8, 0x2008
    dw 0x2008, 0x2468, 0x2E08, 0x2468, 0x2008, 0x2008, 0x3FF8, 0x0000
    OS88_ICON16_END

; --- the extension this program opens ---------------------------------------
    OS88_ASSOC16
    db 1
    OS88_ASSOC_EXT 'GB'
    OS88_ASSOC16_END

%include "os88parts.inc"

RW_CONT_W       equ 160
RW_CONT_H       equ 144
RW_BUDGET       equ 2000            ; M-cycles a core run: ~5.6 ms on a 286
RW_BUDGET86     equ 700             ; ...and on an 8088, where 2000 is ~20 ms
                                    ;   with interrupts off - two bytes of a
                                    ;   1200-baud serial mouse into an 8250
                                    ;   that holds one
RW_DRAWTICKS    equ 3               ; a frame drawn at least every 3 ticks
RW_PERTICK      equ 840             ; frames a BIOS tick, x 256
RW_BEHIND       equ 30              ; frames a machine catches up at most:
                                    ;   half a second, longer than an 8088's
                                    ;   draw, which the frames during it
                                    ;   must outlast or the game slows
RW_OWEDMAX      equ RW_BEHIND * 256
RW_ROMMAX_KB    equ 256

; --- the bss: the standard's words first, then ours --------------------------
rw_win          equ os88_image_end + OP_BSS
rw_state        equ rw_win + 2      ; 0 no game, 1 running, 2 stopped
rw_pause        equ rw_state + 1
rw_resetq       equ rw_pause + 1    ; Reset asked; the worker does it
rw_abon         equ rw_resetq + 1   ; the About card is up
rw_shown        equ rw_abon + 1     ; rw_fbuf holds a frame
rw_argpend      equ rw_shown + 1
rw_argvol       equ rw_argpend + 1
rw_last         equ rw_argvol + 1   ; word: the tick last counted
rw_owed         equ rw_last + 2     ; word: frames owed, x 256
rw_romseg       equ rw_owed + 2
rw_romkb        equ rw_romseg + 2
rw_banks        equ rw_romkb + 2
rw_argdir       equ rw_banks + 2
rw_spawned      equ rw_argdir + 2
rw_name         equ rw_spawned + 2  ; 16: the game's file name
rw_ovl          equ rw_name + 16    ; the F1 overlay is up
rw_f1was        equ rw_ovl + 1      ; F1 was held at the last look
rw_nrun         equ rw_f1was + 1    ; word: frames run since the last count
rw_ndrawn       equ rw_nrun + 2     ; word: ...and drawn
rw_tstat        equ rw_ndrawn + 2   ; word: the tick that count began
rw_ovltxt       equ rw_tstat + 2    ; 16: 'NNN% NNfps', composed once a second
rw_budget       equ rw_ovltxt + 16  ; word: M-cycles a core run, by CPU tier
rw_drawt        equ rw_budget + 2   ; word: the tick the last frame was drawn
rw_pfmt         equ rw_drawt + 2    ; rw_pbuf holds: 0 nothing, 1 the dither,
                                    ;   4 BLITP's planes (rb_render4)
rw_nobp         equ rw_pfmt + 1     ; BLITP refused us: dither until a paint
rw_incore       equ rw_nobp + 1     ; the worker is in the machine (rwfsx.inc)
rw_fsq          equ rw_incore + 1   ; full screen asked: the worker keeps out
rw_infsx        equ rw_fsq + 1      ; the machine runs in the bracket
rw_fsrate       equ rw_infsx + 1    ; ...paced by FSXF_RATE, not the tick
rw_fsrun        equ rw_fsrate + 1   ; frames run undrawn
rw_ovlnew       equ rw_fsrun + 1    ; rw_ovltxt changed since it was drawn
rw_fowed        equ rw_ovlnew + 1   ; word: rate periods counted by the hook
rw_fsleft       equ rw_fowed + 2    ; word: frames still to run this turn
rw_fsi          equ rw_fsleft + 2   ; FSI_SIZE: the mode's info block
rw_font         equ rw_fsi + FSI_SIZE ; 768: glyphs 32-127, copied at entry
rw_jitseg       equ rw_font + 768   ; word: the recompiler's 64KB, or 0
rw_jitwant      equ rw_jitseg + 2   ; translate when there is a cache for it
rw_jitq         equ rw_jitwant + 1  ; Machine > Recompiler asked; the worker
rw_tone         equ rw_jitq + 1     ; word: the hertz the speaker plays (0 off)
rw_sch          equ rw_tone + 2     ; byte: the square channel on the speaker
rw_ramseg       equ rw_sch + 1      ; word: cartridge RAM's banks, or 0
rw_rambanks     equ rw_ramseg + 2   ; byte: 8KB banks there (0 = none)
rw_batt         equ rw_rambanks + 1 ; byte: a battery: save it on close
rw_rtc          equ rw_batt + 1     ; byte: an MBC3 clock
rw_odst         equ rw_rtc + 1      ; byte: os88data.inc's state for the file
rw_savelen      equ rw_odst + 1     ; word: the .SAV's RAM bytes
rw_rtcgap       equ rw_savelen + 2  ; dword: seconds the save was put away
rw_rtcsave      equ rw_rtcgap + 4   ; 16: the clock, across a reset
rw_savename     equ rw_rtcsave + 16 ; 13: NAME.SAV
rw_fskind       equ rw_savename + 13 ; byte: full screen's writer (RW_FS*)
rw_htab         equ rw_fskind + 1   ; 512: a full-screen writer's table
rw_chg          equ rw_htab + 512   ; 144: the lines rb_renderd changed
rw_fsper        equ rw_chg + 144    ; word: rate periods in the bracket (rw_clk)
rw_logon        equ rw_fsper + 2    ; byte: Machine > Log is on (rwlog.inc)
rw_logst        equ rw_logon + 1    ; byte: os88data.inc's state for the log
rw_logn         equ rw_logst + 1    ; word: records taken
rw_ltick        equ rw_logn + 2     ; word: ticks since the log began
rw_acomp        equ rw_ltick + 2    ; word: lines composed this second
rw_achg         equ rw_acomp + 2    ; word: ...and changed
rw_ams          equ rw_achg + 2     ; word: ms drawing this second
rw_amax         equ rw_ams + 2      ; byte: the longest draw, ms
rw_aowed        equ rw_amax + 1     ; byte: the most frames owed
rw_log          equ rw_aowed + 1    ; RW_LOGN x RW_LOGSZ: the records
rw_fbuf         equ rw_log + RW_LOGN * RW_LOGSZ ; 5,760: rb_render's frame (monochrome)
rw_pbuf         equ rw_fbuf + 5760  ; 11,520: the frame as the screen takes it
RW_BSS          equ rw_pbuf + 11520 - rw_win   ; derived: a sum by hand drifted

; =============================================================================
; rw_entry - the loader calls this once; the window appears afterwards
; =============================================================================
rw_entry:
    push es                         ; op_load spends ES, and OSAPI_ARG_FILE
    call op_load                    ;   reads through the kernel's
    pop es
    jc .refused                     ; no room for the core and view: it said
    mov al, KSC_UP                  ; arm the key map (the first call only
    call OSAPI_KEY_DOWN             ;   arms it)
    OS88_ALTENTER_ARM               ; and Alt, for Alt+Enter
    call OSAPI_ARG_FILE             ; CF = 1: launched empty
    jc .nodoc
    mov di, rw_name
    mov cx, 13
.cpn:
    mov al, [es:si]
    mov [di], al
    inc si
    inc di
    or al, al
    jz .cpd
    loop .cpn
.cpd:
    mov byte [rw_name+13], 0
    mov [rw_argdir], dx
    mov [rw_argvol], bl
    mov byte [rw_argpend], 1
.nodoc:
    mov si, rw_tpl
    call OSAPI_WM_CREATE            ; BX = the window
    jc .refused
    mov [rw_win], bx
    mov ax, rw_onclose              ; the save RAM on the way out
    call OSAPI_WM_ONCLOSE
    mov al, 1
    call OSAPI_WM_SNAP              ; content on the byte grid, for BLITP
    call OSAPI_WM_OWNBG             ; we paint every pixel of it
    OS88_REGION_MOVABLE rw_reloc
    mov si, rw_menus
    call OSAPI_MENU_SET
    mov si, rw_about
    call OSAPI_ABOUT_SET
    mov ax, rw_onwake
    call OSAPI_WM_ONWAKE
    cmp byte [rw_argpend], 0
    je .ok
    call OSAPI_WM_WAKE              ; the document, once the window is up
.ok:
    clc
    ret
.refused:
    stc
    ret

; rw_reloc - OUR REGION MOVED (SPEC.md 66.6.1): BX = where it was, DX = where
; it is. rbsys's own words moved with it; the state block in the view, which
; did not, names our code segment in five vectors. The worker is parked at
; OSAPI_TASK_ALIVE whenever this runs, never in the core.
rw_reloc:
    push ax
    push ds
    mov ax, [cs:rb_viewseg]
    or ax, ax
    jz .r
    mov ds, ax
    cmp [S_EVVEC+2], bx
    jne .1
    mov [S_EVVEC+2], dx
.1:
    cmp [S_IORVEC+2], bx
    jne .2
    mov [S_IORVEC+2], dx
.2:
    cmp [S_IOWVEC+2], bx
    jne .3
    mov [S_IOWVEC+2], dx
.3:
    cmp [S_MBCVEC+2], bx
    jne .4
    mov [S_MBCVEC+2], dx
.4:
    cmp [S_TRACEVEC+2], bx
    jne .5
    mov [S_TRACEVEC+2], dx
.5:
    cmp [S_JITVEC+2], bx            ; the recompiler's entry, rb_jit
    jne .r
    mov [S_JITVEC+2], dx
.r:
    pop ds
    pop ax
    ret

; rbsys asks its host for these: the link port's bytes go nowhere, and this
; core is not a trace build
rb_putc:
rb_trbyte:
    ret

; =============================================================================
; Loading a game
; =============================================================================

; rw_onwake - on the UI task, no lock held: a document we were launched with,
; or the core having stopped
rw_onwake:
    cmp byte [rw_argpend], 0
    je .stopped
    mov byte [rw_argpend], 0
    call OSAPI_GFX_LOCK
    mov dx, [rw_argdir]
    mov bl, [rw_argvol]
    call OSAPI_FILE_GOTO_QM
    jc .unlock
    mov si, [rw_win]
    call rw_load
.unlock:
    call OSAPI_GFX_UNLOCK
    ret
.stopped:
    cmp byte [rw_state], 2
    jne .r
    call OSAPI_GFX_LOCK
    mov si, [rw_win]
    call rw_repaint
    call OSAPI_GFX_UNLOCK
.r:
    ret

; rw_open - File > Open: the Standard File dialog, then rw_opened
rw_open:
    cmp byte [rw_state], 0
    jne .one
    mov al, FDLG_OPEN
    mov bx, si
    mov di, rw_opened
    xor si, si
    call OSAPI_FILE_DLG
    ret
.one:
    mov si, rw_s_one                ; one game a window: another opens in
    jmp rw_toast                    ;   another window

; rw_opened - the dialog's completion: DI = the name, DX:CX = its size
rw_opened:
    push si
    mov si, di                      ; copy the kernel's name now
    mov di, rw_name
    mov bx, 13
.c:
    mov al, [es:si]
    mov [di], al
    inc si
    inc di
    or al, al
    jz .cd
    dec bx
    jnz .c
.cd:
    mov byte [rw_name+13], 0
    pop si
    ; (the size the dialog read out of the listing is not used: rw_load asks
    ; the file itself, which knows its size unpacked)
; rw_load - rw_name in the current folder, SI = our window, the gfx lock
; held. THE SIZE PROBE first - a read with no room answers FERR_BIG with the
; KB the read needs, from the directory and unpacked, with some slack for a
; compressed file's expansion - then a claim that size, the read, and the
; check on the bytes that actually came in: whole 16KB banks, 32 to 256KB.
rw_load:
    push si
    push ds
    pop es
    xor bx, bx
    xor cx, cx
    xor dx, dx
    mov si, rw_name
    call OSAPI_FILE_READ
    jnc .notrom                     ; an empty file
    cmp ax, FERR_BIG
    jne .rdfail0
    cmp dx, 32
    jb .notrom
    cmp dx, RW_ROMMAX_KB + 2        ; (the slack)
    ja .big
    mov [rw_romkb], dx
    call OSAPI_MEM_AVAIL            ; AX = the largest run, in KB
    cmp ax, [rw_romkb]
    jb .room
    mov ax, [rw_romkb]
    call OSAPI_MEM_CLAIM            ; DX = its segment
    jc .room
    mov [rw_romseg], dx
    mov es, dx
    xor bx, bx
    mov ax, [rw_romkb]
    mov cx, 1024
    mul cx
    mov cx, ax                      ; DX:CX = the claim's capacity
    mov si, rw_name
    call OSAPI_FILE_READ            ; DX:AX = the bytes read
    jc .rdfail
    ; the ROM itself: whole 16KB banks, 2 to 16 of them
    test ax, 3FFFh
    jnz .notrom1
    mov cx, 14
.sh:
    shr dx, 1
    rcr ax, 1
    loop .sh                        ; AX = banks
    cmp ax, 2
    jb .notrom1
    cmp ax, RW_ROMMAX_KB / 16
    ja .notrom1
    mov [rw_banks], ax
    call rw_jitclaim
    call rw_dmgclaim
    call rw_ramsetup
    call rw_start
    mov byte [rw_state], 1
    pop si
    call rw_hire
    call rw_repaint
    ret
.notrom1:
    mov dx, [rw_romseg]             ; the claim back
    call OSAPI_MEM_FREE
.notrom:
    mov si, rw_s_notrom
    jmp short .say
.rdfail:
    mov dx, [rw_romseg]
    call OSAPI_MEM_FREE
.rdfail0:
    mov si, rw_s_read
    jmp short .say
.big:
    mov si, rw_s_big
    jmp short .say
.room:
    mov si, rw_s_room
.say:
    pop bx                          ; (the window, banked)
    jmp rw_toast

; rw_start - rb_init: the view, the core, the ROM, its banks - and the
; recompiler over them when it has its cache (REALBOY-SPEC section 16)
rw_start:
    mov al, 2                       ; the view
    call op_seg
    push ax
    xor al, al                      ; the core, both halves from here
    call op_seg
    mov bx, ax
    pop ax
    mov cx, [rw_romseg]
    mov dx, [rw_banks]
    call rb_init
    call rw_ramattach
    call rw_dmgfull
rw_jiton:                           ; (and Machine > Recompiler's way back in)
    push ds
    mov ds, [cs:rb_viewseg]
    cmp word [cs:rw_jitseg], 0      ; no cache or not wanted: the plain
    je .off                         ;   interpreter, hooks and all removed
    cmp byte [cs:rw_jitwant], 0
    je .off
    mov ax, [cs:rw_jitseg]
    call rt_init
    pop ds
    ret
.off:
    xor al, al
    call rt_dispatch
    pop ds
    ret

; rw_jitoff - the interpreter alone, between two core runs (the worker's)
rw_jitoff:
    push ds
    mov ds, [cs:rb_viewseg]
    mov byte [S_JITON], 0
    mov word [S_RESVEC], RBC_RB_DISPATCH
    xor al, al
    call rt_dispatch
    pop ds
    ret

; rw_jitclaim - on the UI task, once: a 64KB cache on a 286 or later. The
; recompiler's code is bigger than the interpreter's, and an 8088's bus makes
; bytes the cost; and without the memory it is simply not used.
rw_jitclaim:
    cmp word [rw_jitseg], 0
    jne .r
    call OSAPI_CPU_INFO
    cmp al, CPU_8086
    je .r
    mov ax, 64
    call OSAPI_MEM_CLAIM            ; DX = its segment, pinned: the core's
    jc .r                           ;   state block names it
    mov [rw_jitseg], dx
    mov byte [rw_jitwant], 1
.r:
    ret

; rw_hire - the worker, once (the lock is held: paint, a menu or a dialog)
rw_hire:
    cmp byte [rw_spawned], 0
    jne .r
    mov ax, rw_worker
    mov bx, [rw_win]
    call OSAPI_TASK_SPAWN
    jc .r                           ; refused for now: the next paint asks
    OS88_WORKER_RESTARTABLE rw_worker_rs
    mov byte [rw_spawned], 1
.r:
    ret

; =============================================================================
; Cartridge RAM, its battery and the MBC3 clock (REALBOY-SPEC section 10.1)
; =============================================================================

; rw_ramsetup - after the ROM is read, on the UI task: what the header says
; the cartridge carries, a claim for the banks when there is more than one
; (or a clock, or a battery), and a battery's NAME.SAV out of SYSTEM\APPDATA
rw_ramsetup:
    push es
    mov es, [rw_romseg]
    mov al, [es:0147h]              ; the cartridge type
    mov ah, [es:0149h]              ; the RAM size code
    pop es
    xor bx, bx
    mov [rw_ramseg], bx
    mov [rw_rtc], bl
    mov [rw_batt], bl
    mov si, rw_battab               ; a battery?
.bt:
    cmp byte [si], 0
    je .bd
    cmp al, [si]
    je .by
    inc si
    jmp short .bt
.by:
    mov byte [rw_batt], 1
.bd:
    cmp al, 0Fh                     ; MBC3 + timer
    je .rt
    cmp al, 10h
    jne .sz
.rt:
    mov byte [rw_rtc], 1
.sz:
    mov cx, 512                     ; MBC2: 512 nibbles of its own
    mov bl, 1
    cmp al, 05h
    je .have
    cmp al, 06h
    je .have
    xor cx, cx
    xor bl, bl
    cmp ah, 1
    jb .have                        ; none
    mov cx, 2048
    mov bl, 1
    je .have                        ; 2KB
    mov cx, 8192
    cmp ah, 2
    je .have
    mov cx, 32768                   ; 32KB - and 64/128KB kept as 32KB
    mov bl, 4
.have:
    mov [rw_savelen], cx
    mov [rw_rambanks], bl
    cmp bl, 1                       ; one bank and nothing to keep: the
    ja .claim                       ;   window alone holds it
    cmp byte [rw_rtc], 0
    jne .claim
    cmp byte [rw_batt], 0
    je .r
    or bl, bl
    jz .r                           ; a battery and no RAM: nothing to save
.claim:
    mov al, bl
    or al, al
    jnz .k
    inc al
.k:
    mov ah, 8
    mul ah                          ; AX = 8KB a bank
    add al, [rw_rtc]                ; + 1KB for the clock's trailer
    push ax
    call OSAPI_MEM_CLAIM            ; DX = its segment, pinned: the state
    pop ax                          ;   block names it
    jc .room
    mov [rw_ramseg], dx
    push es                         ; FFh, as a cartridge without a save
    mov es, dx
    xor di, di
    mov ch, al                      ; (AX = KB, under 128)
    xor cl, cl
    shl ch, 1                       ; CX = KB x 512 words
    mov ax, 0FFFFh
    cld
    rep stosw
    pop es
    call rw_savenm
    cmp byte [rw_batt], 0
    je .r
    ; the save, if there is one: a short or missing file leaves FFh
    push es
    mov es, [rw_ramseg]
    xor bx, bx
    mov cx, [rw_savelen]
    xor dx, dx
    cmp byte [rw_rtc], 0
    je .cap
    add cx, 48
.cap:
    mov si, rw_savename
    call od_read                    ; DX:AX = bytes
    pop es
    jc .r
    cmp byte [rw_rtc], 0
    je .r
    mov cx, [rw_savelen]
    add cx, 44
    cmp ax, cx
    jb .r
    call rw_rtcin
.r:
    ret
.room:
    mov si, rw_s_noram
    jmp rw_toast

; rw_savenm - rw_savename = rw_name with its extension made .SAV
rw_savenm:
    mov si, rw_name
    mov di, rw_savename
    mov cx, 8
.c:
    lodsb
    or al, al
    jz .e
    cmp al, '.'
    je .e
    mov [di], al
    inc di
    loop .c
.e:
    mov word [di], 'S' << 8 | '.'
    mov word [di+2], 'V' << 8 | 'A'
    mov byte [di+4], 0
    ret

; rw_ramattach - after rb_init (which zeroed the view): the banks and the
; clock into the state block, bank 0 into the window, and any time a save
; spent switched off onto the clock
rw_ramattach:
    mov ax, [rw_ramseg]
    mov bl, [rw_rambanks]
    mov bh, [rw_rtc]
    push ds
    pop es                          ; ES = ours, for the clock's copy
    push ds
    mov ds, [cs:rb_viewseg]
    mov [S_RAMSEG], ax
    mov [S_RAMBANKS], bl
    mov byte [S_RAMCUR], 0
    mov si, rw_rtcsave              ; our copy of the clock into the view
    mov di, S_RTC
    mov cx, 13
.c:
    mov dl, [es:si]
    mov [di], dl
    inc si
    inc di
    loop .c
    mov [S_RTC+RTC_ON], bh
    mov byte [S_RTC+RTC_LST], 0FFh
    or ax, ax
    jz .nr
    call rb_ramin                   ; bank 0 into the window
.nr:
    mov ax, [es:rw_rtcgap]          ; the time a save spent put away
    mov dx, [es:rw_rtcgap+2]
    mov cx, ax
    or cx, dx
    jz .p
    call rb_rtcadd
.p:
    pop ds
    xor ax, ax
    mov [rw_rtcgap], ax
    mov [rw_rtcgap+2], ax
    ret

; rw_ramkeep - before a reset or a save: the window back to its bank, and the
; clock into rw_rtcsave
rw_ramkeep:
    push ds
    pop es
    push ds
    mov ds, [cs:rb_viewseg]
    call rb_ramsync
    mov si, S_RTC
    mov di, rw_rtcsave
    mov cx, 16
    cld
    rep movsb
    pop ds
    ret

; rw_onclose - the close negotiator, on the UI task with the lock held: a
; battery's RAM saved, and the close always goes ahead
rw_onclose:
    cmp byte [rw_logon], 0          ; the log, if it was on
    je .s
    mov byte [rw_logon], 0
    call rw_logwrite
.s:
    cmp byte [rw_state], 0
    je .r
    cmp byte [rw_batt], 0
    je .r
    cmp word [rw_ramseg], 0
    je .r
    call rw_save
.r:
    clc
    ret

; rw_save - NAME.SAV into SYSTEM\APPDATA: the RAM, and for a clock VBA's
; 48-byte trailer, so the file is any emulator's
rw_save:
    call rw_ramkeep
    mov cx, [rw_savelen]
    cmp byte [rw_rtc], 0
    je .w
    call rw_rtcout
    add cx, 48
.w:
    push es
    mov es, [rw_ramseg]
    xor bx, bx
    mov si, rw_savename
    mov di, rw_odst
    call od_write
    pop es
    jnc .r
    mov si, rw_s_nosave
    jmp rw_toast
.r:
    ret

; rw_rtcout - the trailer at rw_ramseg:rw_savelen: ten dwords (the live
; registers, then the latched) and the time it was written as 64 bits
rw_rtcout:
    push ax
    push cx
    push dx
    push si
    push di
    push es
    mov es, [rw_ramseg]
    mov di, [rw_savelen]
    mov si, rw_rtcsave
    mov cx, 10
    cld
.c:
    lodsb
    xor ah, ah
    stosw
    xor ax, ax
    stosw
    loop .c
    call rw_unix                    ; DX:AX
    stosw
    mov ax, dx
    stosw
    xor ax, ax
    stosw
    stosw
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop ax
    ret

; rw_rtcin - the trailer read back: the registers, and the seconds since it
; was written (none if the clock reads earlier than the stamp)
rw_rtcin:
    push ds
    push ds
    pop es
    mov si, [rw_savelen]
    mov di, rw_rtcsave
    mov cx, 10
    mov ds, [rw_ramseg]
    cld
.c:
    lodsw
    stosb
    lodsw
    loop .c
    mov ax, [si]                    ; the stamp's low dword
    mov dx, [si+2]
    pop ds
    mov bx, ax
    or bx, dx
    jz .r
    mov cx, ax
    mov bx, dx
    call rw_unix
    sub ax, cx
    sbb dx, bx
    jc .r                           ; the clock is behind the save
    mov [rw_rtcgap], ax
    mov [rw_rtcgap+2], dx
.r:
    ret

; rw_unix - the system clock as seconds since 1970 (DX:AX). Years 1980-2099,
; so every fourth year is a leap year.
rw_unix:
    push bx
    push cx
    push si
    push di
    call OSAPI_CLK_GET              ; CX year, DH:DL month:day, BH:BL h:m,
    push ax                         ;   AH seconds
    push bx
    mov si, cx                      ; SI = the year
    mov bl, dh
    xor bh, bh
    dec bx
    shl bx, 1
    mov di, [rw_cumdays+bx]         ; days before the month
    xor dh, dh
    dec dx
    add di, dx                      ; + the day
    cmp bx, 4                       ; past February in a leap year
    jb .nl
    test si, 3
    jnz .nl
    inc di
.nl:
    mov ax, si
    sub ax, 1969
    shr ax, 1
    shr ax, 1
    add di, ax                      ; + the leap days since 1970
    mov ax, si
    sub ax, 1970
    mov cx, 365
    mul cx
    add ax, di                      ; AX = days since 1970
    mov cx, 43200
    mul cx
    shl ax, 1
    rcl dx, 1                       ; DX:AX = days x 86,400
    mov si, ax
    mov di, dx
    pop bx                          ; BH hour, BL minute
    mov al, bh
    xor ah, ah
    mov cx, 3600
    mul cx
    add si, ax
    adc di, dx
    mov al, bl
    mov cl, 60
    mul cl
    add si, ax
    adc di, 0
    pop ax                          ; AH = seconds
    mov al, ah
    xor ah, ah
    add ax, si
    adc di, 0
    mov dx, di
    pop di
    pop si
    pop cx
    pop bx
    ret

rw_battab:      db 03h, 06h, 09h, 0Fh, 10h, 13h, 1Bh, 1Eh, 0
rw_cumdays:     dw 0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334

; rw_toast - SI = a line of our own, 24 characters at most
rw_toast:
    push ds
    pop es
    xor cx, cx
    call OSAPI_TOAST
    ret

; =============================================================================
; The worker
; =============================================================================
rw_worker_rs:                       ; THE RESTART POINT: our region moved with
rw_worker:                          ;   the worker parked at the top of its
    call OSAPI_CPU_INFO             ;   loop; draw the next frame whole
    mov bx, RW_BUDGET86
    cmp al, CPU_8086
    je .bud
    mov bx, RW_BUDGET
.bud:
    mov [rw_budget], bx
    call OSAPI_GET_TICKS
    mov [rw_last], ax
    sub ax, 100                     ; long enough ago: the next frame draws
    mov [rw_drawt], ax
.loop:
    mov bx, [rw_win]
    call OSAPI_TASK_ALIVE           ; no lock held; a closed window ends here
    mov byte [rw_incore], 1         ; raised BEFORE [rw_fsq] is read: the
    cmp byte [rw_fsq], 0            ;   order rwfsx.inc's handoff rests on
    jne .sleep
    cmp byte [rw_resetq], 0
    je .noreset
    mov byte [rw_resetq], 0
    call rw_reset
.noreset:
    cmp byte [rw_jitq], 0
    je .nojq
    mov byte [rw_jitq], 0
    xor byte [rw_jitwant], 1
    call rw_jitoff
    call rw_jiton
.nojq:
    cmp byte [rw_state], 1
    jne .sleep
    cmp byte [rw_pause], 0
    jne .sleep
    call OSAPI_GET_TICKS
    mov bx, ax
    sub bx, [rw_last]
    js .resync
    mov [rw_last], ax
    cmp bx, 10
    jbe .acc
    mov bx, 10
.acc:
    mov ax, RW_PERTICK
    mul bx
    add ax, [rw_owed]
    cmp ax, RW_OWEDMAX              ; a machine that fell behind runs on from
    jbe .owe                        ;   here rather than racing to catch up
    mov ax, RW_OWEDMAX
.owe:
    mov [rw_owed], ax
    push ax
    mov al, ah                      ; (frames owed, for the log)
    call rw_logowed
    pop ax
    cmp ax, 256                     ; nothing owed yet: sleep to the tick
    jb .sleep
    call rw_keys
    call rw_frame
    jc .loop                        ; it stopped
    call rw_sound
    inc word [rw_nrun]
    call rw_stat
    sub word [rw_owed], 256
    xor bx, bx                      ; caught up: draw this one, once the
    cmp word [rw_owed], 256         ;   last draw's own length has passed
    jb .due                         ;   since it ended...
    mov bx, RW_DRAWTICKS            ; ...or it has been too long: a machine
.due:                               ;   that is behind draws by the CLOCK,
    call rw_drawdue                 ;   so its picture rate is the same
    jnc .loop                       ;   whatever the game's speed
    mov si, rw_present
    call rw_timed                   ; a draw of D ticks: the next after D more
    jmp .loop                       ; the clock is read again after EVERY
                                    ;   frame: a worker that spent what it
                                    ;   was owed before looking slept a tick
                                    ;   it did not have whenever it was behind
.resync:
    mov [rw_last], ax
.sleep:
    cmp byte [rw_pause], 0          ; paused or stopped: the speaker quiet
    jne .q
    cmp byte [rw_state], 1
    je .sl
.q:
    call rw_quiet
.sl:
    mov byte [rw_incore], 0
    mov ax, 1
    call OSAPI_TASK_SLEEP
    jmp .loop

; rw_drawdue - CF = 1 if a draw is due: BX ticks past [rw_drawt], which a
; draw sets to its own end plus its own length (rw_timed) - so drawing takes
; at most half the machine, the game the rest. A 286's draw is under a tick,
; so there the rule is "every frame it is caught up"; an 8088's is several,
; and the game keeps its speed while the picture rate falls.
rw_drawdue:
    push ax
    call OSAPI_GET_TICKS
    sub ax, [rw_drawt]
    cmp ax, bx                      ; signed: [rw_drawt] may be ahead
    pop ax
    jl .no
    stc
    ret
.no:
    clc
    ret

; rw_timed - call SI (a draw), then [rw_drawt] = its end + its length
rw_timed:
    call rw_clk                     ; (the log's clock, finer than a tick)
    push dx
    push ax
    call OSAPI_GET_TICKS
    push ax
    inc word [rw_ndrawn]
    call si
    call rw_clk
    pop cx                          ; (the tick at the start)
    pop bx
    sub ax, bx
    pop bx
    sbb dx, bx
    push cx
    call rw_logdraw
    call OSAPI_GET_TICKS
    pop dx
    sub dx, ax
    neg dx                          ; DX = the draw's ticks
    add ax, dx
    mov [rw_drawt], ax
    ret

; rw_frame - run the machine to its next frame, yielding between budgets.
; CF = 1: the core stopped (a bad opcode), and the UI task is told.
rw_frame:
    mov cx, 26                      ; with the LCD off no frame ever ends:
.run:                               ;   a frame's worth of budgets is one
    push cx
    mov ax, [rw_budget]
    call rb_run                     ; ...and each returns with interrupts
    pop cx                          ;   on, so the tick can pre-empt us
    cmp al, RBX_FRAME               ;   between two: no yield per budget,
    je .done                        ;   which was nine task switches a frame
    cmp al, RBX_BADOP
    je .bad
    loop .run
.done:
    cmp byte [rw_infsx], 0          ; (in the bracket there is no one else)
    jne .ok
    call OSAPI_TASK_YIELD           ; one a frame, for a UI task a click woke
.ok:
    clc
    ret
.bad:
    mov byte [rw_state], 2
    mov bx, [rw_win]
    call OSAPI_WM_WAKE
    stc
    ret

; rw_sound - the speaker, after a frame: the LOUDER of the two square
; channels rbsys keeps (REALBOY-SPEC section 17), at 131,072 / (2048 - x)
; Hz, through OSAPI_SND_TONE - and only when the note changed. A refusal (a
; louder owner of the speaker) leaves [rw_tone] stale-zero, so the next
; frame asks again.
rw_sound:
    push ds
    mov ds, [cs:rb_viewseg]
    xor bx, bx                      ; BL, BH = channel 1's, 2's volume (0 off)
    cmp byte [S_SQ1 + SQ_ON], 0
    je .v2
    mov bl, [S_SQ1 + SQ_VOL]
.v2:
    cmp byte [S_SQ2 + SQ_ON], 0
    je .v
    mov bh, [S_SQ2 + SQ_VOL]
.v:
    pop ds
    mov al, [rw_sch]                ; the channel playing STAYS while it
    cmp al, 1                       ;   sounds, unless the other is clearly
    jne .c2                         ;   louder: two voices crossing as their
    or bl, bl                       ;   envelopes fall made one speaker hop
    jz .any                         ;   between melody and harmony note by
    mov ah, bl                      ;   note (the first field run's "odd")
    add ah, 4
    cmp bh, ah
    jb .have
    mov al, 2
    jmp short .have
.c2:
    cmp al, 2
    jne .any
    or bh, bh
    jz .any
    mov ah, bh
    add ah, 4
    cmp bl, ah
    jb .have
    mov al, 1
    jmp short .have
.any:
    xor al, al                      ; none playing: the louder, if any
    cmp bl, bh
    jb .a2
    or bl, bl
    jz .have
    mov al, 1
    jmp short .have
.a2:
    mov al, 2
.have:
    mov [rw_sch], al
    push ds
    mov ds, [cs:rb_viewseg]
    mov dx, 0FF13h
    mov bl, al                      ; BL = the channel (0 none)
    cmp al, 2
    jne .pick
    mov dx, 0FF18h
.pick:
    xor ax, ax                      ; silent unless a channel sounds
    or bl, bl
    jz .play
    mov si, dx
    mov cx, [si]                    ; NRx3, NRx4: the 11-bit frequency
    and ch, 7
    mov bx, 2048
    sub bx, cx                      ; BX = 2048 - x, 1..2048
    mov dx, 2                       ; DX:AX = 131,072
    xor ax, ax
    div bx                          ; AX = hertz
    cmp ax, 20                      ; past the speaker's range: silent
    jb .zero
    cmp ax, 15000
    jbe .play
.zero:
    xor ax, ax
.play:
    pop ds
    cmp ax, [rw_tone]
    je .r
    mov [rw_tone], ax
    xor cx, cx                      ; until off
    mov dl, 40h
    call OSAPI_SND_TONE
    jnc .r
    mov word [rw_tone], 0FFFFh      ; refused: ask again next frame
.r:
    ret

; rw_quiet - the speaker off, if we had it
rw_quiet:
    cmp word [rw_tone], 0
    je .r
    mov word [rw_tone], 0
    xor ax, ax
    xor cx, cx
    mov dl, 40h
    call OSAPI_SND_TONE
.r:
    ret

; rw_reset - Machine > Reset, on the worker: rb_init again from the ROM
rw_reset:
    cmp byte [rw_state], 0
    je .r
    call rw_ramkeep                 ; the cartridge's RAM and clock survive
    call rw_start
    mov byte [rw_state], 1
    mov word [rw_owed], 0
.r:
    ret

; rw_stat - once a second, the overlay's line: the game's speed, frames run
; against the 59.7275 a second the cartridge expects, and the frames drawn
rw_stat:
    call OSAPI_GET_TICKS
    mov cx, ax
    sub cx, [rw_tstat]              ; CX = ticks counted
    cmp cx, 18
    jb .r
    mov [rw_tstat], ax
    cmp cx, 600                     ; a pause, or the first look: start over
    ja .zero0
    ; speed = run x 100 x 18.2065 / (59.7275 x ticks) = run x 3048 / (ticks x 100)
    mov ax, 100
    mul cx
    mov bx, ax                      ; BX = ticks x 100
    mov ax, [rw_nrun]
    mov dx, 3048
    mul dx                          ; DX:AX = run x 3048
    div bx                          ; AX = speed, %
    push ds
    pop es
    mov di, rw_ovltxt
    call rw_dec
    mov al, '%'
    stosb
    mov al, ' '
    stosb
    ; fps = drawn x 18.2065 / ticks ~ drawn x 182 / (ticks x 10)
    mov ax, 10
    mul cx
    mov bx, ax                      ; BX = ticks x 10
    mov ax, [rw_ndrawn]
    mov dx, 182
    mul dx
    div bx
    call rw_dec
    mov si, rw_s_fps
.c:
    lodsb
    stosb
    or al, al
    jnz .c
    push ds                         ; " JIT": the recompiler is running,
    mov ds, [cs:rb_viewseg]         ;   for a photograph of the glass to say
    mov al, [S_JITON]
    pop ds
    or al, al
    jz .rec
    dec di
    mov si, rw_s_jit
.cj:
    lodsb
    stosb
    or al, al
    jnz .cj
.rec:
    call rw_logsec                  ; the second, into the log if it is on
    jmp short .zero
.zero0:
    call rw_logsec.zero
.zero:
    mov byte [rw_ovlnew], 1
    xor ax, ax
    mov [rw_nrun], ax
    mov [rw_ndrawn], ax
.r:
    ret

; rw_dec - AX (0-999) as decimal at ES:DI, no leading zeros
rw_dec:
    ; STKBALANCE-LOOP: one digit pushed a turn and the second loop pops them; the count is in CX
    push bx
    push cx
    push dx
    mov bx, 10
    xor cx, cx
.d:
    xor dx, dx
    div bx
    push dx
    inc cx
    or ax, ax
    jnz .d
.o:
    pop ax
    add al, '0'
    stosb
    loop .o
    pop dx
    pop cx
    pop bx
    ret

; rw_keys - the joypad, from the keys held - and nothing held while another
; window has the keyboard. F1 toggles the speed overlay.
rw_keys:
    xor dl, dl
    cmp byte [rw_infsx], 0          ; the bracket's keyboard is ours
    jne .f1
    call OSAPI_WM_TOP
    cmp bx, [rw_win]
    jne .set
    call OSAPI_MENU_OWNER
    cmp bx, [rw_win]
    jne .set
.f1:
    mov al, KSC_ALT                 ; Alt held: a chord of ours (Alt+Enter
    call OSAPI_KEY_DOWN             ;   would otherwise press Start too)
    jc .set
    mov al, 3Bh                     ; F1, on its press
    call OSAPI_KEY_DOWN
    sbb al, al
    mov ah, al
    xchg al, [rw_f1was]
    not al
    and al, ah
    jz .nof1
    xor byte [rw_ovl], 1
    mov byte [rw_ovlnew], 1
.nof1:
    mov si, rw_keymap
    mov dh, 1
.k:
    lodsb
    or al, al
    jz .set
    call OSAPI_KEY_DOWN             ; CF = 1: held
    jnc .n
    or dl, dh
.n:
    shl dh, 1
    jnz .k
.set:
    push ds
    mov ds, [cs:rb_viewseg]
    mov [S_JOY], dl
    pop ds
    ret
; S_JOY's bits: Right, Left, Up, Down, A, B, Select, Start
rw_keymap:  db KSC_RIGHT, KSC_LEFT, KSC_UP, KSC_DOWN, 2Dh, 2Ch, 39h, KSC_ENTER, 0

; rw_present - compose the frame and put it on the glass (the worker's)
rw_present:
    mov bx, [rw_win]
    call OSAPI_WM_DISPLAY           ; DH = bits per pixel
    push ds
    pop es
    cmp dh, 1
    jbe .mono
    cmp byte [rw_nobp], 0
    jne .mono
    mov di, rw_pbuf                 ; colour: the planes, composed straight
    call rb_render4                 ;   into the buffer BLITP reads
    mov byte [rw_pfmt], 4
    jmp short .show
.mono:
    cmp byte [rw_pfmt], 1           ; the buffer held the other format:
    je .m1                          ;   every line again
    call rw_dmgfull
.m1:
    call rw_render                  ; AX = the lines that changed
    mov byte [rw_pfmt], 1
    or ax, ax
    jnz .m2
    mov byte [rw_incore], 0         ; nothing did: nothing to put up
    ret
.m2:
    call rw_dither
.show:
    mov byte [rw_incore], 0         ; out of the machine BEFORE the lock: the
                                    ;   UI task may hold it, waiting on this
    mov byte [rw_shown], 1
    cmp byte [rw_abon], 0           ; the About card is over us: keep it
    jne .r
    call OSAPI_GFX_LOCK
    mov ax, KERNEL_SEG              ; a worker loads ES itself
    mov es, ax
    mov bx, [rw_win]
    test word [es:bx + W_FLAGS], 2
    jz .un
    call OSAPI_WM_CLIP_SET          ; CF = 1: not a pixel of us shows
    jc .un
    cmp byte [rw_pfmt], 1
    jne .full
    call rw_blitd                   ; the changed lines' bands
    jmp short .ov
.full:
    call rw_blit
.ov:
    call rw_overlay
.un:
    call OSAPI_GFX_UNLOCK
.r:
    ret

; rw_overlay - the speed line over the picture's top left, when F1 put it up
rw_overlay:
    cmp byte [rw_ovl], 0
    je .r
    cmp byte [rw_ovltxt], 0
    je .r
    mov bx, [rw_win]
    call OSAPI_WM_CONTENT           ; AX = left, DX = top
    mov cx, ax
    mov si, rw_ovltxt
    mov ax, (CWHITE << 8) | CBLACK
    call OSAPI_FONT_RUN
.r:
    ret

; rw_blit - rw_pbuf onto the content, the lock held and the clip armed:
; BLITP's four planes on a colour display, the dithered band through BLIT1 on
; a monochrome one (or where BLITP refuses). A buffer composed for the other
; kind of display - the window moved between two - paints white, and the
; worker's next frame, at most RW_DRAWTICKS away, puts the picture back.
rw_blit:
    mov bx, [rw_win]
    call OSAPI_WM_DISPLAY           ; DH = bits per pixel
    cmp dh, 1
    jbe .mono
    cmp byte [rw_pfmt], 4
    jne .colmono
    mov bx, [rw_win]
    call OSAPI_WM_CONTENT           ; AX = left, DX = top
    mov bx, dx
    push ds
    pop es
    mov si, rw_pbuf
    mov di, 4000h | 20              ; walk an armed clip; 20 bytes a plane
    mov bp, 80
    mov cx, RW_CONT_W
    mov dx, RW_CONT_H
    call OSAPI_GFX_BLITP
    jnc .r
    mov byte [rw_nobp], 1           ; refused (a straddle, kern_small): the
    jmp short .white                ;   next frame is dithered
.colmono:
    cmp byte [rw_pfmt], 1
    jne .white
    mov al, CWHITE                  ; the dither on a colour display, in two
    mov ah, CBLACK                  ;   colours
    call OSAPI_GFX_BLIT1_PEN
    jmp short .b1
.mono:
    cmp byte [rw_pfmt], 1
    jne .white
.b1:
    mov bx, [rw_win]
    call OSAPI_WM_CONTENT
    mov bx, dx
    push ds
    pop es
    mov si, rw_pbuf
    mov bp, 20
    mov cx, RW_CONT_W
    mov dx, RW_CONT_H
    call OSAPI_GFX_BLIT1
.r:
    ret
.white:
    jmp rw_fillwhite

; rw_dither - rw_fbuf as one bit a pixel, 1 = lit: shade 0 all lit, 1 a
; quarter dark, 2 half (a checkerboard), 3 all dark - a 2x2 ordered dither
rw_dither:
    push ds
    pop es
    mov si, rw_fbuf
    mov di, rw_pbuf
    xor dx, dx                      ; DL = the row's parity
.row:
    call rw_dchg                    ; ZF = 1: this line did not change
    jnz .do
    add si, 40
    add di, 20
    jmp short .nx
.do:
    mov bl, 0AAh                    ; even rows: half on even columns, the
    mov bh, 0AAh                    ;   quarter on even columns
    test dl, 1
    jz .ev
    mov bl, 055h                    ; odd rows: the other half, no quarter
    xor bh, bh
.ev:
    mov cx, 20
.b:
    mov al, [si]                    ; bit 0
    mov ah, [si+20]                 ; bit 1
    mov dh, al
    and dh, ah                      ; shade 3: dark
    not al
    and al, ah                      ; shade 2: bit 1 alone
    and al, bl
    or dh, al
    mov al, [si]
    not ah
    and al, ah                      ; shade 1: bit 0 alone
    and al, bh
    or al, dh
    not al                          ; lit = not dark
    stosb
    inc si
    loop .b
    add si, 20
.nx:
    inc dl
    cmp dl, RW_CONT_H
    jb .row
    ret

; rw_dchg - DL = a line: ZF = 0 if the last rb_renderd changed it
rw_dchg:
    push bx
    mov bl, dl
    xor bh, bh
    cmp byte [rw_chg + bx], 0
    pop bx
    ret

; rw_render - rb_renderd into rw_fbuf, and its changed lines into rw_chg
; (every line, without the damage memory). AX = how many.
rw_render:
    push cx
    push si
    push di
    push ds
    pop es
    mov di, rw_fbuf
    call rb_renderd
    push ax
    add [rw_achg], ax               ; (the log's counts)
    mov di, rw_chg
    mov cx, 144 / 2
    mov ax, [rb_dmgseg]
    or ax, ax
    jnz .cp
    add word [rw_acomp], 144
    mov ax, 0101h
    rep stosw
    jmp short .r
.cp:
    push ds
    mov ds, ax
    mov si, RB_DCHG
    rep movsw
    xor ax, ax
    xchg ax, [RB_DCOMP]
    pop ds
    add [rw_acomp], ax
.r:
    pop ax
    pop di
    pop si
    pop cx
    ret

; rw_blitd - the lines rb_renderd changed onto the content, a band a run of
; them, the lock held and the clip armed. Nothing changed, nothing drawn.
rw_blitd:
    mov bx, [rw_win]
    call OSAPI_WM_DISPLAY           ; DH = bits per pixel
    cmp dh, 1
    jbe .mono
    mov al, CWHITE                  ; the dither on a colour display
    mov ah, CBLACK
    call OSAPI_GFX_BLIT1_PEN
.mono:
    xor dl, dl                      ; DL = the line
.find:
    call rw_dchg
    jnz .run
.nx:
    inc dl
    cmp dl, RW_CONT_H
    jb .find
    ret
.run:
    mov dh, dl                      ; DH = the run's first line
.ext:
    inc dl
    cmp dl, RW_CONT_H
    jae .put
    call rw_dchg
    jnz .ext
.put:                               ; DH = the run's first line, DL past it
    push dx
    mov bl, dh
    xor bh, bh
    mov ax, 20
    mul bx
    mov si, rw_pbuf
    add si, ax                      ; SI = the run in the dithered buffer
    push bx
    mov bx, [rw_win]
    call OSAPI_WM_CONTENT           ; AX = left, DX = top
    pop bx
    add bx, dx                      ; BX = the run's row on the screen
    pop dx
    push dx
    mov cl, dl
    sub cl, dh
    xor ch, ch
    mov dx, cx                      ; DX = its lines
    push ds
    pop es
    mov bp, 20
    mov cx, RW_CONT_W
    call OSAPI_GFX_BLIT1
    pop dx
    jmp short .nx

; rw_dmgclaim - on the UI task, once: rb_renderd's memory, when there is
; room (without it every frame is composed whole)
rw_dmgclaim:
    cmp word [rb_dmgseg], 0
    jne .r
    mov ax, (RB_DMG_SIZE + 1023) / 1024
    call OSAPI_MEM_CLAIM
    jc .r
    mov [rb_dmgseg], dx
.r:
    ret

; rw_dmgfull - the next rb_renderd composes and writes every line
rw_dmgfull:
    push es
    push ax
    mov ax, [rb_dmgseg]
    or ax, ax
    jz .r
    mov es, ax
    mov byte [es:RB_DFULL], 1
.r:
    pop ax
    pop es
    ret

; =============================================================================
; The window
; =============================================================================

; rw_paint - SI = the window, the lock held, the clip armed
rw_paint:
    call rw_mgrey
    push si
    mov byte [rw_nobp], 0           ; a paint asks BLITP again: the window
    cmp byte [rw_shown], 0          ;   may have moved off the straddle
    je .blank
    call rw_blit
    jmp short .about
.blank:
    call rw_fillwhite
    mov si, rw_s_open1
    cmp byte [rw_state], 2
    jne .t
    mov si, rw_s_stop1
.t:
    mov dx, 60
    call rw_line
    mov si, rw_s_open2
    cmp byte [rw_state], 2
    jne .t2
    mov si, rw_s_stop2
.t2:
    mov dx, 74
    call rw_line
.about:
    pop si
    cmp byte [rw_abon], 0
    je .r
    push si
    mov bx, si
    mov si, rw_ablines
    call os88ui_about_d
    pop si
    cmp byte [rw_spawned], 0        ; a refused hire is asked again here
    jne .r
    cmp byte [rw_state], 1
    jne .r
    call rw_hire
.r:
    ret

; rw_line - SI = a string, DX = its row in the content, centred
rw_line:
    push ax
    push bx
    push cx
    push dx
    mov cx, dx
    mov bx, [rw_win]
    call OSAPI_WM_CONTENT           ; AX = left, DX = top
    add dx, cx                      ; DX = the row
    mov bx, ax
    call OSAPI_FONT_WIDTH           ; AX = the string's width
    mov cx, RW_CONT_W
    sub cx, ax
    sar cx, 1
    add cx, bx                      ; CX = x
    mov ax, (CWHITE << 8) | CBLACK
    call OSAPI_FONT_RUN
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; rw_fillwhite - the content white
rw_fillwhite:
    push ax
    push bx
    push cx
    push dx
    mov al, CWHITE
    call OSAPI_SET_COLOR
    mov bx, [rw_win]
    call OSAPI_WM_CONTENT
    mov bx, dx
    mov cx, ax
    add cx, RW_CONT_W - 1
    add dx, RW_CONT_H - 1
    call OSAPI_GFX_FILL
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; rw_repaint - SI = the window, the lock held: everything, ourselves
rw_repaint:
    push bx
    mov bx, si
    call OSAPI_WM_CLIP_SET
    pop bx
    jc .r
    jmp rw_paint
.r:
    ret

; rw_oncmd - AH = the menu, AL = the item, SI = the window, the lock held
rw_oncmd:
    push ax
    call rw_abdismiss
    pop ax
    cmp ah, 0
    jne .machine
    cmp al, 0
    je rw_open
    mov bx, si                      ; File > Close
    call OSAPI_WM_CLOSE
    ret
.machine:
    cmp al, 0
    jne .pause
    mov byte [rw_resetq], 1         ; Reset: the worker's to do
    ret
.pause:
    cmp al, 1
    je .p
    cmp al, 2
    je rw_fsenter                   ; Full Screen
    cmp al, 4
    je rw_logtoggle                 ; Log
    cmp word [rw_jitseg], 0         ; Recompiler: the worker flips it
    je .r
    mov byte [rw_jitq], 1
.r:
    ret
.p:
    xor byte [rw_pause], 1
    ret

; rw_onkey - AX = a typed key, SI = the window, the lock held: Alt+Enter is
; Machine > Full Screen (SPEC.md 11.2.1.1); the game reads the keys held,
; not the keys typed, so nothing else here is ours
rw_onkey:
    cmp ax, KEY_ALTENTER
    jne .r
    call rw_abdismiss
    jmp rw_fsenter
.r:
    ret

rw_about:
    mov byte [rw_abon], 1
    mov bx, si
    mov si, rw_ablines
    jmp os88ui_about

rw_abdismiss:
    mov bx, rw_abon
    mov ax, rw_repaint
    jmp os88ui_abdismiss

rw_tpl:
    dw 160, 60, RW_CONT_W + 2, RW_CONT_H + TITLE_H + 2
    dw rw_ttl, rw_paint, rw_onkey, rw_abdismiss

    OS88_MENUSET rw_menus, rw_ttl, rw_oncmd
        OS88_MENU rw_m_file, rw_i_file, 2
        OS88_MENU rw_m_mach, rw_i_mach, 5
    OS88_MENUSET_END rw_menus

rw_ttl:         db 'RealBoy', 0
rw_m_file:      db 'File', 0
rw_i_file:      dw rw_it_open, rw_it_close
rw_it_open:     db 'Open...', 0
rw_it_close:    db 'Close', 0
rw_m_mach:      db 'Machine', 0
rw_i_mach:      dw rw_it_reset, rw_it_pause, rw_it_fs0, rw_it_jit0, rw_it_log0
rw_it_reset:    db 'Reset', 0
rw_it_pause:    db 'Pause', 0
rw_it_fs:       db 'Full Screen', 0
rw_it_fs0:      db MENU_DIS, 'Full Screen', 0
rw_it_jon:      db 'Recompiler: On', 0
rw_it_joff:     db 'Recompiler: Off', 0
rw_it_jit0:     db MENU_DIS, 'Recompiler (286)', 0
rw_it_log0:     db 'Log: Off', 0
rw_it_log1:     db 'Log: On', 0

rw_s_fps:       db 'fps', 0
rw_s_jit:       db ' JIT', 0
rw_s_open1:     db 'File > Open a', 0
rw_s_open2:     db 'Game Boy .GB', 0
rw_s_stop1:     db 'The game stopped:', 0
rw_s_stop2:     db 'an invalid opcode', 0
rw_s_one:       db 'REALBOY: one game each', 0
rw_s_big:       db 'REALBOY: ROM over 256K', 0
rw_s_notrom:    db 'REALBOY: not a GB ROM', 0
rw_s_room:      db 'REALBOY: no room for ROM', 0
rw_s_read:      db 'REALBOY: read failed', 0
rw_s_noram:     db 'REALBOY: no room for RAM', 0
rw_s_nosave:    db 'REALBOY: save failed', 0

rw_ablines:
    dw rw_ab1, rw_ab2, rw_ab3, rw_ab4, rw_ab5, rw_ab6, rw_ab7, 0
rw_ab1:         db 'RealBoy', 0
rw_ab2:         db 'a Game Boy for os8088', 0
rw_ab3:         db 0
rw_ab4:         db 'Arrows, X = A, Z = B', 0
rw_ab5:         db 'Enter = Start', 0
rw_ab6:         db 'Space = Select', 0
rw_ab7:         db 'F1 = speed', 0

%include "rbdefs.inc"
%include "rbsys.inc"
%include "rbppu.inc"
%include "rwfsx.inc"
%include "rbjit.inc"

%include "os88data.inc"
%include "os88alt.inc"
%include "os88pit.inc"
%include "rwlog.inc"

%define OS88UI_ABOUT
%define OS88UI_NOBTN
%define OS88UI_ABDISMISS
%include "os88ui.inc"

; THE PART TABLE (SPEC.md 20.12.3): the core, compressed on the disk, and the
; view, a zeroed carve that costs no disk at all
OS88_PARTS_BEGIN 3
    OS88_PART OP_SEG, OP_COMP                   ; 0  the core's first half
    OS88_PART OP_ASSET, OP_COMP                 ; 1  ...and its second: one
                                                ;    part is at most 65,024
                                                ;    bytes (SPEC.md 20.12.11)
    OS88_PART OP_ASSET, OP_ZERO, 64             ; 2  the view
OS88_PARTS_END
    align 2, db 0
    OS88_BSS OP_BSS + RW_BSS
    OS88_IMAGE_END
