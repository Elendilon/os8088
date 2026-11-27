; Optional international input, SPEC.md 9.16. No translator/table/state is
; resident: the core contains dispatch, activation and instance teardown.
%ifdef KERN_MEGA
%if MOD_HIOK & (1 << MOD_KEYBOARD)
  %error "keyboard IRQ/reflection entry must remain conventional"
%endif
%endif
KL_NENT equ 2
KL_SCAN equ 0
KL_CMD equ 4
KLC_SUSPEND equ 6             ; private HIBER font repair, never public SDK
KLC_REARM equ 7
KBDV_QUERY equ 0
KBDV_SET equ 1
KBDV_HOLD equ 2
KBDV_RELEASE equ 3
KBDV_CANCEL equ 4
KBDV_RAW equ 5
KBDL_BIOS equ 0
KBDL_US equ 1
KBDL_ES equ 2
KBDL_LA equ 3
KBDL_FR equ 4

section .text
; The public cell stamps its owner. Built-in glyph holds use the PRIVATE
; control entry with DH=FF; a package cannot claim that shared hold. An owner
; this refuses becomes RAW, whose own owner test answers AX = 1, CF = 1 for
; it on every task (kernel size pass 21: the refusal was a second copy here)
osapi_keyboard:
    push dx
    call inst_caller
    cmp al, KBDV_HOLD
    jb .call
    cmp al, KBDV_CANCEL
    je .call
    cmp dh, INST_MAX
    jb .call
    mov al, KBDV_RAW            ; DH >= INST_MAX: kl_control_x's .raw refuses
.call:
    call COLD_SEG:kl_control_x
    pop dx
    ret

; Instance teardown already has AL=owner; preserve it for later releases.
kl_release_inst:
    push ax
    push dx
    mov dh, al
    mov al, KBDV_RELEASE
    call COLD_SEG:kl_control_x
    pop dx
    pop ax
    ret

%ifdef KERN_MEGA
; A conventional module has both a protected selector and this real alias.
; Only mega_r15 (already in real mode) uses it; disarmed before the drop.
kl_rfp: dw 0,0
%endif

section .cold
; Same AL/AH contract as OSAPI_KEYBOARD; private HOLD/RELEASE DH=FF is
; Control Panel's own glyph client. No state is kept in the resident core.
;
; One pass of tests (kernel size pass 21): [sch_cur] is read once into CL;
; QUERY, SET 0, RELEASE and CANCEL go straight to the module-present test;
; only SET 1..4 and HOLD load, so `.call` asks SET alone; the three refusals
; share one `cbw / stc` tail. Every answer, flag and call is the one the
; two-pass form gave.
kl_control_x:
    push bx
    push cx
    push dx
    pushf
    mov cl, [sch_cur]           ; CL = the task: nothing below writes CL
    or cl, cl                   ; before its second test (.raw does, and
    jz .ui                      ; never returns there)
    cli                        ; a worker's QUERY/RAW: no drop while in the image
.ui:
    cmp al, KBDV_RAW
    je .raw
    or al, al
    jz .noload                 ; read-only QUERY is safe on every task
    or cl, cl
    jnz .context
    cmp al, KBDV_CANCEL
    ja .bad
    cmp al, KBDV_HOLD
    je .load
    cmp al, KBDV_SET
    jne .noload                ; RELEASE, CANCEL: only a present module
    or ah, ah
    jz .noload                 ; SET 0, BIOS input: the same
    cmp ah, KBDL_FR
    ja .bad
.load:
    push ax
    mov al, MOD_KEYBOARD
    call mod_need
    pop ax
    jc .resource
%ifdef KERN_MEGA
    push ax
    push dx                    ; SEG_REAL must not replace the stamped owner
    mov dx, [mod_r_keyboard]
    mov bl, SEG_REAL
    call COLD_SEG:osapi_seg
    ; SEG_REAL cannot refuse this valid conventional module claim.
    mov word [kl_rfp], klm_scan
    mov [kl_rfp+2], dx
    pop dx
    pop ax
%endif
.call:                          ; AL = SET (AH = 1..4) or HOLD here
    cmp al, KBDV_SET
    jne .invoke
    call KERNEL_SEG:rmk_8       ; existing KEY_DOWN cell arms the raw observer;
    jmp short .invoke           ; AL = 1 asks after Esc, an answer nobody reads
