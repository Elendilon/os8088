; =============================================================================
; kernel/mega.inc - kern_mega's protected mode (docs/plans/KERN-MEGA-PLAN.md)
;
; kern_big boots in real mode exactly as it does on every other machine, and
; at the end of kmain, with the desktop painted and before task 0 becomes the
; UI task, mega_enter switches the CPU into 286 PROTECTED MODE and leaves it
; there. This file is that switch and everything protected mode needs that
; real mode got from the ROM. It is wave M1 of KERN-MEGA-PLAN 10.
;
; THE MAP (KERN-MEGA-PLAN 3). Every segment value the kernel and its packages
; already hold keeps meaning what it means:
;
;   GDT entry i, for every i from 8 to 8191, is DATA with base i x 128 and a
;   64KB limit, so selector N is segment N whenever N is a multiple of 8. That
;   is every heap base (all of them are multiples of 32 paragraphs), LOW_SEG,
;   0x0040, 0xA000, 0xB000, 0xB800 and 0xF000.
;
;   The EXCEPTIONS are the kernel's two code segments: entry 12 is KERNEL_SEG
;   (0x0060) as READABLE CODE, because every package far-calls 0x0060:cell,
;   and entry COLD_SEG/8 is `.cold` as code. Entries 1-7 have bases inside the
;   IVT, which nothing loads as a segment, so they carry the kernel's own
;   selectors (MEGA_SEL_*).
;
;   LDT entry i, for i from 0 to 2047, is READABLE CODE with base i x 512, so
;   any 512-aligned conventional segment S has a code alias (S >> 2) | 4 - a
;   package, a driver or a module is far-called through that. Its TI bit is
;   set, so it can never equal an identity selector.
;
; Both tables and the IDT live above 1MB (MEGA_*_LIN), which is why this is
; kern_big's and why xm_sniff keeps XMEM.DRV out on this build: kern_mega
; owns the memory up there.
;
; THE ROM (KERN-MEGA-PLAN 2.2). A 286 cannot leave protected mode except by
; resetting the CPU, so nothing on a per-event path may go through the BIOS:
;
;   * IRQ0's ROM half (the tick at 40:6C, the floppy motor-off count and the
;     EOI) is mega_t08, and sch_isr reaches it through the [sch_old08] chain
;     it already makes - the ISR itself is unchanged.
;   * IRQ1's ROM half (scancode to the BIOS buffer at 40:1E) is mega_k09, the
;     target of kbm_isr's existing `jmp far [cs:kbm_old9]`.
;   * int 16h is mega_i16, a native reader of that same buffer, so every
;     caller of int 16h - the kernel's and a package's - is unchanged.
;   * every other int 10h-1Fh is REFLECTED (mega_svc): the CPU goes back to
;     real mode, the BIOS's own vectors for the tick and the keyboard are in
;     the IVT, every IRQ that is not the BIOS's own is masked, the call is
;     made, and the CPU comes back. That is the disk, the video mode sets and
;     the equipment queries.
;
; TWO WAYS BACK TO REAL MODE. A 386 clears CR0.PE. A 286 cannot - lmsw only
; sets it - so it resets the CPU: CMOS shutdown code 0Ah sends the BIOS
; straight to 40:67, which mega_r286 owns, with RAM, A20 and every device as
; they were. QEMU CANNOT TEST THE 286's ARM: its CPU is a 386 (so it takes the
; other one), and its reset resets the whole machine, the VGA with it. That
; arm is the Victory 286's to check.
;
; THE FAULT REPORTER. Every exception and every software interrupt nobody
; handles ends in mega_fault, which writes the vector, the error code, CS:IP,
; SS:SP and the registers to QEMU's debug console (port E9h) and stops. In
; real mode a wild write corrupts something; here it is a #GP at the
; instruction that did it, and that is only worth having if it is reported.
; =============================================================================

%ifdef KERN_MEGA

MEGA_GDT_LIN    equ 0x110000        ; above the HMA, which KERN-MEGA-PLAN 2.7
MEGA_LDT_LIN    equ 0x120000        ; keeps free for the DOS box's real-mode
MEGA_IDT_LIN    equ 0x124000        ; half
MEGA_GDT_N      equ 8192            ; the CPU's maximum: 64KB
MEGA_LDT_N      equ 2048            ; 1MB / 512 bytes: 16KB

MEGA_SEL_LOW0   equ 0x08            ; data, base 0: the IVT and the BDA, for
                                    ; code that used ES = 0 (selector 0 is NULL)
MEGA_SEL_KDATA  equ 0x10            ; data, base KERNEL_SEG x 16: the kernel's
                                    ; DS. 0x0060 is CODE (above), so a store
                                    ; through it would fault
MEGA_SEL_LDT    equ 0x18            ; the LDT's own descriptor
MEGA_SEL_WIN    equ 0x20            ; data, a WINDOW whose base is moved to
                                    ; reach a table above 1MB
MEGA_SEL_ODD    equ 0x30            ; data, base moved per use: a selector for
                                    ; a segment OFF the 8-paragraph grid
                                    ; (mega_oddsegf)
MEGA_SEL_BCODE  equ 0x28            ; code, base KERNEL_SEG x 16: the
                                    ; BOOTSTRAP's CS between the first lmsw
                                    ; and the far jump into the real tables,
                                    ; and after that the CS the ROM-half
                                    ; chains (mega_t08, mega_k09) are entered
                                    ; through

MEGA_PIC_BASE   equ 0x20            ; IRQ0-7 in protected mode. 08h-0Fh are
                                    ; CPU exceptions there (8 is the double
                                    ; fault), so the master 8259 moves
MEGA_BDA        equ 0x0040          ; an identity selector, and the BDA

%if (KERNEL_SEG % 8) || (LOW_SEG % 8) || (COLD_SEG % 8)
 %error "kern_mega's identity map needs KERNEL_SEG, LOW_SEG and COLD_SEG on a multiple of 8 paragraphs (KERN-MEGA-PLAN 3.1)"
%endif
%if (COLD_SEG >> 3) == (KERNEL_SEG >> 3)
 %error "COLD_SEG and KERNEL_SEG share a GDT entry"
%endif

section .text
cpu 286

; ---- state, in .text: written only while DS is the kernel's -----------------
                                    ; k_dsel - the kernel's data segment for
                                    ; KDS/KES - lives beside the API table in
                                    ; kernel.asm (its note says why)
mega_on     db 0                    ; 1 = the CPU is in protected mode
mega_extkb  dw 0                    ; xm_sniff's int 15h AH=88h answer
mega_bgdt:                          ; THE BOOTSTRAP GDT, six entries. Entry 0
    dw 6*8 - 1                      ; doubles as lgdt's pseudo-descriptor,
    dw 0, 0                         ; which the CPU never reads as an entry
    dw 0                            ; (the base is filled in at run time)
    dw 0x04FF, 0x0000               ; 0x08 LOW0: data, base 0 - the IVT and
                                    ; the BDA and NOT ONE BYTE MORE, so a store
                                    ; meant for the kernel that arrives with a
                                    ; base of 0 faults instead of landing on
                                    ; the API table at 0x600
    db 0x00, 0x92
    dw 0
    dw 0xFFFF, KERNEL_SEG << 4      ; 0x10 KDATA: data, base 0x600
    db (KERNEL_SEG >> 12), 0x92
    dw 0
    dw 0, 0, 0, 0                   ; 0x18 (the LDT, in the real GDT only)
mega_bwin:
    dw 0xFFFF, MEGA_GDT_LIN & 0xFFFF ; 0x20 WIN: data, base moved per table
    db MEGA_GDT_LIN >> 16, 0x92
    dw 0
    dw 0xFFFF, KERNEL_SEG << 4      ; 0x28 BCODE: code, base 0x600
    db (KERNEL_SEG >> 12), 0x9A
    dw 0
mega_gdtr   dw MEGA_GDT_N*8 - 1     ; the real tables
            dw MEGA_GDT_LIN & 0xFFFF, MEGA_GDT_LIN >> 16
mega_idtr   dw 256*8 - 1
            dw MEGA_IDT_LIN & 0xFFFF, MEGA_IDT_LIN >> 16
mega_rmidtr dw 0x03FF               ; real mode's: the IVT
            dw 0, 0
mega_nullidt dw 0                   ; the 286's reset: an IDT that holds nothing
            dw 0, 0
mega_rss    dw 0                    ; the reflection's stack, across a 286 reset
mega_rsp    dw 0
mega_old08  dd 0                    ; the BIOS's own int 08h and int 09h, put
mega_old09  dd 0                    ; back in the IVT for every reflection
mega_ses    dw 0                    ; mega_svc's: ES and DS as the caller held
mega_sds    dw 0                    ; them, as the BIOS was given them, the
mega_res    dw 0                    ; vector, the tick it started on and the
mega_rds    dw 0                    ; IMRs it masked
mega_t0     dw 0
mega_rv     db 0
mega_imr1   db 0
mega_imr2   db 0

; -----------------------------------------------------------------------------
; mega_enter - switch to protected mode (KERN-MEGA-PLAN 2.1)
;
; in:       real mode, DS = ES = KERNEL_SEG, SS = LOW_SEG; called from kmain
;           immediately before `jmp ui_task`
; out:      protected mode with DS = ES = MEGA_SEL_KDATA, or - on a CPU or a
;           machine M1 cannot drive - real mode exactly as it came in. Every
;           register but AX, CX, DX, SI, DI and the segment registers kept
; -----------------------------------------------------------------------------
mega_enter:
    cmp byte [cpu_tier], CPU_286
    jae .cpu
    mov si, mega_m86                ; an 8088 or 8086: no protected mode at all
    mov dx, mega_t86
    jmp short .refuse
.cpu:
    cmp word [mega_extkb], 192      ; the tables want 1MB + 64KB .. + 82KB
    jae .mem
    mov si, mega_mmem
    mov dx, mega_tmem
    jmp short .refuse
.mem:
    call mega_tasks_ok              ; nothing suspended in real mode that the
    jnc .tasks                      ; switch cannot convert (mega_tasks_ok)
    mov si, mega_mtask
    mov dx, mega_ttask
    jmp short .refuse
