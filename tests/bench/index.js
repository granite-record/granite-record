// `node --test tests/bench/index.js` runs every test of the shared bench
// (workers/bench/, functions/bench.js and functions/api/bench/), in one
// process, as tests/follow/index.js does for email following. preflight
// (_bench_tests) names this file, and fails when a *.test.js here is missing
// from the list below.

import "./store.test.js";
import "./functions.test.js";
