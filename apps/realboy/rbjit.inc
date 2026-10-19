; =============================================================================
; os8088 - apps/realboy/rbjit.inc
;
; RealBoy's RECOMPILER (docs/REALBOY-SPEC.md section 16): Game Boy code from
; ROM translated, a block at a time, into 8086 code in the core's own
; segment. Included by a host after rbsys.inc, with build/rbcore.inc (the
; core's offsets) and build/rbtmpl.bin (the templates) on its include path.
;
; A translated instruction is its interpreter handler's own body - apps/
; realboy/rbtmpl.py lifts each one out of the generated core with the dispatch
; taken off and the operands made immediates - so translated code computes
; exactly what the interpreter does, and every gate on the one is a gate on
; the other. What it saves is the interpreter's fixed cost: the three-
; instruction dispatch, which flushes a 286's prefetch queue every time, and
; the operand fetches through SI.
;
; THE CODE goes into a 64KB CACHE SEGMENT of the host's, which also holds
; copies of the core's helper tails at their own offsets (rbtmpl.py lists
; the slots): a template reaches every helper with a near jump, which is
; what lets one be copied at all, and ~60KB is left for code. A helper that
; leaves for rbsys records its own CS first, so rbsys comes back to the copy
; that called it. When the cache is full, everything is thrown away and
; translation starts again (rt_flush).
;
; A BLOCK is straight-line code from one PC to the first control transfer, at
; most RT_MAXI instructions, and never across 4000h or 8000h. It is keyed by
; its PC and, in 4000-7FFF, the ROM bank (tr_enter's table). What leaves it:
;   - a control transfer, translated here: its M-cycles, the event check the
;     interpreter makes at a branch, and on to tr_enter with SI = the target;
;   - an opcode that has no template and is not a jump (HALT, STOP, RETI, an
;     invalid one): SI = its PC and the interpreter's dispatch, which comes
;     back through tr_enter at its next branch;
;   - a store that took an interrupt (rb_irqnow moves SI: the store is
;     guarded with SI = the next PC, and left by when it moved), or that
;     switched the bank under a block running from 4000-7FFF.
; RAM is never translated: tr_enter interprets a PC at 8000h or above.
; =============================================================================

%include "rbcore.inc"

RT_MAXI         equ 40              ; instructions a block at most
RT_CTL          equ 72              ; bytes a control transfer's code may take
                                    ;   (RET cc 63, JR cc to a spin-wait on
                                    ;   (HL) 71: each rt_room asks for what
                                    ;   it writes, since most gaps are ~106)
RT_FALL         equ 24              ; ...and a block's fall-through exit
; the translator's scratch, in the view after JIT_BUF's 128 bytes of code
RT_PC0          equ JIT_BUF + 80h   ; word: the block's PC
RT_N            equ JIT_BUF + 82h   ; word: code bytes in JIT_BUF
RT_IX           equ JIT_BUF + 84h   ; word: the instruction's place in it
RT_START        equ JIT_BUF + 86h   ; word: the block's offset in the core
RT_CNT          equ JIT_BUF + 88h   ; word: instructions so far
RT_BANKW        equ JIT_BUF + 8Ah   ; word: S_BANK/S_BANKHI as it was
RT_NEXT         equ JIT_BUF + 8Ch   ; word: the instruction's next PC
RT_IMM          equ JIT_BUF + 8Eh   ; word: its operand bytes
RT_REC          equ JIT_BUF + 90h   ; word: its template record
RT_GUARD        equ JIT_BUF + 92h   ; byte: 1 store guard, 2 bank guard
RT_OP           equ JIT_BUF + 93h   ; byte: the opcode
RT_T            equ JIT_BUF + 94h   ; word: a jump's target
RT_IDLE         equ JIT_BUF + 96h   ; byte: rt_idle's answer for it
RT_LOOP         equ JIT_BUF + 0A0h  ; 16: a spin-wait's body, for rt_idle

RT_HFREE        equ 1040            ; the table's free ranges: offset, count
RT_HTAIL        equ 1044            ; ...its tail slots
RT_HJD          equ 1048            ; ...the interpreter's JDISPATCH sites
rt_tab:
    incbin "rbtmpl.bin"

; rt_init - DS = the view, after rb_init; AX = the cache's segment, a 64KB
; claim of the host's. The core's helper tails copied into it at their own
; offsets, the cache empty, and the core's two doors pointed at it -
; tr_enter's miss at rb_jit, and rbsys's resume (after every event) at
; tr_enter rather than the interpreter's dispatch
rt_init:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    mov [S_JITSEG],ax
    mov [S_JITOUT+2],ax
    mov es,ax
    mov word [S_JITVEC],rb_jit
    mov [S_JITVEC+2],cs
    mov word [S_RESVEC],RBC_TR_ENTER
    mov bx,[cs:rt_tab + RT_HTAIL]       ; the tail slots
    mov dx,[cs:rt_tab + RT_HTAIL + 2]
.slot:
    mov ah,[cs:rt_tab + bx]
    xor al,al
    mov si,ax
    mov di,ax
    mov cx,128
    push ds
    mov ds,[S_DISP+2]               ; the core
    rep movsw
    pop ds
    inc bx
    dec dx
    jnz .slot
    call rt_flush
    mov byte [S_JITON],1
    mov al,1
    call rt_dispatch                ; the interpreter's sites look again
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; rt_dispatch - AL = 1: the interpreter's control transfers look for
; translated code (JDISPATCH as built); AL = 0: they DISPATCH, as the
; interpreter did before there was a recompiler - each site's first five
; bytes, cmp si,8000h / jae, become mov dh,[si] / inc si / jmp dx, so a
; machine that never translates (an 8088) pays nothing for one. DS = view.
rt_dispatch:
    push ax
    push bx
    push cx
    push si
    push es
    mov es,[S_DISP+2]               ; the core
    mov si,[cs:rt_tab + RT_HJD]
    mov cx,[cs:rt_tab + RT_HJD + 2]
.s:
    mov bx,[cs:rt_tab + si]
    or al,al
    jz .off
    mov word [es:bx],0FE81h         ; cmp si,8000h / jae (+3 stays)
    mov word [es:bx+2],8000h
    mov byte [es:bx+4],73h
    jmp short .n
.off:
    mov word [es:bx],348Ah          ; mov dh,[si] / inc si / jmp dx
    mov word [es:bx+2],0FF46h
    mov byte [es:bx+4],0E2h
.n:
    inc si
    inc si
    loop .s
    pop es
    pop si
    pop cx
    pop bx
    pop ax
    ret

; rt_flush - DS = the view: every block forgotten, the first gap current
rt_flush:
    push ax
    push cx
    push di
    push es
    mov es,[S_JITSEG]
    mov di,JIT_HASH
    mov cx,JIT_HASHN * 8 / 2
    xor ax,ax
    rep stosw
    mov word [S_JITGI],0
    mov di,[cs:rt_tab + RT_HFREE]       ; the gap list
    mov ax,[cs:rt_tab + di]
    mov [S_JITPTR],ax
    mov ax,[cs:rt_tab + di + 2]
    sub ax,3                        ; a gap keeps 3 bytes for its way out
    mov [S_JITEND],ax
    inc word [S_JITFL]
    pop es
    pop di
    pop cx
    pop ax
    ret

; rb_jit - tr_enter's miss, SS:SP the game's stack: translate the block at SI
; on the host's stack and go back into the core at tr_back
rb_jit:
    RB_TOHOST
    push ax
    push bx
    push cx
    push si
    push di
    push bp
    push es
    call rt_translate
    pop es
    pop bp
    pop di
    pop si
    pop cx
    pop bx
    pop ax
    jmp rb_ret

; -----------------------------------------------------------------------------
; rt_translate - SI = the PC, [S_JITBK] its bank key, DS = the view. Out:
; [S_JITOUT] = the block's offset in the core. ES:DI writes the code.
; -----------------------------------------------------------------------------
rt_translate:
    mov [RT_PC0],si
.restart:
    mov si,[RT_PC0]
    mov ax,[S_BANK]
    mov [RT_BANKW],ax
    ; the Game Boy's code, up to the end of its region, into JIT_BUF
    mov cx,4000h
    mov bx,[S_VIEW]
    cmp si,4000h
    jb .reg
    mov cx,8000h
    mov bx,[S_ROMX]
.reg:
    sub cx,si
    cmp cx,80h
    jbe .n
    mov cx,80h
.n:
    mov [RT_N],cx
    push ds
    pop es
    mov di,JIT_BUF
    push ds
    mov ds,bx
    rep movsb
    pop ds
    mov es,[S_JITSEG]               ; ES = the cache
    mov di,[S_JITPTR]
    mov cx,RT_FALL + 2
    call rt_room
    jc .restart
    mov [RT_START],di
    mov word [RT_IX],0
    mov word [RT_CNT],0
.next:
    mov bx,[RT_IX]
    cmp word [RT_CNT],RT_MAXI
    jae .fall
    lea ax,[bx+3]
    cmp ax,[RT_N]
    ja .fall
    mov al,[JIT_BUF+bx]
    mov [RT_OP],al
    mov ax,[JIT_BUF+bx+1]
    mov [RT_IMM],ax
    call rt_pick                    ; a constant address: one MOV
    jnc .tm
    mov al,[RT_OP]
    xor ah,ah
    cmp al,0CBh
    jne .tm
    mov al,[JIT_BUF+bx+1]
    inc ah
.tm:
    shl ax,1
    xchg ax,si
    mov si,[cs:rt_tab + si]
    or si,si
    jz .ctl
    mov [RT_REC],si
    call rt_tmpl
    jc .restart
    inc word [RT_CNT]
    jmp .next
.ctl:
    mov cx,RT_CTL
    call rt_room
    jc .restart
    mov ax,[RT_IX]
    add ax,[RT_PC0]                 ; AX = the instruction's PC
    call rt_ctl
    jmp short .done
.fall:
    mov cx,RT_FALL
    call rt_room
    jc .restart
    mov ax,[RT_IX]
    add ax,[RT_PC0]
    call rt_exit_or                 ; on to the next PC, checking BP
.done:
    mov [S_JITPTR],di
    mov ax,di                       ; (stat: the block's bytes, / 16 - a
    sub ax,[RT_START]               ;   range move inside it reads high)
    mov cl,4
    shr ax,cl
    add [S_JITBY],ax
    ; the table: this PC and bank key -> the block
    mov si,[RT_PC0]
    mov dl,[S_JITBK]
    mov bx,si
    xor bl,dl
    mov dh,bh                       ; (tr_enter's slot: PC >> 11 folded in)
    shr dh,1
    shr dh,1
    shr dh,1
    xor bl,dh
    and bh,7
    shl bx,1
    shl bx,1
    shl bx,1
    mov [es:JIT_HASH+bx],si
    mov [es:JIT_HASH+bx+2],dl
    mov ax,[RT_START]
    mov [es:JIT_HASH+bx+4],ax
    mov [S_JITOUT],ax
    inc word [S_JITNB]
%ifdef RT_DEBUG
    mov bx,[S_JITNB]                ; the last 8 PCs translated, and keys
    and bx,7
    shl bx,1
    shl bx,1
    mov [JIT_BUF+0C0h+bx],si
    mov al,[S_JITBK]
    mov [JIT_BUF+0C2h+bx],al
%endif
    ret

; rt_pick - the instruction at [RT_OP]/[RT_IMM] by its operand: CF = 0 and
; AX = a chosen-by-operand record (rbgen.EXTRA: 512 + k), [RT_IMM] the
; whole address, when it is LDH or LD (nn) on an address the interpreter's
; own fast path takes directly; CF = 1 otherwise
rt_pick:
    mov al,[RT_OP]
    mov dx,[RT_IMM]
    cmp al,0F0h                     ; LDH A,(n): n >= 80h
    jne .e0
    cmp dl,80h
    jb .no
    mov ax,512
    jmp short .ff
.e0:
    cmp al,0E0h                     ; LDH (n),A: 80h <= n < FFh
    jne .fa
    cmp dl,80h
    jb .no
    cmp dl,0FFh
    je .no
    mov ax,513
.ff:
    mov dh,0FFh
    mov [RT_IMM],dx
    clc
    ret
.fa:
    cmp al,0FAh                     ; LD A,(nn): bank 0, 8000-FEFF, FF80+
    jne .ea
    cmp dh,40h
    jb .rd
    cmp dh,80h
    jb .no
    cmp dh,0FFh
    jne .rd
    cmp dl,80h
    jb .no
.rd:
    mov ax,514
    clc
    ret
.ea:
    cmp al,0EAh                     ; LD (nn),A: 8000-FEFF, FF80-FFFE
    jne .no
    test dh,dh
    jns .no
    cmp dh,0FFh
    jne .wr
    cmp dl,80h
    jb .no
    cmp dl,0FFh
    je .no
.wr:
    mov ax,515
    clc
    ret
.no:
    stc
    ret

; rt_room - CX = the bytes about to be written at ES:DI. On to the next gap
; when this one has not got them, with a jump from here to there; with no gap
; left, everything is flushed and CF = 1: the caller starts its block again.
rt_room:
    mov ax,di
    add ax,cx
    jc .adv
    cmp ax,[S_JITEND]
    jbe .ok
.adv:
    push bx
    mov bx,[S_JITGI]
    inc bx
    mov ax,[cs:rt_tab + RT_HFREE + 2]       ; the gaps there are
    cmp bx,ax
    jb .g
    pop bx
    call rt_flush
    stc
    ret
.g:
    inc word [S_JITADV]
    mov [S_JITGI],bx
    shl bx,1
    shl bx,1
    add bx,[cs:rt_tab + RT_HFREE]
    mov ax,[cs:rt_tab + bx]         ; the gap's start: jmp near there
    push ax
    mov byte [es:di],0E9h
    sub ax,di
    sub ax,3
    mov [es:di+1],ax
    pop di
    mov ax,[cs:rt_tab + bx + 2]
    sub ax,3
    mov [S_JITEND],ax
    pop bx
    jmp short rt_room
.ok:
    clc
    ret

; -----------------------------------------------------------------------------
; rt_tmpl - one templated instruction at [RT_IX], record [RT_REC]: its guards,
; the template, its operands and its fixups. CF = 1: flushed, start again.
; -----------------------------------------------------------------------------
rt_tmpl:
    mov si,[RT_REC]
    xor ah,ah
    mov al,[cs:rt_tab + si + 3]     ; the instruction's length
    add ax,[RT_IX]
    mov [RT_IX],ax
    add ax,[RT_PC0]
    mov [RT_NEXT],ax
    ; the guards (REALBOY-SPEC section 16.5)
    mov byte [RT_GUARD],0
    mov al,[cs:rt_tab + si + 4]
    test al,1
    jnz .sg
    test al,2
    jz .c16
    mov ah,[RT_IMM]                 ; LDH (n),A: IF or IE?
    cmp ah,0Fh
    je .sg
    cmp ah,0FFh
    je .sg
    jmp short .bk
.c16:
    test al,4
    jz .bk
    cmp word [RT_IMM],0FF0Eh        ; LD (nn),A / LD (nn),SP into I/O, HRAM
    jae .sg
    jmp short .bk
.sg:
    or byte [RT_GUARD],1
.bk:
    cmp word [RT_PC0],4000h         ; running from the bank: a store that
    jb .room                        ;   could reach the MBC is checked after
    test al,1
    jnz .bg
    test al,4
    jz .room
    cmp word [RT_IMM],8000h
    jae .room
.bg:
    or byte [RT_GUARD],2
.room:
    mov cl,[cs:rt_tab + si + 2]
    xor ch,ch
    test byte [RT_GUARD],1          ; and exactly the guards' bytes
    jz .r2
    add cx,12
.r2:
    test byte [RT_GUARD],2
    jz .r3
    add cx,20
.r3:
    call rt_room
    jnc .go
    ret
.go:
    test byte [RT_GUARD],1
    jz .copy
    mov al,0BEh                     ; mov si,NEXT
    stosb
    mov ax,[RT_NEXT]
    stosw
.copy:
    mov si,[RT_REC]
    mov cl,[cs:rt_tab + si + 2]
    xor ch,ch
    push di                         ; the template's place
    push si
    push ds
    push cs
    pop ds
    lea si,[rt_tab + si + 9]
    rep movsb
    pop ds
    pop si
    pop bx                          ; BX = where the template went
    ; the fixups
    mov dx,bx
    sub dx,[cs:rt_tab + si]         ; DX = its place - its origin
    mov cl,[cs:rt_tab + si + 2]
    xor ch,ch
    lea bp,[si + 9]
    add bp,cx                       ; BP = the position lists (in rt_tab)
    mov cl,[cs:rt_tab + si + 5]     ; IMM8
    jcxz .i16
.p8:
    mov al,[cs:rt_tab + bp]
    inc bp
    xor ah,ah
    xchg ax,si
    mov al,[RT_IMM]
    mov [es:bx+si],al
    xchg ax,si
    mov si,[RT_REC]
    loop .p8
.i16:
    mov cl,[cs:rt_tab + si + 6]
    jcxz .ab
.p16:
    mov al,[cs:rt_tab + bp]
    inc bp
    xor ah,ah
    xchg ax,si
    mov ax,[RT_IMM]
    mov [es:bx+si],ax
    mov si,[RT_REC]
    loop .p16
.ab:
    mov cl,[cs:rt_tab + si + 7]
    jcxz .rl
.pab:
    mov al,[cs:rt_tab + bp]
    inc bp
    xor ah,ah
    xchg ax,si
    add [es:bx+si],dx
    mov si,[RT_REC]
    loop .pab
.rl:
    mov cl,[cs:rt_tab + si + 8]
    jcxz .post
.prl:
    mov al,[cs:rt_tab + bp]
    inc bp
    xor ah,ah
    xchg ax,si
    sub [es:bx+si],dx
    mov si,[RT_REC]
    loop .prl
.post:
    test byte [RT_GUARD],1
    jz .bank
    mov ax,0FE81h                   ; cmp si,NEXT / je +3 / jmp tr_enter:
    stosw                           ;   an interrupt the store took moved SI
    mov ax,[RT_NEXT]
    stosw
    mov ax,0374h
    stosw
    mov ax,RBC_TR_ENTER
    call rt_jmp
.bank:
    test byte [RT_GUARD],2
    jz .r
    mov ax,8136h                    ; cmp word [ss:S_BANK],BANKW
    stosw
    mov al,3Eh
    stosb
    mov ax,S_BANK
    stosw
    mov ax,[RT_BANKW]
    stosw
    mov ax,0674h                    ; je +6
    stosw
    mov al,0BEh                     ; mov si,NEXT / jmp tr_enter
    stosb
    mov ax,[RT_NEXT]
    stosw
    mov ax,RBC_TR_ENTER
    call rt_jmp
.r:
    clc
    ret

; rt_jmp - jmp near AX (a core offset) at ES:DI
rt_jmp:
    push ax
    mov al,0E9h
    stosb
    pop ax
    sub ax,di
    sub ax,2
    stosw
    ret

; rt_exit_or - on to the Game Boy address AX, testing BP's sign here
rt_exit_or:
    push ax
    mov ax,0ED0Bh                   ; or bp,bp
    stosw
    pop ax
; rt_exit - on to the Game Boy address AX, the flags BP's (a SUB BP just
; before): SI = AX, the event entry when BP went negative, and otherwise the
; block there - directly when it is translated already and its bank cannot
; differ, through tr_link (which patches this exit into that jump) when it
; is not translated yet, and through tr_enter when it is not chainable.
; DS is not loaded: translated code does not keep it (tr_int does).
rt_exit:
    push bx
    push dx
    push ax
    mov al,0BEh                     ; mov si,AX
    stosb
    pop ax
    stosw
    mov bx,ax                       ; bank 0: chained, now if the block
    mov dl,0FFh                     ;   is there already
    cmp ah,40h
    jb .key
    cmp ah,80h
    jae .enter                      ; RAM: never translated
    mov ax,0E78h                    ; 4000-7FFF: js +14 / ELEVEN bytes,
    stosw                           ;   mov dx,SITE / jmp tr_link and five
    mov al,0BAh                     ;   spare, which tr_link makes a bank
    stosb                           ;   check and a jmp (16.4) / then the
    mov ax,di                       ;   exit's own jmp tr_enter, for when
    dec ax                          ;   the bank is another
    stosw
    mov ax,RBC_TR_LINK
    call rt_jmp
    mov ax,9090h
    stosw
    stosw
    stosb
    jmp short .enter2
.key:
    mov dh,dl                       ; DH = its key; the table's slot
    xor bl,dl
    mov dl,bh
    shr dl,1
    shr dl,1
    shr dl,1
    xor bl,dl
    and bh,7
    shl bx,1
    shl bx,1
    shl bx,1
    cmp [es:JIT_HASH+bx],ax
    jne .link
    cmp [es:JIT_HASH+bx+2],dh
    jne .link
    mov bx,[es:JIT_HASH+bx+4]
    or bx,bx
    jz .link
    mov ax,0378h                    ; js +3 / jmp near the block
    stosw
    mov ax,bx
    call rt_jmp
    jmp short .ev
.link:
    mov ax,0678h                    ; js +6 / mov dx,SITE / jmp tr_link
    stosw
    mov al,0BAh
    stosb
    mov ax,di
    dec ax
    stosw
    mov ax,RBC_TR_LINK
    call rt_jmp
    jmp short .ev
.enter:
    mov ax,0378h                    ; js +3 / jmp tr_enter
    stosw
.enter2:
    mov ax,RBC_TR_ENTER
    call rt_jmp
.ev:
    mov ax,0FF36h                   ; jmp far [ss:S_EVVEC]
    stosw
    mov al,2Eh
    stosb
    mov ax,S_EVVEC
    stosw
    pop dx
    pop bx
    ret

; rt_subbp - sub bp,AL
rt_subbp:
    mov ah,al
    mov al,83h
    stosb
    mov al,0EDh
    stosb
    mov al,ah
    stosb
    ret

; rt_skip - Jcc short over what follows: AL = the opcode. Out: BX = the
; displacement byte's place, for rt_land
rt_skip:
    stosb
    mov bx,di
    xor al,al
    stosb
    ret
rt_land:
    mov ax,di
    sub ax,bx
    dec ax
    mov [es:bx],al
    ret

; -----------------------------------------------------------------------------
; rt_ctl - the control transfer, or the opcode with no template, at Game Boy
; address AX: [RT_OP], [RT_IMM]. Ends the block.
; -----------------------------------------------------------------------------
RT_SKIP_NZ      equ 74h             ; after SAHF, the Jcc that SKIPS a taken
RT_SKIP_Z       equ 75h             ;   NZ / Z / NC / C transfer
RT_SKIP_NC      equ 72h
RT_SKIP_C       equ 73h
rt_skips:       db RT_SKIP_NZ, RT_SKIP_Z, RT_SKIP_NC, RT_SKIP_C

rt_ctl:
    mov si,ax                       ; SI = the instruction's PC
    mov bl,[RT_OP]
    cmp bl,18h
    je .jr
    mov bh,bl
    and bh,0E7h
    cmp bh,20h
    je .jrcc
    cmp bl,0C3h
    je .jp
    cmp bh,0C2h
    je .jpcc
    cmp bl,0CDh
    je .call
    cmp bh,0C4h
    je .callcc
    cmp bl,0C9h
    je .ret
    cmp bh,0C0h
    je .retcc
    mov bh,bl
    and bh,0C7h
    cmp bh,0C7h
    je .rst
    cmp bl,0E9h
    je .jphl
    ; no template and no jump: the interpreter takes it from its PC, in
    ; the core (RB_DISPATCH, through S_DISP)
    mov al,0BEh                     ; mov si,PC / jmp tr_int
    stosb
    mov ax,si
    stosw
    mov ax,RBC_TR_INT
    jmp rt_jmp
.cond:                              ; SAHF and the Jcc that skips: BX = its
    mov al,9Eh                      ;   displacement's place
    stosb
    mov bl,[RT_OP]
    mov cl,3
    shr bl,cl
    and bx,3
    mov al,[cs:rt_skips + bx]
    jmp rt_skip
.jr:
    lea ax,[si+2]
    call rt_jrt
    ret
.jrcc:
    call .cond
    push bx
    lea ax,[si+2]
    call rt_jrt
    pop bx
    call rt_land
    mov al,2
    call rt_subbp
    lea ax,[si+2]
    jmp rt_exit
.jp:
    mov al,4
    call rt_subbp
    mov ax,[RT_IMM]
    jmp rt_exit
.jpcc:
    call .cond
    push bx
    mov al,4
    call rt_subbp
    mov ax,[RT_IMM]
    call rt_exit
    pop bx
    call rt_land
    mov al,3
    call rt_subbp
    lea ax,[si+3]
    jmp rt_exit
.call:
    lea ax,[si+3]
    call rt_push
    mov al,6
    call rt_subbp
    mov ax,[RT_IMM]
    jmp rt_exit
.callcc:
    call .cond
    push bx
    lea ax,[si+3]
    call rt_push
    mov al,6
    call rt_subbp
    mov ax,[RT_IMM]
    call rt_exit
    pop bx
    call rt_land
    mov al,3
    call rt_subbp
    lea ax,[si+3]
    jmp rt_exit
.ret:
    mov al,4
    jmp rt_ret
.retcc:
    call .cond
    push bx
    mov al,5
    call rt_ret
    pop bx
    call rt_land
    mov al,2
    call rt_subbp
    lea ax,[si+1]
    jmp rt_exit
.rst:
    lea ax,[si+1]
    call rt_push
    mov al,4
    call rt_subbp
    mov al,[RT_OP]
    and ax,38h
    jmp rt_exit
.jphl:
    mov ax,0DE89h                   ; mov si,bx
    stosw
    mov al,1
    jmp rt_retds

; rt_push - push the Game Boy address AX: mov dx,AX / push dx / xor dl,dl
rt_push:
    push ax
    mov al,0BAh
    stosb
    pop ax
    stosw
    mov al,52h
    stosb
    mov ax,0D230h
    stosw
    ret

; rt_ret - RET, its M-cycles in AL: pop si, the check, and an INLINE CACHE
; of where this RET went last (tr_retlink fills it): cmp si,PC / jne +3 /
; jmp near BLOCK, else mov dx,SITE / jmp tr_retlink
rt_ret:
    push ax
    mov al,5Eh                      ; pop si
    stosb
    pop ax
    call rt_subbp
    mov ax,0F78h                    ; js +15
    stosw
    push bx
    mov bx,di                       ; SITE
    mov ax,0FE81h                   ; cmp si,0FFFFh: nothing returns there
    stosw
    mov ax,0FFFFh
    stosw
    mov ax,0375h                    ; jne +3
    stosw
    mov al,0E9h                     ; jmp near BLOCK: nowhere yet, the next
    stosb                           ;   instruction
    xor ax,ax
    stosw
    mov al,0BAh                     ; mov dx,SITE / jmp tr_retlink
    stosb
    mov ax,bx
    stosw
    pop bx
    mov ax,RBC_TR_RETLINK
    call rt_jmp
    mov ax,0FF36h                   ; jmp far [ss:S_EVVEC]
    stosw
    mov al,2Eh
    stosb
    mov ax,S_EVVEC
    stosw
    ret

; rt_retds - JP HL's end: SI is set, AL = its M-cycles; the check, tr_enter
rt_retds:
    call rt_subbp
    mov ax,0378h                    ; js +3 / jmp tr_enter / jmp far ev
    stosw
    mov ax,RBC_TR_ENTER
    call rt_jmp
    mov ax,0FF36h
    stosw
    mov al,2Eh
    stosb
    mov ax,S_EVVEC
    stosw
    ret

; rt_jrt - a taken JR whose next PC is AX: its target from [RT_IMM]'s low
; byte, and a spin-wait to it skipped as the interpreter skips one
rt_jrt:
    mov dl,[RT_IMM]
    mov dh,dl
    sar dh,1                        ; sign-extend e (8086: no MOVSX)
    sar dh,1
    sar dh,1
    sar dh,1
    sar dh,1
    sar dh,1
    sar dh,1
    add ax,dx
    mov [RT_T],ax
    cmp dx,0FFFDh                   ; -3, a JR NZ, after DEC A/B/C: a
    jne .nocnt                      ;   countdown (cnt_ff, section 8.1)
    cmp byte [RT_OP],20h
    jne .nocnt
    mov bx,[RT_IX]
    or bx,bx
    jz .nocnt
    mov dl,[JIT_BUF+bx-1]
    cmp dl,3Dh
    je .cnt
    cmp dl,05h
    je .cnt
    cmp dl,0Dh
    jne .nocnt
.cnt:
    mov al,0BEh                     ; mov si,T
    stosb
    mov ax,[RT_T]
    stosw
    mov ax,0C736h                   ; mov word [ss:S_RET],FALLBACK
    stosw
    mov al,06h
    stosb
    mov ax,S_RET
    stosw
    mov ax,di
    add ax,7                        ; past this word, mov dl and the jmp
    stosw
    mov al,0B2h                     ; mov dl,DEC
    stosb
    mov al,dl
    stosb
    mov ax,RBC_CNT_FF
    call rt_jmp
    jmp .plain                      ; FALLBACK: the taken JR as usual
.nocnt:
    cmp dx,0FFF0h                   ; -16..-4: a spin-wait's shape?
    jb .plain
    cmp dx,0FFFCh
    ja .plain
    call rt_idle
    cmp byte [RT_IDLE],0
    je .plain
    cmp byte [RT_IDLE],1
    je .yes
    ; HL's: only while HL is WRAM or HRAM (rbgen's idle_hl)
    mov ax,0FF80h                   ; cmp bh,0C0h
    stosw
    mov al,0C0h
    stosb
    mov al,72h                      ; jb .no
    call rt_skip
    push bx
    mov ax,0FF80h                   ; cmp bh,0FFh
    stosw
    mov al,0FFh
    stosb
    mov ax,0575h                    ; jne .yes: past the cmp and jb below
    stosw
    mov ax,0FB80h                   ; cmp bl,80h
    stosw
    mov al,80h
    stosb
    mov al,72h                      ; jb .no
    call rt_skip
    push bx
    call .emit_yes
    pop bx
    call rt_land
    pop bx
    call rt_land
    jmp short .plain
