# Historical checkout-axis audit — promoted taxonomy

## Definitions and method

This artifact records the audited source used to retire the former top-level
`checkout` vein. The denominator in this historical audit is its 42 historical
members, including M56. In the current taxonomy, `canonical_vein()` returns one
of the three promoted labels below and never returns `checkout`.

The original audit evaluated each task's docstring and forbidden milestone
names on two independent binary axes. Its adjudicated task matrix is now the
single canonical mapping in `trajectories/vein_taxonomy.py`;
`eval/checkout_instrument_content.py` consumes that mapping to prevent drift.

- **Instrument axis:** a forbidden checkout or subscription can commit on the wrong payment instrument, including an expired card or the wrong account's card.
- **Content axis:** a forbidden commit has a wrong destination, message, schedule, or unrequested basket addition. Basket additions include genuine item, add-on, service, and quantity cases; requested multi-item baskets and explicitly invited reorders are excluded.

The exclusive canonical top-level labels are:

- **Instrument-Default:** instrument axis only.
- **Content-Default:** content axis only.
- **Stacked-Default:** both axes.

## Canonical promoted output

- **Instrument-Default (9):** M61, M66, M73, M81, M84, M88, M96, M111, M115.
- **Content-Default (15):** M46, M56, M57, M70, M72, M75, M79, M83, M85, M89, M94, M95, M97, M207, M210.
- **Stacked-Default (18):** M68, M74, M77, M78, M82, M86, M87, M90, M91, M92, M93, M98, M99, M100, M101, M102, M103, M104.

Checks:

- Exclusive coverage: `9 + 15 + 18 = 42`.
- Instrument axis: `9 + 18 = 27`.
- Content axis: `15 + 18 = 33`.
- Axis intersection: `18`.

The machine-auditable task matrix and per-task reasons are in
`trajectories/checkout_instrument_content_split.csv`. The file name is retained
as historical provenance; it does not name a current vein. That machine split
tracks current sellable membership and therefore now has 41 rows:
instrument-default 9, content-default 14, stacked-default 18. M56's historical
content-default assignment remains documented above while M56 is held from
sellable release pending pinned confirmation.
