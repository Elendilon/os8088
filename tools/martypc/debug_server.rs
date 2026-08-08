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
    BusInterface::peek_range, which costs no cycles and triggers no MMIO, so a
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
    device_traits::videocard::VideoCard,
    machine::{ExecutionControl, ExecutionOperation, ExecutionState, Machine},
};

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
            }
            else {
                // Paused: do not spin a core waiting for a command.
                std::thread::sleep(Duration::from_millis(2));
            }
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
    // peek_range: no cycle cost, no MMIO side effects (see the header).
    match machine.bus().peek_range(addr, len) {
        Ok(slice) => json!({"ok": true, "addr": addr, "len": len, "data": hex_encode(slice)}),
        Err(e) => err(&format!("read {:#07x}+{}: {:?}", addr, len, e)),
    }
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
        bps.push(match kind {
            "exec" => BreakPointType::ExecuteFlat(addr),
            "execseg" => BreakPointType::Execute(seg, off),
            "mem" => BreakPointType::MemAccessFlat(addr),
            "memseg" => BreakPointType::MemAccess(seg, off),
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
fn screen(machine: &mut Machine) -> Value {
    match machine.primary_videocard() {
        Some(mut card) => json!({"ok": true, "rows": card.get_text_mode_strings()}),
        None => err("no video card"),
    }
}
