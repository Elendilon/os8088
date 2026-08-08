/*
    MartyPC
    https://github.com/dbalsom/martypc

    Copyright 2022-2026 Daniel Balsom

    Permission is hereby granted, free of charge, to any person obtaining a
    copy of this software and associated documentation files (the “Software”),
    to deal in the Software without restriction, including without limitation
    the rights to use, copy, modify, merge, publish, distribute, sublicense,
    and/or sell copies of the Software, and to permit persons to whom the
    Software is furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in
    all copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
    FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
    DEALINGS IN THE SOFTWARE.

    ---------------------------------------------------------------------------

    debug_server.rs - A remote debug server for headless operation.

    This is the "backend to run an event loop" that run() has always wanted:
    the headless frontend builds a whole Machine - ROMs, config, floppies,
    VHDs - and then exits, because nothing drives or stops it. A socket does
    both, and gives every debugger facility marty_core already has (memory,
    registers, breakpoints, single-step, cycle counts, instruction history) to
    a process on the other end.

    WHY A SOCKET AND NOT A GDB STUB. A gdbstub would be the more standard
    answer and it is the wrong one here twice over: gdb's remote protocol has
    no notion of a segmented real-mode address, so every command would be
    translated through a flat address and the segment - which is most of what
    you are debugging on an 8088 - would be lost at the boundary; and the
    protocol has nowhere to put the things this emulator knows that gdb has
    never heard of, which are the whole reason to use MartyPC rather than
    QEMU: cycle counts, the prefetch queue, per-device state.

    THE READS DO NOT PERTURB THE MACHINE. Memory comes back through
    BusInterface::get_vec_at_ex, which costs no cycles and only ever PEEKS a
    mapped device, so a
    debugger reading a guest's memory while it runs changes neither its timing
    nor its behaviour. That matters more than usual here: MartyPC is
    cycle-accurate, and an instrument that costs cycles cannot be used to
    measure a machine whose cycles are the thing under test. I/O ports are the
    exception and say so - an `in` is a real bus read with real side effects,
    because there is no peek for a port.
*/

use std::{
    collections::VecDeque,
    io::{BufRead, BufReader, ErrorKind, Write},
    net::{TcpListener, TcpStream},
    path::Path,
    time::{Duration, Instant},
};

use marty_core::{
    breakpoints::BreakPointType,
    cpu_common::{Cpu, Register16},
    device_traits::videocard::{RenderBpp, VideoCard},
    keys::MartyKey,
    machine::{ExecutionControl, ExecutionOperation, ExecutionState, Machine},
};
use crate::KeyboardModifiers;
use std::str::FromStr;

use serde_json::{json, Value};

/// How many cycles to run between polls of the socket. At 4.77MHz this is
/// about a 60Hz frame, which is what the GUI frontend uses - so the machine
/// runs in the same shaped batches it does there, and a command waits at most
/// one batch to be seen.
const BATCH_DIVISOR: f64 = 60.0;

/// A `step` of more than this is refused rather than run, because a step loop
/// holds the socket for its whole length and a typo should not take the
/// server away for an hour.
const MAX_STEP: u64 = 1_000_000;

/// Reads are bounded so that one command cannot ask for a reply larger than
/// the far end is prepared to buffer. A caller wanting more loops; the host
/// client does it for you.
const MAX_READ: usize = 1 << 20;

/// The standard IBM 16-colour palette, RGBA, for the cards that publish none.
const IBM16: [[u8; 4]; 16] = [
    [0x00, 0x00, 0x00, 0xFF], [0x00, 0x00, 0xAA, 0xFF],
    [0x00, 0xAA, 0x00, 0xFF], [0x00, 0xAA, 0xAA, 0xFF],
    [0xAA, 0x00, 0x00, 0xFF], [0xAA, 0x00, 0xAA, 0xFF],
    [0xAA, 0x55, 0x00, 0xFF], [0xAA, 0xAA, 0xAA, 0xFF],
    [0x55, 0x55, 0x55, 0xFF], [0x55, 0x55, 0xFF, 0xFF],
    [0x55, 0xFF, 0x55, 0xFF], [0x55, 0xFF, 0xFF, 0xFF],
    [0xFF, 0x55, 0x55, 0xFF], [0xFF, 0x55, 0xFF, 0xFF],
    [0xFF, 0xFF, 0x55, 0xFF], [0xFF, 0xFF, 0xFF, 0xFF],
];