.tasks:
    call mega_a20
    jnc .a20
    mov si, mega_ma20
    mov dx, mega_ta20
.refuse:                            ; ...and every refusal says so on the GLASS
    call mega_say                   ; as well as the debug port: a field run
    push es                         ; that stays in real mode must not look
    push ds                         ; like one that never tried
    pop es
    mov si, dx
    mov cx, 146
    call toast_show
    pop es
    ret
.a20:
    cli
    in al, 0x70                     ; NMI off across the switch: a real-mode
    or al, 0x80                     ; IVT is not an IDT
    out 0x70, al

    les ax, [sch_old08]             ; the BIOS's own handlers, kept for the
    mov [mega_old08], ax            ; reflection's IVT...
    mov [mega_old08+2], es
    les ax, [kbm_old9]
    mov [mega_old09], ax
    mov [mega_old09+2], es
    push ds
    pop es

    ; --- the bootstrap: protected mode on a six-entry GDT ---------------------
    mov ax, ds                      ; lgdt takes a LINEAR base
    mov dx, ax
    shl ax, 4
    shr dx, 12
    add ax, mega_bgdt
    adc dx, 0
    mov [mega_bgdt+2], ax
    mov [mega_bgdt+4], dl
    lgdt [mega_bgdt]
    smsw ax
    or al, 1
    lmsw ax
    db 0xEA                         ; jmp far MEGA_SEL_BCODE:.boot
    dw .boot, MEGA_SEL_BCODE
.boot:
    mov ax, MEGA_SEL_KDATA
    mov ds, ax
    mov ax, MEGA_SEL_WIN
    mov es, ax
    cld

    ; --- the GDT, through WIN at MEGA_GDT_LIN ----------------------------------
    xor di, di
    xor bx, bx                      ; BX = the entry
.gdt:
    cmp bx, 8
    jb .gspecial
    mov ax, 0xFFFF                  ; IDENTITY: base BX x 128
    stosw
    mov ax, bx
    shl ax, 7
    stosw
    mov ax, bx
    shr ax, 9                       ; base 23:16 (BX < 8192, so < 16)
    mov ah, 0x92
    cmp bx, KERNEL_SEG >> 3
    je .gcode
    cmp bx, COLD_SEG >> 3
    jne .gput
.gcode:
    mov ah, 0x9A                    ; ...but the kernel's code is CODE
.gput:
    stosw
    xor ax, ax
    stosw
    jmp short .gnext
.gspecial:                          ; entries 0-7: the bootstrap's own, plus
    mov si, bx                      ; the LDT's
    shl si, 3
    add si, mega_bgdt
    cmp bx, MEGA_SEL_LDT >> 3
    jne .gcopy
    mov si, mega_ldtd
.gcopy:
    or bx, bx
    jz .gz
    cmp bx, 6                       ; the bootstrap has six; 6 and 7 are spare
    jb .gmov
.gz:
    mov si, mega_zero8
.gmov:
    movsw
    movsw
    movsw
    movsw
.gnext:
    inc bx
    cmp bx, MEGA_GDT_N
    jb .gdt

    ; --- the LDT and the IDT, through WIN moved to MEGA_LDT_LIN ---------------
    mov word [mega_bwin+2], MEGA_LDT_LIN & 0xFFFF
    mov byte [mega_bwin+4], MEGA_LDT_LIN >> 16
    mov ax, MEGA_SEL_WIN            ; reload ES: the cache holds the old base
    mov es, ax
    xor di, di
    xor bx, bx
.ldt:
    mov ax, 0xFFFF                  ; CODE: base BX x 512
    stosw
    mov ax, bx
    shl ax, 9
    stosw
    mov ax, bx
    shr ax, 7
    mov ah, 0x9A
    stosw
    xor ax, ax
    stosw
    inc bx
    cmp bx, MEGA_LDT_N
    jb .ldt

    mov di, MEGA_IDT_LIN - MEGA_LDT_LIN
    call mega_idt_build             ; ES:DI = the IDT, 256 gates

    ; --- the real tables -------------------------------------------------------
    lgdt [mega_gdtr]
    lidt [mega_idtr]
    mov ax, MEGA_SEL_LDT
    lldt ax
    db 0xEA                         ; jmp far KERNEL_SEG:.pm - CS is 0x0060
    dw .pm, KERNEL_SEG              ; again, now as GDT entry 12
.pm:
    mov ax, MEGA_SEL_KDATA
    mov ds, ax
    mov es, ax
    mov ax, ss                      ; LOW_SEG, an identity selector
    mov ss, ax
    mov word [k_dsel], MEGA_SEL_KDATA
    mov byte [mega_on], 1
    mov byte [ss:mega_pm], 1        ; ...and .cold's copy of the same fact
    mov word [k_seg0], MEGA_SEL_LOW0 ; low memory's selector (MEGA_SEG0)
    mov word [ss:mega_seg0], MEGA_SEL_LOW0
    call mega_frames_fix
    call mega_mods_fix

    ; --- the ROM's halves, in the chains the ISRs already make ---------------
    mov word [sch_old08], mega_t08  ; THROUGH MEGA_SEL_BCODE, not 0x0060:
    mov word [sch_old08+2], MEGA_SEL_BCODE ; the same code at the same base,
    mov word [kbm_old9], mega_k09   ; under a different number - kbm_isr
    mov word [kbm_old9+2], MEGA_SEL_BCODE ; refuses to chain to its OWN CS
                                    ; (the `.selfchain` guard) and would
                                    ; swallow every key

    ; --- the IVT keeps the BIOS's own tick and keyboard, for a reflection ----
    mov ax, MEGA_SEL_LOW0
    mov es, ax
    mov ax, [mega_old08]
    mov [es:0x08*4], ax
    mov ax, [mega_old08+2]
    mov [es:0x08*4+2], ax
    mov ax, [mega_old09]
    mov [es:0x09*4], ax
    mov ax, [mega_old09+2]
    mov [es:0x09*4+2], ax
    push ds                         ; ...and a COPY of IVT 08h-0Fh at 20h-27h:
    push cx                         ; the 8259 stays at its protected-mode base
    push es                         ; through every reflection (mega_svc), so
    pop ds                          ; an IRQ the BIOS takes in real mode comes
    mov si, 0x08*4                  ; in on 20h-27h. Those are DOS's vectors,
    mov di, MEGA_PIC_BASE*4         ; which nothing here has
    mov cx, 16
    cld
    rep movsw
    pop cx
    pop ds
    push ds
    pop es

    call mega_pic_pm                ; IRQ0-7 to 20h-27h
    in al, 0x70                     ; NMI back on
    and al, 0x7F
    out 0x70, al
    sti
    mov si, mega_mon
    call mega_say
    push es                         ; ...and on the GLASS, for a field machine
    push ds                         ; with no debug port: the menu bar says it
    pop es                          ; for a few seconds (toast_show only
    mov si, mega_mtoast             ; stages; the UI task's first idle pass
    cmp byte [cpu_tier], CPU_386    ; ...naming the way BACK it will use,
    jb .t286                        ; which is the thing a field run is for
    mov si, mega_mtoast3
.t286:
    mov cx, 146                     ; draws it), for eight seconds: long enough
                                    ; to photograph
    call toast_show
    pop es
    ret

; -----------------------------------------------------------------------------
; mega_idt_build - the IDT, from the IVT as the boot left it
;
; in:       protected mode, DS = KDATA, ES:DI = where the 256 gates go
; out:      ES:DI past them. Clobbers AX, BX, CX, DX, SI
;
; Exceptions 00h-0Fh get the fault reporter; 10h-1Fh are the BIOS's software
; services; 20h-27h are IRQ0-7, taken from IVT 08h-0Fh; everything else is
; taken from the IVT entry of the same number. An IVT entry whose segment is
; the kernel's becomes a gate to the same offset in the same segment (0x0060
; or COLD_SEG are code selectors); a 512-aligned heap segment becomes its LDT
; code alias; anything else - the ROM - becomes the EOI stub for an IRQ and
; the fault reporter for a software interrupt, which nothing here should make.
; -----------------------------------------------------------------------------
mega_idt_build:
    xor bx, bx                      ; BL = the vector
.v:
    mov ax, bx
    cmp al, 0x10
    jae .notx
    mov dx, ax                      ; an EXCEPTION: stub BX
    shl dx, 3                       ; (mega_xs is 8 bytes a stub)
    add dx, mega_xs
    mov cx, KERNEL_SEG
    jmp .put
.notx:
    cmp al, 0x20
    jae .notsvc
    mov dx, ax                      ; a BIOS SERVICE
    sub dx, 0x10
    shl dx, 3
    add dx, mega_ss
    mov cx, KERNEL_SEG
    cmp al, 0x16
    jne .put
    mov dx, mega_i16                ; ...the keyboard is native
    jmp .put
.notsvc:
    mov si, ax                      ; IVT slot to translate
    cmp al, 0x28
    jae .ivt
    sub si, MEGA_PIC_BASE - 8       ; 20h-27h are IRQ0-7: IVT 08h-0Fh
.ivt:
    push es
    push ax
    mov ax, MEGA_SEL_LOW0
    mov es, ax
    shl si, 2
    mov dx, [es:si]                 ; DX = offset
    mov cx, [es:si+2]               ; CX = segment
    pop ax
    pop es
    cmp cx, KERNEL_SEG
    je .put
    cmp cx, COLD_SEG
    je .put
    cmp cx, 0xA000                  ; the ROM and the option ROMs
    jae .rom
    test cx, 31
    jnz .rom
    shr cx, 2                       ; a heap image: its LDT code alias
    or cx, 4
    jmp .put
.rom:
    mov cx, KERNEL_SEG
    mov dx, mega_unh                ; a software interrupt: nobody's
    cmp al, 0x28
    jb .irqm
    cmp al, 0x70
    jb .put
    cmp al, 0x78
    jae .put
    mov dx, mega_eoi2               ; IRQ8-15 the ROM owned
    jmp .put
.irqm:
    mov dx, mega_eoi1               ; IRQ0-7 the ROM owned
