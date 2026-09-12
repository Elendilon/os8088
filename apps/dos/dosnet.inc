; =============================================================================
; os8088 - apps/dos/dosnet.inc
;
; THE CABLE TRANSLATION (SPEC.md 96.26, docs/plans/DOS-CABLE-NET-PLAN.md)
;
; **A slirp in reverse.** The DOS program believes it is on an Ethernet: it
; ARPs, it builds IP headers, it runs its own TCP. Every frame it emits is
; terminated HERE and re-issued as a socket verb; every socket byte that
; arrives is wrapped in a header and handed back through §96.23.4's up-call.
;
; WHY, AND IT IS LATENCY RATHER THAN BANDWIDTH. The obvious design relays raw
; frames over the cable, and at PERFORMANCE.md Set 39's 3,741 B/s a frame is
; 0.405 s each way - so one round trip is 0.81 s, which sits on the edge of
; mTCP's own retransmit timeout. The first queue behind a data frame tips it
; into permanent retransmit. Translating sends only PAYLOAD and answers every
; acknowledgement locally in microseconds, so the client measures an RTT of
; about zero and its timers never fire.
;
; **IT DOES NOT KNOW WHICH WIRE IS UNDER IT.** Everything here goes through
; NETV_OPEN/STATUS/SEND/RECV/CLOSE, and both drivers answer those - the card
; and the cable. [net_cls] is the whole difference, which is why this is
; developed and tested against ETHER.DRV under QEMU (DOSNETCARD=1) and works
; over NET.DRV unchanged.
;
; WHAT IT IS NOT: there is no ICMP (so no ping) and no UDP but the DNS port
; below, because the socket ABI has neither. Every TCP application works.
; =============================================================================

; --- THE ROUTER'S OWN ADDRESS, and it is image data rather than bss ---------
; A locally-administered unicast MAC: bit 1 of the first byte set, bit 0 clear
; (so it is not multicast), which is the range IEEE reserves for exactly this.
; It never reaches a wire - the client is the only thing that ever reads it -
; but a client that saw a multicast bit here would refuse to ARP for us.
dn_gwmac:   db 0x02, 'o', 's', '8', '8', 0x01

; --- ...and the one we tell the CLIENT it has -------------------------------
; There is no PROM to read on this path, so get_address has to answer
; something (SPEC.md 96.26.4). One digit off the gateway's: a client that saw
; its own address as a frame's source would drop it as a loop.
dn_ourmac:  db 0x02, 'o', 's', '8', '8', 0x02

; -----------------------------------------------------------------------------
; dn_init - the translation is the route; forget everything
; out: nothing
; -----------------------------------------------------------------------------
dn_init:
    push ax
    push bx
    push cx
    mov bx, dn_flows
    mov cx, DN_NFLOW
.f:
    mov byte [bx+DN_F_USED], 0
    add bx, DN_F_SIZE
    loop .f
    mov bx, dn_names
    mov cx, DN_NNAME
.n:
    mov byte [bx+DN_N_USED], 0
    add bx, DN_N_SIZE
    loop .n
    mov word [dn_pend], 0
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dn_shut - every flow closed, on the way out of the bracket
; -----------------------------------------------------------------------------
dn_shut:
    push ax
    push bx
    push cx
    mov bx, dn_flows
    mov cx, DN_NFLOW
.f:
    cmp byte [bx+DN_F_USED], 0
    je .next
    push bx
    push cx
    mov al, [bx+DN_F_HAND]
    mov bh, [net_cls]
    mov bl, NETV_CLOSE
    call OSAPI_DRV_CALL
    pop cx
    pop bx
    mov byte [bx+DN_F_USED], 0
