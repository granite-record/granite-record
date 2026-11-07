# The owner's thirty pairs, one person each in people.json (held for the owner's word)

The branch is `fix/movers-merge`, from dev `dd3f7ef9`. It is a yes-or-no for the owner, with a
default of yes. If the answer is no, the branch is dropped, and the API page and `people.json`
are made to say that these pairs are listed separately.

## The question

On 2 November the owner confirmed 30 members as one person each, one who sat in both the House
and the Senate (`corrections/member_corrections.json`, `same_person`). The site joins each pair's
two pages into one. But on 30 October, before that confirmation, the register of person numbers
(`generated/person_numbers.json`) had issued each pair as two people, one per chamber, and
`people.json` follows the register. So the new public download gives each of the 30 as two
people, the second with no name and no page. It is new in the 11 November update; it is not live
yet (it answers 404 on graniterecord.org), so no published number moves if the register is put
right now.

**Should the register merge each pair into one person?**

## What the branch does

Three commits, each passing preflight on its own:

1. **The register's check allows a merge.** A merge is the register's own way, as
   `person_numbers.py` and the API page describe it: the person kept takes the other's numbers,
   and the other keeps an entry with `replaced_by` and no numbers, so a number stored elsewhere
   still finds them. `check_register` refused every such merge in which the person who goes is
   numbered by an employee number, which all thirty are. It now allows that number to be held by
   the person it was replaced by, and by nobody else. The API page counts people, not entries, and
   says what a `replaced_by` line is.
2. **The thirty merges, in the register.** The person kept is the one the published rule gives
   over both numbers: the PersonID where one side has one (10 pairs), else the employee number
   that voted first (20 pairs). Nobody else in the register changes, and every person issued on
   30 October is still there.
3. **A check that every confirmed pair is one person** (`_same_person_one_person`). It fails on
   all thirty without commit 2, so a pair the owner confirms later cannot go out as two people.

## The thirty

The House and Senate columns are the site's ids, as `same_person` gives them.

| Member | House id | Senate id | Person kept | Person replaced |
|---|---|---|---|---|
| Boutin, David | 375968 | 37 | 37 (PersonID) | 375968 |
| Boyce, Robert | 376100 | 209042 | 376100 (employee number) | 209042 |
| Bradley, Jeb | 374827 | 36 | 36 (PersonID) | 374827 |
| Bragdon, Peter | 376311 | 209062 | 376311 (employee number) | 209062 |
| Burling, Peter | 373134 | 209059 | 373134 (employee number) | 209059 |
| Cataldo, Sam | 376444 | 45 | 45 (PersonID) | 376444 |
| Cilley, Jacalyn | 376564 | 209071 | 376564 (employee number) | 209071 |
| Clegg, Robert | 375976 | 209058 | 375976 (employee number) | 209058 |
| DeVries, Betsi | 376569 | 209066 | 376569 (employee number) | 209066 |
| Denley, William | 376666 | 209072 | 376666 (employee number) | 209072 |
| Downing, Michael | 376116 | 209065 | 376116 (employee number) | 209065 |
| Estabrook, Iris | 376117 | 209056 | 376117 (employee number) | 209056 |
| Fraser, Leo | 371138 | 202333 | 202333 (employee number) | 371138 |
| Gallus, John | 376291 | 209048 | 376291 (employee number) | 209048 |
| Gordon, Edward | 7369 | 205010 | 7369 (PersonID) | 205010 |
| Groen, Fenton | 9949 | 209082 | 9949 (PersonID) | 209082 |
| Houde, Matthew | 376778 | 209073 | 376778 (employee number) | 209073 |
| Kenney, Joseph | 376013 | 209049 | 376013 (employee number) | 209049 |
| King, Frederick | 376486 | 205005 | 205005 (employee number) | 376486 |
| Lasky, Bette | 376241 | 209075 | 376241 (employee number) | 209075 |
| Letourneau, Robert | 376142 | 209060 | 376142 (employee number) | 209060 |
| Levesque, Melanie | 376690 | 9405 | 9405 (PersonID) | 376690 |
| Merrill, Amanda | 373902 | 209077 | 209077 (employee number) | 373902 |
| O'Hearn, Jane | 375954 | 209044 | 375954 (employee number) | 209044 |
| Odell, Bob | 376371 | 209051 | 376371 (employee number) | 209051 |
| Peterson, Andrew | 376157 | 209052 | 376157 (employee number) | 209052 |
| Pierce, David | 376682 | 44 | 44 (PersonID) | 376682 |
| Reagan, John | 376737 | 47 | 47 (PersonID) | 376737 |
| Sapareto, Frank | 455 | 209055 | 455 (PersonID) | 209055 |
| Stiles, Nancy | 376631 | 41 | 41 (PersonID) | 376631 |

A person number is not a page. Frederick King's and Leo Fraser's one person is numbered by their
Senate employee numbers, which voted first, while their one page is the House's (fix/movers-term
puts it there). The register's numbers and the site's pages answer different questions.
