// No test of the live Worker reaches the network. Every test hands run() and
// look() a fetch of its own (world.js); a code path that forgot to would
// reach for the global one, and this makes that global a failure that says
// so, before it could ask YouTube or Healthchecks anything.
globalThis.fetch = async url => {
  throw new Error(`a live test reached for the network (${String(url).split("?")[0]})`);
};
