# Desk Board Design

The desk board (`frontend/`) is the one screen where a human watches the bulldog agent team work a ticket, decides what the team proposed, and sees what it cost. This doc covers how the board looks and why. It's kept in sync with the page: when the design changes, this file changes with it (see [Revisions](#revisions)).

**Run it:** from the hw5 folder, activate the venv (`source .venv/bin/activate`), start the API with `uvicorn main:app --reload --port 8000`, then the board with `npm run dev`. Open `http://localhost:5173`. The board calls the API directly at `http://localhost:8000`, and the API only accepts browser requests from `http://localhost:5173`.

---

## 1. Overall look

| Choice | What it looks like | Why |
|---|---|---|
| **Layout: choose → watch → decide** | Three columns. Left: the tickets. The selected ticket is tinted light blue (`#e8f0fa`) with a Yale-blue border, and its card opens to show its item or linked lease/invoice, the **Start agent team** button, and run details. There's no separate details box. Center: the agent team, the original **ticket request**, the Boss's plan, the summaries, and the activity feed. Right: approvals and cash. | It follows the order you work in, left to right: pick a ticket, watch the team, then approve and check the money. The things that need your hand (approvals, cash) never scroll out of the center story. |
| **Palette** | Warm cream "shop floor" background (`#f6f1e7`), off-white cards (`#fffdf8`), and a **Yale blue** header and accents (`#00356b`). | Campus Customs is a Yale apparel shop. The blue says Yale, and the warm neutrals feel like a store, not a spreadsheet. |
| **Selected ticket** | Light-blue card with a blue border; only that card expands to show details and controls. | Which ticket you're looking at is obvious at a glance, and its controls sit right on it instead of in a fourth box that repeated the card. |
| **Status colors** | Blue = working / open, amber = needs you / waiting, green = done / resolved / executed, red = refused, declined, or money going out. | Each color means exactly one thing everywhere on the page, so a glance tells you where attention is needed. Color always comes with words ("Needs your approval", "✓ Resolved"), never alone. |
| **Type** | Monospace for headings, names, and money (`$3,400.00`). System sans-serif for everything you read at length. | The monospace matches the pixel-art bulldogs and keeps dollar amounts lined up. Long agent text stays easy to read. |
| **The stage** | The five bulldogs stand on a striped "wallpaper" with a tan floor strip. | It reads as a little office where the team works, not a table of rows. |
| **Top bar** | The Customer Service bulldog as the logo, sitting right on the Yale-blue bar (no white tile) so it blends into the header, shop name, desk date, the "Approving as" name, live checking balance, a **Sound on/off** toggle, and **Reset shop**. | The three things that matter all session (who's approving, how much cash, start over) are always visible. |

## 2. How the agents read differently

All five agents are the **same small pixel bulldog**, 16 pixels wide: folded brown ears, a small rounded cream muzzle with a big nose, and a "w" mouth. Each one is told apart by **one accessory and one accent color**. Keeping the dog identical says "one team." Changing only the gear makes each role recognizable even at 26 px in the activity feed.

| Agent | Accessory | Accent | Why this accessory |
|---|---|---|---|
| **Boss** | Navy suit and red tie | Navy `#2c3e66` | Your idea; it reads instantly as "in charge." |
| **Inventory** | Clipboard checklist held at the chest | Clipboard brown `#b9814a` | Counting stock is checklist work. The clipboard is clearer than a box at pixel size. |
| **Accounting** | Green accountant's visor | Visor green `#2e9e5b` | The visor sits on the head, so it stays visible even in the small feed avatars. |
| **Facilities** | Yellow hard hat | Gold `#c99700` | Facilities owns the physical shop. The hard hat says "building." |
| **Customer Service** | Headset with red ear cups and a mic | Red `#c0392b` | The headset is the universal support cue. |

Each agent's accent color is taken from its accessory and appears in its **name label** and its **speaking outline**. Color and gear tell the same story.

**What each agent is doing** is shown in four ways, all built from the live event stream:

| State | How it looks | When |
|---|---|---|
| Waiting | Bulldog **asleep**: eyes shut, slow bounce, dashed empty bubble ("Zzz…" or "Standing by…"), grey **Waiting** chip | Not called on this run (yet) |
| Working | Bulldog **bobs**, blue **Working…** chip with animated dots | Using a tool, or a teammate has asked it something |
| Speaking | Bubble **outlined in the agent's accent color** | It produced the newest event: only one dog speaks at a time, so your eye knows where to look |
| Done / Stopped | Green **Done** chip / red **Stopped** chip. A teammate turning Done plays a short rising chime in its own pitch; the Boss turning Done (plan ready, the team's work is finished) plays a longer fanfare | It reported back / the run hit an error or limit |

The **speech bubble** shows the agent's latest line in plain words: "Using check_vendor_can_ship…", "Asking Accounting: …", "Accounting asked me: …", "To Boss: …", or "Plan ready: …". Long lines are cut to four lines in the bubble; hover to see all of it.

The **activity feed** keeps the full record. Each line has the agent's bulldog avatar and a timestamp:
- Tool calls are grey, since they're background detail.
- Plans and resolutions are bold.
- Human decisions are blue, with a 👤 instead of a bulldog.
- Desk-system events (a blocked action, a failed run) get a ⚙️.

The feed scrolls to the newest event like a chat.

Between the stage and the plan, a **Ticket request** card quotes what the requester originally asked ("Needs a tee in size S."), with who sent it, the ticket type, and when it arrived (shop time). It's tinted like the selected ticket and shows even before a run, so you can read the ask before seeing what the team made of it. Notes appended later (approved messages, status changes) are left out.

After the run, **"What each agent did"** gives each bulldog one short recap: tools used (with counts, e.g. `check_stock ×3`), who it consulted, and the first lines of what it reported. Agents that weren't needed are faded and say so. The Boss's full plan sits in its own card above, with the **cash check** set off in a tinted box, so the recap only has to name it.

## 3. How resolved tickets show up

A ticket is **resolved** once the run has finished and you have approved every action the team proposed, or you click **Mark ticket resolved**. The backend then marks it resolved through the MCP server, with you as the approver. If you approved an agent's own status change (such as "waiting"), that status is kept.

| Where | Open | Waiting on you | Resolved |
|---|---|---|---|
| Ticket card pill | Blue **OPEN** | Blue **OPEN** | Green **✓ RESOLVED** |
| Ticket card run chip | Grey "Not run yet" / blue "Agents working…" | Amber **"Needs your approval"** or **"Needs your OK to close"**, then blue "Resolving…" for a moment while the server records it | Green **"Run finished"** |
| Selected ticket's card (expanded) | **Start agent team** button | Button reads "Run the team again" | Button disabled, with the note "Resolved. Reset the shop to run it again." |
| Page banner | — | Amber "The team is waiting on you: N actions need approval." | — |
| Nothing left to approve, but not resolved | — | Amber **"Needs your OK to close"** chip and a green **Mark ticket resolved** button, with a note on why (something was declined, refused, or belongs to another ticket, or the plan had nothing to approve). The button needs your name in "Approving as," like every approval. | — |

Agents never resolve a ticket on their own. If you approve everything, the ticket resolves with your approval. If you decline something, the server refuses something, an action belongs to another ticket, or the plan had nothing to approve, you close it yourself (or run the team again).

**Why:** the card answers "is this done?" and the chip answers "what's happening with the agents?" Those are different questions, so they get different badges. Amber is used only when the next move is yours.

## 4. How approvals and cash show up

**Approvals panel** (right column):
- **Payments and purchases come first**, with a gold border, a soft glow while pending, and the amount in large monospace. Messages and ticket updates follow in plain cards. *Why:* these are the actions that move money, which is the riskiest thing a human signs off on.
- Buttons say what they do: **Approve payment** / **Approve purchase** / **Decline**. They stay disabled until you type your name in "Approving as," because every approval is recorded with a name.
- Customer messages have a **"Read the draft"** toggle, so you approve the exact words.
- An action that belongs to a different ticket (for example #101 proposing #102's rent) shows as grey **Belongs to another ticket** with no buttons, so the same bill can't be approved twice.
- Once decided, the buttons are replaced by the outcome in place:
  - green **Done · name**, with "Checking $3,400.00 → $1,000.00";
  - amber **Declined**;
  - red **Refused by the shop rules**, with the server's reason (for example, overdraft or vendor blocked).

**Checking balance** shows in two places:
- **Top bar:** always visible, so you see the effect the moment you approve.
- **Checking balance panel:**
  - the balance in large Yale-blue monospace;
  - the change since the **last reset**, in red when cash went down ("−$3,248.00 since $3,400.00 at the last reset"). The starting point comes from the database, not from when the page opened: it's the current balance plus every payment since the reset, so it stays right after a page reload or an API restart;
  - what's still owed (open invoices plus rent due within 30 days);
  - a **ledger** of each payment since the last reset, read from the database's `payments` table, such as "#101 Invoice 501 · Bulldog Print Co −$840.00", "Vendor order · 1 x CC-TEE-WHITE S −$8.00", and "#102 Rent · Chapel Street shop −$2,400.00". Hover a line to see who approved it and when. A reset clears it, so the ledger always adds up to the change shown above it.

The panel ends with the house rule in fine print: *No revenue is modeled, so cash only goes down, and it can never go below $0.* The final adjusted balance is the big number once every action is decided.

## 5. Behavior choices

- **Live but calm:** while agents are working, the board polls every 1.5 s; otherwise every 4 s. If the API isn't up yet, the board keeps retrying and clears the error banner once it connects.
- **Playful motion:** sleeping bulldogs bounce slowly (out of step with each other), working bulldogs do a quick two-frame pixel bob, and any bulldog hops when the cursor touches it (the hop always finishes, even if the cursor moves away). If your system asks for reduced motion, all of it is turned off.
- **Sound:** chimes are synthesized in the browser (no sound files) and only play for changes in a run you're watching live, not when you open an old run. The top-bar toggle mutes them, and the choice is remembered.
- **Survives restarts:** the API rebuilds each ticket's latest run from the audit trail when it starts, and the cash panel reads straight from the database. Restarting the server or reloading the page shows the same run chips, plan, activity feed, approvals, and ledger as before.
- **Linkable tickets:** `http://localhost:5173/?ticket=102` opens the board on that ticket. The screenshots in `output/resolved_board.html` were taken this way.
- **Errors say how to fix them**, for example: "Cannot reach the desk API. Start it from hw5/ with: uvicorn main:app --reload --port 8000."
- **Reset asks first**, because it wipes every run and approval and starts a fresh audit trail (the old one is archived), and then **says whether it worked**: a green banner confirms the new balance and where the old audit trail was saved, a grey one says a canceled reset changed nothing, and a red one says it didn't go through and why (for example, a ticket is still running or an approval is still being carried out). The green and grey banners fade after 8 seconds.
- **Responsive:** on narrower screens, approvals and cash move below the team, and the stage wraps to 3 dogs per row. On phones, everything stacks in one column.
- **Accessible:**
  - Sections are labeled landmarks, and the feed is a polite live region.
  - Each bulldog has a text description, such as "Accounting bulldog with green visor."
  - All controls are real buttons.

## 6. Where to change things

| To change… | Edit |
|---|---|
| Bulldog art and accessories | `frontend/src/sprites.ts` (each character is one pixel; `PALETTE` sets the colors) |
| Chimes | `frontend/src/sounds.ts` (pitches per agent, Boss fanfare) |
| Sleep, bob, and hop animations | `snooze`, `bob`, and `hop` keyframes in `frontend/src/index.css` |
| Logo, banners (reset result, waiting on you), Mark ticket resolved | `frontend/src/App.tsx` |
| Agent names, jobs, accent colors | `AGENTS` in `frontend/src/agents.ts` |
| Bubble wording / what counts as working or done | `deriveAgents` in `frontend/src/agents.ts` |
| Colors, type, layout | `frontend/src/index.css` (`:root` variables at the top) |
| Approval card wording and order | `frontend/src/components/ApprovalPanel.tsx` |
| Cash panel | `frontend/src/components/CashPanel.tsx`; its data comes from `GET /cash` (`starting_balance`, `payments`) |
| API address | `VITE_API_URL` (default `http://localhost:8000`) in `frontend/src/api.ts`; allowed board origin: `BOARD_ORIGINS` in `backend/main.py` |

---

## Revisions

| # | Change | Why |
|---|---|---|
| 1 | First design: three-column choose → watch → decide layout; pixel bulldogs with one accessory each; status colors; approvals with money first; cash panel with ledger. | Initial build (Problem 8). |
| 2 | The board calls the API directly at `http://localhost:8000` from `http://localhost:5173`. The API's CORS allows only that origin. `npm run dev` starts the board. | Matches the required origins and start command. Plain GETs skip the CORS preflight, so polling sends half as many requests. |
| 3 | Simpler bulldogs with one accessory each; sleeping dogs shut their eyes and bounce; dogs hop on hover; chimes when an agent finishes and a Boss fanfare when the team is done, with a sound toggle. | Your design feedback: simpler, more alive, and an audible cue so you don't have to watch the board. |
| 4 | Bulldogs redrawn narrower and smaller (16 px wide, shown at 64 px), with a new snout: a small rounded muzzle, big nose, and "w" mouth instead of wide jowls and teeth. Added **Mark ticket resolved** and the "Belongs to another ticket" state. | Your feedback on the dog shape. The resolve button follows the review fix that only a human can close a ticket. |
| 5 | The Boss bulldog replaces the "CC" logo. Reset now confirms whether it went through. | Your feedback: the logo should be the team's face, and a reset shouldn't be silent. |
| 6 | Review fixes that show on the board: a blue "Resolving…" chip while a ticket is being closed; an action that belongs to another ticket now keeps the ticket open for your OK; ⚙️ marks desk-system events in the feed; reset clears the payment ledger along with the balance. | Keeps every state honest: nothing closes without a human, and the ledger never disagrees with the balance. |
| 7 | The logo's white tile is gone, so the Boss sits on the blue header. The selected ticket is tinted light blue, and the separate details box was merged into the selected ticket's card (dropping the From and Status lines and the run chip, which the card already shows). The column heading stays "Tickets" rather than "Selected Ticket", since it still lists all three. | Your feedback: the logo should blend in, the selected ticket should be obvious, and the fourth box was redundant. |
| 8 | The Boss's suit is black instead of navy, on the stage and in the logo; the Boss's name label and speaking outline follow it. | Your feedback. A black suit also stands out from the Yale-blue header now that the logo sits right on it. |
| 9 | The Boss's suit is light gray instead of black; its name label and speaking outline use a darker slate gray from the same family. | Your feedback: light gray contrasts better with the dark-blue header behind the logo. Light gray text would be too faint on cream, hence the darker accent. |
| 10 | The cash panel measures change from the **last reset**, and its ledger lists every payment saved in the database, both from `GET /cash`. | Before, the baseline was whatever the balance was when the page loaded, and the ledger lived in the API's memory, so after a restart the panel said "No change from $152.00" with an empty ledger. Now it always tells the true story since the reset. |
| 11 | The Boss's suit is navy again, and the Customer Service bulldog replaces the Boss as the logo (and, later, as the browser-tab icon, `frontend/public/favicon.svg`). | Your feedback. Customer Service is the shop's face to customers, and its red ear cups and gray headset stand out on the dark-blue header, where a navy suit would blend in. |
| 12 | Finished runs survive an API restart: the run chip, Boss's plan, activity feed, agent recaps, and approval cards are rebuilt from the audit trail. | Your question: tickets showed "✓ Resolved" next to "Not run yet" because the run lived only in the API's memory. The two badges now always agree. |
| 13 | A **Ticket request** card with the original request text sits above the Boss's plan. | Your feedback: read the ask first, then the plan, without going back to the ticket list. |