.next:
    add bx, DN_F_SIZE
    loop .f
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dn_tx - ONE frame from the client, CX bytes at DS:SI (our own segment)
;
; This is NETV_RAWTX's place in the routing (SPEC.md 96.26.1). It always
; reports success: a frame we do not understand is DROPPED, which is what a
; real wire does to a packet nothing answers, and a client that mistook a
; refusal for a dead card would stop trying.
; out: CF=0 always
; -----------------------------------------------------------------------------
dn_tx:
    push ax
    push bx
    push cx
    push si
    push di
    cmp cx, DN_EH_LEN
    jbe .drop
    mov ax, [si+DN_EH_TYP]          ; the ethertype, wire order
    xchg al, ah
    cmp ax, NET_ETY_ARP
    je .arp
    cmp ax, NET_ETY_IP
    jne .drop
    cmp cx, DN_TCP
    jb .drop
    cmp byte [si+DN_IP_VIHL], 0x45  ; v4, no options - the same refusal
    jne .drop                       ; eth_frame makes, for its reason
    mov al, [si+DN_IP_PROTO]
    cmp al, DN_IPP_TCP
    je .tcp
    cmp al, DN_IPP_UDP
    je .udp
.drop:
    pop di
    pop si
    pop cx
    pop bx
    pop ax
    clc
    ret
.arp:
    call dn_arp
    jmp short .drop
.udp:
    call dn_udp
    jmp short .drop
.tcp:
    call dn_tcp_in
    jmp short .drop

; -----------------------------------------------------------------------------
; dn_arp - answer it, whatever it asked for (SPEC.md 96.26.1)
; in:  SI = the frame, CX = its length
;
; **WE ARE THE WHOLE SEGMENT.** There is no wire to forward an ARP onto, so
; every request gets the same synthetic MAC and the client's routing table
; collapses to "everything is one hop away". That is exactly true here.
; -----------------------------------------------------------------------------
dn_arp:
    push ax
    push cx
    push si
    push di
    cmp cx, DN_ARP_END
    jb .out
    mov ax, [si+DN_ARP_OP]
    cmp ax, 0x0100                  ; oper 1, wire order: a REQUEST
    jne .out

    mov di, dn_frame                ; --- build the reply ---
    push si
    mov cx, 6                       ; destination: whoever asked
    add si, DN_ARP_SHA
    call dn_copy
    pop si
    mov di, dn_frame + DN_EH_SRC
    push si
    mov si, dn_gwmac                ; source: us, the router
    mov cx, 6
    call dn_copy
    pop si
    mov word [dn_frame+DN_EH_TYP], 0x0608   ; ARP, wire order
    mov word [dn_frame+DN_EH_LEN+0], 0x0100 ; htype 1
    mov word [dn_frame+DN_EH_LEN+2], 0x0008 ; ptype IPv4
    mov byte [dn_frame+DN_EH_LEN+4], 6
    mov byte [dn_frame+DN_EH_LEN+5], 4
    mov word [dn_frame+DN_ARP_OP], 0x0200   ; oper 2: a REPLY
    mov di, dn_frame + DN_ARP_SHA
    push si
    mov si, dn_gwmac                ; sender hardware: us
    mov cx, 6
    call dn_copy
    pop si
    push si                         ; sender protocol: WHATEVER WAS ASKED FOR,
    add si, DN_ARP_TPA              ; copied straight back out of the request
    mov di, dn_frame + DN_ARP_SPA
    mov cx, 4
    call dn_copy
    pop si
    push si                         ; target hardware and protocol: the asker
    add si, DN_ARP_SHA
    mov di, dn_frame + DN_ARP_THA
    mov cx, 6
    call dn_copy
    pop si
    push si
    add si, DN_ARP_SPA
    mov di, dn_frame + DN_ARP_TPA
    mov cx, 4
    call dn_copy
    pop si
    mov word [dn_pend], DN_ARP_END  ; ...and it is waiting for the next poll
.out:
    pop di
    pop si
    pop cx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dn_ready - is there a frame for the client, and how long is it?
