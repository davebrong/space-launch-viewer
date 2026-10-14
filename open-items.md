# Open items

Ideas and deferred work to reassess later. Not committed scope.

## Space Launch Delta 45 hazard-notice PDFs as a backup hazard-area source

*Logged 2026-10-14 · Status: deferred*

**Idea:** Add Space Launch Delta 45's public launch hazard notices (PDFs) as a second hazard-area source next to USCG NAVCEN SOLAR (`services/api/adapters/navcen.py`). It is free and needs no key or registration.

**How it would work (programmatic, no AI):**
1. The worker checks the Space Launch Delta 45 notice page for new PDFs, within the shared request budget, robots and terms.
2. A pinned pure-Python library (pypdf or pdfminer.six) extracts the text; pattern matching reads the mission name, dates and coordinates (e.g. `28-35-12N 080-20-45W`).
3. A notice is associated with a launch by exact normalized mission name, plus a notice window that covers the launch date, as SOLAR is.
4. The coordinates become a bearing sector from the pad, shown as "Hazard area (not a flight path)" with a link to the PDF. Like SOLAR, it is used only to cross-check or narrow a published heading, never as a centerline.
5. All-or-nothing parsing: an unexpected layout means "unavailable", not a guess. Saved fixture PDFs and regression tests are required before admission.

**Hosting impact:** one more pinned library in the existing worker container; negligible load. Scanned (image-only) PDFs would need OCR, which is a large system package and unreliable for coordinates. Treat them as unsupported instead.

**Why deferred:**
- The notices cover areas close to shore and near the pad, so they barely narrow the departure direction. The equivalent near-pad SOLAR closures (`_rna`, `_sec`, `_spaceSec`) are already ignored for that reason.
- Its main value is as a backup if SOLAR's unstable `tmp/test.js` path disappears. The app would then show "Route source unavailable".
- PDF URLs are unpredictable.

**Before building:**
- Confirm the PDFs contain extractable text rather than scans.
- Confirm robots and terms allow automated retrieval.
- Collect a few real notices as fixtures.

**Revisit when:** SOLAR breaks or changes format, or a mission is seen with a near-pad notice but no SOLAR notice.

**Background:** `evidence/build/flight-plan-audit/STATUS.md` (source verdicts), issue #1.
