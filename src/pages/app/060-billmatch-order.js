// BILLMATCH:BEGIN -- the order bills sort in; see the note above SYN.
const KINDORDER={HB:0,HR:1,HCR:2,CACR:3,SB:4,SR:5,SCR:6,HJR:7,SJR:8};
function billKey(b){
  const m=/^([A-Z]+)\s*(\d+)/.exec(b.id.toUpperCase())||[];
  return [KINDORDER[m[1]] ?? 99, parseInt(m[2]||"0",10)];
}
// BILLMATCH:END
