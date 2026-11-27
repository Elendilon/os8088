; =============================================================================
; os8088 - cpw_drv.inc
;
; The wide Drivers page (SPEC.md 135.8): %included by cpwide.inc into
; CPWIDE.DRV's image, in `.modv`. Prefix `cpd_`. It draws NATIVELY with the
; widget kit (cpwkit.inc) and changes state only through CPE_GATE's driver ops
; (CPG_DRVON / OFF / WANT / TTL / STAT / MEM, SPEC.md 135.4), so the compact
; page and this one run ONE body for a load, an unload and a want bit.
;
; WHAT IT SHOWS (SPEC.md 135.8): category filter tabs (All, then the
; categories with a row on this kernel), a scrolling table of every drv_tab row
; - category icon, name, status badge, memory, Start at boot - and a DETAILS
; box for the selected row with Load, Unload, Settings... and Ports....
;
; ITS STATE is in the working area's page block (CPW_W_PAGE, 80 bytes), which
; the page showing owns whole (SPEC.md 135.5.1), and NOTHING is kept between
; visits except the filter and the selection, which are the working area's
; KEPT bytes (CPW_W_DFLT, CPW_W_DSEL) - outside the block, because the Theme
; and Display pages lay their own maps over all of it. Everything is
; content-relative; ES = the asset view.
;
; REDRAW ONLY WHAT CHANGED (CLAUDE.md, Performance): a row is painted opaque,
; in the spans AROUND its text, so a selection change is two rows and the
; details, a want bit one row, a load one row, the details, the status line and
; (only when its length moved) the page list. A filter change draws the two
; tabs whose look changed and steps past the rest, and DETAILS draws its icon
; and each of its buttons only when that look is not the one on the glass.
; =============================================================================