; out: CF=0 and CX = its length, IN dn_frame; CF=1 = nothing waiting
;
; **IT DOES NOT COPY, and that is why it is not shaped like NETV_RAWRX.** The
; card path's frame arrives in a heap claim and has to be moved into a buffer
; the caller names; ours was BUILT in dn_frame, in the one segment everything
; here shares, so a copy would be from our own bss to our own bss. The
; up-call's own copy to the client is the only one on this path.
;
; Two sources, and the order matters: a frame already staged - an ARP reply, a
; reset - goes first, because it is an answer the client is blocked on. Only
; then is a socket asked for data.
; -----------------------------------------------------------------------------
dn_ready:
    cmp word [dn_pend], 0
    jne .have
    call dn_pump                    ; nothing staged, so try the sockets
    cmp word [dn_pend], 0
    je .none
.have:
    mov cx, [dn_pend]
    mov word [dn_pend], 0
    clc
    ret
.none:
    stc
    ret

; -----------------------------------------------------------------------------
; dn_copy - DS:SI -> DS:DI, CX bytes. One segment, so no override and no
;           string instruction whose DF we would have to trust.
; -----------------------------------------------------------------------------
dn_copy:
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

; -----------------------------------------------------------------------------
; dn_cksum - the one's-complement sum of CX bytes at SI, folded to 16 bits
; out: AX = the value to STORE (already complemented)
;
; The carry is folded back on every word rather than collected and added at
; the end - the end-around carry is what makes that identical, and it removes
; the second fold that a collector needs and that is easy to forget.
; -----------------------------------------------------------------------------
dn_cksum:
    push bx
    push cx
    push dx
    push si
    xor bx, bx
    mov dl, cl                      ; bank the ODDNESS before CX becomes words
    and dl, 1
    shr cx, 1
    jz .tail
.w:
    mov ah, [si]                    ; wire order: the first byte is the HIGH
    mov al, [si+1]                  ; half of the word
    add bx, ax
    adc bx, 0
    inc si
    inc si
    loop .w
.tail:
    or dl, dl                       ; an odd length pads with a zero LOW byte
    jz .done
    mov ah, [si]
    xor al, al
    add bx, ax
    adc bx, 0
.done:
    mov ax, bx
    not ax
    pop si
    pop dx
    pop cx
    pop bx
    ret

; -----------------------------------------------------------------------------
; dn_get32 / dn_put32 - a 32-bit wire field, in DX:AX
;
; TCP's sequence numbers are the one place this file needs arithmetic wider
; than the machine. They are stored in the flow the same way they arrive - as
; DX:AX pairs in host order - and converted only at the header, because every
; comparison and every addition happens in the pair and only the wire cares
; which end is which.
; in:  get  SI = the field.  put  DI = the field, DX:AX = the value
; -----------------------------------------------------------------------------
dn_get32:
    mov ah, [si]                    ; big-endian: byte 0 is the most
    mov al, [si+1]                  ; significant
    mov dx, ax
    mov ah, [si+2]
    mov al, [si+3]
    ret

dn_put32:
    xchg dh, dl
    mov [di], dx
    xchg dh, dl
    xchg ah, al
    mov [di+2], ax
    xchg ah, al
    ret

; -----------------------------------------------------------------------------
; dn_flow - the flow this frame belongs to, by the client's port
; in:  SI = the frame
; out: CF=0 and BX = the flow; CF=1 = none
; -----------------------------------------------------------------------------
dn_flow:
    push ax
    push cx
    mov ax, [si+DN_T_SPORT]         ; wire order both sides, so no swap
    mov bx, dn_flows
    mov cx, DN_NFLOW
.l:
    cmp byte [bx+DN_F_USED], 0
    je .next
    cmp [bx+DN_F_LPORT], ax
    je .got
.next:
    add bx, DN_F_SIZE
    loop .l
    pop cx
    pop ax
    stc
    ret
.got:
    pop cx
    pop ax
    clc
    ret

; --- dn_flow_new - a free flow, or CF=1 -------------------------------------
dn_flow_new:
    push cx
    mov bx, dn_flows
    mov cx, DN_NFLOW
