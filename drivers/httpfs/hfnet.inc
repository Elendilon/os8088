; =============================================================================
; hfnet.inc - the address, and ONE HTTP GET over the socket verbs (SPEC.md
; 120.2)
;
; The Wire's profile (SPEC.md 92.4) plus `Range:`: HTTP/1.0, Connection:
; close, no chunked decoding, no redirects, one connection a request. The
; socket verbs are netpkg.inc's, behind OSAPI_DRV_CALL to whichever class
; apps/os88sock.inc's net_find answers - the card first, then the cable - so
; the drive runs over either with no line here knowing which.
;
; EVERY VERB IS NON-BLOCKING (netpkg.inc), SO THE WAITING IS OURS, and it is
; bounded by the system tick and not a loop count: HF_IDLE ticks with nothing
; arriving is a timeout, whatever the CPU. A file verb runs on the UI task with
; the gfx lock held, so this bound IS the longest a dead server can freeze the
; machine (SPEC.md 120.2).
;
; THE READER IS ONE KB OF STAGING (hf_rbuf). Header lines are read a byte at a
; time out of it; a body is copied out of it in runs. ES on the way into every
; socket verb is OUR segment (the X stub), so a NETV_RECV lands in the staging
; buffer and a run is moved from there to the kernel's buffer.
; =============================================================================

HF_IDLE      equ 182            ; ticks: ten seconds with nothing arriving
HF_RBUF      equ 1024           ; = NET_SKMAX: the most one NETV_RECV moves
HF_URLMAX    equ 96             ; the address, NUL included
HF_PFXMAX    equ 96             ; the path prefix, NUL included
HF_PATHMAX   equ 224            ; a record's path below the prefix: HF_DEPTH
                                ; names of 13, '/' included
HF_LINEMAX   equ 64             ; a header line kept (longer is clipped)

; -----------------------------------------------------------------------------
; hf_parse - [hf_url] -> [hf_host], [hf_port], [hf_pfx]
; out: CF=0; CF=1 and AX = HFE_URL. clobbers: AX
;
; `http://` is optional and `https://` is refused by name, as the browser
; refuses it (SPEC.md 71.2): TLS is the host proxy's. The prefix always starts
; and ends with `/`, so a record's path is appended to it as it is.
; -----------------------------------------------------------------------------
hf_parse:
    push bx
    push cx
    push si
    push di
    push es
    push ds                     ; ES IS THE KERNEL'S on every callback (20.1),
    pop es                      ; and every stosb below writes OUR buffers
    mov si, hf_url
    mov ax, [si]
    or ax, 0x2020               ; 'ht' in either case
    cmp ax, 'ht'
    jne .host
    mov ax, [si+2]
    or ax, 0x2020
    cmp ax, 'tp'
    jne .host
    mov al, [si+4]
    cmp al, ':'
    je .scheme
    or al, 0x20
    cmp al, 's'
    je .bad                     ; https:// - not on this machine
    jmp short .host
.scheme:
    cmp word [si+5], '//'
    jne .bad
    add si, 7
.host:
    mov di, hf_host
    mov cx, NET_HOSTMAX - 1
.h:
    lodsb
    cmp al, ':'
    je .hend
    cmp al, '/'
    je .hend
    or al, al
    jz .hend
    cmp al, ' '
    jbe .bad
    stosb
    loop .h
    jmp short .bad              ; a host longer than the socket verbs take
.hend:
    cmp di, hf_host
    je .bad                     ; no host at all
    mov byte [di], 0
    mov word [hf_port], 80
    cmp al, ':'
    jne .path
    xor bx, bx                  ; the port, decimal, 1..65535
    mov cx, 6
.p:
    lodsb
    cmp al, '/'
    je .pend
    or al, al
    jz .pend
    sub al, '0'
    cmp al, 9
    ja .bad
    push ax                     ; BX = BX x 10 + the digit
    push dx
    mov ax, 10
    mul bx
    or dx, dx
    pop dx
    pop bx                      ; BL = the digit
    jnz .bad
    xor bh, bh
    add ax, bx
    jc .bad
    xchg ax, bx
    loop .p
    jmp short .bad
.pend:
    or bx, bx
    jz .bad
    mov [hf_port], bx
