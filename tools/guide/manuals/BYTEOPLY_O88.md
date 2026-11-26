# Byteopoly

Byteopoly is a property-trading board game about collecting vintage
computers. Two to four players roll the dice and move round a board of
28 spaces, buy the computers they land on, from the Commodore PET to the
486DX2, collect rent from each other, and trade, upgrade and mortgage
their way to the top. Everyone can play at one PC, taking turns at the
keyboard, or on two PCs joined by a null-modem cable.

## Starting Byteopoly

Byteopoly has a disk of its own. Double-click **BYTEOPLY.O88** to start. It
runs on VGA, EGA, CGA and Hercules screens. Two Byteopoly windows can be
open at once, each with its own game.

The game opens on the **New Game** screen, which has three tabs:

- **Same PC**: everyone plays here, taking turns at one keyboard.
- **Host Cable**: you host a game over the cable and keep the bank.
- **Join Cable**: you join a game the other PC hosts.

## Setting up a game

- **Players.** Two to four, added and removed with `-` and `+`. Click a
  name, or press `Enter` on it, to type a new one of up to eight letters;
  `Enter` keeps it and `Esc` cancels. Each player picks a token, **Floppy**,
  **Mouse**, **Joystick** or **Cassette**, with the arrow keys or a click.
  Two players cannot share a token.
- **Rules.** **Classic** plays until one player is left. **Quick Match**
  ends after 10, 20 or 30 rounds, and the richest player wins.
- **Start Game** (`S`) begins. Everyone rolls for who goes first; ties roll
  again.

`Tab` and the arrow keys move around the screen, `Enter` or `Space`
presses, and `Esc` goes back.

## The board

The 28 spaces run clockwise round the screen: **BOOT** at the bottom left,
**REPAIR SHOP** at the top left, **SWAP MEET** at the top right and
**CRASH!** at the bottom right.

- **Computers.** Sixteen, in six collections: Commodore (C), Home Micros
  (H), Apple (A), IBM (I), 16-bit Rivals (R) and Power PCs (P). Each space
  shows its collection's letter, so a black-and-white screen loses nothing.
- **Utilities.** **POWER** and **BBS**.
- **Cards.** **Floppy Find** and **System Error**, two spaces each.
- **Charges.** **Import Duty** costs 100 cr and the **E-waste Fee** 75 cr.

The sidebar lists the players and their cash, with the current player's
row picked out. Below it are the details of the selected space, the cable
link's state in a cable game, and a log of what just happened. Click a
space, or move to it with the arrow keys, to see its price and rent table;
`Home` jumps back to the current player.

## A turn

1. **Roll** with `Space`. You move clockwise. Passing or landing on BOOT
   pays 200 cr.
2. **Land.** On a computer or utility nobody owns, **Buy** it (`B`) or send
   it to **Auction** (`A`). On someone else's, you pay them rent. On a card
   space, read the card and press `Enter`.
3. **Manage.** Before you end your turn you can propose a trade (`T`) or
   open your collection (`M` or `C`) to upgrade, sell, mortgage or redeem.
4. **End Turn** (`E`). After doubles you roll again instead; three doubles
   in a row send you to the Repair Shop.

A button you cannot use is grey, and pressing it says why. The bar at the
bottom lists the keys the current panel takes. When several players share
one PC, a **Pass the keyboard** panel names the next player between turns;
press `Enter` when they are ready.

## Money and collections

Everyone starts with 1,500 cr. Rent goes to the owner; charges, cards,
purchases and auctions pay the bank.

- **Collections.** Owning a whole collection doubles the rent of its
  computers that have no upgrades, as long as none of them is mortgaged.
- **Upgrades.** On a complete collection you can add one to four RAM
  chips to each computer, then a Workshop as the fifth step. Build and sell
  evenly: no computer in the set may be more than one step ahead of
  another. Rent at levels 1 to 5 is 5, 15, 30, 45 and 60 times the base
  rent. Selling a step returns half its cost.
- **Utilities.** Rent is 4 times the dice with one utility, 10 times with
  both.
- **Mortgages.** Mortgaging pays half the price, and the property earns no
  rent until you redeem it for the loan plus 10%. A computer can only be
  mortgaged when its whole collection has no upgrades.

In **My Collection** (`M`), choose a computer and press `U` to upgrade,
`S` to sell an upgrade, `M` to mortgage or `R` to redeem.

## Auctions

Declining a purchase, or not having the cash for it, starts an auction
among every player still in the game, including you. Bids are multiples of
10 cr, each at least 10 above the highest bid, and never more than your
cash. Press `B` to bid, after setting the amount with `-` and `+` or by
typing it, or `P` to pass; a pass is final. A player who cannot raise is
passed automatically, and the panel says so. The last bidder pays and takes
the computer. There is no time limit.

## Trades

On your turn, before or after you roll, press `T` to propose a trade with
one other player. A trade can include any of either side's computers and
utilities, their Recovery Disks, and one sum of cash paid by either side.
A collection with upgrades cannot be traded. Once sent, the offer is fixed:
the other player accepts (`A`) or rejects (`R`) it, and you can cancel it
(`C`). If anything has changed by the time they accept, the whole trade is
refused; it never half happens.

## The Repair Shop

Landing on the Repair Shop is only a visit. CRASH!, the General Protection
Fault card or a third double in a row send you there detained, with no
salary. At the start of your turn, leave by one of these:

- pay 50 cr (`P`);
- use a Recovery Disk (`F` for one from Floppy Find, `S` for one from System
  Error);
- roll doubles (`R`).

