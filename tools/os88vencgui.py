#!/usr/bin/env python3
"""The video encoder with a window on it (VIDEO-PLAN 14.2, E1-E4).

    python3 tools/os88vencgui.py

Same engine, different face - `tools/os88proxygui.py`'s rule one tool along:
**it imports `os88venc` and reimplements none of it.** The window's settings
become the argv `os88venc.parser()` reads, the encode is `os88venc.encode`,
and what it prints is the log. So the form is DERIVED from that parser:
every option the encoder has is on a tab here, with its own help text as
the tooltip, and an option added to the encoder tomorrow appears here with
nothing to do - `tests/vencguitest.py` fails if one has no tooltip.

What the window adds is ASSISTANCE, in the order a person needs it:

    1. What am I making it FOR?   - a target machine, which sets the
                                     preset, the pixel format and the
                                     storage profile together
    2. What is my video?          - ffprobe's answer, and the defaults it
                                     implies (its rate, its length, whether
                                     it has sound)
    3. What will it look like?    - a scrubber over the ENCODED frames as
                                     the adapter shows them: CGA's colours,
                                     a VGA's palette, composite through the
                                     monitor model, one bit as one bit
    4. How do I get it onto the machine? - Save writes the .V88; "Make a
                                     disk" puts it and VIDEO.O88 on a
                                     floppy image of any of the four sizes

tkinter because it is in the standard library: one file, no pip. Tk is
imported SOFTLY for the proxy GUI's reason - everything above `App` loads
on a machine with no Tk, so the test can check the table, the argv and the
preview renderer without a display.
"""
import base64
import contextlib
import io
import os
import queue
import subprocess
import sys
import threading
import traceback

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except Exception:                                            # pragma: no cover
    tk = None
    filedialog = messagebox = ttk = None

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import os88venc as V                                          # noqa: E402
import os88vid as vid                                         # noqa: E402

APPNAME = "os8088 video encoder"

# WHAT IT IS FOR: a machine, which is three settings at once. The profile
# is the storage and CPU budget (os88venc's PROFILES say what each is); a
# fifth element is anything else the choice sets.
#   label                                        preset   pixfmt     profile
TARGETS = [
    ("IBM 5150/XT, CGA - black and white", "cga", "mono", "5150-st225"),
    ("IBM 5150/XT, CGA - 4 colours, full screen", "cga4", "cga4",
     "5150-st225"),
    ("IBM 5150/XT, CGA - 16 colours at 160 x 100, full screen", "c160",
     "c160", "5150-st225"),
    ("IBM 5150/XT, CGA on a composite monitor - colour", "cga", "cgacomp",
     "5150-st225"),
    ("IBM 5150/XT, Hercules - black and white", "herc", "mono",
     "5150-st225"),
    ("IBM 5150/XT, a floppy - small and slow", "cga-small", "mono",
     "floppy"),
    ("286, VGA - 16 colours in the window", "vga4", "vga4", "286-vga"),
    ("286, VGA - 256 colours, full screen", "vga8", "vga8", "286-vga"),
    ("286, VGA - Mode X, 256 colours, square pixels", "modex", None,
     "286-vga"),
    ("Live on a CGA desktop - short, black and white, read whole", None,
     None, "5150-st225", {"live": "cga"}),
    ("Live on a Hercules desktop - short, black and white", None, None,
     "5150-st225", {"live": "herc"}),
    ("Live on a VGA desktop - short, black and white", None, None,
     "286-vga", {"live": "vga"}),
]
TARGETS = [t + ({},) if len(t) == 4 else t for t in TARGETS]

# the tabs, and which options go on which - an option named nowhere here
# still appears, on Advanced
TABS = ("Basic", "Picture", "Colour", "Sound", "Budget", "Loop and keys",
        "Advanced")