.resource:                      ; (HERE, in short reach of every refusal on
                                ; kern_mega too, whose SEG_REAL block above
                                ; would push them past it at the foot)
    mov al, 2
    jmp short .fail
.context:
    mov al, 3
    jmp short .fail
.bad:
    mov al, 1
.fail:
    cbw                         ; AX = 1, 2 or 3 (no `db` skip: .cold holds
    stc                         ; no data, os88ovlchk rule 1)
    jmp short .out
.raw:
    cmp dh, INST_MAX
    jae .bad
    mov cl, ah                  ; the policy, before MUL spends AH
    mov al, I_RECSZ
    mul dh                      ; AX = DH * I_RECSZ: the existing flags byte
    xchg ax, bx
    or cl, cl
    jz .native
    or byte [bx+inst_tab+I_FLAGS], IF_RAWKBD
    jmp short .query
.native:
    and byte [bx+inst_tab+I_FLAGS], ~IF_RAWKBD & 0xff
.query:
    mov al, KBDV_QUERY          ; (AH is BH's: a QUERY reads AL alone)
.noload:
    cmp word [mod_r_keyboard], 0
    je .zero
.invoke:
    call far [KLFP+KL_CMD]
    jnc .out
    or al, al                   ; CF = 0 from here on, as it always was
    jnz .out
.zero:                          ; ...QUERY before the allocated image is armed
    xor ax, ax
.out:
    sbb cx, cx                 ; carry the result's CF across the popf
    popf
    shr cx, 1
    pop dx
    pop cx
    pop bx
    retf

; Tail target after the controller has restored all module frames. The
; original FAR return belongs to kl_control_x; no module instruction remains
; reachable on the stack when mod_drop frees its image. Its slots disarm
; atomically, and a real IRQ alias is cleared before that final free.
kl_drop_x:
%ifdef KERN_MEGA
    mov word [kl_rfp+2], 0
%endif
    mov al, MOD_KEYBOARD
    call mod_drop
    xor ax, ax
    retf

%ifdef KERN_MEGA
; Boot activation is after mega's font-pointer/cache promotion.
kl_boot_x:
    mov ah, [drv_cfg+CFG_KL]
    or ah, ah
    jz .out
    mov al, KBDV_SET
    call COLD_SEG:kl_control_x
.out:
    retf
%endif

section .modq
mods_kl_header:
    dw 0x384f
    db MOD_VER, MOD_KEYBOARD
    dw BUILD_NUM, MOD_STAMP
    dw MODQ_SIZE, KL_NENT
    dw 0                       ; no kept cache: activation fills the font image
    dw klm_scan, klm_control

; ES = this image's writable alias. SMSW is only in the mega build, whose
; CPU is >=286, and distinguishes native PM from the real reflection's IRQ.
%macro KLM_DATA 0
    mov bx, cs
%ifdef KERN_MEGA
    cpu 286
    smsw ax
    cpu 8086
    test al, 1
    jz %%real
    add bx, 8
%%real:
%endif
    mov es, bx
%endmacro

%macro KLM_BDA 0
    mov bx, 0x40
%ifdef KERN_MEGA
    cpu 286
    smsw ax
    cpu 8086
    test al, 1
    jz %%real
    mov bx, MEGA_BDA
%%real:
%endif
    mov es, bx
%endmacro

%if KBDV_SET != KBDV_QUERY + 1 || KBDV_HOLD != KBDV_SET + 1 || KBDV_RELEASE != KBDV_HOLD + 1
  %error "the control ladder takes HOLD and RELEASE as the range past SET"
%endif
%if (KBDV_HOLD ^ KBDV_RELEASE) != 1
  %error "HOLD's built-in owner stores the verb XOR RELEASE"
%endif
%if I_RECSZ != 32
  %error "the focus test indexes inst_tab by owner << 5"
%endif

; (klm_control's arms that its ladder reaches backwards, in short reach)
; Wake's private commands leave layout/client holds pinned and never drop.
klm_suspend:
    call klf_suspend
    jmp klm_private
klm_rearm:
    call klf_rearm
    pushf
    cli                        ; BIOS wake state and compose cancellation agree
    call klm_seed
    mov byte [es:klm_dead], 0
    mov byte [es:klm_prefix], 0 ; discard the restored pending prefix, too
    popf
klm_private:
    xor di, di                 ; status only: the QUERY path cannot drop
    jmp klm_status

; HOLD (AL = 2) and RELEASE (AL = 3) for the stamped owner DH: FF is the
; Control Panel's built-in hold, any other a bit of klm_clients.
klm_hold:                       ; (RELEASE too, AL saying which)
    cmp dh, 0xff
    je .built
    cmp dh, INST_MAX
    jae klm_bad
    mov cl, dh
    mov bx, 1
    shl bx, cl
    cmp al, KBDV_HOLD
    jne .release
    call klf_enable
    or [es:klm_clients], bx
    jmp klm_status
.release:
    not bx
    and [es:klm_clients], bx
    jmp klm_status
.built:
    cmp al, KBDV_HOLD
    jne .bset
    call klf_enable            ; (keeps AX)
.bset:
    xor al, KBDV_RELEASE       ; HOLD -> 1, RELEASE -> 0
    mov [es:klm_builtin], al
    jmp klm_status

; Control: AX inputs, DH stamped owner. Every other register preserved.
; Nothing on this entry's paths writes SI or BP (klf_enable banks its own SI,
; and cw_gfx_lock/unlock keep every register), so only what is spent is
; banked (driver size pass 2).
klm_control:
    push bx
    push cx
    push dx
    push di
    push es
    mov di, ax                 ; the verb, which klm_status reads again
    KLM_DATA
%ifdef KERN_MEGA
    mov ax, di                 ; (SMSW took AX)
%endif
    cmp al, KBDV_QUERY
    je klm_status
    cmp al, KBDV_SET
    je klm_set
    cmp al, KBDV_RELEASE
    jbe klm_hold               ; HOLD or RELEASE: one owner test for both
    cmp al, KLC_SUSPEND
    je klm_suspend
    cmp al, KLC_REARM
    je klm_rearm
    cmp al, KBDV_CANCEL
    jne klm_bad
    mov byte [es:klm_dead], 0
klm_status:
    mov al, [es:klm_layout]
    cbw                        ; (a layout is 0..KBDL_FR)
    or al, al
    jnz .held
    cmp word [es:klm_clients], 0
    jne .held
    cmp byte [es:klm_builtin], 0
    jne .held
    mov bx, di
    or bl, bl                  ; KBDV_QUERY
    jz .done
    cmp bl, KBDV_CANCEL
    je .done
    call klf_disable
    jmp klm_return.drop
.held:
    inc ah
.done:
    clc
    jmp klm_return
klm_bad:
    mov ax, 1
    stc
klm_return:
    pop es
    pop di
    pop dx
    pop cx
    pop bx
    retf
.drop:                          ; second FAR epilogue, same original frame
    pop es
    pop di
    pop dx
    pop cx
    pop bx
    jmp COLD_SEG:kl_drop_x      ; leave the image before freeing its claim
; klf_enable cannot fail (it returns CF = 0 always; kbdlayoutfont pins it),
; so SET and HOLD have no refusal of their own past the argument tests.
klm_set:
    cmp ah, KBDL_FR
    ja klm_bad
    or ah, ah
    jz .publish
    call klf_enable
.publish:
    pushf
    cli                        ; seed and selection publish see the same scan
    or ah, ah
    jz .store
    cmp byte [es:klm_layout], 0
    jne .store
    push ax
    call klm_seed
    pop ax
.store:
    mov [es:klm_layout], ah
    mov byte [es:klm_dead], 0
    popf
    jmp klm_status
; Seed a newly selected layout from the BIOS's lock/modifier snapshot.
; Out: AX, DX spent.
klm_seed:
    push es
    KLM_BDA
    mov al, [es:0x17]
    and al, 0x4f               ; BDA left/right Shift, Ctrl/Alt/Caps
    mov ah, [es:0x96]
    mov dh, [es:0x18]
    test ah, 0x10              ; enhanced keyboard: right Ctrl/Alt snapshot
    jz .mods
    test al, 4
    jz .alt
    test ah, 4
    jz .alt
    or al, 32
    test dh, 1
    jnz .alt
    and al, 0xfb
.alt:
    test al, 8
    jz .mods
    test ah, 8
    jz .mods
    or al, 16
    test dh, 2
    jnz .mods
    and al, 0xf7
.mods:
    and dh, 0x40               ; Caps held already: typematic is not an edge
    mov dl, 0                  ; ...and no Pause pending
    and ah, 2
    shr ah, 1
    pop es
    mov [es:klm_mods], ax      ; modifiers, then the pending E0 prefix
    mov [es:klm_pause], dx     ; Pause, then Caps held
    mov byte [es:klm_focus], 0xff
    ret

; A layout-0 scan (BIOS input with only a glyph hold loaded): CF = 1 from
; the compare that came here, and nothing else touched.
klm_off:
    pop es
    pop bp
    pop bx
    pop ax
    retf

; Raw set-1 scan, after kbd_track. CF=1 pass, CF=0 consumed; every
; register preserved. No kernel calls, I/O, allocation or unbounded work.
klm_scan:
    push ax
    push bx
    push bp
    push es
    mov bp, ax                 ; BP = the scan as it arrived (SMSW takes AX)
    KLM_DATA
    cmp byte [es:klm_layout], 1
    jb klm_off                 ; CF = 1: BIOS input
    push cx
    push dx
    push si
    ; The focus owner: bounded existing UI/instance tables, read only; no WM
    ; call from IRQ. Modifier state keeps tracking while a foreign owner
    ; receives BIOS input.
    mov al, [wm_zn]
    cmp al, MAX_WIN
    jbe .bounded
    mov al, MAX_WIN
.bounded:
    cbw
    xchg ax, si
.next:
    dec si
    js .none
    mov al, [wm_zord+si]
    cmp al, MAX_WIN
    jae .next
    mov dl, al
    mov bl, WIN_SIZE
    mul bl
    xchg ax, bx
    mov ax, [wm_wins+bx+W_FLAGS]
    and ax, WF_DESK | 2
    cmp ax, 2
    jne .next
    mov bx, wm_owner
    mov al, dl
    xlat
    jmp .owner
.paused:                        ; (the rare arms, here in reach of their tests)
    dec byte [es:klm_pause]
    jmp klm_pass
.pause5:
    mov byte [es:klm_pause], 5
    jmp klm_pass
.prefixed:
    mov byte [es:klm_prefix], 1
    jmp klm_pass
.none:
    mov al, 0xff
.owner:
    cmp al, [es:klm_focus]
    je .same
    mov [es:klm_focus], al
    mov byte [es:klm_dead], 0
.same:
    xor dx, dx
    cmp al, INST_MAX
    jae .out
    cbw
    mov bx, ax
    mov cl, 5
    shl bx, cl
    test byte [inst_tab+bx+I_FLAGS], IF_RAWKBD
    jz .out
    inc dx
.out:
    cmp dl, [es:klm_foreign]
    je .done
    mov [es:klm_foreign], dl
    mov byte [es:klm_dead], 0
    or dl, dl
    jnz .done
    push ax                    ; the owner across the seed
    call klm_seed              ; BIOS may have owned IRQs in a foreign session
    pop ax
    mov [es:klm_focus], al      ; retain focus for the first native dead key
.done:
    mov ax, bp                 ; the scan
    cmp byte [es:klm_pause], 0
    jne .paused
    cmp al, 0xe1
    je .pause5
    cmp al, 0xe0
    je .prefixed
    and bp, 0x7f
    xor cx, cx
    xchg cl, [es:klm_prefix]
    mov bx, bp
    cmp bl, 0x38
    je klm_alt
    cmp bl, 0x1d
    je klm_ctrl
    or cl, cl
    jnz klm_pass              ; grey navigation, fake shifts, keypad / and Enter
    mov cl, 2                 ; match BDA: left Shift bit1, right bit0
    cmp bl, 0x2a
    je klm_modifier
    mov cl, 1
    cmp bl, 0x36
    je klm_modifier
    cmp bl, 0x3a
    je klm_caps
    test al, 0x80
    jnz klm_pass
    cmp byte [es:klm_foreign], 0
    jne klm_pass
    push es
    KLM_BDA
    test byte [es:0x18], 8     ; BIOS Pause: its resume key goes to the ROM
    pop es
    jnz klm_special
    mov bx, bp                 ; KLM_BDA took BX (and AX on mega)
    cmp bl, KLM_IDX_N
    jae klm_special
    mov bl, [cs:klm_idx+bx]    ; the key's index + 1, KLM_BS, or 0
    dec bx
    cmp bl, KLM_KEYS
    jb klm_translate           ; BX = the key's index in every plane
    jne klm_special
    cmp byte [es:klm_dead], 0  ; Backspace cancels the dead accent alone
    je klm_pass
    mov byte [es:klm_dead], 0
klm_eaten:
    db 0xa8                    ; test al, 0F9h: CF = 0, over klm_pass's stc
klm_pass:
    stc
    pop si
    pop dx
    pop cx
    pop es
    pop bp
    pop bx
    pop ax
    retf
klm_special:
    mov byte [es:klm_dead], 0
    jmp klm_pass
klm_alt:
    mov ch, 8
    or cl, cl
    jz klm_modch                  ; CL=0 plain left Alt
    mov ch, 16
    jmp klm_modch
klm_ctrl:
    mov ch, 4
    or cl, cl
    jz klm_modch
    mov ch, 32
klm_modch:
    mov cl, ch
klm_modifier:
    test al, 0x80
    jz klm_down
    not cl
    and [es:klm_mods], cl
    jmp klm_pass
klm_down:
    or [es:klm_mods], cl
    jmp klm_pass
klm_caps:
    test al, 0x80
    jz klm_capdown
    mov byte [es:klm_capsdown], 0
    jmp klm_pass
klm_capdown:
    cmp byte [es:klm_capsdown], 0
    jne klm_pass
    mov byte [es:klm_capsdown], 1
    xor byte [es:klm_mods], 0x40
    jmp klm_pass

; The arms of klm_translate and klm_character that a plain key does not take,
; here so that the plain key's tests fall through (their targets in reach).
klm_chord:                      ; DL = the modifiers: an Alt and/or a Ctrl
    test dl, 16
    jnz .altgr                  ; right Alt
    test dl, 8
    jz klm_control_key          ; no Alt: a Ctrl alone
    test dl, 0x24
    jz klm_pass                 ; ordinary left-Alt BIOS shortcuts
.altgr:                         ; right Alt, or left Alt with either Ctrl
    cmp si, klm_map_us         ; US: AltGr stays the BIOS's (it has no
    je klm_pass                ; AltGr plane - keymaps.inc)
    test dl, 3                 ; no Shift+AltGr column in these legacy layouts
    jnz klm_eaten
    add si, KLM_KEYS*2
    jmp klm_translate.lookup
