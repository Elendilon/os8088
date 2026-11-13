; WireArena's FRAME BLOCK and the renderer part's ABI (docs/plans/
; WIREARENA-PARTS-PLAN.md section 7). Included by BOTH halves, which is what
; makes the block one layout: the primary (wirearena.asm) expands WA_FBLOCK
; in its BSS, the renderer part (wrpart.asm) at WR_FB in its image, each
; through its own WA_FBV, so the variables come in this order in both. A
; variable's address in the part is therefore its primary address
; - wa_fb_cfg + WR_FB (WA_RAT below).
;
; Who writes what, and when the primary copies it across:
;   config   G writes (wa_setmode, wa_setfov); G -> R by wa_rsync
;   frame    G writes (the sim, the keys); G -> R every frame by wa_render
;   figs     G writes F_X..F_Z (bytes 0..19: G -> R every frame and
;            before TRACE) and F_HEAD/F_PATH; R writes the projection,
;            F_PZ..F_PWH, and keeps it. G's own F_PZ means only "drawn since
;            it spawned" (1 after each frame, 0 from wa_spawn); before TRACE
;            a 0 there zeroes the part's, so a figure respawned since the
;            frame is not hit where its body lay
;   arena    R writes (ARENA); R -> G by wa_loadarena
; A variable the RENDERER reads that the primary writes belongs in config
; or frame, and nowhere else: R reads only its own copy.

; --- the renderer part's header ---------------------------------------------
WR_MAGIC0   equ 'WR'                ; +0: 'WRPART', then the ABI byte and the
WR_MAGIC1   equ 'PA'                ;     verb count - checked by the primary
WR_MAGIC2   equ 'RT'                ;     at launch, refused on a mismatch
WR_ABI      equ 3                   ; (2: the camera's sin/cos in FRAME;
                                    ; 3: F_Z, the treads, ARENA's heights)
WR_H_ABI    equ 6
WR_H_NV     equ 7
WR_H_VERB   equ 8                   ; +8: a word per verb, its offset
WR_FB       equ 32                  ; the frame block's offset in the part

; the verbs: index x 2. In: DS = the part's data (the primary's glue sets
; it), SS the caller's, ES anything. Out: retf; every register but DS, SS
; and SP may be clobbered, ES included.
WRV_INIT    equ 0                   ; after a mode set: row tables, stamps
WRV_GEOM    equ 2                   ; after ARENA: wa_geominit
WRV_ARENA   equ 4                   ; AL = an arena: its working tables
WRV_RENDER  equ 6                   ; out AL = the frame number (wa_frame)
WRV_PRESENT equ 8                   ; out AX = text cells written (wa_nwr)
WRV_TRACE   equ 10                  ; out AX = the hit figure's offset in
                                    ; wa_figs, or -1 (the pistol's ray)
WR_NVERB    equ 6

WA_FIGHEAD  equ 20                  ; figs: the bytes G -> R every frame
                                    ; (F_X..F_Z)

%define WA_RAT(x) ((x) - wa_fb_cfg + WR_FB)

; --- the block: WA_FBLOCK, expanded where the includer keeps it -------------
%macro WA_FBLOCK 0
WA_FBV wa_fb_cfg, 0                 ; CONFIG
WA_FBV wa_vseg, 2
WA_FBV wa_w, 2
WA_FBV wa_w2, 2
WA_FBV wa_k16, 2
WA_FBV wa_c16, 2
WA_FBV wa_kyq, 2
WA_FBV wa_kyh, 2
WA_FBV wa_wf, 2
WA_FBV wa_mono, 1
WA_FBV wa_fbpad0, 1
WA_FBV wa_fb_frm, 0                 ; FRAME
WA_FBV wa_px, 2
WA_FBV wa_py, 2
WA_FBV wa_ang, 2
WA_FBV wa_pitch, 2
WA_FBV wa_eye, 2
WA_FBV wa_fsn, 2                    ; the camera's sin and cos, Q14, at wa_ang
WA_FBV wa_fcs, 2                    ; >> 6 (G: wa_rframe, from its wa_sincos)
WA_FBV wa_fov, 1
WA_FBV wa_hyst, 1
WA_FBV wa_grid, 1
WA_FBV wa_sparse, 1
WA_FBV wa_mflash, 1
WA_FBV wa_treads, 1                 ; a ramp drawn as stepped treads (T: the
                                    ; graphics option, HEIGHTS-PLAN 7.4.2)
WA_FBV wa_figs, F_SIZE*WA_NFIG      ; FIGS (follows FRAME: one copy)
WA_FBV wa_fb_arn, 0                 ; ARENA
WA_FBV wa_sx, 2
WA_FBV wa_sy, 2
WA_FBV wa_sa, 2
WA_FBV wa_nbox, 2
WA_FBV wa_boxes, WA_MBOX*8
WA_FBV wa_aflat, 1                  ; 1: no box below the tallest, no lift
WA_FBV wa_fbpad2, 1                 ; (HEIGHTS-PLAN 7.4: the sim's heights)
WA_FBV wa_ahmax, 2                  ; the tallest height (wa_hmax's copy)
WA_FBV wa_bxh, WA_MBOX*4            ; per box: height, kind, faces - a
                                    ; lift's height the sim's to move (G
                                    ; writes it into R's every frame)
WA_FBV wa_lift, 2                   ; the lift: its record's offset in
WA_FBV wa_lrest, 2                  ; wa_bxh (-1: none), its rest and raised
WA_FBV wa_ltop, 2                   ; heights (HEIGHTS-PLAN 3.2)
WA_FBV wa_apn, 2                    ; the arena's own patrols: bytes (0: the
WA_FBV wa_apath, WA_APATHSZ         ; primary's), and their block
WA_FBV wa_fb_end, 0
%endmacro