.put:
    mov ax, dx                      ; an INTERRUPT gate (IF off), DPL 0
    stosw
    mov ax, cx
    stosw
    mov ax, 0x8600
    stosw
    xor ax, ax
    stosw
    inc bx
    cmp bx, 256
    jb .v
    ret

; -----------------------------------------------------------------------------
; the PIC to MEGA_PIC_BASE, once at mega_enter and again only if a 286's BIOS
; re-initialised it during a reset (mega_r286). Never per reflection: ICW1
; resets the edge latches (mega_svc). The IMR the 8259 forgets is kept
; -----------------------------------------------------------------------------
mega_pic_pm:
    in al, 0x21
    push ax
    mov al, 0x11                    ; ICW1: edge, cascade, ICW4
    out 0x20, al
    mov al, MEGA_PIC_BASE           ; ICW2: the base
    out 0x21, al
    mov al, 0x04                    ; ICW3: the slave on IRQ2
    out 0x21, al
    mov al, 0x01                    ; ICW4: 8086 mode
    out 0x21, al
    pop ax
    out 0x21, al
    ret

; -----------------------------------------------------------------------------
; mega_a20 - open the A20 line and prove it (CF = 1 it will not open)
; Port 92h first, which every AT-class chipset since the PS/2 has; then the
; 8042's output port, which every AT has. The proof is the only thing that
; counts: 0000:0500 and FFFF:0510 are the same byte with the gate shut.
; -----------------------------------------------------------------------------
mega_a20:
    call mega_a20t
    jnc .ret                        ; already open: do not poke a working line
    pushf                           ; --- the FAST gate, port 92h -----------
    cli
    in al, 0x92
    test al, 2                      ; set (an absent port reads FFh) and the
    jnz .nofast                     ; line still shut: not the gate here
    or al, 2
    and al, 0xFE                    ; bit 0 is a RESET
    out 0x92, al
.nofast:
    popf
    call mega_a20s
    jnc .ret
    pushf                           ; --- the 8042, in ONE window: between D1h
    cli                             ; and DFh the next byte written to 60h is
    call mega_kbw                   ; its output port, and a keyboard ISR's
    jnz .kbx                        ; own traffic there can reset the CPU
    mov al, 0xD1
    out 0x64, al
    call mega_kbw
    jnz .kbx
    mov al, 0xDF                    ; A20 on, reset line high
    out 0x60, al
    call mega_kbw
.kbx:
    popf
    call mega_a20s                  ; ...and the controller acknowledges long
.ret:                               ; before the line moves, hence the settle
    ret
