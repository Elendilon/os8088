; =============================================================================
; os8088 - apps/realboy/rbsys.inc
;
; RealBoy's SYSTEM half: everything the core (build/realboy/rbcore.asm, from
; apps/realboy/rbgen.py) does not do inline - the event loop, interrupts,
; the PPU's timing, the timer, the I/O registers, the joypad, the link port,
; OAM DMA and the cartridge's bank switching. docs/plans/REALBOY-PLAN.md
; section 4 is the design and rbdefs.inc the layout.
;
; %included by every HOST: REALBOY.O88 and the boot-sector harness in
; tests/rbcore/. A host provides:
;
;   rb_putc     near proc: AL = a byte the game sent on its link port, or one
;               the trace prints. May be a bare RET.
;
; and calls, near, with CS the segment this file assembled into:
;
;   rb_init     AX = the view's segment, BX = the core's, CX = the ROM
;               image's, DX = the image's size in 16KB banks. Copies bank 0
;               into the view and sets the machine to the state the boot ROM
;               leaves (RealBoy has no boot ROM, plan section 3.1).
;   rb_run      AX = M-cycles to run at most. Returns AX = RBX_*: a frame is
;               ready (a VBlank began), the budget ran out, or the game hit
;               an opcode the SM83 does not have or STOP.
;
; Everything here runs on the HOST's stack. The core enters it by a far jump
; with SS:SP the Game Boy's stack; the first thing each entry does is save
; that SP and switch to the host stack rb_run left in S_HSS:S_HSP, so that
; nothing below writes under the game's SP.
; =============================================================================

RB_FAR_HI       equ 0x7FFF              ; "never": the high word of a far time
RB_LINE         equ 114                 ; M-cycles a scan line
RB_FRAME        equ 154*114             ; 17,556 M-cycles a frame
RB_VBL          equ 144*114             ; line 144's start, frame-relative
RB_HBL          equ 63                  ; mode 0 begins 63 M-cycles into a line

rb_viewseg      dw 0                    ; the view, for code on the host stack
rb_coreseg      dw 0

; =============================================================================
; rb_init - AX = view, BX = core, CX = ROM image, DX = 16KB banks in it
; =============================================================================
rb_init:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push ds
    push es
    cld
    mov [cs:rb_viewseg],ax
    mov [cs:rb_coreseg],bx
    mov es,ax
    ; the whole view to zero, then bank 0 copied into 0000-3FFF
    push cx
    xor di,di
    xor ax,ax
    mov cx,8000h
    rep stosw
    pop cx
    mov [es:S_ROMSEG],cx
    mov [es:S_NBANKS],dx
    mov ds,cx
    xor si,si
    xor di,di
    mov cx,2000h
    rep movsw
    mov ax,es
    mov ds,ax                           ; DS = view from here on
    mov [S_VIEW],ax
    ; the two flag tables: F <-> the LAHF image the core keeps in AH
    xor bx,bx
.ftab:
    xor al,al
    test bl,80h
    jz .f1
    or al,RBF_Z
.f1:
    test bl,40h
    jz .f2
    or al,RBF_N
.f2:
    test bl,20h
    jz .f3
    or al,RBF_H
.f3:
    test bl,10h
    jz .f4
    or al,RBF_C
.f4:
    mov [RB_F2AH+bx],al
    xor al,al
    test bl,RBF_Z
    jz .g1
    or al,80h
.g1:
    test bl,RBF_N
    jz .g2
    or al,40h
.g2:
    test bl,RBF_H
    jz .g3
    or al,20h
.g3:
    test bl,RBF_C
    jz .g4
    or al,10h
.g4:
    mov [RB_AH2F+bx],al
    inc bl
    jnz .ftab
    ; the far vectors the core jumps through
    mov ax,cs
    mov word [S_EVVEC],rb_ev_entry
    mov [S_EVVEC+2],ax
    mov word [S_IORVEC],rb_ior
    mov [S_IORVEC+2],ax
    mov word [S_IOWVEC],rb_iow
    mov [S_IOWVEC+2],ax
    mov word [S_MBCVEC],rb_mbc
    mov [S_MBCVEC+2],ax
    mov word [S_TRACEVEC],rb_trace
    mov [S_TRACEVEC+2],ax
    mov ax,[cs:rb_coreseg]
    mov [S_RETFAR+2],ax
    mov [S_DISP+2],ax
    mov word [S_DISP],0DD00h            ; RB_DISPATCH, slot DD's main half
    ; the cartridge: its MBC from the header, bank 1 in ROMX
    mov es,[S_ROMSEG]
    mov al,[es:0147h]
    mov ah,RBM_MBC1
    cmp al,01h
    jb .none
    cmp al,03h
    jbe .mbc
    mov ah,RBM_MBC2
    cmp al,05h
    jb .none
    cmp al,06h
    jbe .mbc
    mov ah,RBM_MBC3
    cmp al,0Fh
    jb .none
    cmp al,13h
    jbe .mbc
    mov ah,RBM_MBC5
    cmp al,19h
    jb .none
    cmp al,1Eh
    jbe .mbc