.l:
    cmp byte [bx+DN_F_USED], 0
    je .got
    add bx, DN_F_SIZE
    loop .l
    pop cx
    stc
    ret
.got:
    pop cx
    clc
    ret

; =============================================================================
; THE DNS HIJACK (SPEC.md 96.26.2)
; =============================================================================
; There is no UDP in the socket ABI, so a DNS query cannot be relayed - and
; that is the best simplification in this file rather than its hard edge,
; because NETV_OPEN takes a host NAME and the far side resolves it.
;
; So: remember the name, answer with a synthetic address out of 10.88.0.0/24,
; and when the client connects to that address, open the NAME. We never need a
; resolver, a cache or a UDP path of our own.
; -----------------------------------------------------------------------------
; dn_udp - a UDP datagram from the client. Port 53 is ours; the rest is
;          dropped, which is what an unrouted datagram deserves.
; in:  SI = the frame, CX = its length
; -----------------------------------------------------------------------------
dn_udp:
    push ax
    cmp cx, DN_UDP + 8 + 12
    jb .out
    mov ax, [si+DN_UDP+2]           ; the DESTINATION port, wire order
    cmp ax, 0x3500                  ; 53
    jne .out
    call dn_dns
.out:
    pop ax
    ret

; -----------------------------------------------------------------------------
; dn_dns - one query in, one A record out
; in:  SI = the frame
;
; It reads ONE question and answers it, which is all any resolver in a DOS
; program sends. The QNAME is copied out in its wire form - length-prefixed
; labels - and flattened to dots, because that is the shape NETV_OPEN wants.
; -----------------------------------------------------------------------------
dn_dns:
    push ax
    push bx
    push cx
    push dx
    push si
    push di

    mov di, si
    add di, DN_UDP + 8              ; the DNS header
    cmp word [di+4], 0x0100         ; exactly one question, wire order
    jne .out

    ; --- the QNAME, labels to dots ----------------------------------------
    mov bx, di
    add bx, 12                      ; the question starts after the header
    mov si, bx
    mov di, dn_qname
    xor cx, cx                      ; CX = how long the flattened name is
.lab:
    mov al, [si]
    or al, al
    jz .named                       ; the root label ends it
    test al, 0xC0                   ; a POINTER has no business in a query and
    jnz .out                        ; following one here would be a loop we
                                    ; have no budget to detect
    inc si
    xor ah, ah
    push ax
    add cx, ax
    inc cx                          ; ...and the dot
    cmp cx, DN_NAMEMAX - 1
    jae .outp                       ; a name longer than we can hold is a
                                    ; refusal, not a truncation
    pop ax
    mov cx, ax
.cp:
    mov al, [si]
    mov [di], al
    inc si
    inc di
    loop .cp
    mov byte [di], '.'
    inc di
    jmp short .lab
.outp:
    pop ax
    jmp short .out
.named:
    cmp di, dn_qname                ; an empty name is not a question
    je .out
    dec di                          ; ...and the trailing dot comes off
    mov byte [di], 0

    ; --- remember it, and answer with the slot's own address ---------------
    call dn_name_put                ; AL = the pool index, CF=1 = full
    jc .out
    mov [dn_lastip], al
    call dn_dns_reply
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dn_name_put - remember dn_qname, and say which synthetic address it is
; out: CF=0 and AL = the last octet; CF=1 = no room
;
; A name already known keeps its address, so a client that resolves twice and
; connects once still connects to the right thing.
; -----------------------------------------------------------------------------
dn_name_put:
    push bx
    push cx
    push si
    push di
    mov bx, dn_names                ; --- pass 1: do we know it already? ---
    xor cl, cl
.known:
    cmp byte [bx+DN_N_USED], 0
    je .knext
    mov si, dn_qname
    mov di, bx
    add di, DN_N_NAME
    call dn_streq
    je .hit
.knext:
    add bx, DN_N_SIZE
    inc cl
    cmp cl, DN_NNAME
    jb .known
    mov bx, dn_names                ; --- pass 2: a free slot? ---
    xor cl, cl
