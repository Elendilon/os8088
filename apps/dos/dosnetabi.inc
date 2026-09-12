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
                                    ;       to, wire order
DN_F_SND    equ 11                  ; 4:    our next sequence TO the client
DN_F_RCV    equ 15                  ; 4:    the next we expect FROM it - which
                                    ;       is also the ack we send
DN_F_SIZE   equ 19

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

