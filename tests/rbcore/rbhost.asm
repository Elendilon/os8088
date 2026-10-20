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
;   MODE 3 (play)   as MODE 1, pressing buttons on gbprof's platformer
;                   script, with the counters and the ticks restarted at
;                   frame 800.
;   MODE 4 (idle)   as MODE 3 with no buttons pressed.
;   MODE 5 (render) as MODE 3, composing every frame with rb_render - the
;                   picture's CPU cost, with no screen written.
;   MODE 6 (damage) as MODE 3, and every third frame composed twice: by
;                   rb_renderd into a buffer it keeps, and whole by
;                   rb_render. The DONE line counts the frames whose two
;                   pictures differ (REALBOY-SPEC section 13.2's gate).
;
; Memory: the boot sector at 0000:7C00, the stack below it, this harness at
; 0800:0000, the core at 1000:0000, the view at 2000:0000, the ROM from
; 3000:0000 (up to 368KB).
; =============================================================================

cpu 8086
bits 16

HOST_SEG        equ 0x0800
CORE_SEG        equ 0x1000
VIEW_SEG        equ 0x2000
ROM_SEG         equ 0x3000
CACHE_SEG       equ 0x9000                  ; the recompiler's 64KB, past the
HASH_SEG        equ 0x8C00                  ;   ROM's 368KB at most, and its
                                            ;   block table's 16KB before it
FRAME_SEG       equ 0x0500                  ; rb_render's 5,760 bytes, under the
                                            ;   boot stack: the harness (with the
                                            ;   recompiler's templates) runs past A000h
FRAMED_SEG      equ 0x0060                  ; MODE 6: rb_renderd's buffer
DMG_SEG         equ 0x01D0                  ;   and its damage memory

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
b_jit       db 1                        ; patched: translate (REALBOY-SPEC 16)
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
    mov al,[b_jit]
    mov [es:h_jit],al
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
h_jit       db 0

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
    cmp byte [h_mode],2
    jne .nt
    call rb_trace_on
    jmp short .nojit
.nt:
    push ds
    mov ax,VIEW_SEG
    mov ds,ax
    cmp byte [cs:h_jit],0               ; the recompiler, unless asked not:
    je .plain                           ;   then the interpreter as it was
    mov ax,CACHE_SEG                    ;   before there was one
    mov bx,HASH_SEG
    call rt_init
    jmp short .jdone
.plain:
    xor al,al
    call rt_dispatch
.jdone:
    pop ds
.nojit:
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
    je .budget
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
.budget:
    inc word [nbudget]                  ; a budget is 8000h M-cycles, under two
    mov ax,[h_frames]                   ;   frames: with the LCD off no frame
    shl ax,1                            ;   ever ends, so a run stops after
    add ax,100                          ;   2 x FRAMES + 100 of them anyway
    cmp ax,[nbudget]
    ja .run
    jmp .end
.frame:
    inc word [nframes]
    cmp byte [h_mode],3
    jb .nj
    call joy_script
    cmp byte [h_mode],5                 ; MODE 5: compose every frame too
    jne .n6
    push es
    mov ax,FRAME_SEG
    mov es,ax
    xor di,di
    call rb_render
    pop es
    jmp short .nj
.n6:
    cmp byte [h_mode],6                 ; MODE 6: by damage and whole
    jne .nj
    call dmg_check
.nj:
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
    mov si,s_jit                        ; the recompiler's blocks and flushes
    call puts
    push ds
    mov ds,[cs:rb_viewseg]
    mov ax,[S_JITNB]
    mov bx,[S_JITFL]
    pop ds
    call dec16
    mov si,s_jfl
    call puts
    mov ax,bx
    call dec16
    mov si,s_jby
    call puts
    push ds
    mov ds,[cs:rb_viewseg]
    mov ax,[S_JITBY]
    mov bx,[S_JITADV]
    pop ds
    call dec16
    mov si,s_jadv
    call puts
    mov ax,bx
    call dec16
%ifdef RT_DEBUG
    push ds
    mov ds,[cs:rb_viewseg]
    mov si,JIT_BUF+0C0h
    mov cx,16
.dbg:
    lodsw
    pop ds
    call hex16
    push ds
    mov ds,[cs:rb_viewseg]
    loop .dbg
    pop ds
%endif
    cmp byte [h_mode],6
    jne .nd
    mov si,s_dmg
    call puts
    mov ax,[dmg_bad]
    call dec16
    mov si,s_dmg1
    call puts
    mov ax,[dmg_first]
    call dec16
    mov si,s_dmg2
    call puts
    mov ax,[dmg_lines]
    call dec16
    mov si,s_dmg3
    call puts
    mov ax,[dmg_off]
    call dec16
%ifdef DMG_DEBUG
    mov si,dmg_dump
    mov cx,85
.dd:
    lodsb
    call hex8
    loop .dd
%endif
.nd:
    mov si,s_end
    call puts
    cmp byte [h_mode],3                 ; MODES 3 and 4 end with the picture's
    jb .halt                            ; inputs, for tests/rbcore/rbshot.py
    mov si,s_vram
    call puts
    push ds
    mov ds,[cs:rb_viewseg]
    mov si,8000h                        ; VRAM
    mov cx,2000h
    call dump
    mov si,0FE00h                       ; OAM
    mov cx,0A0h
    call dump
    mov si,0FF40h                       ; LCDC to WX
    mov cx,0Ch
    call dump
    mov si,0A000h                       ; and A000-A0FF, where Blargg's ROMs
    mov cx,100h                         ;   leave their verdict as text
    call dump
    mov si,S_AF                         ; and the registers, where Mooneye's
    mov cx,12                           ;   leave theirs: AF BC DE HL SP PC
    call dump
    pop ds
    push es                             ; and the frame, as rb_render
    mov ax,FRAME_SEG                    ;   composes it
    mov es,ax
    xor di,di
    call rb_render
    pop es
    push ds
    mov ax,FRAME_SEG
    mov ds,ax
    xor si,si
    mov cx,5760
    call dump
    pop ds
    push ds                             ; and what it was composed from: the
    mov ds,[cs:rb_viewseg]              ;   raster log, the snapshot, and the
    mov si,RB_RLOG                      ;   frame counter and tags
    mov cx,RB_RLOG_MAX*4
    call dump
    mov si,RB_SNAP
    mov cx,8
    call dump
    mov si,S_FRAMES
    mov cx,2
    call dump
    mov al,[S_SNAPTAG]
    call com1
    mov al,[S_RLOGN]
    call com1
    pop ds
.halt:
    hlt
    jmp .halt

; dmg_check - MODE 6: every third frame, rb_renderd against rb_render
dmg_check:
    push ax
    push cx
    push dx
    push si
    push di
    push ds
    push es
    mov ax,[nframes]
    xor dx,dx
    mov cx,3
    div cx
    or dx,dx
    jnz .r
    cmp word [cs:rb_dmgseg],0
    jne .on
    mov word [cs:rb_dmgseg],DMG_SEG     ; the first time: everything
    mov ax,DMG_SEG
    mov es,ax
    mov byte [es:RB_DFULL],1
.on:
    mov ax,FRAMED_SEG
    mov es,ax
    xor di,di
    call rb_renderd                     ; AX = the lines it changed
    add [cs:dmg_lines],ax
    mov ax,FRAME_SEG
    mov es,ax
    xor di,di
    call rb_render
    mov ax,FRAMED_SEG
    mov ds,ax
    xor si,si
    xor di,di
    mov cx,5760 / 2
    repe cmpsw
    je .r
    inc word [cs:dmg_bad]
    cmp word [cs:dmg_first],0
    jne .r
    mov ax,[cs:nframes]
    mov [cs:dmg_first],ax
    mov [cs:dmg_off],si                 ; (past the first word that differs)
%ifdef DMG_DEBUG
    mov ax,si                           ; both copies of that line
    dec ax
    dec ax
    xor dx,dx
    mov cx,40
    div cx
    mul cx
    mov si,ax
    push ds
    pop ax
    push cs
    pop es
    mov di,dmg_dump
    mov cx,40
    rep movsb
    sub si,40
    mov ax,FRAME_SEG
    mov ds,ax
    mov cx,40
    rep movsb
    mov ax,DMG_SEG
    mov ds,ax
    mov si,RB_DTCH
    mov cx,5
    rep movsb
%endif
.r:
    pop es
    pop ds
    pop di
    pop si
    pop dx
    pop cx
    pop ax
    ret
dmg_bad     dw 0
dmg_first   dw 0
dmg_lines   dw 0
dmg_off     dw 0
%ifdef DMG_DEBUG
dmg_dump    times 85 db 0
%endif

; MODE 3's input, tools/gbprof/gbprof.c's platformer script frame for frame:
; Start at 150, 400 and 700, Right held, A for 14 frames of every 50, B for
; the last 29 of every 400. At frame 800 the counters start from zero, as
; gbprof's statistics do, so the two shares compare like for like.
joy_script:
    push ax
    push bx
    push cx
    push dx
    push ds
    mov bx,[nframes]
    xor dl,dl
    cmp byte [cs:h_mode],4              ; MODE 4: the same, no buttons
    je .nb
    mov dl,01h                          ; Right
    mov ax,bx
    sub ax,150
    cmp ax,6
    jb .st
    mov ax,bx
    sub ax,400
    cmp ax,6
    jb .st
    mov ax,bx
    sub ax,700
    cmp ax,6
    jae .nst
.st:
    or dl,80h
.nst:
    mov ax,bx
    push dx
    xor dx,dx
    mov cx,50
    div cx
    cmp dx,14
    pop dx
    jae .na
    or dl,10h
.na:
    mov ax,bx
    push dx
    xor dx,dx
    mov cx,400
    div cx
    cmp dx,370
    pop dx
    jbe .nb
    or dl,20h
.nb:
    mov ds,[cs:rb_viewseg]
    mov [S_JOY],dl
    cmp bx,800
    jne .r
    xor ax,ax
    mov [S_SKIPPED],ax
    mov [S_SKIPPED+2],ax
    mov [S_EVCOUNT],ax
    mov ds,ax                           ; and the ticks: the frames timed are
    mov ax,[0x46C]                      ; 800 onwards, the game in play
    mov dx,[0x46E]
    mov [cs:t0],ax
    mov [cs:t0+2],dx
.r:
    pop ds
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; rb_putc: what the game sends on its link port, to COM1 and the screen - or
; in MODE 2 to the screen only, COM1 carrying nothing but trace records
rb_putc:
    push ax
    push dx
    cmp byte [cs:h_mode],2
    je .s0
    call com1
.s0:
    cmp al,10
    jne .s
    mov al,13
    call scr
    mov al,10
.s:
    call scr
    pop dx
    pop ax
    ret

; CX bytes at DS:SI, raw, to COM1
dump:
    lodsb
    call com1
    loop dump
    ret

; rb_trbyte: a trace record's byte, raw, to COM1
rb_trbyte:
    push dx
    call com1
    pop dx
    ret
com1:
    push ax
    mov dx,0x3FD
.w:
    in al,dx
    test al,0x20
    jz .w
    pop ax
    mov dx,0x3F8
    out dx,al
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
s_dmg   db " damage-bad ",0
s_dmg1  db " first ",0
s_dmg2  db " lines ",0
s_dmg3  db " at ",0
s_ticks db " ticks ",0
s_ev    db " events ",0
s_skip  db " skipped ",0
s_jit   db " jit ",0
s_jfl   db " flushes ",0
s_jby   db " bytes/16 ",0
s_jadv  db " moves ",0
s_end   db " END",10,0
s_vram  db "RBVRAM",0
nframes dw 0
nbudget dw 0
t0      dd 0
ticks   dw 0

%include "rbsys.inc"
%include "rbppu.inc"
%include "rbjit.inc"