TAB_OF = {
    "preset": "Basic", "pixfmt": "Basic", "profile": "Basic",
    "title": "Basic", "credits": "Basic", "start": "Basic", "end": "Basic",
    "fps": "Basic",
    "layout": "Picture", "box": "Picture", "fit": "Picture",
    "dither": "Picture", "stable": "Picture", "levels": "Picture",
    "clip": "Picture", "gamma": "Picture", "contrast": "Picture",
    "brightness": "Picture", "invert": "Picture", "detail": "Picture",
    "cga_palette": "Colour", "cga_bright": "Colour", "cga_bg": "Colour",
    "vga8_dither": "Colour", "vga8_stable": "Colour",
    "vga4_stable": "Colour", "comp_dither": "Colour",
    "comp_stable": "Colour", "comp_quick": "Colour", "mix": "Colour",
    "levels_mix": "Colour", "flip": "Colour",
    "audio": "Sound", "rate": "Sound", "adpcm": "Sound", "jobs": "Sound",
    "volume": "Sound",
    "disk": "Budget", "avg": "Budget", "peak": "Budget",
    "loop_from": "Loop and keys", "repeat": "Loop and keys",
    "keysecs": "Loop and keys", "poster": "Loop and keys",
    "poster_at": "Loop and keys", "resident": "Loop and keys",
    "live": "Loop and keys",
}
# what the window runs itself, and so does not offer
HIDDEN = {"help", "src", "out", "preview_png", "quiet", "profiles"}


def fields():
    """Every option the encoder takes, as the window shows it: a dict per
    option - dest, flag, label, kind (choice / bool / text), default,
    choices, tooltip, tab. Built from os88venc.parser() every time, so the
    window can never be missing one"""
    out = []
    for act in V.parser()._actions:
        if act.dest in HIDDEN or not act.option_strings:
            continue
        flag = act.option_strings[-1]
        kind = "bool" if act.nargs == 0 else \
            "choice" if act.choices is not None else "text"
        dflt = act.default
        out.append(dict(
            dest=act.dest, flag=flag,
            label=flag.lstrip("-").replace("-", " ").capitalize(),
            kind=kind,
            default="" if dflt is None or kind == "bool" else str(dflt),
            choices=[""] + [str(c) for c in act.choices]
            if kind == "choice" else None,
            tip=(act.help or "").strip(),
            tab=TAB_OF.get(act.dest, "Advanced")))
    return out


def argv_from(src, out, values):
    """The form's VALUES (dest -> string, "1"/"" for a switch) -> the
    encoder's command line. A value left at the parser's default is left
    off, so the encoder's own defaulting (the profile's rate, VGA8's 15
    fps) still happens"""
    argv = [src, out]
    for f in fields():
        v = str(values.get(f["dest"], "")).strip()
        if f["kind"] == "bool":
            if v in ("1", "True", "true"):
                argv.append(f["flag"])
            continue
        if v == "" or v == f["default"]:
            continue
        argv += [f["flag"], v]
    return argv


def target_values(i):
    """The values a TARGET sets - every one of them, so choosing another
    target takes back what the last one set"""
    label, preset, pixfmt, profile, extra = TARGETS[i]
    vals = {"preset": preset or "", "pixfmt": pixfmt or "",
            "profile": profile, "live": ""}
    vals.update(extra)
    return vals


def suggest(src):
    """(a line describing the source, the values its facts imply): its
    frame rate and length, and no sound when it has none"""
    sw, sh, dar, sfps, dur, has_audio = V.probe(src)
    text = ("%d x %d, %.2f fps, %.1f s, %s, %.3f:1"
            % (sw, sh, sfps, dur, "with sound" if has_audio else "SILENT",
               dar))
    vals = {"title": os.path.splitext(os.path.basename(src))[0][:47]}
    if not has_audio:
        vals["audio"] = "none"
    return text, vals


# --------------------------------------------------------------------------
# the preview: a file's frames as the adapter shows them
# --------------------------------------------------------------------------
def _rgb16():
    import numpy as np
    return np.frombuffer(vid.STD16, np.uint8).astype(np.uint16).reshape(
        16, 3) * 255 // 63