.free:
    cmp byte [bx+DN_N_USED], 0
    je .take
    add bx, DN_N_SIZE
    inc cl
    cmp cl, DN_NNAME
    jb .free
    mov bx, dn_names                ; --- FULL: slot 0 goes ---
    xor cl, cl                      ; A name we cannot answer is a connection
                                    ; that fails, and the client has just said
                                    ; which name it cares about NOW. Four is
                                    ; more than any one program resolves at a
                                    ; time, so this is the pathological case
                                    ; and not the ordinary one
.take:
    mov byte [bx+DN_N_USED], 1
    mov si, dn_qname
    mov di, bx
    add di, DN_N_NAME
    push cx                         ; CL IS THE SLOT and dn_copy wants CX for
    mov cx, DN_NAMEMAX              ; the count - it preserves CX, so what
    call dn_copy                    ; comes back is the count and not the slot
    pop cx
.hit:
    mov al, cl
    add al, DN_POOL0
    pop di
    pop si
    pop cx
    pop bx
    clc
    ret

; --- dn_streq - is the NUL string at SI the same as the one at DI? ----------
; out: ZF=1 = equal
dn_streq:
    push si
    push di
    push ax
.l:
    mov al, [si]
    cmp al, [di]
    jne .no
    or al, al
    jz .yes
    inc si
    inc di
    jmp short .l
.yes:
    pop ax
    pop di
    pop si
    cmp al, al                      ; ZF=1, touching nothing else
    ret
.no:
    pop ax
    pop di
    pop si
    or al, 1                        ; ZF=0
    ret

