; =============================================================================
; stkdiag.inc - what an INTERRUPT costs on a task stack, measured by the
;               machine itself (docs/STACK-SLOTS-PLAN.md).  `make STKDIAG=1`
;               ONLY.
;
; docs/STACK-SLOTS-PLAN.md 2 priced the interrupt floor at 82 of 384 bytes and
; found that 50 of those are the ROM's `int 08h` handler running on whichever
; task stack it interrupted - measured under QEMU, by an A/B between two
; kernels. Two things make that number unsafe to build on:
;
;   * it is SeaBIOS's, and every ROM is different. The whole point of the
;     number is to size a task slice on a 5150, an XT clone and a 386, and
;     QEMU is none of them.
;   * docs/KERNEL-MEMORY.md's "Task stacks" says the opposite - that SeaBIOS
;     services its interrupt entries on an internal stack of its own, so the
;     only foreign frames a slice carries under `make test` are ours. If that
;     were true the 82 would be nearly all ours and the +46 QEMU-to-5150
;     correction quoted beside it would be a second, independent adder. It
;     cannot be both.
;
; So this asks the question from INSIDE, where the answer is exact and needs no
; second kernel: a sentinel is written into the free bytes below SP, the ROM is
; called, and what came back scrubbed is what the ROM used. One boot, one
; number, on any BIOS.
;
; WHY IT IS A KERNEL KNOB AND NOT A PACKAGE. tests/stackprobe asks the
; neighbouring question and has to be launched, which means a double-click,
; which means the mouse has already moved before the quiet measurement starts -
; and the quiet measurement is the one that matters most and the only one a
; human cannot perturb. A knob boots to its own panel with no input at all.
; It also reaches `sch_old08`, which no package can name.
;
; WHAT IT COSTS THE MEASUREMENT. The diagnostic task below takes a slot and a
; slice of its own, so a STKDIAG kernel has two fewer worker slots than a
; shipped one (the idle task's and this one's). It does NOT perturb the number:
; the floor is read off the IDLE task's slice, which this code only ever reads.
;
; Prefix sd_.
; =============================================================================
%ifdef STK_DIAG

section .text

; ---- the sentinel window ----------------------------------------------------
; 0xE5 rather than task_spawn's 0xCC (SPEC.md 8.3), so the two fills can never
; be confused: this one answers "what did the ROM touch just now", that one
; answers "how deep has anything ever been", and a byte that reads as the wrong
; instrument is worse than no byte.
;
; 192 is three times the deepest ROM chain seen so far and is CLAMPED below by
; the slice base at every fill, so an unknown BIOS that uses more reports a
; saturated 192 rather than eating the canary. A diagnostic that halts the
; machine it was sent to diagnose is worthless.
SD_SENT    equ 0xE5
SD_SCRATCH equ 512              ; the private chain stack, sized for a ROM
                                ; handler AND a tick nested inside it

; ---- the phase clock, in system ticks (18.2065 Hz) --------------------------
; Wall clock and not "when the human is ready", because the point of the phases
; is that each one is the same length on every machine it is run on. A phase
; the operator sat out still yields its own number; it just equals the phase
; before it, which is a reading and not a hole.
SD_T_QUIET equ 546              ; 0 .. 30s   nothing touched
SD_T_MSTOP equ 1001             ; ..55s      mouse moving
SD_T_MOUSE equ 1092             ; ..60s      HANDS OFF, then latch
SD_T_KSTOP equ 1547             ; ..85s      keys held
SD_T_KEYS  equ 1638             ; ..90s      HANDS OFF, then latch

; THIRTY SECONDS OF QUIET, NOT FIFTEEN. The high water is a sample of a nesting
; distribution and the rarest combinations take a while to come round: a 15s
; quiet phase latched 84 on a machine whose maximum was still climbing to 130
; a few seconds later, which put the difference in the wrong row and read as
; the keyboard's cost. The MAX row is the one to quote and it only ever rises;
; the phase rows are the cumulative maximum at each boundary.

; The two STOP windows are the bulletproofing, and they are there because the
; first run needed them: the operator was still typing when phase 3 latched, so
; "+keys" read 84 while the live row read 130 and the difference the phase
; exists to show was in the wrong row. Five seconds of HANDS OFF before each
; latch costs nothing and makes a late finger harmless.
SD_PERIOD  equ 9                ; ticks between repaints, ~0.5s