def render(r, surf):
    """Frame `surf` of Reader `r` as an RGB PIL image, at the proportions
    the screen shows it (the file's pixel aspect, 98.1.1)"""
    import numpy as np
    from PIL import Image
    g = r.g
    pf = r.pixfmt
    if pf in (vid.PF_MONO1, vid.PF_CGACOMP, vid.PF_CGA4, vid.PF_C160):
        cv = np.frombuffer(g.canvas(surf), np.uint8).reshape(g.h, g.wb)
        bits = np.unpackbits(cv, axis=1)
        if pf == vid.PF_MONO1:
            rgb = np.repeat((bits * 255).astype(np.uint8)[..., None], 3, 2)
        elif pf == vid.PF_CGACOMP:
            import os88cgacomp
            rgb = os88cgacomp.render(bits)
        else:
            n = 2 if pf == vid.PF_CGA4 else 4
            idx = bits.reshape(g.h, -1, n) @ (1 << np.arange(n - 1, -1, -1))
            if pf == vid.PF_CGA4:
                idx = np.array(vid.cga4_colours(r.cgapal))[idx]
            rgb = _rgb16()[idx].astype(np.uint8)
    else:                               # a pixel a byte: VGA8, VGA4, Mode X
        cv = np.frombuffer(g.canvas(surf), np.uint8).reshape(g.h, g.w)
        pal = _rgb16() if pf == vid.PF_VGA4 else \
            np.frombuffer(r.palette, np.uint8).astype(np.uint16).reshape(
                -1, 3) * 255 // 63
        rgb = pal[cv].astype(np.uint8)
    if r.rowscale > 1:
        rgb = np.repeat(rgb, r.rowscale, axis=0)
    img = Image.fromarray(np.ascontiguousarray(rgb))
    an, ad = r.aspect
    w, h = img.size
    return img.resize((max(1, round(w * an / ad)), h), Image.NEAREST)