klm_control_key:
    mov al, [cs:si+bx]
    cmp al, 'a'
    jb .punct
    cmp al, 'z'
    ja .punct
    sub al, 0x60
    jmp klm_single
.punct:
    cmp al, '['
    jb .other
    cmp al, ']'
    ja .other
    sub al, 0x40
    jmp klm_single
.other:
    cmp al, '6'
    jne .minus
    mov al, 0x1e
    jmp klm_single
.minus:
    cmp al, '-'
    jne klm_pass
    mov al, 0x1f
    jmp klm_single

klm_shcaps:                     ; DL = the modifiers: a Shift and/or Caps Lock
    test dl, 0x40
    jz .shift                   ; Shift alone: the shift plane
    cmp bl, [cs:si-1]           ; Caps Lock: the layout's first [si-1] keys
    jae .bycaps                 ; follow it; the rest do not
    test dl, 3
    jnz klm_translate.lookup    ; Caps Lock undoes Shift: the base plane
.shift:
    add si, KLM_KEYS
    jmp klm_translate.lookup
.bycaps:
    test dl, 3
    jnz .shift
    jmp klm_translate.lookup
; BX = the key's index in every plane (BH = 0), BP = its scan.
klm_translate:
    mov al, [es:klm_layout]    ; KBDL_US..KBDL_FR
    cbw
    add ax, ax
    xchg ax, si
    mov si, [cs:klm_maps-2+si] ; the base plane; shift and AltGr follow it
    mov dl, [es:klm_mods]
    test dl, 0x3c              ; either Alt or Ctrl
    jnz klm_chord
    test dl, 0x43              ; either Shift or Caps Lock
    jnz klm_shcaps