.none:
    mov ah,RBM_NONE
.mbc:
    mov [S_MBC],ah
    mov byte [S_BANK],1
    call rb_setbank
    ; the registers the DMG boot ROM leaves
    mov byte [S_AF],01h                 ; A = 01, F = B0 as AH sees it
    mov al,[RB_F2AH+0B0h]
    mov [S_AF+1],al
    mov word [S_BC],0013h
    mov word [S_DE],00D8h
    mov word [S_HL],014Dh
    mov word [S_SP],0FFFEh
    mov word [S_PC],0100h
    ; the I/O registers the boot ROM leaves
    mov byte [0FF00h],0CFh
    mov byte [0FF02h],7Eh
    mov byte [0FF0Fh],0E1h
    mov byte [0FF10h],80h
    mov byte [0FF11h],0BFh
    mov byte [0FF12h],0F3h
    mov byte [0FF14h],0BFh
    mov byte [0FF16h],3Fh
    mov byte [0FF19h],0BFh
    mov byte [0FF1Ah],7Fh
    mov byte [0FF1Bh],0FFh
    mov byte [0FF1Ch],9Fh
    mov byte [0FF1Eh],0BFh
    mov byte [0FF20h],0FFh
    mov byte [0FF23h],0BFh
    mov byte [0FF24h],77h
    mov byte [0FF25h],0F3h
    mov byte [0FF26h],0F1h
    mov byte [0FF40h],91h
    mov byte [0FF41h],85h
    mov byte [0FF47h],0FCh
    mov byte [0FF48h],0FFh
    mov byte [0FF49h],0FFh
    ; time: zero is now. The LCD is on, line 0 begins now.
    mov byte [S_LCDON],1
    mov word [S_TVBL],RB_VBL
    mov word [S_TVBL+2],0
    mov word [S_TSTAT+2],RB_FAR_HI
    mov word [S_TTIMA+2],RB_FAR_HI
    mov word [S_TSTOP+2],RB_FAR_HI
    mov word [S_TNEXT],RB_VBL
    mov word [S_BP],RB_VBL
    mov byte [S_SNAPTAG],0FFh
    mov word [S_IDLENO],0FFFFh
    pop es
    pop ds
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; =============================================================================
; rb_run - AX = budget in M-cycles. Out: AX = RBX_*.
; =============================================================================
rb_run:
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    push ds
    push es
    cld
    mov ds,[cs:rb_viewseg]
    push ax
    mov bp,[S_BP]
    call rb_now                         ; DX:AX = now
    mov [S_NOW],ax
    mov [S_NOW+2],dx
    pop cx
    add ax,cx
    adc dx,0
    mov [S_TSTOP],ax
    mov [S_TSTOP+2],dx
    mov [S_HSP],sp
    mov [S_HSS],ss
    call rb_sched                       ; TNEXT = the earliest event, BP to it
    mov [S_BP],bp
    jmp rb_resume

; rb_exit: back to rb_run's caller, from anywhere on the host stack. DS = view.
rb_exit:
    mov sp,[S_HSP]
    xor ax,ax
    xchg al,[S_EXIT]
    pop es
    pop ds
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    ret

; rb_resume: into the core with the state block's registers. DS = view.
rb_resume:
    mov ax,[S_AF]
    mov bx,[S_HL]
    mov cx,[S_BC]
    mov di,[S_DE]
    mov si,[S_PC]
    mov bp,[S_BP]
    mov dx,si
    and dh,0C0h
    cmp dh,40h
    mov dx,[S_VIEW]
    jne .v
    mov dx,[S_ROMX]
.v:
    cli
    mov ss,[S_VIEW]
    mov sp,[ss:S_SP]
    sti
    mov ds,dx
    xor dx,dx
    jmp far [ss:S_DISP]

; =============================================================================
; Entries from the core. Each arrives with SS:SP the game's stack.
; =============================================================================

; RB_TOHOST: save the game's SP and DS, switch to the host stack, DS = view.
%macro RB_TOHOST 0
    mov [ss:S_SAVDS],ds
    cli
    mov [ss:S_SP],sp
    mov sp,[ss:S_HSP]
    mov ss,[ss:S_HSS]
    sti
    mov ds,[cs:rb_viewseg]
    cld
%endmacro