.path:
    mov di, hf_pfx              ; '/' and then whatever followed it
    mov byte [di], '/'
    inc di
    or al, al
    jz .pclose                  ; `http://host` with no path at all
    mov cx, HF_PFXMAX - 3
.q:
    lodsb
    or al, al
    jz .pclose
    cmp al, ' '
    jbe .bad
    stosb
    loop .q
    jmp short .bad
.pclose:
    cmp byte [di-1], '/'
    je .term
    mov byte [di], '/'
    inc di
.term:
    mov byte [di], 0
    clc
    jmp short .out
.bad:
    mov ax, HFE_URL
    stc
.out:
    pop es
    pop di
    pop si
    pop cx
    pop bx
    ret

; -----------------------------------------------------------------------------
; hf_nc - a socket verb. BL = the verb; AX/CX/SI/DI its arguments
; out: the verb's AX, CX and flags. Every other register preserved.
; -----------------------------------------------------------------------------
hf_nc:
    push bx
    push dx
    push si
    push di
    push bp
    mov bh, [net_cls]
    call OSAPI_DRV_CALL         ; ES:SI / ES:DI = OUR segment (the X stub)
    pop bp
    pop di
    pop si
    pop dx
    pop bx
    ret

; --- hf_tstart / hf_tcheck - the idle bound. tcheck: CF=1 = it has run out ---
hf_tstart:
    push ax
    call OSAPI_GET_TICKS
    mov [hf_tbase], ax
    pop ax
    ret

hf_tcheck:
    push ax
    call OSAPI_GET_TICKS
    sub ax, [hf_tbase]
    cmp ax, HF_IDLE             ; CF=1 while under the bound...
    cmc                         ; ...so it is inverted: CF=1 = out of time
    pop ax
    ret

; -----------------------------------------------------------------------------
; hf_open - connect to [hf_host]:[hf_port]
; out: CF=0 and [hf_sock] = the handle; CF=1 and AX = HFE_NONET /
;      HFE_CONNECT / HFE_TIMEOUT. clobbers: AX, CX
; -----------------------------------------------------------------------------
hf_open:
    call net_find               ; CF=1: no socket driver; ZF=1: no link
    jc .nonet
    jz .nonet
    call hf_tstart
.o:
    mov si, hf_host
    mov cx, [hf_port]
    push bx
    mov bl, NETV_OPEN
    call hf_nc
    pop bx
    jnc .opened
    cmp ax, NETE_BUSY
    jne .noconn                 ; FULL, REFUSED, NOLINK... - not ours to wait
    call hf_tcheck
    jnc .o
    jmp short .tmo
.opened:
    mov [hf_sock], al
.w:
    push bx
    mov al, [hf_sock]
    mov bl, NETV_STATUS
    call hf_nc
    pop bx
    jc .wbusy
    cmp ah, NSK_UP
    je .up
    cmp ah, NSK_CLOSING         ; up and already closed by the peer: there
    je .up                      ; may be bytes waiting all the same
    cmp ah, NSK_CONNECT
    jne .noconn                 ; FAILED, CLOSED, FREE
.wbusy:
    call hf_tcheck
    jnc .w
.tmo:
    mov ax, HFE_TIMEOUT
    jmp short .fail
.up:
    clc
    ret
.nonet:
    mov ax, HFE_NONET
    stc
    ret
.noconn:
    mov ax, HFE_CONNECT
.fail:
    call hf_abort
    stc
    ret

; --- hf_close / hf_abort - give the handle back (both keep every register) --
hf_close:
    push bx
    mov bl, NETV_CLOSE
    jmp short hf_drop
hf_abort:                       ; DROP IT NOW: a transfer abandoned midway
    push bx                     ; must not sit in TIME-WAIT holding a slot
    mov bl, NETV_ABORT
hf_drop:
    push ax
    push cx
    pushf
    mov byte [hf_live], 0
    mov al, 0
    xchg al, [hf_sock]
    or al, al
    jz .out
    call hf_nc
.out:
    popf
    pop cx
    pop ax
    pop bx
    ret

; -----------------------------------------------------------------------------
; hf_send - the CX bytes at DS:SI, all of them
; out: CF=0; CF=1 and AX = an HFE_*. clobbers: AX, CX, SI
; -----------------------------------------------------------------------------
hf_send:
    call hf_tstart
