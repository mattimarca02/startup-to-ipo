# Sound plan (design only)

Owner decision D8 (2026-10-06): **sound at launch**, all through one `SoundConfig`; a slot with asset id 0 plays nothing, so the game is complete before any asset exists. Design only; nothing changed in the game. The owner supplies every asset (section 5); no id is named here because none could be verified. Context: docs/GAMEPLAY_FIRST_HOUR_PROPOSAL.md section 5. **(unverified)** = from memory, not checked.

## 1. Slots

Volume (0 to 1) is multiplied by the master and the player's volume; priority 5 matters most; cooldown = the shortest time between two plays (the rate limit). Every slot starts with id 0; only `Music` loops.

| Slot key | Event (who decides it) | Mood | Max s | Volume | Prio | Cooldown s |
|---|---|---|---|---|---|---|
| `UiClick` | any button tap (client) | soft tick | 0.15 | 0.3 | 1 | 0.08 |
| `WindowOpen`, `WindowClose` | a window opens, closes (`OpenPanel`) | light swish up, down | 0.3 | 0.3 | 1 | 0.25 |
| `Buy` | the server confirms a purchase (upgrade, egg, desk, HR level) | bright register | 0.6 | 0.5 | 3 | 0.15 |
| `BuyRefused` | the server refuses one | soft low bonk, never harsh | 0.3 | 0.35 | 2 | 0.5 |
| `Hire` | an employee starts work | friendly ding | 0.5 | 0.45 | 3 | 0.5 |
| `Hatch` | the reveal opens: **one sound for every egg and rarity** | shell crack, small pop | 0.8 | 0.5 | 4 | 1 |
| `CallRing` | a call arrives (server state) | soft desk phone, one trill | 1.0 | 0.4 | 3 | 3 |
| `CallAnswered` | the server grades an answer | pick-up click, coin tick | 0.4 | 0.45 | 3 | 0.2 |
| `CallMissed` | a call expires | short descending blip | 0.4 | 0.3 | 2 | 1 |
| `IncomeTick` | the Cash counter | barely audible, or nothing | 0.1 | 0.05 | 0 | 5 |
| `StageUp` | a milestone or funding stage | 3-4 note fanfare | 2.0 | 0.6 | 5 | 3 |
| `Ipo` | going public | one bell ring, small cheer | 3.0 | 0.7 | 5 | 10 |
| `RoundRaised` | a funding round raised | pen scratch, coins | 1.2 | 0.55 | 4 | 3 |
| `PoachWin` | a poach succeeds | short upbeat deal sting | 1.0 | 0.5 | 4 | 3 |
| `PoachLoss` | an own employee is poached | soft low note, calm | 1.0 | 0.4 | 4 | 3 |
| `DailyClaim` | the server confirms a claim | paper rustle, chime | 1.2 | 0.55 | 4 | 3 |
| `Music` (optional) | always, if the player turns it on | calm lo-fi office, no lyrics | 60-120 | 0.25 | 0 | none |

`IncomeTick` keeps id 0 even with an asset (a sound a second is noise). `Music` is **off by default** (proposal question 6).

## 2. `SoundConfig` design

A ModuleScript in ReplicatedStorage, like the other configs:

```lua
SoundConfig.Enabled = true            -- global mute for everyone (a kill switch)
SoundConfig.MasterVolume = 0.5        -- 0 to 1
SoundConfig.MaxSimultaneous = 4       -- effects playing at once (music not counted)
SoundConfig.MusicOnByDefault = false
SoundConfig.Slots = {
    Buy = { id = 0, volume = 0.5, maxSeconds = 0.6, loop = false, priority = 3, cooldown = 0.15 },
    -- one row per slot of section 1
}
```

**Who plays sounds.** Only a new client, `SoundClient` (StarterPlayerScripts): it owns every `Sound` (one per slot, in `SoundGroup`s Effects and Music) and a BindableEvent other clients fire with a slot key only. Ids and volumes live in `SoundConfig` only.

