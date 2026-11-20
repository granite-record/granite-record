/* BEFORE THE FIRST PAINT, and that is the whole reason this is inline in the
   head rather than in app.js. app.js loads at the end of the body: by the
   time it ran, a reader who had chosen dark would have already been shown a
   white page. Three lines, no dependencies, and wrapped in try/catch because
   localStorage throws outright in a locked-down browser rather than
   returning null. Absent or unrecognised means follow the system, which is
   what the stylesheet does on its own.
   And html.js, set first: a record page carries its record as plain HTML
   for a reader that runs no scripts (shell.page's static), which app.css
   hides once scripts are known to run, so it is never painted over. */
document.documentElement.classList.add("js");
try{var t=localStorage.getItem("gr-theme");
if(t==="dark"||t==="light")document.documentElement.dataset.theme=t;}catch(e){}