.s:
    jcxz .done
    push cx
    push bx
    mov al, [hf_sock]
    mov bl, NETV_SEND
    call hf_nc                  ; CX = how many it took
    pop bx
    jc .ref                     ; (CX is still pushed)
    mov ax, cx
    pop cx
    or ax, ax
    jz .busy
    add si, ax
    sub cx, ax
    call hf_tstart
    jmp short .s
.ref:
    pop cx
    cmp ax, NETE_BUSY           ; BUSY is the only refusal worth waiting out
    jne .broke
.busy:
    call hf_tcheck
    jnc .s
    mov ax, HFE_TIMEOUT
    ret
.broke:
    mov ax, HFE_CONNECT
    stc
    ret
.done:
    clc
    ret

; -----------------------------------------------------------------------------
; hf_fill - the staging buffer, refilled
; out: CF=0 and [hf_rlen] > 0, [hf_rpos] = 0; CF=1 and AX = HFE_SHORT (the
;      peer closed with nothing left), HFE_CONNECT or HFE_TIMEOUT
; clobbers: AX
;
; A NETV_RECV of 0 IS NOT THE END (netpkg.inc): the end is NSK_CLOSING with
; nothing readable, which is what NETV_STATUS is asked when RECV has nothing.
; -----------------------------------------------------------------------------
hf_fill:
    push bx
    push cx
    push di
    call hf_tstart
.r:
    mov al, [hf_sock]
    mov di, hf_rbuf
    mov cx, HF_RBUF
    mov bl, NETV_RECV
    call hf_nc
    jc .why
    jcxz .st
    mov [hf_rlen], cx
    mov word [hf_rpos], 0
    clc
    jmp short .out
.why:
    cmp ax, NETE_BUSY
    je .wait
    jmp short .broke
.st:
    mov al, [hf_sock]
    mov bl, NETV_STATUS
    call hf_nc
    jc .wait
    cmp ah, NSK_UP
    je .wait
    cmp ah, NSK_CONNECT
    je .wait
    cmp ah, NSK_CLOSING
    jne .end                    ; CLOSED, FAILED, FREE: nothing more is coming
    jcxz .end                   ; CLOSING with nothing readable: the end
.wait:
    call hf_tcheck
    jnc .r
    mov ax, HFE_TIMEOUT
    jmp short .out
.end:
    mov ax, HFE_SHORT
    stc
    jmp short .out
.broke:
    mov ax, HFE_CONNECT
    stc
.out:
    pop di
    pop cx
    pop bx
    ret

; --- hf_getc - AL = the next byte. CF=1 and AX = an HFE_* at the end ---------
hf_getc:
    push si
    mov si, [hf_rpos]
    cmp si, [hf_rlen]
    jb .have
    call hf_fill
    jc .out
    xor si, si
.have:
    mov al, [hf_rbuf+si]
    inc si
    mov [hf_rpos], si
    clc
.out:
    pop si
    ret

; -----------------------------------------------------------------------------
; hf_line - one header line into [hf_lbuf], CR and LF taken off, clipped at
;           HF_LINEMAX-1. out: CF=0, CX = its length; CF=1, AX = an HFE_*
; -----------------------------------------------------------------------------
hf_line:
    push di
    mov di, hf_lbuf
    xor cx, cx
.c:
    call hf_getc
    jc .out
    cmp al, 10
    je .eol
    cmp al, 13
    je .c
    cmp cx, HF_LINEMAX - 1
    jae .c                      ; clipped, and still read to its end
    mov [di], al
    inc di
    inc cx
    jmp short .c
.eol:
    mov byte [di], 0
    clc
.out:
    pop di
    ret

; --- hf_hdris - does [hf_lbuf] start with the NUL name at SI, any case? -----
;     out: ZF=1 and SI = the first byte after it and any spaces. clobbers: AX
hf_hdris:
    push di
    mov di, hf_lbuf
.c:
    mov al, [si]
    or al, al
    jz .yes
    mov ah, [di]
    cmp ah, 'a'
    jb .u
    cmp ah, 'z'
    ja .u
    sub ah, 0x20
.u:
    cmp al, ah
    jne .out                    ; ZF=0
    inc si
    inc di
    jmp short .c
