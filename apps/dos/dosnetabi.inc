; =============================================================================
; os8088 - apps/dos/dosnetabi.inc
;
; THE CABLE TRANSLATION'S CONSTANTS (SPEC.md 96.26), in a file of their own for
; hddabi.inc's reason (SPEC.md 52.11.1): the bss table is a %assign chain and
; the preprocessor cannot see an `equ` from a file included after it. So the
; numbers come in EARLY, beside the packet driver's own, and apps/dos/dosnet.inc
; - which is code - comes in at the end where a package's code goes.
; =============================================================================

DN_NFLOW    equ 4                   ; connections at once. mTCP's ftp wants two
                                    ; (control and data) and htget one; four is
                                    ; a browser's worth and 92 bytes
DN_NNAME    equ 4                   ; ...and remembered names (dn_dns)

; --- a flow ------------------------------------------------------------------
DN_F_USED   equ 0                   ; byte: 1 = live
DN_F_HAND   equ 1                   ; byte: the socket handle
DN_F_ST     equ 2                   ; byte: DN_S_*
DN_F_LPORT  equ 3                   ; word: the CLIENT's port, wire order
DN_F_RPORT  equ 5                   ; word: ...and the one it asked for
DN_F_RIP    equ 7                   ; 4:    the synthetic address it connected
                                    ;       to, wire order - which is also the
                                    ;       SOURCE of everything we send it
DN_F_LIP    equ 11                  ; 4:    ...and its own, the destination
DN_F_SND    equ 15                  ; 4:    our next sequence TO the client
DN_F_RCV    equ 19                  ; 4:    the next we expect FROM it - which
                                    ;       is also the ack we send
DN_F_SIZE   equ 23

; **THE ETHERNET ADDRESSES ARE NOT PER FLOW**, and that is worth stating
; because it is the kind of field that gets added by habit. We told the client
; its own MAC (dn_ourmac) and we are the only other station, so every frame we
; build goes FROM dn_gwmac TO dn_ourmac whatever the flow - there is nothing
; to remember and nothing to look up.

DN_S_FREE   equ 0
DN_S_OPEN   equ 1                   ; NETV_OPEN issued, waiting on NSK_UP
DN_S_UP     equ 2
DN_S_FIN    equ 3                   ; the far side is done; a FIN is owed
DN_S_DEAD   equ 4

; --- a remembered name (SPEC.md 96.26.2) -------------------------------------
DN_N_USED   equ 0                   ; byte: 1 = taken
DN_N_NAME   equ 1                   ; DN_NAMEMAX, NUL-terminated
DN_NAMEMAX  equ 48                  ; longer than any host this box will meet,
                                    ; and NET_HOSTMAX bounds the far side
DN_N_SIZE   equ DN_N_NAME + DN_NAMEMAX

; --- the synthetic segment we invent ----------------------------------------
; The client is told the whole world is on 10.88.0.0/24 behind ONE router, and
; that router is us. None of this reaches a wire: the addresses are handed to
; the client in a DNS answer and handed back in an IP header, and the far side
; is opened BY NAME (SPEC.md 96.26.2).
DN_GWMAC    equ 0                   ; (offset into dn_gwmac)
DN_POOL0    equ 16                  ; 10.88.0.16 is the first name we hand out

; --- THE TRANSLATION'S STATE, laid out in the NETWORK CLAIM ------------------
; Offsets from PKB_STATE (apps/dos/dos.asm), not from this package's bss:
; **DS IS THE CLAIM inside every dn_* routine** (SPEC.md 96.26.6), so a bss
; byte here would be a byte of the DOS program's own arena spent on a wire
; that may not exist. dosnet.inc's premise was already "one segment, no
; override"; the segment is simply not ours.
;
; Laid out here rather than in dos.asm for this file's own reason one level
; on: the frame offsets above and the state offsets below are read together
; by every routine in dosnet.inc, and splitting them across two files is how
; a layout ends up known in two places.
DNB_FLOWS   equ 0
DNB_NAMES   equ DNB_FLOWS + DN_NFLOW * DN_F_SIZE
DNB_QNAME   equ DNB_NAMES + DN_NNAME * DN_N_SIZE
DNB_PEND    equ DNB_QNAME + DN_NAMEMAX      ; word: bytes of frame waiting
DNB_LASTIP  equ DNB_PEND + 2                ; byte: the pool octet last used
DNB_PSEUDO  equ DNB_LASTIP + 1              ; 12: TCP's pseudo-header
DNB_RR      equ DNB_PSEUDO + 12             ; byte: dn_pump's round robin - a
                                            ; busy first flow would starve
                                            ; every other one, and FTP opens
                                            ; two
DNB_GWMAC   equ DNB_RR + 1                  ; 6:  the router's address and...
DNB_OURMAC  equ DNB_GWMAC + 6               ; 6:  ...the client's, COPIED in by
                                            ; dn_init out of the image, where
                                            ; they are `db` constants a
                                            ; claim-relative DS cannot reach
DNB_SIZE    equ DNB_OURMAC + 6

; --- offsets, wire order -----------------------------------------------------
DN_EH_DST   equ 0
DN_EH_SRC   equ 6
DN_EH_TYP   equ 12
DN_EH_LEN   equ 14
DN_ARP_OP   equ DN_EH_LEN + 6       ; htype,ptype,hlen,plen then oper
DN_ARP_SHA  equ DN_EH_LEN + 8
DN_ARP_SPA  equ DN_EH_LEN + 14
DN_ARP_THA  equ DN_EH_LEN + 18
DN_ARP_TPA  equ DN_EH_LEN + 24
DN_ARP_END  equ DN_EH_LEN + 28

DN_IP_VIHL  equ DN_EH_LEN + 0
DN_IP_LEN   equ DN_EH_LEN + 2
DN_IP_TTL   equ DN_EH_LEN + 8
DN_IP_PROTO equ DN_EH_LEN + 9
DN_IP_CK    equ DN_EH_LEN + 10
DN_IP_SRC   equ DN_EH_LEN + 12
DN_IP_DST   equ DN_EH_LEN + 16
DN_IP_HLEN  equ 20
DN_TCP      equ DN_EH_LEN + DN_IP_HLEN
DN_UDP      equ DN_EH_LEN + DN_IP_HLEN

DN_T_SPORT  equ DN_TCP + 0
DN_T_DPORT  equ DN_TCP + 2
DN_T_SEQ    equ DN_TCP + 4
DN_T_ACK    equ DN_TCP + 8
DN_T_OFF    equ DN_TCP + 12         ; data offset in the high nibble
DN_T_FLAGS  equ DN_TCP + 13
DN_T_WIN    equ DN_TCP + 14
DN_T_CK     equ DN_TCP + 16
DN_T_URG    equ DN_TCP + 18
DN_T_HLEN   equ 20
DN_T_PAY    equ DN_TCP + DN_T_HLEN

DN_FIN      equ 0x01
DN_SYN      equ 0x02
DN_RST      equ 0x04
DN_PSH      equ 0x08
DN_ACK      equ 0x10

DN_IPP_ICMP equ 1
DN_IPP_TCP  equ 6
DN_IPP_UDP  equ 17

DN_WIN      equ 1024                ; what we advertise, and it is our staging
                                    ; buffer's size: the client must never send
                                    ; more than we can hold, because we have
                                    ; nowhere to put the overflow and no
                                    ; reassembly (DOS-CABLE-NET-PLAN 5)

