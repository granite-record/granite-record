// The live Worker's test suite (workers/live/), in one process: preflight's
// _live_tests runs `node --test tests/live/index.js`, and fails while a
// *.test.js in this folder is not imported here, since a file left out is
// never run and passes in silence. no_network.js first: no test asks the
// network, YouTube or Healthchecks.
import "./no_network.js";
import "./clock.test.js";
import "./sql.test.js";
import "./store.test.js";
import "./replay.test.js";
import "./functions.test.js";
import "./page.test.js";
import "./tds.test.js";
import "./votes.test.js";
import "./wire.test.js";
import "./youtube.test.js";