; rb_ret: back into the core at S_RETFAR, the game's DS and SP restored.
; DH (an I/O read's answer) survives; DL leaves as 0.
rb_ret:
    cli
    mov ss,[cs:rb_viewseg]
    mov sp,[ss:S_SP]
    sti
    mov ds,[ss:S_SAVDS]
    xor dl,dl
    jmp far [ss:S_RETFAR]

; --- the event entry: BP < 0, HALT, a spin-wait, RETI, STOP, a bad opcode ---
rb_ev_entry:
    mov [ss:S_AF],ax
    mov [ss:S_HL],bx
    mov [ss:S_BC],cx
    mov [ss:S_DE],di
    mov [ss:S_PC],si
    mov [ss:S_BP],bp
    RB_TOHOST
    call rb_events                      ; CF = 1: leave for the host
    jc rb_exit
    jmp rb_resume

; --- an I/O register read: BX = FF00-FF7F. Answers DH. ----------------------
rb_ior:
    RB_TOHOST
    push ax
    push bx
    push cx
    push si
    push di
    push es
    call rb_ioread                      ; AL = the byte
    mov dh,al
    pop es
    pop di
    pop si
    pop cx
    pop bx
    pop ax
    jmp rb_ret

; --- an I/O register write: BX = FF00-FF7F or FFFF, [S_WVAL] = the byte -----
rb_iow:
    RB_TOHOST
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    call rb_iowrite
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    cmp byte [S_TAKEINT],0              ; IF or IE written: an interrupt now
    je rb_ret                           ;   pending is taken at once, before
    mov byte [S_TAKEINT],0              ;   the next instruction
    call rb_irqnow
    jmp rb_ret

; rb_irqnow: if an interrupt is enabled and pending, take it NOW, from inside
; an instruction's write: SI (the core's PC) is already the next
; instruction's, so it is what gets pushed. DS = view. Moves SI, SP (via
; S_SP), the core's DS (via S_SAVDS) and BP; everything else kept.
rb_irqnow:
    push ax
    push bx
    push cx
    cmp byte [S_IME],0
    je .r
    mov al,[0FFFFh]
    and al,[0FF0Fh]
    and al,1Fh
    jz .r
    mov byte [S_IME],0
    xor cl,cl
    mov ah,1
.w:
    test al,ah
    jnz .t
    shl ah,1
    inc cl
    jmp .w
.t:
    not ah
    and [0FF0Fh],ah
    mov bx,[S_SP]
    sub bx,2
    mov [S_SP],bx
    mov [bx],si
    mov al,cl
    shl al,1
    shl al,1
    shl al,1
    add al,40h
    xor ah,ah
    mov si,ax
    mov ax,[S_VIEW]
    mov [S_SAVDS],ax
    sub bp,5
.r:
    pop cx
    pop bx
    pop ax
    ret

; --- a write to the cartridge (0000-7FFF): BX = address, [S_WVAL] = byte ----
rb_mbc:
    RB_TOHOST
    mov [S_PC],si                       ; rb_setbank asks where the game runs
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    call rb_mbcwrite
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    jmp rb_ret

; --- RB_TRACE builds: one line per instruction, then dispatch ---------------
rb_trace:
    mov [ss:S_AF],ax
    mov [ss:S_HL],bx
    mov [ss:S_BC],cx
    mov [ss:S_DE],di
    mov [ss:S_PC],si
    RB_TOHOST
    push ax
    push bx
    push cx
    push si
    push di
    call rb_trline
    pop di
    pop si
    pop cx
    pop bx
    pop ax
    cli
    mov ss,[cs:rb_viewseg]
    mov sp,[ss:S_SP]
    sti
    mov ds,[ss:S_SAVDS]
    xor dx,dx
    jmp far [ss:S_DISP]                 ; the RAW dispatch, never traced
rb_trline:
    mov al,'P'
    call rb_putc
    mov ax,[S_PC]
    call rb_hex16
    mov al,' '
    call rb_putc
    mov al,[S_AF]                       ; A
    call rb_hex8
    mov bl,[S_AF+1]                     ; F, as the Game Boy holds it
    xor bh,bh
    mov al,[RB_AH2F+bx]
    call rb_hex8
    mov ax,[S_BC]
    call rb_hex16
    mov ax,[S_DE]
    call rb_hex16
    mov ax,[S_HL]
    call rb_hex16
    mov ax,[S_SP]
    call rb_hex16
    mov al,10
    jmp rb_putc
rb_hex16:
    push ax
    mov al,ah
    call rb_hex8
    pop ax
rb_hex8:
    push ax
    shr al,1
    shr al,1
    shr al,1
    shr al,1
    call .nib
    pop ax
.nib:
    push ax
    and al,0Fh
    add al,'0'
    cmp al,'9'
    jbe .p
    add al,7
.p:
    call rb_putc
    pop ax
    ret

; =============================================================================
; Time. Every time is a dword of M-cycles since rb_init.
; =============================================================================

