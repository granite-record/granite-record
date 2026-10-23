// `node --test tests/follow/index.js` runs this file, which runs every test
// here. Node takes a folder named on its command line as a module and loads
// its index.js, so `node --test tests/follow/` does the same on Node 22; it
// failed on GitHub's Node 24 under Windows, so preflight (_follow_tests)
// names this file, and fails when a *.test.js is missing from the list below.

import "./changes.test.js";
import "./address.test.js";
import "./store.test.js";
import "./sender.test.js";
import "./signup.test.js";
import "./confirm.test.js";
import "./manage.test.js";
import "./unsubscribe.test.js";
import "./count.test.js";
import "./lsr.test.js";
import "./bounce.test.js";
import "./html.test.js";
import "./mail.test.js";
import "./privacy.test.js";