.lookup:
    mov dl, [cs:si+bx]
klm_character:                  ; DL: 0 unmappable, 1..KLM_DEAD_N a dead accent
    mov al, [es:klm_dead]       ; AL = the pending accent, 0 = none
    cmp dl, KLM_DEAD_N + 1
    jb klm_deadkey
    or al, al
    jnz klm_compose_key
    mov al, dl                 ; the plain character
klm_single:
    xor cx, cx
    mov dx, bp
    mov ah, dl
klm_store:
%ifdef KERN_MEGA
    push ax                    ; first word while BDA alias macro uses AX
%endif
    KLM_BDA
%ifdef KERN_MEGA
    pop ax
%endif
    mov bx, [es:0x1c]
    lea si, [bx-KBD_BUFB]
    cmp si, KBD_BUFE-KBD_BUFB
    jae klm_eaten2             ; a tail outside the ring
    test bl, 1
    jnz klm_eaten2
    mov si, bx
    call klm_next
    cmp si, [es:0x1a]
    je klm_eaten2
    mov dx, si
    jcxz .publish
    call klm_next
    cmp si, [es:0x1a]
    je klm_lost                ; reserve both before writing either
.publish:
    mov [es:bx], ax
    jcxz .tail
    mov bx, dx
    mov [es:bx], cx
