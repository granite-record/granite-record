// GRANITE_VERSION: 2026-09-04.2
// A DOM stub just deep enough to load bills.html's script and call render().
const made = {};
function el(tag = "div") {
  const e = {
    tagName: tag, dataset: {}, style: {}, children: [], hidden: false,
    textContent: "", value: "", scrollTop: 0,
    classList: { toggle(){}, add(){}, remove(){}, contains(){ return false; } },
    setAttribute(){}, getAttribute(){ return null; }, removeAttribute(){},
    // Listeners are kept rather than dropped, so a check can fire one. The
    // page's behaviour lives in these -- typing in the search box, clicking a
    // card -- and none of it was reachable from a test while they went
    // nowhere.
    _on: {},
    addEventListener(t, f){ (this._on[t] = this._on[t] || []).push(f); },
    fire(t, ev){ (this._on[t] || []).forEach(f => f(Object.assign(
      {target: this, preventDefault(){}, stopPropagation(){}}, ev || {}))); },
    removeEventListener(){}, focus(){}, blur(){},
    click(){}, append(){}, appendChild(){}, remove(){},
    closest(){ return null; }, contains(){ return false; },
    querySelector(){ return el(); }, querySelectorAll(){ return []; },
    getBoundingClientRect(){ return {top:0,left:0,width:0,height:0}; },
    scrollIntoView(){},
  };
  Object.defineProperty(e, "innerHTML", {
    get(){ return e._html || ""; }, set(v){ e._html = String(v); },
  });
  return e;
}
const doc = {
  documentElement: el("html"), body: el("body"), head: el("head"),
  title: "", readyState: "complete",
  getElementById(id){ return (made[id] ||= el()); },
  querySelector(sel){ return (made[sel] ||= el()); },
  querySelectorAll(){ return []; },
  createElement(t){ return el(t); },
  addEventListener(){}, removeEventListener(){},
};
globalThis.document = doc;
globalThis.window = globalThis;
globalThis.location = { hash: "", search: "", href: "https://x/bills.html",
                        pathname: "/bills.html", origin: "https://x" };
globalThis.history = { pushState(){}, replaceState(){}, back(){}, state: null };
globalThis.navigator = { userAgent: "node" };
globalThis.scrollTo = () => {};
globalThis.scrollY = 0;
globalThis.matchMedia = () => ({ matches: false, addEventListener(){} });
globalThis.requestAnimationFrame = (f) => f();
globalThis.setTimeout = (f) => { try { f(); } catch(_){} return 0; };
globalThis.fetch = async () => ({ ok: true, status: 200, json: async () => ([]),
                                  text: async () => "[]" });
globalThis.IntersectionObserver = class { observe(){} disconnect(){} };
globalThis.addEventListener = () => {};
globalThis.removeEventListener = () => {};
globalThis.getComputedStyle = () => ({ getPropertyValue: () => "" });
globalThis.localStorage = { getItem(){return null;}, setItem(){}, removeItem(){} };
globalThis.URLSearchParams = URLSearchParams;
