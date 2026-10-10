// GRANITE_VERSION: 2026-10-09.1
/* A BILL'S PRINT SHEET. A reference sheet of one bill's record for paper,
   composed in the reader's browser from the record the page already holds,
   beside a short menu of settings, and printed with the browser's own dialog
   (the person's decisions of 6 October 2026, the bill-print-sheet design;
   the second-round prototype, approved 9 October 2026, less the rail's
   table and the hearings and session days, which the person found
   redundant with How It Got Here).

   ONE CALL MOUNTS IT. A bill's page draws the Print button, and the button
   does

       GRPrint.open(record, row)

   with the bill's record (app.js's detail[dkey(id)], the page's gr-data)
   and its index row (the chip's word, the number with its suffix). It
   covers the page with the sheet and its settings, asks for the bill's
   versions where it has them, and prints only the sheet. Escape, or "Back
   to the bill", puts the page back as it was. print.css is this file's
   stylesheet, loaded the first time the sheet opens.

   NO FILE PER BILL. The deploy is near half of Cloudflare's file cap, and a
   print page for each of 33,683 bills would take most of the rest; and a
   second rendering would drift from the page. So the sheet is the record
   drawn again here, at the moment it is asked for.

   NOTHING HERE FORMATS A BILL, A PERSON, A VOTE OR A DATE OF ITS OWN (the
   component plan, approved 9 October 2026). A date is components.js's
   dateWords, a person its pchip, a committee its cmteLink, the words
   WORDBOOK's; the names of a kind of measure, of a way of voting, of a body
   on How It Got Here and of a member who did not vote are app.js's own
   tables, read through pageWords() so that none is typed twice. Where the
   component plan's later steps put a vote's head or a document's row into
   components.js, this calls those.

   WHAT IS ITS OWN is what no page draws: the QR code (an encoder written
   here, after ISO/IEC 18004; no outside library, no network), and which
   amendment made which change to the text. The versions are the record of
   that: a bill's versions file holds its texts in order, so the change
   from one to the next is one step, and each step is joined to the
   amendments the record shows adopted between the two versions' days.
   Read in order -- the reading `git blame` gives a file -- every word of
   the current text has the step that put it there and every word struck
   from the introduced text the step that took it out. Where a step joins
   to one amendment the number is that amendment's; to several, a change is
   given to the one whose own text holds its new words, and otherwise to
   the step; to none, it is marked with no number and the list says why.
   No guessing.

   NEVER COLOUR ALONE: party as its letter (the chip's label carries it),
   outcomes in words, changes underlined or struck through and bracketed,
   tables ruled. preflight holds that, renders the sheet in node with every
   section present and absent, and reads the QR code back. */