; ---- the panel, in pixels ---------------------------------------------------
; Sized for the SMALLEST screen this can boot on - CGA is 640x200 (SPEC.md 39)
; - and clamped to the live geometry at draw time like bootprof's.
SD_X       equ 12
SD_Y       equ 20
SD_ROW     equ 8
SD_VALX    equ SD_X + 25*8
SD_ROWS    equ 19

; ---- state ------------------------------------------------------------------
; In .text with real initialisers, for dsk_dpt's reason (SPEC.md 18.92):
; `-f bin` zeroes nothing and .bss is the previous session's bytes on a warm
; restart, which for a MAXIMUM is the difference between a reading and a lie.
sd_rom08:   dw 0                ; deepest the ROM's int 08h chain has gone
sd_savesp:  dw 0                ; the task's SP across the swap
sd_busy:    db 0                ; a chain is already on the scratch
sd_alt:     db 0                ; ALTERNATES. Running every chain on the
                                ; scratch measures the chain perfectly and
                                ; makes the floor a lie - it becomes the floor
                                ; of the machine 4.1 PROPOSES, not the one that
                                ; ships, and the panel would report 38 where
                                ; the shipping kernel is 82. So odd ticks are
                                ; measured on the scratch and even ticks run
                                ; plainly on the task stack, where the 0xCC
                                ; fill records them. Both numbers on the panel
                                ; are then true of the kernel they describe,
                                ; and the DIFFERENCE between them is what 4.1
                                ; is worth on this machine
sd_n:       dw 0                ; sentinel passes actually taken. A reading of
                                ; 0 beside a floor that moved means the
                                ; instrument never ran, which is a different
                                ; fault from a chain that costs nothing - and
                                ; without this row the two are the same picture
sd_sat:     db 0                ; non-zero: it filled the whole window, so the
                                ; number above is a FLOOR and not the answer
sd_q:       dw 0                ; idle-slice high water, latched per phase
sd_m:       dw 0
sd_k:       dw 0
sd_phase:   db 0                ; 0 quiet, 1 mouse, 2 keys, 3 done
sd_t0:      dw 0                ; [ticks] when the panel came up
sd_slot:    db 0xFF             ; the diagnostic task's own slot

sd_armed:   db 0                ; non-zero: the desktop is up and the sentinel
                                ; may run. IT MUST NOT RUN DURING BOOT - the
                                ; fill happens inside sch_isr with IF=0, and
                                ; SPEC.md 9.4.1's identify window is decided by
                                ; a 1200-baud burst the 8250 holds one byte at
                                ; a time. Measured, before this gate existed:
                                ; the loading screen stops at "Looking for
                                ; Mouse", which is that byte loss exactly and
                                ; is the failure sched.inc's own comment warns
                                ; about one routine up

; ---- the 'SD' block (SPEC.md 57.2) ------------------------------------------
; So an emulator run is READ rather than photographed: tools/stkdiagread.py
; follows the registry to this and prints the same numbers the panel draws.
; Knob-built under 57.2's rule - it COUNTS, which is work a kernel has no other
; reason to do.
sd_dbg_blk:
    dw DBG_TAG_STKD             ; 'SD' - the tag is the first word too, so a
    dw sd_rom08                 ; reader can check where its pointer landed
    dw sd_q
    dw sd_m
    dw sd_k
    dw sd_phase                 ; byte-wide, but the block is words: the reader
    dw SCH_STACK                ; takes the low half
    dw MAX_TASKS

; -----------------------------------------------------------------------------
; sd_slice_base - the base of slot AL's slice, or CF=1 if it has none
; in:       AL = slot;  DS = KERNEL_SEG
; out:      CF = 0 and BX = the slice base (a LOW_SEG offset), else CF = 1
; clobbers: BX, flags
;
; sch_switch's arithmetic, in one place that three readers here share. Slot 0
; owns no slice of sch_stacks (SPEC.md 8) and is refused rather than answered.
; -----------------------------------------------------------------------------
sd_slice_base:
    push ax
    push cx
    push dx
    or al, al
    jz .none                    ; task 0's stack is not a slice of sch_stacks
                                ; (SPEC.md 2.1) and nothing here measures on
                                ; it: the two tasks below are spun precisely so
                                ; that the ticks land somewhere whose base this
                                ; routine can derive and whose free space is
                                ; known. Filling below ui_task's SP was tried
                                ; and left the panel half-drawn
    cmp al, MAX_TASKS
    jae .none
    dec al
    mov ah, 0
    mov dx, SCH_STACK
    mul dx                      ; DX:AX = (slot-1) * SCH_STACK; the guard in
                                ; sched.inc bounds the product to one segment
    add ax, sch_stacks
    mov bx, ax
    pop dx
    pop cx
    pop ax
    clc
    ret
