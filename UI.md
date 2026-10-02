# UI plan

What the review app looks like, and how it gets built: every page, component, color and build step, for Stage 1 and the later stages. `Plan.md` Steps 13–14 cover the backend and when the UI is built. The progress page on the VM (Plan Step 6) uses the same colors and fonts.

## Goals

- **Clean:** two colors carry meaning (ally blue, enemy red); everything else is gray. No gradients, shadows or decoration.
- **Neat:** one spacing scale, one card style, numbers lined up (tabular figures, right-aligned in tables).
- **Simple:** four pages. No modals, settings pages or menus. Every panel on the review page follows one value: the selected time.

## Rules

1. **Blue means your team or good for you. Red means the enemy or bad for you.** This is League's own convention (on the minimap allies are blue whichever side you play), so the side you played (blue side / red side) only appears as text.
2. **Color is never the only signal.** Grades have glyphs (`!!`, `!`, `?`, `??`), deltas have signs (+18%, −11%), results have words (Victory).
3. **The frontend has no game logic.** It shows what the backend sends: the curve, the moments, and a snapshot every 15 s. The state at time `t` is `snapshots[Math.floor(t / 15)]`.
4. **One card style.** `--surface` background, 1 px `--border`, 10 px radius, 16 px padding, a 14 px semibold title in `--text-2`. 24 px between cards.
5. **No layout shift.** Loading skeletons are the final size; images have fixed sizes.
6. **Text uses the text colors.** The colored mark beside a label carries the meaning. Colored text is kept to Δ%, the result word, grade badges and error messages, and each of those also has a sign, glyph or word.

## Design tokens (`frontend/src/styles/tokens.css`)

Dark theme only. The League client, the minimap and champion icons are all dark, and one theme halves the checking. Every value is a CSS variable, so a light theme later is one extra block.

| Token | Value | Use |
|---|---|---|
| `--bg` | `#0f1115` | page |
| `--surface` | `#171a21` | cards, top bar |
| `--surface-2` | `#1e222b` | hover, selected row, empty item slot, skeletons |
| `--border` | `#2a2f3a` | card borders, dividers, the 50% line |
| `--text` | `#e6e8eb` | main text (14.2:1 on `--surface`) |
| `--text-2` | `#9aa1ad` | secondary text, card titles (6.7:1) |
| `--text-3` | `#7d8592` | muted: axis labels, dates, footnotes (4.7:1) |
| `--ally` | `#3987e5` | your team, good for you, focus ring (4.8:1) |
| `--enemy` | `#e66767` | enemy team, bad for you (5.4:1) |
| `--ally-tint` | `#3987e529` | `!` badge, graph fill above 50%, your scoreboard row |
| `--enemy-tint` | `#e6676729` | `?` badge, graph fill below 50% |
| `--warn` | `#fab219` | key-expired banner, `Miss` badge (Stage 2) |

Checked: the ally/enemy pair passes the dataviz palette validator on `--surface` (colorblind ΔE 19, normal vision ΔE 29), and every text token passes WCAG AA (4.5:1) on `--surface`. Text on a filled `--ally` or `--enemy` badge is `--bg` (5.2:1 and 5.9:1), not white (3.6:1).

**Type**
- Inter, self-hosted with `@fontsource-variable/inter` (no CDN); fallback `system-ui, sans-serif`.
- Sizes: 12 (badges, axis labels, footer), 14 (body, tables), 16 (inputs, review title), 20 (page titles), 32 (wordmark on the search page).
- Weights: 400 and 600 only.
- `font-variant-numeric: tabular-nums` on times, tables, deltas and axis ticks.

**Spacing** 4, 8, 12, 16, 24, 32, 48 px. **Radius** 6 px (inputs, buttons, badges), 10 px (cards), round champion icons.
**Motion** 120 ms ease-out on hover and selection only; none under `prefers-reduced-motion`.
**Icons** `lucide-react` at 16 px for controls (chevrons, play, search, refresh). Game images come from Data Dragon.

**Formatting** (`lib/format.ts`)
- Time `mm:ss` (`h:mm:ss` past an hour). Win chance as a whole percent, shown as 1–99% until `GAME_END` so the graph never claims certainty early. Deltas `+18%` / `−11%` with a real minus sign (U+2212). Gold `9.1k`. Dates relative ("2 days ago"), the full date on hover.