/// Put a raw sector image in a floppy drive.
///
/// The headless frontend parses `--mount fd:N:path` into
/// `config.emulator.media.floppy` and then NOBODY READS IT - mounting is done
/// by the eframe frontend's file manager, which a headless run does not have.
/// So a headless machine always booted with empty drives, which GLaBIOS
/// reports as "Disk Boot Fail. You monster." and the IBM BIOS reports by
/// dropping into cassette BASIC. Both look like the image being wrong rather
/// than absent.
pub fn mount_floppy(machine: &mut Machine, drive: usize, path: &Path) -> Result<(), String> {
    let bytes = std::fs::read(path).map_err(|e| format!("{}: {}", path.display(), e))?;
    let len = bytes.len();
    match machine.fdc() {
        Some(fdc) => {
            fdc.load_image_from(drive, bytes, Some(path), false)
                .map_err(|e| format!("{}: {}", path.display(), e))?;
            log::info!("Mounted {} ({} bytes) in floppy drive {}", path.display(), len, drive);
            Ok(())
        }
        None => Err("no floppy controller in this machine".to_string()),
    }
}

pub struct DebugServer {
    wavs:     Vec<WavSink>,
    listener: TcpListener,
    client:   Option<BufReader<TcpStream>>,
    pending:  VecDeque<String>,
    quit:     bool,
}

impl DebugServer {
    pub fn bind(addr: &str) -> std::io::Result<Self> {
        let listener = TcpListener::bind(addr)?;
        listener.set_nonblocking(true)?;
        log::info!("Debug server listening on {}", addr);
        Ok(Self {
            wavs: Vec::new(),
            listener,
            client: None,
            pending: VecDeque::new(),
            quit: false,
        })
    }

    /// The machine loop. Returns when a client asks us to quit.
    ///
    /// The machine starts PAUSED whatever the config's auto_poweron said. A
    /// debugger that attached to a machine already several million cycles
    /// into its boot cannot set a breakpoint on anything it wanted to watch,
    /// and "it had already happened" is the one failure a debugger must not
    /// have. `run` starts it.
    /// Capture every sound source to `<dir>.<source>.wav`.
    pub fn capture_audio(&mut self, machine: &Machine, dir: &str) {
        for src in machine.get_sound_sources() {
            match WavSink::open(dir, src) {
                Ok(w) => self.wavs.push(w),
                Err(e) => log::error!("Could not open capture for '{}': {}", src.name, e),
            }
        }
        if self.wavs.is_empty() {
            log::warn!("MARTYPC_WAV set but this machine has no sound sources");
        }
    }

    pub fn run_loop(&mut self, machine: &mut Machine) {
        let mut exec = ExecutionControl::new();
        exec.set_state(ExecutionState::Paused);

        let batch = ((machine.get_cpu_mhz() * 1_000_000.0) / BATCH_DIVISOR) as u32;
        log::info!("Debug server: {} cycles per batch", batch);

        while !self.quit {
            self.poll_socket();
            while let Some(line) = self.pending.pop_front() {
                let reply = self.dispatch(machine, &mut exec, &line);
                self.send(&reply);
            }

            if matches!(exec.get_state(), ExecutionState::Running) {
                machine.run(batch, &mut exec);
                // Drain after every batch, not on a timer: the channels are
                // bounded and a device that outruns the reader drops samples,
                // which would read as the guest having gone quiet.
                for w in self.wavs.iter_mut() {
                    w.drain();
                }
            }
            else {
                // Paused: do not spin a core waiting for a command.
                std::thread::sleep(Duration::from_millis(2));
            }
        }
        for w in self.wavs.iter_mut() {
            w.close();
        }
    }

    // --- socket plumbing -----------------------------------------------------

    fn poll_socket(&mut self) {
        if self.client.is_none() {
            match self.listener.accept() {
                Ok((stream, peer)) => {
                    log::info!("Debug client connected from {}", peer);
                    let _ = stream.set_nonblocking(true);
                    self.client = Some(BufReader::new(stream));
                }
                Err(ref e) if e.kind() == ErrorKind::WouldBlock => return,
                Err(e) => {
                    log::error!("Debug server accept failed: {}", e);
                    return;
                }
            }
        }

        let mut drop_client = false;
        if let Some(reader) = self.client.as_mut() {
            let mut line = String::new();
            loop {
                match reader.read_line(&mut line) {
                    Ok(0) => {
                        // EOF. A disconnect leaves the machine exactly as it
                        // is - running or paused - so a client may come and
                        // go without disturbing what it was watching.
                        log::info!("Debug client disconnected");
                        drop_client = true;
                        break;
                    }
                    Ok(_) => {
                        let trimmed = line.trim().to_string();
                        if !trimmed.is_empty() {
                            self.pending.push_back(trimmed);
                        }
                        line.clear();
                    }
                    Err(ref e) if e.kind() == ErrorKind::WouldBlock => break,
                    Err(e) => {
                        log::error!("Debug client read failed: {}", e);
                        drop_client = true;
                        break;
                    }
                }
            }
        }
        if drop_client {
            self.client = None;
        }
    }