; rb_now: DX:AX = S_TNEXT - BP (signed). BP = the core's.
rb_now:
    mov ax,[S_TNEXT]
    mov dx,[S_TNEXT+2]
    or bp,bp
    js .neg
    sub ax,bp
    sbb dx,0
    ret
.neg:
    sub ax,bp
    sbb dx,-1
    ret

; rb_force: make the core leave at its next check. BP = 0, TNEXT = now.
rb_force:
    push ax
    push dx
    call rb_now
    mov [S_TNEXT],ax
    mov [S_TNEXT+2],dx
    xor bp,bp
    pop dx
    pop ax
    ret

; rb_sched: TNEXT = the earliest pending event (never more than 0x7FFF
; M-cycles past now), BP = TNEXT - now. In: [S_NOW] = now.
rb_sched:
    mov ax,[S_NOW]
    mov dx,[S_NOW+2]
    add ax,7FFFh
    adc dx,0
    mov si,S_TVBL
    call .min
    mov si,S_TSTAT
    call .min
    mov si,S_TTIMA
    call .min
    mov si,S_TSTOP
    call .min
    mov [S_TNEXT],ax
    mov [S_TNEXT+2],dx
    sub ax,[S_NOW]
    mov bp,ax
    ret
.min:                                   ; DX:AX = min(DX:AX, [SI])
    cmp dx,[si+2]
    jb .keep
    ja .take
    cmp ax,[si]
    jbe .keep
.take:
    mov ax,[si]
    mov dx,[si+2]
.keep:
    ret

; rb_lcdpos: the PPU's position at [S_NOW]. Out: AL = LY, DX = M-cycles into
; the line. Normalises S_TFRAME to the frame holding now.
rb_lcdpos:
    push bx
.again:
    mov ax,[S_NOW]
    mov dx,[S_NOW+2]
    sub ax,[S_TFRAME]
    sbb dx,[S_TFRAME+2]
    jnz .adv                            ; a frame's worth or more behind
    cmp ax,RB_FRAME
    jb .ok
.adv:
    add word [S_TFRAME],RB_FRAME
    adc word [S_TFRAME+2],0
    jmp .again
.ok:
    xor dx,dx
    mov bx,RB_LINE
    div bx                              ; AX = line, DX = position
    pop bx
    ret

; =============================================================================
; rb_events - the core left for an event. DS = view, state block current.
; CF = 1: return to the host (S_EXIT says why); CF = 0: resume the core.
; =============================================================================
rb_events:
    inc word [S_EVCOUNT]
    mov bp,[S_BP]
    call rb_now
    mov [S_NOW],ax
    mov [S_NOW+2],dx
    cmp byte [S_EXIT],0
    jne .leave
    ; HALT or a spin-wait: nothing happens until the next event, so go there
    mov al,[S_HALT]
    or al,[S_IDLE]
    jz .due
    mov byte [S_IDLE],0
    cmp byte [S_HALT],0
    je .skip
    mov al,[0FFFFh]
    and al,[0FF0Fh]
    and al,1Fh
    jz .skip
    mov byte [S_HALT],0                 ; a pending interrupt ends HALT
    jmp .due
.skip:
    call rb_sched                       ; TNEXT = the next event, BP to it
    or bp,bp
    jle .due                            ; one is already due
    add [S_SKIPPED],bp
    adc word [S_SKIPPED+2],0
    mov ax,[S_TNEXT]
    mov dx,[S_TNEXT+2]
    mov [S_NOW],ax
    mov [S_NOW+2],dx
.due:
    ; every event whose time has come
    mov si,S_TVBL
    call .isdue
    jnc .n1
    call rb_vblank
.n1:
    mov si,S_TSTAT
    call .isdue
    jnc .n2
    call rb_statev
.n2:
    mov si,S_TTIMA
    call .isdue
    jnc .n3
    call rb_timaev
.n3:
    mov si,S_TSTOP
    call .isdue
    jnc .n4
    mov word [S_TSTOP+2],RB_FAR_HI
    cmp byte [S_EXIT],0
    jne .n4
    mov byte [S_EXIT],RBX_BUDGET
.n4:
    ; an interrupt, if one is enabled and pending
    mov al,[0FFFFh]
    and al,[0FF0Fh]
    and al,1Fh
    jz .noint
    mov byte [S_HALT],0
    cmp byte [S_IME],0
    je .noint
    mov byte [S_IME],0
    mov cl,0
    mov ah,1
.which:
    test al,ah
    jnz .take
    shl ah,1
    inc cl
    jmp .which