## Pages

| Route | Page |
|---|---|
| `/` | Search |
| `/p/:platform/:name/:tag` | Games: the player's recent ranked solo games |
| `/review/:matchId?p=<participantId>&t=<seconds>` | Review |
| `/model` | Model |

The review keeps the selected time in the URL (`t`, updated with `replaceState` at most every 200 ms), so reload and back/forward return to the same moment.

### App shell

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ LeagueVODreview                                              Search    Model │
├──────────────────────────────────────────────────────────────────────────────┤
│ Riot API key expired. Paste a new one after RIOT_API_KEY= in .env.           │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│                   page content, centered, max width 1280 px                  │
│                                                                              │
├──────────────────────────────────────────────────────────────────────────────┤
│ LeagueVODreview isn't endorsed by Riot Games …      Model 2026-10-01 · 26.19 │
└──────────────────────────────────────────────────────────────────────────────┘
```

- **Top bar** (56 px): the wordmark links to `/`; two text links, the active one in `--text`, the other in `--text-2`.
- **Banner:** only when `GET /api/health` (polled every 60 s) reports a problem: key expired or missing. A 3 px `--warn` left border and the fix in plain words.
- **Footer** (12 px, `--text-3`): Riot's required legal line ("LeagueVODreview isn't endorsed by Riot Games and doesn't reflect the views or opinions of Riot Games or anyone officially involved in producing or managing Riot Games properties. Riot Games, and all associated properties are trademarks or registered trademarks of Riot Games, Inc.") and the model's date and patches, or "Placeholder model".

### Search (`/`)

```
                            LeagueVODreview
                 See how every moment moved your win chance.

           ┌────────────────────────────────┬────────┬──────────┐
           │ Name#TAG                       │ NA   ▾ │  Search  │
           └────────────────────────────────┴────────┴──────────┘
             Recent   Me#NA1  ·  Friend#1234
```

- One input group, 44 px tall, about a third of the way down the page. Autofocused.
- Server select lists every platform; NA is the default; the last choice is remembered.
- Checked on submit: needs a `#`, a 3–16 character name and a 3–5 character tag. The error shows under the input in `--enemy`.
- Enter submits; the button shows a spinner while the lookup runs.
- **Recent:** the last 5 Riot IDs as text links (in `localStorage`, read and written inside try/catch so the page still works without it).
- Success goes to the Games page.

### Games (`/p/:platform/:name/:tag`)

```
┌──────────────────────────────────────────────────────────────────────────┐
│ Name#TAG                                                      ↻ Refresh  │
│ Gold III · 47 LP · NA                                                    │
├──────────────────────────────────────────────────────────────────────────┤
│▌(Ahri)  Victory   Mid       8 / 2 / 11   212 CS   31:42   2 days ago   ✓ │
│▌(Lux)   Defeat    Support   1 / 6 / 9     34 CS   24:05   2 days ago     │
│▌(Ahri)  Victory   Mid       5 / 5 / 7    198 CS   28:10   3 days ago     │
│ (Ahri)  Remake              0 / 0 / 0      4 CS    3:30   4 days ago     │
│  …                                                                       │
│                              Load 10 more                                │
└──────────────────────────────────────────────────────────────────────────┘
```

- One card with one 56 px row per game. The whole row is a link (it works with middle-click and keyboard).
- A 3 px left bar and the result word: `--ally` for Victory, `--enemy` for Defeat. Remakes are muted, say "Remake" and aren't links.
- Columns: champion icon (32 px), result, role, K/D/A, CS, length, date, and a `✓` in `--text-3` when the review is already cached (it opens instantly).
- Hover: `--surface-2` background.
- Loading: 10 skeleton rows. Empty: "No ranked solo games found."
- **Refresh** reloads the match list; matches already cached cost no API calls.

### Review (`/review/:matchId`)

The main page. Everything on it follows one value: the selected time `t`.