    fn send(&mut self, value: &Value) {
        if let Some(reader) = self.client.as_mut() {
            let mut out = value.to_string();
            out.push('\n');
            if reader.get_mut().write_all(out.as_bytes()).is_err() {
                self.client = None;
            }
        }
    }

    // --- the command set -----------------------------------------------------

    fn dispatch(&mut self, machine: &mut Machine, exec: &mut ExecutionControl, line: &str) -> Value {
        let req: Value = match serde_json::from_str(line) {
            Ok(v) => v,
            Err(e) => return err(&format!("bad json: {}", e)),
        };
        let cmd = match req.get("cmd").and_then(Value::as_str) {
            Some(c) => c.to_string(),
            None => return err("no cmd"),
        };

        match cmd.as_str() {
            "ping" => json!({"ok": true, "pong": true}),
            "status" => status(machine, exec),
            "regs" => regs(machine),
            "setreg" => setreg(machine, &req),
            "read" => read_mem(machine, &req),
            "write" => write_mem(machine, &req),
            "inb" => in_port(machine, &req),
            "outb" => out_port(machine, &req),
            "run" => {
                exec.set_op(ExecutionOperation::Run);
                exec.set_state(ExecutionState::Running);
                status(machine, exec)
            }
            "pause" => {
                exec.set_op(ExecutionOperation::Pause);
                exec.set_state(ExecutionState::Paused);
                status(machine, exec)
            }
            "step" => step(machine, exec, &req),
            "reset" => {
                exec.set_op(ExecutionOperation::Reset);
                machine.run(1, exec);
                status(machine, exec)
            }
            "bp" => breakpoints(machine, &req),
            "screen" => screen(machine),
            "video" => video(machine),
            "fbuf" => fbuf(machine, &req),
            "key" => key(machine, &req),
            "mouse" => mouse(machine, &req),
            "history" => json!({"ok": true, "history": machine.cpu().dump_instruction_history_string()}),
            "callstack" => json!({"ok": true, "callstack": machine.cpu().dump_call_stack()}),
            "quit" => {
                self.quit = true;
                json!({"ok": true, "quit": true})
            }
            other => err(&format!("unknown cmd: {}", other)),
        }
    }
}

// --- helpers -----------------------------------------------------------------

fn err(msg: &str) -> Value {
    json!({"ok": false, "err": msg})
}

/// A flat 20-bit address, from either `addr` or a `seg`/`off` pair.
///
/// Both spellings exist because both questions are real: a dump wants a linear
/// address and everything in a real-mode kernel's own source is a segment and
/// an offset. Doing the shift in the client instead would put an 8086 address
/// rule in every language that ever talks to this.
fn address_of(req: &Value) -> Result<usize, String> {
    if let Some(a) = req.get("addr").and_then(Value::as_u64) {
        return Ok(a as usize);
    }
    match (
        req.get("seg").and_then(Value::as_u64),
        req.get("off").and_then(Value::as_u64),
    ) {
        (Some(s), Some(o)) => Ok((((s & 0xFFFF) << 4) + (o & 0xFFFF)) as usize),
        _ => Err("need addr, or seg and off".to_string()),
    }
}

fn hex_encode(bytes: &[u8]) -> String {
    let mut s = String::with_capacity(bytes.len() * 2);
    for b in bytes {
        s.push_str(&format!("{:02x}", b));
    }
    s
}

fn hex_decode(s: &str) -> Result<Vec<u8>, String> {
    let s = s.trim();
    if s.len() % 2 != 0 {
        return Err("hex data must have an even number of digits".to_string());
    }
    let mut out = Vec::with_capacity(s.len() / 2);
    let b = s.as_bytes();
    for i in (0..b.len()).step_by(2) {
        let pair = std::str::from_utf8(&b[i..i + 2]).map_err(|e| e.to_string())?;
        out.push(u8::from_str_radix(pair, 16).map_err(|e| e.to_string())?);
    }
    Ok(out)
}

fn state_name(s: ExecutionState) -> &'static str {
    match s {
        ExecutionState::Paused => "paused",
        ExecutionState::BreakpointHit => "breakpoint",
        ExecutionState::StepOverHit => "stepover",
        ExecutionState::Running => "running",
        ExecutionState::Halted => "halted",
    }
}

