# For the owner to paste: `same_person`, 2 November 2026

Your answers to the 31 pairs in `CANDIDATES.md`, as the section that
`corrections/member_corrections.json` takes. The rows are numbered as there.
Thirty are the same person. Row 31, David Pierce of Hillsborough 6 (House
2015-2018, R), is a different person from Sen. David Pierce of SD 5, and is
marked so, so that nothing joins them later. Row 23, the David Pierce of
Grafton 9 (House 2007-2012), is the senator: House 2006-2012, then SD 5
2012-2016, as you gave his career.

**How to paste:** in `corrections/member_corrections.json`, add the key below
at the top level, beside `"members"`, `"ballots"` and `"spellings"`, with a
comma after the entry before it. The build reads only entries whose
`confirmed` begins with a date. `"no, two people"` is kept as the record of
the answer.

```json
"same_person": [
  {
    "house": "374827",
    "senate": "36",
    "name": "Bradley, Jeb",
    "row": 1,
    "evidence": "House Carr 8 1999-2002; Senate SD 3 2009-2024; party R -> R",
    "confirmed": "2026-11-02, owner"
  },
  {
    "house": "376311",
    "senate": "209062",
    "name": "Bragdon, Peter",
    "row": 2,
    "evidence": "House Hills 13 2001-2002; Senate SD 11 2005-2014; party R -> R",
    "confirmed": "2026-11-02, owner"
  },
  {
    "house": "373134",
    "senate": "209059",
    "name": "Burling, Peter",
    "row": 3,
    "evidence": "House Sull 19 1999-2004; Senate SD 5 2005-2008; party D -> D",
    "confirmed": "2026-11-02, owner"
  },
  {
    "house": "376444",
    "senate": "45",
    "name": "Cataldo, Sam",
    "row": 4,
    "evidence": "House Straf 3 2003-2012; Senate SD 6 2013-2016; party R -> R",
    "confirmed": "2026-11-02, owner"
  },
  {
    "house": "376564",
    "senate": "209071",
    "name": "Cilley, Jacalyn",
    "row": 5,
    "evidence": "House Straf 4 2005-2018; Senate SD 6 2007-2010; party D -> D",
    "confirmed": "2026-11-02, owner"
  },
  {
    "house": "375976",
    "senate": "209058",
    "name": "Clegg, Robert",
    "row": 6,
    "evidence": "House Hills 23 1999-2002; Senate SD 14 2003-2008; party R -> R",
    "confirmed": "2026-11-02, owner"
  },
  {
    "house": "376569",
    "senate": "209066",
    "name": "DeVries, Betsi",
    "row": 7,
    "evidence": "House Hills 15 2005-2006; Senate SD 18 2007-2010; party D -> D",
    "confirmed": "2026-11-02, owner"
  },
  {
    "house": "376666",
    "senate": "209072",
    "name": "Denley, William",
    "row": 8,
    "evidence": "House Carr 5 2007-2008; Senate SD 3 2009-2009; party R -> R",
    "confirmed": "2026-11-02, owner"
  },
  {
    "house": "376117",
    "senate": "209056",
    "name": "Estabrook, Iris",
    "row": 9,
    "evidence": "House Straf 8 1999-2002; Senate SD 21 2003-2008; party D -> D",
    "confirmed": "2026-11-02, owner"
  },
  {
    "house": "376291",
    "senate": "209048",
    "name": "Gallus, John",
    "row": 10,
    "evidence": "House Coos 7 1999-2002; Senate SD 1 2003-2012; party R -> R",
    "confirmed": "2026-11-02, owner"
  },
  {
    "house": "7369",
    "senate": "205010",
    "name": "Gordon, Edward",
    "row": 11,
    "evidence": "House Grafton 9 2019-2022; Senate SD 2 1999-2002; party R -> R",
    "confirmed": "2026-11-02, owner"
  },
  {
    "house": "9949",
    "senate": "209082",
    "name": "Groen, Fenton",
    "row": 12,
    "evidence": "House Strafford 19 2021-2022; Senate SD 6 2011-2012; party R -> R",
    "confirmed": "2026-11-02, owner"
  },
  {
    "house": "376778",
    "senate": "209073",
    "name": "Houde, Matthew",
    "row": 13,
    "evidence": "House Sull 1 2007-2008; Senate SD 5 2009-2012; party D -> D",
    "confirmed": "2026-11-02, owner"
  },
  {
    "house": "376013",
    "senate": "209049",
    "name": "Kenney, Joseph",
    "row": 14,
    "evidence": "House Carr 6 1999-2002; Senate SD 3 2003-2008; party R -> R",
    "confirmed": "2026-11-02, owner"
  },
  {
    "house": "376486",
    "senate": "205005",
    "name": "King, Frederick",
    "row": 15,
    "evidence": "House Coos 1 2003-2008; Senate SD 1 1999-2000; party R -> R",
    "confirmed": "2026-11-02, owner"
  },
  {
    "house": "376241",
    "senate": "209075",
    "name": "Lasky, Bette",
    "row": 16,
    "evidence": "House Hills 26 1999-2008; Senate SD 13 2009-2018; party D -> D",
    "confirmed": "2026-11-02, owner"
  },
  {
    "house": "376142",
    "senate": "209060",
    "name": "Letourneau, Robert",
    "row": 17,
    "evidence": "House Rock 77 1999-2004; Senate SD 19 2005-2010; party R -> R",
    "confirmed": "2026-11-02, owner"
  },
  {
    "house": "376690",
    "senate": "9405",
    "name": "Levesque, Melanie",
    "row": 18,
    "evidence": "House Hills 26 2007-2014; Senate SD 12 2019-2020; party D -> D",
    "confirmed": "2026-11-02, owner"
  },
  {
    "house": "373902",
    "senate": "209077",
    "name": "Merrill, Amanda",
    "row": 19,
    "evidence": "House Straf 6 2013-2014; Senate SD 21 2009-2012; party D -> D",
    "confirmed": "2026-11-02, owner"
  },
  {
    "house": "375954",
    "senate": "209044",
    "name": "O'Hearn, Jane",
    "row": 20,
    "evidence": "House Hills 26 1999-2000; Senate SD 12 2001-2004; party R -> R",
    "confirmed": "2026-11-02, owner"
  },
  {
    "house": "376371",
    "senate": "209051",
    "name": "Odell, Bob",
    "row": 21,
    "evidence": "House Sull 5 2001-2002; Senate SD 8 2003-2014; party R -> R",
    "confirmed": "2026-11-02, owner"
  },
  {
    "house": "376157",
    "senate": "209052",
    "name": "Peterson, Andrew",
    "row": 22,
    "evidence": "House Hills 3 1999-2010; Senate SD 11 2003-2004; party R -> R",
    "confirmed": "2026-11-02, owner"
  },
  {
    "house": "376682",
    "senate": "44",
    "name": "Pierce, David",
    "row": 23,
    "evidence": "House Graf 9 2007-2012; Senate SD 5 2013-2016; party D -> D",
    "confirmed": "2026-11-02, owner"
  },
  {
    "house": "376737",
    "senate": "47",
    "name": "Reagan, John",
    "row": 24,
    "evidence": "House Rock 1 2007-2012; Senate SD 17 2013-2022; party R -> R",
    "confirmed": "2026-11-02, owner"
  },
  {
    "house": "455",
    "senate": "209055",
    "name": "Sapareto, Frank",
    "row": 25,
    "evidence": "House Rockingham 6 1999-2018; Senate SD 19 2003-2004; party R -> R",
    "confirmed": "2026-11-02, owner"
  },
  {
    "house": "376631",
    "senate": "41",
    "name": "Stiles, Nancy",
    "row": 26,
    "evidence": "House Rock 15 2005-2010; Senate SD 24 2011-2016; party R -> R",
    "confirmed": "2026-11-02, owner"
  },
  {
    "house": "375968",
    "senate": "37",
    "name": "Boutin, David",
    "row": 27,
    "evidence": "House Merr 9 2007-2010; Senate SD 16 2010-2016; party R -> R; years overlap, but no day both voted: a move within the year",
    "confirmed": "2026-11-02, owner"
  },
  {
    "house": "376100",
    "senate": "209042",
    "name": "Boyce, Robert",
    "row": 28,
    "evidence": "House Belk 5 1999-2000; Senate SD 4 2001-2006; party R -> R; Belknap is not a county of today's Senate district 4 (Strafford); districts were redrawn in 2002, 2012 and 2022",
    "confirmed": "2026-11-02, owner"
  },
  {
    "house": "376116",
    "senate": "209065",
    "name": "Downing, Michael",
    "row": 29,
    "evidence": "House Rock 26 1999-2002; Senate SD 22 2007-2010; party D -> R; party differs (D in the House, R in the Senate)",
    "confirmed": "2026-11-02, owner"
  },
  {
    "house": "371138",
    "senate": "202333",
    "name": "Fraser, Leo",
    "row": 30,
    "evidence": "House Merr 37 2001-2004; Senate SD 4 1999-2000; party R -> R; Merrimack is not a county of today's Senate district 4 (Strafford); districts were redrawn in 2002, 2012 and 2022",
    "confirmed": "2026-11-02, owner"
  },
  {
    "house": "862",
    "senate": "44",
    "name": "Pierce, David",
    "row": 31,
    "evidence": "House Hillsborough 6 2015-2018; Senate SD 5 2013-2016; party R -> D; BOTH VOTED ON THE SAME DAY: two people, or a mid-term move to check; party differs (R in the House, D in the Senate); Hillsborough is not a county of today's Senate district 5 (Grafton, Merrimack, Sullivan); districts were redrawn in 2002, 2012 and 2022",
    "confirmed": "no, two people"
  }
]
```
