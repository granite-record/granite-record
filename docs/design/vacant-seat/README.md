# An empty seat on the Officials page

The owner asked, through the manager session on 5 November 2026, for this
change, for 24 November. A Strafford County commissioner resigned mid-term.
A record in `corrections/officials.json` with an empty name drew nothing, so
the County Officials tab would have shown two commissioners and said nothing
of the third.

## The record

The office's record keeps its name empty and says, under `vacant`, the day
the seat fell empty and the page that says so:

```json
"2": {
  "name": "",
  "office": "County Commissioner, District 2",
  "district": "2",
  "party": "",
  "vacant": {"since": "YYYY-MM-DD", "source": "https://...", "read": "YYYY-MM-DD"},
  "elect": {"name": "...", "party": "...", "source": "https://...", "takes_office": "YYYY-MM-DD"}
}
```

`elect` is optional and works as it does for any other record. On its
`takes_office` day, `build_members_elect.officials_on` makes the successor
the holder, and a record with a name is never drawn as vacant.

## What the page draws

The row has:

- a dashed box reading **Vacant**, the same dashed outline the seat chart
  uses for a vacant seat. It sits where a chip would, but it is not one:
  the chip is a person's, and preflight holds every chip to that;
- the seat;
- *Vacant since {day}.*;
- *Source:* and the source's host, linked;
- the successor's line, where the record names one. It shows the party for
  a commissioner but not for a sheriff, county attorney, treasurer or
  register, which are drawn with no party.

No name is drawn for an empty seat. Who left it is the source's to say.

A vacancy with no `source`, or with a `since` that is not a YYYY-MM-DD day,
stops the build. A record with no name and no `vacant` still draws nothing,
as before.

Spanish: `off.vacant` is "Vacante" and `off.vacant_since` is "Vacante desde
el {day}.". Both are marked draft.

The check is `_officials_vacant_seat`.

## Shots

Made-up names and a made-up source, drawn with this branch's `app.css`:

- `v-strafford-en-1280-light.png`
- `v-strafford-en-390-dark.png`
- `v-strafford-es-390-light.png`
