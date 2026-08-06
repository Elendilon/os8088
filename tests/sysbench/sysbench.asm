; =============================================================================
; os8088 - tests/sysbench/sysbench.asm
;
; SYSBENCH: the machine under the graphics. CPU, bus, memory, the clock, the
; scheduler's own interrupt load, the API's far-call floor and the floppy - the
; things PERFORMANCE.md Part 2 quotes without ever having measured on the
; target, and the things a future agent needs in order to price a change it
; cannot run.
;
;   make bench
;   make test TESTAPPS=build/bench.img
;
; The same caution as its sibling: under QEMU the microsecond column is the
; HOST's speed. With `-icount shift=3,sleep=off` the counts column is guest
; INSTRUCTIONS, which is reproducible and is not time. build/bench360.img on a
; real 4.77 MHz 8088 is where these numbers mean what they say.
;
; --- the headline: 8086-nominal clocks against an 8088 -----------------------
;
; PERFORMANCE.md Part 2 ends with "8086-nominal cycle counts under-report an
; 8088 by 20-40%", cites a plan document, and leaves it there - so every margin
; anyone has computed from an instruction-timing table since has rested on a
; range someone remembered. The CPU block measures it: each row runs SB_UNROLL
; copies of one instruction, and the derived table beside it prints the
; MEASURED clocks, the 8086 book figure, and the ratio. The interesting part is
; that the ratio is not one number - it is near 1.0 for `mul`, which is
; execution-bound, and much worse for `nop`, which on an 8088 is starved by a
; 4-byte prefetch queue behind an 8-bit bus. That shape is the actual finding,
; and a single "add 30%" cannot carry it.
;
; One PIT count is EXACTLY four CPU clocks on a period machine: both divide the
; same 14.31818 MHz crystal, the PIT by 12 and the 8088 by 3. So the clock
; column needs no calibration on an IBM PC or XT - and on a turbo clone it is
; wrong by exactly the turbo factor, which is why the block also derives an
; estimated CPU speed from the two execution-bound rows. Two estimates, from
; different instructions, that must agree.
;
; --- the interrupt load ------------------------------------------------------
;
; The one measurement here that is about os8088 rather than about the machine.
; The same fixed workload is timed twice: once with method P, whose cli window
; excludes every interrupt, and once with method T, which includes all of them.
; The difference is what the tick, the mouse and the scheduler cost per second
; of ordinary work - a figure nothing in this tree has ever put a number on,
; and one that bounds every "is there room for this?" question.
;
; --- the floppy --------------------------------------------------------------
;
; dsk_xfer issues one int 13h per sector (SPEC.md 18.4.1), so throughput is
; dominated by rotational latency rather than by bandwidth, and it is the
; reason a 116KB module load is a coffee break. Two reads of the same file are
; timed: the first pays the motor spin-up, the second does not. Both are
; reported, because quoting either alone is misleading.
;
; Prefix sb_.
; =============================================================================

%include "os88api.inc"

    OS88_HEADER 'SYSBENCH', sb_entry

SB_UNROLL   equ 32                ; copies of the instruction under test in one
                                  ; body. Enough that the call, the ret and the
                                  ; two PIT reads are a few percent, few enough
                                  ; that the body stays inside the prefetch
                                  ; behaviour of ordinary code
SB_BWROWS   equ 32                ; the bandwidth shape gfxbench uses, so the
SB_BWCOLS   equ 64                ; RAM rows of the two harnesses are directly
SB_BWBYTES  equ SB_BWROWS * SB_BWCOLS   ; comparable - which is the point of
                                  ; measuring RAM in both (rule 7)
SB_WORKN    equ 800               ; iterations of the interrupt-load workload.
                                  ; One is ~2.5 ms of rep stosw on a 4.77 MHz
                                  ; 8088, so this is two seconds - 36 ticks, a
                                  ; 3% quantisation. At 200 it was 9 ticks and
                                  ; the answer was quantised to 11%
SB_BIGKB    equ 32                ; the heap claim the file reads land in
SB_TICKTRY  equ 30000             ; bound on every wait-for-tick spin here. A
                                  ; stopped tick must produce a wrong number,
                                  ; never a hung machine

; -----------------------------------------------------------------------------
; sb_entry - package entry (SPEC.md 20.2)
; -----------------------------------------------------------------------------
sb_entry:
    push si
    call sb_facts
    call sb_hint                    ; the invitation, so the first thing on
    mov si, sb_tpl                  ; screen is not a blank page
    call OSAPI_WM_CREATE
    jc .out
    mov [sb_win], bx
    mov al, 1
    call OSAPI_WM_SNAP              ; mono only; PRESERVES FLAGS
    mov si, sb_menus
    call OSAPI_MENU_SET
    mov si, sb_onabout
    call OSAPI_ABOUT_SET
    clc
.out:
    pop si
    ret

sb_paint:
    call bl_paint
    ret

; -----------------------------------------------------------------------------
; sb_onkey - R runs, S saves, everything else pages
; -----------------------------------------------------------------------------
sb_onkey:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov [sb_win], si
    mov bl, al
    or bl, 0x20
    cmp bl, 'r'
    je .run
    cmp bl, 's'
    je .save
    call bl_key
    jc .out
    call bl_paint
    jmp short .out
.run:
    call sb_run
    call sb_repaint
    jmp short .out
.save:
    mov si, sb_f_out
    call bl_save
    call bl_paint
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

