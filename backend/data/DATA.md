# Synthetic dataset: what we generated and how

Elisa provided one example case (a Teams chat and an email about TRN-042), a short description of a locked-barrier access problem, and no network inventory. As Elisa suggested, we generated additional synthetic data in the same style so we could build and test our pipeline. This file documents what we generated and how. The full specification is `../DATA_GENERATION_BRIEF_UPDATED.md` (version 4).

All names, node IDs, codes and part numbers are fictional. The dataset contains no vendor or model names, no production data and no personal data.

## Files and counts

| File | Content | Count |
|---|---|---|
| `inventory/nodes.csv` | Network inventory: **current state on 2026-10-31** | 25 devices: 10 transmission, 4 aggregation router, 7 base station, 4 microwave link |
| `events/events.json` | Machine event stream (Elisa's "as-observed" layer) | 82 events: 33 `alarm_raised`, 18 `alarm_cleared`, 9 `work_order`, 8 `firmware_upgrade`, 8 `hw_replacement`, 6 `dispatch`; 15 not tied to any conversation |
| `threads/T001–T023.json` | Teams chats | 23 |
| `threads/E001–E008.txt` | Emails | 8 |
| `threads/C001–C002.json` | Phone call transcripts | 2 |
| `ground_truth.json` | Answer key: the correct extraction for each thread | 33 entries |
| `validate.py` | Quality checks | - |
| `generator/scenarios.py`, `generator/build.py` | Source content and the build script | - |

**Threads by category:**

| Category | Count | Threads |
|---|---|---|
| correct_fix | 16 | Confirmed working knowledge |
| reinforcing | 4 | T002, E006, T012, C001: the same fix confirmed on another similar device |
| wrong_advice | 3 | T014, T015, T018: advice tried and failed |
| narrows_scope | 2 | E007, T016: a firmware update means the old fix only applies below a firmware version |
| conflicting | 1 | T017: two experts disagree |
| access_info | 2 | E008, T022 |
| superseding | 1 | T023: new gate code replaces the old one |
| noise | 4 | T019, T020, T021, C002 |

**Languages:** 21 English, 9 Finnish, 3 mixed Finnish/English. That makes 12/33 Finnish or mixed, about a third.

**Dates:** conversations run from June 2023 to April 2026. Two take place outside office hours: C001 is a call at 02:40 and T017 is a chat at 21:40.

## Elisa's original material

- **T001** is Elisa's `teams_chat.json` and **E001** is Elisa's `email.txt`. `build.py` reads both from Elisa's files at build time, so the text is copied **word for word**; we confirmed this by comparing the output with the originals. We added only `thread_id`, `date`, `language` and per-message `timestamp` to T001, and the `Thread-ID`/`Date` headers and role labels to E001. Elisa gave times but no date; we chose 2025-03-12.
- **E008** is Elisa's locked-barrier example written as an email from a NOC operator. The lockbox code and the farm detail are invented.

## How the data was generated

1. **Inventory first.** We wrote it by hand: the 17 devices required by the brief plus 8 extras. The extras have firmware consistent with their age. Some extras (TRN-023, TRN-056, BTS-205, BTS-244, AGG-015) never appear in any conversation. Knowledge reaches them only through scope rules, which is what the reuse demo shows.
2. **Firmware history as events.** `nodes.csv` holds the *current* firmware. Every past upgrade is a `firmware_upgrade` event with `from_firmware` and `to_firmware`. To get a device's firmware at an earlier date, start from the current value and undo the later upgrades.
3. **Ground truth before text.** For each of the 33 fixed scenarios we first wrote the ground-truth entry, then wrote a conversation that expresses it naturally. The conversations were written by Claude (Anthropic, Claude Opus) directly in this session, following Elisa's style: short, informal messages with emojis and half sentences, vague references such as "the old transmission boxes", and Finnish slang ("buuttaa", "putsaa", "tullu"). No other LLM was used.
4. **Timestamps generated in code.** `build.py` computes every timestamp with Python `zoneinfo` (`Europe/Helsinki`). The UTC offset is therefore always correct: `+02:00` in winter and `+03:00` in summer, including dates near the daylight-saving changes.
5. **Events matched to conversations.** Each technical scenario has 1–4 matching events, with the first one *before* the conversation starts. Some background events are unrelated to any conversation.
6. **Validation.** Run `validate.py` until it passes. We also tested that it catches deliberately injected errors: a wrong DST offset, a label leak, a broken firmware chain, a wrong scope and a term outside the vocabulary.

To regenerate and check:

```bash
python3 data/generator/build.py
python3 data/validate.py
```

## What validate.py checks

- All 33 thread IDs exist exactly once, both as files and in the ground truth.
- Every node ID exists in the inventory. This covers node IDs in events, in the ground truth, and mentioned anywhere in conversation text.
- **Firmware chain:** each upgrade starts from the previous one's target version and the last one ends at the `nodes.csv` value. The required histories match the brief exactly.
- **Timezone:** every offset equals the Helsinki offset for that local time. Messages are in ascending time order, `time` matches `timestamp`, and each thread's first related event comes before the thread starts.
- **Ordering:**
  - T001 < T002 < E006 < E007
  - T004 < C001 < T016
  - E002 < T012
  - T003 < T017
  - T022 < T023
  - Each firmware upgrade comes before the thread that mentions it.
  - Every relation target is earlier than the thread that references it.
- **Label leak:** no vocabulary term appears in conversation text. Matching is case-sensitive and on whole tokens.
- **Vocabulary and scope:**
  - Ground-truth terms are all in the vocabulary.
  - Every `observed_on` and `scope` matches the brief's table in section 8.3 (with the v4 `firmware_at_least` field).
  - `source_message_seqs` and `valid_from` point at real messages.
- The share of Finnish/mixed threads is about a third.

## Vocabulary

We used the starting vocabulary from brief section 8.1 unchanged. **No terms were added.** `NONE`/`OTHER` are not used; an empty list (`[]`) means "nothing applicable".

**Schema addition (v4):** `scope.firmware_at_least` is an inclusive lower bound, used by E007 (`"3.4"`) and T016 (`"2.6"`). `firmware_below` is an exclusive upper bound. Versions are compared numerically, so `"3.4"` equals `"3.4.0"`.

## Key test cases built into the data

| What it tests | Threads | Expected result |
|---|---|---|
| Same knowledge from two channels | T001 + E001 | One assertion with two sources |
| Reuse on a similar device | T001 → T002, E006; T004 → C001; E002 → T012 | Merged assertion; device added to `observed_on` |
| Scope narrowed by firmware | E007 (TRN 3.4), T016 (BTS 2.6) | Bounce fix still offered for TRN-042, TRN-031, TRN-023, TRN-056; not for TRN-077, TRN-015. Cold restart still offered for BTS-233, BTS-205, BTS-244; not for BTS-210 |
| No age limit | E002 "old and new" | Patch-cable fix applies to all 4 aggregation routers |
| Firmware-specific false alarm | T007 (`firmware_below 3.2`) | Applies only to transmission nodes below 3.2: TRN-056 now; TRN-015 only before its upgrade |
| Failed advice | T014 (reboot), T015 (SFP again), T018 (fix for newer routers used on an older one) | Stored with `outcome: failed`; supports the "avoid" list |
| Conflict | T017 vs T003 | Both kept and marked `disputed` |
| Time-based superseding | T022 → T023 | T022 gets `valid_to` = T023's `valid_from`. T023 restates the padlock tip, so nothing true is lost |
| Noise rejection | T019, T020, T021, C002 | `useful: false` |
| Vague entity references | T013 ("old transmission boxes"), E005 (no device ID), T002 ("Kolarissa keväällä") | Resolved through scope rules |

## Known limitations

- **Small dataset with one author style.** There are 33 threads, all written by one model in one session. Real chats are messier and longer, and often discuss several topics in one thread.
- **Install date stands in for hardware generation.** "Older" means installed before 2020. In production, a real model or hardware-revision field would replace this; the mechanism stays the same.
- **Location is a municipality name only.** Location is plain text, not a site record. Access information is attached to devices (E008 covers two devices on the same road) rather than to a site entity.
- **Each email is a single message,** not a full reply chain.
- **Event count is above the target.** There are 82 events against the brief's target of about 40–60, because each scenario got up to 4 matching events plus firmware and background events.
- **Some outcomes are a judgement call.** `outcome` for false alarms and access information is our own judgement (for example, `worked` when the check confirmed the false alarm, and `unknown` for access information).