.take:
    not ah
    and [0FF0Fh],ah
    mov bx,[S_SP]
    sub bx,2
    mov [S_SP],bx
    mov ax,[S_PC]
    mov [bx],ax
    mov al,cl                           ; PC = 40h + 8 * the bit
    shl al,1
    shl al,1
    shl al,1
    add al,40h
    xor ah,ah
    mov [S_PC],ax
    add word [S_NOW],5
    adc word [S_NOW+2],0
.noint:
    cmp byte [S_HALT],0                 ; still halted: on to the next event
    je .sched
    cmp byte [S_EXIT],0
    jne .sched
    jmp .skip
.sched:
    call rb_sched
    mov [S_BP],bp
    cmp byte [S_EXIT],0
    jne .leave
    clc
    ret
.leave:
    call rb_sched
    mov [S_BP],bp
    stc
    ret
.isdue:                                 ; CF = 1 if [SI] <= now
    mov ax,[S_NOW]
    mov dx,[S_NOW+2]
    cmp dx,[si+2]
    ja .yes
    jb .no
    cmp ax,[si]
    jae .yes
.no:
    clc
    ret
.yes:
    stc
    ret

; rb_catchup: run every event already due at [S_NOW] that sets IF - from
; inside an instruction, so nothing here takes an interrupt or leaves. A read
; of IF sees what the hardware would; the core's own TNEXT may then point at
; an event already handled, which costs one empty event entry and no more.
rb_catchup:
    push ax
    push bx
    push dx
    push si
    mov si,S_TVBL
    call rb_events.isdue
    jnc .c1
    call rb_vblank
.c1:
    mov si,S_TSTAT
    call rb_events.isdue
    jnc .c2
    call rb_statev
.c2:
    mov si,S_TTIMA
    call rb_events.isdue
    jnc .c3
    call rb_timaev
.c3:
    pop si
    pop dx
    pop bx
    pop ax
    ret

; --- VBlank: line 144 began -------------------------------------------------
rb_vblank:
    or byte [0FF0Fh],01h
    test byte [0FF41h],10h
    jz .n
    or byte [0FF0Fh],02h
.n:
    inc word [S_FRAMES]
    mov byte [S_IDLECNT],0
    add word [S_TVBL],RB_FRAME
    adc word [S_TVBL+2],0
    cmp byte [S_EXIT],0
    jne .r
    mov byte [S_EXIT],RBX_FRAME
.r:
    ret

; --- STAT: an enabled LYC, mode 2 or mode 0 condition began -----------------
rb_statev:
    call rb_lcdpos                      ; AL = LY, DX = position
    mov ah,[0FF41h]
    or dx,dx
    jnz .h
    test ah,40h                         ; LYC
    jz .m2
    cmp al,[0FF45h]
    je .irq
.m2:
    test ah,20h                         ; mode 2, lines 0-143
    jz .r
    cmp al,144
    jb .irq
    jmp .r
.h:
    cmp dx,RB_HBL
    jne .r
    test ah,08h                         ; mode 0
    jz .r
    cmp al,144
    jae .r
.irq:
    or byte [0FF0Fh],02h
.r:
    jmp rb_statsch

; rb_statsch: S_TSTAT = the first STAT condition AFTER now.
rb_statsch:
    mov word [S_TSTAT+2],RB_FAR_HI
    cmp byte [S_LCDON],0
    je .r
    mov ah,[0FF41h]
    test ah,68h
    jz .r
    call rb_lcdpos                      ; AL = LY, DX = position
    mov bl,al                           ; BL = line, DX = position, CX = lines
    xor cx,cx                           ;   from now (0 = this one)
.line:
    cmp cx,155
    ja .r
    ; candidates in line BL, at frame time CX*114 - position + offset
    or cx,cx
    jnz .start
    ; this line: only what is still ahead of the position
    cmp bl,144
    jae .next
    test ah,08h
    jz .next
    cmp dx,RB_HBL
    jae .next
    mov si,RB_HBL
    jmp .found
.start:
    test ah,40h
    jz .s2
    cmp bl,[0FF45h]
    je .at0
.s2:
    cmp bl,144
    jae .next
    test ah,20h
    jnz .at0
    test ah,08h
    jz .next
    mov si,RB_HBL
    jmp .found
.at0:
    xor si,si
.found:                                 ; time = now - DX + CX*114 + SI
    push dx
    mov ax,RB_LINE
    mul cx
    add ax,si
    pop dx
    sub ax,dx
    add ax,[S_NOW]
    mov dx,[S_NOW+2]
    adc dx,0
    mov [S_TSTAT],ax
    mov [S_TSTAT+2],dx
.r:
    ret
.next:
    inc cx
    inc bl
    cmp bl,154
    jb .line
    xor bl,bl
    jmp .line

