; =============================================================================
; os8088 - tests/rbcore/rbhost.asm
;
; RealBoy's core on a BARE machine: a boot sector that loads this harness,
; the 64KB core (build/realboy/rbcore.bin) and a Game Boy ROM, then runs the
; ROM with no os8088 underneath. It is how the core is gated before there is
; a package (docs/plans/REALBOY-PLAN.md wave 1), and how its cost per
; M-cycle is measured on machines that time things - MartyPC's 8088 and
; 86Box's 286 - without the OS's own costs in the number.
;
; Built by tests/rbcore/rbimg.py, which patches the geometry and the three
; lengths into the boot sector and appends the harness, the core and the ROM.
;
;   MODE 0 (test)   run until FRAMES frames have passed; what the game sends
;                   on its link port goes to the screen and COM1. Blargg's
;                   test ROMs print their verdict that way.
;   MODE 1 (bench)  run FRAMES frames and print FRAMES, the BIOS ticks they
;                   took, and the core's own counts.
;   MODE 2 (trace)  as MODE 0, with an RB_TRACE core: one line per
;                   instruction on COM1 only (tools/gbtrace.py diffs it).
;
; Memory: the boot sector at 0000:7C00, the stack below it, this harness at
; 0800:0000, the core at 1000:0000, the view at 2000:0000, the ROM from
; 3000:0000 (up to 384KB).
; =============================================================================

cpu 8086
bits 16

HOST_SEG        equ 0x0800
CORE_SEG        equ 0x1000
VIEW_SEG        equ 0x2000
ROM_SEG         equ 0x3000

; --- the boot sector ---------------------------------------------------------
section boot start=0 vstart=0x7C00
boot:
    jmp short boot_go
    nop
b_spt       db 9                        ; patched: sectors a track
b_heads     db 2                        ; patched: heads
b_hostsec   dw 0                        ; patched: harness sectors
b_coresec   dw 128
b_romsec    dw 0                        ; patched: ROM sectors
b_mode      db 0                        ; patched: MODE
b_frames    dw 600                      ; patched: FRAMES
boot_go:
    cli
    xor ax,ax
    mov ss,ax
    mov sp,0x7C00
    mov ds,ax
    sti
    cld
    mov [b_drive],dl
    mov word [b_lba],1
    mov ax,HOST_SEG
    mov cx,[b_hostsec]
    call load
    mov ax,CORE_SEG
    mov cx,[b_coresec]
    call load
    mov ax,ROM_SEG
    mov cx,[b_romsec]
    call load
    ; hand the harness its parameters through its own header
    mov ax,HOST_SEG
    mov es,ax
    mov al,[b_mode]
    mov [es:h_mode],al
    mov ax,[b_frames]
    mov [es:h_frames],ax
    mov ax,[b_romsec]
    mov [es:h_romsec],ax
    jmp HOST_SEG:host_main

; load CX sectors from LBA [b_lba] to AX:0000, one at a time
load:
    jcxz .r
    push ax
    push cx
    mov es,ax
    mov ax,[b_lba]
    xor dx,dx
    mov bl,[b_spt]
    xor bh,bh
    div bx                              ; AX = track, DX = sector - 1
    mov cl,dl
    inc cl
    xor dx,dx
    mov bl,[b_heads]
    div bx                              ; AX = cylinder, DX = head
    mov ch,al
    mov dh,dl
    mov dl,[b_drive]
    mov di,4
.try:
    xor bx,bx
    mov ax,0x0201
    int 0x13
    jnc .ok
    xor ax,ax
    int 0x13
    dec di
    jnz .try
    mov si,s_err
.p:
    lodsb
    or al,al
    jz $
    mov ah,0x0E
    int 0x10
    jmp .p
.ok:
    inc word [b_lba]
    pop cx
    pop ax
    add ax,0x20
    loop load
.r:
    ret
b_drive db 0
b_lba   dw 0
s_err   db "rbhost: disk error",0
    times 510-($-$$) db 0
    dw 0xAA55

; --- the harness -------------------------------------------------------------
section host follows=boot vstart=0
h_mode      db 0
h_frames    dw 0
h_romsec    dw 0

%include "rbdefs.inc"