mega_a20s:                          ; SETTLE: up to 512 probes for a gate to
    mov cx, 512                     ; take (XMEM.DRV's XM_A20_SETTLE, whose
.p:                                 ; sequence this is - the first version
    call mega_a20t                  ; here probed once, and on the Victory 286
    jnc .o                          ; that read SHUT: "real mode: A20 will
    loop .p                         ; not open")
.o:
    ret
; mega_leds - the keyboard's lock lights from KB_FLAG (DS = the BDA): command
; EDh and the LED byte (bit 0 Scroll, 1 Num, 2 Caps = KB_FLAG bits 4-6), each
; ACK read here - unless the byte waiting is the PS/2 mouse's, which is left
; for IRQ12. 40:97's low bits follow, as the ROM keeps them.
mega_leds:
    mov al, [0x17]
    shr al, 4
    and al, 7
    mov ah, al
    mov al, [0x97]
    and al, 0xF8
    or al, ah
    mov [0x97], al
    call mega_kbw
    jnz .out
    mov al, 0xED
    out 0x60, al
    call mega_kack
    call mega_kbw
    jnz .out
    mov al, ah
    out 0x60, al
    call mega_kack
.out:
    ret
mega_kack:                          ; wait for the keyboard's ACK and take it
    xor cx, cx
.w:
    in al, 0x64
    test al, 1
    jnz .got
    loop .w
    ret
.got:
    test al, 0x20                   ; the aux port's byte: not ours
    jnz .ret
    in al, 0x60
.ret:
    ret
mega_kbw:
    xor cx, cx
.w:
    in al, 0x64
    test al, 2
    loopnz .w
    ret
mega_a20t:                          ; CF = 1 the gate is SHUT. Complement
    push ds                         ; the word at FFFF:0510 and see whether
    push es                         ; 0000:0500 moved, then complement it back
    push bx                         ; (whichever word it landed on), inside
    pushf                           ; one cli: an ISR touching low memory in
    cli                             ; between would make the probe lie
    xor ax, ax
    mov es, ax
    dec ax
    mov ds, ax
    mov bx, [es:0x0500]
    not word [0x0510]
    mov ax, [es:0x0500]
    not word [0x0510]
    popf
    cmp ax, bx                      ; equal: the flip went a megabyte up
    pop bx
    pop es
    pop ds
    je .open
    stc
    ret
.open:
    clc
    ret

; -----------------------------------------------------------------------------
; mega_t08 - the ROM's half of IRQ0, reached through sch_isr's
; `pushf / call far [sch_old08]` exactly as the ROM was: the tick at 40:6C and
; its midnight wrap, the floppy motor-off count at 40:40, the EOI, iret.
; int 1Ch, which the ROM calls from here, is NOT called: nothing in the tree
; hooks it outside the DOS box, which is real mode (KERN-MEGA-PLAN 2.7).
; -----------------------------------------------------------------------------
mega_t08:
    push ax
    push dx
    push ds
    mov ax, MEGA_BDA
    mov ds, ax
    add word [0x6C], 1
    adc word [0x6E], 0
    cmp word [0x6E], 0x18
    jne .day
    cmp word [0x6C], 0xB0
    jne .day
    xor ax, ax
    mov [0x6C], ax
    mov [0x6E], ax
    mov byte [0x70], 1
.day:
    cmp byte [0x40], 0
    je .eoi
    dec byte [0x40]
    jnz .eoi
    and byte [0x3F], 0xF0           ; every motor off, as the ROM does
    mov al, 0x0C
    mov dx, 0x3F2
    out dx, al
.eoi:
    mov al, 0x20
    out 0x20, al
    pop ds
    pop dx
    pop ax
    iret

; -----------------------------------------------------------------------------
; mega_k09 - the ROM's half of IRQ1: scancode set 1 (the 8042 translates) to
; the BIOS's own buffer at 40:1E, with the shift state at 40:17, so that
; mega_i16 - and a reflected int 16h, were there ever one - read the same
; thing. Reached through kbm_isr's `jmp far [cs:kbm_old9]`.
; -----------------------------------------------------------------------------
mega_k09:
    pusha
    push ds
    mov ax, MEGA_BDA
    mov ds, ax
    in al, 0x60
    cmp al, 0xE0
    jne .note0
    or byte [0x96], 0x02            ; the ROM's own E0 flag (40:96 bit 1)
    jmp .eoi
.note0:
    cmp al, 0xE1                    ; Pause: swallowed
    je .eoi
    mov ah, [0x96]
    and byte [0x96], 0xFD           ; E0 is spent by this code either way
    mov bl, al
    and bl, 0x7F                    ; BL = the key
    mov bh, 0
    ; --- the shift keys, make and break ---
    mov cl, 0x02                    ; left shift
    cmp bl, 0x2A
    je .shift
    mov cl, 0x01                    ; right shift
    cmp bl, 0x36
    je .shift
    mov cl, 0x04                    ; ctrl, either
    cmp bl, 0x1D
    je .shift
    mov cl, 0x08                    ; alt, either
    cmp bl, 0x38
    je .shift
    test al, 0x80
    jz .make
    mov cl, 0x40                    ; a LOCK key's break: no longer held
    cmp bl, 0x3A                    ; (40:18, which is what stops a typematic
    je .lockup                      ; repeat toggling it again)
    mov cl, 0x20
    cmp bl, 0x45
    je .lockup
    mov cl, 0x10
    cmp bl, 0x46
    jne .eoi                        ; every other break is nothing
.lockup:
    not cl
    and [0x18], cl
    jmp .eoi
.make:
    mov cl, 0x40                    ; caps lock
    cmp bl, 0x3A
    je .toggle
    mov cl, 0x20                    ; num lock
    cmp bl, 0x45
    je .toggle
    mov cl, 0x10                    ; scroll lock
    cmp bl, 0x46
    je .toggle
    test ah, 0x02
    jz .plain
    ; --- an E0 key: the grey cluster, keypad Enter and keypad / ---
    mov al, 0xE0
    cmp bl, 0x1C
    jne .e0slash
    mov ax, 0xE00D
    jmp .store
.e0slash:
    cmp bl, 0x35
    jne .e0grey
    mov ax, 0xE02F
    jmp .store
.e0grey:
    test byte [0x17], 0x08          ; alt + grey = (scan + 50h) << 8
    jz .e0ctrl
    add bl, 0x50
    mov ah, bl
    xor al, al
    jmp .store
.e0ctrl:
    mov ah, bl
    jmp .store
.shift:                             ; E0 2A / E0 AA are the keyboard's fake
    test ah, 0x02                   ; shifts around a grey key: ignored
    jz .shreal
    cmp bl, 0x2A
    je .eoi
    cmp bl, 0x36
    je .eoi
.shreal:
    test al, 0x80
    jnz .shbreak
    or [0x17], cl
    jmp .eoi
.shbreak:
    not cl
    and [0x17], cl
    jmp .eoi
.toggle:
    test [0x18], cl                 ; held: a repeat, not a press
    jnz .eoi
    or [0x18], cl
    xor [0x17], cl
    call mega_leds                  ; ...and the light, which is the HOST's
    jmp .eoi                        ; to set: a keyboard never sets its own
.plain:
    cmp bl, 0x58
    ja .eoi
    mov dl, [0x17]
    ; Ctrl+Alt+Del: the ROM's warm boot, by the 8042's reset line
    mov dh, dl
    and dh, 0x0C
    cmp dh, 0x0C
    jne .noreset
    cmp bl, 0x53
    jne .noreset
    mov word [0x72], 0x1234
    call mega_kbw
    mov al, 0xFE
    out 0x64, al
.hang:
    hlt
    jmp .hang
.noreset:
    mov si, bx                      ; SI = the key, for the tables
    cmp bl, 0x3B                    ; F1-F10: 3B-44
    jb .chars
    cmp bl, 0x44
    jbe .fkey
    cmp bl, 0x57                    ; F11, F12: 85h, 86h
    jb .pad
    add bl, 0x85 - 0x57
    mov ah, bl
    test dl, 0x08
    jz .f1112s
    add ah, 6                       ; alt: 8Bh, 8Ch
    jmp .f1112o
.f1112s:
    test dl, 0x04
    jz .f1112h
    add ah, 4                       ; ctrl: 89h, 8Ah
    jmp .f1112o
.f1112h:
    test dl, 0x03
    jz .f1112o
    add ah, 2                       ; shift: 87h, 88h
.f1112o:
    xor al, al
    jmp .store
.fkey:
    mov ah, bl
    test dl, 0x08
    jz .fctrl
    add ah, 0x68 - 0x3B             ; alt: 68h-71h
    jmp .fout
.fctrl:
    test dl, 0x04
    jz .fshift
    add ah, 0x5E - 0x3B             ; ctrl: 5Eh-67h
    jmp .fout
.fshift:
    test dl, 0x03
    jz .fout
    add ah, 0x54 - 0x3B             ; shift: 54h-5Dh
.fout:
    xor al, al
    jmp .store
.pad:                               ; 45-56: the keypad
    cmp bl, 0x47
    jb .chars
    cmp bl, 0x53
    ja .chars
    mov dh, dl
    and dh, 0x20                    ; num lock...
    test dl, 0x03
    jz .padnl
    xor dh, 0x20                    ; ...xor shift
.padnl:
    mov ah, bl
    xor al, al
    or dh, dh
    jz .store                       ; a navigation key: ASCII 0
    mov al, [cs:mega_kpad + si - 0x47]
    jmp .store
.chars:
    cmp bl, 0x39                    ; past SPACE the tables have nothing
    ja .eoi
    mov ah, bl
    test dl, 0x08
    jz .ctrl
    xor al, al                      ; alt + a key: ASCII 0, the scan code
    cmp bl, 0x02                    ; ...and alt + 1-0, - and = are 78h-83h
    jb .store
    cmp bl, 0x0D
    ja .store
    add ah, 0x78 - 0x02
    jmp .store
.ctrl:
    mov al, [cs:mega_kbase + si]
    test dl, 0x04
    jz .shf
    cmp al, 'a'
    jb .ctrl2
    cmp al, 'z'
    ja .ctrl2
    sub al, 0x60                    ; ctrl + a letter: 1-26
    jmp .store
.ctrl2:
    cmp al, 0x0D
    je .store                       ; ctrl+Enter keeps its CR
    cmp al, 0x08
    jne .ctrl3
    mov al, 0x7F
    jmp .store
.ctrl3:
    xor al, al
    jmp .store
.shf:
    mov dh, dl
    and dh, 0x03                    ; shift...
    cmp al, 'a'
    jb .shf2
    cmp al, 'z'
    ja .shf2
    test dl, 0x40                   ; ...xor caps, for a letter
    jz .shf2
    xor dh, 0x03
.shf2:
    or dh, dh
    jz .store
    mov al, [cs:mega_kshift + si]
.store:
    or ax, ax
    jz .eoi
    mov bx, [0x1C]                  ; the tail, and the slot after it
    mov si, bx
    inc si
    inc si
    cmp si, [0x82]
    jb .wrap
    mov si, [0x80]
.wrap:
    cmp si, [0x1A]
    je .eoi                         ; full: the ROM beeps, this drops
    mov [bx], ax
    mov [0x1C], si
.eoi:
    mov al, 0x20
    out 0x20, al
    pop ds
    popa
    iret

; the unshifted and the shifted ASCII for scan codes 00h-39h (SPACE is 39h),
; and the keypad's digits for 47h-53h. Anything past 39h but the keypad and
; the function keys has no ASCII on the ROM either
mega_kbase:
    db 0, 0x1B, '1234567890-=', 0x08, 0x09
    db 'qwertyuiop[]', 0x0D, 0
    db 'asdfghjkl;', "'", '`', 0, '\'
    db 'zxcvbnm,./', 0, '*', 0, ' '
mega_kshift:
    db 0, 0x1B, '!@#$%^&*()_+', 0x08, 0
    db 'QWERTYUIOP{}', 0x0D, 0
    db 'ASDFGHJKL:"~', 0, '|'
    db 'ZXCVBNM<>?', 0, '*', 0, ' '
mega_kpad:
    db '789-456+1230.'
%if mega_kshift - mega_kbase != 0x3A || mega_kpad - mega_kshift != 0x3A
 %error "mega_k09's tables are one byte a scan code, 00h-39h"
%endif

; -----------------------------------------------------------------------------
; mega_i16 - int 16h, natively, over the buffer mega_k09 fills
; AH = 00h/10h read (waits), 01h/11h peek (ZF = 1 empty), 02h/12h the shift
; state, 05h store CX. Anything else returns with AX unchanged, which is what
; a ROM without the function does.
; -----------------------------------------------------------------------------
mega_i16:
    push bp
    mov bp, sp                      ; [bp+2] IP, [bp+4] CS, [bp+6] FLAGS
    push bx
    push si
    push ds
    mov bx, MEGA_BDA
    mov ds, bx
    cmp ah, 0x00
    je .get
    cmp ah, 0x10
    je .get
    cmp ah, 0x01
    je .peek
    cmp ah, 0x11
    je .peek
    cmp ah, 0x02
    je .shift
    cmp ah, 0x12
    je .shift
    cmp ah, 0x05
    je .put
    jmp .out
.get:
    mov si, ax                      ; SI's high byte = the function
.wait:
    cli
    mov bx, [0x1A]
    cmp bx, [0x1C]
    jne .have
    sti
    hlt                             ; the tick or the key wakes it
    jmp .wait
.have:
    mov ax, [bx]
    inc bx
    inc bx
    cmp bx, [0x82]
    jb .gw
    mov bx, [0x80]
.gw:
    mov [0x1A], bx
    sti
    test si, 0xF000                 ; AH = 00h: an E0 ASCII reads as 0
    jnz .out
    cmp al, 0xE0
    jne .out
    xor al, al
    jmp .out
.peek:
    mov si, ax
    mov bx, [0x1A]
    cmp bx, [0x1C]
    jne .pfull
    or word [bp+6], 0x0040          ; ZF = 1: empty
    jmp .out
.pfull:
    and word [bp+6], ~0x0040
    mov ax, [bx]
    test si, 0xF000
    jnz .out
    cmp al, 0xE0
    jne .out
    xor al, al
    jmp .out
.shift:
    mov al, [0x17]
    cmp ah, 0x12
    jne .out
    mov ah, [0x18]
    jmp .out
.put:
    mov bx, [0x1C]
    mov si, bx
    inc si
    inc si
    cmp si, [0x82]
    jb .pw
    mov si, [0x80]
.pw:
    cmp si, [0x1A]
    mov al, 1                       ; AL = 1: full
    je .out
    mov [bx], cx
    mov [0x1C], si
    xor al, al
.out:
    pop ds
    pop si
    pop bx
    pop bp
    iret

; -----------------------------------------------------------------------------
; the BIOS's software services, 10h-1Fh: sixteen stubs of eight bytes, each
; `push imm8 vector / jmp near mega_svc / three bytes of padding`
; -----------------------------------------------------------------------------
mega_ss:
%assign mega_v 0x10
%rep 16
    push byte mega_v
    jmp near mega_svc
    times 3 nop
  %assign mega_v mega_v + 1
%endrep
%if $ - mega_ss != 16*8
 %error "mega_ss is eight bytes a stub"
%endif

; the exceptions, 00h-0Fh, the same eight bytes. 8 and 10-14 arrive with an
; error code under the return address; the rest do not, and their stub pushes
; a 0 in its place, so mega_fault always sees [vector] [error] [IP] [CS] [FLAGS]
mega_xs:
%assign mega_v 0
%rep 16
 %if mega_v == 8 || (mega_v >= 10 && mega_v <= 14)
    push byte mega_v
    jmp near mega_fault
    times 3 nop
 %else
    push byte 0
    push byte mega_v
    jmp near mega_fault
    nop
 %endif
  %assign mega_v mega_v + 1
%endrep
%if $ - mega_xs != 16*8
 %error "mega_xs is eight bytes a stub"
%endif

mega_unh:                           ; a software interrupt nothing handles
    push byte 0                     ; (the vector is not known here; the
    push byte -1                    ; reporter prints FF)
    jmp mega_fault

mega_eoi2:                          ; an IRQ the ROM owned and nothing now
    push ax                         ; does: dismissed
    mov al, 0x20
    out 0xA0, al
    out 0x20, al
    pop ax
    iret
mega_eoi1:
    push ax
    mov al, 0x20
    out 0x20, al
    pop ax
    iret

; -----------------------------------------------------------------------------
; mega_fault - report and stop
; in:       [SP] = vector, [SP+2] = error code (0 where the CPU gives none),
;           then the IP, CS and FLAGS the fault pushed
; -----------------------------------------------------------------------------
mega_fault:
    cli
    pusha                           ; [SP] DI SI BP SP BX DX CX AX, then the
    push ds                         ; vector
    push es
    mov bp, sp
    mov ax, MEGA_SEL_KDATA
    mov ds, ax
    cmp byte [ss:bp+20], 0x0D
    je mega_gpfix                   ; a far transfer to an image's DATA segment
mega_report:                        ; is finished there, not reported
    mov si, mega_mflt
    call mega_puts
    mov ax, [ss:bp+20]              ; the vector
    call mega_hex2
    mov si, mega_mfst
    call mega_puts
    mov cx, 16                      ; sixteen words of whatever the CPU left: the
    lea bx, [bp+22]                 ; error code (or IP), IP, CS, FLAGS, ...
.st:
    mov ax, [ss:bx]
    call mega_hex4
    mov al, ' '
    call mega_putc
    inc bx
    inc bx
    loop .st
    mov si, mega_mreg
    call mega_puts
    mov cx, 10                      ; ES DS DI SI BP SP BX DX CX AX
    mov bx, bp
.rg:
    mov ax, [ss:bx]
    call mega_hex4
    mov al, ' '
    call mega_putc
    inc bx
    inc bx
    loop .rg
    mov ax, ss
    call mega_hex4
    mov al, 10
    call mega_putc
    ; --- ...and on the GLASS, for a machine with no debug port: one line
    ; under the menu bar, through font_run, the way KFZTRACE's strip is
    ; drawn (sched.inc). Once only: a fault inside the drawing comes back
    ; here, and the second time the E9 line above is all there is
    cmp byte [mega_infault], 0
    jne .dead
    mov byte [mega_infault], 1
    push ds
    pop es
    mov di, mega_fbuf + MEGA_FB_V
    mov ax, [ss:bp+20]              ; the vector
    call mega_bhex2
    mov di, mega_fbuf + MEGA_FB_E
    mov ax, [ss:bp+22]              ; the error code
    call mega_bhex4
    mov di, mega_fbuf + MEGA_FB_C
    mov ax, [ss:bp+26]              ; CS
    call mega_bhex4
    mov di, mega_fbuf + MEGA_FB_I
    mov ax, [ss:bp+24]              ; IP
    call mega_bhex4
    mov di, mega_fbuf + MEGA_FB_S
    mov ax, [ss:bp+10]              ; SP as pusha saw it
    call mega_bhex4
    mov byte [gfx_lock_flag], 0     ; whatever the fault interrupted, nobody
    mov word [wm_clip_n], 0         ; is drawing now
    mov byte [gfx_dis], 0
    mov cx, 8
    mov dx, MBAR_H + 8
    mov si, mega_fbuf
    mov ax, (CWHITE << 8) | CBLACK
    call font_run
.dead:
    hlt
    jmp .dead

; -----------------------------------------------------------------------------
; mega_svc - a BIOS service, REFLECTED to real mode (KERN-MEGA-PLAN 2.2)
;
; in:       [SP] = the vector, then the interrupt's IP, CS, FLAGS; every
;           register is the caller's argument to the BIOS
; out:      every register the BIOS's answer, and its CF, ZF and the rest in
;           the FLAGS the iret restores (IF stays the caller's)
;
; DS and ES go to the BIOS as SEGMENTS: an identity selector already is one,
; the kernel's data alias is KERNEL_SEG, LOW0 is 0, and an LDT code alias is
; its 512-aligned base. Coming back, a register the BIOS left alone is given
; its own selector back, and one it changed - int 13h AH=08h's ES:DI, int 10h
; AX=1130h's ES:BP - is taken as the identity selector it now is.
; -----------------------------------------------------------------------------
mega_svc:
    pusha
    push ds
    push es
    mov bp, sp                      ; +0 ES +2 DS +4..+18 DI..AX +20 vector
    mov ax, MEGA_SEL_KDATA          ; +22 IP +24 CS +26 FLAGS
    mov ds, ax
    cmp byte [ss:bp+20], 0x19       ; int 19h: nothing to come back to - the
    jne .refl                       ; 8042's reset line, with the CMOS
    mov al, 0x0F                    ; shutdown byte cleared so the POST is a
    out 0x70, al                    ; whole one
    xor al, al
    out 0x71, al
    call mega_kbw
    mov al, 0xFE
    out 0x64, al
.hang:
    hlt
    jmp .hang
.refl:
    mov ax, [ss:bp+0]               ; ES and DS as SEGMENTS
    mov [mega_ses], ax
    call mega_s2seg
    mov [ss:bp+0], ax
    mov [mega_res], ax
    mov ax, [ss:bp+2]
    mov [mega_sds], ax
    call mega_s2seg
    mov [ss:bp+2], ax
    mov [mega_rds], ax
    mov al, [ss:bp+20]
    mov [mega_rv], al
    push es
    mov ax, MEGA_BDA
    mov es, ax
    mov ax, [es:0x6C]               ; the tick, so the ones the BIOS takes
    pop es                          ; while it holds the CPU are credited
    mov [mega_t0], ax
    in al, 0x21                     ; every IRQ but the BIOS's own masked:
    mov [mega_imr1], al             ; 0 tick, 1 keyboard, 2 cascade, 6 floppy
    or al, 0xB8                     ; on the master, 14 and 15 (the disks) on
    out 0x21, al                    ; the slave. A kernel ISR running in real
    in al, 0xA1                     ; mode would load a SELECTOR as a segment
    mov [mega_imr2], al
    or al, 0x3F
    out 0xA1, al
    ; NO re-initialisation of the 8259 for real mode: ICW1 resets its edge
    ; latches, so a byte the serial mouse sent while IRQ4 was masked above
    ; was LOST - and the UART then holds its line high and never makes the
    ; next edge, so the mouse was dead for the rest of the session. The PIC
    ; stays at MEGA_PIC_BASE and real mode finds the BIOS's handlers there
    ; (mega_enter copies IVT 08h-0Fh to 20h-27h); the masked edge is still
    ; latched when the masks come off
    cmp byte [cpu_tier], CPU_386
    jb .r286
cpu 386
    mov eax, cr0                    ; REAL MODE, the 386's way: clear PE
    and al, 0xFE
    mov cr0, eax
cpu 286
    db 0xEA                         ; jmp far KERNEL_SEG:.rm - reloads CS as a
    dw .rm, KERNEL_SEG              ; real-mode segment, the same base
.r286:                              ; REAL MODE, THE 286's WAY: reset the CPU.
    mov [mega_rss], ss              ; lmsw cannot clear PE, so the BIOS is told
    mov [mega_rsp], sp              ; where to come back to - 40:67, with CMOS
    push es                         ; shutdown code 0Ah, "jump there, no POST,
    mov ax, MEGA_BDA                ; no EOI" - and the CPU is triple-faulted.
    mov es, ax                      ; RAM, the A20 gate and every device keep
    mov word [es:0x67], mega_r286   ; their state; the CPU loses its registers,
    mov word [es:0x69], KERNEL_SEG  ; GDTR, IDTR and LDTR, which is why the way
    pop es                          ; back reloads all three
    mov al, 0x8F                    ; NMI off, CMOS index 0Fh
    out 0x70, al
    mov al, 0x0A
    out 0x71, al
    lidt [mega_nullidt]             ; an IDT with no room in it, then a fault:
    int 3                           ; nothing can be delivered, the 286 shuts
.rhang:                             ; down, and the AT's logic resets it
    hlt
    jmp .rhang
.rm:
    lidt [cs:mega_rmidtr]
.rmc:
    mov ax, ss                      ; LOW_SEG: the selector IS the segment
    mov ss, ax
    mov ax, KERNEL_SEG
    mov ds, ax
    mov al, [mega_rv]               ; real mode: code is memory again
    mov [.intop+1], al
    jmp short .go                   ; ...and the prefetch queue is flushed
.go:
    pop es
    pop ds
    popa                            ; SP is at the vector word
    sti
.intop:
    int 0x10                        ; (the vector, patched above)
    cli
    pushf                           ; +20 the BIOS's FLAGS, +22 vector, +24 IP
    pusha
    push ds
    push es
    mov bp, sp
    mov ax, KERNEL_SEG
    mov ds, ax
    lgdt [mega_gdtr]                ; all three again: a 286's reset cleared
    lidt [mega_idtr]                ; them (and a 386's CR0 path kept them,
    smsw ax                         ; which costs it nothing to redo). lmsw
    or al, 1                        ; can SET PE on either CPU
    lmsw ax
    db 0xEA                         ; jmp far 0x0060:.pm - GDT entry 12 now
    dw .pm, KERNEL_SEG
.pm:
    mov ax, MEGA_SEL_LDT
    lldt ax
    mov ax, MEGA_SEL_KDATA
    mov ds, ax
    mov ax, ss
    mov ss, ax
    mov al, [mega_imr1]
    out 0x21, al
    mov al, [mega_imr2]
    out 0xA1, al
    push es
    mov ax, MEGA_BDA
    mov es, ax
    mov ax, [es:0x6C]
    pop es
    sub ax, [mega_t0]
    add [ticks], ax
    mov ax, [ss:bp+0]               ; ES back: its own selector if the BIOS
    cmp ax, [mega_res]              ; left it alone, the identity selector it
    jne .esnew                      ; now is if it did not
    mov ax, [mega_ses]
.esnew:
    mov [ss:bp+0], ax
    mov ax, [ss:bp+2]
    cmp ax, [mega_rds]
    jne .dsnew
    mov ax, [mega_sds]
.dsnew:
    mov [ss:bp+2], ax
    mov ax, [ss:bp+20]              ; the BIOS's arithmetic flags into the
    and ax, 0x08D5                  ; caller's FLAGS: OF SF ZF AF PF CF
    and word [ss:bp+28], ~0x08D5
    or [ss:bp+28], ax
    pop es
    pop ds
    popa
    add sp, 4                       ; the BIOS's FLAGS and the vector
    iret

; mega_r286 - where a 286's reset comes back to (40:67, CMOS shutdown 0Ah),
; in real mode with every register undefined and interrupts off. The stack
; the reflection was on is put back, the shutdown code cleared so the next
; reset is a real one, and the reflection carries on at mega_svc's real-mode
; half - which reloads the IDTR (the reset left it at the IVT anyway).
mega_r286:
    cli
    mov ax, KERNEL_SEG
    mov ds, ax
    mov ss, [mega_rss]
    mov sp, [mega_rsp]
    mov al, 0x8F
    out 0x70, al
    xor al, al
    out 0x71, al                    ; shutdown code 0: a normal reset next time
    mov al, 0x0D                    ; ...and NMI back on (index 0Dh, a read-only
    out 0x70, al                    ; register, bit 7 clear), as mega_enter
    in al, 0x21                     ; leaves it. A BIOS that re-initialised
    mov ah, [mega_imr1]             ; the 8259 on its way here moved its base
    or ah, 0xB8                     ; back to 08h and cleared the masks, and
    cmp al, ah                      ; the masks are what says so: put ours
    je .picok                       ; back (mega_svc's note on why the 8259
    call mega_pic_pm                ; is otherwise left alone)
    mov al, [mega_imr1]
    or al, 0xB8
    out 0x21, al
    mov al, [mega_imr2]
    or al, 0x3F
    out 0xA1, al
.picok:
    jmp mega_svc.rm

mega_thm_set:                       ; OSAPI_THM_SET's hand-made hot cell
    mov ds, [cs:k_dsel]
    jmp api_thm_set

; -----------------------------------------------------------------------------
; mega_oddsegf - a selector for ANY paragraph (far; KERN-MEGA-PLAN 3.1)
; in:  AX = a real-mode segment. out: AX = a data selector with that base -
;      itself when it is on the identity grid, MEGA_SEL_ODD with its base
;      moved when it is not. Everything else preserved, FLAGS included. In
;      REAL MODE (before mega_enter) AX comes back as it went in.
; ONE scratch descriptor: a caller holds MEGA_SEL_ODD only until its next
; call here, and nothing that can run in between (an ISR) asks for one.
; The loader's decompressor target is the one off-grid segment in M1 (a
; package's prefix is 64 bytes, so its body starts 4 paragraphs along, and
; lz_decomp_x wants DI = 0).
; -----------------------------------------------------------------------------
mega_oddsegf:
    pushf
    cmp word [cs:k_dsel], KERNEL_SEG ; REAL MODE - the boot, before mega_enter:
    je .grid                        ; a segment is its own answer. The boot
                                    ; expands every compressed driver it loads
                                    ; through here, and the protected-mode arm
                                    ; run in real mode wrote a descriptor into
                                    ; the IVT and handed back 0030h, so the
                                    ; driver landed on the API table
    test al, 7
    jz .grid
    push di
    push es
    push ax
    mov di, MEGA_SEL_WIN            ; the GDT itself, as data
    mov es, di
    mov di, MEGA_SEL_ODD
    mov word [es:di], 0xFFFF
    shl ax, 4
    mov [es:di+2], ax
    pop ax
    push ax
    shr ax, 12
    mov ah, 0x92
    mov [es:di+4], ax
    mov word [es:di+6], 0
    pop ax
    mov ax, MEGA_SEL_ODD
    pop es
    pop di
.grid:
    popf
    retf

; -----------------------------------------------------------------------------
; A NEW TASK'S FRAME (sch_frame) names its segment three times - DS, ES and the
; iret's CS - and in protected mode those want three different selectors for
; one segment: the identity DATA selector, the kernel's data alias for ES, and
; the CODE alias for CS. Both helpers are bimodal: before mega_enter (the idle
; task, a boot worker) they answer the real-mode value, and mega_enter fixes
; the frames those left behind (mega_frames_fix).
; in: BP = the task's segment (KERNEL_SEG for a kernel task). out: AX
; -----------------------------------------------------------------------------
mega_frame_ds:
    mov ax, bp
    cmp ax, KERNEL_SEG
    jne .out
    mov ax, [cs:k_dsel]
.out:
    ret
mega_frame_cs:
    cmp byte [cs:mega_on], 0
    je .out
    cmp ax, KERNEL_SEG
    je .out
    shr ax, 2                       ; a package's: its LDT code alias
    or al, 4
.out:
    ret

; mega_frames_fix - every live task but the running one was suspended in real
; mode, so its saved DS and ES may say KERNEL_SEG, which is CODE now: a store
; through either would fault. Both become the data alias. Its CS is right as
; it is - 0x0060 is code - and a package's worker cannot exist yet, nothing
; having been launched before the desktop.
mega_frames_fix:
    push ax
    push bx
    push cx
    push di
    mov bx, sch_tasks
    xor cx, cx
.t:
    cmp byte [bx+T_STATE], 0
    je .n
    cmp cl, [sch_cur]
    je .n
    mov di, [bx+T_SP]
    cmp word [ss:di], KERNEL_SEG    ; the saved DS...
    jne .es
    mov word [ss:di], MEGA_SEL_KDATA
.es:
    cmp word [ss:di+2], KERNEL_SEG  ; ...and ES
    jne .n
    mov word [ss:di+2], MEGA_SEL_KDATA
.n:
    add bx, T_SIZE
    inc cx
    cmp cx, MAX_TASKS
    jb .t
    pop di
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; mega_gpfix - #GP(S) where S is an image's segment: a FAR TRANSFER through the
; data segment that real mode lets code call, finished through S's code alias
;
; A loaded image - a driver, a module, a package's region - is 512-aligned, so
; its segment S is both an identity DATA selector (GDT entry S/8) and, through
; the LDT, an exact CODE alias (S >> 2) | 4. Kernel code converts at the call
; (MEGA_PCALL), but an image that far-calls ANOTHER image by the segment it was
; handed - HDD.DRV into HDDTOOL.DRV and back through hd_tfar and hd_rdisp, the
; Victory 286's Control Panel Hard Drive page - cannot know it should. Loading
; S into CS is #GP with S as the error code, and nothing else loads a data
; identity selector and faults, so the error code says what happened: this
; decodes the instruction at CS:IP to be sure, and does the transfer itself.
;
; Taken: FF /3 and FF /5 (call/jmp far [mem], any 16-bit modrm, with ES, CS, SS
; or DS overrides), 9A and EA (the immediate forms), CB and CA (retf). Anything
; else, or a target that is not S, goes to the reporter unchanged. The frame
; mega_fault built (ES DS DI SI BP SP BX DX CX AX vector error IP CS FLAGS, at
; [ss:bp]) sits directly below the interrupted stack, so a CALL moves it down
; four bytes to make room for the return address and a RETF moves it up over
; the words the transfer popped. Inline, not called: the frame moves.
; -----------------------------------------------------------------------------
mega_gpfix:
    ; STKBALANCE-OK: rewrites the fault frame in place - SP comes back from BP,
    ; moved by the bytes the emulated CALL pushed or RETF popped
    mov ax, [ss:bp+22]              ; the error code: S, TI and EXT clear
    or ax, ax
    jz mega_gpw                     ; #GP(0): a WRITE through a code segment
    test al, 0x1F                   ; ...512-aligned (and so TI = EXT = 0)
    jnz mega_report
    cmp ax, 0xA000                  ; a heap image, not the ROM or video
    jae mega_report
    mov [mega_gps], ax
    mov es, [ss:bp+26]              ; ES:SI = the faulting instruction (a code
    mov si, [ss:bp+24]              ; selector is readable)
    mov dx, [ss:bp+2]               ; DX = its data segment: DS unless told
    xor bx, bx                      ; BL = 1 once a prefix named one
    mov cx, 4                       ; prefixes, at most
.pfx:
    mov al, [es:si]
    mov di, [ss:bp+0]
    cmp al, 0x26                    ; ES:
    je .seg
    mov di, [ss:bp+26]
    cmp al, 0x2E                    ; CS:
    je .seg
    mov di, ss
    cmp al, 0x36                    ; SS:
    je .seg
    mov di, [ss:bp+2]
    cmp al, 0x3E                    ; DS:
    jne .op
.seg:
    mov dx, di
    mov bl, 1
    inc si
    loop .pfx
    jmp mega_report
.op:
    cmp al, 0xFF
    je .ff
    cmp al, 0x9A
    je .imm
    cmp al, 0xEA
    je .imm
    cmp al, 0xCB
    je .retf
    cmp al, 0xCA
    je .retf
    jmp mega_report
.imm:                               ; 9A/EA ptr16:16
    mov cx, [es:si+1]               ; CX = the offset
    mov di, [es:si+3]               ; DI = the segment
    add si, 5                       ; SI = the next instruction
    mov ah, al
    cmp ah, 0x9A
    jmp .target                     ; ZF = 1: a call
.ff:                                ; FF /3 or /5 [mem]
    mov ah, [es:si+1]               ; AH = modrm
    mov al, ah
    and al, 0x38
    cmp al, 0x18                    ; /3: call far
    je .modrm
    cmp al, 0x28                    ; /5: jmp far
    jne mega_report
.modrm:
    mov [mega_gpop], al
    mov al, ah
    shr al, 6                       ; mod
    cmp al, 3
    je mega_report                  ; a register is not a far pointer
    mov cl, ah
    and cl, 7                       ; CL = rm
    xor di, di                      ; DI = the effective address
    cmp al, 0
    jne .base
    cmp cl, 6
    jne .base
    mov di, [es:si+2]               ; mod 0 rm 6: [disp16]
    add si, 4
    jmp short .ea
.base:
    cmp cl, 4
    je .rsi
    cmp cl, 5
    je .rdi
    cmp cl, 7
    je .rbx
    cmp cl, 6
    je .rbp
    test cl, 2                      ; 0,1: BX+..; 2,3: BP+..
    jnz .bp2
    add di, [ss:bp+12]
    jmp short .idx
.bp2:
    add di, [ss:bp+8]
    or bl, bl
    jnz .idx
    mov dx, ss                      ; BP-based: SS, unless overridden
.idx:
    test cl, 1
    jnz .rdi
.rsi:
    add di, [ss:bp+6]
    jmp short .disp
.rdi:
    add di, [ss:bp+4]
    jmp short .disp
.rbx:
    add di, [ss:bp+12]
    jmp short .disp
.rbp:
    add di, [ss:bp+8]
    or bl, bl
    jnz .disp
    mov dx, ss
.disp:
    cmp al, 1
    jne .d16
    mov al, [es:si+2]
    cbw
    add di, ax
    add si, 3
    jmp short .ea
.d16:
    cmp al, 2
    jne .d0
    add di, [es:si+2]
    add si, 4
    jmp short .ea
.d0:
    add si, 2
.ea:
    push ds
    mov ds, dx
    mov cx, [di]                    ; CX = the offset
    mov di, [di+2]                  ; DI = the segment
    pop ds
    cmp byte [mega_gpop], 0x18
.target:                            ; ZF = 1 a call, 0 a jmp; CX:DI the target
    pushf
    cmp di, [mega_gps]
    jne .nottarget
    mov ax, di                      ; AX = the code alias
    shr ax, 2
    or al, 4
    popf
    jnz .jmp
    ; --- CALL: the frame down four bytes, the return address above it -----
    mov dx, [ss:bp+26]              ; the caller's CS
    mov bx, si                      ; BX = the return IP
    xor si, si
.dn:
    mov di, [ss:bp+si]
    mov [ss:bp+si-4], di
    add si, 2
    cmp si, 30
    jb .dn
    sub bp, 4
    mov [ss:bp+30], bx              ; the return IP...
    mov [ss:bp+32], dx              ; ...and CS, where the call put them
.jmp:
    mov [ss:bp+24], cx
    mov [ss:bp+26], ax
.resume:
    mov sp, bp
    pop es
    pop ds
    popa
    add sp, 4                       ; vector and error code
    iret
.nottarget:
    popf
    jmp mega_report
.retf:                              ; CB / CA iw: [T] = IP, [T+2] = CS
    mov cx, [ss:bp+30]
    mov di, [ss:bp+32]
    cmp di, [mega_gps]
    jne mega_report
    mov dx, 4                       ; DX = the bytes the retf takes away
    cmp al, 0xCA
    jne .rup
    add dx, [es:si+1]
.rup:
    mov ax, di
    shr ax, 2
    or al, 4
    mov [ss:bp+24], cx
    mov [ss:bp+26], ax
    mov si, 28                      ; the frame UP by DX, top word first
.up:
    mov di, [ss:bp+si]
    push si
    add si, dx
    mov [ss:bp+si], di
    pop si
    sub si, 2
    jns .up
    add bp, dx
    jmp .resume

; -----------------------------------------------------------------------------
; mega_gpw - #GP(0) from a WRITE through a code segment, done as the code meant
;
; Real mode lets an image use its own segment as data, and on kern_mega that
; segment is read-only. The kernel's own modules are converted at the source
; (PUSH_CSDATA, CSDO); the PACKAGES - some 1,240 such writes and 146
; `push cs / pop` pairs across 37 of them, Pixel alone 594 - run on every
; kernel, so they are met here instead, without a change to any package:
;   * DS or ES is a CODE selector - a package's LDT alias, or the kernel's
;     0x0060 - because the code said `push cs / pop ds`: the register gets the
;     image's DATA segment, which is also the value real mode would have put
;     there, and the instruction runs again;
;   * the instruction carries a CS: prefix: CS cannot be made writable, so the
;     one instruction is copied to mega_tramp with DS: in place of CS:, run
;     there with DS = the image's data segment, and control comes back after
;     it with DS as it was - FLAGS from the instruction, IF as the caller had
;     it. IF is off while it runs, so nothing else reaches the trampoline.
; A fault per write, so a hot loop is slow and right: converting it at the
; source is the fast path. Anything this cannot decode is reported as before.
; -----------------------------------------------------------------------------
mega_gpw:
    ; STKBALANCE-OK: returns by iret from the fault frame, never by ret
    mov ax, [ss:bp+26]              ; AX = the image's data segment, from CS
    call mega_cs2ds
    jc mega_report
    mov dx, ax
    mov es, [ss:bp+26]              ; ES:SI = the instruction
    mov si, [ss:bp+24]
    mov cx, 4                       ; prefixes, at most
    xor bx, bx                      ; BX = where the CS: prefix is, +1
.pfx:
    mov al, [es:si+bx]
    cmp al, 0x2E
    je .csp
    cmp al, 0x26
    je .np
    cmp al, 0x36
    je .np
    cmp al, 0x3E
    je .np
    cmp al, 0xF3
    je .np
    cmp al, 0xF2
    je .np
    cmp al, 0xF0
    jne .op
.np:
    inc bx
    loop .pfx
    jmp mega_report
.csp:
    mov [mega_tcs], bx
    inc word [mega_tcs]
    inc bx
    loop .pfx
    jmp mega_report
.op:
    cmp word [mega_tcs], 0
    jne .tramp
    ; --- no CS: prefix - a code selector in DS or ES -----------------------
    mov cx, 0                       ; CX = registers fixed
    mov ax, [ss:bp+2]
    call mega_cs2ds
    jc .es
    mov [ss:bp+2], ax
    inc cx
.es:
    mov ax, [ss:bp+0]
    call mega_cs2ds
    jc .fixed
    mov [ss:bp+0], ax
    inc cx
.fixed:
    jcxz .noreg
    jmp mega_gpfix.resume           ; the same instruction, again
.noreg:
    jmp mega_report
.tramp:
    ; --- a CS: write: BX = prefix bytes, AL = the opcode -------------------
    mov di, bx                      ; DI = the instruction's length so far
    inc di                          ; ...with the opcode
    mov ah, 0                       ; AH = the immediate's bytes
    cmp al, 0xA2
    je .moffs
    cmp al, 0xA3
    je .moffs
    mov cl, al                      ; ALU r/m,reg: 00-3F with low bits 0/1
    cmp al, 0x40
    jae .grp
    and cl, 0x06
    jnz mega_report                 ; (a reg,r/m or AL,imm form: no write)
    jmp .modrm
.grp:
    cmp al, 0x80
    je .ib
    cmp al, 0x82
    je .ib
    cmp al, 0x83
    je .ib
    cmp al, 0x81
    je .iw
    cmp al, 0xC6
    je .ib
    cmp al, 0xC7
    je .iw
    cmp al, 0xC0
    je .ib
    cmp al, 0xC1
    je .ib
    cmp al, 0x86
    jb mega_report
    cmp al, 0x89
    jbe .modrm                      ; xchg, mov r/m,reg
    cmp al, 0x8C
    je .modrm
    cmp al, 0x8F
    je .modrm
    cmp al, 0xD0
    jb mega_report
    cmp al, 0xD3
    jbe .modrm
    cmp al, 0xFE
    jae .modrm
    cmp al, 0xF6
    je .modrm
    cmp al, 0xF7
    je .modrm
    jmp mega_report
.iw:
    inc ah
.ib:
    inc ah
.modrm:
    push bx
    mov bl, [es:si+bx+1]            ; the modrm byte, after the opcode
    inc di
    mov bh, bl
    and bh, 0xC0
    cmp bh, 0xC0
    je .bad                         ; a register: no memory written
    cmp bh, 0x40
    je .d1
    cmp bh, 0x80
    je .d2
    and bl, 7                       ; mod 0: only rm 6 has a displacement
    cmp bl, 6
    jne .dn
.d2:
    inc di
.d1:
    inc di
.dn:
    pop bx
    mov al, [es:si+bx]              ; F6/F7 /0 and /1 (TEST) carry an immediate
    cmp al, 0xF6
    je .test
    cmp al, 0xF7
    jne .len
.test:
    push bx
    mov bl, [es:si+bx+1]
    test bl, 0x30
    pop bx
    jnz .len
    mov ah, 1
    cmp al, 0xF6
    je .len
    inc ah
    jmp short .len
.bad:
    pop bx
    jmp mega_report
.moffs:
    add di, 2                       ; A2/A3: a 16-bit address
.len:
    mov al, ah
    xor ah, ah
    add di, ax                      ; DI = the whole length
    cmp di, MEGA_TRN
    ja mega_report
    ; --- copy it, CS: made DS:, NOPs after --------------------------------
    push ds
    pop es                          ; ES = the kernel's data, for the copy
    mov cx, di
    push ds
    mov ds, [ss:bp+26]              ; DS:SI = the instruction, through CS's
    xor bx, bx                      ; selector (readable)
.cp:
    mov al, [si+bx]
    cmp al, 0x2E
    jne .cp1
    cmp bx, [es:mega_tcs]           ; THE prefix (BX = its index + 1 - 1)
    jae .cp1
    mov al, 0x3E
.cp1:
    mov [es:mega_tramp+bx], al
    inc bx
    loop .cp
    pop ds
.nop:
    cmp bx, MEGA_TRN
    jae .copied
    mov byte [mega_tramp+bx], 0x90
    inc bx
    jmp short .nop
.copied:
    mov word [mega_tcs], 0
    mov ax, [ss:bp+24]              ; back to just past it
    add ax, di
    mov [mega_tret], ax
    mov ax, [ss:bp+26]
    mov [mega_tret+2], ax
    mov ax, [ss:bp+2]               ; DS as it was, put back after
    mov [mega_tds], ax
    mov [ss:bp+2], dx               ; ...and the image's for the instruction
    mov byte [mega_tif], 0x90       ; IF: back on after, if it was on
    test byte [ss:bp+29], 0x02
    jz .noif
    mov byte [mega_tif], 0xFB       ; sti
.noif:
    and byte [ss:bp+29], 0xFD       ; ...and off while it runs
    mov word [ss:bp+24], mega_tramp
    mov word [ss:bp+26], KERNEL_SEG
    jmp mega_gpfix.resume

; AX = a CODE selector -> AX = the DATA segment with its base, CF = 0; CF = 1
; for anything else (a data selector, the null one, .cold's code). The LDT is
; nothing but the 512-aligned images' code aliases, (S >> 2) | 4.
mega_cs2ds:
    test al, 4
    jnz .ldt
    cmp ax, KERNEL_SEG
    jne .no
    mov ax, MEGA_SEL_KDATA
    clc
    ret
.ldt:
    and al, 0xF8
    shl ax, 2
    clc
    ret
.no:
    stc
    ret

MEGA_TRN    equ 12                  ; the longest instruction it will copy
mega_tramp:                         ; ...run here, at KERNEL_SEG (written
    times MEGA_TRN nop              ; through the data alias: same bytes)
    mov ds, [cs:mega_tds]
mega_tif:   nop                     ; sti, when the caller's IF was on
    jmp far [cs:mega_tret]
mega_tds    dw 0
mega_tret   dw 0, 0
mega_tcs    dw 0                    ; the CS: prefix's index + 1, 0 = none

mega_gps    dw 0                    ; mega_gpfix's S
mega_gpop   db 0                    ; ...and FF's /reg

; -----------------------------------------------------------------------------
; mega_dsimg / mega_csdata - an image's own DATA segment, for PUSH_CSDATA and
; CSDO (kernel/kernel.asm). FAR, and called from the image: the CS a far call
; pushes IS the caller's, so it is read off the return address rather than
; passed. In real mode that CS is the segment itself; in protected mode it is
; the LDT code alias (S >> 2) | 4, so S = (CS & ~7) << 2. FLAGS and every
; register but the answer preserved.
; -----------------------------------------------------------------------------
mega_dsimg:                         ; out: DS = the caller's image, as data
    push bp
    mov bp, sp
    pushf
    push ax
    mov ax, [ss:bp+4]               ; the caller's CS
    cmp word [cs:k_dsel], KERNEL_SEG
    je .rm
    and al, 0xF8
    shl ax, 2
.rm:
    mov ds, ax
    pop ax
    popf
    pop bp
    retf

mega_csdata:                        ; the word under the return address - the
    push bp                         ; caller's `push cs` - made its data
    mov bp, sp                      ; segment
    pushf
    cmp word [cs:k_dsel], KERNEL_SEG
    je .rm
    and byte [ss:bp+6], 0xF8
    shl word [ss:bp+6], 2
.rm:
    popf
    pop bp
    retf

; mega_tasks_ok - CF = 0 when every task but the running one is the KERNEL'S
; (no instance, not a driver's service worker). A package's worker suspended
; in real mode holds real-mode code segments in its stack - the frame's CS and
; every far return into the package beneath it - and nothing can find those to
; convert them, so the switch is refused instead. Only AUTOSTART (SPEC.md
; 26.10.5) can launch one before mega_enter. Clobbers CX, flags.
mega_tasks_ok:
    push bx
    mov bx, sch_tasks
    xor cx, cx
.t:
    cmp byte [bx+T_STATE], 0
    je .n
    cmp cl, [sch_cur]
    je .n
    cmp byte [bx+T_INST], 0xFF
    jne .no
    test byte [bx+T_FLAGS], TF_SERVICE
    jnz .no
.n:
    add bx, T_SIZE
    inc cx
    cmp cx, MAX_TASKS
    jb .t
    pop bx                          ; CF = 0 from the compare (CX < MAX_TASKS
    clc                             ; failed), said outright
    ret
.no:
    pop bx
    stc
    ret

; mega_mods_fix - the module slots the BOOT armed hold a real-mode segment
; (mod_check stores the CODE alias only once mega_pm is set), so every loaded
; module's block is converted here: a slot naming its image's segment becomes
; that image's LDT code alias. A disarmed slot (mod_gone, KERNEL_SEG) is
; already right. mod_fpr's arithmetic, inline: that one is `.cold`.
mega_mods_fix:
    push ax
    push bx
    push cx
    push dx
    push di
    mov bx, mod_tab
.r:
    cmp bx, mod_tab_end
    jae .done
    mov ax, [bx+MODR_SEG]
    or ax, ax
    jz .n
    mov dx, ax
    shr dx, 1
    shr dx, 1
    or dl, 4                        ; DX = its code alias
    mov di, bx
    shr di, 1
    mov cx, [di + mod_fpt + 2 - (MOD_TAB_OFF >> 1)]
    mov di, [di + mod_fpt - (MOD_TAB_OFF >> 1)]
    sub cx, di
    shr cx, 1
    shr cx, 1
    jcxz .n
.s:
    cmp [di+2], ax
    jne .k
    mov [di+2], dx
.k:
    add di, 4
    loop .s
.n:
    add bx, MODR_SIZE
    jmp short .r
.done:
    mov di, dkv                     ; ...and the two vector tables a module
    mov cx, DKI_N                   ; writes ITSELF into with `mov reg, cs`
    call mega_vfix                  ; (DOCK.DRV's dkv, WIN95.DRV's thv): right
    mov di, thv                     ; in protected mode, a real-mode segment
    mov cx, THV_N                   ; if the boot hooked them
    call mega_vfix
    pop di
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; DI = a table of CX far pointers: every segment that is neither the kernel's
; code segment nor .cold's - so a module image's, 512-aligned - becomes its
; LDT code alias. Clobbers AX, CX, DI, flags.
mega_vfix:
    mov ax, [di+2]
    cmp ax, KERNEL_SEG
    je .k
    cmp ax, COLD_SEG
    je .k
    test ax, 31
    jnz .k
    shr ax, 1
    shr ax, 1
    or al, 4
    mov [di+2], ax
.k:
    add di, 4
    loop mega_vfix
    ret

; mega_s2segf - mega_s2seg for a FAR caller (.cold): AX = a selector in, the
; real-mode segment with its base out, everything else preserved. retf.
mega_s2segf:
    call mega_s2seg
    retf

; AX = a selector -> AX = the real-mode segment with the same base. READ OFF
; THE DESCRIPTOR rather than assumed: an identity selector's base is N x 16 by
; construction, but GDT entries 1-7 are the kernel's own and MEGA_SEL_ODD's
; base moves, and a DMA transfer handed the wrong segment lands where nothing
; can watch it - it took the API table out once, from a package load whose
; decompressor target was MEGA_SEL_ODD. A base above 1MB has no real-mode
; segment and comes back as 0xFFFF, which no BIOS transfer can land on.
mega_s2seg:
    cmp word [cs:k_dsel], KERNEL_SEG ; REAL MODE: AX is a segment already
    je .ret                         ; (mega_oddsegf's note)
    or ax, ax
    jz .ret                         ; the null selector: 0, as it was
    test al, 4
    jz .gdt
    and al, 0xF8                    ; LDT: entry i is base i x 512, always
    shl ax, 2
.ret:
    ret
.gdt:
    push es
    push bx
    and al, 0xF8
    mov bx, ax
    mov ax, MEGA_SEL_WIN            ; the GDT, as data
    mov es, ax
    mov ax, [es:bx+2]               ; base 15:0
    mov bl, [es:bx+4]               ; base 23:16
    cmp bl, 0x0F
    ja .high
    shr ax, 4
    mov bh, bl
    shl bh, 4                       ; base 23:16 is segment 15:12
    or ah, bh
    jmp short .out
.high:
    mov ax, 0xFFFF
.out:
    pop bx
    pop es
    ret

mega_say:                           ; SI = a NUL string: to E9 and return
    call mega_puts
    ret
mega_puts:
    push ax
.l:
    mov al, [cs:si]
    inc si
    or al, al
    jz .d
    call mega_putc
    jmp .l
.d:
    pop ax
    ret
mega_putc:
    out 0xE9, al
    ret
mega_hex4:
    push ax
    mov al, ah
    call mega_hex2
    pop ax
mega_hex2:
    push ax
    shr al, 4
    call .n
    pop ax
.n:
    push ax
    and al, 15
    add al, '0'
    cmp al, '9'
    jbe .o
    add al, 7
.o:
    call mega_putc
    pop ax
    ret

; ---- the API's hot cells' stubs (OSAPI_SLOT's kern_mega arm) --------------
; One per OSAPI_SLOT, in table order: DS = the kernel's data, then on to the
; routine, whose near `ret` goes back to the cell's `pop ds / retf`.
%assign mega_i 0
%rep mega_nslot
mega_sl_%[mega_i]:
    mov ds, [cs:k_dsel]
    jmp mega_slt_%[mega_i]
 %assign mega_i mega_i + 1
%endrep

; ---- the inline cells that store a register (MEGA_ICW's kern_mega arm) ----
%macro MEGA_ICW_STUB 2
mega_icw_%1:
    push ds
    mov ds, [cs:k_dsel]
    mov [%1], %2
    pop ds
    retf
%endmacro
    MEGA_ICW_STUB gfx_color, al
    MEGA_ICW_STUB osapi_seed, ax
%ifndef BANDCOMP
    MEGA_ICW_STUB gfx_b1ink, ax
%endif
    MEGA_ICW_STUB ico_c1, ax
%macro MEGA_ICWB_STUB 1
mega_icwb_%1:
    push ds
    mov ds, [cs:k_dsel]
    mov [bx+%1], ax
    pop ds
    retf
%endmacro
    MEGA_ICWB_STUB W_ONSIZE
    MEGA_ICWB_STUB W_ONSZ
    MEGA_ICWB_STUB W_ONWK
    MEGA_ICWB_STUB W_ONRC
    MEGA_ICWB_STUB W_ONCLICK

; mega_bhex4 / mega_bhex2 - AX (AL) as 4 (2) hex digits at ES:DI
mega_bhex4:
    push ax
    mov al, ah
    call mega_bhex2
    pop ax
mega_bhex2:
    push ax
    shr al, 4
    call .n
    pop ax
.n:
    push ax
    and al, 15
    add al, '0'
    cmp al, '9'
    jbe .o
    add al, 7
.o:
    stosb
    pop ax
    ret

mega_infault db 0
mega_fbuf   db " kern_mega FAULT vv err eeee at cccc:iiii sp ssss - reboot "
            db 0
MEGA_FB_V   equ 17
MEGA_FB_E   equ 24
MEGA_FB_C   equ 32
MEGA_FB_I   equ 37
MEGA_FB_S   equ 45

mega_zero8  dw 0, 0, 0, 0
mega_ldtd:                          ; the LDT's descriptor (GDT entry 3)
    dw MEGA_LDT_N*8 - 1, MEGA_LDT_LIN & 0xFFFF
    db MEGA_LDT_LIN >> 16, 0x82
    dw 0
mega_m86    db "kern_mega: an 8086-class CPU - staying in real mode", 10, 0
mega_mmem   db "kern_mega: under 192KB above 1MB - staying in real mode", 10, 0
mega_ma20   db "kern_mega: the A20 line will not open - staying in real mode", 10, 0
mega_mtask  db "kern_mega: a package task predates the switch - staying in real mode", 10, 0
mega_t86    db "real mode: 8086-class CPU", 0
mega_tmem   db "real mode: under 192KB above 1MB", 0
mega_ta20   db "real mode: A20 will not open", 0
mega_ttask  db "real mode: a task predates it", 0
mega_mon    db "kern_mega: protected mode", 10, 0
mega_mtoast db "protected, 286 reset", 0
mega_mtoast3 db "protected, 386 CR0", 0
mega_mflt   db 10, "kern_mega FAULT vector ", 0
mega_mfst   db "  stack: ", 0
mega_mreg   db 10, "  ES DS DI SI BP SP BX DX CX AX SS: ", 0

section .lowbss
mega_seg0   resw 1                  ; MEGA_SEG0's word for code outside .text
mega_pm     resb 1                  ; 1 = protected mode, for .cold (KDATAR_C):
                                    ; .lowbss is zeroed, which is the right
                                    ; answer before mega_enter
section .text
cpu 8086
%endif
