# Slice 36: link cards that say what they decide

Planned 2026-09-23 with the owner, after reviewing the 67 `relink` cards from the first
`suggest_links` pass. Fast mode: one card, one list, one label.
**Built and verified 2026-09-23 (Proof, below).**

## What was reported

- Some approvals "did not happen": the card left and the count stayed. Two causes, both found
  and reproduced: **"Not now" moves a card to the end and sends nothing**, which reads as a
  rejection; and **cards jump under the pointer** -- an approved card is removed at once and the
  list refetches, so a quick next click lands on the next card's space picker or text (in a test,
  a click 250ms after the first hit a `SELECT` once and the next card's text once).
- The owner, in their words: "how do I reject or cancel the proposal, it's not like filing ...
  it's a link suggest." Rejecting took tapping every chip off and then pressing Approve.
- A card for an item filed by hand (no stored proposal) said "Proposal rejected".

## Decided with the owner, 2026-09-23

1. **A card with proposed links decides links, and its buttons say so**: **Link** (**Link N**
   when N chips are on) keeps those chips; **No links** rejects every one in one tap, the item
   going back unchanged and the pairs never suggested again; **Later** replaces "Not now". The
   chips stay for choosing some and not others. For a `linked` item (not filed yet) the same
   buttons also file it.
2. **Later says what it did**: "Moved to the end".
3. **Clicks settle after a decision**: for half a second after a card leaves, the cards are not
   clickable, so a fast repeat does nothing instead of hitting the next card.
4. **The reason line checks why an item waits before whether it has a proposal**.

## Acceptance

1. A `relink` card shows Link / No links / Later; Link reads "Link 2" with two chips on and
   "Link 1" after one is tapped off; with none on, Link is gone and No links remains.
2. No links sends `links: []`; Link sends the chips still on.
3. Later moves the card to the end and says "Moved to the end"; nothing is sent.
4. A click 250ms after an approval, where the button was, sends nothing and opens nothing.
5. A `relink` item with no stored proposal says "Filed already: suggested links to check".

## Verification

`npm run ui` with the new checks (stubbed queue, as S33/S34); `tsc`; `pytest` unchanged; looked
at on 390px and desktop. Deploy as `v2.3` with the same backup and checks as `v2.2`.

## Proof (2026-09-23, local)

- `npm run ui`: **21/21**, one new: S36 against a stubbed queue that forgets what is approved, as
  the server does -- "Link 2", "Link 1" after one chip off, "No links" with none; the reason
  "Filed already"; Later moves the card to the end, says so, sends nothing; a click 250ms after an
  approval, where the button was, sends nothing and opens nothing; No links sends `links: []`.
  **Shown to fail without the settle**: the quick second click then *approved the next card*, a
  decision the owner never made -- worse than the lost click reported. `tsc` clean.
- `pytest`: 370 passed, 9 deselected (no backend change).
- Looked at on 390px: LINK 2 / NO LINKS / LATER under "Filed already: suggested links to check".