.yes:
    call .emit_yes
    ret
.emit_yes:
    mov al,0BEh                     ; mov si,T / jmp idle_yes, which
    stosb                           ;   charges the JR's 3 M-cycles itself
    mov ax,[RT_T]
    stosw
    mov ax,RBC_IDLE_YES
    jmp rt_jmp
.plain:
    mov al,3
    call rt_subbp
    mov ax,[RT_T]
    jmp rt_exit

; -----------------------------------------------------------------------------
; rt_idle - is the loop from [RT_T] to the JR at [RT_T]+len a spin-wait?
; REALBOY-SPEC section 8's rule, decided here once rather than at every pass.
; Out: [RT_IDLE] = 0 no, 1 yes, 2 yes while HL is WRAM or HRAM.
; -----------------------------------------------------------------------------
rt_idle:
    push si
    push di
    push es
    mov byte [RT_IDLE],0
    ; the loop's bytes, from wherever they are
    mov si,[RT_T]
    mov bx,[S_VIEW]
    cmp si,4000h
    jb .src
    cmp si,8000h
    jae .r                          ; RAM: never
    mov bx,[S_ROMX]
.src:
    push ds
    pop es
    mov di,RT_LOOP
    mov cx,16
    push ds
    mov ds,bx
    rep movsb
    pop ds
    ; L = the body's length: the JR is at [RT_T] + L
    mov ax,[RT_IX]
    add ax,[RT_PC0]
    sub ax,[RT_T]                   ; AX = L
    cmp ax,14
    ja .r
    mov dh,al                       ; DH = L
    mov dl,[RT_LOOP]
    cmp dl,0FAh
    je .fa
    cmp dl,0F0h
    je .f0
    cmp dl,7Eh
    je .hl1
    cmp dl,0CBh
    jne .r
    cmp dh,2                        ; BIT b,(HL) alone
    jne .r
    mov dl,[RT_LOOP+1]
    and dl,0C7h
    cmp dl,46h
    jne .r
    mov byte [RT_IDLE],2
    jmp short .r
