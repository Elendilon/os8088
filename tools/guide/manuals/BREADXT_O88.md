# Breadboard XT

Breadboard XT is an electronics workbench. A breadboard fills the middle of
the window: you plug resistors, LEDs, switches, capacitors, logic chips and
a 555 timer into its holes, join them with wires, and run the circuit. A
probe reads the voltage at any hole, the current through a part, and the
logic level on a chip's pin, and a two-channel oscilloscope draws how
voltages change over time.

It is a teaching tool. It works out DC circuits, digital logic with HIGH,
LOW, unknown (X) and floating (Z) levels, and capacitors charging and
discharging over time, using idealised parts. It does not model heat,
damage or the inside of a transistor, and on a 4.77 MHz XT it calculates
much slower than real time. Eight example circuits come with it, ready to
open, change and run.

## Starting Breadboard XT

Breadboard XT has a disk of its own. Double-click **BREADXT.O88** to start
with an empty board, or double-click one of the example `.BBX` files beside
it, such as [[FLASHER.BBX]], to open that circuit. A `.BBX` file opens in
Breadboard XT from any folder.

It runs on VGA, EGA, CGA and Hercules screens, and lays itself out for the
screen it has:

- **VGA** shows everything at once: a tool bar, the parts palette and the
  examples on the left, the board in the middle, the inspector on the
  right, the oscilloscope docked under the board, and a status bar.
- **EGA and Hercules** show the same without the docked oscilloscope. Tabs
  over the middle switch between **Breadboard**, **Net list** and
  **Scope**.
- **CGA**, or any small window, shows one view at a time across the whole
  width, chosen with the tabs **Board**, **Parts**, **Inspect**, **Scope**
  and **Nets**.

A 256KB machine can run Breadboard XT on its own; close other programs
first. When memory is short it draws a plainer face with text in place of
pictures, and the status bar says **Plain face: low memory**. Everything
else works the same, and Help then points you to the `HELP.TXT` file on the
disk.

## The tool bar

The picture buttons along the top are **Select**, **Wire** and **Probe**
(the three tools, also `V`, `W` and `P`; the current one looks pressed),
**Rotate** and **Undo**, and **Run**, **Pause**, **Step** and **Reset**. A
button that cannot act at the moment is grey. Beside them the run-state
field shows a lamp and **Running**, **Paused**, **Stale** or what is wrong
with the circuit.

## The board

The board has 30 columns, numbered 1 to 30, and rows **a** to **j**. In
each column, holes a to e are joined in one strip and f to j in another,
with a trench between them. Neighbouring columns are not joined. Along the
top and bottom run the power rails, red for positive and blue for negative.
Every rail is split in the middle, between columns 15 and 16, and the two
halves are separate until a wire bridges them.

Each hole takes one lead, including a wire's end. To join a wire to a part,
put the wire in another hole of the same strip. Wires connect only at their
ends: two wires that cross on the screen are not joined.

When you select a hole, solid marks show its strip and dotted marks show
the other strips joined to it by wires. The `Hole:` line under the board
names the hole under the pointer.

## Building a circuit

1. Choose a part: click it in the parts palette, use the **Parts** menu, or
   press `F2`. The palette has three groups, **Basics**, **Logic** and
   **More**; click the group's name, or press `Tab` while the palette has
   the focus, to change group.
2. Click the holes for the part's leads. A preview shows where it will go.
3. Press `Enter` to place it, or `Esc` to cancel.

Chips sit across the trench, pin 1 on row f at the left, with a notch and a
pin-1 mark to show which way round they are. `R` rotates the selected part.

The parts are a resistor, an LED, a switch, a capacitor, a potentiometer, a
DC supply, ground, a logic input, a logic lamp, a clock, the logic chips
74HC00 (NAND), 74HC04 (NOT), 74HC08 (AND), 74HC32 (OR) and 74HC86 (XOR),
and an NE555 timer. A circuit needs one supply and a ground.

To add a wire, press `W` or pick **Wire** in the palette, click the hole for
one end and then the other, and press `Enter`. Before `Enter`, `B` adds a
bend at the second hole you clicked; a wire can have two bends. Bends change
only the picture.

## Changing a circuit

Press `V` for the select tool and click a part, a pin or a wire. The
inspector on the right shows what you selected.

- `E`, or a click on the inspector's value box, edits the part's value. Type
  it and press `Enter`. The small arrows beside the box step the value up
  and down through the usual sizes.
- `T` edits a part's setting: a potentiometer's wiper, a capacitor's
  starting voltage, a logic input's level, a clock's duty.
- `Space` opens or closes a selected switch, and switches a selected logic
  input between 0 and 1.
- `M` moves the selected part: click where pin 1 should go.
- `Del` removes the selection. Removing a part leaves its wires in place.
- The inspector's **Rotate** and **Toggle** buttons rotate the part and
  flip a switch or logic input.
- `[` and `]` select the previous or next pin of a part.
- `Ctrl-Z` undoes and `Ctrl-Y` redoes, up to 16 changes.

Values are typed as you would write them: `330`, `10k` or `68k` for
resistors, `10nF`, `0.1uF` or `10uF` for capacitors, `5V` or `5000` for the
supply. A value out of range, or between the steps the part allows, is
refused rather than rounded.

## Running it

Click **Run**, pick **Simulate > Run**, or press `Space` (when a switch or
logic input is selected, `Space` flips it instead). `Space` also pauses a
running circuit. The lamp in the run-state field turns green and the
clock counts simulated time, which runs in steps of one millisecond. `.`
(full stop) advances one step, **Pause** stops and keeps everything as it
is, and **Reset** puts capacitors, clocks and the timer back to where they
start and clears the oscilloscope.