const GRPrint=(()=>{
"use strict";

// =================================================================== QR CODE
// Byte mode, error correction level M, the smallest version 1 to 6 the
// address fits (an address of this site is 40-odd bytes: version 3 or 4),
// and the mask with the lowest penalty: the standard's own steps, written out
// after Project Nayuki's reference implementation, as the prototype's qr.py
// was. qrRead() reads a symbol back -- the format bits, the unmasking, the
// codewords in placement order, the Reed-Solomon remainders and the data --
// which is how preflight holds the writer to what it wrote.
const QR_EC={1:[10,1],2:[16,1],3:[26,1],4:[18,2],5:[24,2],6:[16,4]};
const QR_TOTAL={1:26,2:44,3:70,4:100,5:134,6:172};
const QR_ALIGN={1:[],2:[6,18],3:[6,22],4:[6,26],5:[6,30],6:[6,34]};
const QR_MASKS=[(x,y)=>(x+y)%2===0,(x,y)=>y%2===0,(x,y)=>x%3===0,(x,y)=>(x+y)%3===0,
  (x,y)=>(Math.floor(x/3)+Math.floor(y/2))%2===0,(x,y)=>x*y%2+x*y%3===0,
  (x,y)=>(x*y%2+x*y%3)%2===0,(x,y)=>((x+y)%2+x*y%3)%2===0];

function gfMul(x,y){
  let z=0;
  for(let i=7;i>=0;i--){
    z=((z<<1)^((z>>>7)*0x11D))&0x1FF;
    z^=((y>>>i)&1)*x;
  }
  return z&0xFF;
}
function rsDivisor(deg){
  const r=new Array(deg).fill(0);r[deg-1]=1;
  let root=1;
  for(let i=0;i<deg;i++){
    for(let j=0;j<deg;j++){
      r[j]=gfMul(r[j],root);
      if(j+1<deg)r[j]^=r[j+1];
    }
    root=gfMul(root,0x02);
  }
  return r;
}
function rsRemainder(data,div){
  const r=new Array(div.length).fill(0);
  for(const b of data){
    const f=b^r.shift();
    r.push(0);
    div.forEach((c,i)=>{r[i]^=gfMul(c,f);});
  }
  return r;
}
function qrCodewords(text){
  const data=Array.from(new TextEncoder().encode(String(text)));
  let ver=0;
  for(let v=1;v<=6;v++){
    const [ecl,nb]=QR_EC[v];
    if(4+8+8*data.length<=(QR_TOTAL[v]-ecl*nb)*8){ver=v;break;}
  }
  if(!ver)throw new Error("too long for a QR code of version 1 to 6: "+text);
  const [ecl,nb]=QR_EC[ver], ndata=QR_TOTAL[ver]-ecl*nb;
  const bits=[];
  const put=(v,n)=>{for(let i=n-1;i>=0;i--)bits.push((v>>>i)&1);};
  put(0b0100,4);                 // byte mode
  put(data.length,8);            // its count: 8 bits below version 10
  data.forEach(b=>put(b,8));
  const cap=ndata*8;
  put(0,Math.min(4,cap-bits.length));
  put(0,(8-bits.length%8)%8);
  for(let pad=0xEC;bits.length<cap;pad^=0xEC^0x11)put(pad,8);
  const words=[];
  for(let i=0;i<bits.length;i+=8)words.push(parseInt(bits.slice(i,i+8).join(""),2));
  // Every block is the same length up to version 6 at level M; interleaved.
  const per=ndata/nb, div=rsDivisor(ecl), blocks=[];
  for(let i=0;i<nb;i++){const d=words.slice(i*per,(i+1)*per);blocks.push([d,rsRemainder(d,div)]);}
  const out=[];
  for(let i=0;i<per;i++)blocks.forEach(([d])=>out.push(d[i]));
  for(let i=0;i<ecl;i++)blocks.forEach(([,e])=>out.push(e[i]));
  return [ver,out];
}
function qrFormatBits(mask){
  const data=mask;               // level M's two bits are 00
  let rem=data;
  for(let i=0;i<10;i++)rem=(rem<<1)^((rem>>>9)*0x537);
  return ((data<<10)|rem)^0x5412;
}
function qrSymbol(ver){
  const n=ver*4+17;
  const m=Array.from({length:n},()=>new Array(n).fill(false));
  const fn=Array.from({length:n},()=>new Array(n).fill(false));
  const set=(x,y,dark)=>{m[y][x]=dark;fn[y][x]=true;};
  const format=mask=>{
    const bits=qrFormatBits(mask), g=i=>((bits>>>i)&1)===1;
    for(let i=0;i<6;i++)set(8,i,g(i));
    set(8,7,g(6));set(8,8,g(7));set(7,8,g(8));
    for(let i=9;i<15;i++)set(14-i,8,g(i));
    for(let i=0;i<8;i++)set(n-1-i,8,g(i));
    for(let i=8;i<15;i++)set(8,n-15+i,g(i));
    set(8,n-8,true);             // the dark module
  };
  for(let i=0;i<n;i++){set(6,i,i%2===0);set(i,6,i%2===0);}
  for(const [cx,cy] of [[3,3],[n-4,3],[3,n-4]])
    for(let dy=-4;dy<=4;dy++)for(let dx=-4;dx<=4;dx++){
      const x=cx+dx,y=cy+dy;
      if(x>=0&&x<n&&y>=0&&y<n){const d=Math.max(Math.abs(dx),Math.abs(dy));set(x,y,d!==2&&d!==4);}
    }
  const al=QR_ALIGN[ver];
  al.forEach((a,i)=>al.forEach((b,j)=>{
    if((i===0&&j===0)||(i===0&&j===al.length-1)||(i===al.length-1&&j===0))return;
    for(let dy=-2;dy<=2;dy++)for(let dx=-2;dx<=2;dx++)
      set(a+dx,b+dy,Math.max(Math.abs(dx),Math.abs(dy))!==1);
  }));
  format(0);
  // The data modules in placement order: two columns at a time from the
  // right, up then down, skipping the vertical timing column.
  const order=()=>{
    const out=[];
    for(let right=n-1;right>=1;right-=2){
      if(right===6)right=5;
      for(let vert=0;vert<n;vert++)for(let j=0;j<2;j++){
        const x=right-j, up=((right+1)&2)===0, y=up?n-1-vert:vert;
        if(!fn[y][x])out.push([x,y]);
      }
    }
    return out;
  };
  return {n,m,fn,format,order};
}
function qrPenalty(m){
  const n=m.length;let p=0;
  const cols=m[0].map((_,x)=>m.map(r=>r[x]));
  for(const lines of [m,cols])for(const row of lines){
    let run=0,prev=null;
    for(const v of row){
      if(v===prev)run++;
      else{if(run>=5)p+=run-2;run=1;prev=v;}
    }
    if(run>=5)p+=run-2;
    const s=row.map(v=>v?"1":"0").join("");
    for(const pat of ["10111010000","00001011101"])
      for(let i=s.indexOf(pat);i>=0;i=s.indexOf(pat,i+1))p+=40;
  }
  for(let y=0;y<n-1;y++)for(let x=0;x<n-1;x++)
    if(m[y][x]===m[y][x+1]&&m[y][x]===m[y+1][x]&&m[y][x]===m[y+1][x+1])p+=3;
  const dark=m.reduce((t,r)=>t+r.filter(Boolean).length,0);
  p+=Math.floor((Math.abs(dark*20-n*n*10)+n*n-1)/(n*n))*10;
  return p;
}
// The symbol for `text`: rows of modules, true where dark.
function qrEncode(text){
  const [ver,words]=qrCodewords(text);
  let best=null;
  for(let mask=0;mask<8;mask++){
    const s=qrSymbol(ver);
    const bits=[];
    words.forEach(w=>{for(let i=7;i>=0;i--)bits.push((w>>>i)&1);});
    s.order().forEach(([x,y],k)=>{s.m[y][x]=k<bits.length&&bits[k]===1;});
    for(let y=0;y<s.n;y++)for(let x=0;x<s.n;x++)
      if(!s.fn[y][x]&&QR_MASKS[mask](x,y))s.m[y][x]=!s.m[y][x];
    s.format(mask);
    const pen=qrPenalty(s.m);
    if(!best||pen<best[0])best=[pen,s.m];
  }
  return best[1];
}
// Read a symbol back: what it says, or an Error saying which part is wrong.
function qrRead(m){
  const n=m.length, ver=(n-17)/4;
  if(!QR_TOTAL[ver])throw new Error("not a symbol of version 1 to 6");
  const pos=[[8,0],[8,1],[8,2],[8,3],[8,4],[8,5],[8,7],[8,8],[7,8]];
  for(let i=9;i<15;i++)pos.push([14-i,8]);
  const pos2=[];
  for(let i=0;i<8;i++)pos2.push([n-1-i,8]);
  for(let i=8;i<15;i++)pos2.push([8,n-15+i]);
  const read=ps=>ps.reduce((t,[x,y],i)=>t|(m[y][x]?1<<i:0),0);
  const bits=read(pos), bits2=read(pos2);
  const mask=[0,1,2,3,4,5,6,7].find(k=>qrFormatBits(k)===bits);
  if(mask===undefined||bits!==bits2)throw new Error("the format bits do not read");
  const s=qrSymbol(ver), raw=[];
  s.order().forEach(([x,y])=>raw.push((m[y][x]!==QR_MASKS[mask](x,y))?1:0));
  const words=[];
  for(let i=0;i<QR_TOTAL[ver]*8;i+=8)words.push(parseInt(raw.slice(i,i+8).join(""),2));
  const [ecl,nb]=QR_EC[ver], ndata=QR_TOTAL[ver]-ecl*nb, per=ndata/nb, div=rsDivisor(ecl);
  const data=[];
  for(let b=0;b<nb;b++){
    const d=[],e=[];
    for(let i=0;i<per;i++)d.push(words[i*nb+b]);
    for(let i=0;i<ecl;i++)e.push(words[ndata+i*nb+b]);
    if(rsRemainder(d,div).join()!==e.join())throw new Error("a Reed-Solomon block does not check");
    data.push(d);
  }
  const flat=[];
  for(let b=0;b<nb;b++)flat.push(...data[b]);
  const bs=flat.map(w=>w.toString(2).padStart(8,"0")).join("");
  if(bs.slice(0,4)!=="0100")throw new Error("not byte mode");
  const cnt=parseInt(bs.slice(4,12),2), out=[];
  for(let i=0;i<cnt;i++)out.push(parseInt(bs.slice(12+8*i,20+8*i),2));
  return {version:ver,mask,size:n,text:new TextDecoder().decode(new Uint8Array(out))};
}
// One path, its dark modules in the sheet's ink (currentColor), on a quiet
// zone of four modules in the paper's ground: print.css colours both.
function qrSvg(m,label){
  const n=m.length, q=4, w=n+2*q, d=[];
  for(let y=0;y<n;y++)for(let x=0;x<n;){
    if(!m[y][x]){x++;continue;}
    const s=x;while(x<n&&m[y][x])x++;
    d.push(`M${s+q} ${y+q}h${x-s}v1h-${x-s}z`);
  }
  return `<svg class="ps-qrsvg" viewBox="0 0 ${w} ${w}" role="img" aria-label="${esc(label)}"
    shape-rendering="crispEdges"><rect class="ps-qrbg" width="${w}" height="${w}"/><path
    fill="currentColor" d="${d.join("")}"/></svg>`;
}

// ============================================================ THE TEXT, BLAMED
// A version as tokens: a paragraph mark carrying its indent, then the words,
// each with the General Court's own mark for current law ("", "cut", "add").
// From "STATE OF NEW HAMPSHIRE" on, where a version has it: what is above it
// is the docket's stamps, the sponsors and the analysis, which the sheet
// prints from the record.
const PARA="¶";
function tokens(doc){
  const blocks=Array.isArray(doc)?doc:(doc&&Array.isArray(doc.blocks))?doc.blocks
    :String(doc||"").split("\n").map(l=>({runs:[["",l]]}));
  const text=b=>(b.runs||[]).map(r=>r[1]).join("");
  let start=blocks.findIndex(b=>/STATE OF NEW HAMPSHIRE/.test(text(b)));
  if(start<0)start=0;
  const out=[];
  blocks.slice(start).forEach(b=>{
    const t0=((b.runs||[])[0]||["",""])[1];
    out.push({w:PARA,f:"",ind:t0.length-t0.replace(/^\t+/,"").length});
    (b.runs||[]).forEach(([f,t])=>String(t).split(/[\s ]+/).forEach(w=>{
      if(w)out.push({w,f:f||""});
    }));
  });
  return out;
}
const tkey=t=>t.w+"\u0000"+t.f;

// Myers' diff of two lists of keys: [[tag,i1,i2,j1,j2]] with tag "equal",
// "delete", "insert" or "replace", or null where the two need more than
// `limit` edits (the caller marks the whole stretch as replaced then).
function myers(A,B,limit){
  const n=A.length,m=B.length;
  let pre=0;
  while(pre<n&&pre<m&&A[pre]===B[pre])pre++;
  let suf=0;
  while(suf<n-pre&&suf<m-pre&&A[n-1-suf]===B[m-1-suf])suf++;
  const a=A.slice(pre,n-suf),b=B.slice(pre,m-suf),N=a.length,M=b.length,max=N+M;
  const edits=[];        // [kind,i,j] in a's and b's own indices: "=", "-", "+"
  if(N&&M){
    const off=max+1, v=new Int32Array(2*max+3), trace=[];
    let D=-1;
    for(let d=0;d<=max&&D<0;d++){
      if(d>limit)return null;
      trace.push(v.slice(off-d-1,off+d+2));
      for(let k=-d;k<=d;k+=2){
        let x=(k===-d||(k!==d&&v[off+k-1]<v[off+k+1]))?v[off+k+1]:v[off+k-1]+1, y=x-k;
        while(x<N&&y<M&&a[x]===b[y]){x++;y++;}
        v[off+k]=x;
        if(x>=N&&y>=M){D=d;break;}
      }
    }
    let x=N,y=M;
    for(let d=D;d>0;d--){
      const V=trace[d], at=k=>V[k+d+1], k=x-y;
      const pk=(k===-d||(k!==d&&at(k-1)<at(k+1)))?k+1:k-1;
      const px=at(pk), py=px-pk;
      while(x>px&&y>py){x--;y--;edits.push(["=",x,y]);}
      if(x===px){y--;edits.push(["+",x,y]);}else{x--;edits.push(["-",x,y]);}
    }
    while(x>0&&y>0){x--;y--;edits.push(["=",x,y]);}
    edits.reverse();
  }else if(N)for(let i=0;i<N;i++)edits.push(["-",i,0]);
  else for(let j=0;j<M;j++)edits.push(["+",0,j]);
  const ops=[];
  const add=(tag,i1,i2,j1,j2)=>{
    if(i1===i2&&j1===j2)return;
    const p=ops[ops.length-1];
    if(p&&p[2]===i1&&p[4]===j1&&(p[0]===tag||(p[0]!=="equal"&&tag!=="equal"))){
      p[0]=p[0]===tag?tag:"replace";p[2]=i2;p[4]=j2;return;
    }
    ops.push([tag,i1,i2,j1,j2]);
  };
  add("equal",0,pre,0,pre);
  let i=pre,j=pre;
  edits.forEach(([e])=>{
    if(e==="=")add("equal",i,++i,j,++j);
    else if(e==="-")add("delete",i,++i,j,j);
    else add("insert",i,i,j,++j);
  });
  add("equal",i,n,j,m);
  return ops;
}
// The trace Myers keeps grows with the square of the edits, so a stretch
// needing more than this many is marked whole: struck, then put in. That is
// what an amendment replacing a long stretch outright did, and it keeps a
// phone's memory to a few megabytes.
const MYERS_LIMIT=2000;

// Two texts' tokens compared paragraph by paragraph first, then word by word
// inside the stretches whose paragraphs differ: as good as one comparison of
// every word, and the size of HB 2 of 2025 (107,482 words a version) stays
// a matter of its changed stretches. Then the prototype's tidy: an unchanged
// run of one or two words between two changes is taken into the change, so a
// rewritten clause reads as one struck run and one added run, not a comb of
// "the".
function diffTokens(a,b){
  // A paragraph starts at each mark, and at the first word where an earlier
  // step struck the mark before it.
  const paras=ts=>{
    if(!ts.length)return [];
    const at=[0];
    ts.forEach((t,i)=>{if(t.w===PARA&&i>0)at.push(i);});
    return at.map((s,k)=>[s,k+1<at.length?at[k+1]:ts.length]);
  };
  const pa=paras(a),pb=paras(b);
  const pkey=(ts,[s,e])=>ts.slice(s,e).map(tkey).join("\u0001");
  const at=(ps,i,len)=>i<ps.length?ps[i][0]:len;
  let pops=myers(pa.map(p=>pkey(a,p)),pb.map(p=>pkey(b,p)),MYERS_LIMIT);
  if(!pops)pops=[["replace",0,pa.length,0,pb.length]];
  const ops=[];
  const push=(tag,i1,i2,j1,j2)=>{
    if(i1===i2&&j1===j2)return;
    const p=ops[ops.length-1];
    if(p&&p[0]===tag){p[2]=i2;p[4]=j2;}else ops.push([tag,i1,i2,j1,j2]);
  };
  pops.forEach(([tag,i1,i2,j1,j2])=>{
    const s1=at(pa,i1,a.length),e1=at(pa,i2,a.length),s2=at(pb,j1,b.length),e2=at(pb,j2,b.length);
    if(tag==="equal"){push("equal",s1,e1,s2,e2);return;}
    const sub=myers(a.slice(s1,e1).map(tkey),b.slice(s2,e2).map(tkey),MYERS_LIMIT)
      ||[["replace",0,e1-s1,0,e2-s2]];
    sub.forEach(([t,x1,x2,y1,y2])=>push(t==="equal"?"equal":"change",s1+x1,s1+x2,s2+y1,s2+y2));
  });
  const out=[];
  ops.forEach((op,k)=>{
    let [tag,i1,i2,j1,j2]=op;
    if(tag==="equal"&&k>0&&k<ops.length-1&&i2-i1<=2&&!a.slice(i1,i2).some(t=>t.w===PARA))tag="change";
    const p=out[out.length-1];
    if(tag!=="equal"&&p&&p[0]!=="equal"){p[2]=i2;p[4]=j2;}
    else out.push([tag,i1,i2,j1,j2]);
  });
  return out;
}

// The current text as tokens, each "eq" (as introduced), "add" (with the tag
// of the step that put it in) or "del" (struck, with the tag of the step that
// took it out), from the versions' tokens in order and each step's tag. Words
// one amendment put in and a later one took out are in neither the
// introduced text nor the current one, and are not shown: the step that did
// so is noted in `revised`, for the list to say.
function blame(versions,tags){
  let doc=versions[0].map(t=>Object.assign({},t,{st:"eq",tag:null}));
  const revised=new Set();
  for(let s=1;s<versions.length;s++){
    const nw=versions[s], tag=tags[s-1];
    const a=[],pre=[];
    let cur=[];
    doc.forEach(t=>{if(t.st==="del")cur.push(t);else{a.push(t);pre.push(cur);cur=[];}});
    const tail=cur, out=[];
    diffTokens(a,nw).forEach(([op,i1,i2,j1,j2])=>{
      if(op==="equal"){
        for(let i=i1,j=j1;i<i2;i++,j++){
          out.push(...pre[i]);
          const t=a[i];t.f=nw[j].f;if(t.w===PARA)t.ind=nw[j].ind;
          out.push(t);
        }
        return;
      }
      for(let i=i1;i<i2;i++){
        out.push(...pre[i]);
        const t=a[i];
        if(t.st==="add"){revised.add(JSON.stringify([tag,t.tag]));continue;}
        t.st="del";t.tag=tag;out.push(t);
      }
      for(let j=j1;j<j2;j++)out.push(Object.assign({},nw[j],{st:"add",tag}));
    });
    doc=out.concat(tail);
  }
  return {doc,revised:[...revised].map(x=>JSON.parse(x))};
}

// ================================================== WHICH AMENDMENT, AND WHY
// A version's day, "12/11/2025 16:02:08", as the ISO day the record's other
// dates are, to compare with them; app.js's recordDay says it to a reader.
function vday(s){
  const m=/^(\d{1,2})\/(\d{1,2})\/(\d{4})\b/.exec(String(s||""));
  return m?`${m[3]}-${m[1].padStart(2,"0")}-${m[2].padStart(2,"0")}`:String(s||"").slice(0,10);
}
const wordsOf=s=>String(s||"").toLowerCase().split(/[^a-z0-9]+/).filter(Boolean);

// The steps from one version to the next, each with its tag and the entries
// the list prints, from the record's adopted amendments (PRINT_SHEET_DESIGN,
// "Linking a version to its amendment"). An entry: {tag, a: amendment or
// null, v: the version the step made, kind: "one" | "shared" | "step" |
// "chaptered" | "none", with: [tags] for a step that carried several}.
function joinSteps(d,ix){
  const vs=ix.versions||[], amds=(d.amendments||[]).filter(a=>a.adopted===true&&a.date);
  const out=[];let n=0;
  for(let s=1;s<vs.length;s++){
    const lo=vday(vs[s-1].date), hi=vday(vs[s].date), v=vs[s];
    const made=amds.filter(a=>lo<a.date&&a.date<=hi);
    if(made.length===1){n++;out.push({tag:String(n),a:made[0],v,kind:"one",entries:[]});}
    else if(made.length>1){
      const with_=made.map(a=>({tag:String(++n),a,v,kind:"shared"}));
      out.push({tag:String(++n),a:null,v,kind:"step",with:with_.map(x=>x.tag),
        made:with_,entries:with_});
    }
    else if(/chapter/i.test(`${v.title||""} ${v.label||""}`))out.push({tag:"C",a:null,v,kind:"chaptered"});
    // Its own key, so its words are counted apart from another such step's,
    // and a "~" that says it is never printed.
    else out.push({tag:`~${s}`,a:null,v,kind:"none"});
  }
  return out;
}
const printed=g=>!!g&&g.charAt(0)!=="~";

// A change in a step that carried several amendments goes to the one whose
// own text holds its new words, where exactly one does; the rest keep the
// step's own number. An amendment prints the language it inserts, which is
// what makes this a reading of the record and not a guess.
function settleShared(doc,steps){
  steps.filter(s=>s.kind==="step").forEach(s=>{
    const texts=s.made.map(x=>({tag:x.tag,w:" "+wordsOf(x.a.text).join(" ")+" "}));
    let run=[];
    const flush=()=>{
      if(!run.length)return;
      const said=" "+wordsOf(run.map(t=>t.w).join(" ")).join(" ")+" ";
      const hold=said.trim()?texts.filter(x=>x.w.includes(said)):[];
      if(hold.length===1)run.forEach(t=>{t.tag=hold[0].tag;});
      run=[];
    };
    doc.forEach(t=>{
      if(t.st==="add"&&t.tag===s.tag&&t.w!==PARA)run.push(t);
      else if(t.w!==PARA)flush();
    });
    flush();
  });
}

// ====================================================================== WORDS
// The tables a bill's page already draws with, from app.js: the names of a
// kind of measure (TYPE_NAME), of the ways a vote is taken (AVK), of a body
// on How It Got Here (JBODY) and of a member recorded as not voting (OTHER);
// and its readers of the record: rsaChapters, recordDay, and tallyWhole,
// which keeps "299–28" on one line. Read, never typed again here.
function pageWords(){
  return {type:TYPE_NAME,how:AVK,body:JBODY,other:OTHER,rsa:rsaChapters,day:recordDay,
    tally:tallyWhole};
}

// ================================================================= SETTINGS
// Remembered in this browser only (localStorage "gr-print"), never sent.
const KEY="gr-print";
const SECS=["summary","votes","reports","text","docs"];
function defaults(){
  return {sec:{summary:1,votes:1,reports:1,text:1,docs:1},names:0,qr:1,text:"marked"};
}
function loadSettings(){
  const st=defaults();
  try{
    const s=JSON.parse(localStorage.getItem(KEY)||"null");
    if(s&&s.sec){SECS.forEach(k=>{if(k in s.sec)st.sec[k]=s.sec[k]?1:0;});
      st.names=s.names?1:0;st.qr=s.qr===0?0:1;if(typeof s.text==="string")st.text=s.text;}
  }catch(_){}
  return st;
}
function saveSettings(st){try{localStorage.setItem(KEY,JSON.stringify(st));}catch(_){}}

// A BILL TOO LONG TO PRINT BY ACCIDENT. Above about twenty pages of text the
// text is off until the reader ticks it, with its length said beside the box
// (the design's open question 1: "about 20 pages is the starting guess").
// PER_PAGE is measured, not assumed: on Letter in this sheet's type, HB
// 1681's chaptered text took about three pages for its 1,156 words clean and
// about five for 1,882 marked (its struck words counted), so about 400 a
// page. The twenty is the design's guess, still the person's to settle.
const PER_PAGE=400, LONG_PAGES=20;

// ================================================================ THE RECORD
const hasIndex=d=>!!d&&(((d.nver||0)>1)||!!(d.namd||0));
const verKey=d=>`${d.year}/${d.id}`;
// What this record can print, so the menu offers only that and the sheet
// draws only that: each section where the record has it, as the tabs do.
function has(d,ctx){
  const ix=(ctx.versions||{}).ix;
  const vs=(ix&&ix.versions)||[];
  const body=!!String((d.billtext||{}).body||"").trim();
  const ownAmd=(d.amendments||[]).some(a=>String(a.text||"").trim())
    ||!!(ix&&(ix.amendments||[]).length);
  const stages=(d.stages||[]).length||!!d.narrative;
  return {
    summary:!!((d.billtext||{}).analysis||stages||(d.notes||[]).length
      ||(d.veto_message&&(d.veto_message.text||[]).length)),
    votes:!!((d.rollcalls||[]).length||d.ballot),
    names:(d.rollcalls||[]).some(r=>(r.members||[]).length),
    reports:!!((d.reports||[]).length||(d.docket_reports||[]).length),
    text:hasIndex(d)||body||ownAmd,
    docs:!!(d.documents||[]).length,
    marked:vs.length>1||(hasIndex(d)&&!ix),
    clean:vs.length>0||body||(hasIndex(d)&&!ix),
    amendments:ownAmd,
    introduced:vs.length>1||(hasIndex(d)&&!ix),
  };
}
// The text choice the sheet will draw: the reader's where the record has it,
// and otherwise the first the record has, in the menu's order.
function textChoice(d,ctx,st){
  const h=has(d,ctx);
  return [st.text,"marked","clean","amendments","introduced"].find(c=>h[c])||"";
}
function textWords(d,ctx){
  const ix=(ctx.versions||{}).ix, vs=(ix&&ix.versions)||[];
  if(vs.length)return vs[vs.length-1].words||0;
  return Math.round(String((d.billtext||{}).body||"").length/6);
}
const isLong=(d,ctx)=>textWords(d,ctx)>PER_PAGE*LONG_PAGES;
const pagesOf=(d,ctx)=>Math.max(1,Math.round(textWords(d,ctx)/PER_PAGE));

// The files the sheet's text needs that are not here yet: the versions'
// blocks for the marked, clean and introduced texts, the amendments' own
// texts for theirs. open() asks for them and draws again as they land.
function needs(d,ctx,st){
  const ix=(ctx.versions||{}).ix;
  if(!st.sec.text||!ix||!has(d,ctx).text||(isLong(d,ctx)&&!st.long))return [];
  const have=(ctx.versions||{}).files||{}, vs=ix.versions||[];
  const choice=textChoice(d,ctx,st);
  const u=v=>v&&(v.blocks_url||v.text_url);
  const want=choice==="marked"?vs.map(u):choice==="clean"?[u(vs[vs.length-1])]
    :choice==="introduced"?[u(vs[0])]
    :choice==="amendments"?(ix.amendments||[]).map(a=>a.text_url):[];
  return want.filter(x=>x&&!(x in have));
}

// ================================================================ THE SHEET
const tally=(y,n)=>`<span class="ps-nw">${esc(y)}–${esc(n)}</span>`;
const plain=u=>String(u||"").replace(/^https?:\/\/(www\.)?/,"");
const typeOf=d=>((/^[A-Za-z]+/.exec(String(d.id||""))||[""])[0]).toUpperCase();
const numberOf=(d,b)=>(b&&b.n)||String(d.id||"").replace(/^([A-Za-z]+)(\d)/,"$1 $2");
const sec=(name,title,body,cls)=>`<section class="ps-sec${cls?" "+cls:""}"${
  name?` data-sec="${name}"`:""}><h3 class="ps-h3">${title}</h3>${body}</section>`;
const fact=(k,v)=>v?`<tr><th scope="row">${esc(k)}</th><td>${v}</td></tr>`:"";

function masthead(d,b,ctx,st,W){
  const num=numberOf(d,b), url=ctx.url, chip=(b&&(b.chip||b.status))||"";
  const law=((d.journey||{}).rail||[]).find(s=>s.stop==="Law"&&s.mark==="p"&&s.date);
  const said=[];
  if(b&&b.status&&b.status!==chip)said.push(esc(b.status));
  if(d.chapter)said.push(`Chapter ${esc(d.chapter)}, Laws of ${esc(d.year)}${
    law?`, in effect ${esc(dateWords(law.date,"full"))}`:""}`);
  if(!chip&&!said.length&&d.next_step)said.push(esc(d.next_step));
  const qr=st.qr&&url?`<figure class="ps-qr">${qrSvg(qrEncode(url),
    `QR code: ${plain(url)}`)}<figcaption>This bill&rsquo;s page<span class="ps-addr">${
    esc(plain(url)).replace(/\//g,"/<wbr>")}</span></figcaption></figure>`:"";
  return `<header class="ps-mast">
<div class="ps-brandrow"><span class="ps-brand">Granite Record</span><span class="ps-addr">graniterecord.org</span></div>
<div class="ps-mtop${qr?"":" ps-noqr"}"><div class="ps-mmain">
<p class="ps-kind">${esc(W.type[typeOf(d)]||typeOf(d))}${d.term?` &middot; ${esc(d.term)} term, ${esc(d.year)} session`:""}</p>
<h2 class="ps-title">${esc(num)} <span class="ps-yr">(${esc(d.year)})</span></h2>
<p class="ps-ttl">${esc(d.title||"")}</p>
${chip||said.length?`<p class="ps-status">${chip?`<span class="ps-word ps-word-m">${esc(chip)}</span>`:""}${
  said.length?`<span>${said.join("; ")}</span>`:""}</p>`:""}
</div>${qr}</div>
<p class="ps-asof">${ctx.asOf?`The record as of ${esc(dateWords(ctx.asOf,"full"))}, printed `:"Printed "}<span class="ps-today">${
  esc(dateWords(ctx.today,"full"))}</span>. The official record at gc.nh.gov takes precedence.</p>
</header>`;
}

function glance(d,b,ctx,W){
  const sp=d.sponsors||[];
  const prime=sp.filter(s=>s.prime), cos=sp.filter(s=>!s.prime);
  // The row says "Prime sponsor", so the chip's own Prime label would say it
  // twice: the chip is drawn as a member's.
  const chips=xs=>xs.map(s=>pchip(Object.assign({},s,{role:"Member",prime:false}))).join(" ");
  const intro=((d.journey||{}).rail||[]).find(s=>s.stop==="Introduced"&&s.date);
  const where=W.body[String((prime[0]||{}).chamber||typeOf(d).charAt(0)).toUpperCase().charAt(0)];
  const law=((d.journey||{}).rail||[]).find(s=>s.stop==="Law"&&s.mark==="p"&&s.date);
  const cm=[d.house_committee&&cmteLink("House "+d.house_committee,d.term,null),
    d.senate_committee&&cmteLink("Senate "+d.senate_committee,d.term,null)].filter(Boolean);
  const ch=W.rsa(d).map(([n])=>esc(n));
  const subject=!(d.subject==="Miscellaneous"&&d.subject_source==="granite record")&&d.subject;
  const rows=[
    fact(prime.length>1?"Prime sponsors":"Prime sponsor",chips(prime)),
    fact(cos.length>1?"Cosponsors":"Cosponsor",chips(cos)),
    fact(cm.length>1?"Committees":"Committee",cm.join("; ")),
    fact("Introduced",intro?`${esc(dateWords(intro.date))}${where?`, in the ${esc(where)}`:""}`:""),
    fact("Chapter law",d.chapter?`Chapter ${esc(d.chapter)}, Laws of ${esc(d.year)}${
      law?`, in effect ${esc(dateWords(law.date))}`:""}`:""),
    fact(ch.length>1?"Amends RSA chapters":"Amends RSA chapter",ch.join(", ")),
    fact("Subject",subject?esc(subject):""),
    fact("Request number",d.lsr?`LSR ${esc(d.lsr)}`:""),
  ].join("");
  return rows?sec("","At a Glance",`<table class="ps-facts">${rows}</table>`):"";
}

function analysis(d){
  const a=(d.billtext||{}).analysis, st=(d.documents||[]).find(x=>x.kind==="status");
  return a?sec("summary","Official Legislative Analysis",`<p>${esc(a)}</p>${
    st?`<p class="ps-sm">Source: NH General Court, <span class="ps-addr">${esc(plain(st.url))}</span></p>`:""}`):"";
}

// HOW IT GOT HERE, ALWAYS: where the bill went, one line per decision, in
// the record's words. It is the rail said in words, which is why the
// rail's own table is not printed (the person, 9 October 2026).
function how(d,W){
  const st=(d.journey||{}).steps||[];
  const law=((d.journey||{}).rail||[]).find(s=>s.stop==="Law"&&s.date);
  if(!st.length)return "";
  return sec("","How It Got Here",`<table class="ps-how">${st.map(s=>{
    const day=s.date||(s.body==="L"&&law?law.date:"");
    return `<tr><th scope="row">${esc(W.body[s.body]||s.body)}</th><td class="ps-d">${
      day?esc(dateWords(day)):""}</td><td>${W.tally(esc(s.text||""))}</td></tr>`;}).join("")}</table>`);
}

function story(d,W){
  const v=d.veto_message;
  const parts=(d.stages||[]).length
    ?d.stages.map(s=>`<div class="ps-stage">${s.label?`<h4 class="ps-h4">${esc(s.label)}</h4>`:""}<p>${
      W.tally(esc(s.text))}</p>${(s.notes||[]).map(n=>`<p class="ps-note">${esc(n)}</p>`).join("")}</div>`).join("")
    :d.narrative?`<p>${W.tally(esc(d.narrative))}</p>`:"";
  const notes=(d.notes||[]).map(n=>`<p class="ps-note">${esc(n)}</p>`).join("");
  const veto=v&&(v.text||[]).length?`<div class="ps-stage"><h4 class="ps-h4">The Governor&rsquo;s Veto Message</h4>${
    v.text.map(p=>`<p>${esc(p)}</p>`).join("")}<p class="ps-sm">${esc(v.governor||"")}${
    v.date?`, ${esc(dateWords(v.date))}`:""}${(v.source||{}).name?`. Printed in ${esc(v.source.name)}`:""}${
    (v.source||{}).url?`, <span class="ps-addr">${esc(plain(v.source.url))}</span>`:""}.</p></div>`:"";
  return parts||notes||veto?sec("summary","The Story",notes+parts+veto):"";
}

function votes(d,st,W){
  const V=WORDBOOK.votes, rcs=d.rollcalls||[];
  const rows=rcs.map(rc=>{
    const vk=rc.vote_kind||"RC";
    const sub=[];
    if(rc.amendment)sub.push(`Amendment ${esc(rc.amendment)}`);
    if(rc.mover)sub.push(`Moved by ${esc(rc.mover)}`);
    const parties=Object.entries(rc.tally||{}).map(([p,t])=>{
      const off=Object.entries(t).filter(([k])=>k!=="Yea"&&k!=="Nay").reduce((x,[,c])=>x+c,0);
      return `<span class="ps-nw"><b>${esc(p)}</b> ${esc(t.Yea||0)} Yea, ${esc(t.Nay||0)} Nay${
        off?`, ${esc(off)} did not vote`:""}</span>`;}).join("; ");
    return `<tr><td class="ps-d">${esc(dateWords(rc.date))}<span class="ps-sub">${
      esc(W.body[rc.body]||rc.body)}</span></td><td><b class="ps-q">${esc(rc.question)}</b>${
      sub.map(x=>`<span class="ps-sub">${x}</span>`).join("")}${
      parties?`<span class="ps-sub">By party: ${parties}</span>`:""}${
      rc.threshold_note?`<span class="ps-sub">${esc(rc.threshold_note)}</span>`:""}${
      rc.outcome_conflict?`<span class="ps-sub">${esc(rc.outcome_conflict)}</span>`:""}</td><td>${
      esc(W.how[vk]||vk)}${rc.yeas!=null&&rc.nays!=null?`, ${tally(rc.yeas,rc.nays)}`:""}</td><td><span class="ps-word">${
      esc(rc.passed?V.passed:V.failed)}</span></td></tr>`;});
  const bl=d.ballot;
  if(bl){
    const y=bl.yes,n=bl.no,decided=!bl.pending&&y!=null&&n!=null;
    rows.push(`<tr><td class="ps-d">${esc(dateWords(bl.date))}<span class="ps-sub">The voters</span></td><td><b class="ps-q">${
      esc(bl.label||"")}</b><span class="ps-sub">State general election. An amendment to the constitution needs two thirds of the votes cast on it.</span><span class="ps-sub">Source: ${
      esc([bl.by,bl.cite].filter(Boolean).join(", "))}${bl.source?`, <span class="ps-addr">${esc(plain(bl.source))}</span>`:""}</span></td><td>${
      decided?`Statewide vote, ${tally(Number(y).toLocaleString("en-US"),Number(n).toLocaleString("en-US"))}`:"At the general election"}</td><td><span class="ps-word">${
      decided?(bl.ratified?"Ratified":"Not ratified"):"Still to come"}</span></td></tr>`);
  }
  if(!rows.length)return "";
  const names=st.names?rcs.filter(rc=>(rc.members||[]).length).map(rc=>{
    const groups=[["Yea","Yea"],["Nay","Nay"]].concat(W.other.map(([code,label])=>[code,label]));
    return `<div class="ps-roll"><h4 class="ps-h4">${esc(W.body[rc.body]||rc.body)} ${
      esc(W.how.RC)}, ${esc(dateWords(rc.date))}: ${esc(rc.question)}, member by member</h4>${
      groups.map(([code,label])=>{
        const ms=rc.members.filter(m=>m.v===code).sort((x,y)=>String(x.s||x.n).localeCompare(String(y.s||y.n)));
        return ms.length?`<h5 class="ps-h5">${esc(label)} <span>${ms.length}</span></h5><ul class="ps-names">${
          ms.map(m=>`<li>${esc(m.n)}</li>`).join("")}</ul>`:"";}).join("")}</div>`;}).join(""):"";
  return sec("votes","Votes",`<table class="ps-table ps-votes"><thead><tr><th scope="col">Day</th><th scope="col">The question</th>
<th scope="col">How it was taken</th><th scope="col">What it did</th></tr></thead><tbody>${rows.join("")}</tbody></table>${names}`);
}

function reports(d,W){
  const head=(r,cmte)=>`<h4 class="ps-h4">${esc([W.body[r.body||"H"],cmte].filter(Boolean).join(" "))} committee${
    r.date?`, ${esc(dateWords(r.date))}`:""}</h4>`;
  const written=(d.reports||[]).map(r=>{
    const cmte=((r.reports||[])[0]||{}).committee||"";
    return `<div class="ps-rep">${head(r,cmte)}${(r.reports||[]).map(e=>{
      const rec=e.side==="Minority"?r.minority_recommendation:r.majority_recommendation;
      return `<p class="ps-sub2">${rec?`<span class="ps-word">${esc(rec)}</span> `:""}<b>${esc(e.side||"Committee")}</b>${
        e.vote_yeas!=null&&e.vote_nays!=null?`, ${tally(e.vote_yeas,e.vote_nays)}`:""}${e.amendment?`, amendment ${esc(e.amendment)}`:""}${
        r.calendar?`, on the ${esc(r.calendar)}`:""}. ${e.author?`For the committee: ${esc(e.author)}. `:""}${
        r.cite?`Source: ${esc(r.body==="S"?r.cite:(r.source||r.cite))}.`:""}</p>${
        (e.text||"").trim()?`<p>${esc(e.text)}</p>`:e.note?`<p class="ps-note">${esc(e.note)}</p>`:""}`;}).join("")}</div>`;}).join("");
  const docket=(d.docket_reports||[]).map(r=>`<div class="ps-rep">${head(r,r.committee)}<p class="ps-sub2">${
    r.recommendation?`<span class="ps-word">${esc(r.recommendation)}</span> `:""}<b>${
    esc(r.side||"Committee")}</b>${r.vote_yeas!=null&&r.vote_nays!=null?`, ${tally(r.vote_yeas,r.vote_nays)}`:""}${
    r.amendment?`, amendment ${esc(r.amendment)}`:""}. As the docket records it; its written report is not on this site.</p></div>`).join("");
  return written||docket?sec("reports","Committee Reports",written+docket):"";
}

function docs(d){
  return (d.documents||[]).length?sec("docs","Documents",`<ul class="ps-docs">${
    d.documents.map(x=>`<li><b>${esc(x.label)}</b><span class="ps-addr">${esc(plain(x.url))}</span></li>`).join("")}</ul>`):"";
}

// ------------------------------------------------------------------ the text
const IND=n=>`ps-i${Math.min(4,Math.max(0,n||0))}`;
// Paragraphs of tokens. Marked: an amendment's words underlined or struck
// through in brackets, each run with its number; the General Court's own
// marks for the law as it stood (added in bold italics, removed struck)
// with none. Never colour alone.
function drawTokens(doc,marked){
  const paras=[];let cur=null;
  doc.forEach(t=>{
    if(t.w===PARA){cur={ind:t.ind,toks:[]};paras.push(cur);return;}
    if(!cur){cur={ind:0,toks:[]};paras.push(cur);}
    cur.toks.push(t);
  });
  const tag=g=>printed(g)?`<sup class="ps-tag"><span class="ps-vh">amendment </span>${esc(g)}</sup>`:"";
  return paras.filter(p=>p.toks.length).map(p=>{
    const runs=[];
    p.toks.forEach(t=>{
      const k=marked?[t.st,t.tag,t.f]:["eq",null,t.f], r=runs[runs.length-1];
      if(r&&r.k.join("\u0000")===k.join("\u0000"))r.ws.push(t.w);else runs.push({k,ws:[t.w]});
    });
    const html=runs.map(({k:[st,g,f],ws})=>{
      let x=esc(ws.join(" "));
      if(f==="add")x=`<b class="ps-law-add">${x}</b>`;else if(f==="cut")x=`<s class="ps-law-cut">${x}</s>`;
      return st==="add"?`<ins class="ps-ins">${x}</ins>${tag(g)}`
        :st==="del"?`<del class="ps-del">[${x}]</del>${tag(g)}`:x;
    }).join(" ");
    const gone=marked&&p.toks.every(t=>t.st==="del");
    return `<p class="ps-ln ${IND(p.ind)}${gone?" ps-gone":""}">${html}</p>`;
  }).join("");
}
function lines(body){
  const ls=String(body||"").split("\n").map(l=>l.trim());
  let s=ls.findIndex(l=>/^(STATE OF NEW HAMPSHIRE|Be it (Enacted|Resolved)|That the following|Whereas\b|RESOLVED\b)/i.test(l));
  if(s<0)s=0;
  return ls.slice(s).filter(Boolean).map(l=>`<p class="ps-ln ps-i0">${esc(l)}</p>`).join("");
}
const label=v=>{const t=String((v&&(v.title||v.label))||"");return t===t.toUpperCase()?t.charAt(0)+t.slice(1).toLowerCase():t;};

// The blame of a bill's versions, worked out once a bill and kept: HB 2 of
// 2025 is five versions of about 100,000 words.
const BLAMED=new WeakMap();
function blamed(d,ctx){
  const v=ctx.versions, ix=v.ix;
  if(BLAMED.has(ix))return BLAMED.get(ix);
  const vs=ix.versions||[], files=v.files||{};
  const docs=vs.map(x=>files[x.blocks_url||x.text_url]);
  if(docs.some(x=>x==null))return null;
  const steps=joinSteps(d,ix);
  const out=blame(docs.map(tokens),steps.map(s=>s.tag));
  settleShared(out.doc,steps);
  const by={};
  out.doc.forEach(t=>{if((t.st==="add"||t.st==="del")&&t.w!==PARA){
    const c=by[t.tag||""]=by[t.tag||""]||[0,0];c[t.st==="add"?0:1]++;}});
  const res={doc:out.doc,revised:out.revised,steps,by};
  BLAMED.set(ix,res);
  return res;
}

function amendmentList(d,B,W){
  const count=t=>{const c=B.by[t]||[0,0];
    return `${c[0].toLocaleString("en-US")} word${c[0]===1?"":"s"} put in, ${
      c[1].toLocaleString("en-US")} taken out`;};
  const vline=v=>`the text &ldquo;${esc(label(v))}&rdquo; (${esc(W.day(v.date))})`;
  const amd=a=>`<b>Amendment ${esc(a.num)}</b>, ${esc(a.kind||"Amendment")}${
    a.proposed_by?` (${esc(a.proposed_by)})`:a.mover?` (moved by ${esc(a.mover)})`:""}; adopted in the ${
    esc(W.body[a.body]||a.body)}, ${esc(dateWords(a.date))}${W.how[a.vote_kind]?` (${esc(W.how[a.vote_kind])})`:""}.${
    (a.targets||[]).includes("the whole bill")?" It replaced everything after the enacting clause.":""}`;
  const item=(tag,html)=>`<li><span class="ps-tagk">${printed(tag)?esc(tag):"&ndash;"}</span><div>${html}</div></li>`;
  const out=[];
  B.steps.forEach(s=>{
    if(s.kind==="one")out.push(item(s.tag,`${amd(s.a)} It made ${vline(s.v)}: ${count(s.tag)}.`));
    else if(s.kind==="step"){
      s.made.forEach(x=>out.push(item(x.tag,`${amd(x.a)} A change it made is numbered ${esc(x.tag)} where its own text holds the new words: ${count(x.tag)}.`)));
      out.push(item(s.tag,`${vline(s.v)} carried amendments ${s.with.map(esc).join(" and ")} together, and the record cannot say which of them made a change numbered ${esc(s.tag)}: ${count(s.tag)}.`));
    }
    // A step no amendment made that changed no word of the text printed here
    // -- its version differs from the one before only above STATE OF NEW
    // HAMPSHIRE, where the stamps, sponsors and analysis are -- has nothing
    // to number or list.
    else if(!(B.by[s.tag]||[0,0]).some(Boolean))return;
    else if(s.kind==="chaptered")out.push(item("C",`<b>The chaptered text</b>, ${vline(s.v)}. Not an amendment: the record joins no adopted amendment to this step, so these are the changes made in chaptering it. ${count("C")}.`));
    else out.push(item(s.tag,`${vline(s.v)}: the record joins no adopted amendment to this step, so its changes are marked with no number. ${count(s.tag)}.`));
  });
  const name=t=>t==="C"?"the chaptered text":printed(t)?`amendment ${esc(t)}`:"a step with no number";
  const rev={};
  B.revised.forEach(([later,earlier])=>{(rev[later]=rev[later]||new Set()).add(earlier);});
  const said=Object.keys(rev).map(l=>`${name(l)} took out words ${[...rev[l]].map(name).join(" and ")} had put in`);
  return `<ol class="ps-amds">${out.join("")}</ol>${said.length?`<p class="ps-sm">Words one amendment put in and a later one took out are in neither the introduced text nor this one, so they are not shown: ${said.join("; ")}.</p>`:""}`;
}

function text(d,ctx,st,W){
  const h=has(d,ctx);
  if(!h.text)return "";
  const choice=textChoice(d,ctx,st), v=ctx.versions||{}, ix=v.ix, files=v.files||{};
  const vs=(ix&&ix.versions)||[];
  const wait=`<p class="ps-sm">Loading the bill&rsquo;s text&hellip;</p>`;
  const got=x=>x&&files[x.blocks_url||x.text_url];
  // Whether the files a choice draws from are here: "" when they are, "wait"
  // while one is on its way, and a note where one could not be had.
  const state=xs=>{
    const fs=xs.map(x=>files[x]), bad=fs.find(x=>x&&x.error);
    return bad?`<p class="ps-sm">Part of the bill&rsquo;s text could not be loaded (${esc(bad.error)}). The Documents list gives the General Court&rsquo;s own.</p>`
      :fs.some(x=>x===undefined)?wait:"";
  };
  const urls=xs=>xs.map(x=>x&&(x.blocks_url||x.text_url)).filter(Boolean);
  const law=!!d.chapter;
  let body="";
  if(hasIndex(d)&&!ix)body=v.error?`<p class="ps-sm">The versions of this bill could not be loaded (${esc(v.error)}).</p>`:wait;
  else if(choice==="marked"){
    const B=state(urls(vs))||blamed(d,ctx);
    const still=typeof B!=="string"&&!Object.values(B.by).some(c=>c[0]||c[1]);
    body=typeof B==="string"?B:still?`<p class="ps-sm">${law?"The text as it became law":"The latest text"} (${
      esc(label(vs[vs.length-1]))}, ${esc(W.day(vs[vs.length-1].date))}). No word of it changed between its ${
      vs.length} versions, so nothing is marked. The bill&rsquo;s own changes to the law as it stood are printed as the General Court prints them.</p><div class="ps-text">${
      drawTokens(B.doc,false)}</div>`:`<p class="ps-sm">${law?"The text as it became law":"The latest text"} (${esc(label(vs[vs.length-1]))}, ${
      esc(W.day(vs[vs.length-1].date))}), with every change since it was introduced marked and numbered by the amendment that made it.</p>
${amendmentList(d,B,W)}
<div class="ps-legend"><p><b>How the changes are marked.</b> <ins class="ps-ins">Underlined</ins><sup class="ps-tag">1</sup>: words an amendment put in, with its number. <del class="ps-del">[Struck through, in brackets]</del><sup class="ps-tag">1</sup>: words an amendment took out, with its number.</p>
<p>The bill&rsquo;s own changes to the law as it stood are printed as the General Court prints them, with no number: <b class="ps-law-add">law added in bold italics</b>, law removed <s class="ps-law-cut">struck through</s> inside its brackets.</p></div>
<div class="ps-text">${drawTokens(B.doc,true)}</div>`;
  }else if(choice==="clean"){
    const last=vs[vs.length-1];
    body=vs.length?(state(urls([last]))||`<p class="ps-sm">${law?"The text as it became law":"The latest text"} (${
      esc(label(last))}, ${esc(W.day(last.date))}), clean. The bill&rsquo;s own changes to the law as it stood are printed as the General Court prints them.</p><div class="ps-text">${
      drawTokens(tokens(got(last)),false)}</div>`)
      :`<p class="ps-sm">The text as the record holds it${(d.billtext||{}).version?` (${esc(label({title:d.billtext.version}))})`:""}. The record holds one version, so no change is marked; text in [brackets] is being removed from the law as it stood.</p><div class="ps-text">${lines(d.billtext.body)}</div>`;
  }else if(choice==="introduced"){
    body=state(urls([vs[0]]))||`<p class="ps-sm">The text as introduced (${esc(W.day(vs[0].date))}).</p><div class="ps-text">${drawTokens(tokens(got(vs[0])),false)}</div>`;
  }else if(choice==="amendments"){
    const own=ix&&(ix.amendments||[]).length
      ?ix.amendments.map(a=>state([a.text_url])||`<h4 class="ps-h4">Amendment of ${esc(W.day(a.date))}</h4><p class="ps-flat">${
        esc(String(files[a.text_url]).replace(/\f/g," ").trim())}</p>`).join("")
      :(d.amendments||[]).filter(a=>String(a.text||"").trim()).map(a=>`<h4 class="ps-h4">Amendment ${esc(a.num)}${
        a.date?`, ${esc(dateWords(a.date))}`:""}${a.adopted===true?", adopted":a.adopted===false?", not adopted":""}</h4><p class="ps-flat">${esc(a.text)}</p>`).join("");
    body=`<p class="ps-sm">Each amendment&rsquo;s own text, as the General Court published it. Text in [brackets] is being removed.</p>${own}`;
  }
  return sec("text","The Bill&rsquo;s Text",body);
}

// The sheet, as it prints: the sections the settings ask for, in order. `ctx`
// is what the page knows beyond the record: {url, asOf, today, versions:
// {ix, files, error}, words}. Pure: the same record and settings draw the
// same sheet.
function sheet(d,b,ctx,st){
  const W=ctx.words||pageWords(), h=has(d,ctx);
  const on=k=>h[k]&&st.sec[k];
  const textOn=on("text")&&!(isLong(d,ctx)&&!st.long);
  return `<div class="ps-sheet">${masthead(d,b,ctx,st,W)}${glance(d,b,ctx,W)}${
    on("summary")?analysis(d):""}${how(d,W)}${on("summary")?story(d,W):""}${
    on("votes")?votes(d,st,W):""}${on("reports")?reports(d,W):""}${
    textOn?text(d,ctx,st,W):""}${on("docs")?docs(d):""}</div>`;
}

// The settings: what the sheet holds, and which text. Only what this record
// has is offered.
function menu(d,b,ctx,st){
  const h=has(d,ctx), num=`${numberOf(d,b)}`, law=!!d.chapter;
  const box=(k,label,on,hint,cls)=>`<label class="ps-opt${cls?" "+cls:""}"><input type="checkbox" ${k}${
    on?" checked":""}><span>${label}${hint?`<span class="ps-hint">${hint}</span>`:""}</span></label>`;
  const nRc=(d.rollcalls||[]).filter(r=>(r.members||[]).length).length;
  const long=isLong(d,ctx);
  const radio=(v,label)=>h[v]?`<label class="ps-opt"><input type="radio" name="ps-text" value="${v}"${
    textChoice(d,ctx,st)===v?" checked":""}><span>${label}</span></label>`:"";
  return `<form class="ps-form" novalidate>
<h3 class="ps-mh" id="ps-mh">Print This Bill</h3>
<p class="ps-mlead">A reference sheet of ${esc(num)}&rsquo;s record, for paper. It reads in black and white: nothing on it is said by colour alone.</p>
<fieldset class="ps-fs"><legend>What the sheet holds</legend>
<p class="ps-always">Always: the bill&rsquo;s number, title and status, At a Glance${
  ((d.journey||{}).steps||[]).length?", and How It Got Here":""}.</p>
${h.summary?box('data-sec="summary"',"The analysis and the story",st.sec.summary):""}
${h.votes?box('data-sec="votes"',"Votes",st.sec.votes):""}
${h.names?box('data-opt="names"',"Each member&rsquo;s vote on a roll call",st.names,
  `About a page for each House roll call: this bill has ${nRc===1?"one":nRc}.`,"ps-optsub"):""}
${h.reports?box('data-sec="reports"',"Committee reports",st.sec.reports):""}
${h.text?box('data-sec="text"',"The bill&rsquo;s text",st.sec.text&&(!long||st.long),
  long?`About ${pagesOf(d,ctx)} pages, so it is left off unless you tick it.`:""):""}
${h.docs?box('data-sec="docs"',"Documents, with their addresses",st.sec.docs):""}
${box('data-opt="qr"',"A QR code to this bill&rsquo;s page",st.qr)}
</fieldset>
${h.text?`<fieldset class="ps-fs ps-textfs"><legend>The bill&rsquo;s text</legend>
${radio("marked",`${law?"As it became law":"The latest text"}, with each amendment&rsquo;s changes marked and numbered`)}
${radio("clean",`${law?"As it became law":"The latest text"}, clean`)}
${radio("amendments","Each amendment&rsquo;s own text")}
${radio("introduced","As introduced")}
</fieldset>`:`<p class="ps-mlead">The record holds no text of this bill: the Documents list gives the General Court&rsquo;s own.</p>`}
<div class="ps-btns"><button type="button" class="ps-btn ps-do" data-ps="print">Print</button><button type="button" class="ps-btn" data-ps="close">Back to the bill</button></div>
<p class="ps-live" role="status" aria-live="polite"></p>
<p class="ps-keep">Your choices are kept in this browser only, for the next bill you print. The paper size is your printer&rsquo;s: Letter or A4.</p>
</form>`;
}

// ================================================================== ON A PAGE
// The day, as the browser's clock has it, for "printed ...".
function today(){
  const t=new Date();
  return [t.getFullYear(),String(t.getMonth()+1).padStart(2,"0"),String(t.getDate()).padStart(2,"0")].join("-");
}
// Each printed page's foot: the bill, its address, and page n of m (Chrome
// 131 and later draw @page's margin boxes; another browser prints without).
// The words are this bill's, so the rule is written when the sheet opens and
// taken away when it closes. CSS strings escape a quote and a backslash.
function pageFoot(d,b,url){
  const q=s=>String(s).replace(/[\\"]/g,c=>"\\"+c).replace(/\n/g," ");
  return `@page{@bottom-left{content:"${q(`${numberOf(d,b)} (${d.year})`)} \\00B7  ${q(plain(url))}"}}`;
}
function urlOf(d){
  const c=document.querySelector('link[rel="canonical"]');
  const h=c&&c.getAttribute("href");
  return h&&/\/bill\/\d{4}\/[a-z0-9]+$/i.test(h)?h
    :`https://graniterecord.org/bill/${d.year}/${String(d.id||"").toLowerCase()}`;
}
let OPEN=null;
const VCACHE={};

function close(){
  if(!OPEN)return;
  const o=OPEN;OPEN=null;
  o.layer.remove();o.foot.remove();
  document.documentElement.classList.remove("ps-open");
  o.inerted.forEach(el=>{el.inert=false;});
  window.removeEventListener("beforeprint",o.stamp);
  document.removeEventListener("keydown",o.key,true);
  if(o.back&&o.back.focus)o.back.focus();
}

function open(d,b,opts){
  if(!d||!d.id)throw new Error("GRPrint.open needs the bill's record");
  close();
  opts=opts||{};
  // The stylesheet the first time: the layer waits for it, hidden, rather
  // than covering the page with a sheet drawn unstyled.
  let css=document.querySelector('link[data-ps-css]');
  const fresh=!css;
  if(fresh){
    const l=document.createElement("link");
    l.rel="stylesheet";l.href="/print.css";l.setAttribute("data-ps-css","");
    document.head.appendChild(l);
    css=l;
  }
  const st=loadSettings();
  const key=verKey(d);
  const ctx={url:opts.url||urlOf(d),asOf:opts.asOf||"",today:today(),
    words:pageWords(),versions:VCACHE[key]||(VCACHE[key]={ix:null,files:{},error:""})};
  const layer=document.createElement("div");
  layer.className="ps-layer";
  layer.hidden=fresh;
  layer.setAttribute("role","dialog");layer.setAttribute("aria-modal","true");
  layer.setAttribute("aria-labelledby","ps-h");
  layer.innerHTML=`<div class="ps-wrap"><header class="ps-head"><h2 class="ps-h" id="ps-h" tabindex="-1">Print ${
    esc(numberOf(d,b))} <span class="ps-yr">(${esc(d.year)})</span></h2>
<p class="ps-lead">The sheet as it prints, beside its settings. Nothing is printed until you press Print; your browser&rsquo;s own dialog then sends it to paper or to a PDF.</p></header>
<div class="ps-layout"><article class="ps-paper" aria-label="The print sheet for ${esc(numberOf(d,b))} (${esc(d.year)}), as it prints"></article>
<aside class="ps-menu" aria-labelledby="ps-mh"></aside></div></div>`;
  const paper=layer.querySelector(".ps-paper"), side=layer.querySelector(".ps-menu");
  const foot=document.createElement("style");
  foot.setAttribute("data-ps-foot","");
  foot.textContent=pageFoot(d,b,ctx.url);
  const inerted=[...document.body.children].filter(el=>!el.inert&&el.tagName!=="SCRIPT");
  inerted.forEach(el=>{el.inert=true;});
  document.head.appendChild(foot);
  document.body.appendChild(layer);
  document.documentElement.classList.add("ps-open");

  const status=()=>layer.querySelector(".ps-live");
  const draw=()=>{
    paper.innerHTML=sheet(d,b,ctx,st);
    const want=needs(d,ctx,st), btn=layer.querySelector('[data-ps="print"]');
    if(btn)btn.disabled=want.length>0;
    if(status())status().textContent=want.length?"Loading the bill’s text…":"";
    want.forEach(u=>{
      if(ctx.versions.files[u]!==undefined||ctx.versions.asked&&ctx.versions.asked[u])return;
      (ctx.versions.asked=ctx.versions.asked||{})[u]=1;
      fetch(new URL(u.replace(/^\//,""),location.origin+"/").href)
        .then(r=>r.ok?(u.endsWith(".json")?r.json():r.text()):Promise.reject(new Error("HTTP "+r.status)))
        .then(x=>{ctx.versions.files[u]=x;})
        .catch(e=>{ctx.versions.files[u]={error:e.message||String(e)};})
        .then(()=>{if(OPEN&&OPEN.layer===layer)draw();});
    });
  };
  const sync=()=>{
    const f=side.querySelector("form");
    if(!f)return;
    f.querySelectorAll("input[data-sec]").forEach(i=>{
      const k=i.getAttribute("data-sec");
      i.checked=!!st.sec[k]&&(k!=="text"||!isLong(d,ctx)||!!st.long);});
    const nm=f.querySelector('input[data-opt="names"]');
    const row=nm&&nm.closest(".ps-opt");
    if(nm){nm.checked=!!st.names;nm.disabled=!st.sec.votes;}
    if(row)row.classList.toggle("is-off",!st.sec.votes);
    const textOn=!!st.sec.text&&(!isLong(d,ctx)||!!st.long);
    f.querySelectorAll('input[name="ps-text"]').forEach(r=>{r.checked=r.value===textChoice(d,ctx,st);r.disabled=!textOn;});
    const tf=f.querySelector(".ps-textfs");if(tf)tf.classList.toggle("is-off",!textOn);
  };
  side.innerHTML=menu(d,b,ctx,st);
  side.addEventListener("change",e=>{
    const t=e.target;
    if(t.hasAttribute("data-sec")){
      const k=t.getAttribute("data-sec");
      if(k==="text"&&isLong(d,ctx))st.long=t.checked?1:0;
      else st.sec[k]=t.checked?1:0;
    }
    else if(t.getAttribute("data-opt")==="names")st.names=t.checked?1:0;
    else if(t.getAttribute("data-opt")==="qr")st.qr=t.checked?1:0;
    else if(t.name==="ps-text")st.text=t.value;
    saveSettings({sec:st.sec,names:st.names,qr:st.qr,text:st.text});
    sync();draw();
  });
  side.addEventListener("click",e=>{
    const a=e.target.closest("[data-ps]");
    if(!a)return;
    if(a.getAttribute("data-ps")==="print"&&!a.disabled)window.print();
    if(a.getAttribute("data-ps")==="close")close();
  });
  const stamp=()=>{ctx.today=today();layer.querySelectorAll(".ps-today").forEach(x=>{x.textContent=dateWords(ctx.today,"full");});};
  const key_=e=>{if(e.key==="Escape"&&OPEN){e.preventDefault();close();}};
  window.addEventListener("beforeprint",stamp);
  document.addEventListener("keydown",key_,true);
  OPEN={layer,foot,inerted,stamp,key:key_,back:document.activeElement};

  // The versions, where the record says there are some, once a bill.
  if(hasIndex(d)&&!ctx.versions.ix&&!ctx.versions.asking){
    ctx.versions.asking=1;
    fetch(new URL(`versions/${key}.json`,location.origin+"/").href)
      .then(r=>r.ok?r.json():Promise.reject(new Error("HTTP "+r.status)))
      .then(j=>{ctx.versions.ix=j;})
      .catch(e=>{ctx.versions.error=e.message||String(e);})
      .then(()=>{if(OPEN&&OPEN.layer===layer){side.innerHTML=menu(d,b,ctx,st);sync();draw();}});
  }
  // The day the record was built, for "The record as of": build.json, as the
  // page's own footer reads it.
  if(!ctx.asOf)fetch(new URL("build.json",location.origin+"/").href)
    .then(r=>r.ok?r.json():null).then(j=>{
      if(j&&j.finished&&OPEN&&OPEN.layer===layer){ctx.asOf=String(j.finished).slice(0,10);draw();}})
    .catch(()=>{});
  sync();draw();
  const show=()=>{
    if(!OPEN||OPEN.layer!==layer)return;
    layer.hidden=false;
    const h=layer.querySelector("#ps-h");if(h&&h.focus)h.focus();
  };
  if(fresh){css.addEventListener("load",show);css.addEventListener("error",show);}
  else show();
  return layer;
}

return {open,close,sheet,menu,needs,has,defaults,pageWords,
  qr:{encode:qrEncode,read:qrRead,svg:qrSvg},
  text:{tokens,diff:diffTokens,blame,joinSteps,vday},
  PER_PAGE,LONG_PAGES};
})();