.yes:
    mov si, di
.sp:
    cmp byte [si], ' '
    jne .z
    inc si
    jmp short .sp
.z:
    cmp al, al                  ; ZF=1
.out:
    pop di
    ret

; -----------------------------------------------------------------------------
; hf_atol - SI = decimal digits -> DX:AX, SI past them. CF=1 = no digit, or
;           more than 32 bits. clobbers: BX, CX
; -----------------------------------------------------------------------------
hf_atol:
    xor ax, ax
    xor dx, dx
    mov cx, si
.d:
    mov bl, [si]
    sub bl, '0'
    cmp bl, 9
    ja .end
    inc si
    push bx                     ; the digit
    push ax                     ; the low word
    mov ax, dx
    mov bx, 10
    mul bx                      ; DX:AX = high x 10
    or dx, dx
    jnz .ovf2
    mov dx, ax
    pop ax
    push dx                     ; high x 10
    mul bx                      ; DX:AX = low x 10
    pop bx
    add dx, bx
    jc .ovf1
    pop bx
    xor bh, bh
    add ax, bx
    adc dx, 0
    jnc .d
    ret                         ; CF=1: past 32 bits
.ovf2:
    pop ax
.ovf1:
    pop bx
    stc
    ret
.end:
    cmp si, cx
    je .none
    clc
    ret
.none:
    stc
    ret

; -----------------------------------------------------------------------------
; hf_ultoa - DX:AX -> decimal at ES:DI (our segment), DI past it. clobbers:
;            AX, BX, CX, DX
; -----------------------------------------------------------------------------
hf_ultoa:
    ; STKBALANCE-LOOP: one digit pushed a turn and the second loop pops them; the count is in CX
    xor cx, cx                  ; digits pushed
.div:
    mov bx, ax                  ; DX:AX / 10, two steps
    mov ax, dx
    xor dx, dx
    push cx
    mov cx, 10
    div cx                      ; AX = high quotient, DX = remainder
    xchg ax, bx                 ; BX = high quotient, AX = the low word
    div cx                      ; AX = low quotient, DX = the digit
    pop cx
    add dl, '0'
    push dx
    inc cx
    mov dx, bx
    mov bx, ax
    or bx, dx
    jnz .div
.out:
    pop ax
    stosb
    loop .out
    ret

; --- hf_scpy - the NUL string at SI to ES:DI, without its NUL ---------------
hf_scpy:
    lodsb
    or al, al
    jz .z
    stosb
    jmp short hf_scpy
.z:
    ret

; -----------------------------------------------------------------------------
; hf_get - request [hf_path] below the prefix, and read the status and headers
; in:  [hf_rlo]/[hf_rn] = the range wanted when [hf_rng] is 1 (start, count)
; out: CF=0: [hf_status], [hf_clen]/[hf_hasl], [hf_crlo]/[hf_hascr] read and
;      the reader at the body; the status is 200 or 206.
;      CF=1 and AX = an HFE_*; the connection is gone
; clobbers: AX, BX, CX, DX, SI, DI
; -----------------------------------------------------------------------------
hf_get:
    push es
    push ds
    pop es
    xor ax, ax
    mov [hf_status], ax
    mov [hf_hasl], al
    mov [hf_hascr], al
    mov [hf_rlen], ax
    mov [hf_rpos], ax
    mov di, hf_rbuf             ; GET <prefix><path> HTTP/1.0 - COMPOSED IN
                                ; THE RECEIVE BUFFER, which is idle until the
                                ; request has gone: the prefix, a path whose
                                ; every byte is escaped and the host come to
                                ; under 900 bytes of its 1,024
    mov si, hf_s_get
    call hf_scpy
    mov si, hf_pfx
    call hf_scpy
    mov si, hf_path
.pc:
    lodsb                       ; the path, ESCAPED: an 8.3 name may carry
    or al, al                   ; '#', '%' or '&', which a URL may not
    jz .pdone
    call hf_urlch
    jmp short .pc
.pdone:
    mov si, hf_s_host
    call hf_scpy
    mov si, hf_host
    call hf_scpy
    cmp word [hf_port], 80
    je .nop
    mov al, ':'
    stosb
    mov ax, [hf_port]
    xor dx, dx
    call hf_ultoa