```
┌─ ← Games · (Ahri) Ahri · Mid · Victory · 31:42 · Patch 26.19 · 2 days ago ─────────────────────────┐
│ You  !! 1  ! 2  ? 1  ?? 1     Team  !! 2  ! 3  ? 2  ?? 2     Biggest swing  22:10  +18%            │
├─ Win chance  63% ────────────────────────────────────────┬─ Moments   All · Graded · Mine ─────────┤
│                                                          │ ?   03:12  Died to Vi + Lux        −6%  │
│ Win chance from your side. Line, blue fill               │     05:04  Took Ocean Dragon       +2%  │
│ above 50%, red below. Dots: ● !! / ??, ○ ! / ?.          │ !   08:40  Won 2v2 bot             +6%  │
│ A thin line marks the selected time.                     │ ?   14:32  Lost top outer tower    −7%  │
│                                                          │ !!  22:10  Won fight 4 for 1      +18%  │
│ ◀ ▶ ▷  ━━━━━━━━━━━━━━━━━━━━━━━━━━━●━━━━━━━━  22:10       │     52% → 70% · mid lane                │
├─ Minimap ────────────────┬─ Scoreboard @ 22:10 ──────────┤     (Ahri) killed (Zed)                 │
│                          │ Ally   23 · 48.2k · 5 towers  │     (Vi) + (Ahri) killed (Orianna)      │
│                          │ (Ahri) 14   8/2/11  212  9.1k │     (Lee Sin) killed (Ahri)             │
│    map + champion        │ (Vi)   13   4/3/14  141  8.0k │ ??  26:40  Lost fight at Baron    −12%  │
│    icons (canvas)        │ …                             │ !   29:05  Took red inhibitor      +5%  │
│                          │ Enemy  15 · 44.1k · 3 towers  │                                         │
│                          │ …                             │                                         │
└──────────────────────────┴───────────────────────────────┴─────────────────────────────────────────┘
```

**Layout**
- **1280 px and wider:** as drawn. The right column is 360 px, sticky, and scrolls on its own; the left column takes the rest. The page fits 1440×900 without scrolling.
- **1024–1279 px:** Moments moves below the minimap and scoreboard, full width.
- **Under 1024 px:** one column: header, graph, minimap, scoreboard, moments. Usable, but not a design target.

#### Header
- A back link to the player's Games page.
- Champion icon (40 px), then "Ahri · Mid · Victory · 31:42 · Patch 26.19 · 2 days ago". Victory/Defeat in the team color. "· Surrender" when the game ended that way.
- Summary: grade counts for you and for your team, as badges with numbers, and the biggest swing as a link that jumps to it.
- Notes in `--text-3`, only when they apply: "Placeholder model", "Patch 26.17 is older than the model's patches (26.18–26.19)", "Rank used: Gold (you're unranked, so the lobby's median)".

#### Win chance graph
- Recharts area chart, 200 px tall, your team's win chance from 0 to 100%. One series, so no legend: the card title names it and shows the value at `t` ("Win chance 63%").
- A 2 px line in `--text-2`. The area between the line and 50% is `--ally-tint` above and `--enemy-tint` below (one gradient with a hard stop at 50%).
- The 50% line is dashed `--border`. Y ticks at 0, 50 and 100 only; x ticks every 5 minutes; no grid.
- **Moment markers** on the line at each moment's end: `!!` and `??` as 10 px filled dots (`--ally`, `--enemy`), `!` and `?` as 8 px rings, each with a 2 px `--surface` outline so they stand off the line. Ungraded moments get no marker.
- **Hover:** a vertical crosshair and a tooltip: "22:10 · 70% · !! Won fight 4 for 1". The hit area is the whole column under the cursor, not just the dot.
- **Click** anywhere on the graph sets `t`.
- **Selected time:** a 1 px `--text` vertical line, drawn as a positioned `div` over the chart, so dragging the scrubber never re-renders the chart.
- The selected moment's span (`t_start`–`t_end`) is shaded `--surface-2`.
- The last point is 100% or 0% at `GAME_END`, with the final segment dotted.

#### Scrubber
- A native `<input type="range">` from 0 to the game's length in 1 s steps: a 4 px `--border` track, the played part in `--text-2`, a 14 px `--text` thumb.
- To its left: ◀ ▶ (previous/next moment) and ▷/❚❚ (play: one game minute per second, stops at the end). To its right: the time.
- `aria-valuetext` reads "22:10, win chance 63%".