; --- TIMA overflowed ---------------------------------------------------------
rb_timaev:
    or byte [0FF0Fh],04h
    mov al,[0FF06h]                     ; TIMA = TMA, from the overflow on
    mov [S_TIMA0],al
    mov ax,[S_TTIMA]
    mov dx,[S_TTIMA+2]
    mov [S_TTBASE],ax
    mov [S_TTBASE+2],dx
    jmp rb_timasch

; rb_tshift: CL = log2 of M-cycles per TIMA tick for TAC
rb_tshift:
    mov cl,[0FF07h]
    and cl,3
    jnz .n
    mov cl,8                            ; 4096 Hz: 256 M-cycles
    ret
.n:
    shl cl,1                            ; 01: 2, 10: 4, 11: 6
    ret

; TIMA ticks off the SAME free-running counter DIV is the top of: once every
; 2^shift M-cycles of (t - S_TDIV), whenever TIMA was written. So with
; P(t) = (t - TDIV) >> shift,  TIMA(now) = TIMA0 + P(now) - P(TTBASE).

; rb_phase: DX:AX = P(DX:AX). CL = shift. Kept: everything else.
rb_phase:
    push cx
    sub ax,[S_TDIV]
    sbb dx,[S_TDIV+2]
.sh:
    shr dx,1
    rcr ax,1
    dec cl
    jnz .sh
    pop cx
    ret

; rb_timasch: S_TTIMA = TDIV + (P(TTBASE) + 256 - TIMA0) << shift, or never
rb_timasch:
    mov word [S_TTIMA+2],RB_FAR_HI
    test byte [0FF07h],04h
    jz .r
    call rb_tshift
    mov ax,[S_TTBASE]
    mov dx,[S_TTBASE+2]
    call rb_phase
    add ax,256
    adc dx,0
    sub al,[S_TIMA0]
    sbb ah,0
    sbb dx,0
.sh:
    shl ax,1
    rcl dx,1
    dec cl
    jnz .sh
    add ax,[S_TDIV]
    adc dx,[S_TDIV+2]
    mov [S_TTIMA],ax
    mov [S_TTIMA+2],dx
.r:
    ret

; rb_tima: AL = TIMA at [S_NOW], the timer running
rb_tima:
    push bx
    push cx
    push dx
    call rb_tshift
    mov ax,[S_TTBASE]
    mov dx,[S_TTBASE+2]
    call rb_phase
    mov bx,ax
    mov ax,[S_NOW]
    mov dx,[S_NOW+2]
    call rb_phase
    sub ax,bx
    add al,[S_TIMA0]
    pop dx
    pop cx
    pop bx
    ret

; rb_tsettle: TIMA0 = TIMA now, TTBASE = now - before the rate or the
; counter under it changes
rb_tsettle:
    push ax
    test byte [0FF07h],04h
    jz .s
    call rb_tima
    mov [0FF05h],al
.s:
    mov al,[0FF05h]
    mov [S_TIMA0],al
    mov ax,[S_NOW]
    mov [S_TTBASE],ax
    mov ax,[S_NOW+2]
    mov [S_TTBASE+2],ax
    pop ax
    ret

; =============================================================================
; I/O registers. BX = the address; DS = view; BP = the core's.
; =============================================================================
rb_ioread:
    call rb_now
    mov [S_NOW],ax
    mov [S_NOW+2],dx
    cmp bl,44h
    je .ly
    cmp bl,41h
    je .stat
    cmp bl,00h
    je .joy
    cmp bl,04h
    je .div
    cmp bl,05h
    je .tima
    cmp bl,0Fh
    jne .plain
    call rb_catchup                     ; IF: every event already due, first
.plain:
    mov al,[bx]
    ret
.ly:
    xor al,al
    cmp byte [S_LCDON],0
    je .r
    call rb_lcdpos
.r:
    ret
.stat:
    mov al,[0FF41h]
    and al,78h
    or al,80h
    cmp byte [S_LCDON],0
    je .r
    mov ah,al
    call rb_lcdpos                      ; AL = LY, DX = position
    cmp al,[0FF45h]
    jne .s0
    or ah,04h
.s0:
    cmp al,144
    jb .s1
    or ah,1                             ; mode 1
    jmp .s9
.s1:
    cmp dx,20
    jae .s2
    or ah,2                             ; mode 2
    jmp .s9
.s2:
    cmp dx,RB_HBL
    jae .s9                             ; mode 0
    or ah,3                             ; mode 3
.s9:
    mov al,ah
    ret
.joy:                                   ; 0 = pressed AND selected
    mov ah,[0FF00h]
    mov al,0Fh
    mov dl,[S_JOY]
    test ah,10h                         ; P14 low: the directions
    jnz .j1
    mov dh,dl
    not dh
    and al,dh
.j1:
    test ah,20h                         ; P15 low: the buttons
    jnz .j2
    mov dh,dl
    shr dh,1
    shr dh,1
    shr dh,1
    shr dh,1
    not dh
    and al,dh
