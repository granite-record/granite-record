# A ward's own page picks its own ward's districts

On a ward's page (`/town/manchester-ward-5`), switching the map to another kind
of district chose Ward 1's district: `pickTown` took the reader's saved town,
or else the city's first ward, never the page's own. It now prefers the page's
ward (`opts.ward`) when the town is the page's own (`opts.frame`); elsewhere
it is unchanged. Found by the polish/guides-map review, 30 October 2026; dev
had it before that branch.

Measured on the preview's Manchester Ward 5, switching Senate, State House,
US House:

| | dev (2273166) | this branch |
|---|---|---|
| State House | HI21 (Ward 1's) | HI25 (Ward 5's) |
| State Senate | 16 (Ward 1's) | 18 (Ward 5's) |
| US House | 1 | 1 |

`ward5-senate-<before|after>-<390|1280>-<light|dark>.png`: the map on State
Senate after the switch.
