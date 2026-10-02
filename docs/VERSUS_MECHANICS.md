# Placement-based versus foundation

This is an own-board simulator, with no opponent, reward or training algorithm.
`Game` owns resolution; `versus.py` owns immutable facts and pure attack arithmetic.
It implements a documented subset of current TETR.IO Tetra League mechanics,
not a full timed match or replay-compatible TETR.IO engine.

## Evidence and target

Research retrieved the [official client](https://tetr.io/js/tetrio.js) on
2026-10-02. Its current engine version constant is `19`. The SHA-256 of the
retrieved file is
`B310AAF13AC0D7EE73C87C58ABCDEC87E1267217E182C10F4C9CB40DC5D73C92`.
The local research copy is ignored at `artifacts/rules/tetrio.js`; it is not a
distributed dependency. These fingerprints and the function names below permit
repeating the inspection without treating tests as external evidence.

The client's `tetra league` preset selects All-Mini+, multiplier combos,
DOWN rounding, B2B charging, All Clear garbage 5, All Clear B2B 1, garbage
special bonus enabled, combo blocking, garbage cap 8, and opener phase 14.
The [official patch notes](https://tetr.io/about/patchnotes/) establish the
Season 2 change on 2024-08-16 (Beta 1.2.0), garbage-clear bonus on 2024-09-22
(Beta 1.3.0), and immobile T Mini fallback on 2025-01-18 (Beta 1.5.0).

| Client inspection selector | Confirmed behavior | Local compatibility coverage |
| --- | --- | --- |
| `garbage:{SINGLE`, `AnnounceLines`, `AnnounceClear` | Base table, combo minimum, B2B and additive AC | `tests/test_versus.py` attack/counter fixtures |
| `ne=function(e)`, `IsTSpin:function` | T corners, kick upgrade, immobile fallback | `tests/test_versus.py` Spin boundaries |
| `_InternalRotate`, `Fall`, `Harddrop` | Rotation-time classification and invalidation | `tests/test_versus.py` rotation/drop fixtures |
| `FightLines:function`, `TakeAllDamage:function` | FIFO cancellation and ready garbage processing | `tests/test_versus.py` cancellation/insertion fixtures |
| `"tetra league":"options.presets` | Current target options, cap eight | `tests/test_versus.py` cap and clear-blocking fixtures |

These are stable textual selectors in the fingerprinted artifact, not source
line numbers in an unformatted/minified client. Test outcomes verify the local
implementation; the artifact establishes external rule evidence.

## Attack and counters

Client garbage constants and `AnnounceLines` select these base attacks:

| Lines | Ordinary | Full Spin | Mini, any piece |
| --- | --- | --- | --- |
| 0 | 0 | 0 | 0 |
| 1 | 0 | 2 | 0 |
| 2 | 1 | 4 | 1 |
| 3 | 2 | 6 | 2 |
| 4 | 4 | 10 | 4 |

Full Spins are available only for T in this profile. Impossible combinations
in the pure arithmetic table do not create new reachable placements.
The patch-note phrase that All-Minis do not send describes their lack of full
Spin power; the current client still selects Mini Double/Triple/Quad values.

Local combo and B2B counters use `-1` before the first qualifying event; the
client uses internal zero and displays internal count minus one. Any clear
increments combo; no clear resets combo. Quad or Spin clears increment B2B;
ordinary clears reset it; no clear preserves it. An All Clear adds one B2B
increment, plus the difficult-clear increment if applicable. Thus an ordinary
All Clear adds one and a Quad/Spin All Clear adds two. This follows
`AnnounceLines`, `allclear_b2b=1`, and the default `allclear_b2b_dupes=true`;
older secondary descriptions saying every All Clear adds two are insufficient.

A qualifying continuation receives +1 base attack once the resulting displayed
B2B is at least one. Ordinary All Clears do not receive this attack increment
(`allclear_b2b_sends=false`). For displayed combo `c`, multiply the resulting
base by `1 + 0.25*c`. At `c >= 2`, take the maximum of that result and
`ln(1 + 1.25*c)`, including when base is positive, then round down.
`AnnounceClear` separately adds five All Clear attack, outside combo multiplication.
Quad or Spin clearing at least one garbage row adds a flat one after rounding.

B2B charge begins at displayed count four and stores that count as Surge.
Breaking a charged chain releases that amount without combo multiplication.
The engine reports aggregate Surge attack. The client emits three packets and
resolves each separately; packet timing/segmentation is intentionally omitted.
The aggregate preserves cancellation totals with the local ordinary 1:1 rule.

## Spin history and reachable placements

All-Mini+ uses T three-corner/two-front-corner classification and otherwise
immobility (all four one-cell translations blocked) for Mini Spins. Successful
rotation history matters; mere final geometry cannot confer a Spin. Failed
actions preserve history. Successful horizontal/soft-drop movement clears it.
Hard drop preserves rotation history, including positive descent.

The current client's `IsTSpin` helper upgrades a T Mini on kick index three
excluding the initial unshifted test. In this engine's combined table that is
index four. The client applies this without a special exclusion for 180 turns.
Geometry/kick-table parity as a whole remains TO VERIFY.

The client classifies Spin flags at rotation time and preserves them through
hard drop. The engine stores that classification in immutable rotation history
and reuses it at lock. Placement metadata includes rotation history and distinct
Spin classifications may produce distinct actions for the same occupied cells. Enumeration
includes immediate hard-drop outcomes from rotation witnesses. The full snapshot
membership guard remains authoritative.

## Garbage and deterministic state

Immutable Board rows retain existing authoritative cell tuples, with a
`GarbageCell` enum sentinel for inserted garbage. Only cells marked as garbage
contribute to garbage-cleared facts. Clearing a
mixed row counts one garbage line, with no reward attached.

Incoming `GarbageEvent` values contain explicit hole columns and readiness.
All pending rows can be cancelled in FIFO order, even before readiness, as
confirmed by `FightLines` iterating pending damage without an active/status
guard. Partial cancellation keeps the remaining suffix. Attack in excess of
pending damage is outgoing attack. The local rule is ordinary 1:1 cancellation.

On a no-clear lock, ready events enter up to eight rows, in event order; unready
events remain pending. Any clear stalls insertion (client combo blocking).
Explicit readiness replaces the client's clock/status system. Hole columns are
supplied rather than generated by an opponent/scenario generator. Queue capacity
256, visible-board overflow top-out and fixed visible storage are project-specific.
No hidden rows, gravity, margin-time multiplier or Clutch Clear is added.

Board garbage, pending events, combo, B2B and rotation history participate in
snapshot, clone and simulation state. Immutable values may be shared; mutable
randomizer/queue state remains copied. The environment exposes factual clear
events and numerical own-state through contract v2. Neural adapters migrate
mechanically; no learned objective is defined here.

## Intentionally omitted compatibility

Opener double cancellation is confirmed to exist, but omitted: its lifetime,
sent-statistics accounting and interactions with separate attack packets require
a later timed-match boundary. Clutch Clear, hidden-buffer top-out, garbage travel,
activation clocks, dynamic multipliers, Surge packet generation, alternate room
profiles and opponent/network mechanics are outside this foundation. Therefore
do not use these results as exact predictions of a full Tetra League match.

Compatibility fixtures live in `tests/test_versus.py`; engine, environment,
simulation and neural tests cover local invariants independently of the evidence.