fn status(machine: &mut Machine, exec: &ExecutionControl) -> Value {
    let cs = machine.cpu().get_register16(Register16::CS);
    let ip = machine.cpu_mut().get_ip();
    json!({
        "ok": true,
        "state": state_name(exec.get_state()),
        "cycles": machine.cpu_cycles(),
        "instructions": machine.cpu_instructions(),
        "cs": cs,
        "ip": ip,
        "flat_ip": ((cs as u32) << 4).wrapping_add(ip as u32),
    })
}

fn regs(machine: &mut Machine) -> Value {
    let cpu = machine.cpu();
    let g = |r| cpu.get_register16(r);
    let mut o = json!({
        "ok": true,
        "ax": g(Register16::AX), "bx": g(Register16::BX),
        "cx": g(Register16::CX), "dx": g(Register16::DX),
        "sp": g(Register16::SP), "bp": g(Register16::BP),
        "si": g(Register16::SI), "di": g(Register16::DI),
        "cs": g(Register16::CS), "ds": g(Register16::DS),
        "es": g(Register16::ES), "ss": g(Register16::SS),
        "flags": cpu.get_flags(),
    });
    let ip = machine.cpu_mut().get_ip();
    o["ip"] = json!(ip);
    o
}

fn reg_of(name: &str) -> Option<Register16> {
    Some(match name.to_ascii_lowercase().as_str() {
        "ax" => Register16::AX,
        "bx" => Register16::BX,
        "cx" => Register16::CX,
        "dx" => Register16::DX,
        "sp" => Register16::SP,
        "bp" => Register16::BP,
        "si" => Register16::SI,
        "di" => Register16::DI,
        "cs" => Register16::CS,
        "ds" => Register16::DS,
        "es" => Register16::ES,
        "ss" => Register16::SS,
        _ => return None,
    })
}

fn setreg(machine: &mut Machine, req: &Value) -> Value {
    let name = match req.get("reg").and_then(Value::as_str) {
        Some(n) => n,
        None => return err("need reg"),
    };
    let value = match req.get("value").and_then(Value::as_u64) {
        Some(v) => v as u16,
        None => return err("need value"),
    };
    if name.eq_ignore_ascii_case("flags") {
        machine.cpu_mut().set_flags(value);
        return json!({"ok": true});
    }
    match reg_of(name) {
        Some(r) => {
            machine.cpu_mut().set_register16(r, value);
            json!({"ok": true})
        }
        None => err(&format!("unknown register: {}", name)),
    }
}

fn read_mem(machine: &mut Machine, req: &Value) -> Value {
    let addr = match address_of(req) {
        Ok(a) => a,
        Err(e) => return err(&e),
    };
    let len = req.get("len").and_then(Value::as_u64).unwrap_or(1) as usize;
    if len == 0 || len > MAX_READ {
        return err(&format!("len must be 1..{}", MAX_READ));
    }
    // get_vec_at_ex, NOT peek_range. Both are side-effect-free; only this one
    // RESOLVES MMIO. peek_range slices the flat memory vector, so a read of
    // 0xB8000 returned whatever was in RAM under the video card - a screen of
    // zeroes on any machine whose card had never written through, with no
    // error to say so. This takes the fast path (a plain slice) when the range
    // touches no mapped device and falls back to a per-byte peek when it does,
    // so ordinary reads cost what they always did and VRAM now works.
    if addr >= (1 << 20) {
        return err(&format!("read {:#07x}: past the 1MB address space", addr));
    }
    let data = machine.bus().get_vec_at_ex(addr, len);
    if data.len() != len {
        return err(&format!("read {:#07x}+{}: only {} bytes available",
                            addr, len, data.len()));
    }
    json!({"ok": true, "addr": addr, "len": len, "data": hex_encode(&data)})
}

fn write_mem(machine: &mut Machine, req: &Value) -> Value {
    let addr = match address_of(req) {
        Ok(a) => a,
        Err(e) => return err(&e),
    };
    let data = match req.get("data").and_then(Value::as_str) {
        Some(d) => match hex_decode(d) {
            Ok(v) => v,
            Err(e) => return err(&e),
        },
        None => return err("need data (hex)"),
    };
    let bus = machine.bus_mut();
    for (i, b) in data.iter().enumerate() {
        if let Err(e) = bus.write_u8(addr + i, *b, 0) {
            // Report how far it got: a partial write is a fact the caller
            // needs, and silently reporting failure loses where it stopped.
            return json!({"ok": false, "err": format!("{:?}", e), "written": i});
        }
    }
    json!({"ok": true, "written": data.len()})
}