section .modv                   ; CPWIDE.DRV's image, like the file that includes
                                ; this one (os88ovlchk reads each file's own sections)

; --- the state (SPEC.md 135.5.1) ----------------------------------------------
; What outlives a visit - the filter, the selection, and whether the page block
; is still this page's - is in the working area's KEPT bytes, which no other
; page writes. Everything in the page block is rebuilt by cpd_paint, and on a
; FRESH entry (CPD_ON = 0: another page has had the block) the table's first
; row too, so nothing a Theme or Display visit left there is ever read.
CPD_FLT     equ CPW_W_DFLT              ; db the filter: 0 All, else a CWC_*
CPD_SELR    equ CPW_W_DSEL              ; db the selected drv_tab row, 0FFh none
CPD_ON      equ CPW_W_DON               ; db 1 = the page block is this page's
CPD_TB      equ CPW_W_PAGE              ; the table's block (CPKT_SIZE = 18)
CPD_DIC     equ CPD_TB + CPKT_SIZE      ; db the DETAILS icon on the glass...
CPD_DBT     equ CPD_DIC + 1             ; 4 x db ...and each DETAILS button's
                                        ; look on it (cpd_btn): 0FFh, not drawn
                                        ; since cpd_paint laid the ground
CPD_MASK    equ CPD_DBT + 4             ; db one bit per CWC_* that has a row,
                                        ; and bit 0 - All - always
CPD_KC      equ CPD_MASK + 1            ; dw the cells each of the badge, memory
                                        ; and boot columns gains over 616's
CPD_GT      equ CPD_KC + 2              ; dw the DETAILS box's top
CPD_XA      equ CPD_GT + 2              ; dw x CPD_NXA: a row's x's (below)
CPD_ROWS    equ CPD_XA + CPD_NXA * 2    ; db x DRV_MAX: the drv_tab rows listed
; (kernel.asm, after driver.inc, checks CPD_ROWS + DRV_MAX against the block)
CPW_D_ON    equ CPD_ON                  ; (cpwide.inc's name for it)

; --- the geometry, content-relative (SPEC.md 135.8) ---------------------------
CPD_XL      equ CPW_PX + 8              ; the table's, the tabs' and the box's left
CPD_TABY    equ CPW_BY + 4              ; the tab strip's top
CPD_HDRY    equ CPD_TABY + CPK_TABH + 2 ; the column heads' top
CPD_HDRH    equ 12
CPD_ROWY    equ CPD_HDRY + CPD_HDRH     ; the first row's top
CPD_RH      equ 18                      ; a row's pitch
CPD_DH      equ 112                     ; the DETAILS box's height
CPD_BTY     equ CPD_DH - 22             ; its buttons' top, box-relative
CPD_TXC     equ 52                      ; its text column, box-relative
CPD_ROWMIN  equ 465                     ; a row's width at 616x408 (no bar)

; a row's columns, row-relative: 2 icon, 20 name (22 cells), 196 badge
; (12 cells), 292 memory (8), 356 Start at boot (13). The window's width above
; 616 is shared out among the badge, memory and boot columns in whole cells:
; K = 8 x [CPD_KC] px each, so the badge is at SX + K, the memory at MX + 2K
; and the box's column at BXC + 3K.
CPD_NX      equ 20
CPD_NW      equ 22
CPD_SX      equ CPD_NX + CPD_NW * 8
CPD_MX      equ CPD_SX + 96
CPD_BXC     equ CPD_MX + 64
CPD_CKX     equ 46                      ; the check box, in the boot column

; CPD_XA - every x a row is laid at, CONTENT-relative (a row's left is CPD_XL
; on every row), worked out once a paint by cpd_paint rather than once a span.
; The slots, as byte offsets into it:
CPD_XL0     equ 0                       ; XL          the row's left
CPD_XL1     equ 2                       ; XL + 1
CPD_XN0     equ 4                       ; XL + 18     the air before the name
CPD_XN1     equ 6                       ; XL + 19
CPD_XBM     equ 8                       ; the badge - 1 (the name run's last)
CPD_XB      equ 10                      ; the badge (SX + K)
CPD_XBE     equ 12                      ; the badge + 95
CPD_XM      equ 14                      ; the badge + 96: the memory's run, its
                                        ; air to the column as spaces
CPD_XME     equ 16                      ; the memory + 64: past its 8 cells
CPD_XCM     equ 18                      ; the box - 1 (the box is at + 1)
CPD_XCE     equ 20                      ; the box + 12: past it
CPD_XR      equ 22                      ; the row's last column (no bar)
CPD_XTR     equ 24                      ; the table's last column (its bar's)
CPD_NXA     equ 13

CPD_MSTR    equ CPW_W_STR + 48          ; a row's memory line, composed after
                                        ; its name (which is at CPW_W_STR)

CPD_GRN     equ 10                      ; the badges' papers (EGA indices)
CPD_RED     equ 12
CPD_YEL     equ 14

%if CPG_DRVOFF != CPG_DRVON + 1
  %error "cpw_drv: cpd_rel picks Load or Unload by adding the button"
%endif
%if CWC_UNK != 0
  %error "cpw_drv: cpd_build's and cpd_det's category 0 is the unknown one"
%endif

; -----------------------------------------------------------------------------
; cpd_paint - the whole page: ground, tabs, column heads, table, DETAILS
; in:  nothing. out: nothing
; The page area's ground goes down in ONE fill (the compact pages' own
; precedent, cp_page); every widget after it is opaque, so a later redraw of
; one of them never needs the ground again.
; -----------------------------------------------------------------------------
cpd_paint:
    mov di, CPD_TB              ; --- the geometry, from the content's size
    mov ax, CPD_XL
    stosw                       ; CPKT_X
    mov ax, CPD_ROWY
    stosw                       ; CPKT_Y
    mov ax, [es:CPW_W_CW]
    sub ax, CPD_XL + 8
    stosw                       ; CPKT_W, the box's width too
    mov word [es:di], CPD_RH    ; CPKT_RH
    mov word [es:CPD_TB + CPKT_ROW], cpd_row
    xchg ax, dx                 ; DX = the table's width
    mov di, CPD_DIC
    mov ax, 0FFFFh              ; the ground is about to cover DETAILS: none
    stosw                       ; of its icon or its buttons is on the glass
    stosw
    stosb
    inc di                      ; (CPD_MASK is cpd_build's)
    mov ax, dx
    sub ax, CPK_SBW + CPD_ROWMIN    ; the width over 616's, in 24 px steps: a
    jge .e                          ; third of it, in cells, to each column
    xor ax, ax
.e:
    mov cl, 24
    div cl
    cbw
    stosw                       ; CPD_KC
    mov cl, 3
    shl ax, cl
    xchg ax, bx                 ; BX = K, 8 px a cell of it
    call cpw_sty
    sub ax, 4 + CPD_DH          ; the box: its bottom 3 rows above the page's
    stosw                       ; CPD_GT
    sub ax, 3 + CPD_ROWY        ; ...and the rows that fit above it
    mov cl, CPD_RH
    div cl
    cbw
    mov [es:CPD_TB + CPKT_NV], ax
    mov ax, CPD_XL              ; --- CPD_XA, slot by slot
    stosw
    inc ax
    stosw
    mov al, CPD_XL + 18
    stosw
    inc ax
    stosw
    lea ax, [bx + CPD_XL + CPD_SX - 1]
    stosw                       ; the badge - 1
    inc ax
    stosw                       ; the badge
    add ax, 95
    stosw
    inc ax
    stosw                       ; the badge + 96
    add ax, bx
    add ax, 64
    stosw                       ; the memory + 64 (MX + 2K + 64)
    add ax, bx
    add ax, CPD_CKX - 1
    stosw                       ; the box - 1 (BXC + 3K + 45)
    add ax, 13
    stosw                       ; the box + 12
    xchg ax, dx
    add ax, CPD_XL - CPK_SBW - 1
    stosw                       ; the row's last column
    add ax, CPK_SBW
    stosw                       ; the table's
    mov al, 1                   ; --- the rows. A FRESH entry (the block was
    xchg al, [es:CPD_ON]        ; another page's) does not trust its first
    push ax                     ; row: from the top, and then down only as
    call cpd_build              ; far as the kept selection needs to be in
    pop ax                      ; view (SEL 0FFFFh, none: the top)
    or al, al
    jnz .go
    mov ax, [es:CPD_TB + CPKT_SEL]
    sub ax, [es:CPD_TB + CPKT_NV]
    inc ax
    jg .t
    xor ax, ax
.t:
    mov [es:CPD_TB + CPKT_TOP], ax
.go:
    call cpd_ground
    mov ah, 0FFh                ; every tab
    call cpd_tabs
    call cpd_hdr
    mov bx, CPD_TB
    call cpk_table
    mov ax, CPD_XL                  ; the DETAILS box: its band and frame
    mov bx, [es:CPD_GT]
    mov cx, [es:CPD_XA + CPD_XTR]
    mov dx, bx
    add dx, CPD_DH - 1
    mov si, cpd_s_det
    call cpk_group
    jmp cpd_det

; -----------------------------------------------------------------------------
; cpd_ground - the page area's white ground, from y CPW_BY (or, entered at
; cpd_groundb, from y BX) to the status line's rule: the one fill each wide
; page drawn natively lays first (the Theme page's too)
; in:  nothing (BX). out: nothing; AX CX DX spent
; -----------------------------------------------------------------------------
cpd_ground:
    mov bx, CPW_BY
cpd_groundb:
    call cpw_sty2               ; DX = the last row above the rule
    mov byte [gfx_color], CWHITE
    mov ax, CPW_PX
    mov cx, [es:CPW_W_CW]
    dec cx
    jmp cpw_fill

; -----------------------------------------------------------------------------
; cpd_build - the table's rows: the drv_tab rows the filter keeps, the
;             categories present, the selection's place in the list
; in:  [CPD_FLT], [CPD_SELR]. out: [CPD_ROWS], N, SEL, TOP clamped, [CPD_MASK];
;      AX BX CX DX SI DI BP spent
; A selection the filter dropped (or none yet) becomes the first row shown.
; -----------------------------------------------------------------------------
cpd_build:
    mov dx, 1                   ; DL = the categories present: All always
    xor ch, ch                  ; CH = the drv_tab row
    mov bp, CPD_ROWS            ; BP = where the next listed row goes
    mov bx, drv_tab
    mov si, 0FFFFh              ; SI = the selected row's place
.r:
    cmp word [bx + DRVR_FILE], 0
    je .n
    mov al, ch
    call cpw_cat                ; ES:DI = its record, CF = 1 none
    mov ah, CWC_UNK
    jc .m
    mov ah, [es:di + CWD_C_CAT]
    mov cl, ah
    mov al, 1
    shl al, cl
    or dl, al
.m:
    mov al, [es:CPD_FLT]
    or al, al
    jz .take
    cmp al, ah
    jne .n
.take:
    cmp ch, [es:CPD_SELR]
    jne .ns
    mov si, bp                  ; its place in the list: CPD_ROWS is a bss
    sub si, CPD_ROWS            ; LABEL of the image since CPWIDE.DAT folded
                                ; in, so no `lea [bp - label]` (driver size
                                ; pass 2: +2, and no layout assumed)
.ns:
    mov [es:bp], ch
    inc bp
.n:
    add bx, DRVR_SIZE
    inc ch
    cmp ch, DRV_MAX
    jb .r
    mov [es:CPD_MASK], dl
    xchg ax, bp
    sub ax, CPD_ROWS            ; AX = the rows listed
    mov [es:CPD_TB + CPKT_N], ax
    or si, si
    jns .sel
    or ax, ax                   ; the selection is not listed: the first row
    mov dl, 0FFh                ; shown, if there is one
    jz .none
    inc si
    mov dl, [es:CPD_ROWS]
.none:
    mov [es:CPD_SELR], dl
.sel:
    mov [es:CPD_TB + CPKT_SEL], si
    sub ax, [es:CPD_TB + CPKT_NV]   ; the last top there is
    jge .t
    xor ax, ax
.t:
    cmp [es:CPD_TB + CPKT_TOP], ax
    jle .o
    mov [es:CPD_TB + CPKT_TOP], ax
.o:
    ret

; -----------------------------------------------------------------------------
; cpd_tabs - the filter strip: All, then each category a row has, the chosen
;            one barred. Each tab is cpk_tabs' with the one label (and the
;            empty string that ends it) so the strip can be any subset.
; in:  AH = the categories to DRAW, a bit each (0FFh all). A filter change
;      draws the two tabs whose look changed and steps past the others at
;      cpk_tabs' widths - 4 + 4 + 1, and 8 a character
; out: nothing; AX BX CX DX SI DI spent
; -----------------------------------------------------------------------------
cpd_tabs:
    mov cx, CPD_XL
    mov dx, CPD_TABY
    mov bh, [es:CPD_MASK]
    mov di, cpd_cn
    xor bl, bl                  ; BL = the category, 0 All
.c:
    shr ah, 1
    sbb al, al                  ; AL = 0FFh draw it, 0 step past it
    shr bh, 1
    jnc .nx                     ; no row has it: no tab
    mov si, [cs:di]
    or al, al
    jz .step
    mov al, bl
    xor al, [es:CPD_FLT]        ; 0 = the chosen one
    call cpk_tabs               ; CX = past it
    jmp short .nx
.step:
    inc cx
.w:
    add cx, 8
    cs lodsb
    or al, al
    jnz .w
.nx:
    inc di
    inc di
    inc bx
    or bh, bh
    jnz .c
    ret

; -----------------------------------------------------------------------------
; cpd_hdr - the column heads: one run on a light grey band. The line is spaces
; to the table's right with each head laid over them at its cell, a wide
; window's extra width going between the columns ([CPD_KC] cells a gap)
; -----------------------------------------------------------------------------
cpd_hdr:
    mov ax, [es:CPD_TB + CPKT_W]
    sub ax, CPD_NX
    mov cl, 3
    shr ax, cl
    cmp ax, 95
    jbe .l
    mov ax, 95
.l:
    xchg ax, cx
    mov di, CPW_W_STR
    mov al, ' '
    rep stosb
    mov [es:di], cl             ; (CX = 0) the NUL
    mov si, cpd_hd
    xor dx, dx                  ; DX = the air so far
.h:
    cs lodsw                    ; AX = a head, 0 the end
    or ax, ax
    jz .band
    xchg ax, bx
    cs lodsb                    ; AL = its cell before any air
    cbw
    add ax, dx
    add ax, CPW_W_STR
    xchg ax, di
.c:
    mov al, [cs:bx]
    or al, al
    jz .nx
    stosb
    inc bx
    jmp short .c
.nx:
    add dx, [es:CPD_KC]
    jmp short .h
.band:
    mov byte [gfx_color], CLGRAY
    mov ax, CPD_XL                  ; the band round the run
    mov bx, CPD_HDRY
    mov cx, [es:CPD_XA + CPD_XTR]
    mov dx, bx
    inc dx
    call cpw_fill
    add bx, CPD_HDRH - 2
    add dx, CPD_HDRH - 2
    call cpw_fill
    sub bx, CPD_HDRH - 4
    mov dx, bx
    add dx, 7
    mov cx, CPD_XL + CPD_NX - 1
    call cpw_fill
    mov cx, CPD_XL + CPD_NX
    mov dx, bx
    mov si, CPW_W_STR
    mov ax, (CLGRAY << 8) | CBLACK
    mov bl, 2
    call cpw_run                    ; CX = past it
    mov ax, cx
    mov cx, [es:CPD_XA + CPD_XTR]
    cmp ax, cx
    jg .r
    mov byte [gfx_color], CLGRAY
    mov bx, dx
    add dx, 7
    jmp cpw_fill
.r:
    ret

; cpd_cpyn - SI = a string in segment BL (0 CS, 1 DS, 2 ES): at most CX of its
; characters at ES:DI, DI advanced past them (no NUL written). CX SI spent
cpd_cpyn:
    push ax
    push ds
    call cpk_ds
.c:
    mov al, [si]                ; (DS = the string's: not lodsb, which
    or al, al                   ; os88ovlchk refuses in a module image)
    jz .z
    inc si
    stosb
    loop .c
.z:
    pop ds
    pop ax
    ret

; cpd_pad - spaces at ES:DI up to the address in AX, and the NUL. AX CX spent
cpd_pad:
    sub ax, di
    jb .z
    xchg ax, cx
    mov al, ' '
    rep stosb
.z:
    mov byte [es:di], 0
    ret

; cpd_rowp - AL = a drv_tab row -> BX = its address. Keeps the rest
cpd_rowp:
    push ax
    mov ah, DRVR_SIZE
    mul ah
    add ax, drv_tab
    xchg ax, bx
    pop ax
    ret

; cpd_name - a row's name: AL = the drv_tab row, BP = its catalog record (0
; none). out: SI/BL = the catalog's long name (ES), else its drv_tab title
; staged by CPG_DRVTTL (DS). AH spent
cpd_name:
    or bp, bp
    jz .t
    lea si, [bp + CWD_C_LONG]
    mov bl, 2
    ret
.t:
    mov ah, CPG_DRVTTL
    call cpw_gate               ; SI = cp_sbuf
    mov bl, 1
    ret

; cpd_memstr - a row's memory figure, as the compact page prints it (SPEC.md
; 31.6.2): '~', the KB to the half, 'K', and '+' for a store it sizes
; in:  AL = a row, ES:DI = where. out: DI at the NUL; AX BX CX DX SI spent
cpd_memstr:
    mov ah, CPG_DRVMEM
    call cpw_gate               ; AX = the half-KB word, DRVM_PLUS in bit 15
    mov bx, ax
    and ax, 0x7FFF
    jz .z
    push ax
    mov al, '~'
    stosb
    pop ax
    shr ax, 1
    sbb si, si                  ; SI = -1 for a half
    call cpw_utoa
    or si, si
    jz .k
    mov ax, '.5'
    stosw