.nop:
    mov si, hf_s_ua
    call hf_scpy
    cmp byte [hf_rng], 0
    je .norng
    mov si, hf_s_rng            ; Range: bytes=<lo>-<lo+n-1>
    call hf_scpy
    mov ax, [hf_rlo]
    mov dx, [hf_rlo+2]
    call hf_ultoa
    mov al, '-'
    stosb
    mov ax, [hf_rlo]
    mov dx, [hf_rlo+2]
    add ax, [hf_rn]
    adc dx, 0
    sub ax, 1
    sbb dx, 0
    call hf_ultoa
    mov ax, 0x0A0D
    stosw
.norng:
    mov si, hf_s_end
    call hf_scpy
    mov cx, di
    sub cx, hf_rbuf
    pop es
    mov [hf_reqn], cx
    ; --- A KEPT CONNECTION, if the last GET left one (SPEC.md 120.2.1) ------
    ; Up, and with nothing unread on it: a byte waiting there now would be
    ; read as the start of THIS reply. Anything else is dropped and a fresh
    ; one opened, which is all a server's idle close costs.
    mov byte [hf_kept], 0
    cmp byte [hf_live], 0
    je .fresh
    mov byte [hf_live], 0
    push bx
    mov al, [hf_sock]
    mov bl, NETV_STATUS
    call hf_nc
    pop bx
    jc .stale
    cmp ah, NSK_UP
    jne .stale
    jcxz .reuse
.stale:
    call hf_abort
    jmp short .fresh
.reuse:
    mov byte [hf_kept], 1
    jmp short .send
.fresh:
    call hf_open
    jc .out
.send:
    xor ax, ax
    mov [hf_rlen], ax
    mov [hf_rpos], ax
    mov si, hf_rbuf
    mov cx, [hf_reqn]
    call hf_send
    jc .drop
    call hf_line                ; the status line: HTTP/1.x NNN ...
    jc .drop
    cmp word [hf_lbuf], 'HT'
    jne .shape
    cmp word [hf_lbuf+2], 'TP'
    jne .shape
    mov al, [hf_lbuf+7]         ; HTTP/1.1 keeps the connection unless it
    sub al, '1'                 ; says close; HTTP/1.0 only if it says
    cmp al, 1                   ; keep-alive (below)
    sbb al, al
    and al, 1
    mov [hf_keep], al
    mov si, hf_lbuf + 9
    call hf_atol
    jc .shape
    mov [hf_status], ax
.h:
    call hf_line
    jc .drop
    jcxz .hdone
    mov si, hf_s_clen
    call hf_hdris
    jne .cr
    call hf_atol
    jc .h
    mov [hf_clen], ax
    mov [hf_clen+2], dx
    mov byte [hf_hasl], 1
    jmp short .h
.cr:
    mov si, hf_s_conn
    call hf_hdris
    jne .cr2
    mov al, [si]
    and al, 0xDF                ; K(eep-alive) or C(lose), either case
    cmp al, 'K'
    mov al, 1
    je .kset
    dec ax
.kset:
    mov [hf_keep], al
    jmp short .h
.cr2:
    mov si, hf_s_crng
    call hf_hdris
    jne .h
    call hf_atol
    jc .h
    mov [hf_crlo], ax
    mov [hf_crlo+2], dx
    mov byte [hf_hascr], 1
    jmp short .h
.hdone:
    cmp byte [hf_hasl], 0
    jne .lenok
    mov byte [hf_keep], 0       ; no length: the body ends at the close
.lenok:
    mov ax, [hf_status]
    cmp ax, 200
    je .ok
    cmp ax, 206
    je .ok
    mov ax, HFE_STATUS
    jmp short .drop
.shape:
    mov ax, HFE_CONNECT         ; not an HTTP answer at all
.drop:
    call hf_abort
    cmp byte [hf_kept], 0       ; a KEPT connection that died before a byte
    je .fail                    ; of the reply - the server's idle close -
    cmp word [hf_rlen], 0       ; is tried once more on a fresh one; the
    jne .fail                   ; request is still in hf_rbuf, since nothing
    mov byte [hf_kept], 0       ; was received over it
    jmp .fresh
.fail:
    stc
    jmp short .out
.ok:
    clc
.out:
    ret