fn in_port(machine: &mut Machine, req: &Value) -> Value {
    match req.get("port").and_then(Value::as_u64) {
        // NOT side-effect free, unlike a memory read: there is no peek for a
        // port, and reading one really does clock the device. Several of them
        // clear a status or advance a sequencer by being read at all.
        Some(p) => json!({"ok": true, "value": machine.bus_mut().io_read_u8(p as u16, 0)}),
        None => err("need port"),
    }
}

fn out_port(machine: &mut Machine, req: &Value) -> Value {
    let port = match req.get("port").and_then(Value::as_u64) {
        Some(p) => p as u16,
        None => return err("need port"),
    };
    let value = match req.get("value").and_then(Value::as_u64) {
        Some(v) => v as u8,
        None => return err("need value"),
    };
    machine.bus_mut().io_write_u8(port, value, 0, None);
    json!({"ok": true})
}

fn step(machine: &mut Machine, exec: &mut ExecutionControl, req: &Value) -> Value {
    let n = req.get("n").and_then(Value::as_u64).unwrap_or(1);
    if n == 0 || n > MAX_STEP {
        return err(&format!("n must be 1..{}", MAX_STEP));
    }
    // A step is only legal from a stopped state, and set_op enforces that -
    // so ask for the pause first rather than assuming the caller did.
    if !matches!(exec.get_state(), ExecutionState::Paused
        | ExecutionState::BreakpointHit
        | ExecutionState::StepOverHit)
    {
        exec.set_op(ExecutionOperation::Pause);
        exec.set_state(ExecutionState::Paused);
    }
    let over = req.get("over").and_then(Value::as_bool).unwrap_or(false);
    let started = Instant::now();
    for _ in 0..n {
        exec.set_op(if over {
            ExecutionOperation::StepOver
        }
        else {
            ExecutionOperation::Step
        });
        machine.run(0, exec);
        // A breakpoint reached mid-step ends the run: the caller asked for n
        // instructions and got fewer, and the state field says why.
        if matches!(exec.get_state(), ExecutionState::BreakpointHit) {
            break;
        }
        if started.elapsed() > Duration::from_secs(30) {
            break;
        }
    }
    status(machine, exec)
}

fn breakpoints(machine: &mut Machine, req: &Value) -> Value {
    let list = match req.get("list").and_then(Value::as_array) {
        Some(l) => l,
        None => return err("need list (an array; empty clears)"),
    };
    let mut bps: Vec<BreakPointType> = Vec::new();
    for item in list {
        let kind = item.get("type").and_then(Value::as_str).unwrap_or("exec");
        let addr = item.get("addr").and_then(Value::as_u64).unwrap_or(0) as u32;
        let seg = item.get("seg").and_then(Value::as_u64).unwrap_or(0) as u16;
        let off = item.get("off").and_then(Value::as_u64).unwrap_or(0) as u16;
        // The segmented forms are FOLDED TO FLAT here rather than passed
        // through, because BreakPointType::Execute(seg, off) and
        // BreakPointType::MemAccess(seg, off) are declared in
        // breakpoints.rs and matched by NEITHER CPU - grep cpu_808x and
        // cpu_vx0 for them and you get nothing, while their Flat twins are
        // handled in six places each. Passed through, they set silently and
        // never fire: measured here on 0060:37F5, os8088's timer hook, which
        // executes 18.2 times a second - `execseg` never stopped and `exec`
        // on the same address stopped immediately.
        //
        // Folding costs one property and it is worth naming: a flat
        // breakpoint aliases every seg:off pair that reaches the same linear
        // address, so 0060:37F5 and 0000:3DF5 are one breakpoint here. On a
        // real-mode 8086 that is almost always what was meant anyway - and
        // it is certainly better than a breakpoint that looks armed and is
        // not.
        bps.push(match kind {
            "exec" => BreakPointType::ExecuteFlat(addr),
            "execseg" => BreakPointType::ExecuteFlat(((seg as u32) << 4) + off as u32),
            "mem" => BreakPointType::MemAccessFlat(addr),
            "memseg" => BreakPointType::MemAccessFlat(((seg as u32) << 4) + off as u32),
            "int" => BreakPointType::Interrupt(addr as u8),
            "io" => BreakPointType::IoAccess(addr as u16),
            other => return err(&format!("unknown breakpoint type: {}", other)),
        });
    }
    // The whole set is replaced, not appended to: a debugger that can only add
    // breakpoints accumulates them across a session until something stops for
    // a reason nobody remembers asking for.
    let n = bps.len();
    machine.set_breakpoints(bps);
    json!({"ok": true, "count": n})
}