; -----------------------------------------------------------------------------
; dn_ip_out - wrap dn_frame's payload in Ethernet + IP and stage it
; in:  SI = the frame the client SENT (its addresses are reversed into ours),
;      AL = the IP protocol, CX = the payload's length past DN_TCP,
;      [dn_lastip] = the last octet of the source we claim to be
; out: [dn_pend] = the whole frame's length
; -----------------------------------------------------------------------------
dn_ip_out:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov dl, al                      ; the protocol, banked
    mov bx, cx                      ; ...and the payload length

    mov di, dn_frame                ; --- Ethernet: back to whoever sent it ---
    push si
    add si, DN_EH_SRC
    mov cx, 6
    call dn_copy
    pop si
    mov di, dn_frame + DN_EH_SRC
    push si
    mov si, dn_gwmac
    mov cx, 6
    call dn_copy
    pop si
    mov word [dn_frame+DN_EH_TYP], 0x0008   ; IPv4, wire order

    mov byte [dn_frame+DN_IP_VIHL], 0x45    ; --- IP ---
    mov byte [dn_frame+DN_EH_LEN+1], 0      ; no DSCP
    mov ax, bx
    add ax, DN_IP_HLEN
    xchg al, ah
    mov [dn_frame+DN_IP_LEN], ax            ; total length, wire order
    mov word [dn_frame+DN_EH_LEN+4], 0      ; id: nothing here fragments, and
    mov word [dn_frame+DN_EH_LEN+6], 0      ; flags/offset with it
    mov byte [dn_frame+DN_IP_TTL], 64
    mov [dn_frame+DN_IP_PROTO], dl
    mov word [dn_frame+DN_IP_CK], 0         ; zero ACROSS the sum, always
    push si                                 ; source: the address the client
    add si, DN_IP_DST                       ; was TALKING to, straight back
    mov di, dn_frame + DN_IP_SRC
    mov cx, 4
    call dn_copy
    pop si
    push si                                 ; ...and destination: its own
    add si, DN_IP_SRC
    mov di, dn_frame + DN_IP_DST
    mov cx, 4
    call dn_copy
    pop si
    mov si, dn_frame + DN_EH_LEN
    mov cx, DN_IP_HLEN
    call dn_cksum
    xchg al, ah
    mov [dn_frame+DN_IP_CK], ax
    mov ax, bx
    add ax, DN_TCP
    mov [dn_pend], ax
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dn_dns_reply - the question back, plus one A record pointing at us
; in:  SI = the query frame, [dn_lastip] = the address to answer with
;
; The answer is the QUESTION COPIED BACK with an answer appended, which is
; what every resolver accepts and what keeps this free of a name encoder: the
; labels we would have to emit are already on the wire in front of us.
; -----------------------------------------------------------------------------
dn_dns_reply:
    push ax
    push bx
    push cx
    push dx
    push si
    push di

    mov bx, si
    add bx, DN_UDP + 8              ; the query's DNS header
    mov cx, [si+DN_UDP+4]           ; the UDP length, wire order
    xchg cl, ch
    sub cx, 8                       ; ...so this is the DNS message's length
    cmp cx, 12
    jb .out
    cmp cx, 400                     ; a query we would not fit an answer
    ja .out                         ; behind is one we decline to answer

    mov di, dn_frame + DN_UDP + 8   ; --- the DNS message, copied whole ---
    push cx
    mov si, bx
    call dn_copy
    pop cx
    mov di, dn_frame + DN_UDP + 8
    mov word [di+2], 0x8081         ; QR=1, RD=1, RA=1 - wire order of 0x8180
    mov word [di+6], 0x0100         ; ANCOUNT = 1
    mov word [di+8], 0              ; ...and no authority or additional
    mov word [di+10], 0

    add di, cx                      ; --- the answer, after the question ---
    mov word [di+0], 0x0CC0         ; NAME: a pointer to offset 12, which is
                                    ; where the question's own name sits
    mov word [di+2], 0x0100         ; TYPE A
    mov word [di+4], 0x0100         ; CLASS IN
    mov word [di+6], 0              ; TTL: 30 seconds, wire order. Short on
    mov word [di+8], 0x1E00         ; purpose - the mapping lives in four
                                    ; slots and a client that cached for an
                                    ; hour would outlive its own entry
    mov word [di+10], 0x0400        ; RDLENGTH 4
    mov byte [di+12], 10            ; ...and the address: 10.88.0.N
    mov byte [di+13], 88
    mov byte [di+14], 0
    mov al, [dn_lastip]
    mov [di+15], al
    add cx, 16                      ; the DNS message is that much longer

    mov ax, [si+DN_UDP+2]           ; --- UDP: the ports, swapped ---
    mov [dn_frame+DN_UDP+0], ax
    mov ax, [si+DN_UDP+0]
    mov [dn_frame+DN_UDP+2], ax
    mov ax, cx
    add ax, 8
    xchg al, ah
    mov [dn_frame+DN_UDP+4], ax     ; length, wire order
    mov word [dn_frame+DN_UDP+6], 0 ; **CHECKSUM ZERO IS LEGAL FOR UDP over
                                    ; IPv4 and means "not computed"** (RFC
                                    ; 768), which every resolver accepts and
                                    ; which saves a pseudo-header sum here
    add cx, 8                       ; the payload past DN_TCP
    mov al, DN_IPP_UDP
    call dn_ip_out
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; =============================================================================
; THE TCP ENDPOINT - WAVE 3'S SEAM (SPEC.md 96.26.3)
; =============================================================================
; **NOT BUILT YET, AND IT REFUSES RATHER THAN PRETENDING.** Every segment is
; answered with RST, which is a real answer: the client stops instead of
; retrying into a silence, and its own error path says "connection refused"
; where a drop would read as a dead network.
;
; That is what makes wave 2 testable on its own. A client ARPs, resolves a
; name, gets an address out of our pool and connects - and the first two of
; those are observable precisely because the third fails cleanly.
;
; What goes here is the state machine, the sequence arithmetic and the
; checksum, and DOS-CABLE-NET-PLAN 5 is the list of what it does NOT need:
; no congestion control, no retransmit queue, no reassembly.
; -----------------------------------------------------------------------------
dn_tcp_in:
    push ax
    test byte [si+DN_T_FLAGS], DN_RST
    jnz .out                        ; never answer an RST with an RST
    call dn_tcp_rst