.j2:
    and al,0Fh
    and ah,30h
    or al,ah
    or al,0C0h
    ret
.div:
    mov ax,[S_NOW]
    mov dx,[S_NOW+2]
    sub ax,[S_TDIV]
    sbb dx,[S_TDIV+2]
    mov cl,6
    shr ax,cl
    mov cl,10
    shl dx,cl
    or ax,dx
    ret
.tima:
    test byte [0FF07h],04h
    jz .tstat
    call rb_tima
    ret
.tstat:
    mov al,[0FF05h]
    ret

rb_iowrite:
    call rb_now
    mov [S_NOW],ax
    mov [S_NOW+2],dx
    mov al,[S_WVAL]
    cmp bl,0FFh
    je .ie
    cmp bl,40h
    jae .lcd
    cmp bl,0Fh
    je .if
    cmp bl,00h
    je .joy
    cmp bl,02h
    je .sc
    cmp bl,04h
    je .div
    cmp bl,05h
    je .tima
    cmp bl,07h
    je .tac
.plain:
    mov [bx],al
    ret
.ie:
    mov [bx],al
    mov byte [S_TAKEINT],1
    jmp rb_force
.if:
    or al,0E0h
    mov [bx],al
    mov byte [S_TAKEINT],1
    jmp rb_force
.joy:
    and al,30h
    or al,0C0h
    mov [bx],al
    ret
.sc:
    mov [bx],al
    and al,81h
    cmp al,81h
    jne .r
    mov al,[0FF01h]                     ; the game sent a byte; nobody is on
    push ax                             ;   the other end, so it reads FF back
    mov bl,[S_SERN]
    xor bh,bh
    mov [RB_SERBUF+bx],al
    inc byte [S_SERN]
    jnz .sc1
    dec byte [S_SERN]
.sc1:
    pop ax
    call rb_putc
    mov byte [0FF01h],0FFh
    and byte [0FF02h],7Fh
    or byte [0FF0Fh],08h
    jmp rb_force
.div:
    call rb_tsettle
    mov ax,[S_NOW]
    mov dx,[S_NOW+2]
    mov [S_TDIV],ax
    mov [S_TDIV+2],dx
    call rb_timasch
    jmp rb_force
.r:
    ret
.tima:
    mov [S_TIMA0],al
    mov [bx],al
    mov ax,[S_NOW]
    mov dx,[S_NOW+2]
    mov [S_TTBASE],ax
    mov [S_TTBASE+2],dx
    call rb_timasch
    jmp rb_force
.tac:
    call rb_tsettle                     ; TIMA under the old rate, first
    or al,0F8h
    mov [0FF07h],al
    call rb_timasch
    jmp rb_force
.lcd:
    cmp bl,4Ch
    jae .plain
    cmp bl,46h
    je .dma
    cmp bl,44h
    je .r                               ; LY is read-only
    cmp bl,41h
    je .stat
    cmp bl,45h
    je .lyc
    call rb_rlog                        ; a raster write, if mid-frame
    cmp bl,40h
    jne .plain
    ; LCDC: the PPU starts or stops with bit 7
    mov ah,[0FF40h]
    mov [bx],al
    xor ah,al
    test ah,80h
    jz .r
    test al,80h
    jz .off
    mov byte [S_LCDON],1
    mov ax,[S_NOW]
    mov dx,[S_NOW+2]
    mov [S_TFRAME],ax
    mov [S_TFRAME+2],dx
    add ax,RB_VBL
    adc dx,0
    mov [S_TVBL],ax
    mov [S_TVBL+2],dx
    call rb_statsch
    jmp rb_force
.off:
    mov byte [S_LCDON],0
    mov word [S_TVBL+2],RB_FAR_HI
    mov word [S_TSTAT+2],RB_FAR_HI
    jmp rb_force
.stat:
    and al,78h
    mov ah,[0FF41h]
    and ah,07h
    or al,ah
    mov [bx],al
    call rb_statsch
    jmp rb_force
.lyc:
    mov [bx],al
    call rb_statsch
    jmp rb_force
.dma:
    mov [bx],al
    push ds
    mov es,[S_VIEW]
    mov di,0FE00h
    mov ah,al
    xor al,al
    mov si,ax                           ; SI = source
    cmp ah,40h
    jb .dv
    cmp ah,80h
    jae .dv
    mov ds,[S_ROMX]
.dv:
    mov cx,160
    rep movsb
    pop ds
    ret