/// What the video card is actually displaying, in text modes.
///
/// This exists because `read` CANNOT answer it. Video memory is an MMIO
/// region owned by the card, and BusInterface::peek_range reads the flat
/// memory vector underneath it - so peeking 0xB8000 returns whatever is in
/// RAM at that address, which on a machine whose card has never written
/// through is a screen of zeroes. It does not error; it returns a plausible
/// blank screen, which is the worst way to be wrong. Ask the card instead.
/// Which card, and whether it is in a graphics mode.
///
/// A host that wants the framebuffer has to know the layout, and GUESSING it
/// from memory does not work: an unmapped 0xB0000 reads as zeroes rather than
/// erroring, so "is there something at the MDA aperture" answers yes on a
/// machine that has only a CGA. The card knows; ask it.
fn video(machine: &mut Machine) -> Value {
    match machine.primary_videocard() {
        Some(mut card) => {
            let ext = card.display_extents();
            let apers: Vec<Value> = card
                .display_apertures()
                .iter()
                .map(|a| json!({"w": a.w, "h": a.h, "x": a.x, "y": a.y, "debug": a.debug}))
                .collect();
            json!({
                "ok": true,
                "type": format!("{:?}", card.video_type()).to_lowercase(),
                // NOT TO BE TRUSTED ON VGA: `mode_graphics` is initialised to
                // false in the VGA card and never assigned anywhere, so this
                // answers false in mode 12h exactly as it does in mode 3. It
                // is honest on CGA and MDA. Ask `fbuf` for the geometry
                // instead - the card cannot fake having rasterised 480 rows.
                "graphics": card.is_in_graphics_mode(),
                "field_w": ext.field_w,
                "field_h": ext.field_h,
                "stride": ext.row_stride,
                "double_scan": ext.double_scan,
                "apertures": apers,
            })
        }
        None => err("no video card"),
    }
}

/// The card's RENDERED framebuffer, cropped to one of its display apertures,
/// as packed 24-bit RGB.
///
/// This is the general answer to "what is on the screen", and it is the only
/// one that works on VGA: mode 12h is four planes behind the Graphics
/// Controller, so there is no flat framebuffer in guest memory to read the way
/// `shot` reads a CGA's or a Hercules'. What comes back here is what the card
/// actually rasterised, so a mode it never really entered shows up as an image
/// that is visibly wrong rather than as a plausible dump of the wrong bytes.
///
/// THE PIXEL SIZE COMES FROM `render_depth()` AND MUST. `display_buf()` casts
/// the card's own array to `&[u8]`, and the cards disagree about what an
/// element is: CGA, MDA and EGA hold `[u8]` palette INDICES (`Four`/`Six`),
/// VGA holds `[u32]` packed RGBA already through the DAC (`ThirtyTwo`). One
/// byte per pixel and four bytes per pixel are both correct, on different
/// machines, and assuming either gives a black or a sheared picture on the
/// other WITHOUT an error - the VGA's channel bytes are full of 0x00 and 0xFF,
/// so even the histogram of a wrong read looks plausible.
///
/// DERIVING it from `buf.len() / (pitch * field_h)` is the obvious thing and
/// it is wrong twice: the buffer is allocated at the card's MAXIMUM raster
/// rather than its current one (a VGA at the 25MHz clock carries a buffer
/// sized for 28MHz), and `field_h` on a double-scanned CGA is twice the rows
/// the card actually renders. Ask the card.
///
/// `row_stride` is in PIXELS, so the byte stride is `row_stride * bpp`. The
/// answer is always rgb24, resolved here, because a caller wanting a picture
/// should not have to know which kind of buffer it came out of.
fn fbuf(machine: &mut Machine, req: &Value) -> Value {
    let sel = req.get("aperture").and_then(Value::as_u64).unwrap_or(0) as usize;
    match machine.primary_videocard() {
        Some(mut card) => {
            let apers = card.display_apertures();
            let a = match apers.get(sel) {
                Some(a) => *a,
                None => return err(&format!("aperture {} of {}", sel, apers.len())),
            };
            let bpp = match card.render_depth() {
                RenderBpp::ThirtyTwo => 4,
                _ => 1,
            };
            let pitch = card.display_extents().row_stride;
            // Only the VGA publishes a palette (its DAC is the guest's to
            // program). CGA, MDA and EGA answer None, because their colours
            // are fixed and the GUI frontend's own renderer holds the table -
            // which a headless build does not link. So the standard IBM 16
            // live here, and on the two 1bpp adapters only entries 0 and 15
            // are ever reached anyway.
            let pal = card.palette().unwrap_or_else(|| IBM16.to_vec());
            let buf = card.display_buf();
            if bpp == 1 && pal.is_empty() {
                return err("indexed framebuffer but the card published no palette");
            }
            let stride = pitch * bpp;
            let need = (a.y + a.h - 1) as usize * stride + (a.x + a.w) as usize * bpp;
            if need > buf.len() {
                return err(&format!(
                    "aperture {}x{}+{}+{} wants {} bytes of a {}-byte buffer at stride {}",
                    a.w,
                    a.h,
                    a.x,
                    a.y,
                    need,
                    buf.len(),
                    stride
                ));
            }
            let mut out = Vec::with_capacity((a.w * a.h) as usize * 3);
            for row in 0..a.h {
                let s = (a.y + row) as usize * stride + a.x as usize * bpp;
                for px in 0..a.w as usize {
                    let p = s + px * bpp;
                    if bpp == 4 {
                        out.extend_from_slice(&buf[p..p + 3]); // RGBA; drop alpha
                    }
                    else {
                        let c = pal[buf[p] as usize % pal.len()];
                        out.extend_from_slice(&c[..3]);
                    }
                }
            }
            json!({
                "ok": true,
                "w": a.w,
                "h": a.h,
                "bpp": bpp,
                "format": "rgb24",
                "data": hex_encode(&out),
            })
        }
        None => err("no video card"),
    }
}