.none:
    pop dx
    pop cx
    pop ax
    stc
    ret

; -----------------------------------------------------------------------------
; sd_pre08 / sd_post08 - what the ROM's int 08h chain costs a task stack
; in:       BP = SP at the chain, taken by sch_isr BEFORE either call;
;           DS = KERNEL_SEG, IF = 0
; out:      [sd_rom08] raised if this pass was the deepest yet
; clobbers: nothing (every register and the flags are restored)
;
; THE ANCHOR IS PASSED IN, and that is the whole of what the first version got
; wrong: it read SP inside itself, where `call` had already moved it, so the
; window sat two bytes below where the chain actually writes and the ROM's
; frames landed above it. The dump said so in the end - `00 F0` segments on the
; slice with the sentinel untouched underneath them.
;
; ONLY ON THE IDLE TASK'S SLICE. Its own footprint is at most 4 bytes
; (task_yield's `pushf` is followed by `cli`), so the bytes below the anchor are
; free by construction and there is always room for the window. The floor is
; read off sd_victim's slice instead, which this never writes to - an
; instrument that scrubs the fill the measurement reads is measuring itself.
;
; What it reports is the WHOLE chain - our `pushf`, the far call's own return
; frame, the ROM's handler, and anything that nested inside it because a real
; BIOS `sti`s before int 1Ch. That is deliberate: it is what the A/B in
; docs/STACK-SLOTS-PLAN.md 2 removed, so the two numbers answer the same
; question and can be compared.
; -----------------------------------------------------------------------------
; -----------------------------------------------------------------------------
; sd_chain_call - run the ROM's int 08h chain on a PRIVATE stack and measure it
; in:       DS = KERNEL_SEG, SS = LOW_SEG, IF = 0; called from sch_isr in place
;           of `pushf` / `call far [sch_old08]`
; out:      the chain has run; [sd_rom08] raised if this pass was the deepest
; clobbers: nothing the ISR still needs (AX/BX/CX/DI/ES are saved here)
;
; THE THIRD DESIGN, and the first that is both safe and unconditional. The two
; before it tried to sentinel the free bytes below SP on a task stack:
;
;   * on the idle task's slice only - which took no samples at all, because on
;     a desktop with a repainting panel the tick lands on task 0 far more often
;     than on the idle task;
;   * on whatever task was interrupted - which meant filling below ui_task's SP
;     on task 0's 1,024 bytes, and left the panel half drawn.
;
; Switching SP instead touches NO task stack. It is exact on every tick whoever
; was interrupted, it cannot corrupt a slice or a canary, and it is also a
; working prototype of the fix docs/STACK-SLOTS-PLAN.md 4.1 proposes - so a
; field run measures the ROM's cost AND demonstrates that moving it off the
; task stack works on that machine, in one boot.
;
; SS is not touched: every task already runs SS = LOW_SEG (SPEC.md 1/2.1) and
; the scratch is in .lowbss, so this is an SP swap and nothing else.
;
; RE-ENTRANCY IS REAL. A ROM handler sends the EOI and then typically `sti`s to
; call int 1Ch, so a second IRQ0 can arrive inside the first. The busy flag
; sends that one down the plain path - it still runs on the scratch, because SP
; is the scratch, which is why SD_SCRATCH is sized for the nesting rather than
; for one chain.
; -----------------------------------------------------------------------------
sd_chain_call:
%ifndef STK_FIX
    xor byte [sd_alt], 1        ; every other tick runs plainly, so the floor
    jz .plain                   ; the panel reports is the SHIPPING floor.
                                ; `make STKFIX=1` drops the alternation: every
                                ; chain goes on the scratch, and the floor the
                                ; panel then reports is the floor of the machine
                                ; 4.1 and 4.2 PROPOSE. That is a lie about the
                                ; shipping kernel and the whole point on a disk
                                ; whose job is to price the proposal - so it is
                                ; a third arm and never the default
%endif
    cmp byte [sd_busy], 0
    je .measure
.plain:
    pushf                       ; nested: chain plainly, measure nothing
    call far [sch_old08]
    ret

.measure:
    push ax
    push bx
    push cx
    push di
    push es
    mov byte [sd_busy], 1

    mov ax, LOW_SEG             ; fill the scratch with the sentinel
    mov es, ax
    mov di, sd_scratch
    mov cx, SD_SCRATCH
    mov al, SD_SENT
    cld
    rep stosb

    pop es                      ; restore what the chain does not need saved
    pop di                      ; ACROSS the stack swap - anything still on the
    pop cx                      ; stack when SP moves would be stranded
    pop bx
    pop ax

    mov [sd_savesp], sp         ; --- the swap ---------------------------------
    mov sp, sd_scratch + SD_SCRATCH
    pushf
    call far [sch_old08]
    mov sp, [sd_savesp]         ; --- and back ---------------------------------

    push ax
    push bx
    push cx
    push di
    push es
    mov ax, LOW_SEG
    mov es, ax
    mov di, sd_scratch + SD_SCRATCH - 1
    mov cx, SD_SCRATCH
    mov al, SD_SENT
    std                         ; down from the top: the cost is the DEPTH, not
    repne scasb                 ; the scratch, and every clock here is inside
    cld                         ; sch_isr's IF=0 window
    jne .sat                    ; nothing left: it used the whole scratch
    inc di                      ; DI = the deepest byte still sentinel...
    mov ax, sd_scratch + SD_SCRATCH
    sub ax, di
    dec ax                      ; ...so the deepest byte TOUCHED is one above
    inc word [sd_n]
    cmp ax, [sd_rom08]
    jbe .done
    mov [sd_rom08], ax
    jmp short .done
.sat:
    cld
    mov byte [sd_sat], 1
    mov word [sd_rom08], SD_SCRATCH
.done:
    mov byte [sd_busy], 0
    pop es
    pop di
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; sd_water - the high water of slot AL's slice, from task_spawn's 0xCC fill
; in:       AL = slot;  DS = KERNEL_SEG
; out:      AX = bytes used from the slice top, or 0 if it was never spawned
; clobbers: AX, flags
;
; tools/stkwater.py's `water()`, in the kernel: the scan starts ABOVE the canary
; word and a slice whose canary is not there was never spawned. Reading the
; DEPTH and not the occupancy - a slice is written at both ends by construction.
; -----------------------------------------------------------------------------
sd_water:
    push bx
    push cx
    push di
    push es
    call sd_slice_base
    jc .none
    mov cx, LOW_SEG
    mov es, cx
    cmp word [es:bx], SCH_MAGIC
    jne .none                   ; no canary: never spawned
    mov di, bx
    inc di
    inc di                      ; ...start above it
    mov cx, SCH_STACK - 2
    mov al, SPB_CC
    cld
    repe scasb                  ; the first byte that is not the fill
    jne .hit
    xor ax, ax                  ; nothing but fill: untouched
    jmp short .out
.hit:
    dec di
    mov ax, bx
    add ax, SCH_STACK           ; the slice top...
    sub ax, di                  ; ...less how far up the fill survived
    jmp short .out
.none:
    xor ax, ax
.out:
    pop es
    pop di
    pop cx
    pop bx
    ret

SPB_CC     equ 0xCC             ; task_spawn's fill (SPEC.md 8.3)

%ifndef NO_MOUPRIV
; -----------------------------------------------------------------------------
; sd_mwater - how deep the mouse ISR has been on its own stack (SPEC.md 9.10)
; in:       DS = KERNEL_SEG
; out:      AX = bytes used from the top of mou_pstack
;
; The stack is filled with the sentinel ONCE, by sd_start, and never again: the
; deepest excursion leaves the lowest scrubbed byte behind it, so a cumulative
; high water needs no per-interrupt work at all. That matters here more than it
; did for the tick - IRQ4 arrives ~120 times a second while the hand is moving
; (SPEC.md 9), and a fill on each one would be the instrument outweighing what
; it measures.
; -----------------------------------------------------------------------------
sd_mwater:
    push bx
    push cx
    push di
    push es
    mov ax, LOW_SEG
    mov es, ax
    mov di, mou_pstack + MOU_PSTK - 1
    mov cx, MOU_PSTK
    mov al, SD_SENT
    std
    repne scasb                 ; down from the top to the first survivor
    cld
    jne .full                   ; none left: it used the whole stack
    inc di
    mov ax, mou_pstack + MOU_PSTK
    sub ax, di
    dec ax
    jmp short .out
.full:
    mov ax, MOU_PSTK
.out:
    pop es
    pop di
    pop cx
    pop bx
    ret
%endif

; -----------------------------------------------------------------------------
; sd_iwater - the IDLE task's slice, and THIS is the floor
; in:       DS = KERNEL_SEG
; out:      AX = bytes, or 0 if there is no idle task
;
; The idle task's own footprint is at most 4 bytes (SS-1.1), so everything its
; slice reads above that is interrupt and nothing else. That is the definition
; of the floor, and it is the number a slot class is cut from.
;
; It is a SEPARATE row from the deepest-slice one below because the field
; compared the wrong one across machines and got a spread that is not there:
; the deepest slice is almost always THIS PANEL'S OWN PAINTER, which draws
; under the gfx lock, so its depth is its own work and it tracks the ADAPTER's
; drawing cost - 124 on EGA against 74 on VGA - while the floor beneath it
; moved by 8. A row labelled "quote this" has to be the one worth quoting.
; -----------------------------------------------------------------------------
sd_iwater:
    mov al, [sch_idleslot]
    cmp al, 0xFF
    jne sd_water
    xor ax, ax
    ret

; -----------------------------------------------------------------------------
; sd_vwater - the deepest ANY slice has been: THE FLOOR
; in:       DS = KERNEL_SEG
; out:      AX = bytes, or 0 if the victim was refused a slot
;
; EVERY slice and not just the idle task's, which is what this read first, and
; the reason is the phases: while the operator is moving the mouse or holding a
; key the UI task is AWAKE, so those interrupts land on whatever is running and
; never on the idle task at all. Reading one slice made "+mouse" and "+keys"
; both report +0 on a machine whose deepest slice was 46 bytes further down.
;
; Nothing here writes to a slice - the chain runs on sd_scratch (see
; sd_chain_call), so every slice's 0xCC fill (SPEC.md 8.3) is intact and
; records exactly the interrupts that landed on it.
; -----------------------------------------------------------------------------
sd_vwater:
    push bx
    push dx
    xor dx, dx                  ; DX = the deepest seen so far
    mov bx, 1
.next:
    mov ax, bx
    call sd_water
    cmp ax, dx
    jbe .skip
    mov dx, ax
.skip:
    inc bx
    cmp bx, MAX_TASKS
    jb .next
    mov ax, dx
    pop dx
    pop bx
    ret

; -----------------------------------------------------------------------------
; sd_victim - a task that exists to be interrupted, and does nothing else
; -----------------------------------------------------------------------------

; -----------------------------------------------------------------------------
; sd_utoa - AX unsigned -> decimal at ES:DI, NUL-terminated
; in:       AX = value, ES:DI = destination (needs 6 bytes)
; out:      DI -> the stored NUL
; clobbers: AX, flags
;
; files.inc's fm_utoa does this and lives in `.cold`, with a NEAR `ret` - so it
; is neither near-callable from here (os88ovlchk refuses the crossing) nor
; far-callable at all (SPEC.md 2.6 wants an `_x` body and a resident thunk, and
; fm_utoa is an internal helper with neither). Fifteen instructions is cheaper
; than either, and this runs twice a second on a diagnostic kernel.
; -----------------------------------------------------------------------------
sd_utoa:
    push bx
    push cx
    push dx
    xor cx, cx
    mov bx, 10
.split:
    xor dx, dx
    div bx                      ; AX = quotient, DX = this digit
    push dx                     ; least significant first, popped in print order
    inc cx
    or ax, ax
    jnz .split
.emit:
    pop ax
    add al, '0'
    stosb
    loop .emit
    mov byte [es:di], 0
    pop dx
    pop cx
    pop bx
    ret

; -----------------------------------------------------------------------------
; sd_ident - copy the ROM's date string and model byte out of F000
; in:       DS = KERNEL_SEG
; out:      [sd_bios] = "MM/DD/YY",0;  AL = the model byte
; clobbers: AX, flags
;
; F000:FFF5 is eight ASCII characters on every IBM and every clone that wanted
; to be one, and F000:FFFE is the model (FC = AT, FE = XT, FF = PC). Neither is
; guaranteed, so nothing here PARSES them - they are copied to the panel as
; found, because their job is to tell two field results apart and a byte that
; is not what we expected still does that.
; -----------------------------------------------------------------------------
sd_ident:
    push bx
    push cx
    push si
    push di
    push ds
    push es
    mov ax, ds
    mov es, ax                  ; ES = KERNEL_SEG, for the destination
    mov di, sd_bios
    mov ax, 0xF000
    mov ds, ax
    mov si, 0xFFF5
    mov cx, 8
    cld
    rep movsb
    mov byte [es:di], 0
    mov al, [0xFFFE]            ; the model byte, through the same DS
    mov [es:sd_model], al       ; ...banked, so the paint path formats and does
    pop es                      ; not re-probe: one reader of F000 is enough
    pop ds
    pop di
    pop si
    pop cx
    pop bx
    ret

; -----------------------------------------------------------------------------
; sd_label / sd_value / sd_hexb - one row of the panel
; in:       SI = string (label) or AX = number (value);  BP = the row's y
; -----------------------------------------------------------------------------
sd_label:
    push ax
    push cx
    push dx
    mov cx, SD_X
    mov dx, bp
    mov ax, (CBLACK << 8) | CWHITE   ; AL = ink, AH = the panel's ground
    call font_run
    pop dx
    pop cx
    pop ax
    ret

sd_value:
    push ax
    push cx
    push dx
    push si
    push di
    push es
    mov cx, ds
    mov es, cx
    mov di, sd_buf
    call sd_utoa
    pop es
    mov si, sd_buf
    mov cx, SD_VALX
    mov dx, bp
    mov ax, (CBLACK << 8) | CWHITE
    call font_run
    pop di
    pop si
    pop dx
    pop cx
    pop ax
    ret

; ---- AL -> two hex characters at ES:DI (ES = KERNEL_SEG), DI advanced -------
sd_hexb:
    push ax
    push bx
    push cx
    mov ah, al
    mov cl, 4
    shr al, cl
    mov bx, 2
.digit:
    cmp al, 10
    jb .num
    add al, 'A' - 10
    jmp short .put
.num:
    add al, '0'
.put:
    mov [es:di], al
    inc di
    mov al, ah
    and al, 0x0F
    dec bx
    jnz .digit
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; sd_paint - the whole panel, under the gfx lock
; in:       DS = KERNEL_SEG
;
; Redrawn whole every SD_PERIOD ticks rather than patched: the numbers only
; rise, a repaint is ~15 font_run rows, and this is the one kernel in the tree
; whose job is to be photographed rather than to be fast.
; -----------------------------------------------------------------------------
sd_paint:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    push es

    call gfx_lock
    mov byte [gfx_color], CBLACK
    mov ax, SD_X - 4
    mov bx, SD_Y - 4
    mov cx, SD_VALX + 7*8
    mov dx, SD_Y + SD_ROWS * SD_ROW
    cmp cx, [vid_w]             ; the LIVE geometry decides, never SCREEN_W
    jb .wok                     ; (SPEC.md 39 - this boots on all three)
    mov cx, [vid_w]
    dec cx
.wok:
    cmp dx, [vid_h]
    jb .hok
    mov dx, [vid_h]
    dec dx
.hok:
    call gfx_fill

    mov bp, SD_Y
    mov si, sd_s_hdr
    call sd_label

    add bp, SD_ROW              ; ...and WHICH BUILD, inverted so a photograph
    mov si, sd_s_arm            ; cannot lose it (see sd_s_arm)
    push ax
    mov cx, SD_X
    mov dx, bp
    mov ax, (CWHITE << 8) | CBLACK
    call font_run
    pop ax

    add bp, SD_ROW              ; --- who this machine is -------------------
    mov si, sd_s_bios
    call sd_label
    mov ax, ds                  ; "MM/DD/YY  FC" into the shared buffer: the
    mov es, ax                  ; date as found and the model as two hex
    mov di, sd_buf              ; digits, neither of them parsed (see sd_ident)
    mov si, sd_bios
    mov cx, 8
    cld
    rep movsb
    mov al, ' '
    stosb
    stosb
    mov al, [sd_model]
    call sd_hexb
    mov byte [es:di], 0
    mov si, sd_buf
    mov cx, SD_X + 5*8
    mov dx, bp
    mov ax, (CBLACK << 8) | CWHITE
    call font_run

    add bp, SD_ROW              ; --- and what it is running ----------------
    mov si, sd_s_geom
    call sd_label
    mov ax, [vid_w]
    call sd_value
    add bp, SD_ROW
    mov si, sd_s_slice
    call sd_label
    mov ax, SCH_STACK
    call sd_value

    add bp, SD_ROW + SD_ROW     ; --- the instruction, inverted -------------
    mov bl, [sd_phase]          ; ...and inside a phase, the STOP window gets
    mov bh, 0                   ; its own line: see SD_T_MSTOP
    mov ax, [ticks]
    sub ax, [sd_t0]
    cmp bl, 1
    jne .notm
    cmp ax, SD_T_MSTOP
    jb .pick
    mov bl, 4
    jmp short .pick
.notm:
    cmp bl, 2
    jne .pick
    cmp ax, SD_T_KSTOP
    jb .pick
    mov bl, 5
.pick:
    mov bh, 0
    shl bx, 1
    mov si, [bx + sd_s_phase]
    push ax
    mov cx, SD_X
    mov dx, bp
    mov ax, (CWHITE << 8) | CBLACK   ; inverse: this is the line the operator
    call font_run                    ; has to read from across a room
    pop ax

    add bp, SD_ROW + SD_ROW     ; --- the numbers ---------------------------
    mov si, sd_s_rom
    call sd_label
    mov ax, [sd_rom08]
    call sd_value
    cmp byte [sd_sat], 0
    je .nosat
    push ax                     ; a saturated reading is marked ON the row, so
    mov si, sd_s_sat            ; a photograph cannot lose it
    mov cx, SD_VALX + 4*8
    mov dx, bp
    mov ax, (CBLACK << 8) | CWHITE
    call font_run
    pop ax
.nosat:
    add bp, SD_ROW
    mov si, sd_s_q
    call sd_label
    mov ax, [sd_q]
    call sd_value
    add bp, SD_ROW
    mov si, sd_s_m
    call sd_label
    mov ax, [sd_m]
    call sd_value
    add bp, SD_ROW
    mov si, sd_s_k
    call sd_label
    mov ax, [sd_k]
    call sd_value

    add bp, SD_ROW              ; --- the floor, and then the deepest slice ---
    mov si, sd_s_flr
    call sd_label
    call sd_iwater
    call sd_value
    add bp, SD_ROW
    mov si, sd_s_now
    call sd_label
    call sd_vwater
    call sd_value
    add bp, SD_ROW
    mov si, sd_s_n
    call sd_label
    mov ax, [sd_n]
    call sd_value
%ifndef NO_MOUPRIV
    add bp, SD_ROW
    mov si, sd_s_mou
    call sd_label
    call sd_mwater
    call sd_value
%endif

    add bp, SD_ROW + SD_ROW     ; --- and every other slice ------------------
    mov si, sd_s_slots
    call sd_label
    mov bx, 1                   ; one four-digit column per slot, slot 1 first;
.slot:                          ; a slot that was never spawned reads 0
    mov ax, bx
    call sd_water
    push es
    mov cx, ds
    mov es, cx
    mov di, sd_buf
    call sd_utoa                ; DI -> the NUL it stored
    pop es
    mov ax, bx
    dec ax
    mov cx, 40                  ; 5 characters a column, 8 pixels a character
    mul cx
    add ax, SD_X
    mov cx, ax
    mov dx, bp
    add dx, SD_ROW
    mov si, sd_buf
    mov ax, (CBLACK << 8) | CWHITE
    call font_run
    inc bx
    cmp bx, MAX_TASKS
    jb .slot

    call gfx_unlock

    pop es
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; sd_task - the diagnostic task: drive the phase clock and repaint
; in:       spawned by sd_start; never returns
;
; A task and not a paint from the ISR, which is what KFZ's heartbeat does
; (SPEC.md 8.4): that one bypasses the primitives and writes the framebuffer
; itself precisely because an ISR may not take the gfx lock, and a panel this
; size is not worth writing twice. Here there is a scheduler and a lock to use,
; so it uses them.
; -----------------------------------------------------------------------------
sd_task:
    call sd_ident               ; once - the ROM is not going to change
    mov ax, [ticks]
    mov [sd_t0], ax
.loop:
    mov ax, [ticks]
    sub ax, [sd_t0]             ; wrap-safe over a run this short

    cmp byte [sd_phase], 3      ; already finished: keep repainting (the panel
    je .paint                   ; is the deliverable) and latch nothing more

    cmp ax, SD_T_QUIET
    jb .paint                   ; still in phase 0
    cmp byte [sd_phase], 0
    jne .p1
    call sd_vwater           ; --- quiet ended: latch it
    mov [sd_q], ax
    mov [sd_m], ax              ; seed the later phases, so a run that is
    mov [sd_k], ax              ; photographed early reads as "no change yet"
    mov byte [sd_phase], 1      ; rather than as a zero somebody has to explain
    jmp short .paint
.p1:
    mov ax, [ticks]
    sub ax, [sd_t0]
    cmp ax, SD_T_MOUSE
    jb .paint
    cmp byte [sd_phase], 1
    jne .p2
    call sd_vwater
    mov [sd_m], ax
    mov [sd_k], ax
    mov byte [sd_phase], 2
    jmp short .paint
.p2:
    mov ax, [ticks]
    sub ax, [sd_t0]
    cmp ax, SD_T_KEYS
    jb .paint
    call sd_vwater
    mov [sd_k], ax
    mov byte [sd_phase], 3
.paint:
    call sd_paint
    mov ax, SD_PERIOD
    call task_sleep
    jmp short .loop

; -----------------------------------------------------------------------------
; sd_start - spawn the diagnostic task.  Called from kmain, desktop up.
; -----------------------------------------------------------------------------
sd_start:
    push ax
    push bx
    push dx
    mov ax, sd_task
    xor bx, bx
    mov dx, 0x00FF
    call task_spawn
    jc .out
    mov [sd_slot], al
    mov byte [sd_armed], 1      ; ...and only now: see sd_armed
%ifndef NO_MOUPRIV
    call sd_mfill               ; the mouse ISR's own stack, sentinelled once
%endif
.out:
    pop dx
    pop bx
    pop ax
    ret

%ifndef NO_MOUPRIV
sd_mfill:
    push ax
    push cx
    push di
    push es
    mov ax, LOW_SEG
    mov es, ax
    mov di, mou_pstack
    mov cx, MOU_PSTK
    mov al, SD_SENT
    cld
    rep stosb
    pop es
    pop di
    pop cx
    pop ax
    ret
%endif

sd_s_hdr:   db "os8088 TASK STACK DIAGNOSTIC",0
; WHICH BUILD IS THIS? Three photographs came back from the field that could
; not be told apart - same panel, same machine, and no way to know which of the
; three arms the operator had booted. A measurement whose configuration cannot
; be read off the picture is a measurement somebody has to remember, and
; remembering is what the disk exists to replace.
;
; RECUT WHEN THE MOUSE FIX SHIPPED (SPEC.md 9.10): arm 1 is the default and so
; already carries it, and arm 2 is now the BEFORE picture rather than the after
; one. The pair is still the same experiment read in the same direction - arm 1
; minus arm 2 is what the mouse fix is worth on the machine in front of you.
%ifdef STK_FIX
sd_s_arm:   db "ARM 3 of 3   + STKFIX",0
%elifdef NO_MOUPRIV
sd_s_arm:   db "ARM 2 of 3   NOMOUPRIV (before)",0
%else
sd_s_arm:   db "ARM 1 of 3   as it ships",0
%endif
sd_s_bios:  db "ROM",0
sd_s_geom:  db "screen width",0
sd_s_slice: db "slice bytes",0
sd_s_rom:   db "ROM int08 on our stack",0
sd_s_q:     db "floor  quiet",0
sd_s_m:     db "floor  +mouse",0
sd_s_k:     db "floor  +keys",0
sd_s_flr:   db "FLOOR, idle  <- quote this",0
sd_s_now:   db "deepest slice (inc. panel)",0
sd_s_n:     db "chain samples taken",0
sd_s_mou:   db "mouse ISR, own stack",0
sd_s_slots: db "every slice, slot 1 up",0
sd_s_sat:   db "OVER!",0

; The four instructions, and they are the only thing on the panel a human has
; to act on. Phase 0 needs nothing done and is the reading that matters most.
sd_s_p0:    db "PHASE 1/3  QUIET - TOUCH NOTHING",0
sd_s_p1:    db "PHASE 2/3  MOVE THE MOUSE NOW",0
sd_s_p2:    db "PHASE 3/3  HOLD DOWN A KEY",0
sd_s_p3:    db "DONE - WAIT 2 MIN, THEN PHOTOGRAPH",0
sd_s_stop:  db "HANDS OFF - LATCHING THE NUMBER",0
sd_s_phase: dw sd_s_p0, sd_s_p1, sd_s_p2, sd_s_p3, sd_s_stop, sd_s_stop

section .lowbss
resb (2 - (($-$$) % 2)) % 2     ; even, so SP is even across the swap. `alignb`
                                ; spelled out: NASM refuses the macro form
                                ; against this nobits section (sch_stacks'
                                ; declaration carries the same note)
sd_scratch: resb SD_SCRATCH     ; THE PRIVATE CHAIN STACK. It must be in
                                ; .lowbss and not .bss: SS is LOW_SEG for every
                                ; task (SPEC.md 1/2.1), and the swap moves SP
                                ; alone - a scratch in the kernel's own segment
                                ; would be addressed through the wrong one
section .bss
sd_buf:     resb 16             ; fm_utoa's 6, or the date string and the model
sd_bios:    resb 12             ; the ROM's date string, 8 chars and a NUL
sd_model:   resb 1              ; F000:FFFE - FC AT, FE XT, FF PC, or a clone's
section .text

%endif