.tail:
    mov [es:0x1c], si          ; publish completed word(s) last
klm_eaten2:                     ; klm_eaten's exit, in the store's reach
    db 0xa8                    ; test al, 0F9h: CF = 0, over the stc
    stc
    pop si
    pop dx
    pop cx
    pop es
    pop bp
    pop bx
    pop ax
    retf
; A dead accent's code, or 0: unmappable (for example Euro).
klm_deadkey:
    or dl, dl
    jz klm_eaten2
    mov bl, dl
    mov dl, [cs:klm_deadch-1+bx] ; DL = the accent's CP850 byte
    or al, al
    jz .wait
    cmp al, dl
    je .literal
    mov [es:klm_dead], dl     ; old literal emitted, new accent stays pending
    jmp klm_single
.wait:
    mov [es:klm_dead], dl
    jmp klm_eaten2
.literal:
    mov byte [es:klm_dead], 0
    jmp klm_single
; AL = the pending accent, DL = an ordinary character.
klm_compose_key:
    mov byte [es:klm_dead], 0
    cmp dl, ' '
    je .single                 ; accent then Space: the accent (AL)
    mov si, klm_compose
.accent:
    mov cx, [cs:si]            ; CL = accent, CH = its run's pair count
    inc si
    inc si
    jcxz .miss                 ; dw 0 ends the table
    cmp al, cl
    mov cl, ch
    mov ch, 0
    je .find                   ; scan only this accent's run
    add si, cx
    add si, cx
    jmp .accent