fn screen(machine: &mut Machine) -> Value {
    match machine.primary_videocard() {
        Some(mut card) => json!({"ok": true, "rows": card.get_text_mode_strings()}),
        None => err("no video card"),
    }
}

// --- input ------------------------------------------------------------------
//
// BOTH GO THROUGH THE REAL DEVICES, and that is the whole reason they are
// here rather than in the guest. A debug module poking [mouse_x] would skip
// the UART, the packet decoder and SPEC.md 9.5's port contest - which is to
// say it would skip the code most likely to be wrong. `key` enters the
// emulator's keyboard buffer, so it reaches the guest through the 8255 and
// int 09h; `mouse` builds a real Microsoft 3-byte packet and clocks it into
// the serial controller, so the guest's own mouse ISR decodes it.
//
// It also means neither one needs anything in the guest at all: an
// unmodified shipped kernel is driven exactly as a person would drive it.

/// A keypress, a release, or both.
///
/// `key` names a MartyKey variant ("KeyA", "Enter", "Digit1", "ArrowUp") -
/// the emulator's own vocabulary rather than a second mapping table here,
/// because a table that has to agree with an enum is a table that will stop
/// agreeing with it.
fn key(machine: &mut Machine, req: &Value) -> Value {
    let name = match req.get("key").and_then(Value::as_str) {
        Some(k) => k,
        None => return err("need key (a MartyKey name, e.g. KeyA or Enter)"),
    };
    let code = match MartyKey::from_str(name) {
        Ok(k) => k,
        Err(_) => return err(&format!("unknown key: {}", name)),
    };
    // Default is press-then-release, because a debugger asking for "a
    // keystroke" wants one and a stuck modifier is a machine nobody can get
    // back. down/up are separate for the cases that genuinely need a hold.
    let down = req.get("down").and_then(Value::as_bool).unwrap_or(true);
    let up = req.get("up").and_then(Value::as_bool).unwrap_or(true);
    if down {
        machine.key_press(code, KeyboardModifiers::default());
    }
    if up {
        machine.key_release(code);
    }
    json!({"ok": true})
}

/// A mouse movement and/or button state.
///
/// dx/dy are RELATIVE and clamped to a signed byte, because that is what a
/// Microsoft packet carries - a caller wanting to cross the screen sends
/// several. The client does the chunking, exactly as tools/mouse.py does for
/// QEMU and for the same reason.
///
/// The SPEED SCALER IS FORCED TO 1.0 here, and that is the whole reason a
/// caller can count in pixels at all. MartyPC's mouse defaults to 0.25 - a
/// human's acceleration preference - so an unscaled `dx` of 60 reaches the
/// guest as 15, and a script that derives absolute position by pinning
/// against the kernel's edge clamp then lands a QUARTER of the way to
/// everything it aims at. Nothing errors: the pointer moves, menus open, and
/// every click misses by a factor that reads as a broken hit-test.
fn mouse(machine: &mut Machine, req: &Value) -> Value {
    let dx = req.get("dx").and_then(Value::as_i64).unwrap_or(0);
    let dy = req.get("dy").and_then(Value::as_i64).unwrap_or(0);
    if !(-127..=127).contains(&dx) || !(-127..=127).contains(&dy) {
        return err("dx and dy must be -127..127: a Microsoft packet carries a signed byte");
    }
    let l = req.get("l").and_then(Value::as_bool).unwrap_or(false);
    let r = req.get("r").and_then(Value::as_bool).unwrap_or(false);
    match machine.mouse_mut() {
        Some(m) => {
            m.set_speed(1.0);
            m.update(l, r, dx as f32, dy as f32);
            json!({"ok": true})
        }
        None => err("no mouse in this machine - add the microsoft_serial_mouse_com1 overlay"),
    }
}