host_main:
    mov ax,cs
    mov ds,ax
    mov es,ax
    mov ax,0x0003                       ; a clean text screen
    int 0x10
    ; COM1, 115200 8N1, polled
    mov dx,0x3FB
    mov al,0x80
    out dx,al
    mov dx,0x3F8
    mov al,1
    out dx,al
    inc dx
    xor al,al
    out dx,al
    mov dx,0x3FB
    mov al,3
    out dx,al
    mov si,s_hello
    call puts
    ; rb_init: view, core, ROM, banks = sectors / 32
    mov dx,[h_romsec]
    mov cl,5
    shr dx,cl
    cmp dx,2
    jae .b
    mov dx,2
.b:
    mov ax,VIEW_SEG
    mov bx,CORE_SEG
    mov cx,ROM_SEG
    call rb_init
    ; the BIOS tick count as we start
    push ds
    xor ax,ax
    mov ds,ax
    mov ax,[0x46C]
    mov dx,[0x46E]
    pop ds
    mov [t0],ax
    mov [t0+2],dx
.run:
    mov ax,0x8000
    call rb_run
    cmp al,RBX_FRAME
    je .frame
    cmp al,RBX_BUDGET
    je .run
    cmp al,RBX_STOP
    je .run
    ; a bad opcode: say where and stop
    mov si,s_bad
    call puts
    push ds
    mov ds,[cs:rb_viewseg]
    mov al,[S_BADOP]
    mov bx,[S_PC]
    pop ds
    call hex8
    mov al,' '
    call putc
    mov ax,bx
    call hex16
    jmp .end
.frame:
    inc word [nframes]
    mov ax,[nframes]
    cmp ax,[h_frames]
    jb .run
.end:
    push ds
    xor ax,ax
    mov ds,ax
    mov ax,[0x46C]
    mov dx,[0x46E]
    pop ds
    sub ax,[t0]
    sbb dx,[t0+2]
    mov [ticks],ax
    mov si,s_done
    call puts
    mov ax,[nframes]
    call dec16
    mov si,s_ticks
    call puts
    mov ax,[ticks]
    call dec16
    mov si,s_ev
    call puts
    push ds
    mov ds,[cs:rb_viewseg]
    mov ax,[S_EVCOUNT]
    mov bx,[S_SKIPPED]
    mov cx,[S_SKIPPED+2]
    pop ds
    call dec16
    mov si,s_skip
    call puts
    mov ax,cx
    call hex16
    mov ax,bx
    call hex16
    mov si,s_end
    call puts
.halt:
    hlt
    jmp .halt

; rb_putc: what the game sends on its link port (and the trace)
rb_putc:
    push ax
    push dx
    push ax
    mov dx,0x3FD
.w:
    in al,dx
    test al,0x20
    jz .w
    pop ax
    mov dx,0x3F8
    out dx,al
    cmp byte [cs:h_mode],2
    je .r
    cmp al,10
    jne .s
    mov al,13
    call scr
    mov al,10
.s:
    call scr
.r:
    pop dx
    pop ax
    ret

putc:
    jmp rb_putc
scr:
    push ax
    push bx
    mov ah,0x0E
    xor bx,bx
    int 0x10
    pop bx
    pop ax
    ret
puts:
    push ax
.l:
    mov al,[cs:si]
    inc si
    or al,al
    jz .r
    call putc
    jmp .l
.r:
    pop ax
    ret
hex16:
    push ax
    mov al,ah
    call hex8
    pop ax
hex8:
    push ax
    shr al,1
    shr al,1
    shr al,1
    shr al,1
    call .n
    pop ax
.n:
    push ax
    and al,0x0F
    add al,'0'
    cmp al,'9'
    jbe .p
    add al,7
.p:
    call putc
    pop ax
    ret
dec16:
    push ax
    push bx
    push cx
    push dx
    mov bx,10
    xor cx,cx
.d:
    xor dx,dx
    div bx
    push dx
    inc cx
    or ax,ax
    jnz .d
.o:
    pop ax
    add al,'0'
    call putc
    loop .o
    pop dx
    pop cx
    pop bx
    pop ax
    ret

s_hello db "RealBoy core harness",10,0
s_bad   db 10,"RBHOST BADOP ",0
s_done  db 10,"RBHOST DONE frames ",0
s_ticks db " ticks ",0
s_ev    db " events ",0
s_skip  db " skipped ",0
s_end   db " END",10,0
nframes dw 0
t0      dd 0
ticks   dw 0

%include "rbsys.inc"