.find:
    cmp dl, [cs:si]
    jne .next
    mov al, [cs:si+1]
.single:
    jmp klm_single
.next:
    inc si
    inc si
    loop .find
.miss:
    mov cx, bp
    mov ch, cl                 ; CX = second word, physical scan and character
    mov cl, dl
    mov dx, bp
    mov ah, dl
    jmp klm_store

; Neither half of a pair fits: drop both and say so, SPEC.md 9.8's way.
klm_lost:
    cmp byte [kbd_ovn], KBD_OVBEEPS
    jae klm_eaten2
    inc byte [kbd_ovn]
    mov byte [kbd_ovb], 1      ; the UI task beeps (kbd_ovspend)
    inc byte [ui_post]
    jmp klm_eaten2
klm_next:
    inc si
    inc si
    cmp si, KBD_BUFE
    jb .out
    mov si, KBD_BUFB
.out:
    ret

%include "keymaps.inc"
%include "keyfont.inc"
section .modq
MODQ_IMG equ $ - $$

section .modqb
klm_layout:   resb 1
klm_mods:     resb 1
klm_prefix:   resb 1
klm_pause:    resb 1
klm_capsdown: resb 1
klm_dead:     resb 1
klm_focus:    resb 1
klm_foreign:  resb 1
klm_clients:  resw 1
klm_builtin:  resb 1
%if klm_prefix != klm_mods + 1 || klm_capsdown != klm_pause + 1
  %error "the seed stores the modifier/prefix and pause/Caps pairs as words"
%endif
section .text
