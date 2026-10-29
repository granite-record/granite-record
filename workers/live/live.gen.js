// WRITTEN BY src/pages/live_gen.py FROM THE REPOSITORY'S OWN FILES. Do not edit it:
// change the value where the comment above it says it comes from, then run
//     python3 src/pages/live_gen.py
// and commit this file with the change. preflight fails while it differs from
// what that command would write.

// src/fetch/youtube/fetch_channel_index.py CHANNELS, by chamber: each one's YouTube channel; its uploads playlist is the id with UC made UU.
export const CHANNELS = {"H": "UCxqjz56akoWRL_5vyaQDtvQ", "S": "UCjBZdtrjRnQdmg-2MPMiWrA"};
// refusal.py NIGHT_WINDOWS, in UTC: [weekday (0 is Monday) or null for every day, [start hour, minute], [end hour, minute]].
export const NIGHT_WINDOWS = [[null, [8, 0], [13, 30]], [0, [4, 0], [6, 30]]];
// src/pages/live_gen.py SESSION_TITLE: the beginning of a session stream's title stem, by chamber (a RegExp source).
export const SESSION_TITLE = {"H": "^house session\\b", "S": "^senate session\\b"};
// src/fetch/gc_db/probe_db.py: DATABASE, USER and PASSWORD, the read-only login the General Court publishes. The host is not here: wrangler.toml names it under production alone.
export const SQL_LOGIN = {"database": "NHLegislatureDB", "user": "publicuser", "password": "PublicAccess"};
// src/fetch/gc_db/fetch_rollcalls_db.py: VOTE_WORD, a ballot's code and the record's word.
export const VOTE_WORD = {"0": "", "1": "Yea", "2": "Nay", "3": "Not Voting/Excused", "4": "Not Voting/Not Excused", "5": "No vote recorded", "6": "Presiding", "7": "No vote recorded"};
// VOTE_WORD's codes as the live file's one character: Y Yea, N Nay, E excused, X not excused, P presiding, . no vote recorded (src/pages/live_gen.py BALLOT_CHARS).
export const BALLOT_CHAR = {"0": ".", "1": "Y", "2": "N", "3": "E", "4": "X", "5": ".", "6": "P", "7": "."};
// records/docket_abbrev.json: the docket's abbreviations whose words are an outcome, as the General Court's key writes them.
export const DOCKET_OUTCOME = {"AA": "Amendment Adopted", "AF": "Amendment Failed", "AL": "Amendment Lost", "MA": "Motion Adopted", "MF": "Motion Failed", "ML": "Motion Lost"};