.hl1:
    mov cl,1
    mov ch,2
    jmp short .walk
.f0:
    cmp byte [RT_LOOP+1],80h
    jb .r
    mov cl,2
    mov ch,1
    jmp short .walk
.fa:
    mov al,[RT_LOOP+2]
    cmp al,0C0h
    jb .r
    cmp al,0FFh
    jne .fa1
    cmp byte [RT_LOOP+1],80h
    jb .r
.fa1:
    mov cl,3
    mov ch,1
.walk:                              ; CL = the place, DH = L, CH = the answer
    cmp cl,dh
    jae .r                          ; a read and no test
.t:
    mov bl,cl
    xor bh,bh
    mov al,[RT_LOOP+bx]
    cmp al,0A7h
    je .one
    cmp al,0B7h
    je .one
    cmp al,0FEh
    je .two
    cmp al,0E6h
    je .two
    cmp al,0CBh
    jne .jrc
    mov al,[RT_LOOP+bx+1]
    and al,0C7h
    cmp al,47h
    je .two
    jmp short .r
.jrc:
    and al,0E7h
    cmp al,20h
    jne .r
    mov al,[RT_LOOP+bx+1]
    add al,cl
    add al,2
    jz .two
    js .r
    mov ah,dh
    add ah,2
    cmp al,ah
    jb .r
.two:
    inc cl
.one:
    inc cl
    cmp cl,dh
    jb .t
    jne .r
    mov [RT_IDLE],ch
.r:
    pop es
    pop di
    pop si
    ret
