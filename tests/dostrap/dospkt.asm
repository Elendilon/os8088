; DOSPKT.COM - a Crynwr packet driver client, for os8088's own (SPEC.md 96.23).
; OURS, MIT with the rest of the tree.
;
; WHY THIS EXISTS. mTCP is the validation target for wave 4 and mTCP is the
; CLIENT half - GPL, not in this repository, and a program whose verdict we
; cannot read (SPEC.md 96.18.3 makes that argument at length about Creative's
; TEST-SBC). This asks the same questions a client asks and prints the answers
; where a test can assert on them.
;
; It runs unchanged under a real DOS with a real packet driver, which is the
; whole of docs/DOS-DEBUGGING.md's method: two sides, one binary, diff.
;
; WHAT IT DOES, in the order a client does it:
;   1. walk 60h..80h for `PKT DRVR` at offset 3
;   2. driver_info          - version, class, type, functionality
;   3. access_type          - a handle for ARP (0806), receiver registered
;   4. get_address          - our own station address
;   5. send_pkt             - a broadcast ARP request for the gateway, which
;                             is a frame a real host must answer
;   6. spin on the tick     - the reply arrives through the UP-CALL, which is
;                             the half no other row here can reach
;   7. release_type
;
; Every line is `NAME value`, which is tests/dosirq.py's parser.
    org 0x100
    cpu 8086

VEC_LO      equ 0x60
VEC_HI      equ 0x80
ETY_ARP     equ 0x0806
RXMAX       equ 1514

; the gateway QEMU's slirp always puts at 10.0.2.2, and the address its DHCP
; hands our own stack. Both are facts about the harness (SPEC.md 72.9) and the
; program prints what it used, so a different net is a readable failure.
GW_IP       db 10, 0, 2, 2
MY_IP       db 10, 0, 2, 15

start:
    mov sp, stack_top
    cld                             ; **THE FRAME IS BUILT WITH rep stosb AND
                                    ; rep movsb**, and nothing promises a DOS
                                    ; program DF=0 on entry. Without this the
                                    ; frame is assembled BACKWARDS out of the
                                    ; buffer and what goes on the wire is
                                    ; whatever the image had there
    mov ax, 0x0003                  ; **CLEAR THE SCREEN FIRST.** The bracket
    int 0x10                        ; puts the adapter in FSXM_TEXT80 and does
                                    ; not blank it, so what a program writes
                                    ; lands in the middle of the desktop's own
                                    ; framebuffer read as characters - which is
                                    ; unreadable, and looks exactly like a
                                    ; program that crashed

    call find_driver
    jnc .found
    mov dx, s_nodrv
    call puts
    jmp done
.found:
    mov dx, s_vec
    call puts
    mov al, [pktvec]
    call puthex8
    call crlf

    call driver_info
    call do_access
    jnc .acc
    mov dx, s_noacc
    call puts
    jmp done
.acc:
    call get_address
    call send_arp
    call wait_rx
    call release

done:
    mov dx, s_ready
    call puts
    mov ah, 0                       ; **IT HOLDS THE SCREEN**, the way
    int 0x16                        ; tests/dosirq's own probe does: the box
    mov ax, 0x4C00                  ; has no windowed text yet (wave 6), so a
    int 0x21                        ; program that exits takes its output with
                                    ; it and the only reader is a screenshot
                                    ; taken while the bracket is still up

; -----------------------------------------------------------------------------
; find_driver - the signature at offset 3 is the whole of how a client finds one
; -----------------------------------------------------------------------------
find_driver:
    push es
    mov bl, VEC_LO
.v:
    xor bh, bh
    mov ax, bx
    shl ax, 1
    shl ax, 1
    mov si, ax
    xor ax, ax
    mov es, ax
    mov ax, [es:si+2]
    mov di, [es:si]
    or ax, ax
    jz .next
    push ds
    mov ds, ax
    mov si, di
    add si, 3
    push cs
    pop es
    mov di, s_sig
    mov cx, 8
    repe cmpsb
    pop ds
    jcxz .got
.next:
    inc bl
    cmp bl, VEC_HI
    jbe .v
    pop es
    stc
    ret
.got:
    mov [pktvec], bl
    mov al, bl                      ; build the INT the calls go through: an
    mov [callvec+2], al             ; 8086 has no `int reg`, so the opcode is
    pop es                          ; patched once and called from then on
    clc
    ret

; --- callvec - `int <pktvec>`, written by find_driver ------------------------
;
; **IT PRESERVES DS, AND THAT IS NOT TIDINESS.** `driver_info` is DEFINED to
; return DS:SI pointing at the driver's name, so a client that calls it and
; keeps going runs with the DRIVER's segment as its own data segment from then
; on. Every symptom of that is somewhere else: the strings print as garbage,
; the frame handed to send_pkt is read out of the driver's image, and the
; ethertype access_type is given is two bytes of somebody else's code - so no
; arriving frame ever matches the handle and the receive path looks broken.
; `get_statistics` returns DS:SI the same way.
;
; mTCP saves DS around these calls. Ours did not, and it cost most of a
; session (SPEC.md 96.23.9).
callvec:
    push ds
    db 0xCD, 0x60
    pop ds
    ret