; rb_rlog: a write to LCDC/SCY/SCX/BGP/OBP0/OBP1/WY/WX, AL = the value, BL =
; the register. If it lands inside the visible lines of a frame, log it with
; the line it takes effect on (plan section 4.4), so the renderer can draw
; the frame in bands; the first such write of a frame first snapshots all
; eight as the frame began.
rb_rlog:
    push ax
    push bx
    push cx
    push dx
    push si
    mov cl,al                           ; CL = the value, CH = the register
    mov ch,bl
    cmp byte [S_LCDON],0
    je .done
    call rb_lcdpos                      ; AL = LY, DX = position
    cmp dx,RB_HBL
    jb .cur
    inc al                              ; written in HBlank: from the next line
.cur:
    cmp al,144
    jae .done
    mov dl,al                           ; DL = the line
    mov al,[S_FRAMES]
    cmp al,[S_SNAPTAG]
    je .app
    mov [S_SNAPTAG],al                  ; this frame's first: the snapshot
    mov byte [S_RLOGN],0
    mov al,[0FF40h]
    mov [RB_SNAP+0],al
    mov ax,[0FF42h]
    mov [RB_SNAP+1],ax
    mov ax,[0FF47h]
    mov [RB_SNAP+3],ax
    mov al,[0FF49h]
    mov [RB_SNAP+5],al
    mov ax,[0FF4Ah]
    mov [RB_SNAP+6],ax
.app:
    mov al,[S_RLOGN]
    cmp al,RB_RLOG_MAX
    jae .done
    inc byte [S_RLOGN]
    xor ah,ah
    shl ax,1
    shl ax,1
    mov si,ax
    mov [RB_RLOG+si],dl                 ; line
    mov [RB_RLOG+si+1],ch               ; register
    mov [RB_RLOG+si+2],cl               ; value
.done:
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; =============================================================================
; The cartridge. BX = 0000-7FFF, [S_WVAL] = the byte.
; =============================================================================
rb_mbcwrite:
    mov al,[S_WVAL]
    mov ah,[S_MBC]
    cmp ah,RBM_NONE
    je .r
    cmp bh,20h
    jb .ramen
    cmp bh,40h
    jb .rom
    cmp bh,60h
    jb .hi
    cmp ah,RBM_MBC1
    jne .r
    and al,1
    mov [S_MBCMODE],al
.r:
    ret
.ramen:
    cmp ah,RBM_MBC2
    jne .re
    test bh,01h                         ; MBC2: address bit 8 picks the bank
    jnz .rom2
.re:
    and al,0Fh
    cmp al,0Ah
    mov al,0
    jne .re1
    inc al
.re1:
    mov [S_RAMEN],al
    ret
.rom:
    cmp ah,RBM_MBC2
    je .rom2b
    cmp ah,RBM_MBC5
    je .rom5
    cmp ah,RBM_MBC3
    je .rom3
    and al,1Fh                          ; MBC1: five bits, 0 means 1
    jnz .r1
    inc al
.r1:
    mov [S_BANK],al
    jmp rb_setbank
.rom2:
.rom2b:
    and al,0Fh
    jnz .r2
    inc al
.r2:
    mov [S_BANK],al
    jmp rb_setbank
.rom3:
    and al,7Fh
    jnz .r3
    inc al
.r3:
    mov [S_BANK],al
    jmp rb_setbank
.rom5:
    cmp bh,30h
    jae .rom5h
    mov [S_BANK],al
    jmp rb_setbank
.rom5h:
    and al,1
    mov [S_BANKHI],al
    jmp rb_setbank
.hi:
    cmp ah,RBM_MBC1
    jne .ram
    and al,3                            ; MBC1: bank bits 5-6 (mode 0)
    mov [S_BANKHI],al
    jmp rb_setbank
.ram:
    mov [S_RAMBANK],al
    ret

; rb_setbank: S_ROMX for S_BANK/S_BANKHI, masked to the ROM's size. If the
; game is executing from 4000-7FFF the core's DS (S_SAVDS) moves with it.
rb_setbank:
    push ax
    push dx
    mov al,[S_BANK]
    mov ah,[S_BANKHI]
    cmp byte [S_MBC],RBM_MBC1
    jne .m5
    mov dl,ah                           ; MBC1: hi bits are bank bits 5-6
    mov ah,0
    shl dl,1
    shl dl,1
    shl dl,1
    shl dl,1
    shl dl,1
    or al,dl
    jmp .mask
.m5:
    cmp byte [S_MBC],RBM_MBC5
    je .mask
    xor ah,ah
.mask:
    mov dx,[S_NBANKS]
    dec dx
    and ax,dx
    mov dx,ax                           ; ROMX = ROMSEG + bank*400h - 400h
    mov ax,0400h
    mul dx
    add ax,[S_ROMSEG]
    sub ax,0400h
    mov [S_ROMX],ax
    mov dx,[S_PC]
    and dh,0C0h
    cmp dh,40h
    jne .r
    mov [S_SAVDS],ax
.r:
    pop dx
    pop ax
    ret