.out:
    pop ax
    ret

; -----------------------------------------------------------------------------
; dn_tcp_rst - "there is nothing listening here"
; in:  SI = the segment that provoked it
;
; The ACK number is the one field that matters: a client checks it before it
; believes an RST, which is what stops an off-path reset. Ours is in-path by
; construction, so this is simply the sequence after whatever it sent.
; -----------------------------------------------------------------------------
dn_tcp_rst:
    push ax
    push cx
    push dx
    push si
    push di
    mov ax, [si+DN_T_DPORT]         ; the ports, swapped
    mov [dn_frame+DN_T_SPORT], ax
    mov ax, [si+DN_T_SPORT]
    mov [dn_frame+DN_T_DPORT], ax
    mov word [dn_frame+DN_T_SEQ], 0 ; our sequence: nothing has been sent
    mov word [dn_frame+DN_T_SEQ+2], 0
    push si
    add si, DN_T_SEQ                ; ...and the ack is theirs plus one, which
    call dn_get32                   ; is what a SYN consumes
    add ax, 1
    adc dx, 0
    pop si
    mov di, dn_frame + DN_T_ACK
    call dn_put32
    mov byte [dn_frame+DN_T_OFF], 0x50      ; five 32-bit words, no options
    mov byte [dn_frame+DN_T_FLAGS], DN_RST | DN_ACK
    mov word [dn_frame+DN_T_WIN], 0
    mov word [dn_frame+DN_T_CK], 0
    mov word [dn_frame+DN_T_URG], 0
    mov cx, DN_T_HLEN
    call dn_tcp_ck
    mov cx, DN_T_HLEN
    mov al, DN_IPP_TCP
    call dn_ip_out
    pop di
    pop si
    pop cx
    pop cx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dn_tcp_ck - the TCP checksum, over the PSEUDO-HEADER and the segment
; in:  SI = the client's frame (for the addresses), CX = the TCP length
;
; The pseudo-header is source, destination, a zero, the protocol and the TCP
; length - and it is NOT on the wire, so it is assembled in a scratch block
; and summed with the segment. Two sums folded together is the same answer as
; one sum over a contiguous buffer, which is what lets the block stay separate
; from the frame.
; -----------------------------------------------------------------------------
dn_tcp_ck:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov bx, cx                      ; the TCP length, banked

    mov di, dn_pseudo               ; source: the address we are SENDING from,
    mov si, dn_frame + DN_IP_SRC    ; which dn_ip_out has already written
    mov cx, 4
    call dn_copy
    mov di, dn_pseudo + 4
    mov si, dn_frame + DN_IP_DST
    mov cx, 4
    call dn_copy
    mov byte [dn_pseudo+8], 0
    mov byte [dn_pseudo+9], DN_IPP_TCP
    mov ax, bx
    xchg al, ah
    mov [dn_pseudo+10], ax

    mov si, dn_pseudo               ; --- sum one: the pseudo-header ---
    mov cx, 12
    call dn_cksum
    not ax                          ; dn_cksum complements, and a PARTIAL sum
    mov dx, ax                      ; must not be - so undo it and redo the
                                    ; complement once at the end
    mov si, dn_frame + DN_TCP       ; --- sum two: the segment ---
    mov cx, bx
    call dn_cksum
    not ax
    add ax, dx                      ; fold them, end-around
    adc ax, 0
    not ax
    xchg al, ah
    mov [dn_frame+DN_T_CK], ax
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dn_pump - ask the sockets whether anything has arrived
;
; WAVE 3'S other half. With no flow ever established there is nothing to ask,
; so this is a `ret` that documents where the asking goes rather than an empty
; routine somebody has to wonder about.
; -----------------------------------------------------------------------------
dn_pump:
    ret