After three failed rolls you pay 50 cr and move. While detained you still
collect rent, bid, trade and manage.

## Cards

There are two decks of eight cards. **Floppy Find** is mostly good news;
**System Error** is mostly bad, and its Bench Service card charges 25 cr
for each RAM chip and 100 cr for each Workshop you own. A **Recovery Disk**
card is kept until you use it or trade it.

## Debt and bankruptcy

When you owe more than you have, the **Debt** panel shows who you owe, how
much, your cash and how short you are. Sell upgrades and mortgage to raise
the cash, then **Settle** (`S`). Or declare **Bankrupt** (`K`, then `K`
again to confirm). Owing a player, they take everything you have left,
mortgages and all; owing the bank, it takes your properties back for other
players to buy. Either way you are out of the game.

## Winning

In **Classic**, the last player left wins. In **Quick Match**, when the
last round is over everyone is scored: cash, plus the price of each
property less its mortgage, plus the resale value of its upgrades. The
highest score wins, and a tie shares the win. The end screen offers
**Review** (`R`) to look at the final board, **New Game** (`N`) and
**Exit** (`X`).

## Two PCs over a null-modem cable

1. Join the two PCs' serial ports with a null-modem cable. The link runs at
   2400 baud, 8N1. **Port** can be left on **Auto**, or set to **COM1** or
   **COM2**.
2. On one PC choose **Host Cable**, on the other **Join Cable**, and press
   **Connect** on both. The link box shows the search, then the other PC.
3. The host sets up the players and the rules. The **Computer** column says
   which PC plays each player: one, two or three players on each PC, up to
   four in all.
4. Both press **Ready**, then the host presses **Start Game**.

The host keeps the bank and rolls the dice; the other PC follows every move
and checks that it reaches the same game. You can only act for the players
on your own PC, and a panel for a player on the other PC says who it is
waiting for.

- **A pulled cable** pauses both PCs on a **Link Paused** panel, and nothing
  changes. Plug it back in and the game carries on where it stopped. A move
  that was being sent happens once, never twice.
- **Game > Paired Save** saves the game on both PCs at the same moment.
  Later, connect again and pick **Game > Resume Pair** in the lobby, or
  **Load Pair** on the Link Paused panel. The two saves must match.
- **Help > Chat...** sends a short line to the other PC.
- If the two PCs ever disagree about the game, the joining PC offers **Use
  host**, which takes the host's copy.

## The Game menu

| Item | Key | What it does |
|---|---|---|
| New Game... | | Go to the New Game screen; an unsaved game asks first |
| Load... | `F3` | Load a saved game (not in a cable game) |
| Save... | `F2` | Save the game on this PC (not in a cable game) |
| Paired Save | | Save a cable game on both PCs |
| Resume Pair | | In the cable lobby, carry on a paired save |
| Close | | Close the window; an unsaved game asks whether to save it |

## The Collection menu

| Item | What it does |
|---|---|
| Propose Trade... | Start a trade with another player (`T`) |
| My Collection... | Upgrade, sell, mortgage or redeem (`M`) |
| Standings | Every player's cash, assets and score |

## The Options menu

| Item | What it does |
|---|---|
| Sound | Turn the sound effects on or off |
| Music | Turn the music on or off |
| Fast Animation | Switches between On and Off; play looks the same either way |
| Diagnostics | In a cable game, the link's counters |

## The Help menu

| Item | What it does |
|---|---|
| Rules | Four pages of rules (`F1`); `PgUp` and `PgDn` turn the pages |
| Keys | Three pages listing the keys |
| Chat... | In a cable game, send a line to the other PC |

## Keys

| Key | What it does |
|---|---|
| `Space` | Roll the dice |
| `B` | Buy the computer, or bid in an auction |
| `A` | Send it to auction, or accept a trade |
| `P` | Pass in an auction, or pay 50 cr to leave the Repair Shop |
| `R` | Roll to leave the Repair Shop, reject a trade, or redeem |
| `T` | Propose a trade |
| `M` or `C` | Open your collection |
| `U`, `S` | Upgrade, or sell an upgrade, in your collection |
| `E` | End your turn |
| `S` | Settle a debt |
| `K` | Declare bankruptcy; `K` again to confirm |
| `F`, `S` | Use a Recovery Disk in the Repair Shop |
| Arrow keys, `Home` | Move round the board, or jump to the current player |
| `Tab`, `Enter` | Move to the next button, press it |
| `F1`, `F2`, `F3` | Rules, Save, Load |
| `Esc` | Go back: close a panel or cancel an edit |

The mouse works too: click a space, a button or a row.

## Sound

With an AdLib or Sound Blaster and the system's sound driver, Byteopoly
plays music: a theme on the New Game screen, a quiet tune during play, a
tenser one during an auction, and a fanfare for the winner. With only the
PC speaker the music plays the tune alone and starts off; turn it on in
**Options** if you want it. The sound effects, for the dice, buying, rent,
the cards, CRASH!, bids, trades and more, play on either.

## Files

**Game > Save...** writes the game to a file, named `BYTEOPLY.BPS` unless
you choose another name, and **Game > Load...** reads one back. A damaged
or wrong file is refused and the game in progress is left alone. A paired
save in a cable game keeps two files on each PC: `BPHOSTA.BPC` and
`BPHOSTB.BPC` on the host, `BPCLNTA.BPC` and `BPCLNTB.BPC` on the other PC.

## Good to know

- There are no computer players: every seat is a person.
- A cable game joins exactly two PCs.
- On a machine too short of memory to load its sounds, the game plays
  silently.