; -----------------------------------------------------------------------------
driver_info:
    mov ah, 1
    mov al, 0xFF
    call callvec
    jc .no
    push cx
    push dx
    mov dx, s_ver
    call puts
    mov ax, bx
    call puthex16
    call crlf
    pop dx
    pop cx
    push cx
    mov dx, s_class
    call puts
    mov al, ch
    call puthex8
    call crlf
    pop cx
    ret
.no:
    mov dx, s_noinfo
    call puts
    ret

; -----------------------------------------------------------------------------
; do_access - a handle for ARP, with our receiver on it
; -----------------------------------------------------------------------------
do_access:
    mov ah, 2
    mov al, 1                       ; if_class: DIX Ethernet
    mov bx, 0xFFFF                  ; if_type: any
    mov dl, 0                       ; if_number
    mov si, arp_type
    mov cx, 2
    push cs
    pop es
    mov di, receiver
    call callvec
    jc .no
    mov [handle], ax
    push ax
    mov dx, s_hand
    call puts
    pop ax
    call puthex16
    call crlf
    clc
    ret
.no:
    mov [lasterr], dh
    stc
    ret

; -----------------------------------------------------------------------------
get_address:
    mov ah, 6
    mov bx, [handle]
    push cs
    pop es
    mov di, mymac
    mov cx, 6
    call callvec
    jc .no
    mov dx, s_mac
    call puts
    mov si, mymac
    mov cx, 6
.l:
    lodsb
    call puthex8
    loop .l
    call crlf
    ret
.no:
    mov dx, s_nomac
    call puts
    ret

; -----------------------------------------------------------------------------
; send_arp - a broadcast ARP request for the gateway
;
; A REAL FRAME A REAL HOST MUST ANSWER, which is what makes this row worth
; having: a send that is merely accepted proves the call and not the wire.
; -----------------------------------------------------------------------------
; **THE FRAME IS A TABLE, NOT A DRAWING.** It was built field by field with
; rep stosb/rep movsb, and that is eleven chances to be wrong about DF, about
; ES, and about byte order - for a frame whose every byte but the two MAC
; fields is a constant. A static template is checkable by eye against the
; RFC, and all this routine does is poke in the address the driver gave us.
send_arp:
    mov si, mymac                   ; source, twice: the Ethernet header's and
    mov di, txbuf + 6               ; the ARP sender's
    mov cx, 6
    call cpy
    mov si, mymac
    mov di, txbuf + 14 + 8
    mov cx, 6
    call cpy

    mov ah, 4
    mov si, txbuf
    mov cx, TXLEN
    call callvec
    jc .no
    mov dx, s_tx
    call puts
    mov al, 1
    call puthex8
    call crlf
    ret
.no:
    mov dx, s_notx
    call puts
    mov al, dh
    call puthex8
    call crlf
    ret

; -----------------------------------------------------------------------------
; wait_rx - spin on the BIOS tick while the up-call does the work
;
; **NOTHING HERE POLLS THE DRIVER.** That is the point: a Crynwr client does
; not, and if frames only arrived when we asked for them the box would be
; passing a test no real client would pass.
; -----------------------------------------------------------------------------
wait_rx:
    push es
    xor ax, ax
    mov es, ax
    mov bx, [es:0x46C]              ; the BDA tick, our only clock
    add bx, 55                      ; ~3 seconds at 18.2 Hz
.w:
    mov ax, [es:0x46C]
    cmp ax, bx
    jae .out
    cmp word [nrx], 0               ; ...but stop early once the reply is in,
    je .w                           ; so a passing run is not a slow one
    cmp word [narp], 0
    je .w
.out:
    pop es
    mov dx, s_rx
    call puts
    mov ax, [nrx]
    call puthex16
    call crlf
    mov dx, s_arp
    call puts
    mov ax, [narp]
    call puthex16
    call crlf
    mov dx, s_ety
    call puts
    mov ax, [firstety]
    call puthex16
    call crlf
    ret

; -----------------------------------------------------------------------------
release:
    mov ah, 3
    mov bx, [handle]
    call callvec
    ret