Keyboard, anywhere on the page except while typing in an input:

| Key | Action |
|---|---|
| ← / → | previous / next moment |
| Shift + ← / → | 15 s back / forward |
| Home / End | start / end |
| Space | play / pause |

The arrows step through moments the way chess.com's arrows step through moves.

#### Minimap (canvas)
- Square, filling its column (about 360 px on a 1440 px screen), drawn at `devicePixelRatio` so icons are sharp.
- Background: Data Dragon's `map11.png` for the game's patch at 80% brightness, so icons stand out.
- **Coordinates** (`lib/map.ts`): game y points up, canvas y points down. `cx = (x − MIN) / (MAX − MIN) × size`, `cy = (1 − (y − MIN) / (MAX − MIN)) × size`. MIN and MAX come from Plan Step 3 (about −120 and 14,870). Check: the tower squares land on the towers in the image.
- **Draw order:** buildings, kill marks, enemy icons, ally icons, you.
  - Buildings: 6 px squares in the team color; destroyed ones are hollow `--border` squares.
  - Champions: 26 px round icons with a 2 px ring in `--ally` or `--enemy`. Yours gets an extra 2 px `--text` outer ring.
  - Positions only exist once a minute, so an icon's opacity drops from 100% (fresh) to 50% (60 s old).
  - Dead: grayscale and 40% opacity at the death spot, with the respawn seconds under it in 11 px text.
  - Kills in the last 10 s: an ✕ in the killer's team color at the kill spot.
- **Hover** a champion for a tooltip: champion, Riot ID, level, K/D/A, "position 0:42 old".
- Redraws only when `t` changes, inside `requestAnimationFrame`. The map and the 10 icons are loaded before the first draw.
- `?debug=1` draws the map zones from `map_data.py` on top, to check the moment descriptions.

#### Scoreboard
```
 Ally    23 kills · 48.2k · 5 towers · 2 dragons · Baron 1:12      +4.1k
 (Ahri)  Me        14   8 / 2 / 11   212   9.1k   ▢▢▢▢▢▢ ▢
 (Vi)    Friend    13   4 / 3 / 14   141   8.0k   ▢▢▢▢▢▢ ▢
 …
 Enemy   15 kills · 44.1k · 3 towers · 1 dragon
 (Zed)   Someone   dead 0:12  3 / 6 / 2   180   7.2k   ▢▢▢▢▢▢ ▢
 …
```
- Ally team first, then enemy, each sorted by role.
- Team header: kills, gold, towers, dragons (types on hover; soul written out, e.g. "Ocean soul"), the active buff with time left, and the gold lead on the leading team's header.
- Columns: champion (24 px), Riot ID name (truncated, 12 px `--text-2`), level, K/D/A, CS, gold, 6 items + trinket (20 px; empty slots `--surface-2`).
- 32 px rows; numbers tabular and right-aligned.
- Your row has an `--ally-tint` background. A dead player's row is at 50% opacity and shows "dead 0:12" in place of the level.
- Re-renders only when the snapshot index changes (every 15 s of game time), not on every scrubber tick.

#### Moments list
- Card title "Moments" with a segmented control: **All · Graded · Mine** ("Mine" = moments you were part of). Default: All.
- 40 px rows: grade badge (a 28 px slot, empty when ungraded), time, title (one line, truncated, full text on hover), Δ% right-aligned (`--ally` when positive, `--enemy` when negative, `--text-3` when ungraded). Moments you were in get a small dot after the time.
- **Badges:** `!!` filled `--ally` with `--bg` text; `!` `--ally-tint` with `--ally` text; `?` `--enemy-tint` with `--enemy` text; `??` filled `--enemy` with `--bg` text. Screen readers hear Great, Good, Mistake, Blunder.
- Hovering a row grows its marker on the graph. Clicking a row sets `t` to the moment's end (the state after it, like chess.com shows the board after a move) and opens its detail.
- The list scrolls to keep the selected row in view as you step with ← →.

#### Moment detail
Opens inline under the selected row; there's no separate panel.
- "52% → 70% · +18%".
- Where: "Mid lane, near red outer tower".
- The events in order, one per line, with 16 px champion icons: "(Ahri) killed (Zed)", "(Vi) + (Ahri) killed (Orianna)", "Took Infernal Dragon".
- Later stages add their sections here (see "Later stages").

### Model (`/model`)

```
┌─ Model · trained Oct 1 on 412k games · patches 26.18–26.19 ──────────────────┐
│ ┌ Accuracy at 10:00 ┐ ┌ Log loss ─┐ ┌ Calibration ─┐ ┌ Games ─┐              │
│ │ 71.8%             │ │ 0.512     │ │ ±1.4 pts     │ │ 412k   │              │
│ └───────────────────┘ └───────────┘ └──────────────┘ └────────┘              │
│ ┌ Accuracy by minute ────────────────┐ ┌ Calibration ──────────────────────┐ │
│ │ LightGBM ──    baseline - -        │ │ predicted vs actual, diagonal     │ │
│ └────────────────────────────────────┘ └───────────────────────────────────┘ │
│ ┌ By tier ───────────────────────────┐ ┌ Top features ─────────────────────┐ │
│ │ table                              │ │ horizontal bars                   │ │
│ └────────────────────────────────────┘ └───────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
```

- **Stat tiles:** one number each, with one line underneath in `--text-3` saying what it means ("Picks the winner 7 times in 10 at 10:00").
- **Accuracy by minute:** two lines in neutral inks (LightGBM solid `--text`, baseline dashed `--text-3`), each named at its right end; a crosshair tooltip shows both values.
- **Calibration:** 10 dots (predicted vs actual win rate) and a dashed diagonal. Caption, from the bin nearest 70%: "When the model says 70%, teams won 69% of the time."
- **By tier:** a table of tier, test games, accuracy and log loss. Your tier's row is highlighted.
- **Top features:** the top 15 by gain as horizontal bars in `--text-3`, each with its value.
- Each chart has a "Numbers" `<details>` under it with the same data as a plain table.
- **No model yet:** one card: "No trained model yet; the app is using a placeholder. Train on Kaggle (Plan Step 10) and put `model.txt` and `metrics.json` in `models/`."

### Progress page (VM)

Same tokens in an inline `<style>`, the system font, no JavaScript, plain tables. Plan Step 6 has its content.

## States

Every view that loads data has the same four states.

| State | What you see |
|---|---|
| Loading | Skeleton blocks at the final size in `--surface-2`, with a slow pulse (none with reduced motion) |
| Building a review | The review skeleton, with "Building review…" in the graph card |
| Empty | One line of `--text-2` text, centered in the card |
| Error | `ErrorBox`: the message, plus a Retry button when retrying can help |

Messages, by the backend's `error.code`:

| Code | Message |
|---|---|
| `riot_id_not_found` | No player called Name#TAG on NA. |
| `key_expired` | Riot API key expired. Paste a new one after `RIOT_API_KEY=` in `.env`; it's picked up within a minute. |
| `rate_limited` | Riot's rate limit is full, retrying in 8 s. (Retries by itself.) |
| `riot_unavailable` | Riot's API isn't responding. [Retry] |
| `match_not_found` | Match not found. |
| `unsupported_queue` | Only ranked solo/duo games can be reviewed. |
| anything else | Something went wrong. [Retry] (details in the browser console) |

## Data the UI uses

The TypeScript types are generated from the backend's pydantic models (`lolreview/schemas.py`) with `openapi-typescript` (`npm run gen:api`), so the two sides can't drift apart. In outline:

```ts
type Role = "TOP" | "JUNGLE" | "MIDDLE" | "BOTTOM" | "UTILITY";
type GradeCounts = { "!!": number; "!": number; "?": number; "??": number };
type Building = { id: string; team: "ally" | "enemy"; kind: "tower" | "inhibitor" | "nexus"; x: number; y: number };

// GET /api/health
type Health = {
  riot_key: "ok" | "expired" | "missing";
  model: { kind: "trained" | "stub"; version: string; trained_at?: string; patches?: string[] };
};

// GET /api/player/{platform}/{name}/{tag}?start=0&count=10
type PlayerGames = {
  puuid: string; riot_id: string; platform: string;
  rank: { tier: string; division: string | null; lp: number } | null;
  games: GameSummary[]; next_start: number | null;          // null = no more games
};
type GameSummary = {
  match_id: string; participant_id: number; champion: string; role: Role;
  result: "win" | "loss" | "remake"; k: number; d: number; a: number; cs: number;
  duration_s: number; started_at: string; patch: string; reviewed: boolean;
};

// GET /api/review/{match_id}?p={participant_id}
type Review = {
  match: {
    match_id: string; platform: string; patch: string; ddragon_version: string;
    started_at: string; duration_s: number; result: "win" | "loss"; surrender: boolean;
    my_side: "blue" | "red"; tier_used: string; tier_note: string | null;
    model: { kind: "trained" | "stub"; version: string }; patch_in_training: boolean;
  };
  players: Player[];                    // 10, ally first, by role
  buildings: Building[];                // fixed: id, team, kind, x, y
  curve: { t: number; p: number }[];    // your team's win chance 0–1: every 15 s, around events, GAME_END
  moments: Moment[];
  snapshots: Snapshot[];                // every 15 s; index = floor(t / 15)
  summary: { me: GradeCounts; team: GradeCounts; biggest_id: string };
};
type Player = {
  participant_id: number; riot_id: string;
  champion: string;                     // Data Dragon id, e.g. "MonkeyKing"
  champion_name: string;                // display name, e.g. "Wukong"
  role: Role; team: "ally" | "enemy"; is_me: boolean;
};
type Moment = {
  id: string; t_start: number; t_end: number; p_before: number; p_after: number; delta: number;
  grade: "!!" | "!" | "?" | "??" | null; title: string; zone: string; involves_me: boolean;
  events: GameEvent[];
};
type GameEvent = {
  t: number; team: "ally" | "enemy";
  kind: "kill" | "dragon" | "elder" | "baron" | "herald" | "grubs" | "atakhan" | "tower" | "inhibitor" | "plate";
  killer?: number; victim?: number; assists?: number[];
  detail?: string;                      // "Infernal", "mid outer"
  x?: number; y?: number;
};
type Snapshot = {
  t: number; players: PlayerState[]; teams: { ally: TeamState; enemy: TeamState };
  buildings_down: string[];
  recent_kills: { x: number; y: number; team: "ally" | "enemy"; age_s: number }[];
};
type PlayerState = {
  participant_id: number; x: number; y: number; pos_age_s: number;
  level: number; k: number; d: number; a: number; cs: number; gold: number;
  items: (number | null)[];             // 6 slots
  trinket: number | null; respawn_in_s: number;              // 0 = alive
};
type TeamState = {
  kills: number; gold: number; towers: number; dragons: string[]; soul: string | null;
  grubs: number; heralds: number; barons: number;
  buff: { kind: "baron" | "elder"; ends_in_s: number } | null;
};

// GET /api/model → metrics.json, as written by training/train.py (Plan Step 10)
```

- Errors are `{"error": {"code": "...", "message": "...", "retry_after_s": 8}}` with a matching HTTP status.
- A 30-minute game is about 120 snapshots: roughly 120 KB of JSON, 25 KB gzipped.
- Later stages add fields without changing these: `windows` (Stage 2), `plays` on moments and windows (Stage 3), `camps` in snapshots (Stage 4), `positions_1s` (Stage 5).

## Images (Data Dragon)

- **Version:** `match.ddragon_version`. The backend maps the game's patch (26.19) to the newest Data Dragon version for that patch (26.19.1, from `api/versions.json`), so items look the way they did in that game.
- **Champions:** `cdn/{v}/img/champion/{champion}.png`, using the `championName` id (Wukong is `MonkeyKing`); display names from `champion.json`.
- **Items:** `cdn/{v}/img/item/{id}.png`. **Map:** `cdn/{v}/img/map/map11.png`.
- Loaded directly from `ddragon.leagueoflegends.com`; the browser caches them. A missing image falls back to a `--surface-2` square with two letters.

## Tech stack

- **Vite + React + TypeScript** (strict), versions pinned in `package-lock.json`.
- **React Router** for the four routes.
- **TanStack Query** for fetching, caching and retries (a `rate_limited` error waits `retry_after_s`, then retries).
- **Recharts** for the win chance graph and the Model page charts.
- **Plain CSS:** `tokens.css`, `base.css`, and one CSS Module per component. No UI kit, no Tailwind.
- `@floating-ui/react` (tooltips), `lucide-react` (icons), `@fontsource-variable/inter` (font).
- **No state library.** Server data lives in TanStack Query. Review state is three `useState`s (`t`, selected moment, filter) plus the URL.
- **Dev only:** Vitest + Testing Library, MSW (mock API), Playwright, ESLint, Prettier, openapi-typescript.

## Files

```
frontend/
  index.html  package.json  vite.config.ts      # dev server proxies /api to :8000
  src/
    main.tsx  App.tsx                          # router, query client, app shell
    styles/      tokens.css  base.css
    api/         client.ts  types.ts (generated)  queries.ts
    lib/         format.ts  map.ts  ddragon.ts  grades.ts
    components/  TopBar  Footer  HealthBanner  Card  GradeBadge  Delta  ChampIcon
                 ItemIcon  Segmented  Skeleton  ErrorBox  Tooltip
    pages/
      SearchPage.tsx  GamesPage.tsx  ModelPage.tsx  DevComponents.tsx (dev build only)
      review/    ReviewPage.tsx  ReviewHeader.tsx  WinGraph.tsx  Scrubber.tsx  Minimap.tsx
                 Scoreboard.tsx  MomentList.tsx  MomentDetail.tsx  useReviewTime.ts
    mocks/       handlers.ts  review.json  player.json  model.json  health.json
  e2e/           review.spec.ts
```

## Running it

- **Daily use:** `python -m lolreview.app` starts FastAPI, which serves the API and the built UI (`frontend/dist`) at `http://localhost:8000`. One command, one port.
- **While building the UI:** `uvicorn lolreview.api:app --reload` and `npm run dev`, then `http://localhost:5173` with hot reload. `npm run dev:mock` runs the UI on the MSW mocks with no backend at all.
- **npm scripts:** `dev`, `dev:mock`, `build`, `test`, `e2e`, `lint`, `typecheck`, `gen:api`.

## Build steps

Each step ends with something you can open and click. U1–U3 need only the mocks; U4 onwards can use the real backend with the placeholder model, so none of this waits for the crawl (see "Build order" in `Plan.md`).

**U1 — Scaffold.** Vite + React + TS, router with four empty pages, TanStack Query, `tokens.css` + `base.css`, top bar, footer, ESLint, Prettier, Vitest, the `/api` proxy, and the frontend jobs in CI.
*Done when:* `npm run dev` shows the shell, and `lint`, `typecheck`, `test` and `build` pass.

**U2 — API types and mocks.** `schemas.py` → `npm run gen:api` → `api/types.ts`. Mock JSON for health, player, review and model, served by MSW with `npm run dev:mock`. The mocks start hand-written from the types; once Step 13 runs, the review mock is regenerated by the backend from a test fixture with the placeholder model, so it's real data.
*Done when:* the mocks type-check against the generated types.

**U3 — Shared components.** Card, GradeBadge, Delta, ChampIcon, ItemIcon, Segmented, Skeleton, ErrorBox, Tooltip, plus `lib/format.ts` with unit tests. A `/dev/components` page (dev build only) shows all of them together, so the look can be checked in one place.
*Done when:* the dev page looks right next to the tokens table above, and the format tests pass.

**U4 — Search and Games pages.** Input checks, server select, recent searches, the games list with load more, every state (loading, empty, each error).
*Done when:* searching your Riot ID lists your games, a typo shows "No player called…", and a missing key shows the banner.

**U5 — Review layout and header.** The grid at all three widths, header, summary, notes, loading and error states, `t` and `p` in the URL.
*Done when:* the page skeleton holds its layout at 1920, 1440, 1280, 1100 and 800 px, and reloading keeps `t`.

**U6 — Graph and scrubber.** The area chart with the 50% split, markers, crosshair tooltip, click-to-seek, the overlay time line, the scrubber, play/pause, and the keyboard table.
*Done when:* dragging the scrubber never re-renders the chart (React Profiler), and ← → step through the moments.

**U7 — Moments list and detail.** Rows, badges, filters, hover-to-highlight, click-to-jump, inline detail, scroll-into-view.
*Done when:* every moment in the mock is reachable by keyboard, and its graph marker, list row and detail agree.

**U8 — Scoreboard.** Team headers, rows, items, your row, dead rows; memoized on the snapshot index.
*Done when:* the scoreboard at 10:00 and 20:00 matches the in-game scoreboard of a replay of the same game.

**U9 — Minimap.** Map image, coordinate mapping, buildings, champion icons with rings, fading, dead state, kill marks, hover tooltip, `?debug=1` zones.
*Done when:* the towers line up with the image, and at three minute marks the icons are where the replay shows them.

**U10 — Model page.** Tiles, the three charts, the tier table, the "Numbers" tables, and the no-model card.
*Done when:* the numbers match `metrics.json` and `report.md`.

**U11 — Polish and checks.**
- Accessibility: a keyboard-only run-through of all four pages, visible focus rings, and axe checks in Playwright with no serious issues.
- Performance: scrubbing end to end with no dropped frames on the laptop; the first review render under 300 ms after the data arrives.
- A Playwright smoke test on the mocks: search → games → review → step to the next moment → model page. It runs in CI.
- Screenshots at 1440×900 and 1280×800, checked against the rules at the top.
*Done when:* all of the above pass; this closes Plan Step 14.

## Later stages

### Open replay (Plan Step 16)
- An "Open in replay" button to the right of the scrubber's time, and the `O` key.
- Enabled when `GET /api/replay/status` (checked every 5 s while the tab is visible) says this game's replay is open in the client. Otherwise it's disabled with the reason as a tooltip: "Open this game's replay in the League client", or "Replays only exist for the current patch".
- Clicking it jumps the replay to 5 s before `t`, so you see the lead-up.

### Stage 2: missed windows
- Missed windows appear in the Moments list as rows with a **Miss** badge (`--warn` outline and text), a time range ("12:31–13:02"), a title ("Enemy Lee Sin dead, Dragon up") and a value ("worth ~+7%").
- The filter becomes **All · Graded · Missed · Mine**.
- On the graph, each window is a light `--surface-2` band behind the line; missed ones get a 2 px `--warn` tick at the top edge.
- Detail: why the window opened ("Lee Sin dead for 0:31, 2 enemies bot side"), what was available (Dragon, topside camps), what your team did ("recalled"), and the model's value for each option.
- Windows your team used aren't listed as Miss; what you took shows up as a normal moment.

### Stage 3: best plays
In a moment's or window's detail:
```
 What teams did here                                     seen
 1  Take Dragon       ██████████████   +7%              4,120
 2  Invade topside    ████              +4%                610
 –  Recall (you)                         0%              9,880
```
- Bars grow from a zero line: `--ally` when positive, `--enemy` when negative; each is labelled with its value; "seen" is in `--text-3`.
- Plays seen fewer than 200 times are hidden behind "Show rare plays".
- A footnote that is always shown: "Teams that did this here won this much more often. That doesn't prove it was the right move: vision isn't in the data."

### Stage 4: enemy camps
- The minimap gets its first toolbar: a **Camps** toggle.
- Camps are 8 px dots at their spots: filled = probably up, hollow = probably taken, opacity = how sure. Enemy camps only by default.
- Window details can say "Enemy topside camps likely empty (taken ~1:10 ago)".

### Stage 5: positions from replays
- When a game has positions from the replay, the minimap uses them (one per second) and icons move smoothly between seconds. A label above the map says where positions came from: "Replay, every 1 s" or "Timeline, every 60 s".
- The Games page marks games that have them.

## Not planned (keeps it simple)

- Accounts, logins or public sharing (a personal key is for private use).
- A light theme (the tokens make it one block of CSS later).
- A real mobile layout (under 1024 px the page just stacks).
- A settings page: grade thresholds live in `config.toml`.
- Trends across many games or champion stats (could be a later page).
- Anything live in-game (Riot's policy).