**Never the server.** No server script creates or plays a sound, so nothing can make other players hear anything; every sound is local.

**Only after the server agrees.** A success sound waits for the server's answer (`ShopNotify`, a remote reply, `TaskState`): a tap plays `UiClick`, a refusal `BuyRefused` only. Client-only moments (a window, the reveal of a hatch the server decided) play directly.

**Rate limit and cap.** A slot inside its cooldown is skipped, not queued, so spammed taps never stack. Above `MaxSimultaneous` a new sound replaces the oldest lower-priority one, else it is skipped. Each stops at `maxSeconds`.

**Player settings.** A "Sounds" switch and a "Music" switch (where they sit is the UI PR's choice; no settings screen exists today). First version: per session only (no save). Keeping them across sessions needs a new top-level save section (rule A10), a later PR.

**D9.** No sound suggests chance or a prize for anything sold with Robux: no reel, spinner, drumroll or rising suspense on eggs, Luck Boost or Instant Hatch; one `Hatch` sound for every rarity (a louder Legendary would reward the roll); nothing when a Robux prompt opens, and only the ordinary `Buy` when an item is granted; no ticking countdowns; no keys or descriptions with lucky, jackpot, spin or chance.

## 3. Phone

- Short: effects under 1 s except `StageUp`, `Ipo`, `RoundRaised`, `DailyClaim`.
- Mono, small: effects under about 100 KB, music one loop under 2 minutes (targets; Roblox's compression unverified).
- Preload effects once after joining (`ContentProvider:PreloadAsync`); music only when switched on.
- Thin phone speakers: `PoachLoss` and `BuyRefused` must be audible without bass.
- Sounds parented to `SoundService` or the player's GUI play without a position (verify in Studio).
- **Backgrounded app:** whether Roblox mutes a game when the phone app is in the background is **unverified**; don't rely on it, and never replay events from while away (the welcome-back card is silent).
- Roblox's menu volume should cover every game sound (unverified).

## 4. Silent and failed sounds

- **id 0:** `SoundClient` creates no `Sound` for that slot; playing it does nothing, with no warning (it is the normal state).
- **Fails to load** (moderated, private, deleted, network): one `warn` naming the slot, then the slot is silent for the session. **No retry loop**; a rejoin tries again. Nothing waits for a sound.
- **Config errors** (a volume outside 0 to 1, an unknown key): one warning at startup, like the other configs; an unknown key plays nothing.

## 5. Assets: what the owner supplies

### 5.1 Shopping list (Creator Store, Audio)

Search the Creator Store's audio (Studio Toolbox, Audio, or the website); one creator or pack keeps the style matching. Loudness by ear at one phone volume: "medium" = as loud as `Buy`; fine-tune with the slot volume.

| Slot | Search terms | Style; listen for | Length, loudness |
|---|---|---|---|
| `UiClick` | ui click, soft tap, button | dry, no echo; no "pop" at the end | < 0.15 s, quiet |
| `WindowOpen`, `WindowClose` | swoosh, ui whoosh, swipe | airy, short; the pair should match | 0.2-0.3 s, quiet |
| `Buy` | cash register, purchase, coin | cheerful but short; no casino sound | 0.3-0.6 s, medium |
| `BuyRefused` | error soft, denied, bonk | gentle, not a buzzer; no blame | < 0.3 s, quiet |
| `Hire` | ding, notification, bell small | warm, single note | < 0.5 s, medium |
| `Hatch` | egg crack, shell break, pop | crack then pop, no build-up | < 0.8 s, medium |
| `CallRing` | phone ring, desk phone, office phone | one short trill, not an alarm | < 1 s, medium-quiet |
| `CallAnswered` | phone pickup, click, coin | quick and satisfying | < 0.4 s, medium |
| `CallMissed` | blip down, fail soft | short, not sad music | < 0.4 s, quiet |
| `IncomeTick` | tick, coin tiny | almost silent; may stay empty | < 0.1 s, very quiet |
| `StageUp` | level up, fanfare short, success | bright, 3-4 notes, ends cleanly | 1-2 s, medium-loud |
| `Ipo` | bell ring, stock market bell, celebration | one clear bell, short cheer | 2-3 s, loud |
| `RoundRaised` | pen writing, signature, coins | paper and coins, no music | about 1 s, medium |
| `PoachWin` | success sting, deal, short jingle | upbeat, never mocking | < 1 s, medium |
| `PoachLoss` | soft negative, low tone | calm, never scary | < 1 s, quiet |
| `DailyClaim` | gift open, paper unwrap, chime | friendly rustle and chime | about 1 s, medium |
| `Music` | lo-fi, office, calm loop | no lyrics, loops without a gap, no sudden peaks | 1-2 min, quiet |

Listen for clicks at the start or end, silence before the sound (it feels late), and anything like slot machines or prize reels (D9).

### 5.2 Record what you pick

| Slot | Asset id | Name | Creator | Length | License note |
|---|---|---|---|---|---|
| `Buy` | | | | | |

One row per slot; "License note" = why you may use it (Roblox-provided, your upload, or its page's terms). Put an id in `SoundConfig` only after the checks below.

### 5.3 Checks in Creator Hub (all unverified)

- **Can your experience use it?** Your understanding: since 2022, audio by other creators is private unless Roblox provided it or you own it. **Unverified** (my recollection, also unverified: the 2022 change treated sounds over 6 seconds differently from short effects). For each id, read its Creator Store page (creator, any "use in experiences" setting), then play it in a Studio playtest and in the published game: a blocked sound fails to load and Output says so.
- **If the game belongs to a group**, audio may need to be owned by that group, not by you personally (unverified).
- **Uploading your own:** Creator Hub, Creations, upload audio. Formats, length limit, monthly allowance, fee and moderation time are **unverified**: read the upload page on the day. Upload only sounds you made or have rights to (moderation can act on your account, unverified).
- **Age and content rules:** audio follows Roblox's Community Standards: no copyrighted music without rights, no mature lyrics, nothing meant to scare young players; re-check the questionnaire if music with lyrics is added (details unverified).

## 6. Tests for the build PR

In `tools/daily_test.py`, with the real `SoundConfig` and `SoundClient` logic and a fake `Sound`:

1. **Ids only from `SoundConfig`:** no `rbxassetid` literal in another `.lua`; every fired key exists in `SoundConfig.Slots`.
2. **Bounds:** every volume and `MasterVolume` in 0 to 1; `IncomeTick` at most 0.1; `maxSeconds` above 0; cooldowns at least 0; only `Music` loops; `MaxSimultaneous` between 1 and 8.
3. **id 0 is silent:** no `Sound` is created and firing the slot plays nothing, with no warning.
4. **Failed load:** one warning, the slot goes quiet, no second load attempt in the session.
5. **Rate limit:** firing `Buy` 20 times in one second plays it at most 7 times (1 s ÷ 0.15 s, plus the first).
6. **Cap:** with 4 playing, a higher-priority fifth replaces the oldest lower one; an equal or lower one is skipped.
7. **Purchases:** a refused purchase plays `BuyRefused` only; a confirmed one plays `Buy` only; a tap alone plays `UiClick` only.
8. **Server silent:** no server script requires `SoundConfig` or creates a `Sound`.
9. **D9:** no slot key or description contains luck, lucky, chance, odds, jackpot, prize, spin, reel or roll; the `Hatch` slot is the same for every rarity; nothing fires on `PromptProductPurchaseFinished` or `PromptGamePassPurchaseFinished`.
10. **Muted:** with `Enabled = false` or the player's switch off, nothing plays and nothing loads.

## 7. Not verified

Roblox's audio privacy and permission rules, upload formats, limits, fees and moderation times; muting of a backgrounded phone app; compression and file sizes on phones; `PreloadAsync` on phones; whether the menu volume covers every sound; where unparented sounds play. No Creator Store search was made; no asset id is given.