; -----------------------------------------------------------------------------
; receiver - THE UP-CALL, called twice per frame by the driver
;
;   AX=0  give me somewhere to put CX bytes -> ES:DI, or 0:0 to refuse
;   AX=1  here it is, in DS:SI, CX bytes
;
; Far, and it may be entered at ANY time - from the driver's tick - so every
; reference here is through CS and nothing assumes DS.
; -----------------------------------------------------------------------------
receiver:
    or ax, ax
    jnz .have
    cmp cx, RXMAX                   ; a frame we have no room for is REFUSED,
    ja .refuse                      ; which is the contract rather than a
    cmp word [cs:rxbusy], 0         ; failure (SPEC.md 96.23.4.2)
    jne .refuse
    mov word [cs:rxbusy], 1
    mov [cs:rxlen], cx
    push cs
    pop es
    mov di, rxbuf
    retf
.refuse:
    xor ax, ax
    mov es, ax
    xor di, di
    retf
.have:
    push ax
    push bx
    push cx
    push si
    push ds
    push cs
    pop ds
    inc word [nrx]
    mov ax, [rxbuf+12]              ; the ethertype, as it sits on the wire
    xchg al, ah
    cmp word [firstety], 0
    jne .notfirst
    mov [firstety], ax
.notfirst:
    cmp ax, ETY_ARP
    jne .out
    mov al, [rxbuf+14+7]            ; ARP oper, low byte: 2 = a REPLY
    cmp al, 2
    jne .out
    inc word [narp]
.out:
    mov word [rxbusy], 0
    pop ds
    pop si
    pop cx
    pop bx
    pop ax
    retf

; -----------------------------------------------------------------------------
; the console, in the two calls every DOS has
; -----------------------------------------------------------------------------
puts:
    push ax
    mov ah, 9
    int 0x21
    pop ax
    ret

crlf:
    push ax
    push dx
    mov dx, s_crlf
    mov ah, 9
    int 0x21
    pop dx
    pop ax
    ret

puthex16:
    push ax
    mov al, ah
    call puthex8
    pop ax
    call puthex8
    ret

puthex8:
    push ax
    push cx
    push dx
    mov cl, 4
    mov ch, al
    shr al, cl
    call .nyb
    mov al, ch
    and al, 0x0F
    call .nyb
    pop dx
    pop cx
    pop ax
    ret
.nyb:
    add al, '0'
    cmp al, '9'
    jbe .p
    add al, 7
.p:
    push dx
    mov dl, al
    mov ah, 2
    int 0x21
    pop dx
    ret

; -----------------------------------------------------------------------------
; --- cpy - DS:SI -> DS:DI, CX bytes, no string instruction and no ES -------
cpy:
    push ax
    push cx
    push si
    push di
    jcxz .out
.l:
    mov al, [si]
    mov [di], al
    inc si
    inc di
    loop .l
.out:
    pop di
    pop si
    pop cx
    pop ax
    ret

arp_type:   db 0x08, 0x06           ; the ethertype access_type is given, in
                                    ; wire order - which is what the spec says
                                    ; and what makes a big-endian compare right

s_sig:      db 'PKT DRVR'
s_crlf:     db 13, 10, '$'
s_vec:      db 'PKTVEC $'
s_ver:      db 'VER $'
s_class:    db 'CLASS $'
s_hand:     db 'HANDLE $'
s_mac:      db 'MAC $'
s_tx:       db 'TX $'
s_rx:       db 'RX $'
s_arp:      db 'ARP $'
s_ety:      db 'ETY $'
s_nodrv:    db 'NODRV 1', 13, 10, '$'
s_noacc:    db 'NOACC 1', 13, 10, '$'
s_noinfo:   db 'NOINFO 1', 13, 10, '$'
s_nomac:    db 'NOMAC 1', 13, 10, '$'
s_notx:     db 'NOTX $'
s_ready:    db 'READY', 13, 10, '$'

pktvec:     db 0
lasterr:    db 0
handle:     dw 0
nrx:        dw 0
narp:       dw 0
firstety:   dw 0
rxbusy:     dw 0
rxlen:      dw 0
mymac:      times 6 db 0
; --- the ARP request, as a template (every byte but the MACs is a constant) --
txbuf:
            db 0xFF,0xFF,0xFF,0xFF,0xFF,0xFF    ; +0  destination: broadcast
            times 6 db 0                        ; +6  source: poked in
            db 0x08, 0x06                       ; +12 ethertype ARP
            db 0x00, 0x01                       ; +14 htype: Ethernet
            db 0x08, 0x00                       ; +16 ptype: IPv4
            db 6                                ; +18 hlen
            db 4                                ; +19 plen
            db 0x00, 0x01                       ; +20 oper: REQUEST
            times 6 db 0                        ; +22 sender hardware: poked in
            db 10, 0, 2, 15                     ; +28 sender protocol
            times 6 db 0                        ; +32 target hardware: unknown
            db 10, 0, 2, 2                      ; +38 target protocol: the
TXLEN       equ 42                              ;     gateway QEMU always has
            times 64 - TXLEN db 0
rxbuf:      times RXMAX db 0
            times 256 db 0
stack_top:
