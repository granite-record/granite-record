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
