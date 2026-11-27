; =============================================================================
; os8088 - drivers/ether/ethusr.inc
;
; THE CALLER'S SEGMENT, and the only two places it is addressed.
;
; Cut out of ether.asm so the DOS end of the parallel cable can host the same
; socket verbs (ethsock.inc's header). There [eth_useg] is simply DS - the
; .COM's one segment - so the same two routines serve a caller that is a
; package in another segment and a caller that is the program itself.
; =============================================================================
; -----------------------------------------------------------------------------
; usr_read / usr_write - the caller's segment, and the only two places it is
; in: usr_read  SI = their offset, DI = ours, CX = bytes
;     usr_write SI = ours, DI = their offset, CX = bytes
; every register kept
;
; **`rep movsb`, 17 clocks a byte, where a byte loop was ~55** (driver size
; pass 2) - ring_in and ring_out made the same move in SPEC.md 72.16, and
; these two are the copy of every raw frame a DOS stack sends or takes
; (NETV_RAWTX/RAWRX, up to 1,514 bytes a frame) and every datagram of Wire
; Arena's. The two differ only in which segment the caller's is: ES for a
; write, DS for a read - and [eth_useg] is read before DS moves, by the one
; instruction that moves it. A count of 0 moves nothing, as the loop's
; `jcxz` did.
; -----------------------------------------------------------------------------
usr_write:
    push cx
    push si
    push di
    push es
    push ds
    mov es, [eth_useg]          ; ES:DI = theirs, DS:SI = ours
    jmp short usr_mv
usr_read:
    push cx
    push si
    push di
    push es
    push ds
    push ds
    pop es                      ; ES:DI = ours...
    mov ds, [eth_useg]          ; ...and DS:SI theirs
usr_mv:
    cld
    rep movsb
    pop ds
    pop es
    pop di
    pop si
    pop cx
    ret