Any change to the circuit pauses it and marks the readings stale; **Run**
or **Step** works the changed circuit out again.

When something is wrong, such as a missing ground, an LED with no resistor
across the supply, or two outputs fighting, the status bar says so and the
lamp turns red. Click the message to show where the problem is.

## Measuring

Press `P` for the probe and click a hole or a pin. The probe box shows the
voltage there and its logic level (0, 1, X or Z). Click the body of a
two-lead part to read the current through it, from pin 1 to pin 2, in
microamps. A supply delivering power reads negative. A reading that is
floating, unknown or out of date says so; it never shows a made-up 0 V.

There are two probe channels, A and B. `Tab`, or a click on the probe box,
switches between them. Each channel feeds one trace on the oscilloscope.

## The oscilloscope

The oscilloscope draws channel A in green and channel B in yellow; on a
black-and-white screen channel B is dashed. It keeps the last 256 samples
of each. `+` and `-` change the time per division, and `G` sets the
trigger: free running, rising edge or falling edge on channel A. Below the
traces it shows the frequency and duty of a repeating signal, once enough
cycles have been seen.

`F4`, or the button in the scope's header, hides and shows the docked
oscilloscope on VGA. On other screens `F4` switches between the board and
the Scope view.

## The net list

The **Net list** tab lists every joined group of holes, its voltage and
what is connected to it. The selected hole's group is highlighted. `PgUp`
and `PgDn` page through it.

## Examples

The **Examples** list on the left, **File > Examples...** and **View >
Examples** open the eight example circuits. Click one, or press its number
`1` to `8` on the Examples page. An example opens as an untitled copy, so
your changes never overwrite it.

| Example | What it shows |
|---|---|
| [[LEDTEST.BBX]] | An LED lit from 5 V through 330 ohms |
| [[DIVIDER.BBX]] | Two 10k resistors halving the supply |
| [[POT.BBX]] | A potentiometer as an adjustable divider |
| [[SWITCH.BBX]] | A switch lighting an LED |
| [[LOGIC.BBX]] | A 74HC00 NAND gate and its inputs |
| [[BROKEN.BBX]] | A mistake to find and fix |
| [[RC.BBX]] | A capacitor charging through a resistor |
| [[FLASHER.BBX]] | A 555 timer flashing an LED |

## The File menu

| Item | Key | What it does |
|---|---|---|
| New | `Ctrl-N` | Start an empty board |
| Open... | `Ctrl-O` | Open a `.BBX` project |
| Save | `Ctrl-S` | Save the project |
| Save As... | | Save it under a new name |
| Examples... | | Show the example circuits |
| Close | | Close the window |

New, Open, an example and Close ask whether to save unsaved changes first.

## The Edit menu

| Item | What it does |
|---|---|
| Undo, Redo | Undo or redo the last change (`Ctrl-Z`, `Ctrl-Y`) |
| Delete | Remove the selection (`Del`) |
| Rotate | Turn the selected part round (`R`) |
| Move part | Move the selected part; click where pin 1 goes (`M`) |
| Reroute wire | Move one end of the selected wire: click the new hole, then `Enter` |
| Wire color | Give the selected wire the next colour |
| Value / parameter | Edit the selected part's value (`E`) |

## The Parts menu

Resistor, LED, Capacitor, Switch, Power, Ground and Potentiometer choose
that part. **All parts...** shows the next group of the palette, or the
Parts view on a small screen.

## The Simulate menu

| Item | What it does |
|---|---|
| Run | Run the circuit |
| Pause | Stop, keeping its state |
| Step | Advance one step (`.`) |
| Reset | Return to the starting state and clear the scope |
| Smaller timestep | Halve the step: slower, more exact timing |
| Larger timestep | Double the step: quicker, rougher timing |

## The View menu

| Item | What it does |
|---|---|
| Breadboard | Show the board |
| Parts palette | Show the palette, or its next group (`F2`) |
| Inspector | Show the inspector (`F3`) |
| Oscilloscope | Show or hide the oscilloscope (`F4`) |
| Zoom | Draw the board larger, or back to normal |
| Net highlight | Turn the dotted marks for joined strips off and on |
| Help | Five pages of help (`F1`); `Enter` turns the page, `Esc` returns |
| Examples | Show the example circuits |
| Net list | Show the net list |

## Other keys

| Key | What it does |
|---|---|
| Arrow keys | Move the board in the window |
| `PgUp`, `PgDn` | Move the board four rows |
| `Esc` | Cancel, and go back to the select tool |

The status bar's **F1 Help** box opens Help too.

## Files

Projects are `.BBX` files. Breadboard XT saves them through the system's
file dialog, and a failed save leaves your work open and unsaved. The disk
also carries `HELP.TXT`, a longer guide to the board, the parts and their
limits, which you can read in Note Pad.

## Good to know

- One board holds up to 64 parts and 128 wires.
- Only one supply is supported, connected to ground. A second one gets a
  warning.
- An LED has no built-in resistor: wire one in series, or the circuit
  warns you. Every current must stay within 30 mA.
- Logic chips need power on pin 14 and ground on pin 7. A chip input left
  unconnected reads Z, never LOW.
- The 555 timer's pins are 1 GND, 2 TRIG, 3 OUT, 4 RESET, 5 CONT, 6 THRES,
  7 DISCH and 8 VCC.
- The circuit's clock is its own, not the wall clock. A smaller timestep
  gives more exact timing and takes longer to calculate.