def preview_frames(path, most=2000):
    """(reader, [frame canvases' images]) - every frame, or every n-th of a
    long file so the scrubber stays usable"""
    r = vid.Reader(path)
    step = max(1, -(-r.frames // most))
    out = []
    for f, surf, rec, at, i in vid.v88_frames(r):
        if f % step == 0:
            out.append((f, render(r, surf)))
    return r, out


def disk_argv(v88, size, out=None):
    """os88disk's command line for a floppy holding the video and, when it
    is built, the player"""
    img = out or os.path.splitext(v88)[0] + "-%d.img" % size
    argv = [sys.executable, os.path.join(_HERE, "os88disk.py"), "-o", img,
            "--size", str(size)]
    player = os.path.join(_ROOT, "build", "video.o88")
    if os.path.exists(player):
        argv.append(player)
    return argv + [v88], img


# --------------------------------------------------------------------------
# the window
# --------------------------------------------------------------------------
class Tip(object):
    """A tooltip: the option's help, shown while the pointer rests on it"""

    def __init__(self, widget, text):
        self.w, self.text, self.top = widget, text, None
        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)

    def show(self, _e=None):
        if not self.text or self.top:
            return
        x = self.w.winfo_rootx() + 16
        y = self.w.winfo_rooty() + self.w.winfo_height() + 4
        self.top = tk.Toplevel(self.w)
        self.top.wm_overrideredirect(True)
        self.top.wm_geometry("+%d+%d" % (x, y))
        tk.Label(self.top, text=self.text, justify="left", wraplength=420,
                 background="#ffffe0", relief="solid", borderwidth=1,
                 padx=6, pady=4).pack()

    def hide(self, _e=None):
        if self.top:
            self.top.destroy()
            self.top = None


class _Q(io.TextIOBase):
    def __init__(self, q):
        self.q = q

    def write(self, s):
        self.q.put(("log", s))
        return len(s)


class App(object):
    def __init__(self, root):
        self.root = root
        self.q = queue.Queue()
        self.vars = {}
        self.frames = []
        self.reader = None
        self.busy = False
        root.title(APPNAME)
        root.geometry("1040x720")
        self.src = tk.StringVar()
        self.out = tk.StringVar()
        self.target = tk.StringVar(value=TARGETS[0][0])
        self.info = tk.StringVar(value="Choose a video.")
        self.mkdisk = tk.BooleanVar(value=False)
        self.disksize = tk.StringVar(value="360")
        self._build()
        self.apply_target()
        root.after(100, self._pump)

    def _build(self):
        top = ttk.Frame(self.root, padding=8)
        top.pack(fill="both", expand=True)
        left = ttk.Frame(top)
        left.pack(side="left", fill="both", expand=True)
        right = ttk.Frame(top, padding=(8, 0, 0, 0))
        right.pack(side="right", fill="both")
        # --- the essentials, always on screen
        ess = ttk.Frame(left)
        ess.pack(fill="x")
        for row, (label, var, cmd) in enumerate((
                ("Video", self.src, self.browse_src),
                ("Save as", self.out, self.browse_out))):
            ttk.Label(ess, text=label).grid(row=row, column=0, sticky="w")
            ttk.Entry(ess, textvariable=var, width=60).grid(
                row=row, column=1, sticky="we", padx=4)
            ttk.Button(ess, text="Browse...", command=cmd).grid(
                row=row, column=2)
        ttk.Label(ess, text="Made for").grid(row=2, column=0, sticky="w")
        tg = ttk.Combobox(ess, textvariable=self.target, state="readonly",
                          values=[t[0] for t in TARGETS], width=58)
        tg.grid(row=2, column=1, columnspan=2, sticky="we", padx=4)
        tg.bind("<<ComboboxSelected>>", lambda e: self.apply_target())
        Tip(tg, "The machine and screen it will play on. This sets the "
                "preset, the pixel format and the storage profile below; "
                "change any of them afterwards on their tabs.")
        ttk.Label(ess, textvariable=self.info, foreground="#555").grid(
            row=3, column=1, columnspan=2, sticky="w", padx=4)
        ess.columnconfigure(1, weight=1)
        # --- every option, on tabs
        nb = ttk.Notebook(left)
        nb.pack(fill="both", expand=True, pady=6)
        pages = {}
        for t in TABS:
            pages[t] = ttk.Frame(nb, padding=6)
            nb.add(pages[t], text=t)
        rows = {t: 0 for t in TABS}
        for f in fields():
            p, r = pages[f["tab"]], rows[f["tab"]]
            rows[f["tab"]] += 1
            lab = ttk.Label(p, text=f["label"])
            lab.grid(row=r, column=0, sticky="w", pady=1)
            if f["kind"] == "bool":
                v = tk.StringVar(value="")
                w = ttk.Checkbutton(p, variable=v, onvalue="1", offvalue="")
            elif f["kind"] == "choice":
                v = tk.StringVar(value=f["default"])
                w = ttk.Combobox(p, textvariable=v, values=f["choices"],
                                 width=22)
            else:
                v = tk.StringVar(value=f["default"])
                w = ttk.Entry(p, textvariable=v, width=24)
            w.grid(row=r, column=1, sticky="w", padx=4, pady=1)
            Tip(lab, f["tip"])
            Tip(w, f["tip"])
            self.vars[f["dest"]] = v
        # --- make a disk, and go
        go = ttk.Frame(left)
        go.pack(fill="x")
        cb = ttk.Checkbutton(go, text="...and make a floppy of it",
                             variable=self.mkdisk)
        cb.pack(side="left")
        Tip(cb, "A FAT12 floppy image beside the .V88 with the video on it "
                "and VIDEO.O88 too when build/ has one: put it in B: and "
                "double-click the file.")
        ttk.Combobox(go, textvariable=self.disksize, state="readonly",
                     values=["360", "720", "1200", "1440"],
                     width=6).pack(side="left", padx=4)
        ttk.Label(go, text="KB").pack(side="left")
        self.gobtn = ttk.Button(go, text="Encode", command=self.encode)
        self.gobtn.pack(side="right")
        self.log = tk.Text(left, height=9, wrap="word")
        self.log.pack(fill="x", pady=(6, 0))
        # --- the preview
        ttk.Label(right, text="What the screen will show").pack(anchor="w")
        self.canvas = tk.Canvas(right, width=400, height=300,
                                background="black", highlightthickness=0)
        self.canvas.pack()
        self.scrub = tk.Scale(right, from_=0, to=0, orient="horizontal",
                              length=400, command=self.show_frame,
                              showvalue=False)
        self.scrub.pack(fill="x")
        self.fr = tk.StringVar(value="")
        ttk.Label(right, textvariable=self.fr).pack(anchor="w")

    # --- the essentials
    def browse_src(self):
        p = filedialog.askopenfilename(title="A video")
        if not p:
            return
        self.src.set(p)
        if not self.out.get():
            self.out.set(os.path.splitext(p)[0][:40] + ".V88")
        try:
            text, vals = suggest(p)
        except Exception as e:
            self.info.set("ffprobe could not read it: %s" % e)
            return
        self.info.set(text)
        for k, v in vals.items():
            self.vars[k].set(v)

    def browse_out(self):
        p = filedialog.asksaveasfilename(defaultextension=".V88",
                                         filetypes=[("os8088 video",
                                                     "*.V88")])
        if p:
            self.out.set(p)

    def apply_target(self):
        i = [t[0] for t in TARGETS].index(self.target.get())
        for k, v in target_values(i).items():
            self.vars[k].set(v)

    def argv(self):
        return argv_from(self.src.get(), self.out.get(),
                         {k: v.get() for k, v in self.vars.items()})

    # --- the encode, on a thread; its prints are the log
    def encode(self):
        if self.busy:
            return
        if not self.src.get() or not self.out.get():
            messagebox.showinfo(APPNAME, "Choose a video and where to save "
                                         "it first.")
            return
        argv = self.argv()
        self.log.delete("1.0", "end")
        self.write("os88venc " + " ".join(argv[2:]) + "\n")
        self.busy = True
        self.gobtn.config(state="disabled")
        # (Tk's variables are read HERE: the thread may not touch them -
        # "main thread is not in main loop", found by driving the window)
        disk = int(self.disksize.get()) if self.mkdisk.get() else 0
        threading.Thread(target=self._run, args=(argv, disk),
                         daemon=True).start()

    def _run(self, argv, disk):
        try:
            a = V.parser().parse_args(argv)
            with contextlib.redirect_stdout(_Q(self.q)):
                V.encode(a)
            if disk:
                cmd, img = disk_argv(a.out, disk)
                p = subprocess.run(cmd, capture_output=True, text=True)
                self.q.put(("log", (p.stdout + p.stderr) or
                            "the floppy: %s\n" % img))
            r, frames = preview_frames(a.out)
            self.q.put(("done", (r, frames)))
        except SystemExit as e:
            self.q.put(("fail", str(e)))
        except Exception as e:
            self.q.put(("fail", "%s\n%s" % (e, traceback.format_exc())))

    def write(self, text):
        self.log.insert("end", text)
        self.log.see("end")

    def _pump(self):
        try:
            while True:
                kind, val = self.q.get_nowait()
                if kind == "log":
                    self.write(val)
                elif kind == "fail":
                    self.write("\nFAILED: %s\n" % val)
                    self.busy = False
                    self.gobtn.config(state="normal")
                else:
                    self.reader, self.frames = val
                    self.scrub.config(to=max(0, len(self.frames) - 1))
                    self.scrub.set(0)
                    self.show_frame(0)
                    self.write("\nSaved. Drag the slider to see every "
                               "frame as the screen will.\n")
                    self.busy = False
                    self.gobtn.config(state="normal")
        except queue.Empty:
            pass
        self.root.after(100, self._pump)

    def show_frame(self, i):
        if not self.frames:
            return
        f, img = self.frames[int(i)]
        w, h = img.size
        k = min(400.0 / w, 300.0 / h)
        img = img.resize((max(1, int(w * k)), max(1, int(h * k))))
        buf = io.BytesIO()
        img.save(buf, "PNG")
        self.photo = tk.PhotoImage(data=base64.b64encode(buf.getvalue()))
        self.canvas.delete("all")
        self.canvas.create_image(200, 150, image=self.photo)
        self.fr.set("frame %d of %d (%.2f s)" % (
            f + 1, self.reader.frames, f / self.reader.fps))


def main():
    if tk is None:
        sys.exit("os88vencgui: this Python has no tkinter")
    root = tk.Tk()
    App(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