.k:
    mov al, 'K'
    stosb
    or bx, bx
    jns .z
    mov al, '+'
    stosb
.z:
    mov byte [es:di], 0
    ret

; cpd_blit12 - the 12x12 check box: SI = its 12 pattern words in the image,
; AX/BX = x/y content-relative. Expanded to 4bpp (set = black, clear = white)
; in the icon staging buffer and put down with ONE OSAPI_GFX_BLIT4. Keeps all
; (cpw_vid.inc's Display page draws its tick boxes with it too)
cpd_blit12:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    push ax
    push bx
    mov di, CPW_W_ICON
    mov bp, 12
.r:
    cs lodsw
    xchg ax, dx
    mov cx, 6
.b:
    mov al, 0xFF
    shl dx, 1
    jnc .a
    and al, 0x0F
.a:
    shl dx, 1
    jnc .s
    and al, 0xF0
.s:
    stosb
    loop .b
    dec bp
    jnz .r
    pop bx
    pop ax
    add ax, [es:CPW_W_OX]
    add bx, [es:CPW_W_OY]
    mov cx, 12
    mov dx, cx
    mov bp, 6
    mov si, CPW_W_ICON
    call KERNEL_SEG:api_gfx_blit4
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; cpd_row - the table's row painter (CPKT_ROW, SPEC.md 135.5)
; in:  AX = the list's row, BL = its ground (CWHITE, CBLUE selected), DX = its
;      top - CX and DI, its left and width, are the block's own, and CPD_XA
;      has every x of it. out: nothing; every register kept
;
; The whole row, opaque, in the spans AROUND its runs: nothing is written
; twice. Row-relative: row 0 and 17 the ground; 1-16 the icon (2..17), the
; name (20), the badge (12 cells: its paper over rows 3-14, the label on 5-12),
; the memory, and the Start at boot check box (12x12 at rows 3-14). The ground
; is twelve spans (cpd_rtg) and the badge's paper two (cpd_rtp); a wide
; window's air between the name and the badge and between the badge and the
; memory is those runs' own spaces - so a row is 19 primitives at either width
; (it was 21 at 616 and 23 at 760 until driver size pass 2).
; -----------------------------------------------------------------------------
cpd_row:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    mov [es:CPK_S_Y], dx
    mov [es:CPK_S_B], bl
    xchg ax, si
    mov al, [es:si + CPD_ROWS]
    mov [es:CPK_S_I], al        ; the drv_tab row
    mov al, bl                  ; --- the ground round everything on it
    mov si, cpd_rtg
    call cpd_rects
    mov al, [es:CPK_S_I]        ; --- the icon: the catalog's, or the gear
    call cpw_cat
    mov bp, di                  ; BP = the record, 0 = none
    mov al, CWI16_GEAR
    jnc .rec
    xor bp, bp
    jmp short .ic
.rec:
    mov al, [es:di + CWD_C_ICON]
    cmp al, CWI16_N
    jb .ic
    mov al, CWI16_GEAR
.ic:
    mov cx, CPD_XL + 2
    mov dx, [es:CPK_S_Y]
    inc dx
    xor ah, ah
    mov bl, [es:CPK_S_B]
    call cpw_icon
    mov al, [es:CPK_S_I]        ; --- the name: 22 cells, and the air to the
    call cpd_name               ; badge as spaces
    mov di, CPW_W_STR
    mov cx, CPD_NW
    call cpd_cpyn
    mov ax, [es:CPD_KC]
    add ax, CPW_W_STR + CPD_NW
    call cpd_pad
    mov di, CPD_MSTR            ; --- the memory: the air from the badge as
    mov cx, [es:CPD_KC]         ; spaces, then ' ~12K+' in 8 cells
    inc cx
    mov al, ' '
    rep stosb
    mov al, [es:CPK_S_I]
    call cpd_memstr
    mov ax, [es:CPD_KC]
    add ax, CPD_MSTR + 8
    call cpd_pad
    mov al, [es:CPK_S_I]        ; --- the badge: drv_status's own reading of
    call cpd_rowp               ; the live row, a reported reason outranking
    mov al, [bx + DRVR_ERR]     ; 'Loaded' - cpd_pl's order: loaded, off, no
    dec ax                      ; hardware, any other reason
    cmp al, DRVE_NERR - 1
    jae .n                      ; (0, or past the strings: no reason)
    cmp al, DRVE_HW - 1
    mov al, 2
    je .st
    inc ax
    jmp short .st
.n:
    xor ax, ax
    cmp [bx + DRVR_SEG], ax
    jne .st
    inc ax
.st:
    mov ah, 14
    mul ah
    add ax, cpd_pl
    push ax                     ; its label...
    xchg ax, bx
    mov al, [cs:bx + 13]        ; ...and its paper, after the label's NUL
    push ax
    mov si, cpd_rtp
    call cpd_rects
    pop ax
    mov ah, al
    mov al, CBLACK
    pop si
    mov cx, [es:CPD_XA + CPD_XB]
    mov dx, [es:CPK_S_Y]
    add dx, 5
    xor bl, bl
    call cpw_run
    mov ah, [es:CPK_S_B]        ; --- the name and the memory: black on
    mov al, CBLACK              ; white, white on the selection's blue
    cmp ah, CBLUE
    jne .ink
    mov al, CWHITE
.ink:
    mov bl, 2
    mov si, CPW_W_STR
    mov cx, CPD_XL + CPD_NX
    call cpw_run
    mov si, CPD_MSTR
    mov cx, [es:CPD_XA + CPD_XM]
    call cpw_run
    mov al, [es:CPK_S_I]        ; --- the box: checked when the row is WANTED
    call cpd_rowp
    mov si, cpd_ck0
    cmp byte [bx + DRVR_WANT], 0
    je .ck
    mov si, cpd_ck1
.ck:
    mov ax, [es:CPD_XA + CPD_XCM]
    inc ax
    mov bx, dx
    dec bx
    dec bx                      ; (DX = the row's top + 5)
    call cpd_blit12
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; cpd_rects - a row's spans in pen AL: SI = a table in the image of (x1, x2,
; y1, y2) - the x's CPD_XA slots, the y's from the row's top [CPK_S_Y] - and
; 0FFh to end it. AX BX CX DX SI spent
cpd_rects:
    mov [gfx_color], al
.f:
    cs lodsw                    ; AL/AH = the x slots
    cmp al, 0FFh
    je .r
    mov bl, ah
    xor bh, bh
    mov cx, [es:bx + CPD_XA]
    mov bl, al
    push word [es:bx + CPD_XA]
    cs lodsw                    ; AL/AH = the rows
    mov bl, al
    mov dl, ah
    mov dh, bh
    mov ax, [es:CPK_S_Y]
    add bx, ax
    add dx, ax
    pop ax
    call cpw_fill
    jmp short .f
.r:
    ret

; -----------------------------------------------------------------------------
; cpd_row1 - repaint one list row if it is showing
; in:  AX = the list's row (0FFFFh none). out: nothing; BX CX DX spent
; -----------------------------------------------------------------------------
cpd_row1:
    mov cx, ax
    sub cx, [es:CPD_TB + CPKT_TOP]
    jl .o
    cmp cx, [es:CPD_TB + CPKT_NV]
    jge .o
    mov bl, CWHITE
    cmp ax, [es:CPD_TB + CPKT_SEL]
    jne .g
    mov bl, CBLUE
.g:
    xchg ax, cx
    mov dl, CPD_RH
    mul dl
    add ax, CPD_ROWY
    xchg ax, dx                 ; DX = its top
    xchg ax, cx                 ; AX = the row again
    jmp cpd_row
.o:
    ret

; -----------------------------------------------------------------------------
; cpd_setsel - select list row AX, redrawing what changed: the row losing the
;              bar and the row gaining it (or, when the selection scrolls the
;              view, the rows and the scroll bar's thumb), and the DETAILS
; in:  AX = a list row, in range. out: nothing
; -----------------------------------------------------------------------------
cpd_setsel:
    mov si, [es:CPD_TB + CPKT_SEL]
    cmp ax, si
    je .r
    mov [es:CPD_TB + CPKT_SEL], ax
    mov bx, ax
    mov cl, [es:bx + CPD_ROWS]
    mov [es:CPD_SELR], cl
    mov dx, [es:CPD_TB + CPKT_TOP]  ; DX = the view's top
    mov cx, ax
    cmp ax, dx
    jl .scr                     ; above it: the selection becomes the top
    sub cx, [es:CPD_TB + CPKT_NV]
    inc cx                      ; CX = the top that makes it the last row
    cmp cx, dx
    jle .vis                    ; ...not below the top it has: in view
.scr:
    mov bx, CPD_TB
    mov [es:bx + CPKT_TOP], cx
    call cpk_tbrows             ; the rows, and the thumb moved (SPEC.md
    call cpk_tbsb               ; 13.10.4: three calls, not the bar's
    xchg ax, dx                 ; sixteen) - AX = the pos it was at
    CPWC os88ui_sbmove
    jmp short .det
.vis:
    call cpd_row1               ; the new one...
    xchg ax, si
    call cpd_row1               ; ...and the one losing the bar
.det:
    jmp cpd_det
.r:
    ret

; -----------------------------------------------------------------------------
; cpd_det - the DETAILS body for the selected row: its 32x32 icon, long name,
;           file, description, status sentence, memory and the four buttons.
;           Every line is one opaque padded run (cpk_text), the buttons erase
;           their own interior, so nothing is cleared first; and the icon and
;           each button go down only when that look is not on the glass
;           already (CPD_DIC, CPD_DBT - which cpd_paint forgets)
; in:  nothing. out: nothing
; -----------------------------------------------------------------------------
cpd_det:
    xor bp, bp                  ; BP = the catalog record, 0 = none
    mov al, [es:CPD_SELR]
    cmp al, 0FFh
    je .ic
    call cpw_cat
    jc .ic
    mov bp, di
.ic:
    xor al, al                  ; --- the icon: the category's header icon
    or bp, bp
    jz .i1
    mov al, [es:bp + CWD_C_CAT]
    cmp al, CWC_N
    jb .i1
    xor al, al
.i1:
    mov bx, cpd_c32
    cs xlatb
    cmp al, [es:CPD_DIC]
    je .nm
    mov [es:CPD_DIC], al
    mov ah, 1
    mov bl, CWHITE
    mov cx, CPD_XL + 8
    mov dx, [es:CPD_GT]
    add dx, CPK_BANDH + 4
    call cpw_icon
.nm:
    call cpd_sp                 ; --- the long name
    je .n1
    call cpd_name
.n1:
    mov dx, CPK_BANDH + 4
    call cpd_dlb
    call cpd_sp                 ; --- the file
    je .fl
    call cpd_rowp
    mov si, [bx + DRVR_FILE]
    mov bl, 1
.fl:
    mov dx, CPK_BANDH + 15
    mov ax, (CWHITE << 8) | CDGRAY
    call cpd_dl
    mov si, CWD_C_D1            ; --- the description, two lines
    mov dx, CPK_BANDH + 29
    call .desc
    mov si, CWD_C_D2
    mov dx, CPK_BANDH + 39
    call .desc
    call cpd_sp                 ; --- the status sentence
    je .st
    mov ah, CPG_DRVSTAT
    call cpw_gate               ; SI = cp_sbuf
    mov bl, 1
.st:
    mov dx, CPK_BANDH + 53
    call cpd_dlb
    mov di, CPW_W_ICON + 384    ; --- the memory, composed in the icon buffer
    xor bl, bl                  ; (cpk_text's own line is CPW_W_STR)
    mov si, cpd_s_mem
    mov cx, 8
    call cpd_cpyn
    mov byte [es:di], 0
    call cpd_sp
    je .mm
    call cpd_memstr
.mm:
    mov si, CPW_W_ICON + 384
    mov bl, 2
    mov dx, CPK_BANDH + 64
    call cpd_dlb
    xor ax, ax                  ; --- the buttons
.b:
    call cpd_btn
    inc ax
    cmp al, 4
    jb .b
    ret
.desc:                          ; SI = CWD_C_D1 / D2, DX = the line's top
    xor bl, bl
    or bp, bp
    jz .dk
    mov ax, [es:bp + si]
    or ax, ax
    jz .dk
    add ax, CPW_WSZ
    xchg ax, si
    mov bl, 2
    jmp short cpd_dlb
.dk:
    mov si, cpd_s_sp
    ; falls into cpd_dlb

; cpd_dl - one DETAILS text line: DX = its top, box-relative; SI = the string
; in segment BL; AX = ink / paper (cpd_dlb: black on white). One opaque padded
; run (cpk_text), as wide as the box less its text column and a margin, at
; most 95 cells. CX DX DI spent
cpd_dlb:
    mov ax, (CWHITE << 8) | CBLACK
cpd_dl:
    add dx, [es:CPD_GT]
    mov di, [es:CPD_TB + CPKT_W]
    sub di, CPD_TXC + 8
    mov cl, 3
    shr di, cl
    cmp di, 95
    jbe .w
    mov di, 95
.w:
    mov cx, CPD_XL + CPD_TXC
    jmp cpk_text

; cpd_sp - a DETAILS line's blank (SI/BL = ' ' in the image), and the row to
; read the real one from: AL = [CPD_SELR], ZF = 1 when there is none
cpd_sp:
    mov si, cpd_s_sp
    xor bl, bl
    mov al, [es:CPD_SELR]
    cmp al, 0FFh
    ret

; -----------------------------------------------------------------------------
; The buttons: Load, Unload, Settings..., Ports... (SPEC.md 135.8). Each is
; (x, width less one, label); a press arms CPW_ID0 + its number and acts on
; the release, over it (SPEC.md 13.8.3)
; -----------------------------------------------------------------------------

; cpd_page - the page a loaded row's driver publishes (SPEC.md 31.9)
; in:  AL = a drv_tab row. out: CF = 0 and AL = that page's record; CF = 1
;      none. Every other register kept
cpd_page:
    push bx
    push cx
    call cpd_rowp
    mov ch, [bx + DRVR_CLASS]
    xor cl, cl                  ; CL = the page's ordinal
.k:
    mov al, cl
    CPWC drv_cp_class_x         ; AL = its class, CF = 1 past the last
    jc .o
    inc cx
    cmp al, ch
    jne .k
    mov al, cl
    add al, CP_ITEMS - 1        ; (CF = 0)
.o:
    pop cx
    pop bx
    ret

; cpd_bflags - DI = OS88UI_DIS, or 0 when button AL is live: Load on a row
; that is down, Unload on one that is up or wanted (the compact page's "stop
; asking", SPEC.md 31.6), Settings... on a loaded driver that publishes a page,
; Ports... always. Keeps the rest
cpd_bflags:
    push ax
    push bx
    mov di, OS88UI_DIS
    mov ah, al                  ; AH = the button
    cmp ah, 3
    je .en
    mov al, [es:CPD_SELR]
    cmp al, 0FFh
    je .r
    call cpd_rowp
    cmp word [bx + DRVR_SEG], 0
    je .down
    cmp ah, 1                   ; it is up: not Load; Unload; Settings... if
    jb .r                       ; it publishes a page
    je .en
    call cpd_page
    jnc .en
    jmp short .r
.down:
    cmp ah, 1                   ; it is down: Load; not Settings...; Unload
    jb .en                      ; if it is wanted
    ja .r
    cmp byte [bx + DRVR_WANT], 0
    je .r
.en:
    xor di, di
.r:
    pop bx
    pop ax
    ret

; cpd_btn - draw button AL, AH = 1 pressed, unless that look is the one on the
; glass (CPD_DBT). Keeps every register
cpd_btn:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov dl, ah
    call cpd_bflags
    or di, di
    jnz .d
    or dl, dl
    jz .d
    mov di, OS88UI_DOWN
.d:
    mov bl, al
    xor bh, bh
    mov dx, di
    cmp [es:bx + CPD_DBT], dl
    je .o
    mov [es:bx + CPD_DBT], dl
    mov al, 6
    mul bl
    add ax, cpd_bt
    xchg ax, si
    mov ax, [cs:si]
    mov cx, ax
    add cx, [cs:si + 2]
    mov bx, [es:CPD_GT]
    add bx, CPD_BTY
    mov dx, bx
    add dx, 17
    mov si, [cs:si + 4]
    call cpk_button
.o:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; cpd_bhit - the button at a point. in: AX/BX = x/y, content-relative. out:
; CF = 0 and AL = the button; CF = 1 none. BX CX DX SI spent
cpd_bhit:
    mov cx, [es:CPD_GT]
    add cx, CPD_BTY
    sub bx, cx
    cmp bx, 18
    jae .no
    mov si, cpd_bt
    xor cl, cl
.l:
    mov dx, ax
    sub dx, [cs:si]
    cmp dx, [cs:si + 2]
    jbe .hit
    add si, 6
    inc cx
    cmp cl, 4
    jb .l
.no:
    stc
    ret
.hit:
    mov al, cl
    clc
    ret

; -----------------------------------------------------------------------------
; cpd_click - a press in the page area while this page shows
; in:  AX/BX = the point, content-relative. out: nothing
; A tab filters; the bar scrolls (cpk_tbclick acts on it); a row presses its
; check box (the want bit alone) or selects; a live button arms and draws down.
; -----------------------------------------------------------------------------
cpd_click:
    mov cx, ax
    mov dx, bx
    cmp dx, CPD_TABY
    jl .r
    cmp dx, CPD_TABY + CPK_TABH - 1
    jle .tabs
    cmp dx, CPD_ROWY
    jl .r
    cmp dx, [es:CPD_GT]
    jl .tbl
    call cpd_bhit
    jc .r
    xor ah, ah
    call cpd_bflags
    or di, di
    jnz .r                      ; a greyed button: nothing arms
    xchg ax, si
    lea ax, [si + CPW_ID0]
    CPWC os88ui_arm
    xchg ax, si
    mov ah, 1
    jmp cpd_btn                 ; ...and drawn down
.tabs:                          ; --- which filter is at this x? (cpk_tabs'
    sub ax, CPD_XL              ; widths, and a gap is the tab before it)
    jl .r
    xchg ax, dx                 ; DX = x from the strip's left
    mov bh, [es:CPD_MASK]
    mov di, cpd_cn
    xor bl, bl
.tc:
    shr bh, 1
    jnc .tn
    mov si, [cs:di]
    dec dx
.tw:
    sub dx, 8
    cs lodsb
    or al, al
    jnz .tw
    or dx, dx
    js .th
.tn:
    inc di
    inc di
    inc bx
    or bh, bh
    jnz .tc
    ret
.th:                            ; BL = the filter pressed
    mov al, bl
    xchg al, [es:CPD_FLT]
    cmp al, bl
    je .r
    mov cl, al                  ; the two tabs whose look changes: the strip,
    mov ah, 1                   ; the table (top 0) and DETAILS
    shl ah, cl
    mov cl, bl
    mov al, 1
    shl al, cl
    or ah, al
    push ax
    mov word [es:CPD_TB + CPKT_TOP], 0
    call cpd_build
    pop ax
    call cpd_tabs
    mov bx, CPD_TB
    call cpk_table
    jmp cpd_det
.tbl:
    mov bx, CPD_TB
    call cpk_tbclick
    jc .r
    cmp ax, 0FFFFh
    je .r                       ; the bar: acted on
    mov si, ax                  ; SI = the list row
    xchg ax, cx
    sub ax, [es:CPD_XA + CPD_XCM]
    add ax, CPD_CKX - 1         ; AX = x from the Start at boot column
    cmp ax, 104                 ; (unsigned: left of it wraps)
    jae .sel
    mov al, [es:si + CPD_ROWS]
    call cpd_rowp
    mov cl, [bx + DRVR_WANT]
    xor cl, 1
    mov ah, CPG_DRVWANT         ; the want bit ALONE
    call cpw_gate
    xchg ax, si
    jmp cpd_row1
.sel:
    xchg ax, si
    jmp cpd_setsel
.r:
    ret

; -----------------------------------------------------------------------------
; cpd_rel - the release of a wide control: AX = the id the press armed (spent
; by os88ui_fire), CX/DX = the SCREEN point. The button is drawn up FIRST; it
; acts only when the release is over it
; -----------------------------------------------------------------------------
cpd_rel:
    sub ax, CPW_ID0
    cmp ax, 4
    jae .r
    push ax
    call cpd_btn                ; (AH = 0: up)
    xchg ax, cx
    sub ax, [es:CPW_W_OX]
    mov bx, dx
    sub bx, [es:CPW_W_OY]
    call cpd_bhit
    pop bx
    jc .r
    cmp al, bl
    jne .r
    mov al, [es:CPD_SELR]
    cmp bl, 2
    jb .lu
    ja .ports
    call cpd_page               ; Settings...: that driver's page
    jc .r
    jmp cpw_select
.ports:                         ; Ports...: the compact view, hosted
    mov byte [cp_dview], 1
    mov byte [es:CPD_ON], 0
    jmp cpw_page
.lu:
    mov ah, CPG_DRVON           ; Load, or Unload
    add ah, bl
    call cpw_gate
    mov al, [es:CPW_W_NL]       ; --- a driver coming up or going may have
    push ax                     ; brought or taken its page: the list, when
    call cpw_lbuild             ; its length moved
    pop ax
    cmp al, [es:CPW_W_NL]
    je .ns
    call cpw_list
.ns:
    xor al, al
    call cpw_status             ; the count, if it moved
    mov ax, [es:CPD_TB + CPKT_SEL]
    call cpd_row1
    jmp cpd_det
.r:
    ret

; -----------------------------------------------------------------------------
; cpd_key - Up / Down move the selection. AX = the key word. out: nothing
; (with nothing selected there are no rows, so either way is past the end)
; -----------------------------------------------------------------------------
cpd_key:
    mov bx, [es:CPD_TB + CPKT_SEL]
    inc bx
    cmp ah, 0x50
    je .go
    dec bx
    dec bx
    cmp ah, 0x48
    jne .r
.go:
    cmp bx, [es:CPD_TB + CPKT_N]
    jae .r
    xchg ax, bx
    jmp cpd_setsel
.r:
    ret

; --- the image's tables and strings -------------------------------------------
; a row's spans (x1, x2 as CPD_XA slots; y1, y2 from the row's top): the
; ground's, then the badge's paper's
cpd_rtg:
    db CPD_XL0, CPD_XR,  0, 0           ; row 0
    db CPD_XL0, CPD_XR,  17, 17         ; row 17
    db CPD_XL0, CPD_XL1, 1, 16          ; the margin before the icon
    db CPD_XN0, CPD_XR,  1, 2           ; rows 1-2 and 15-16 past the icon
    db CPD_XN0, CPD_XR,  15, 16
    db CPD_XN0, CPD_XBM, 3, 4           ; over and under the name
    db CPD_XN0, CPD_XBM, 13, 14
    db CPD_XN0, CPD_XN1, 5, 12          ; the air before the name's run
    db CPD_XM,  CPD_XCM, 3, 4           ; over and under the memory, to the box
    db CPD_XM,  CPD_XCM, 13, 14
    db CPD_XME, CPD_XCM, 5, 12          ; the air after the memory's run
    db CPD_XCE, CPD_XR,  3, 14          ; past the box
    db 0FFh
cpd_rtp:
    db CPD_XB,  CPD_XBE, 3, 4           ; the badge's paper over its label
    db CPD_XB,  CPD_XBE, 13, 14         ; ...and under it
    db 0FFh + 0 * (1 / (CPKT_X == 0 && CPKT_Y == 2 && CPKT_W == 4 && CPKT_RH == 6))
    ; (...and a check that costs no byte: cpd_paint lays the table block's
    ; CPKT_X, Y, W and RH out with stosw, in that order, and nasm stops on a
    ; division by zero here if cpwkit.inc ever moves them - an %if cannot see
    ; them, the kit being %included after this file)
cpd_s_det:  db 'DETAILS', 0
cpd_s_sp:   db ' ', 0
cpd_s_mem:  db 'Memory: ', 0
cpd_cn:     dw cpd_s_all, cpd_n1, cpd_n2, cpd_n3, cpd_n4, cpd_n5, cpd_n6, cpd_n7
cpd_s_all:  db 'All', 0, 0              ; (All, then CWC_DISP..SYS)
cpd_n1:     db 'Display', 0, 0
cpd_n2:     db 'Sound', 0, 0
cpd_n3:     db 'Storage', 0, 0
cpd_n4:     db 'Network', 0, 0
cpd_n5:     db 'Input', 0, 0
cpd_n6:     db 'Memory', 0, 0
cpd_n7:     db 'System', 0, 0
; the column heads, each with its cell before any air: Name (22 cells), the
; 12-cell Status column's word, the 8-cell Memory column's, Start at boot
cpd_hd:     dw cpd_h0
            db 0
            dw cpd_h1
            db CPD_NW + 3
            dw cpd_n6
            db CPD_NW + 12 + 1
            dw cpd_h3
            db CPD_NW + 12 + 8
            dw 0
cpd_h0:     db 'Name', 0
cpd_h1:     db 'Status', 0
cpd_h3:     db 'Start at boot', 0
; the badges, 12 characters each, and each one's paper after its NUL (loaded,
; off, no hardware, any other refusal): 14 bytes a badge
cpd_pl:     db '   Loaded   ', 0, CPD_GRN
            db '    Off     ', 0, CLGRAY
            db 'No hardware ', 0, CPD_RED
            db '   Error    ', 0, CPD_YEL
; a category's 32x32 header icon, by CWC_*
cpd_c32:    db CWI32_GEAR, CWI32_DISP, CWI32_SOUND, CWI32_HDD, CWI32_NET
            db CWI32_GEAR, CWI32_GEAR, CWI32_GEAR
; the buttons: x content-relative, width less one, label
cpd_bt:     dw CPD_XL + CPD_TXC,       56 - 1, cpd_b0
            dw CPD_XL + CPD_TXC + 64,  64 - 1, cpd_b1
            dw CPD_XL + CPD_TXC + 136, 104 - 1, cpd_b2
            dw CPD_XL + CPD_TXC + 248, 80 - 1, cpd_b3
cpd_b0:     db 'Load', 0
cpd_b1:     db 'Unload', 0
cpd_b2:     db 'Settings...', 0
cpd_b3:     db 'Ports...', 0
; the check box: 12 rows of 12 bits, bit 15 leftmost
cpd_ck0:
    dw 0xFFF0, 0x8010, 0x8010, 0x8010, 0x8010, 0x8010
    dw 0x8010, 0x8010, 0x8010, 0x8010, 0x8010, 0xFFF0
cpd_ck1:
    dw 0xFFF0, 0x8010, 0x80D0, 0x8190, 0xA310, 0xB610
    dw 0x9E10, 0x8C10, 0x8810, 0x8010, 0x8010, 0xFFF0
