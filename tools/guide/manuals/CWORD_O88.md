# Microsoft Word (C edition)

This is a second Microsoft Word, written again in the C language. It looks
the same as Word on the Word disk: the same nine menus, ribbon, ruler, status
line and dialogs, modelled on Word for Windows 1.1a. Its title bar and the
menu bar also say **Microsoft Word**. The differences are in what it can do
and in its file format: this edition reads and writes **RTF** files only,
holds smaller documents, and has no Undo.

This manual describes the C edition completely. Where it behaves like the
other Word, the text says so briefly; the Microsoft Word manual has more
detail on those parts.

![The C edition with its welcome document open.](shot:cword-window)

## Starting it

The C edition comes on its own floppy. Put that disk in a drive, open it and
double-click **CWORD.O88**. Then use **File > Open...** to open
**WELCOME.RTF**, the welcome document beside it. The disk also has an empty
**DOCS** folder for your own documents.

Once the program has run, double-clicking an `.RTF` file opens it in the C
edition. Each window holds one document. A new document is called
**Document** in the title bar until you save it.

## What is the same as Word

- **The window**: menu bar, ribbon, ruler, text with a scroll bar, and the
  status line with `Pg`, `Sec 1`, the page out of the total, `At`, `Ln`,
  `Col`, and the EXT, CAPS, NUM and OVR lamps. View > Ribbon, Ruler and
  Status Bar hide and show them.
- **The menus**: open them with the mouse (click, or press and drag) or with
  `Alt` and the underlined letter, then the arrows, `Enter` or an item's
  letter. Grey items are features this machine cannot offer.
- **Typing**: click to place the caret; the arrows, `Home`, `End`, `PgUp`,
  `PgDn`, `Backspace` and `Del` work as usual. `Ins` switches overtype on and
  off.
- **Selecting**: drag with the mouse, or press `F8` and stretch the selection
  with the arrow keys. Typing replaces the selection.
- **Character formats**: bold, italic, small caps, underline, word underline,
  double underline and hidden, from the ribbon's B I K U W D buttons, from
  **Format > Character...**, and from `Ctrl+B`, `Ctrl+K`, `Ctrl+U`, `Ctrl+W`
  and `Ctrl+D`.
- **Paragraph formats**: left, centred, right and justified; single, one and
  a half and double spacing; a blank line before; and left, first-line and
  right indents. The keys are `Ctrl+L`, `Ctrl+C`, `Ctrl+R`, `Ctrl+J`,
  `Ctrl+O` (space before), `Ctrl+E` (no space before), `Ctrl+N` (indent half
  an inch more), `Ctrl+T` (hanging indent) and `Ctrl+G` (undo the hanging
  indent).
- **The Font box** lists Pica and the typefaces in the system disk's
  `SYSTEM/FONTS` folder, and sets the whole document in the one you pick. The
  ¶ button at the right of the ribbon shows and hides paragraph marks.
- **Views**: View > Draft wraps to the window, View > Page to a six-inch
  column with page ticks.
- **Go To**: Edit > Go To... (`F5`) moves to a page, counting 54 lines to a
  page.
- **Saving changes**: New, Open, Close and Exit ask **Do you want to save
  changes to** the document, with Yes, No and Cancel.
- **The clipboard** is shared with the other programs.

## What is different

**Files.** The C edition opens only RTF files. Any other file is refused with
**That is not an RTF file.** Save and Save As always write RTF, whatever the
name. The first save of a new document suggests the name **DOC.RTF**.

**What a file keeps.** Saving keeps the text and three character formats:
bold, italic and underline. Word underline and double underline are saved as
plain underline, and small caps, hidden text and all paragraph formats are
not saved at all. They show on screen while the document is open. When it
opens an RTF file, the C edition also reads every paragraph as a normal
left-aligned paragraph.

**Size.** A document holds up to 4,000 characters; past that the program says
**This document is full.** A longer file opens cut short. A document can use
64 different paragraph formats.

**No Undo.** Edit > Undo is grey. Repeat is grey too.

**Keys.** These work differently from Word:

| Key | In the C edition |
|---|---|
| `Ctrl+F` | Opens Format Character (it opens Search in Word) |
| `Ctrl+P` | Opens Go To |
| `Ctrl+S` | Save |
| `F12` | Save As |
| `F1` | About |
| `Tab` | Types a space; there are no tab characters |

Cut, Copy and Paste are on the Edit menu only. The captions beside them
(`Shift+Del`, `Ctrl+Ins`, `Shift+Ins`), and `Ctrl+F12`, `Shift+F12` and
`Alt+F4` on the File menu, are shown but do nothing here: `Del` deletes and
`Ins` switches overtype. There is no `Ctrl+A`, `Ctrl+X`, `Ctrl+2` or
`Ctrl+Space`, and `Esc` does not end extend mode; press `F8` again.

**Menus grey themselves.** Save is grey until the document has changes, Cut
and Copy are grey with nothing selected, and Paste is grey when the
clipboard is empty.

![The Edit menu: Undo and Repeat are grey, and Cut, Copy and Paste have no working keys.](shot:cword-edit-menu)

**The Character dialog** has the seven check boxes and OK and Cancel. Its
Position and Color line is a label. The underline boxes are named Word
Underline and Double Underline.

![The C edition's Character dialog.](shot:cword-character)

**The Paragraph dialog** has Alignment (Left, Centered, Right, Justified),
Line Spacing (Single, 1 1/2 Lines, Double), a **Space Before** check box, and
three Indents boxes. The indent boxes cannot be typed into in this edition;
use `Ctrl+N`, `Ctrl+T` and `Ctrl+G` instead.

![The C edition's Paragraph dialog.](shot:cword-paragraph)

**The ruler** has the Style box, four alignment buttons (L C R J), three
spacing buttons (1, 5 for one and a half, 2) and two buttons for a blank
line before (O) or none (C). Click a button to apply it. The scale shows the
indent markers, but they cannot be dragged.

**Search and Replace.** Edit > Search... has Search For, Whole Word, Match
Upper/Lowercase and Down or Up. It searches from the caret to the end (or
the start) of the document and does not go round. `F4` and `Shift+F4` repeat
it. The `^` and `?` codes are not understood: every character is matched as
itself. Edit > Replace... has a **Replace All** button that replaces every
match and says how many it replaced. The **Confirm Changes** box can be
ticked, but this edition never asks.

**Sort, Renumber and Table of Contents** run at once, with no dialog, on the
selected paragraphs or the whole document.

- **Utilities > Sort...** puts the paragraphs in alphabetical order, ignoring
  capitals.
- **Utilities > Renumber...** puts `1.`, `2.`, `3.` and so on at the start of
  each paragraph, replacing a number that is already there.
- **Insert > Table of Contents...** collects every short paragraph (3 to 40
  characters) that does not end in a full stop, and puts the list at the top
  of the document under a bold **Contents** heading.

**About.** Help > About... (or `F1`) says the program is a reimplementation,
in C, of the interface and file format of Word for Windows 1.1a, with the
Computer History Museum credit.

## The menus

| Menu | Items that work |
|---|---|
| File | New..., Open..., Close, Save, Save As..., Exit |
| Edit | Cut, Copy, Paste, Search..., Replace..., Go To... |
| View | Draft, Page, Ribbon, Ruler, Status Bar |
| Insert | Table of Contents... |
| Format | Character..., Paragraph... |
| Utilities | Renumber..., Sort... |
| Macro | none |
| Window | **1** and the document's name |
| Help | About... |

## Files

RTF in and out. Use **Save As** to name a document, for example in the
**DOCS** folder. The RTF it writes can be opened by Word, Scribe and other
programs that read RTF.

## Good to know

- Keep paragraph formatting for the screen: it is lost when you close the
  document. If you need it in the file, use Word, which saves it.
- If a file is longer than 4,000 characters, the program says **The document
  was truncated to fit.** Do not save over the original.
- Closing the window with its close box does not ask about unsaved changes.
  Use File > Close or Exit.
- If the Font box cannot use a typeface it says **That typeface would not
  open.**