; -----------------------------------------------------------------------------
; hf_done - a reply read WHOLE: its connection is kept for the next GET when
;           the server agreed to keep it and nothing past the body arrived,
;           and closed otherwise. keeps every register
; -----------------------------------------------------------------------------
hf_done:
    cmp byte [hf_keep], 0
    je hf_close
    push ax
    mov ax, [hf_rpos]
    cmp ax, [hf_rlen]
    pop ax
    jne hf_close
    mov byte [hf_live], 1
    ret

; --- hf_urlch - AL into the request, %XX unless it is safe in a path --------
hf_urlch:
    cmp al, '/'
    je .put
    cmp al, '.'
    je .put
    cmp al, '-'
    je .put
    cmp al, '_'
    je .put
    cmp al, '0'
    jb .esc
    cmp al, '9'
    jbe .put
    cmp al, 'A'
    jb .esc
    cmp al, 'Z'
    jbe .put
.esc:
    push ax
    mov al, '%'
    stosb
    pop ax
    push ax
    push cx
    mov cl, 4
    shr al, cl
    call .hex
    pop cx
    pop ax
    and al, 15
.hex:
    add al, '0'
    cmp al, '9'
    jbe .put
    add al, 'A' - '9' - 1
.put:
    stosb
    ret

; -----------------------------------------------------------------------------
; hf_body - [hf_left] bytes of body to [hf_bseg]:[hf_boff], after skipping
;           [hf_skip] (a server that ignored Range:, SPEC.md 120.4)
; out: CF=0; CF=1 and AX = an HFE_*. [hf_prog] = 1 steps the progress bar
; clobbers: AX, CX
; -----------------------------------------------------------------------------
hf_body:
    push si
    push di
    push es
    call hf_bnorm
.loop:
    mov ax, [hf_left]
    or ax, [hf_left+2]
    jz .done
    mov si, [hf_rpos]
    mov cx, [hf_rlen]
    sub cx, si
    ja .have
    call hf_fill
    jc .out
    jmp short .loop
.have:
    mov ax, [hf_skip]           ; a skip first, in runs of what is staged
    or ax, [hf_skip+2]
    jz .take
    cmp word [hf_skip+2], 0
    jne .sk
    cmp cx, [hf_skip]
    jbe .sk
    mov cx, [hf_skip]
.sk:
    add [hf_rpos], cx
    sub [hf_skip], cx
    sbb word [hf_skip+2], 0
    jmp short .loop
.take:
    cmp word [hf_left+2], 0
    jne .n
    cmp cx, [hf_left]
    jbe .n
    mov cx, [hf_left]
.n:
    add [hf_rpos], cx
    sub [hf_left], cx
    sbb word [hf_left+2], 0
    add si, hf_rbuf
    mov es, [hf_bseg]
    mov di, [hf_boff]
    mov ax, cx
    cld
    rep movsb
    add [hf_boff], ax
    call hf_bnorm
    cmp byte [hf_prog], 0
    je .loop
    call OSAPI_FS_PROG          ; AX = since the last report; keeps everything
    jmp .loop
.done:
    clc
.out:
    pop es
    pop di
    pop si
    ret

; hf_bnorm - [hf_bseg]:[hf_boff] with the offset under 128, in whole 128-byte
; granules: cd_bnorm's rule and reason (kern_mega's identity selectors,
; SPEC.md 119.3.4). clobbers: nothing
hf_bnorm:
    push ax
    push cx
    mov ax, [hf_boff]
    mov cl, 4
    shr ax, cl
    and al, 0xF8
    add [hf_bseg], ax
    and word [hf_boff], 127
    pop cx
    pop ax
    ret

hf_s_get:   db 'GET ', 0
hf_s_host:  db ' HTTP/1.0', 13, 10, 'Host: ', 0
hf_s_ua:    db 13, 10, 'User-Agent: os8088 HttpDrive 1.0', 13, 10, 0
hf_s_rng:   db 'Range: bytes=', 0
hf_s_end:   db 'Connection: keep-alive', 13, 10, 13, 10, 0
hf_s_conn:  db 'CONNECTION:', 0
hf_s_clen:  db 'CONTENT-LENGTH:', 0
hf_s_crng:  db 'CONTENT-RANGE: BYTES ', 0