// --- audio capture ----------------------------------------------------------
//
// Headless MartyPC had no audio path at ALL - marty_core's `sound` feature
// was not even enabled for this crate - so a card's samples went nowhere and
// there was nothing for tools/sndcheck.py to read. That is a bigger gap than
// any missing device: without it you can add a Sound Blaster and still not be
// able to say whether it made the right noise.
//
// One file per sound source, at that source's own rate, no mixing: the PC
// speaker and a card run at different sample rates and answer different
// questions, and a mixed file would make each one harder to assert about.
//
// The format is what tools/sndcheck.py already parses - 16-bit PCM - so every
// existing assertion (RMS, Goertzel dominant frequency, --expect-silence)
// works unchanged against a MartyPC capture.
pub struct WavSink {
    name:     String,
    file:     std::fs::File,
    receiver: crossbeam_channel::Receiver<marty_core::device_traits::sounddevice::AudioSample>,
    channels: u16,
    frames:   u32,
}

impl WavSink {
    fn header(rate: u32, channels: u16) -> [u8; 44] {
        let mut h = [0u8; 44];
        let byte_rate = rate * channels as u32 * 2;
        h[0..4].copy_from_slice(b"RIFF");
        h[8..12].copy_from_slice(b"WAVE");
        h[12..16].copy_from_slice(b"fmt ");
        h[16..20].copy_from_slice(&16u32.to_le_bytes());
        h[20..22].copy_from_slice(&1u16.to_le_bytes()); // PCM
        h[22..24].copy_from_slice(&channels.to_le_bytes());
        h[24..28].copy_from_slice(&rate.to_le_bytes());
        h[28..32].copy_from_slice(&byte_rate.to_le_bytes());
        h[32..34].copy_from_slice(&(channels * 2).to_le_bytes());
        h[34..36].copy_from_slice(&16u16.to_le_bytes());
        h[36..40].copy_from_slice(b"data");
        // RIFF and data sizes are patched on close; sndcheck.py reads a zero
        // data size as "to end of file" anyway, which is what makes a killed
        // emulator's capture still readable.
        h
    }

    pub fn open(dir: &str, src: &marty_core::sound::SoundSourceDescriptor) -> std::io::Result<Self> {
        let safe: String = src.name.chars()
            .map(|c| if c.is_ascii_alphanumeric() { c.to_ascii_lowercase() } else { '_' })
            .collect();
        let path = format!("{}.{}.wav", dir.trim_end_matches(".wav"), safe);
        let mut file = std::fs::File::create(&path)?;
        use std::io::Write;
        file.write_all(&Self::header(src.sample_rate, src.channels as u16))?;
        log::info!("Capturing '{}' to {} ({} Hz, {} ch)", src.name, path, src.sample_rate, src.channels);
        Ok(Self {
            name: src.name.clone(),
            file,
            receiver: src.receiver.clone(),
            channels: src.channels as u16,
            frames: 0,
        })
    }

    /// Drain whatever the device has produced since the last call.
    pub fn drain(&mut self) {
        use std::io::Write;
        let mut buf: Vec<u8> = Vec::new();
        while let Ok(s) = self.receiver.try_recv() {
            // f32 -> i16, clamped: a sample out of range is a device bug and
            // wrapping it would hide that as a click.
            let v = (s.clamp(-1.0, 1.0) * 32767.0) as i16;
            buf.extend_from_slice(&v.to_le_bytes());
        }
        if !buf.is_empty() {
            self.frames += (buf.len() / 2 / self.channels as usize) as u32;
            let _ = self.file.write_all(&buf);
        }
    }

    /// Patch the two size fields so ordinary players can read it too.
    pub fn close(&mut self) {
        use std::io::{Seek, SeekFrom, Write};
        let data = self.frames * self.channels as u32 * 2;
        let _ = self.file.seek(SeekFrom::Start(4));
        let _ = self.file.write_all(&(36 + data).to_le_bytes());
        let _ = self.file.seek(SeekFrom::Start(40));
        let _ = self.file.write_all(&data.to_le_bytes());
        let _ = self.file.flush();
        log::info!("Capture '{}': {} frames", self.name, self.frames);
    }
}