sb_onclick:
    push ax
    push si
    mov [sb_win], si
    cmp byte [sb_ran], 0            ; never run: a click runs it, which is what
    jne .page                       ; a user who has just read the invitation
    push bx                         ; will try (tests/fontbench's idiom)
    push cx
    push dx
    push di
    call sb_run
    call sb_repaint
    pop di
    pop dx
    pop cx
    pop bx
    jmp short .out
.page:
    mov al, ' '
    xor ah, ah
    call bl_key
    jc .out
    call bl_paint
.out:
    pop si
    pop ax
    ret

sb_oncmd:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov [sb_win], si
    or ah, ah
    jnz .out
    cmp al, 0
    je .run
    cmp al, 1
    je .save
    cmp al, 2
    je .top
    jmp short .out
.run:
    call sb_run
    call sb_repaint
    jmp short .out
.save:
    mov si, sb_f_out
    call bl_save
    call bl_paint
    jmp short .out
.top:
    mov word [bl_top], 0
    call bl_paint
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

sb_onabout:
    push si
    mov word [bl_top], 0
    call bl_paint
    pop si
    ret

; sb_repaint - nothing here draws outside the text, but a page whose status
; line sat stale for the length of a floppy read is worth putting back whole
sb_repaint:
    push ax
    push bx
    push cx
    push dx
    push si
    mov al, CWHITE
    call OSAPI_SET_COLOR
    mov bx, [sb_win]
    call OSAPI_WM_CONTENT           ; AX = content left, DX = content top
    mov bx, dx
    mov cx, ax
    add cx, [sb_cw]
    dec cx
    add dx, [sb_ch]
    dec dx
    call OSAPI_GFX_FILL
    mov si, [sb_win]
    call bl_paint
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; =============================================================================
; sb_facts - what the machine says about itself, before anything is timed
; =============================================================================
sb_facts:
    push ax
    push bx
    push cx
    push dx
    push di
    push es
    call OSAPI_VIDEO
    mov [sb_vw], ax
    mov [sb_vh], bx
    mov [sb_kind], dl
    call OSAPI_CPU_INFO
    mov [sb_cputier], ax
    call OSAPI_MEM_AVAIL
    mov [sb_mlarge], ax
    mov [sb_mtotal], bx
    call OSAPI_SND_CAPS             ; AX = caps word (SND_CAP_*)
    mov [sb_snd], ax
    call OSAPI_XMEM_CAPS            ; AX = KB the pool can still hand out
    mov [sb_xms], ax
    push ds
    pop es
    mov di, sb_syskb
    call OSAPI_SYS_KB
    pop es
    pop di
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; =============================================================================
; sb_run - the whole suite
; =============================================================================
sb_run:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov word [bl_nrow], 0
    mov word [bl_used], 0
    mov word [bl_top], 0
    mov byte [bl_full], 0
    mov byte [sb_ran], 1

    call sb_geom
    call sb_mktab
    call bl_baseline
    mov [sb_bcnt], ax
    mov [sb_bcnt+2], dx

    mov si, sb_p_head
    call bl_progress
    call sb_header
    mov si, sb_p_cpu
    call bl_progress
    call sb_cpu
    call sb_cpuderive
    mov si, sb_p_mem
    call bl_progress
    call sb_mem
    mov si, sb_p_clk
    call bl_progress
    call sb_clock
    mov si, sb_p_isr
    call bl_progress
    call sb_isrload
    mov si, sb_p_os
    call bl_progress
    call sb_os
    mov si, sb_p_dsk
    call bl_progress
    call sb_disk
    call sb_trailer

    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

sb_geom:
    push ax
    push bx
    push cx
    push dx
    mov bx, [sb_win]
    call OSAPI_WM_GEOM
    mov [sb_cw], cx
    mov [sb_ch], dx
    call OSAPI_WM_CONTENT           ; AX = content left, DX = content top -
    mov [bl_cx], ax                 ; bl_progress draws before bl_paint ever
    mov [bl_cy], dx                 ; runs, so it cannot wait for these
    mov cx, [sb_cw]
    mov ax, cx
    mov cl, 3
    shr ax, cl
    cmp ax, BL_MAXLINE
    jbe .c
    mov ax, BL_MAXLINE
.c:
    mov [bl_vcols], ax
    mov ax, [sb_ch]
    shr ax, cl
    mov [bl_vrows], ax
    or ax, ax
    jz .r
    dec ax
.r:
    mov [bl_prows], ax
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; sb_mktab - the RAM row table, gfxbench's shape exactly
sb_mktab:
    push ax
    push cx
    push di
    mov di, sb_rrow
    mov cx, SB_BWROWS
    mov ax, sb_ram
.r:
    mov [di], ax
    add di, 2
    add ax, SB_BWCOLS
    loop .r
    pop di
    pop cx
    pop ax
    ret

; =============================================================================
; the report blocks
; =============================================================================

; -----------------------------------------------------------------------------
; sb_hint - the report an unrun harness shows. Built out of the same arena the
; results use, so it pages and saves like anything else; a run replaces it.
; -----------------------------------------------------------------------------
sb_hint:
    push si
    mov si, sb_s_ttl1
    call bl_sline
    mov si, sb_s_ttl2
    call bl_sline
    call bl_blank
    mov si, sb_h_1
    call bl_sline
    mov si, sb_h_2
    call bl_sline
    call bl_blank
    mov si, sb_h_3
    call bl_sline
    mov si, sb_h_4
    call bl_sline
    mov si, sb_h_5
    call bl_sline
    call bl_blank
    mov si, sb_h_6
    call bl_sline
    mov si, sb_h_7
    call bl_sline
    pop si
    ret

sb_header:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov si, sb_s_ttl1
    call bl_sline
    mov si, sb_s_ttl2
    call bl_sline
    call bl_blank

    mov si, sb_l_cpu
    mov di, sb_n_8086
    cmp byte [sb_cputier], CPU_286
    jne .c1
    mov di, sb_n_286
.c1:
    cmp byte [sb_cputier], CPU_386
    jne .c2
    mov di, sb_n_386
.c2:
    call bl_kvs
    mov si, sb_l_feat
    mov al, [sb_cputier+1]
    xor ah, ah
    call sb_hex
    mov si, sb_l_adapter
    mov al, [sb_kind]
    xor ah, ah
    call sb_num
    mov si, sb_l_scrw
    mov ax, [sb_vw]
    call sb_num
    mov si, sb_l_scrh
    mov ax, [sb_vh]
    call sb_num
    mov si, sb_l_kern
    mov ax, [sb_syskb + SK_KERN]
    call sb_num
    mov si, sb_l_img
    mov ax, [sb_syskb + SK_IMG]
    call sb_num
    mov si, sb_l_buf
    mov ax, [sb_syskb + SK_BUF]
    call sb_num
    mov si, sb_l_heap
    mov ax, [sb_syskb + SK_HEAP]
    call sb_num
    mov si, sb_l_claim
    mov ax, [sb_syskb + SK_CLAIM]
    call sb_num
    mov si, sb_l_mlarge
    mov ax, [sb_mlarge]
    call sb_num
    mov si, sb_l_mtotal
    mov ax, [sb_mtotal]
    call sb_num
    mov si, sb_l_xms
    mov ax, [sb_xms]
    call sb_num
    mov si, sb_l_snd
    mov ax, [sb_snd]
    call sb_hex
    mov si, sb_l_drive
    call bl_lclr
    xor di, di
    call bl_lput
    call bl_drive
    mov [bl_lscr + BL_C_N], al
    call bl_lcommit

    call bl_blank
    mov si, sb_s_pit1
    call bl_sline
    mov si, sb_s_pit2
    call bl_sline
    mov si, sb_s_pit3
    call bl_sline
    mov si, sb_l_ovh
    mov ax, [sb_bcnt]
    mov dx, [sb_bcnt+2]
    mov cx, 9
    call bl_kv
    call bl_blank
    mov si, sb_s_warn1
    call bl_sline
    mov si, sb_s_warn2
    call bl_sline
    mov si, sb_s_warn3
    call bl_sline
    mov si, sb_s_warn4
    call bl_sline
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

sb_num:
    push cx
    push dx
    xor dx, dx
    mov cx, 9
    call bl_kv
    pop dx
    pop cx
    ret

sb_hex:
    push di
    call bl_lclr
    xor di, di
    call bl_lput
    mov di, BL_C_N
    call bl_hex4
    call bl_lcommit
    pop di
    ret

; --- block 1: the instruction rows -------------------------------------------
sb_cpu:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    call bl_blank
    mov si, sb_s_h_cpu
    call bl_sline
    mov si, sb_s_h_cpu2
    call bl_sline
    call bl_head
    mov word [sb_i], 0
.next:
    mov bx, [sb_i]
    cmp bx, SB_NCPU
    jae .done
    mov cl, 3
    shl bx, cl
    add bx, sb_ctab
    mov ax, [bx+2]                  ; the body
    mov [bl_body], ax
    mov ax, [bx+6]                  ; ...and its iteration count
    mov [bl_n], ax
    mov si, [bx]                    ; the label
    xor al, al                      ; method P
    call bl_run
    mov bx, [sb_i]
    shl bx, 1
    shl bx, 1
    add bx, sb_res
    mov ax, [bl_last]               ; bl_run PRESERVES every register: the
    mov dx, [bl_last+2]             ; result is in bl_last, not in DX:AX
    mov [bx], ax
    mov [bx+2], dx
    inc word [sb_i]
    jmp short .next
.done:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; --- block 2: the same rows as clocks, against the 8086 book -----------------
;
; measured clocks x100 = counts * 400 / (N * SB_UNROLL) - exact on a period
; machine, four clocks a count. The ratio column is the number PERFORMANCE.md
; Part 2 has been quoting as a remembered range.
sb_cpuderive:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    call bl_blank
    mov si, sb_s_h_der
    call bl_sline
    mov si, sb_s_h_der2
    call bl_sline
    mov word [sb_i], 0
.next:
    mov bx, [sb_i]
    cmp bx, SB_NCPU
    jae .done
    mov cl, 3
    shl bx, cl
    add bx, sb_ctab
    mov [sb_ent], bx
    mov bx, [sb_i]
    shl bx, 1
    shl bx, 1
    add bx, sb_res
    mov ax, [bx]
    mov dx, [bx+2]
    mov bx, [sb_ent]
    mov cx, [bx+6]                  ; N
    call sb_clkx100                 ; DX:AX = measured clocks x100
    mov [sb_meas], ax
    mov [sb_meas+2], dx

    call bl_lclr                    ; label
    mov bx, [sb_ent]
    mov si, [bx]
    xor di, di
    call bl_lput
    mov ax, [sb_meas]               ; measured
    mov dx, [sb_meas+2]
    mov di, 22
    mov cx, 9
    call bl_dec
    mov bx, [sb_ent]                ; the 8086 book figure
    mov ax, [bx+4]
    xor dx, dx
    mov di, 32
    mov cx, 9
    call bl_dec
    mov ax, [sb_meas]               ; ...and measured / nominal, x100
    mov dx, [sb_meas+2]
    mov bx, [sb_ent]
    mov bx, [bx+4]
    xor cx, cx
    call gb_ratio_sb
    mov di, 42
    mov cx, 9
    call bl_dec
    call bl_lcommit
    inc word [sb_i]
    jmp .next
.done:
    call sb_mhz
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; sb_mhz - the CPU speed, from the two execution-bound rows
;
; MUL and DIV spend most of their time in the sequencer rather than at the bus,
; so their measured clocks should equal the book figure on a 4.77 MHz machine
; whatever the prefetch is doing. Turn that round and the ratio IS the clock:
; MHz x100 = 477 * nominal / measured. Two rows, two estimates, and they have
; to agree - which is the only check available on a machine whose only other
; timebase is the PIT this harness is already using.
sb_mhz:
    push ax
    push bx
    push cx
    push dx
    push si
    call bl_blank
    mov bx, SB_I_MUL
    call sb_est
    mov si, sb_d_mhzmul
    mov cx, 9
    call bl_kv
    mov bx, SB_I_DIV
    call sb_est
    mov si, sb_d_mhzdiv
    mov cx, 9
    call bl_kv
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; sb_est - BX = a sb_ctab index -> DX:AX = estimated MHz x100
sb_est:
    push bx
    push cx
    push si
    push di
    mov di, bx                      ; DI = the entry index
    mov cl, 3
    shl bx, cl
    add bx, sb_ctab
    mov si, [bx+4]                  ; SI = the nominal, clocks x100
    mov cx, [bx+6]                  ; CX = its iteration count
    mov bx, di
    shl bx, 1
    shl bx, 1
    add bx, sb_res
    mov ax, [bx]                    ; DX:AX = the row's counts
    mov dx, [bx+2]
    call sb_clkx100                 ; DX:AX = measured clocks x100 (CX = N)
    mov bx, ax
    mov cx, dx                      ; CX:BX = measured
    mov ax, si                      ; ...and 477 (4.7727 MHz x100) times the
    xor dx, dx                      ; nominal over it
    mov si, 477
    call sb_mul16
    call sb_divby
    pop di
    pop si
    pop cx
    pop bx
    ret

; --- block 3: memory bandwidth (the RAM half; the framebuffer is gfxbench's) -
sb_mem:
    push ax
    push bx
    push cx
    push dx
    push si
    call bl_blank
    mov si, sb_s_h_mem
    call bl_sline
    call bl_head
    mov ax, ds
    mov [sb_seg], ax
    mov word [sb_tab], sb_rrow
    mov word [bl_n], 8
    mov word [bl_body], sb_b_stosw
    mov si, sb_r_sw
    xor al, al
    call bl_run
    mov word [bl_body], sb_b_stosb
    mov si, sb_r_sb
    xor al, al
    call bl_run
    mov word [bl_body], sb_b_movsw
    mov si, sb_r_mw
    xor al, al
    call bl_run
    mov word [bl_body], sb_b_movsb
    mov si, sb_r_mb
    xor al, al
    call bl_run
    mov word [bl_body], sb_b_scasb
    mov si, sb_r_sc
    xor al, al
    call bl_run
    mov word [bl_n], 4
    mov word [bl_body], sb_b_rmw
    mov si, sb_r_rm
    xor al, al
    call bl_run
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; --- block 4: the clock ------------------------------------------------------
sb_clock:
    push ax
    push bx
    push cx
    push dx
    push si
    call bl_blank
    mov si, sb_s_h_clk
    call bl_sline
    call bl_head
    mov word [bl_n], 300
    mov word [bl_body], sb_b_pit
    mov si, sb_r_pit
    xor al, al
    call bl_run
    mov word [bl_body], sb_b_ticks
    mov si, sb_r_gt
    xor al, al
    call bl_run
    mov word [bl_n], 60
    mov word [bl_body], sb_b_bios1a
    mov si, sb_r_1a
    xor al, al
    call bl_run
    mov word [bl_n], 100
    mov word [bl_body], sb_b_int16
    mov si, sb_r_k16
    xor al, al
    call bl_run
                                    ; NO task_sleep ROW. It is a WORKER's call
                                    ; (SPEC.md 20.6) and this runs on the UI
                                    ; task: sch_switch's "nothing ready" leg
                                    ; resumes the outgoing task, so on a quiet
                                    ; machine task 0 sleeping returns at once -
                                    ; measured as 18 sleeps of one tick taking
                                    ; zero ticks - while leaving T_STATE = 2 on
                                    ; a task the scheduler documents as one
                                    ; that never sleeps. Measuring it costs the
                                    ; number nothing and risks the machine.
    call sb_ticklen                 ; PIT counts observed inside one BIOS tick
    mov si, sb_d_tick
    mov cx, 9
    call bl_kv
    call sb_rtc                     ; and whether int 1Ah AH=02h answers at all
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; sb_ticklen - PIT counts inside one BIOS tick
; out: DX:AX = the count
;
; Counter 0 is reloaded with 0, i.e. 65536, so a tick IS 65536 counts by
; construction and this row exists to CHECK that, not to discover it: the whole
; harness converts ticks to counts by that identity (benchlib, method T). What
; it actually measures is 65536 plus the residual between two same-phase
; samples, so a few hundred counts of ISR-entry jitter is expected and a figure
; that is not near 65536 means the timebase assumption is wrong on this
; machine - which would invalidate every method-T row above it.
sb_ticklen:
    push bx
    push cx
    push si
    push di
    call OSAPI_GET_TICKS
    mov si, ax
    mov cx, SB_TICKTRY
.e1:
    call OSAPI_GET_TICKS            ; wait for a tick edge, so both samples are
    cmp ax, si                      ; taken at the same phase
    jne .go
    loop .e1
.go:
    mov si, ax
    call bl_pit
    mov di, ax                      ; DI = the PIT at the edge
    mov cx, SB_TICKTRY
.e2:
    call OSAPI_GET_TICKS
    cmp ax, si
    jne .end
    loop .e2
.end:
    call bl_pit
    mov bx, di
    sub bx, ax                      ; the down-counter's residual, modular
    mov ax, bx
    xor dx, dx
    add ax, 0                       ; ...on top of the 65536 a full wrap costs
    adc dx, 1
    pop di
    pop si
    pop cx
    pop bx
    ret

; sb_rtc - does int 1Ah AH=02h answer? (SPEC.md 37.90 rung 4)
; An XT BIOS implements AH=00h/01h and nothing else, so this is the one thing
; a package can say about the clock ladder from outside the kernel.
sb_rtc:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov ah, 2
    int 0x1A
    jc .no
    mov si, sb_l_rtc
    mov di, sb_n_yes
    call bl_kvs
    mov si, sb_l_rtch                ; the hour, in BCD as the BIOS returns it
    mov al, ch
    xor ah, ah
    call sb_hex
    jmp short .out
.no:
    mov si, sb_l_rtc
    mov di, sb_n_no
    call bl_kvs
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; --- block 5: what the kernel's own interrupts cost --------------------------
sb_isrload:
    push ax
    push bx
    push cx
    push dx
    push si
    call bl_blank
    mov si, sb_s_h_isr
    call bl_sline
    mov si, sb_s_h_isr2
    call bl_sline
    call bl_head
    mov ax, ds
    mov [sb_seg], ax
    mov word [sb_tab], sb_rrow
    mov word [bl_n], SB_WORKN
    mov word [bl_body], sb_b_stosw
    mov si, sb_r_wp
    xor al, al                      ; method P: the cli window excludes every
    call bl_run                     ; interrupt
    mov ax, [bl_last]
    mov dx, [bl_last+2]
    mov [sb_wp], ax
    mov [sb_wp+2], dx
    mov word [bl_n], SB_WORKN
    mov word [bl_body], sb_b_stosw
    mov si, sb_r_wt
    mov al, 1                       ; method T: all of them included
    call bl_run
    mov ax, [bl_last]
    mov dx, [bl_last+2]
    mov [sb_wt], ax
    mov [sb_wt+2], dx

    mov ax, [sb_wt]                 ; (T - P) / T, x100: the share of a second
    mov dx, [sb_wt+2]               ; of ordinary work the tick, the mouse and
    sub ax, [sb_wp]                 ; the scheduler take
    sbb dx, [sb_wp+2]
    jnc .ok
    xor ax, ax
    xor dx, dx
.ok:
    mov bx, [sb_wt]
    mov cx, [sb_wt+2]
    call gb_ratio_sb
    mov si, sb_d_isr
    mov cx, 9
    call bl_kv
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; --- block 6: the API's far-call floor and the scheduler ---------------------
sb_os:
    push ax
    push bx
    push cx
    push dx
    push si
    call bl_blank
    mov si, sb_s_h_os
    call bl_sline
    call bl_head
    mov word [bl_n], 300
    mov word [bl_body], sb_b_near
    mov si, sb_r_nc
    xor al, al
    call bl_run
    mov word [bl_body], sb_b_ticks
    mov si, sb_r_fc
    xor al, al
    call bl_run
    mov word [bl_body], sb_b_yield
    mov si, sb_r_yl
    xor al, al
    call bl_run
    mov word [bl_body], sb_b_rand
    mov si, sb_r_rn
    xor al, al
    call bl_run
    mov word [bl_body], sb_b_here
    mov si, sb_r_hr
    xor al, al
    call bl_run
    mov word [bl_n], 60
    mov word [bl_body], sb_b_dfree
    mov si, sb_r_df
    xor al, al
    call bl_run
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; --- block 7: the floppy -----------------------------------------------------
;
; Both file rows are method T and refuse to be clever: a read is seconds, the
; gfx lock is held for all of it and the machine looks frozen, which is itself
; the finding. A machine whose heap cannot fund the claim, or a volume without
; the data files, records that and moves on - refusal is a normal path
; (PERFORMANCE.md Part 6 rule 9).
sb_disk:
    push ax
    push bx
    push cx
    push dx
    push si
    call bl_blank
    mov si, sb_s_h_dsk
    call bl_sline
    call bl_head
    mov ax, SB_BIGKB
    call OSAPI_MEM_CLAIM            ; DX = the base segment
    jc .noclaim
    mov [sb_bseg], dx

    mov word [bl_n], 1              ; the first read pays the motor spin-up
    mov word [bl_body], sb_b_rdbig
    mov si, sb_r_d1
    mov al, 1
    call bl_run
    mov ax, [bl_last]
    mov dx, [bl_last+2]
    mov [sb_td1], ax
    mov [sb_td1+2], dx
    mov si, sb_l_derr               ; ...and says whether it worked at all
    mov ax, [sb_rerr]
    call sb_num
    mov si, sb_l_dsz
    mov ax, [sb_rsz]
    call sb_num

    mov word [bl_n], 1              ; the second does not
    mov si, sb_r_d2
    mov al, 1
    call bl_run
    mov ax, [bl_last]
    mov dx, [bl_last+2]
    mov [sb_td2], ax
    mov [sb_td2+2], dx

    mov word [bl_n], 4              ; a one-sector file: the per-call cost of
    mov word [bl_body], sb_b_rdsml  ; finding and opening one, with almost no
    mov si, sb_r_ds                 ; data behind it
    mov al, 1
    call bl_run

    mov ax, [sb_bseg]               ; hand the claim back: a benchmark that
    mov dx, ax                      ; holds 32KB for the session changes what
    call OSAPI_MEM_FREE             ; every row after it is measuring
    jmp short .rate
.noclaim:
    mov si, sb_s_noclaim
    call bl_sline
    jmp short .out
.rate:
    mov ax, [sb_td2]                ; bytes per second, from the WARM read.
    mov dx, [sb_td2+2]              ; counts / 1193 is milliseconds exactly
    mov cx, 1193                    ; enough (1.193182 counts per us), and
    call gb_div_sb                  ; bytes * 1000 / ms then fits 32 bits,
    mov bx, ax                      ; which bytes * 1,000,000 / us does not
    mov cx, dx
    or bx, bx
    jnz .have
    or cx, cx
    jnz .have
    mov bx, 1                       ; a read too fast to time: do not divide
.have:                              ; by zero, and the row will say so
    mov ax, [sb_rsz]
    xor dx, dx
    mov si, 1000
    call sb_mul16
    call sb_divby
    mov si, sb_d_rate
    mov cx, 9
    call bl_kv
.out:
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

sb_trailer:
    push si
    call bl_blank
    mov si, sb_s_end1
    call bl_sline
    mov si, sb_s_end2
    call bl_sline
    pop si
    ret

; =============================================================================
; arithmetic
; =============================================================================

; sb_clkx100 - DX:AX counts over CX iterations of SB_UNROLL instructions
; out: DX:AX = 4.77 MHz CPU clocks per instruction, x100
sb_clkx100:
    push cx
    push si
    mov si, cx
    mov cx, 400                     ; four clocks a count, x100
    call bl_mul48
    mov cx, si
    or cx, cx
    jnz .d
    mov cx, 1
.d:
    call bl_div48
    mov cx, SB_UNROLL
    call bl_div48
    call bl_get32
    pop si
    pop cx
    ret

; gb_ratio_sb - (DX:AX / CX:BX) * 100, both 32-bit. gfxbench's gb_ratio, under
; a name of its own so the two harnesses stay independent sources.
gb_ratio_sb:
    push bx
    push cx
    push si
.shift:
    or cx, cx
    jz .have
    shr cx, 1
    rcr bx, 1
    shr dx, 1
    rcr ax, 1
    jmp short .shift
.have:
    or bx, bx
    jnz .div
    mov bx, 1
.div:
    mov si, bx
    mov cx, 100
    call bl_mul48
    mov cx, si
    call bl_div48
    call bl_get32
    pop si
    pop cx
    pop bx
    ret

; gb_div_sb - DX:AX / CX, saturating
gb_div_sb:
    push cx
    push si
    mov si, cx
    mov cx, 1
    call bl_mul48
    mov cx, si
    or cx, cx
    jnz .d
    mov cx, 1
.d:
    call bl_div48
    call bl_get32
    pop si
    pop cx
    ret

; sb_mul16 - DX:AX *= SI, saturating
sb_mul16:
    push cx
    mov cx, si
    call bl_mul48
    call bl_get32
    pop cx
    ret

; sb_divby - DX:AX /= CX:BX (32-bit divisor), by shifting both until the
; divisor fits a word
sb_divby:
    push bx
    push cx
    push si
.shift:
    or cx, cx
    jz .have
    shr cx, 1
    rcr bx, 1
    shr dx, 1
    rcr ax, 1
    jmp short .shift
.have:
    or bx, bx
    jnz .div
    mov bx, 1
.div:
    mov si, bx
    mov cx, 1
    call bl_mul48
    mov cx, si
    call bl_div48
    call bl_get32
    pop si
    pop cx
    pop bx
    ret

; =============================================================================
; the measured bodies
; =============================================================================

; --- the instruction rows. SB_UNROLL copies each, so the call, the ret and the
; two PIT reads around them are amortised down to a few percent, and the
; baseline row takes even that off.

sb_b_nop:
%rep SB_UNROLL
    nop
%endrep
    ret

sb_b_movrr:
%rep SB_UNROLL
    mov ax, bx
%endrep
    ret

sb_b_add:
%rep SB_UNROLL
    add ax, bx
%endrep
    ret

sb_b_inc:
%rep SB_UNROLL
    inc ax
%endrep
    ret

sb_b_cmp:
%rep SB_UNROLL
    cmp ax, bx
%endrep
    ret

sb_b_xchg:
%rep SB_UNROLL
    xchg ax, bx
%endrep
    ret

sb_b_shl1:
%rep SB_UNROLL
    shl ax, 1
%endrep
    ret

sb_b_shlcl:
    mov cl, 4
%rep SB_UNROLL
    shl ax, cl
%endrep
    ret

sb_b_load:
%rep SB_UNROLL
    mov ax, [sb_scr]
%endrep
    ret

sb_b_store:
%rep SB_UNROLL
    mov [sb_scr], ax
%endrep
    ret

; The next two differ by ONE BYTE - the segment override - and nothing else, so
; the gap between their rows is the override's cost with the addressing, the
; prefetch and the loop identical on both sides.
sb_b_noovr:
    mov si, sb_scr
%rep SB_UNROLL
    mov al, [si]
%endrep
    ret

sb_b_ovr:
    push ds
    pop es
    mov si, sb_scr
%rep SB_UNROLL
    mov al, [es:si]
%endrep
    ret

sb_b_jmp:
%rep SB_UNROLL
    jmp short $+2                   ; taken, and it flushes the prefetch queue
%endrep
    ret

sb_b_pushpop:
%rep SB_UNROLL
    push ax
    pop ax
%endrep
    ret

sb_b_callret:
%rep SB_UNROLL
    call sb_nil
%endrep
    ret
sb_nil:
    ret

; MUL and DIV reload their operand every time, so the row is one reload plus
; one arithmetic instruction and the nominal in sb_ctab says so. DIV is
; reloaded rather than chained for a reason that is not tidiness: an 8086
; divide whose quotient will not fit is an INTERRUPT, not a wrong answer, and
; inside a package that is a hung machine.
sb_b_mul:
    mov bx, 7
%rep SB_UNROLL
    mov ax, 0x5555
    mul bx
%endrep
    ret

sb_b_div:
    mov bx, 7
%rep SB_UNROLL
    xor dx, dx
    mov ax, 0x5555
    div bx
%endrep
    ret

; --- memory bandwidth: gfxbench's shape, so the RAM rows can be compared -----

sb_b_stosw:
    push es
    mov es, [sb_seg]
    mov bx, [sb_tab]
    mov si, SB_BWROWS
    xor ax, ax
    cld
.r:
    mov di, [bx]
    mov cx, SB_BWCOLS / 2
    rep stosw
    add bx, 2
    dec si
    jnz .r
    pop es
    ret

sb_b_stosb:
    push es
    mov es, [sb_seg]
    mov bx, [sb_tab]
    mov si, SB_BWROWS
    xor al, al
    cld
.r:
    mov di, [bx]
    mov cx, SB_BWCOLS
    rep stosb
    add bx, 2
    dec si
    jnz .r
    pop es
    ret

sb_b_movsw:
    push es
    push ds
    pop es
    mov di, sb_ram2
    mov si, sb_ram
    mov cx, SB_BWBYTES / 2
    cld
    rep movsw
    pop es
    ret

sb_b_movsb:
    push es
    push ds
    pop es
    mov di, sb_ram2
    mov si, sb_ram
    mov cx, SB_BWBYTES
    cld
    rep movsb
    pop es
    ret

sb_b_scasb:
    push es
    push ds
    pop es
    mov di, sb_ram
    mov cx, SB_BWBYTES
    mov al, 0xFF                    ; never matches, and repNE is what walks
    cld                             ; the whole run on that: `repe` repeats
    repne scasb                     ; while EQUAL, so scanning for a byte that
                                    ; is not there stopped at the first
                                    ; comparison and the row measured 25 us
                                    ; for 2,048 bytes on a 4.77MHz machine -
                                    ; an impossible number that shipped
                                    ; because nothing on a fast host looks
                                    ; impossible (PERFORMANCE.md Part 9)
    pop es
    ret

sb_b_rmw:
    push es
    mov es, [sb_seg]
    mov bx, [sb_tab]
    mov si, SB_BWROWS
.r:
    mov di, [bx]
    mov cx, SB_BWCOLS
.b:
    mov al, [es:di]
    or al, 0
    mov [es:di], al
    inc di
    loop .b
    add bx, 2
    dec si
    jnz .r
    pop es
    ret

; --- the clock and the OS ----------------------------------------------------

sb_b_pit:
    call bl_pit
    ret

sb_b_ticks:
    call OSAPI_GET_TICKS
    ret

sb_b_bios1a:
    xor ah, ah
    int 0x1A                        ; BIOS read tick count
    ret

sb_b_int16:
    mov ah, 1
    int 0x16                        ; BIOS keyboard status, the cheapest real
    ret                             ; BIOS call there is

sb_b_near:
    call sb_nil
    ret

sb_b_yield:
    call OSAPI_TASK_YIELD
    ret

sb_b_rand:
    call OSAPI_RAND
    ret

sb_b_here:
    call OSAPI_FILE_HERE
    ret

sb_b_dfree:
    call OSAPI_FILE_DFREE
    ret

; --- the floppy --------------------------------------------------------------

sb_b_rdbig:
    push es
    mov es, [sb_bseg]
    xor bx, bx
    mov si, sb_f_big
    mov cx, SB_BIGKB * 1024
    xor dx, dx
    call OSAPI_FILE_READ            ; out CF=0 and DX:AX = the file's size
    jc .err
    mov [sb_rsz], ax
    mov word [sb_rerr], 0
    pop es
    ret
.err:
    mov [sb_rerr], ax
    mov word [sb_rsz], 0
    pop es
    ret

sb_b_rdsml:
    push es
    mov es, [sb_bseg]
    xor bx, bx
    mov si, sb_f_sml
    mov cx, 1024
    xor dx, dx
    call OSAPI_FILE_READ
    pop es
    ret

%include "benchlib.inc"

; =============================================================================
; data
; =============================================================================

sb_tpl:
    dw 7, 22, 632, 448
    dw sb_ttl, sb_paint, sb_onkey, sb_onclick

sb_ttl:     db 'Sys Bench', 0

; label, body, 8086 nominal clocks x100, iterations.
;
; The nominal column is Intel's 8086 timing table, the one every margin in this
; tree has been computed from: EA calculation included where the operand needs
; one, and the reload instructions counted where a row has them. It is the
; BOOK figure and not a claim about this machine - the whole point of the row
; beside it is to find out how far apart the two are.
sb_ctab:
    dw sb_c_nop,     sb_b_nop,       300, 800    ; nop
    dw sb_c_movrr,   sb_b_movrr,     200, 800    ; mov r16,r16
    dw sb_c_add,     sb_b_add,       300, 800    ; add r16,r16
    dw sb_c_inc,     sb_b_inc,       200, 800    ; inc r16
    dw sb_c_cmp,     sb_b_cmp,       300, 800    ; cmp r16,r16
    dw sb_c_xchg,    sb_b_xchg,      300, 800    ; xchg ax,r16
    dw sb_c_shl1,    sb_b_shl1,      200, 800    ; shl r16,1
    dw sb_c_shlcl,   sb_b_shlcl,    2400, 400    ; shl r16,cl  (8 + 4*4)
    dw sb_c_load,    sb_b_load,     1400, 400    ; mov ax,[disp16]  (8 + EA 6)
    dw sb_c_store,   sb_b_store,    1500, 400    ; mov [disp16],ax  (9 + EA 6)
    dw sb_c_noovr,   sb_b_noovr,    1300, 400    ; mov al,[si]      (8 + EA 5)
    dw sb_c_ovr,     sb_b_ovr,      1500, 400    ; ...with a segment override
    dw sb_c_jmp,     sb_b_jmp,      1500, 400    ; jmp short, taken
    dw sb_c_pushpop, sb_b_pushpop,  1900, 300    ; push ax + pop ax (11 + 8)
    dw sb_c_callret, sb_b_callret,  2700, 300    ; call near + ret  (19 + 8)
    dw sb_c_mul,     sb_b_mul,      12900, 100   ; mov ax,imm + mul r16 (4+125)
    dw sb_c_div,     sb_b_div,      16000, 60    ; xor + mov + div r16 (3+4+153)
sb_ctab_end:

SB_NCPU  equ (sb_ctab_end - sb_ctab) / 8
SB_I_MUL equ 15                   ; the two execution-bound rows, by index -
SB_I_DIV equ 16                   ; sb_mhz derives the clock from them

sb_c_nop:     db 'nop', 0
sb_c_movrr:   db 'mov r16,r16', 0
sb_c_add:     db 'add r16,r16', 0
sb_c_inc:     db 'inc r16', 0
sb_c_cmp:     db 'cmp r16,r16', 0
sb_c_xchg:    db 'xchg ax,r16', 0
sb_c_shl1:    db 'shl r16,1', 0
sb_c_shlcl:   db 'shl r16,cl (4)', 0
sb_c_load:    db 'mov ax,[disp16]', 0
sb_c_store:   db 'mov [disp16],ax', 0
sb_c_noovr:   db 'mov al,[si]', 0
sb_c_ovr:     db 'mov al,[es:si]', 0
sb_c_jmp:     db 'jmp short (taken)', 0
sb_c_pushpop: db 'push ax + pop ax', 0
sb_c_callret: db 'call near + ret', 0
sb_c_mul:     db 'mov ax,i + mul r16', 0
sb_c_div:     db 'xor+mov+div r16', 0

sb_f_out:   db 'SYSBENCH.TXT', 0
sb_f_big:   db 'BENCH.DAT', 0
sb_f_sml:   db 'BENCHSML.DAT', 0

sb_n_8086:  db '8086/8088 (tier 0)', 0
sb_n_286:   db '80286 (tier 1)', 0
sb_n_386:   db '80386+ (tier 2)', 0
sb_n_yes:   db 'yes', 0
sb_n_no:    db 'no (CF set)', 0

sb_h_1:     db 'The machine under the graphics: 8086 book clocks against this CPU, RAM', 0
sb_h_2:     db 'bandwidth, the clock, what the kernel own interrupts cost, and the floppy.', 0
sb_h_3:     db '   R  or the Bench menu   run it.  About 40 seconds on a 4.77MHz 8088 -', 0
sb_h_4:     db '                          most of it the two 16KB floppy reads - and the', 0
sb_h_5:     db '                          machine is FROZEN throughout. Watch this line.', 0
sb_h_6:     db '   S  or the Bench menu   save the report to the current volume.', 0
sb_h_7:     db '   Space PgDn PgUp Up Dn Home End   page through it afterwards.', 0

sb_p_head:  db 'running: reading the machine...', 0
sb_p_cpu:   db 'running: instruction timings (1 of 6)', 0
sb_p_mem:   db 'running: RAM bandwidth (2 of 6)', 0
sb_p_clk:   db 'running: the clock and the timers (3 of 6)', 0
sb_p_isr:   db 'running: what the kernel interrupts cost - 4 seconds (4 of 6)', 0
sb_p_os:    db 'running: the API far-call floor (5 of 6)', 0
sb_p_dsk:   db 'running: the floppy - two 16KB reads, the slow one (6 of 6)', 0

sb_s_ttl1:  db 'os8088 SYSBENCH - cpu, bus, memory, clock, scheduler, floppy', 0
sb_s_ttl2:  db '============================================================', 0

sb_l_cpu:     db 'cpu tier', 0
sb_l_feat:    db 'cpu feature bits', 0
sb_l_adapter: db 'video kind 0/1/2', 0
sb_l_scrw:    db 'screen width px', 0
sb_l_scrh:    db 'screen height px', 0
sb_l_kern:    db 'kernel span KB', 0
sb_l_img:     db 'kernel image KB', 0
sb_l_buf:     db 'fat+stacks+bufs KB', 0
sb_l_heap:    db 'claim heap KB', 0
sb_l_claim:   db 'claimed out of it KB', 0
sb_l_mlarge:  db 'largest free run KB', 0
sb_l_mtotal:  db 'total free KB', 0
sb_l_xms:     db 'above 1MB free KB', 0
sb_l_snd:     db 'sound caps word', 0
sb_l_drive:   db 'current volume', 0
sb_l_ovh:     db 'loop overhead counts', 0
sb_l_rtc:     db 'int 1Ah AH=02h', 0
sb_l_rtch:    db '  its hour, BCD', 0
sb_l_derr:    db '  read error code', 0
sb_l_dsz:     db '  bytes read', 0

sb_s_pit1:  db 'One PIT count is 838 ns and EXACTLY four 4.77MHz CPU clocks: both', 0
sb_s_pit2:  db 'divide the 14.31818MHz crystal, the PIT by 12 and the 8088 by 3.', 0
sb_s_pit3:  db 't = tick-timed, ! = near the 55ms wrap, w = it LAPPED and is tick-timed.', 0
sb_s_warn1: db 'CAUTION: under QEMU every time column is the HOST speed. Boot with', 0
sb_s_warn2: db '-icount shift=3,sleep=off and read counts as guest INSTRUCTIONS.', 0
sb_s_warn3: db 'A tick-timed (t) row of 0 counts means it finished inside one 55ms', 0
sb_s_warn4: db 'tick - true on a fast host, and never true on the machine this is for.', 0

sb_s_h_cpu:  db '-- cpu: 32 copies of one instruction per iteration --', 0
sb_s_h_cpu2: db '   (us/op is the whole 32, not one instruction - see the table below)', 0
sb_s_h_der:  db '-- the same rows as clocks, against the 8086 book --', 0
sb_s_h_der2: db 'instruction           measx100  nom x100  ratiox100', 0
sb_s_h_mem:  db '-- RAM bandwidth: 2048 bytes an iteration (gfxbench has the VRAM) --', 0
sb_s_h_clk:  db '-- the clock and the timers --', 0
sb_s_h_isr:  db '-- what the kernel own interrupts cost --', 0
sb_s_h_isr2: db '   the same work timed with interrupts off, then with them on', 0
sb_s_h_os:   db '-- the API far-call floor and the scheduler --', 0
sb_s_h_dsk:  db '-- the floppy: one int 13h per sector, so latency not bandwidth --', 0

sb_r_sw:   db 'RAM rep stosw', 0
sb_r_sb:   db 'RAM rep stosb', 0
sb_r_mw:   db 'RAM rep movsw', 0
sb_r_mb:   db 'RAM rep movsb', 0
sb_r_sc:   db 'RAM repe scasb', 0
sb_r_rm:   db 'RAM read-mod-write', 0

sb_r_pit:  db 'PIT latch + read', 0
sb_r_gt:   db 'OSAPI GET_TICKS', 0
sb_r_1a:   db 'int 1Ah AH=00h', 0
sb_r_k16:  db 'int 16h AH=01h', 0

sb_r_wp:   db 'work, interrupts off', 0
sb_r_wt:   db 'work, interrupts on', 0

sb_r_nc:   db 'near call + ret', 0
sb_r_fc:   db 'API far call cell', 0
sb_r_yl:   db 'TASK_YIELD', 0
sb_r_rn:   db 'RAND', 0
sb_r_hr:   db 'FILE_HERE', 0
sb_r_df:   db 'FILE_DFREE', 0

sb_r_d1:   db 'read 16K, cold motor', 0
sb_r_d2:   db 'read 16K, warm', 0
sb_r_ds:   db 'read 1 sector file', 0

sb_d_mhzmul: db 'est CPU MHz x100 MUL', 0
sb_d_mhzdiv: db 'est CPU MHz x100 DIV', 0
sb_d_tick:   db 'PIT/tick want 65536', 0
sb_d_isr:    db 'interrupt load pct', 0
sb_d_rate:   db 'floppy bytes/sec', 0

sb_s_noclaim: db '  (no 32KB heap claim available: the file rows were skipped)', 0

sb_s_end1:  db 'End of report. R re-runs it, S saves SYSBENCH.TXT to the current', 0
sb_s_end2:  db 'volume and directory (SPEC.md 19.2).', 0

sb_about:   db 'Sys Bench', 0

    OS88_MENUSET sb_menus, sb_about, sb_oncmd
        OS88_MENU sb_m_bench, sb_i_bench, 3
    OS88_MENUSET_END sb_menus

sb_m_bench: db 'Bench', 0
sb_i_bench: dw sb_it_run, sb_it_save, sb_it_top
sb_it_run:  db 'Run', 0
sb_it_save: db 'Save Report', 0
sb_it_top:  db 'Top of Report', 0

; The bss offsets past the scalars are derived, never hand-totalled: a figure
; that is too small is a package writing over benchlib's arena, which assembles
; cleanly and produces a report full of plausible nonsense.
SB_O_SYSKB equ 96
SB_O_RES   equ SB_O_SYSKB + SYSKB_SIZE
SB_O_RROW  equ SB_O_RES + SB_NCPU * 4
SB_O_RAM   equ SB_O_RROW + SB_BWROWS * 2
SB_O_RAM2  equ SB_O_RAM + SB_BWBYTES
SB_BSS_OWN equ ((SB_O_RAM2 + SB_BWBYTES + 511) / 512) * 512   ; benchlib's base must be
                                        ; 512-ALIGNED: bl_out is an int 13h target

    align 512                   ; ...and os88_image_end likewise, which this
                                ; costs up to 511 bytes of image and buys the
                                ; alignment of every bss offset below
    OS88_BSS SB_BSS_OWN + BL_BSS_SIZE
    OS88_IMAGE_END

; --- loader-zeroed bss (SPEC.md 21 step 5) -----------------------------------
sb_win      equ os88_image_end + 0     ; word
sb_vw       equ os88_image_end + 2     ; word
sb_vh       equ os88_image_end + 4     ; word
sb_kind     equ os88_image_end + 6     ; byte
sb_pad0     equ os88_image_end + 7     ; byte
sb_cputier  equ os88_image_end + 8     ; word: AL tier, AH feature bits
sb_mlarge   equ os88_image_end + 10    ; word
sb_mtotal   equ os88_image_end + 12    ; word
sb_snd      equ os88_image_end + 14    ; word
sb_xms      equ os88_image_end + 16    ; word
sb_cw       equ os88_image_end + 18    ; word
sb_ch       equ os88_image_end + 20    ; word
sb_i        equ os88_image_end + 22    ; word: the sb_ctab walk's index
sb_ent      equ os88_image_end + 24    ; word: ...and the entry it is at
sb_seg      equ os88_image_end + 26    ; word: bandwidth target segment
sb_tab      equ os88_image_end + 28    ; word: ...and its row table
sb_scr      equ os88_image_end + 30    ; word: the load/store rows' operand
sb_bseg     equ os88_image_end + 32    ; word: the file rows' heap claim
sb_rsz      equ os88_image_end + 34    ; word: bytes the big read returned
sb_rerr     equ os88_image_end + 36    ; word: ...or the FERR_* it refused with
sb_bcnt     equ os88_image_end + 38    ; dword: the baseline row's raw counts
sb_meas     equ os88_image_end + 42    ; dword: the clocks column being built
sb_wp       equ os88_image_end + 46    ; dword: the workload, interrupts off
sb_wt       equ os88_image_end + 50    ; dword: ...and on
sb_td1      equ os88_image_end + 54    ; dword: the cold read
sb_td2      equ os88_image_end + 58    ; dword: ...and the warm one (58..61)
sb_ran      equ os88_image_end + 62    ; byte: has the suite been run yet?
sb_syskb    equ os88_image_end + SB_O_SYSKB    ; SYSKB_SIZE bytes
sb_res      equ os88_image_end + SB_O_RES      ; SB_NCPU dwords
sb_rrow     equ os88_image_end + SB_O_RROW     ; SB_BWROWS words
sb_ram      equ os88_image_end + SB_O_RAM      ; the bandwidth source...
sb_ram2     equ os88_image_end + SB_O_RAM2     ; ...and destination

    BL_BSS os88_image_end + SB_BSS_OWN
