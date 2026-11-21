// BILLMATCH:BEGIN
/* Bills are drafted in statutory vocabulary; people search in ordinary words.
   "AN ACT relative to the state minimum hourly rate" will never be found by
   someone typing "minimum wage". These are GROUPS rather than mappings: every
   term in a group matches every other, so nothing is declared the real name for
   anything else. That matters on contested subjects, where deciding that one
   word "means" another is a framing choice rather than a translation. Matching
   is by substring, so a singular form also catches its plural.
   A term is written with spaces, never a hyphen: titles are searched with
   their hyphens read as spaces, so "gender-affirming" sat in this list for
   weeks and could not match one (1 October). */
const SYN=[
  ["gun","firearm","weapon","pistol","rifle"],
  ["school","education","student","teacher","classroom"],
  // Not "revenue": the Department of Revenue Administration is named in bills
  // that levy nothing.
  ["tax","taxation","levy"],
  // Three groups where there was one: "zoning" returned every landlord-tenant
  // bill of the term, 166 of them, because all six words shared a group.
  ["housing","dwelling"],
  // Not "lease" (the state leases buildings) nor "subdivision" (every
  // "political subdivision"): measured, both pulled in bills about neither.
  ["landlord","tenant","eviction","rental housing"],
  ["zoning","land use","planning board"],
  ["childcare","daycare"],
  ["marijuana","cannabis","thc"],
  ["dui","dwi","intoxicated","impaired driving"],
  // Not "insurance": a search for health returned every auto and home policy bill.
  ["healthcare","health care","health","medical"],
  ["police","law enforcement","police officer","peace officer","sheriff"],
  ["veteran","military","national guard","armed forces"],
  ["elderly","senior","older adult","aging"],
  ["vote","voting","election","ballot","absentee","voter"],
  // Broadband is internet ACCESS: with "internet" and "telecommunication" in
  // the group it returned obscenity filters and wiretaps.
  ["broadband","internet service","high speed internet"],
  ["road","highway","transportation","bridge"],
  // "greenhouse gas", not "greenhouse": a cannabis greenhouse came up for "solar".
  ["climate","emission","greenhouse gas","renewable","solar"],
  ["trash","landfill","solid waste","recycling"],
  // Two groups: "opioids" found the prescription drug affordability board.
  // "narcan": three titles say it, and it listed nothing in a term where
  // eight bills are about the drug it is the brand of (2 October).
  ["opioid","fentanyl","narcotic","heroin","overdose","naloxone","narcan","substance use",
   "substance misuse","addiction"],
  ["drug","controlled substance"],
  ["vaccine","vaccination","immunization"],
  ["betting","wagering","gambling","casino"],
  ["abortion","reproductive","pregnancy termination"],
  ["transgender","gender identity","gender affirming"],
  ["immigration","immigrant","noncitizen","alien"],
  ["minimum wage","hourly rate","wage"],
  ["union","collective bargaining"],
  // Two groups: "pfas" found every bill naming water, docks and dams included.
  ["water","groundwater","drinking water"],
  // "perfluorinated" and "polyfluorinated": thirteen titles since 2018 say
  // "perfluorinated chemicals", and a signed law of 2025 on ski wax says
  // "per and polyfluorinated alkyl substances" (2 October).
  ["pfas","perfluoroalkyl","polyfluoroalkyl","perfluorinated","polyfluorinated",
   "forever chemical"],
  // The statutes say "number plate" -- 132 titles since 1989 -- and people
  // say "license plate", which 61 do.
  ["license plate","number plate"],
  // "jail" found nothing: the record says "county correctional facility".
  ["prison","jail","correctional","department of corrections","inmate","incarcerated","incarceration"],
  ["court","judicial","judge","judiciary"],
  ["property tax","assessment","abatement"],
  ["energy","electric","ratepayer"],
  ["mental health","behavioral health","mental illness","psychiatric"],
  ["disability","disabled","accessible","accessibility"],
  ["farm","agriculture","livestock","dairy"],
];
/* A WORD SOMEBODY TYPES IS NOT A PROPERTY OF AN OBJECT. These tables are
   looked up by whatever was typed, and "constructor" is a word: on a plain
   object SYNMAP["constructor"] is a function, the search took it for a group
   of synonyms and stopped with a TypeError, and the page drew nothing (2
   October; so did "__proto__"). Every table a typed word is looked up in is
   made with no prototype, and a list read out of a fetched file is checked
   to be a list before it is read. */
const SYNMAP=Object.create(null);
SYN.forEach(g=>g.forEach(t=>{SYNMAP[t]=g;}));
/* AN APOSTROPHE TYPED ON A PHONE IS A CURLY ONE. "driver's license" found 8
   bills and the same words from an iPhone keyboard found none; "children's"
   9 against none (1 October). The mark is inside the word, so taking marks
   off the ends of words never reached it. The search reads a curly one as a
   straight one, and a straight one in a term matches either in a title --
   119 titles across the nineteen terms are printed with the curly one. */
const rxEsc=t=>t.replace(/[.*+?^${}()|[\]\\]/g,"\\$&").replace(/'/g,"['’]");
// Match at a word boundary, not anywhere in the string. Plain substring search
// makes "gun" hit "begun" and "act" hit "enacted". Matching at the START of a
// word still catches plurals and endings, so "firearm" finds "firearms" and
// "incarcerat" finds "incarcerated".
const RXC=Object.create(null);
function hasTerm(hay, term){
  if(term.includes(" ")&&!term.includes("'")) return hay.includes(term);
  let rx=RXC[term];
  if(!rx){ rx=new RegExp("\\b"+rxEsc(term));
           RXC[term]=rx; }
  return rx.test(hay);
}

function expand(word){
  // The original word is ALWAYS kept. Dropping it silently narrows the search:
  // "care" is a prefix of "child care", so without this a search for "care"
  // would match childcare bills and stop matching "health care" — worse than
  // having no synonyms at all.
  //
  // Partial matches need at least four characters, so "gun" does not fire on
  // "begun" and short words do not drag in whole groups.
  // The word's own entry first. "wage" is in the minimum wage group; taking
  // the longest entry it begins put it in the gambling group, by "wagering",
  // and "minimum wage" returned the minimum age for sports betting.
  if(SYNMAP[word])return [...new Set([word, ...SYNMAP[word]])];
  let best=null;
  for(const t in SYNMAP){
    // Prefix match, not "contains anywhere". "guns" should reach the firearm
    // group; "begun" should not, and it does under a contains test. Only
    // one-word entries: "minimum" is not a way of saying "minimum wage", and
    // reading it as one made every bill saying "wage" twice a match.
    if(t.includes(" "))continue;
    // A longer entry the word begins only for a word of six letters or more:
    // "rates" begins "ratepayer", and "electric rates" found 77 energy bills.
    const hit = word.length>=4 && (word.startsWith(t)||(word.length>=6&&t.startsWith(word)));
    if(hit && (!best||t.length>best.length)) best=t;
  }
  return best ? [...new Set([word, ...SYNMAP[best]])] : [word];
}

/* THE WORDS A QUESTION IS ASKED IN. Measured on 14 September against 36
   everyday searches: every word had to match, so "bills about guns" and "bail
   reform" found nothing, and "public education funding" found 11 bills where
   "education funding" found 95. A plural ("rentals") did not find its singular
   and a hyphen ("short-term") did not find its two words. So: words that carry
   no subject are skipped, unless they are all a search has; a plural is read
   as its singular; hyphens are spaces on both sides. */
const STOP=[
  "a","an","the","of","and","or","for","to","in","on","at","by","about","with",
  "from","regarding","relative","related","relating","concerning","bill","bills",
  "law","laws","act","acts","legislation","nh","hampshire","reform","reforms",
  "committee","committees",
  // A word for an attitude toward a subject, not for the subject (1 October):
  // "hormone therapy ban" found nothing, because no title says "ban" -- they
  // say "prohibiting" -- and nor did "anti trans" or "assault weapons ban".
  "ban","bans","banned","banning","anti"
];
const STOPSET=new Set(STOP);
/* THE WORDS PEOPLE TYPE THAT NO BILL USES. Nobody files a "bathroom bill" or
   writes "weed" or "ICE" into a statute. The person, 1 October: "typing lgbtq
   or trans doesn't show the several bathroom ban bills put forward this past
   session, or the hormone therapy ban" -- "lgbtq" found nothing, and "trans"
   found 162 bills titled transfer, transparency and transportation or heard
   by a Transportation committee.

   THIS TABLE IS THE SMALLER HALF OF THE ANSWER. It was written first, alone,
   and measured on fifteen searches nobody had written an entry for: it
   recovered none of them. A table covers what somebody thought of. The larger
   half is below it (THE BILLS' OWN WORDS): the search now reads each bill's
   topic, the drafters' analysis and the text itself, so a word a bill uses is
   found without anyone having listed it. The table is for the rest -- the
   word a reader types that the bills never use ("lgbtq", "weed", "bathroom
   bill", "drunk driving"), and the phrase that must be read as one thing
   ("income tax" is not every bill with "income" and "tax" in it).

   Each entry is a FINDING AID and nothing more: `ask` is what a person might
   type, `terms` is wording the bills themselves use. It says "a reader who
   types one of these is shown the bills that say one of those". It never
   says what a bill is, whom it helps or which side it is on, and it is never
   printed as a label on a bill. Three rules keep it that way:

   - THE BILL'S OWN WORDS OR NOTHING. A term goes in because bills print it,
     in a title, an analysis or their text, and for no other reason: not who
     sponsored a bill, not what a newspaper called it, not what it would do in
     practice. A bill is listed because ITS OWN title, analysis or text has
     the term. SB 520 of 2026, "relative to breast surgeries for minors", was
     listed under "lgbtq" and "sex change" by its title alone; its text is
     about breast reduction for musculoskeletal pain and never mentions
     gender, and it is not listed now. HB 712, with the same words in its
     title, is: its text says "transgender" and "gender reassignment".
     preflight reads every term against every term's titles and search index
     and fails on one that no bill has ever used.
   - EVERY SIDE'S WORD FOR A SUBJECT, ONE LIST. "gun control" and "gun rights"
     return the same bills; so do "pro life" and "pro choice", "gender
     identity" and "biological sex", "trans rights" and "gender ideology",
     "sex change" and "gender affirming care". preflight holds those pairs to
     identical results: if two ever differ, the table has taken a side.
   - WHAT THE READER SEES IS THE BILL'S WORDING. The words typed are never
     shown back as a description. The line under the search box lists the
     terms the bills were searched for, and a bill listed for a word its
     title does not have says which of its own words put it there ("text
     says: lavatory"), so anyone can see why a bill is in the list and argue
     with the list.

   HOW AN ENTRY IS READ. The longest ask is taken first and what it covers is
   not read again. A word or phrase found here is read WHOLE, never as the
   start of a longer word -- that is what stops "trans" being transfer and
   "adu" being adult -- and it stands for the entry's terms instead of
   anything SYN says about it ("teachers" was every school bill of the term,
   321, through SYN). A plural reaches an entry only if the entry lists it:
   "weeds" is aquatic weeds, and was 23 bills about cannabis while the table
   took the s off for itself. A term matches as itself or with an ending. An
   entry marked `also` is the exception, for a word whose older behaviour the
   person ruled on (25 September) and a check holds: "gun" keeps its SYN
   group and still finds the Gunstock Area Commission lower down, "bail"
   still finds the bailiffs, and the entry's terms are added after them.

   THREE THINGS AN ENTRY MAY SAY BESIDES ITS TERMS, each because a bare list
   of terms listed the wrong bills when it was read against the text:
   - `named`: wording that counts where a bill is named or summarised -- its
     title or its analysis -- and not in the body of its text. "gender
     identity" and "sexual orientation" are printed once each wherever a
     statute lists who may not be discriminated against: in a housing voucher
     bill, a zoning bill, a resolution on bearing arms. A bill whose title or
     analysis says them is about them.
   - `with`: a second list, one of which the bill must also say. The four
     vetoed bills the person meant say "lavatory" once, in the text; so do a
     rent registry and a bill on dwellings over water say "bathroom". A
     lavatory AND biological sex is the eight bills. A bill whose TITLE has
     the reader's own word, or a term the entry also lists as an ask, stands
     without it: "restroom" still lists restroom access for truck drivers.
     With `once` beside it, and only then, a single mention in a bill's text
     counts for either list: that is the bathroom and the sports entries,
     and not voter ID, where it listed every absentee ballot bill that
     mentions photo identification in passing.
   - `not`: a title phrase that takes a bill out of what the terms found.
     "digital assets" is what the statutes call cryptocurrency, and the
     Uniform Fiduciary Access to Digital Assets Act is about a dead person's
     email.
   And one that is not about the text at all:
   - `like`: a word of SYN whose group the ask is read as, in a title, as
     if the reader had typed that word ("cops", like "police").

   WHERE A BILL FOUND THIS WAY IS LISTED: after every bill that has the
   reader's own word, and after a bill that has only a longer word it begins
   (looseness, below). "undocumented" lists the two titles that say so first.

   tests/search_cases.json holds real searches to the real bills they must
   and must not return, each named with its title as the record has it. */
const CONCEPTS=[
  // --- gender identity, sex and sexual orientation ---------------------
  // A bill is in whichever of these its own words put it in, whatever it
  // would do: the amendment protecting the right to marry is listed beside
  // the bill removing gender identity from the statutes.
  // Not "basis of sex" alone: it listed the resolution marking the amendment
  // that gave women the vote. Not "pronoun" alone: the analysis of a bill
  // making the register of deeds chapter gender neutral says it. Not "gender
  // dysphoria": a bill on reproductive care says it twice.
  {ask:["lgbtq","lgbt","lgbtqia","glbt","gay","gays","lesbian",
    "lesbians","queer","bisexual","homosexual","homosexuality","gay rights",
    "lgbtq rights","lgbt rights","lgbtq youth","lgbtq kids","lgbtq students",
    "sexual orientation"],
   terms:["homosexual","transsexual","transgender","biological sex","gender transition",
    "gender affirming","gender reassignment","sex reassignment","puberty blocker",
    "puberty blocking","cross sex hormone","alter a minor's gender","gender designation",
    "facilities on the basis of sex","personal identity ideology","names and pronouns",
    "conversion therapy"],
   named:["gender identity","gender expression","sexual orientation","hormone treatment",
    "same sex","same gender","right to marry","civil union","civil marriage"]},
  // Both sides' words are asks here, and return one list: "gender identity"
  // listed 19 bills and "biological sex" 10 while only the first was one.
  {ask:["trans","transgender","transgendered","transsexual","trans rights",
    "transgender rights","trans people","transgender people","trans kids",
    "transgender kids","trans youth","transgender youth","trans women","trans men",
    "nonbinary","non binary","gender identity","gender expression","gender ideology",
    "biological sex","biological male","biological males","biological female",
    "biological females"],
   terms:["transsexual","transgender","biological sex","gender transition","gender affirming",
    "gender reassignment","sex reassignment","puberty blocker","puberty blocking",
    "cross sex hormone","alter a minor's gender","gender designation",
    "facilities on the basis of sex","personal identity ideology","names and pronouns"],
   named:["gender identity","gender expression","hormone treatment"]},
  // No title says bathroom. The bills say "lavatory facilities or locker
  // rooms" in their text, and for four of the eight nowhere else, once.
  // Not "gender identity" in `with`: a 2021 landlord and tenant omnibus
  // counts bathrooms and lists who may not be discriminated against.
  {ask:["bathroom","bathrooms","restroom","restrooms","lavatory","lavatories",
    "bathroom bill","bathroom bills","bathroom ban","bathroom bans","locker room",
    "locker rooms","single sex spaces","women's spaces"],
   terms:["bathroom","restroom","lavatory","locker room"],
   with:["biological sex","basis of sex","transgender"],once:true},
  // Three entries, so that "hormone therapy" is not answered with the
  // surgery bills nor "top surgery" with the hormone bill; the first is all
  // of it, under every name for it.
  {ask:["gender affirming care","gender affirming","trans healthcare","trans health care",
    "transgender healthcare","transgender health care","transition care",
    "gender transition","medical transition","sex change","sex changes",
    "gender reassignment","sex reassignment"],
   terms:["gender transition","gender affirming","gender reassignment","sex reassignment",
    "alter a minor's gender","puberty blocker","puberty blocking","cross sex hormone"],
   named:["hormone treatment"]},
  {ask:["hormone therapy","hormone treatment","hormone treatments","hormones",
    "hormone blockers","puberty blockers","puberty blocker","cross sex hormones","hrt"],
   terms:["puberty blocker","puberty blocking","cross sex hormone","alter a minor's gender",
    "sex reassignment"],
   named:["hormone treatment","hormone therapy"]},
  {ask:["top surgery","bottom surgery","gender surgery","gender surgeries",
    "gender reassignment surgery","sex change surgery","sex reassignment surgery",
    "transgender surgery"],
   terms:["gender reassignment","sex reassignment","gender transition surgery",
    "alter a minor's gender"]},
  // The text of the classification bills covers athletic or sporting
  // competition and their titles do not say so. Sport alone is every bill
  // about a ski area; sport AND one of these is the subject. A 1991 bill
  // titled "relative to women's sports" is listed for those words and not
  // for "trans sports".
  {ask:["trans sports","trans athletes","transgender athletes","transgender sports",
    "trans kids sports","girls sports","girls athletics","women's sports","womens sports",
    "women's athletics","save women's sports","fairness in women's sports"],
   terms:["sport","athletic","athlete"],
   with:["biological sex","basis of sex","transgender"],once:true},
  // `named`, as in the first entry: a form for recording a fetal death asks
  // whether it was the mother's "first marriage or civil union", and that
  // bill was listed under "gay marriage" while these were plain terms.
  {ask:["gay marriage","same sex marriage","same sex marriages","marriage equality",
    "same sex couples","civil unions","civil union","traditional marriage",
    "defense of marriage","definition of marriage"],
   terms:["one man and one woman","definition of marriage"],
   named:["right to marry","same sex","same gender","civil union","civil marriage"]},

  // --- abortion ---------------------------------------------------------
  {ask:["abortion","abortions","abortion ban","abortion bans","abortion rights",
    "abortion access","abortion pill","abortion pills","abortion law","abortion laws",
    "anti abortion","pro life","pro choice","right to life","reproductive rights",
    "reproductive freedom","reproductive health","roe","roe v wade",
    "late term abortion","late term abortions"],
   terms:["abortion","reproductive","pregnancy termination","terminate a pregnancy",
    "termination of the minor's pregnancy","fetal life protection"]},

  // --- firearms ---------------------------------------------------------
  // `also`: "gun" and "firearm" keep their SYN group, and "gun" still finds
  // Gunstock, lower down. Not "background checks": teachers and child care
  // workers have them too, and it listed eight of those bills first.
  // "concealed carry" is here because no bill says "concealed": the bills
  // it means decide where a firearm may be carried. It lists every bill
  // here, the ones with "carry" in the title first (see fit, below).
  {also:true,
   ask:["gun control","gun laws","gun law","gun rights","gun safety","gun violence",
    "gun reform","gun regulation","gun regulations","gun restrictions","gun ban",
    "gun bans","gun owners","gun ownership","guns","gun","firearms","firearm",
    "second amendment","2nd amendment","2a","right to bear arms","concealed carry",
    "open carry","constitutional carry","gun background checks"],
   terms:["gun","firearm","weapon","pistol","rifle","revolver","handgun","shotgun",
    "ammunition","second amendment","bear arms","risk protection order"]},
  // Its own entry: under the firearms one, "red flag law" listed 33 bills
  // with the two it means at 21st and 33rd.
  {ask:["red flag","red flag law","red flag laws","extreme risk protection order",
    "extreme risk protection orders","erpo"],
   terms:["risk protection order","extreme risk protection"]},

  // --- cannabis ---------------------------------------------------------
  // Not "hemp": it is a different crop in the statutes, and a reader who
  // types it gets the bills that say it.
  {ask:["weed","pot","marijuana","cannabis","legal weed","legalize weed","legalizing weed",
    "legalize marijuana","legalizing marijuana","legalize cannabis","legalizing cannabis",
    "legalize pot","legal pot","marijuana legalization","cannabis legalization",
    "recreational marijuana","recreational cannabis","recreational weed","recreational pot",
    "medical marijuana","medical cannabis","thc"],
   terms:["marijuana","cannabis","thc","alternative treatment center"]},
  // "dispensary" is the public's word for what the statute calls an
  // alternative treatment center. Its own entry: under the cannabis one the
  // five bills it means were scattered through 22.
  {ask:["dispensary","dispensaries","marijuana dispensary","marijuana dispensaries",
    "cannabis dispensary","cannabis dispensaries"],
   terms:["alternative treatment center","dispensary"]},

  // --- schools ----------------------------------------------------------
  // Not "adequacy" alone: it listed the adequacy of electricity generation
  // and of access to mental health care.
  {ask:["public education funding","public school funding","education funding",
    "school funding","funding for public schools","funding for schools","education aid",
    "school aid","adequate education","education adequacy","school finance",
    "school funding formula","fair funding","claremont decision","claremont lawsuit",
    "claremont ruling"],
   terms:["education funding","school funding","adequate education","education adequacy",
    "educational adequacy","adequacy grant","adequacy aid","education trust fund",
    "education grant","school building aid","opportunity budget","education financing",
    "education property tax","fund public education","funding public education",
    "aid to school districts","public school expenses"]},
  // Not "voucher" as a term: housing vouchers are vouchers too, and a landlord
  // bill came up for "school choice". A reader who types "vouchers" still gets
  // every title that says so, as their own word. Not "open enrollment" alone:
  // health insurance has open enrollment periods.
  {ask:["school choice","education freedom account","education freedom accounts",
    "education freedom","education savings account","education savings accounts",
    "school voucher","school vouchers","voucher","vouchers","efa","efas"],
   terms:["education freedom account","education freedom savings account","school choice",
    "education savings account","scholarship organization","open enrollment school",
    "school open enrollment","open enrollment in all school districts",
    "charter school and open enrollment","charter schools and open enrollment","efa"]},
  {ask:["homeschool","homeschooling","homeschooled","home school","home schooling",
    "home schooled","homeschoolers"],
   terms:["home education","home school","home schooled"]},
  {ask:["school lunch","school lunches","school meals","school meal","free lunch",
    "free lunches","free school lunch","free school meals","school breakfast","lunch debt"],
   terms:["school lunch","school meal","school breakfast","free and reduced",
    "reduced price","meals to students","breakfast and lunch","meal program",
    "meal balances"]},
  {ask:["book ban","book bans","banned books","banning books","book banning",
    "school library books","library books","obscene books","explicit books",
    "sexually explicit books","inappropriate books","age appropriate books"],
   terms:["public school materials","harmful sexual materials",
    "obscene material by schools","school library"]},
  // The law people call "divisive concepts" and "the CRT ban" is titled the
  // prohibition on teaching discrimination, and before that the right to
  // freedom from discrimination in public workplaces and education.
  {ask:["critical race theory","crt","divisive concepts","divisive concept",
    "divisive concepts law","banned concepts","anti crt","crt ban"],
   terms:["teaching discrimination","divisive concept","freedom from discrimination"]},
  {ask:["dei","diversity equity and inclusion","diversity equity inclusion",
    "diversity and inclusion","diversity training"],
   terms:["dei","diversity training"]},
  // Two entries. "parental rights" is also what family court calls custody
  // ("parental rights and responsibilities"), and those titles have the
  // reader's own words. But "forced outing" and "parental bill of rights"
  // listed them too, 75 across the terms, through the term "parental
  // rights". Those asks have their own entry, without it.
  {ask:["parental rights","parents rights","parent rights","rights of parents"],
   terms:["parental bill of rights","parental rights","parents' bill of rights",
    "parents bill of rights","rights of parents",
    "disclosure by school district employees to parents"]},
  {ask:["parental bill of rights","parents bill of rights",
    "forced outing","outing students","parental notification in schools"],
   terms:["parental bill of rights","parents' bill of rights","parents bill of rights",
    "disclosure by school district employees to parents"]},
  // "teachers" was every title with school, education or student in it, 321,
  // because SYN groups them. The word stands for itself here.
  {ask:["teacher","teachers","educator","educators"],
   terms:["teacher","educator"]},
  // Phrases, because as two words each found bills about something else:
  // "teacher" and "pay" payments to schools, "sex" and "education" biological
  // sex in athletics.
  {ask:["teacher pay","teacher salary","teacher salaries","teacher wages",
    "teacher compensation","educator pay"],
   terms:["teacher compensation","compensation and benefits of teachers"]},
  {ask:["sex education","sex ed","sexual education","sexuality education",
    "sexual health education"],
   terms:["sex education","sexual education","human sexuality"]},
  // A phrase, because as two words "child" and "care" found foster care.
  {ask:["child care","childcare","day care","daycare"],
   terms:["child care","childcare","day care","daycare"]},

  // --- housing ----------------------------------------------------------
  {ask:["adu","adus","accessory dwelling unit","accessory dwelling units",
    "in law apartment","in law apartments","granny flat","accessory apartment"],
   terms:["accessory dwelling","adu"]},
  {ask:["mobile home","mobile homes","trailer park","trailer parks","manufactured home",
    "manufactured homes","manufactured housing"],
   terms:["manufactured housing","manufactured home","mobile home"]},
  {ask:["rent control","rent stabilization","rent cap","rent caps","rent increase",
    "rent increases","rent hikes","rent prices"],
   terms:["rent control","rent increase","monthly rent","rent charged"]},
  // Not "tenancy" alone: a joint tenancy is how two people own a house.
  {ask:["eviction","evictions","evict","landlord","landlords","tenant","tenants",
    "renters","renter","tenant rights","tenants rights","renters rights"],
   terms:["landlord","tenant","eviction","evict","rental housing","termination of tenancy",
    "terminate a tenancy","residential tenancy","residential tenancies",
    "tenancy protections","residential rental","rental properties","rent payments"]},
  {ask:["homeless","homelessness","unhoused","homeless shelter","homeless shelters"],
   terms:["homeless","homelessness","emergency shelter","young adult shelter"]},
  // Not "land use" alone, as a term: a quarter of the titles that say it are
  // about the land use change tax, which is current use taxation.
  {ask:["zoning","zoning laws","zoning reform","land use","planning board","planning boards"],
   terms:["zoning","zoned","downzoning","planning board","parking requirements",
    "land use board","land use regulation","land use control","land use planning",
    "land use decision","planning and land use","governmental land use"]},
  {ask:["affordable housing","workforce housing","housing affordability"],
   terms:["affordable housing","workforce housing","housing champion"]},
  {ask:["short term rental","short term rentals","vacation rental","vacation rentals","airbnb"],
   terms:["short term rental","vacation rental"]},

  // --- taxes ------------------------------------------------------------
  // A phrase, because as two words it found "low-income" beside "tax".
  {ask:["income tax","income taxes","state income tax","personal income tax"],
   terms:["income tax","tax on personal income","interest and dividends tax"]},
  {ask:["sales tax","sales taxes"],
   terms:["sales tax"]},

  // --- immigration ------------------------------------------------------
  // Not "immigration laws" nor "federal immigration" alone: they listed a
  // 2003 resolution on citizenship for veterans and a 2005 bill on labor
  // statutes.
  {ask:["ice","ice agents","287g","deportation","deportations","deport","sanctuary city",
    "sanctuary cities","sanctuary","sanctuary state","immigration enforcement",
    "immigration and customs enforcement"],
   terms:["immigration enforcement","federal immigration authorities",
    "federal immigration program","federal immigration checkpoint",
    "enforcement of immigration laws","enforcement of federal immigration laws",
    "enforcing federal immigration laws","immigration detention","immigration detainer",
    "immigration authorities","immigration and customs enforcement","civil immigration",
    "sanctuary"]},
  // Not "refugees" as an ask: it turned a search with two exact answers into 22.
  {ask:["immigration","immigrant","immigrants","illegal immigrants","illegal immigrant",
    "illegal immigration","illegal aliens","illegal alien","undocumented",
    "undocumented immigrants","undocumented immigrant","migrants","migrant"],
   terms:["immigration","immigrant","noncitizen","non citizen","alien",
    "undocumented immigrant","unlawfully present","refugee","e verify"]},

  // --- elections --------------------------------------------------------
  // Identification AND voting: "photo identification" alone listed photo
  // cards for food stamps and for people leaving prison.
  {ask:["voter id","voter identification","photo id","voter id law","voter id laws"],
   terms:["voter identification","photo identification","proof of identity",
    "voter identity","identification of voter","photographic means of identification",
    "proof of identification"],
   with:["vote","voter","voting","ballot","election"]},
  // "absentee ballot" was 142 bills, every election bill of the term: both
  // words expanded to the whole voting group. The record's word is "absentee".
  {ask:["mail in voting","mail in ballot","mail in ballots","vote by mail","voting by mail",
    "absentee voting","absentee ballot","absentee ballots","absentee","no excuse absentee",
    "early voting"],
   terms:["absentee","early voting"]},
  // The bills that draw the districts are titled "apportioning ...". Not
  // "apportionment" alone: that is also how cooperative school districts
  // split their costs and how the business profits tax divides income.
  {ask:["redistricting","gerrymandering","gerrymander","district maps","redistricting maps"],
   terms:["redistricting","reapportioning","drawing of district boundaries",
    "apportioning state representative districts","apportioning state senate districts",
    "apportioning congressional districts","apportioning executive council districts",
    "apportioning county commissioner districts","apportioning electoral districts",
    "apportionment of state representative districts"]},
  {ask:["term limits","term limit"],
   terms:["term limit","term limitations"]},

  // --- work -------------------------------------------------------------
  {ask:["minimum wage","tipped wage","tipped minimum wage","raise the wage","living wage"],
   terms:["minimum wage","minimum hourly rate","subminimum wage","tipped employees"]},
  // A phrase, so that it is not read as "right" and "work". The bill that
  // is one says so in its text; its title says "join or contribute to a
  // labor union", and that link is the bill's to make, not this table's.
  {ask:["right to work"],
   terms:["right to work"]},
  {ask:["paid family leave","paid family and medical leave","family leave","paid leave"],
   terms:["family and medical leave","paid family","family leave","paid leave"]},

  // --- roads ------------------------------------------------------------
  // Not "intoxicated" alone: it listed possession of a firearm while intoxicated.
  {ask:["drunk driving","drunk drivers","drunk driver","driving drunk","dwi","dui","duis",
    "driving under the influence"],
   terms:["dwi","driving while intoxicated","intoxicated driver","impaired driver",
    "alcohol concentration","under the influence","ignition interlock"]},
  // An inspection AND a vehicle: "safety inspection" alone listed fire
  // inspections of foster homes and the workers' compensation safety program.
  {ask:["car inspection","car inspections","vehicle inspection","vehicle inspections",
    "inspection sticker","inspection stickers","state inspection","auto inspection",
    "annual inspection"],
   terms:["motor vehicle inspection","vehicle inspection","safety inspection",
    "inspection sticker","inspection station","inspection and registration",
    "emission control test"],
   with:["vehicle","motorcycle","automobile"]},
  {ask:["ev","evs","electric car","electric cars","electric vehicle","electric vehicles",
    "ev charging","ev chargers"],
   terms:["electric vehicle","plug in hybrid","charging station","vehicle charging"]},

  // --- health -----------------------------------------------------------
  // "vaccine" alone is left to SYN, which has it with vaccination and
  // immunization. This is the requirement: without it "vaccine mandate" found
  // nothing, and with every vaccine title it found rabies shots for cats.
  {ask:["vaccine mandate","vaccine mandates","vaccine requirement","vaccine requirements",
    "vaccination requirements","vaccine exemption","vaccine exemptions",
    "mandatory vaccination","mandatory vaccines","school vaccines","vaccine choice"],
   terms:["vaccine mandate","mandatory vaccine","vaccine requirement",
    "vaccination requirement","immunization requirement","immunization is required",
    "requiring certain immunizations","vaccine exemption","exemption from immunization",
    "vaccination status","immunization status","mandate vaccination"]},
  // Not "end of life" alone: it listed the disposal of end of life vehicles.
  {ask:["assisted suicide","physician assisted suicide","medical aid in dying",
    "aid in dying","death with dignity","right to die","euthanasia","end of life"],
   terms:["aid in dying","death with dignity","end of life care","end of life decision",
    "end of life choice"]},
  {ask:["vaping","vape","vapes","e cigarettes","e cigarette","juul"],
   terms:["vape","vaping","e cigarette","electronic cigarette","e liquid"]},

  // --- technology and money ---------------------------------------------
  // "ai" is two letters and reads as nothing else; the bills say it in full.
  {ask:["ai","a.i","artificial intelligence","chatbot","chatbots","deepfake","deepfakes",
    "chatgpt"],
   terms:["artificial intelligence","deepfake","synthetic media"]},
  {ask:["social media","tiktok","instagram","facebook"],
   terms:["social media"]},
  {ask:["crypto","cryptocurrency","cryptocurrencies","bitcoin","blockchain"],
   terms:["blockchain","digital currency","digital currencies","digital asset",
    "stable token","cryptocurrency","bitcoin","virtual currency"],
   not:["access to digital assets"]},
  {ask:["casino","casinos","gambling","slot machines","slot machine","slots","betting"],
   terms:["casino","betting","wagering","gambling","charitable gaming",
    "gaming facilities","games of chance","historic horse racing","video lottery",
    "slot machine","keno"]},
  // Sports only: with gambling in it, "sports betting" returned 26 bills about
  // horse racing and video lottery. "gambling" alone still finds those.
  {ask:["sports betting","sports wagering","sports gambling","sportsbook"],
   terms:["sports betting","sports wagering","sports book"]},

  // --- animals, energy and the climate ------------------------------------
  {ask:["animal cruelty","animal abuse","animal welfare","cruelty to animals"],
   terms:["animal cruelty","animal abuse","abuse of animals","cruelty"]},
  // Not "climate" alone: it listed climate control in school buildings and
  // the culture and climate of schools.
  {ask:["climate change","global warming","climate crisis","climate action"],
   terms:["climate change","climate action","climate damage","climate resilience",
    "climate education","climate protection","climate registry","climate initiative",
    "climate corps","climate and health","climate and conservation",
    "climate and environmental","global warming","greenhouse gas","carbon sequestration",
    "carbon pricing","carbon reduction"]},
  // `also`: whether a reader typing "solar" wants the emissions and renewable
  // portfolio bills SYN groups with it is the person's to decide; until then
  // the word finds what it found, and net metering is added.
  {also:true,
   ask:["solar"],
   terms:["solar","net metering","net energy metering","customer generator"]},
  // Its own entry, without the bare word (2 October): "solar panels" listed
  // a ban on solar radiation modification second, and across the terms a
  // school holiday for the solar eclipse. The word alone still finds those.
  {ask:["solar panels","solar panel","solar power","solar energy","solar array",
    "solar arrays","solar farm","solar farms","rooftop solar","net metering"],
   terms:["solar energy","solar panel","solar array","solar power","solar generation",
    "solar project","photovoltaic","net metering","net energy metering",
    "customer generator"]},

  // --- courts and the record ---------------------------------------------
  // `also`: "bail" still finds the bailiffs, lower down.
  {also:true,
   ask:["bail reform","bail","pretrial release"],
   terms:["bail","pretrial release","pretrial detention","pretrial services"]},
  {ask:["death penalty","capital punishment"],
   terms:["death penalty","capital murder"]},
  {ask:["right to know","public records","open records","freedom of information","foia"],
   terms:["right to know","91 a","public records","governmental records"]},

  // --- ADDED AFTER THE TABLE WAS FIRST MEASURED (1 October) ---------------
  // Everything above was scored on fifteen searches nobody had written an
  // entry for, and recovered none of them. These were then written for those
  // searches, from the titles -- so they proved nothing about the next
  // fifteen. What did was reading the bills' own text, below; the entries
  // that are still here are the ones for a word the bills do not use.
  {ask:["drug prices","drug pricing","drug costs","prescription drug prices",
    "prescription prices","prescription costs","cost of prescriptions","pbm","pbms",
    "pharmacy benefit managers"],
   terms:["prescription drug affordability","drug affordability","drug pricing",
    "pharmacy benefit manager","pharmacy benefits manager"]},
  {ask:["food stamps","food stamp","snap","snap benefits","ebt"],
   terms:["snap","supplemental nutrition","supplemental nutritional","food stamp",
    "electronic benefit transfer","ebt"]},
  {ask:["campaign finance","campaign financing","campaign donations","campaign donation",
    "campaign contributions","political donations","money in politics","dark money",
    "super pac","super pacs"],
   terms:["campaign finance","campaign contribution","campaign expenditure",
    "campaign fund","political committee","political contribution",
    "political expenditure"]},
  {ask:["legislator pay","legislators pay","legislator salary","legislator salaries",
    "legislative pay","legislative salary","lawmaker pay","legislator compensation"],
   terms:["legislative salary","legislative compensation","compensation of the legislature",
    "compensation for members of the general court",
    "compensation of members of the legislature"]},
  {ask:["youth detention","juvenile detention","youth detention center","ydc",
    "sununu center","sununu youth center"],
   terms:["youth development center","youth services center","juvenile detention"]},
  {ask:["pornography","porn","pornographic"],
   terms:["pornographic","pornography","obscenity","obscene material"]},
  {ask:["psychedelics","psychedelic","magic mushrooms","shrooms","psilocybin"],
   terms:["psilocybin","psychedelic"]},
  // Not "vessel" alone: a pressure vessel is a boiler.
  {ask:["boating","boaters","boater","boat registration","boater safety"],
   terms:["boat","watercraft","mooring","vessel registration"]},
  {ask:["ems","emt","emts","paramedic","paramedics"],
   terms:["emergency medical services","emergency medical care provider",
    "emergency medical transport","emergency medical technician","ambulance","paramedic"]},
  {ask:["pension","pensions","state pension","state pensions","public pensions","nhrs"],
   terms:["pension","retirement system"]},
  {ask:["data privacy","online privacy","internet privacy","consumer privacy",
    "personal data","data brokers","data broker"],
   terms:["personal data","personal information","expectation of privacy","data broker",
    "biometric"]},
  {ask:["fluoride","fluoridation"],
   terms:["fluoride","fluoridation"]},
  {ask:["license plate readers","license plate reader","license plate scanners",
    "license plate scanner","plate readers","alpr"],
   terms:["number plate scanning","license plate scanning","license plate reader"]},

  // --- FROM THE REVIEW OF THAT TABLE (1 October): everyday words it still
  // missed that the bills never use. The statutes call the gas tax the road
  // toll, an ATV an OHRV, and nobody under 18 a kid.
  // `named`: in a title or an analysis. Read in the text too, "kids" was
  // 183 bills -- every bill that mentions a child twice.
  {ask:["kids","kid"],
   terms:["children"],named:["child","minor","youth","juvenile"]},
  {ask:["atv","atvs","four wheeler","four wheelers","utv","utvs"],
   terms:["ohrv","off highway recreational vehicle","all terrain vehicle"]},
  {ask:["gas tax","gasoline tax","fuel tax"],
   terms:["road toll","motor fuel tax","gasoline tax"]},
  {ask:["scam","scams","scammers"],
   terms:["fraud","fraudulent","deceptive"]},
  {ask:["jury duty"],
   terms:["juror","jury service","jury duty"]},

  // --- FROM THE REVIEW OF THE TEXT INDEX (1 October): four searches on
  // subjects where a wrong answer costs most. None is from a set the search
  // is measured on. "ghost guns" and "gun free zones" are not here: no bill
  // has said the first, and the second is "safe school zone", which is also
  // pocket knives and discipline statistics.
  // As two words "birth control" was one bill, on reporting fetal deaths to
  // the Centers for Disease Control, and "family planning" multi-family
  // housing with a planning board in its analysis.
  {ask:["birth control","contraception","contraceptive","contraceptives","family planning"],
   terms:["contraception","contraceptive","birth control","family planning"]},
  // "pronoun" alone is the grammar of a statute: the register of deeds
  // chapter made gender neutral, a retirement system's "he or she". A
  // pronoun AND one of these is the subject, and one mention counts, since
  // one is all the 2026 bill has.
  {ask:["pronouns","pronoun","preferred pronouns","preferred pronoun","misgendering",
    "deadnaming"],
   terms:["pronoun"],
   with:["gender identity","gender expression","biological sex","transgender",
    "personal identity ideology"],once:true},
  // No bill says "marker". The bills on what a licence or a birth record
  // says say "designation".
  {ask:["gender marker","gender markers","sex marker","sex markers"],
   terms:["gender designation","sex designation"]},
  // Not in SYN beside "ammunition": a word there is also read as the start
  // of a longer one, and "ammonia" would have listed these.
  {ask:["ammo"],
   terms:["ammunition"]},

  // --- FROM THE SECOND REVIEW (2 October): thirty searches nobody had
  // tuned. Each of these is a word a reader types and the record does not
  // use; the terms are what the bills say instead, read out of their titles.
  // 2009 HB 105 "replaces the term voting machines or devices with
  // electronic ballot counting devices", and every bill since says that.
  {ask:["voting machine","voting machines","vote counting machine","vote counting machines",
    "ballot counting machine","ballot counting machines","ballot counting device",
    "ballot counting devices","ballot machines"],
   terms:["ballot counting device","electronic ballot counting","voting machine"]},
  // Half the bills say one and half the other.
  {ask:["telehealth","telemedicine"],
   terms:["telehealth","telemedicine"]},
  // New Hampshire annuls a record; nobody types that.
  {ask:["expungement","expungements","expunge","expunged","expunging"],
   terms:["expungement","expunge","annul","annulment","annulling","annulled"]},
  {ask:["uber","lyft","rideshare","ridesharing","ride share","ride sharing","ride hailing"],
   terms:["transportation network company","transportation network companies","uber",
    "rideshare"]},
  {ask:["silencer","silencers","suppressor","suppressors"],
   terms:["silencing device","suppressor","silencer"]},
  // `like`: the word is read as SYN reads "police" -- law enforcement, peace
  // officers, sheriffs, in a title -- and whole, which a word in SYN is not:
  // there, "cop" would also be the start of "copy" and "copayment", and
  // every word that begins with it would be read as the police.
  {ask:["cops","cop"],like:"police",
   terms:["police"]},
  {ask:["booze"],
   terms:["alcohol","alcoholic","liquor","beer","wine"]},
  // A phrase, so that it is not "child" and "labor": that listed hard labor
  // as a sentence for assaults on children, first.
  {ask:["child labor","child labour"],
   terms:["youth employment","child labor","employment of minors"]},
  {ask:["tax break","tax breaks"],
   terms:["tax exemption","tax credit","tax relief","tax abatement","tax deferral"]},
  // The two taxes a business pays here. As two words it needed "business"
  // beside "tax", and the bills say "business profits tax".
  {ask:["business tax","business taxes"],
   terms:["business profits tax","business enterprise tax","business tax"]},
  // Read whole: as the start of a word "condo" was also "condoms".
  {ask:["condo","condos"],
   terms:["condominium"]},
  // Its own entry: as an ask of the firearms one it listed criminal
  // threatening and air rifles for hunting game. No bill of 2025-2026 says
  // any of these, and the search then lists none, which is the answer.
  {ask:["assault weapons","assault weapon","assault rifle","assault rifles"],
   terms:["assault weapon","semi automatic","semiautomatic","large capacity ammunition"]},
  // What an agency is called for short. `named` and no terms: a department
  // is named in the text of every bill that gives it something to do, and
  // a bill that names it in its title or its analysis is about it.
  {ask:["dmv"],terms:[],named:["division of motor vehicles"]},
  {ask:["dhhs"],terms:[],named:["department of health and human services"]},
  {ask:["dot"],terms:[],named:["department of transportation"]},
  {ask:["des"],terms:[],named:["department of environmental services"]},
  {ask:["doe"],terms:[],named:["department of education"]},
  {ask:["doj"],terms:[],named:["department of justice"]},
  {ask:["puc"],terms:[],named:["public utilities commission"]},
  // Not the whole name: titles print "division for children, youth, and
  // families" with and without the last comma, and no other division is for
  // children.
  {ask:["dcyf"],terms:[],named:["division for children"]},

  // --- FROM THE THIRD REVIEW (2 October): forty searches written blind.
  // Words the record does not use, for bills it has.
  {ask:["ufo","ufos","uap","uaps"],
   terms:["unidentified anomalous"]},
  // The brands; the bills name the class of drug.
  {ask:["ozempic","wegovy","mounjaro","zepbound"],
   terms:["glp 1"]},
  {ask:["ebike","ebikes","e bike","e bikes","electric bike","electric bikes"],
   terms:["electric bicycle","e bike"]}
];
/* THE MARKS A QUESTION IS ASKED WITH, taken off the ENDS of words and nowhere
   else. Only the comma and the hyphen were being removed, so a reader who
   typed the way people type -- "right to know?" -- got 0 bills where "right
   to know" gets 14, and "school funding." got 0 against 33. The question mark
   rode along on the last word: the phrase test looks for " right to know "
   and saw " right to know? ", and the word test then asked the titles for
   /\bknow\?/, which no bill title contains.
   The ends only, because the middle carries meaning here. "91-a:4" is an RSA
   citation and its colon is part of the number -- titles are searched with
   the hyphen already read as a space, so the query must keep the rest of the
   citation intact. "children's" keeps its apostrophe for the same reason: it
   is inside a word, not around one. And this strips a named list of marks
   rather than "anything that is not a-z0-9", which would have eaten the
   final letter of an accented word.
   The plus sign with them (1 October): "lgbtq+ rights" found 2 bills where
   "lgbtq rights" found 19. And a bracket inside a word goes too: "287(g)"
   found nothing where "287g" found 9. */
const EDGEMARK=/^[.?!;:'"“”‘’()\[\]{}…+]+|[.?!;:'"“”‘’()\[\]{}…+]+$/g;
// What was typed, as the words it is read as: lower case, a curly apostrophe
// straightened, commas and hyphens as spaces, marks off the ends of words.
// The table's asks are read the same way, so one spelling there is enough.
const qnorm=s=>String(s||"").toLowerCase().replace(/[‘’]/g,"'").replace(/[,\-]/g," ")
  .split(/\s+/).map(w=>w.replace(EDGEMARK,"").replace(/(\w)[()]+(?=\w)/g,"$1"))
  .filter(Boolean).join(" ");
// A term, as a title is searched: hyphens are spaces.
const cnorm=s=>String(s).toLowerCase().replace(/-/g," ");
const CWORD=Object.create(null),CPHRASES=[];
CONCEPTS.forEach(c=>{
  c.ask=c.ask.map(qnorm);
  c.terms=c.terms.map(cnorm);
  c.named=(c.named||[]).map(cnorm);
  if(c.with)c.with=c.with.map(cnorm);
  if(c.not)c.not=c.not.map(cnorm);
  // What the entry lists both as a word people type and as wording bills use.
  c.plain=[...c.terms,...c.named].filter(t=>c.ask.includes(t));
  c.ask.forEach(a=>{ if(a.includes(" "))CPHRASES.push([a,c]); else CWORD[a]=c; });
});
/* A SYN ENTRY OF TWO WORDS could never fire when typed: the search was split
   into words before SYN was asked, so "law enforcement" searched
   "enforcement" ("law" carries no subject and is skipped) and listed
   building-code enforcement. Thirty-one entries are like that. Two groups
   are switched on here, the two whose results were read (1 October); the
   others stay off until theirs are -- "health care" as a phrase would widen
   to every title with "health" in it. A phrase SYN no longer lists is
   skipped rather than left to stop the page loading, and preflight fails if
   one of these stops being read as a phrase.

   AND EVERY ENTRY NO TITLE HAS EVER USED (2 October). "forever chemicals"
   listed nothing in any term, with "forever chemical" sitting in the PFAS
   group: read as two words it needs a title that says "forever". An entry
   the titles do use ("solid waste", "drinking water") is found as its two
   words. One they never use -- it is in SYN as the public's word for the
   group -- can only be found as the group, so it is read as a phrase: four
   of them, and preflight fails if SYN gains a fifth that is not listed
   here. */
const SYNPHRASES=["mental health","behavioral health","law enforcement",
  "forever chemical","impaired driving","older adult","high speed internet",
  "license plate","number plate"];
SYNPHRASES.forEach(p=>{ if(SYNMAP[p])CPHRASES.push([p,{syn:SYNMAP[p].map(cnorm)}]); });
CPHRASES.sort((a,b)=>b[0].length-a[0].length);
/* A PLURAL IS READ AS ITS SINGULAR, from four letters: "dogs" found only the
   titles with the plural and missed five that say "dog"; "cars", "bees",
   "kids" and "jobs" found little or nothing (1 October). A four-letter word
   just loses its s -- the -ies rule would make "ties" into "ty". Three are
   kept whole because their singular is a different word.
   build_search_index.py has this function too, in Python: the search index
   files a word under what this returns, and preflight runs both over the
   same words and fails if they ever differ. */
const STEMKEEP=new Set(["news","arms","dues"]);
function stem(w){
  if(w.length<4||/(ss|us|is)$/.test(w)||STEMKEEP.has(w))return w;
  if(w.length===4)return w.endsWith("s")?w.slice(0,-1):w;
  if(/ies$/.test(w))return w.slice(0,-3)+"y";
  if(/(xes|ches|shes|sses)$/.test(w))return w.slice(0,-2);
  return w.endsWith("s")?w.slice(0,-1):w;
}
/* A PHRASE OF THE TABLE, TYPED WITH ANOTHER ENDING. "transgender athletes"
   listed eleven bills and "transgender athlete ban" one: the table has the
   plural, and the singular was read as two words. A phrase is the table's
   when each of its words is, read as its singular -- so one spelling of a
   phrase in the table is enough. A single word is still the table's only as
   the table spells it ("weeds" is the plant). */
CPHRASES.forEach(e=>{e.push(e[0].split(" ").map(stem));});
// Where in `words` the phrase `e` is typed, or -1.
function phraseAt(words,stems,e){
  const want=e[2];
  for(let i=0;i+want.length<=words.length;i++){
    let k=0;
    while(k<want.length&&stems[i+k]===want[k])k++;
    if(k===want.length)return i;
  }
  return -1;
}
/* A PLURAL THAT IS NOT MADE WITH AN S. "knife" found nothing in a term with
   a bill titled about "knives", and "woman" not "women": taking the s off
   never reaches these. Each is read as the other, in a title, as a plural is
   read as its singular. Not life and lives, leaf and leaves, half and halves:
   the plural is also a verb, and "leaf" would list every leave of absence. */
const ODDPLURAL=Object.create(null);
[["knife","knives"],["wife","wives"],["wolf","wolves"],["calf","calves"],
 ["shelf","shelves"],["thief","thieves"],["child","children"],["woman","women"],
 ["tooth","teeth"],["goose","geese"],["mouse","mice"]]
  .forEach(([a,b])=>{ODDPLURAL[a]=b;ODDPLURAL[b]=a;});
// "legalize" did not find "legalizing" or "legalization". A verb in -ize or
// -ise is also read without its final e, as the start of a word. Not -ate,
// which was here too: "appropriate" listed 81 bills making appropriations,
// "educate" 316 about education and "moderate" the town moderators.
const VERBEND=/(ize|ise)$/;
/* THE READER'S WORD IN ANOTHER FORM IS STILL THE READER'S WORD (2 October).
   What the table supplies is listed after everything that has the word
   typed, and that is right for wording that is another thing's name: a
   reader who types "eviction" wants the bills that say so before the ones
   titled for landlords. It was wrong for two kinds of term that are the
   word itself:
   - WRITTEN OUT. "dwi" opened on an insurance bill whose analysis mentions
     a spouse's DWI conviction, above every bill titled "driving while
     intoxicated": the letters in an analysis outranked the words in a
     title. A term whose words begin with the letters typed, in order --
     counted with or without the words a search skips, so that "dmv" is the
     division of motor vehicles and "dot" the department of transportation
     -- is the word typed, in full, and a title that has it has the word.
   - WITH ANOTHER ENDING. "eviction" listed a bill titled "notice to evict"
     tenth, under "title says: landlord", below bills on rent payments. A
     one-word term that begins the word typed, or that the word typed
     begins, from four letters, is a form of it: listed as a longer word in
     a title is (see fitAlone), after the bills that have the word and
     before the rest of what the table found, and the card says which word.
   Only among the terms of the entry the word is an ask of, so "trans" is
   still not "transfer". spelt() and kin() say which terms of a group are
   which; they are worked out once, when the search is read. */
const initials=ws=>ws.map(w=>w[0]).join("");
function spelt(word,term){
  if(word.includes(" ")||word.length<2||!term.includes(" "))return false;
  const ws=term.split(/[^a-z0-9]+/).filter(Boolean);
  return initials(ws)===word||initials(ws.filter(w=>!STOPSET.has(w)))===word;
}
const kin=(word,term)=>!word.includes(" ")&&!term.includes(" ")&&word!==term
  &&Math.min(word.length,term.length)>=4&&(word.startsWith(term)||term.startsWith(word));
// For each term a group took from the table, how near the word typed it is:
// 0 written out, 1 another ending. Nothing for the rest.
function nearTerms(g,asked){
  const near=new Map();
  for(let i=g.tab;i<g.alts.length;i++){
    const t=g.alts[i];
    if(asked.some(a=>spelt(a,t)))near.set(t,0);
    else if(asked.some(a=>kin(a,t)))near.set(t,1);
  }
  if(near.size)g.near=near;
}
// One entry of the table as the part of a search it stands for. `own` is
// what the reader typed (and its singular); `tab` is where the entry's terms
// begin and `nam` where its `named` terms do.
function conceptGroup(word,own,c){
  const asked=[...new Set(own)];
  // `like`: SYN's group for that word stands beside the reader's own, and
  // is read where a synonym is read -- in a title.
  own=[...new Set([...asked,...(c.like&&SYNMAP[c.like]||[]).map(cnorm)])];
  const alts=[...new Set([...own,...c.terms])];
  const g={word,alts:alts.concat(c.named.filter(t=>!alts.includes(t))),
    tab:own.length,nam:alts.length,exact:true,asked};
  // The reader's own word, where the entry says it counts only in a title
  // or an analysis: typed "gender identity" is read as the table reads it.
  const on=own.filter(o=>c.named.includes(o));
  if(on.length)g.ownNamed=on;
  if(c.not)g.not=c.not;
  // The words of a typed phrase, for the order of what its entry finds.
  if(word.includes(" "))g.parts=word.split(" ").filter(w=>w.length>2&&!STOPSET.has(w));
  // The reader's word is read in a bill's text only where the entry lists it
  // as the bills' own wording too ("abortion", "restroom"): "trans" in a
  // text is the first half of "trans-portation" broken across a line.
  g.plain=c.plain;
  if(c.with){g.with=c.with;g.once=!!c.once;g.stands=[...new Set([...own,...c.plain])];}
  nearTerms(g,asked);
  return g;
}
// The search as groups, every one required: a concept's phrase is one group of
// its terms, each other word a group of its synonyms. In a group, `alts` is
// everything a bill may say; from index `tab` on they are terms the table
// supplied (looseness lists those after the reader's own word); `exact` says
// the reader's word is read whole, never as the start of a longer one.
/* A SEARCH IS READ TO ITS TWELFTH WORD (2 October). Every word typed is a
   part every bill is asked for, and a part is weighed against the others:
   200 words pasted into the box -- a paragraph of a bill, by accident or to
   find it -- stopped the page for 17 seconds in the term and 220 on All
   terms, and a real Chrome offered to kill it. Nobody types a search of
   thirteen subject words, and a pasted title is found by its first twelve
   as surely as by all thirty: so the words that carry a subject are read up
   to MAXWORDS and the rest are not, and the page says so (`cut`, how many
   words were left unread). The words a search skips are not counted. And a
   word is read to its sixtieth letter: the longest any bill has printed is
   half that, and 20,000 letters with no space between them were matched
   against every title as one word. */
const MAXWORDS=12,MAXLETTERS=60;
function queryGroups(raw){
  const every=qnorm(raw).split(" ").map(w=>w.length>MAXLETTERS?w.slice(0,MAXLETTERS):w);
  let cut=every.length,carry=0;
  for(let i=0;i<every.length;i++)
    if(!STOPSET.has(every[i])&&++carry>MAXWORDS){cut=i;break;}
  let q=" "+every.slice(0,cut).join(" ")+" ";
  const asTyped=q.trim();
  const out=[];
  out.cut=every.length-cut;
  let typed=q.split(" ").filter(Boolean),stems=typed.map(stem);
  for(const e of CPHRASES){
    const p=e[0],c=e[1];
    let as=p;
    if(!q.includes(" "+p+" ")){
      const i=typed.length>=e[2].length?phraseAt(typed,stems,e):-1;
      if(i<0)continue;
      as=typed.slice(i,i+e[2].length).join(" ");
    }
    out.push(c.syn?{word:as,alts:[...new Set([as,p,...c.syn])]}
      :conceptGroup(as,[...new Set([as,p])],c));
    q=q.split(" "+as+" ").join(" ");
    typed=q.split(" ").filter(Boolean);stems=typed.map(stem);
  }
  const words=q.split(" ").filter(Boolean);
  const kept=words.filter(w=>!STOPSET.has(w));
  // The plain word before this one, for two words typed that a title writes
  // as one (WRITTEN AS ONE WORD, OR TWO, below).
  let before=null;
  (kept.length||out.length?kept:words).forEach(w=>{
    // The table's word, whole, and only as the table spells it: "weeds" is
    // not "weed". Its singular is still the reader's own word -- "hormones"
    // lost the title that says "hormone products" without it.
    const one=stem(w),c=CWORD[w];
    if(c&&!c.also){ out.push(conceptGroup(w,[w,one],c)); before=null; return; }
    // A word that is itself an entry is not a plural to take the s off: "pfas".
    const g={word:w,alts:[...new Set([w,...expand(SYNMAP[w]?w:one)].map(cnorm))]};
    const odd=ODDPLURAL[w]||ODDPLURAL[one];
    if(odd){g.odd=odd;if(!g.alts.includes(odd))g.alts.push(odd);}
    if(w.length>=7&&VERBEND.test(w)){g.pre=w.slice(0,-1);g.alts.push(g.pre);}
    if(c){
      g.terms=c.terms;
      g.tab=g.alts.length;g.alts=[...new Set([...g.alts,...c.terms])];
      g.nam=g.alts.length;g.alts=g.alts.concat(c.named.filter(t=>!g.alts.includes(t)));
      nearTerms(g,[w,one]);
    }
    if(before){
      const j=before.word+w;
      (before.joins||(before.joins=[])).push(j);
      g.joins=[j];
    }
    before=c?null:g;
    out.push(g);
  });
  // TAGS:BEGIN
  // A tag's word, or a topic's, the whole search or one part of it (tagGroups).
  tagGroups(out,asTyped);
  // TAGS:END
  // The search as typed, the skipped words still in it: a title that says
  // "medical bills" in those words is the one a reader of them wants first
  // (matchScore, below).
  out.typed=asTyped;
  // What a part of a search may not do alone. `solo`: it is the whole search.
  // `rest`: for a search of several parts, what a title must say for each of
  // the others to be in it -- their own words, not the table's (see fitAlone).
  // `peers`: the other parts themselves, kept where copying or printing a
  // group does not follow them round in a circle.
  if(out.length===1)out[0].solo=true;
  else out.forEach(g=>{
    const others=out.filter(x=>x!==g);
    g.rest=others.map(x=>x.alts.slice(0,x.tab!=null?x.tab:x.alts.length));
    Object.defineProperty(g,"peers",{value:others,enumerable:false});
  });
  return out;
}

/* WHERE A WORD MATCHES, AND HOW. Read against the bills 36 searches returned
   (14 September), the irrelevant ones came from four places:
   - the TOPIC label, a broad bucket: "mental health" returned 80 bills --
     ambulance services, the prescription drug board -- whose only link was a
     topic reading "...Mental Health". See THE BILLS' OWN WORDS, below, for
     how a topic counts now and why that search is still not answered by one.
   - a SPONSOR's name read as the start of a word: "bail" found every bill of a
     member named Bailey. A name matched as a whole word after that, and
     since 17 October 2026 matches nothing (A NAME IS NOT WHAT A BILL IS
     ABOUT, below).
   - a SYNONYM read as the start of a word: "alien" found "parental alienation".
     The reader's own word still matches as a start ("educat" finds education),
     but a word this file supplies matches as itself, or with an ending.
   - no order: the 33 bills titled about school funding sat among 74 that only
     share the Education Funding committee. Best match puts the title first.
   And on 1 October, read against 312 searches, from a fifth:
   - an ENDING on a short word makes another word. "ai" with a d is "aid" and
     "car" with a d is "card": "ai" listed 33 bills about aid and air and none
     about artificial intelligence. A word of one or two letters takes a
     plural s and nothing else; one of three letters a plural, and -ed or
     -ing only where English adds them without doubling the last letter
     ("taxing", "towed" -- not "rating", which is not "rat"). In a phrase it
     is the last word that takes the ending. */
const RXW=Object.create(null);
function altRx(term){
  if(RXW[term])return RXW[term];
  const n=term.length-term.lastIndexOf(" ")-1;
  const ends=n<3?"s?":n===3?(/[wxy]$/.test(term)?"(?:s|es|ed|ing|ings)?":"(?:s|es)?")
    :"(?:s|es|ed|d|ing|ings|er|ers|al)?";
  return RXW[term]=new RegExp("\\b"+rxEsc(term)+ends+"\\b");
}
/* The reader's own word, or its singular: matched as the start of a word.
   Not a word the table owns (`exact`). Not a word of one or two letters:
   nothing "ai" or "ev" began was ever what the reader meant. And not the
   singular of a four-letter plural -- "cars" is "car", not "care" and "card";
   the plural itself, as typed, still is.
   One exception, `short`, set by readShort() below, term by term: in a
   term where the search as typed lists nothing, a word of two letters is
   read as a start after all. "special ed" found 21 bills while "ed" began
   "education", and none once a two-letter word had to be a word. */
const typedAlt=(g,alt,term)=>!g.exact&&(alt.length>2||(!!g.short&&g.short.has(term||"")))
  &&!alt.includes(" ")
  &&(alt===g.word||alt===g.pre||(g.word.length>4&&alt===stem(g.word)));
function inText(hay,g,alt,term){ return typedAlt(g,alt,term)?hasTerm(hay,alt):altRx(alt).test(hay); }

/* THE BILLS' OWN WORDS: THE TOPIC, THE ANALYSIS AND THE TEXT (1 October).
   The person: "I want the system to be smart enough to find what a user is
   likely looking for if they don't know the bill number, so that may also
   include the bill text itself or the topic."

   A title is ten words in statutory vocabulary. Of 499 bills a reader who
   had never seen this file wanted from fifty everyday searches, 268 share no
   word with their own title. What says what a bill is about is the bill:
   - its TOPIC, the heading the General Court files it under (or, for an
     archived term, the one this site's model gave it). It is in the index
     already. A single word the reader typed that is a word of the topic's
     name lists the topic's bills: "housing", "elections", "gambling",
     "insurance". Only a single typed word, never a phrase or a synonym (in a
     search of several words, only as fitAlone() says below), and only a topic
     that names ONE subject: "mental health" would be all 118
     bills filed under Public and Mental Health, ambulances and prescription
     prices among them, which is the 14 September finding above and still
     true; and under Welfare/Medicare/Medicaid a Medicare supplement bill is
     not a Medicaid bill. In "Taxes - Local" the subject is "taxes".
   - its ANALYSIS and its TEXT. Those are 16 MB for one term, so the build
     (build_search_index.py) reduces them to site/sidx/<term>.json: for each
     word, the bills it is central to and how central, 1 to 9. A word used
     once in a forty-page budget is not there; a word in the drafters' own
     summary is. The page fetches that file only when somebody searches, and
     hands it to indexAdd(). Until it arrives, and if it never does, the
     search reads titles as it always did.

   WHAT IS READ THERE. The reader's own word, whole, or its singular, and the
   table's terms. Not a synonym SYN supplied: those were chosen for titles,
   and read in the text "law enforcement" listed a bill on smoking in cars,
   whose text says "police" twice. A weight of 0 is a mention that is not
   central, kept for the table's wording only; it counts under an entry's
   `with` and `once`, and nowhere else.

   A SINGLE WORD THE TABLE SUPPLIED IS READ IN THE ANALYSIS, NOT THE TEXT
   UNDER IT. A phrase of the table is specific ("risk protection order",
   "gender reassignment"); a single word is not. Read in the body of a text,
   "gun control" listed a speed enforcement fund (radar guns), two bills on
   single-use bags and one on Selective Service; "abortion" a ban on
   bisphenol A in baby food ("reproductive toxicants"); "illegal immigrants"
   invasive species and five bills on alien insurers; "landlord" balloons
   released into the air. Measured over the 115 judged searches on 1
   October, a single table word found in a text and nowhere else was never
   a bill a search was judged to want, and was six of the bills judged
   wrong. The drafters' analysis is where a bill says what it is about; the
   text is still read for the word the reader typed, and for a single word
   under an entry's `with`, where a second thing must be there too.

   A LONGER WORD THE READER'S BEGINS ("legaliz" and legalization) is found
   there as it is in a title, but only when the word is the whole search:
   "organ donation" listed political donations to organizations. And only
   for a word of six letters or more (2 October). From four, "bail" listed a
   bill on cloud-stored files whose analysis says "bailment", ninth of nine
   under "in the bill's analysis". Read over the 400 commonest words of the
   term's titles, a short word's longer words are mostly other words -- fee
   and feet, card and cardiac, plan and plant, term and terminal, land and
   landlord, post and postpartum -- and a long word's are mostly the word:
   municipal and municipality, license and licensee, establish and
   establishment, citizen and citizenship. Six is where expand(), above,
   already lets a word reach a longer one ("rates" is not "ratepayer"). In a
   TITLE the start of a longer word still counts from any length, lower
   down, as the person ruled ("bail" and the bailiffs). A card listed this
   way says the word it was listed for: "analysis says: municipality".

   IN A SEARCH OF SEVERAL WORDS each must be found, and a word found
   outside the title must stand beside another word of the search there
   (WORDS THAT STAND TOGETHER, below). Until 2 October each could be found
   in a different place, because the index held words and not where they
   stand. Each such card says "in the bill's text", and is listed after
   every bill whose title has the words.

   The file names a bill by its id and is asked for by the bill's term, so a
   stale file can fail to find a bill and cannot find the wrong one.

   WORDS THAT STAND TOGETHER (2 October). "Each may be found in a different
   place" was the paragraph above this one, and it listed bills that are not
   about what was typed: for "medical debt" the consolidation of the health
   and education facilities authority (its analysis mentions the assumption
   of debts); for "small claims" a tariff tax credit for small businesses,
   whose text says "approved claims"; for "child labor" hard labor as a
   sentence for assaults on children. Six of thirty searches nobody had tuned
   put such a bill in the first ten, and in three it was the first or the
   only one. Before the text was read none of them was listed.

   So in a search of several words, a plain word found only in a bill's
   analysis or text counts only where it STANDS BESIDE another word of the
   search there -- next to it, either way round, with nothing between them
   but words that carry no subject ("custody of children"). The file says
   which pairs of words do: under "b", for each bill, five letters a pair
   (pairCode; build_search_index.py makes them and explains why a pair is a
   code and not two words). The word beside it may be any wording of the
   other part: its synonyms, the table's terms, the first or last word of a
   phrase. Read against every judged search (2 October), every bill that was
   wanted and had been found this way has its words together -- "domestic
   violence", "nursing homes", "town meeting", "child custody
   determination" -- and each of the wrong ones above has them apart.

   Not asked of a word the table owns or supplies (that wording is specific
   already), of a typed phrase, nor beside a two-letter word read as a
   start, which is itself a last resort. Nor where every other part of the
   search is the table's and the TITLE has it: a bill titled for the
   right-to-know law is about public records, and "public records request"
   lists it for the requests its text is about, wherever they stand. That
   is not said of a plain word in a title -- "small" in "small businesses"
   settles nothing about "small claims". And a file from before the pairs
   has none: the search then lists less, and nothing wrong. */
const LONGER_FROM=6;
const SIDX=Object.create(null);
let SIDXGEN=0;
function indexAdd(term,data){
  if(!term||!data||data.v!==1||!Array.isArray(data.ids))return false;
  SIDX[term]={ids:data.ids,w:data.w||{},p:data.p||{},
    b:Array.isArray(data.b)?data.b:[],keys:null,near:null};
  SIDXGEN++;
  return true;
}
// Two words that stand together, as the file keeps them: thirty bits of the
// FNV-1a hash of "first second", in five letters. build_search_index.py's
// pair_code() is this, and preflight runs both over the same pairs.
const CODE64=".BCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
function pairCode(first,second){
  const s=first+" "+second;
  let h=0x811c9dc5;
  for(let i=0;i<s.length;i++)h=Math.imul(h^s.charCodeAt(i),0x01000193)>>>0;
  h=(h^(h>>>30))&0x3fffffff;
  let out="";
  for(let k=24;k>=0;k-=6)out+=CODE64[(h>>>k)&63];
  return out;
}
// One term's pairs, as {code: the bills that have it}. Made the first time a
// search of several words needs it.
function nearMap(X){
  if(X.near)return X.near;
  const m=new Map();
  X.b.forEach((codes,i)=>{
    if(typeof codes!=="string")return;
    for(let j=0;j+5<=codes.length;j+=5){
      const c=codes.slice(j,j+5),at=m.get(c);
      if(at)at.push(X.ids[i]);else m.set(c,[X.ids[i]]);
    }
  });
  return X.near=m;
}
// The keys a word is filed under: itself, its singular, and itself with the
// endings a title match allows. build_search_index.py's word_keys() is this.
function wordKeys(alt){
  const n=alt.length;
  const ends=n<3?[]:n===3?(/[wxy]$/.test(alt)?["ed","ing"]:[]):["ed","d","ing","er","al"];
  return new Set([alt,stem(alt),...ends.map(e=>alt+e)]);
}
// One list of the file as [how far short, in the analysis, the bill's word,
// found by a term this file supplied] per bill id; the best kept.
function readPosts(X,posts,m,base,step,alt,tab,onlyA,once){
  if(!Array.isArray(posts))return;
  let i=0;
  for(const n of posts){
    i+=Math.floor(n/20);
    const w=n%10,inA=n%20>=10;
    if((onlyA&&!inA)||(!w&&!once))continue;
    const d=base+(9-w)*step,id=X.ids[i],cur=m.get(id);
    if(!cur||d<cur[0])m.set(id,[d,inA,alt,tab]);
  }
}
// What one part of a search finds in one term's analyses and texts.
function textHits(g,term){
  const X=SIDX[term];
  if(!X)return null;
  const memo=g._tx||(g._tx={});
  if(memo[term]&&memo[term].X===X)return memo[term].hits;
  const m=new Map(),once=!!g.once;
  g.alts.forEach((alt,i)=>{
    const tab=(g.tab!=null&&i>=g.tab)||!!(g.terms&&g.terms.includes(alt));
    // The reader's own word: as typed, its singular, and the plural that is
    // not made with an s -- "child" is filed under "children" as "dogs" is
    // under "dog".
    const own=g.exact?(!tab&&g.plain.includes(alt))
      :(typedAlt(g,alt)||alt===g.word||alt===stem(g.word)||alt===g.odd);
    if(!own&&!tab)return;                  // a synonym: titles only
    const base=own?0.6:1.6;
    // In the analysis only: wording the entry marks `named`, and any single
    // word this file supplied, unless the entry asks for a second thing as
    // well (`with`). See WHAT IS READ THERE, above.
    const onlyA=(g.nam!=null&&i>=g.nam)||!!(g.ownNamed&&g.ownNamed.includes(alt))
      ||(tab&&!own&&!g.with&&!alt.includes(" "));
    if(alt.includes(" ")){readPosts(X,X.p[alt],m,base,0.04,alt,!own,onlyA,once);return;}
    const keys=wordKeys(alt);
    for(const k of keys)readPosts(X,X.w[k],m,base,0.04,alt,!own,onlyA,once);
    // A longer word the reader's begins, from six letters (A LONGER WORD THE
    // READER'S BEGINS, above). The card says which word.
    if(g.solo&&typedAlt(g,alt)&&alt.length>=LONGER_FROM)
      for(const k of X.keys||(X.keys=Object.keys(X.w)))
        if(k.length>alt.length&&k.startsWith(alt)&&!keys.has(k))
          readPosts(X,X.w[k],m,1.2,0.03,k,true,false,false);
  });
  memo[term]={X,hits:m};
  return m;
}
// Under `with`: the second thing the bill must say, and where it says it.
function withHit(b,g){
  for(const t of g.with)if(altRx(t).test(b.hayT))return ["title",t];
  const X=b.term&&SIDX[b.term];
  if(!X)return null;
  const memo=g._wx||(g._wx={});
  if(!memo[b.term]||memo[b.term].X!==X){
    const m=new Map();
    for(const t of g.with){
      if(t.includes(" "))readPosts(X,X.p[t],m,0,0,t,true,false,g.once);
      else for(const k of wordKeys(t))readPosts(X,X.w[k],m,0,0,t,true,false,g.once);
    }
    memo[b.term]={X,hits:m};
  }
  const h=memo[b.term].hits.get(b.id);
  return h?[h[1]?"analysis":"text",h[2]]:null;
}
// What the reader typed for one part of a search: the word, its singular, a
// verb without its last letter. Not a synonym, nor a term the table supplied.
const ownAlts=g=>g.alts.filter(alt=>!alt.includes(" ")
  &&(typedAlt(g,alt)||alt===g.word||alt===stem(g.word)));
// The keys the file's pairs are made of, for these words: the word and its
// singular, and the word with an ending where some bill of the term is
// filed under that. A phrase stands beside a word by its first or last word.
function pairKeys(X,alts){
  const out=new Set();
  for(const alt of alts){
    const ws=alt.split(" ");
    for(const w of ws.length>1?[ws[0],ws[ws.length-1]]:ws){
      if(!/^[a-z0-9']+$/.test(w))continue;
      const bare=w.replace(/'s$/,"").replace(/'/g,"");
      out.add(bare);out.add(stem(bare));
      for(const k of wordKeys(bare))if(Array.isArray(X.w[k]))out.add(k);
    }
  }
  out.delete("");
  return out;
}
// The bills of one term in whose analysis or text this part of a search
// stands beside another part of it (WORDS THAT STAND TOGETHER, above).
function besideHits(g,term){
  const X=SIDX[term];
  if(!X)return null;
  const memo=g._bx||(g._bx={});
  if(memo[term]&&memo[term].X===X)return memo[term].hits;
  const beside=new Set(),near=nearMap(X);
  const mine=pairKeys(X,ownAlts(g));
  const theirs=pairKeys(X,g.peers.flatMap(o=>o.alts));
  for(const x of mine)for(const y of theirs){
    if(x===y)continue;
    for(const c of [pairCode(x,y),pairCode(y,x)]){
      const at=near.get(c);
      if(at)for(const id of at)beside.add(id);
    }
  }
  memo[term]={X,hits:beside};
  return beside;
}
/* WRITTEN AS ONE WORD, OR TWO, OR WITH A HYPHEN (2 October). Seven titles
   say "E-Z Pass" and only that spelling found them: "ez pass", "ezpass" and
   "e-zpass" each listed nothing in any term. A hyphen is read as a space on
   both sides, so the title was the three words "e z pass" and no joined
   spelling could match. The same letters are one thing however they are
   spaced -- "nonprofit" and "non-profit", "reassessment" and
   "re-assessment", "day care" and "daycare" -- so a title is also read with
   the hyphens taken out of each word of it, and with each two words of it
   that stand together run into one; and two plain words typed next to each
   other are also read as one. A run of two is read only for a word of five
   letters or more, and never across a word the search skips ("in come" is
   not income). */
function joinedTitle(b){
  if(b.hayJ!==undefined)return b.hayJ;
  const h=[],j=[];
  let prev="";
  for(const raw of String(b.title||"").toLowerCase().split(/[^a-z0-9\-]+/)){
    const w=raw.replace(/^-+|-+$/g,"");
    if(!w){prev="";continue;}
    const one=w.replace(/-/g,"");
    if(one!==w)h.push(one);
    if(prev&&!STOPSET.has(prev)&&!STOPSET.has(one)&&!/^\d+$/.test(prev)&&!/^\d+$/.test(one))j.push(prev+one);
    prev=one;
  }
  return b.hayJ=h.length||j.length?{h:" "+h.join(" ")+" ",j:" "+j.join(" ")+" "}:null;
}
function asOne(b,alt){
  const J=joinedTitle(b);
  return !!J&&(altRx(alt).test(J.h)||(alt.length>=5&&altRx(alt).test(J.j)));
}
// TAGS:BEGIN
/* THE TAGS (topics as tags, stages 3 and 4: reports/topics-as-tags-design-
   2026-11.md, sections 5 and 6), SWITCHED OFF UNTIL THE OWNER APPROVES THE
   LIST. build_site_v2 writes them into meta.json only where her registry,
   corrections/tags.json, is in force, and build_pages publishes this file's
   TAGS regions only then; without them every function here does nothing.
   META.tags is the list, each {id, name, group, definition} in the
   registry's own words, which are the only words a page says of a tag
   (design 6.3), and only on a bill's own page and in the Tags filter (the
   owner, 17 November 2026: no card or list shows one); a bill's index row
   carries its tags as places in that list.
   META.tag_words is what a reader may type and where it leads: "tag:ID", or
   "topic:Name" for a word whose subject is a topic ("weed", the topic
   Cannabis), as tag_rules.synonym_table makes it. setTagWords hands both to
   the matcher: app.js when meta.json arrives, find.js for the header search
   and /search. */
let TAGLIST=[],TAGWORDS=new Map();
// A word as the table is looked up: lower case, letters and digits, one space.
const tagKey=w=>String(w||"").toLowerCase().replace(/['‘’]/g,"").replace(/[^a-z0-9+]+/g," ").trim();
function setTagWords(tags,words){
  TAGLIST=Array.isArray(tags)?tags.filter(t=>t&&t.id&&t.name):[];
  TAGWORDS=new Map();
  if(TAGLIST.length&&words&&typeof words==="object")
    for(const w of Object.keys(words))if(tagKey(w))TAGWORDS.set(tagKey(w),String(words[w]));
}
// A bill's tags, by id, in the registry's order; and a tag by its id.
const tagIdsOf=b=>(b&&Array.isArray(b.tags)?b.tags:[]).map(i=>TAGLIST[i]&&TAGLIST[i].id).filter(Boolean);
const tagOf=id=>TAGLIST.find(t=>t.id===id)||null;
// TAGS:END
// TAGS:BEGIN
// Whether a bill is where a word leads: a tag it carries, or its topic.
function tagLeads(b,to){
  const s=String(to||""),i=s.indexOf(":"),k=s.slice(0,i),v=s.slice(i+1);
  return k==="tag"?tagIdsOf(b).includes(v):k==="topic"?String(b.topic||"")===v:false;
}
/* A TAG'S WORD, OR A TOPIC'S, LISTS ITS BILLS (design 6.1; the owner, 17
   November 2026: tags "may replace the synonym matching system by having
   those sorts of synonyms built in but not displayed"). A part of the
   search that is a tag's name or one of the words that lead to it (the
   registry's asks and synonyms) carries where it leads, `to`, and where it
   is the whole search fitAlone lists that tag's bills, or that topic's,
   after every bill whose title says the reader's word and every bill whose
   analysis or text does ("eviction" lists the bills that say it first;
   measured on tests/search_cases.json, 17 November 2026: at a topic's own
   level, 0.5, a tagged bill came above them). A topic is said on the card as ever ("topic:
   Cannabis"); a tag, and the words that led to it, never are (whyListed).
   The whole word or phrase only, never the start of one, so a large tag is
   not listed for a few letters; and the whole search only, never one word
   of a longer one, where it listed a bill the words found apart ("college
   students voting", tests/search_cases.json). A whole search of several
   words that is one such phrase ("attorney general", "gravel tax") is read
   as that phrase, one part, where it was a part a word. */
function tagGroups(out,typed){
  if(!TAGLIST.length||!TAGWORDS.size)return;
  const whole=tagKey(typed);
  if(out.length>1&&whole.includes(" ")&&TAGWORDS.has(whole)){
    const w=String(typed).trim();
    out.splice(0,out.length,{word:w,alts:[w]});
  }
  if(out.length===1){const to=TAGWORDS.get(tagKey(out[0].word));if(to)out[0].to=to;}
}
// TAGS:END
// The topic's name as searched: what stands before " - ", and nothing at all
// where that names more than one subject.
const topicHay=b=>{
  if(b.hayP!==undefined)return b.hayP;
  const head=String(b.topic||"").toLowerCase().split(" - ")[0];
  return b.hayP=/[,&\/]| and /.test(head)?"":head.replace(/[^a-z0-9']+/g," ");
};
/* HOW FAR SHORT OF THE WORD ITSELF ONE PART OF A SEARCH FALLS ON ONE BILL
   (the person, 25 September: "have direct word matches be at the top of the
   best match sorting"; and 1 October, the order for what the bill's own
   words add). null where the bill does not have the part at all. Otherwise
   [how far short, why, and under `with` the second thing found]:
     0     a word of the title -- the word itself, with one of altRx's
           endings ("guns", "taxes"), one of its synonyms, or the letters
           typed written out in full ("dwi", driving while intoxicated);
     0.5   a word of the topic the bill is filed under;
     0.6 to 0.96   in the analysis or the text, the most central first;
     1     the title has only a longer word the part begins ("bail" and the
           bailiffs, "gun" and the Gunstock Area Commission), or a term of
           the table that is the word with another ending ("eviction" and
           "evict");
     1.2 to 1.5    the analysis or text has only such a longer word;
     1.45  the bill has both things an entry's `with` asks for;
     1.5   the title has none of the reader's words and has one of the terms
           the table (CONCEPTS) stands them for;
     1.6 to 2      the analysis or text has one of those terms;
           (either, a tenth less for each word of a typed phrase that the
           title has: "concealed carry" lists the titles that say "carry"
           before the rest of the firearms entry;)
     2     only a committee's name has it; 3 where that has a longer word.
   Best match orders by the total before anything else, so a bill whose title
   has every word of the search is never listed below one that has only the
   start of one, and a bill the table found is never listed above either.
   A committee's name counts for less than a longer word in the title: that
   is "Best match puts the title first", above, kept. Counted as direct, the
   committee put the 187 bills of 2025-2026 whose only link to "municipal"
   is a committee named for municipal affairs above the 26 whose titles say
   "municipalities".

   A NAME IS NOT WHAT A BILL IS ABOUT (17 October 2026). The person: "Searching
   a representative's name like alice should not show bills sponsored by alice
   wade on the bill search page or the general search page since there's a
   separate filter for searching by rep." Until that day a word of the prime
   sponsor's name counted as a word of the title, and the notes here had grown
   rules to keep it in its place: "bail" was not Rep. Bailey, "weeds" not Rep.
   Weed, "gay" not Rep. Betty Gay's 36 bills on election officers. Every one of
   those rules existed because a name kept answering searches about subjects.
   Now the sponsor and the co-sponsors are matched by nothing typed in the box:
   the Sponsor filter is where a person's bills are found, /search and the
   header list the person themselves, and /bills offers that filter when the
   name typed lists nothing (sponsorHint, below). A bill whose title, topic,
   analysis or text has the word still lists, whoever filed it. */
function fitAlone(b,g){
  let d=4,why=null;
  const out=g.not&&g.not.some(t=>hasTerm(b.hayT,t));
  for(let i=0;i<g.alts.length;i++){
    const alt=g.alts[i];
    if(g.tab!=null&&i>=g.tab){
      // The word typed, written out or with another ending (g.near), is
      // nearer than the rest of what the table supplied.
      const far=g.near&&g.near.has(alt)?g.near.get(alt):1.5;
      if(!out&&d>far&&altRx(alt).test(b.hayT)){d=far;why=far?["title",alt]:null;}
      continue;
    }
    const own=typedAlt(g,alt)||alt===g.word;
    if(altRx(alt).test(b.hayT)||(own&&!g.exact&&asOne(b,alt))){d=0;why=null;break;}
    if(d>1&&inText(b.hayT,g,alt,b.term)){d=1;why=null;}
    if(d>2&&own&&altRx(alt).test(b.hayC)){d=2;why=null;}
    if(d>3&&own&&inText(b.hayC,g,alt,b.term)){d=3;why=null;}
  }
  // Two words typed that the title writes as one: "day care" and daycare,
  // "e zpass" and E-ZPass.
  if(d>0&&g.joins&&g.joins.some(j=>altRx(j).test(b.hayT)||asOne(b,j))){d=0;why=null;}
  // The topic. For a word that is the whole search, a word of the topic's
  // name. In a search of several words a topic stands for one of them only
  // when it is that word and nothing else, and the title has every other:
  // "property taxes" lists a bill titled about real property and filed
  // under Taxes, but "car insurance" listed seventeen health insurance
  // bills (the topic Insurance, and "care" or "carrier" in the title) and
  // "civil rights" a bill on rights in private roads (the topic Civil
  // Actions).
  if(d>0.5&&!g.exact&&!g.word.includes(" ")&&b.topic){
    const t=topicHay(b);
    if(t&&(altRx(g.word).test(t)||(g.word.length>4&&altRx(stem(g.word)).test(t)))
       &&(g.solo||(g.rest&&!/\S\s+\S/.test(t)
          &&g.rest.every(alts=>alts.some(a=>altRx(a).test(b.hayT)))))){d=0.5;why=["topic"];}
  }
  // TAGS:BEGIN
  // Where a tag's word or a topic's leads (tagGroups), for the whole search
  // only, at 1.1: after a bill whose title has the word or a longer word it
  // begins (1) and one whose analysis or text has the word itself (0.6 to
  // 0.96), and before the rest -- a longer word in a text, the table's
  // terms. The tag's id third, where no word found is: nothing is "found"
  // in it, and the card says nothing (whyListed).
  if(d>1.1&&g.solo&&g.to&&tagLeads(b,g.to)){
    d=1.1;why=/^tag:/.test(g.to)?["tag","",g.to.slice(4)]:["topic"];}
  // TAGS:END
  if(d>0.6&&b.term){
    const m=textHits(g,b.term),h=m&&m.get(b.id);
    if(h&&h[0]<d&&!(out&&h[3])){d=h[0];why=[h[1]?"analysis":"text",h[3]?h[2]:""];}
  }
  if(d>=4)return null;
  // A bill the table found whose title has words of the phrase typed is
  // listed before one that has none: "concealed carry" is an ask of the
  // whole firearms entry, and the titles that say "carry" come first of it.
  if(d>=1.5&&d<2&&g.parts){
    let n=0;
    for(const w of g.parts)if(altRx(w).test(b.hayT)||altRx(stem(w)).test(b.hayT))n++;
    d-=Math.min(n,3)*0.1;
  }
  if(g.with&&!g.stands.some(t=>altRx(t).test(b.hayT))){
    const second=withHit(b,g);
    if(!second)return null;
    // Two things the bill says together are worth more than one term in a
    // title: listed just ahead of those.
    return [Math.min(d,1.45),why,second];
  }
  return [d,why];
}
/* IN A SEARCH OF SEVERAL WORDS, TWO WEAK FINDINGS ARE NOT A BILL. A longer
   word in the title is a guess at what the reader meant, and so is a word
   that only the topic, the analysis or the text has. One guess a bill is
   listed for, after the bills that have the words. Both together listed nine
   bills on health carriers for "car insurance" -- "care" or "carrier" in the
   title, "insurance" in the analysis -- and tax dollars donated to
   non-profit organizations for "organ donation". So the start of a longer
   title word does not count beside a word found only outside the title.
   Not for a two-letter word read as a start (readShort): that reading is
   itself the last resort of a search that listed nothing.

   THE SAME OF EVERY GUESS (2 October). A committee's name is a guess too.
   "child labor" listed two bills heard by a Labor committee whose text says
   "child". So neither counts beside a word found only outside the title,
   and the two do not count together, unless both are the committee's name
   ("ways means").
   And a two-letter word read as a start counts beside the reader's own
   words, not beside a synonym this file supplied: "student id" listed
   "identifying certain school district offices" (id, identifying; student,
   school).

   NO NAME, AND NO TITLE BEFORE ONE (17 October 2026). From 2 October a
   sponsor's name was read here too -- "senator carson" as Sen. Sharon
   Carson's bills, "tim lang" as Sen. Timothy Lang's -- with "rep" and
   "senator" read as the sponsor's title. The person asked that a name not
   list bills at all (A NAME IS NOT WHAT A BILL IS ABOUT, above), so that
   reading is gone, and "rep" or "senator" is a word like any other.

   And a plain word found only in the analysis or the text counts only
   where it stands beside another word of the search there: WORDS THAT
   STAND TOGETHER, above. */
// A longer word in the title, or a committee's name.
const weakFit=f=>f[0]>=1&&!f[1];
// The title has this part in the reader's own word, not a synonym of it.
const ownInTitle=(b,o)=>ownAlts(o).some(a=>altRx(a).test(b.hayT)||asOne(b,a))
  ||!!(o.joins&&o.joins.some(j=>altRx(j).test(b.hayT)||asOne(b,j)));
// The title has this part of the search, and the part is the table's.
function tableInTitle(b,o){
  if(!o.exact&&o.tab==null)return false;
  const x=fitAlone(b,o);
  return !!x&&(x[1]?x[1][0]==="title":x[0]===0);
}
/* WHAT A PART OF A SEARCH FOUND IN A BILL IS WORKED OUT ONCE. One drawing of
   /bills asks it six times over -- the list, each of four filters' counts,
   the order -- and then again for every card's "Listed for" line: on All
   terms that was five seconds a letter on a phone and over half a second on
   a desktop (2 October), three quarters of it the filters' counts asking
   what the list had just been told. fit() and groupWeight() keep their
   answer for each bill on the group itself, for as long as the group is
   read the same way: until more of the bills' text arrives (indexAdd), or
   readShort() changes how a two-letter word is read. */
function recall(g,slot){
  let m=g[slot];
  if(!m||m.gen!==SIDXGEN)m=g[slot]={gen:SIDXGEN,of:new Map()};
  return m.of;
}
function fit(b,g){
  const of=recall(g,"_f");
  let f=of.get(b);
  if(f===undefined){f=fitNow(b,g);of.set(b,f);}
  return f;
}
function fitNow(b,g){
  let f=fitAlone(b,g);
  const peers=g.peers;
  if(!peers)return f;
  const t=b.term||"";
  if(!f)return null;
  if(weakFit(f)){
    const short=!!(g.short&&g.short.has(t));
    for(const o of peers){
      const x=fitAlone(b,o);
      if(!x)continue;
      if(short){
        if(x[0]===0&&!x[1]&&!o.exact&&!ownInTitle(b,o))return null;
        continue;
      }
      if(x[1]&&x[1][0]!=="title")return null;
      if(weakFit(x)&&!(f[0]>=2&&x[0]>=2))return null;
    }
    return f;
  }
  if(!g.exact&&g.tab==null&&!g.word.includes(" ")&&f[1]&&!f[1][1]
     &&(f[1][0]==="analysis"||f[1][0]==="text")){
    const others=peers;
    if(others.length&&!others.some(o=>o.short&&o.short.has(t))
       &&!others.every(o=>tableInTitle(b,o))){
      const beside=besideHits(g,t);
      if(!beside||!beside.has(b.id))return null;
    }
  }
  return f;
}
// 3 in the title, 1 in a committee's name, 0 not at all; and 2.5 where it is
// the topic, the analysis or the text that has it. The sponsor's name is not
// read (A NAME IS NOT WHAT A BILL IS ABOUT, 17 October 2026). A committee's
// name matches only what the reader typed: a synonym found in a committee's
// name ("energy", for "electric vehicles") put a bill about hunting from a
// vehicle in the results.
function groupWeight(b,g){
  const of=recall(g,"_w");
  let w=of.get(b);
  if(w===undefined){w=weightNow(b,g);of.set(b,w);}
  return w;
}
function weightNow(b,g){
  const f=fit(b,g);
  if(!f)return 0;
  if(f[1])return f[1][0]==="title"?3:2.5;
  let w=0;
  for(const alt of g.alts){
    if(inText(b.hayT,g,alt,b.term))return 3;
    if(!(typedAlt(g,alt)||alt===g.word))continue;
    if(w<1&&inText(b.hayC,g,alt,b.term))w=1;
  }
  return w||2.5;
}
function looseness(b,gs){
  let n=0;
  for(const g of gs){const f=fit(b,g);n+=f?f[0]:3;}
  return n;
}
/* HOW MUCH OF A SEARCH A BILL HAS: what best match orders by after
   looseness. 0 where it lacks a part of it. /bills, the header's panel,
   /search and preflight's cases each added this up for themselves, in four
   copies of one sentence; it is one function now, so that they cannot
   differ.
   Each part by where it was found (groupWeight); half a point more where
   the title has the reader's own word and not only a synonym of it; and two
   more where the title has the words of the search in order -- as they were
   typed, the skipped words still in them. "medical bills" is read as
   "medical", which SYN reads as health too: 183 bills, and the one titled
   "payment and dispute resolution for medical bills" was 57th of them (2
   October). */
function matchScore(b,gs){
  let s=0;
  for(const g of gs){
    const w=groupWeight(b,g);
    if(!w)return 0;
    s+=w+(ownInTitle(b,g)?0.5:0);
  }
  const words=gs.map(g=>g.word).join(" "),typed=gs.typed||"";
  if((gs.length>1&&b.hayT.includes(words))
     ||(typed.includes(" ")&&typed!==words&&b.hayT.includes(typed)))s+=2;
  return s;
}
/* HOW MUCH OF THE TITLE IS THE SEARCH: what best match breaks a tie by,
   after looseness and matchScore (16 October 2026, approved by the person
   that day). For a search of one word every bill whose title has it scores
   the same, and the bill number decided: "housing" opened on HB 465, 530,
   572 and 628 -- a revenue transfer, a program, a landlord's vouchers --
   while "relative to manufactured housing" was eighth, and 42 of the
   term's 138 housing bills shared that first place.
   The share is the title's words that carry a subject (not the words a
   search skips) that some part of the search has, over all of them: a word
   counted as often as the title says it, a synonym counted as matchScore
   counts it in a title, a phrase of the search covering each of its words.
   "manufactured housing" is half the search; "increasing the amount of
   revenue transfered from the real estate transfer tax to the affordable
   housing fund" is one word in eleven.
   A part counts as itself or with an ending (altRx), never as the start of
   a longer word: looseness has already put those below, and read as starts,
   "lang" counted every "language" in a title, and "rep" every "report".
   It reads the title and nothing else, so it cannot read an outcome: over
   fourteen searches the Passed and the Died among the first ten stayed near
   the share of each among everything listed. It was measured beside a
   bill's topic, which names a subject for five of the fourteen searches and
   is blind to the rest, and its latest action, which filled the first
   places with Interim Study, whose study hearings come in the autumn -- one
   outcome ranked above another, which the Status sort's own note forbids. */
// altRx's pattern, to find every place a title says it.
const RXSHARE=Object.create(null);
const shareRx=alt=>RXSHARE[alt]||(RXSHARE[alt]=new RegExp(altRx(alt).source,"g"));
// Worked out once for each bill and each reading of a search, as fit() is:
// /bills sorts again for every page of cards scrolled to and every card
// opened, and on All terms "education" lists 4,042 bills.
function titleShare(b,gs){
  const of=gs._share||(gs._share=new Map());
  let s=of.get(b);
  if(s===undefined){s=shareNow(b,gs);of.set(b,s);}
  return s;
}
function shareNow(b,gs){
  const t=String(b.title||"").toLowerCase().replace(/-/g," ");
  // Each word's start and end: "authority's" is one word, as it is read.
  const at=[];
  for(const m of t.matchAll(/[a-z0-9]+(?:['’][a-z]+)*/g))
    if(!STOPSET.has(m[0]))at.push([m.index,m.index+m[0].length]);
  if(!at.length)return 0;
  const said=new Set();
  for(const g of gs){
    // And two words typed that the title writes as one (WRITTEN AS ONE
    // WORD, OR TWO, OR WITH A HYPHEN).
    for(const a of g.joins?g.alts.concat(g.joins):g.alts)
      if(altRx(a).test(t))for(const m of t.matchAll(shareRx(a))){
        const end=m.index+m[0].length;
        at.forEach((w,i)=>{if(w[0]<end&&m.index<w[1])said.add(i);});
      }
  }
  return said.size/at.length;
}
/* WHY A BILL IS LISTED, where its title does not have the reader's word: in
   the bill's own words, never the reader's. "topic: Housing"; "in the bill's
   text" for the word typed; "text says: lavatory" for a word this file
   stood the typed one for. Nothing for a bill whose title or committee has
   the word -- the card shows those. */
function whyListed(b,gs){
  const said=[];
  for(const g of gs){
    const f=fit(b,g);
    if(!f)continue;
    const y=f[1],z=f[2];
    if(!y)continue;
    // TAGS:BEGIN
    // A bill a tag listed says nothing of it on its card (the owner, 17
    // November 2026: tags are a search tool, built in and not displayed).
    if(y[0]==="tag")continue;
    // TAGS:END
    let s=y[0]==="topic"?"topic: "+b.topic
      :y[1]?y[0]+" says: "+y[1]:"in the bill's "+y[0];
    if(z)s+=y[1]&&z[0]===y[0]?" and "+z[1]:", "+z[0]+" says: "+z[1];
    if(!said.includes(s))said.push(s);
  }
  return said.join("; ");
}
/* A SEARCH THAT LISTS NOTHING. Two things, and neither changes a search
   that lists a bill.

   A WORD OF TWO LETTERS, AS THE START OF A WORD. "special ed" found 21
   bills while "ed" began "education", and none once a two-letter word had
   to be a word -- which is right for "ai" and "ev", where the table has
   the word, and for a search that finds something. It is decided term by
   term: read over every term at once, "special ed" listed one bill, a 2001
   bill on number plates whose sponsor is an Ed, where this term alone
   listed 29. A wider search must never list less. (A sponsor's name lists
   nothing since 17 October 2026; a word of a title can do the same.)

   A WORD NO BILL HAS EVER USED, OFFERED AS THE WORD IT SOUNDS LIKE.
   "medicade" and "fentynal" find nothing. The page then offers the word of
   the bills being searched that sounds the same -- the same consonants in
   the same order, which is what a misspelling by ear keeps -- or, failing
   that, a word one letter away: "Did you mean medicaid?", with how many
   bills that finds. By sound first: "medicade" is one letter from Medicare
   and two from Medicaid, and it is Medicaid that it sounds like.

   IT IS AN OFFER, AND ONLY FOR A WORD THAT IS NOT ONE. For one day
   (1 October) the search was read again by itself, and the page said "no
   bill says incest: showing invest" over 98 bills about investment -- when
   three bills of the term say incest, in texts that are not about it.
   "white" was read as "with", "bible" as "bill", "syria" as "sharia", a
   former senator's name as "house" (2,052 bills), "salem" as "sale". What
   was missing was any way to know a real word from a misspelt one. So:
   - sidx/words.json (build_search_index.py) is every word of five letters
     or more that any bill of any term uses -- title, analysis, text,
     sponsor or committee -- with the names of members and towns. A word in
     it is a word, and is never offered as another. Nor is the start of
     one: "londo" is somebody typing Londonderry. The page fetches the file
     only when a search has listed nothing, and offers nothing without it;
   - a word is never offered as one the search skips ("with", "bill");
   - nothing is done until the reader chooses. A word the bills have never
     used can still be a word -- Haiti, lynching -- and offering "hate" for
     it is a poor guess; listing the hate crime bills under it unasked would
     be a wrong answer. */
const asSaid=w=>w.replace(/ph/g,"f").replace(/c(?=[eiy])/g,"s").replace(/[ckq]/g,"k").replace(/z/g,"s");
function soundKey(w){
  const s=asSaid(w);
  return (s[0]+s.slice(1).replace(/[aeiouyh']/g,"")).replace(/(.)\1+/g,"$1");
}
// Letters added, dropped, changed or swapped with a neighbour, up to `max`.
function lettersApart(a,b,max){
  if(Math.abs(a.length-b.length)>max)return max+1;
  let p2=null,p1=[];
  for(let j=0;j<=b.length;j++)p1[j]=j;
  for(let i=1;i<=a.length;i++){
    const row=[i];
    let low=i;
    for(let j=1;j<=b.length;j++){
      const c=a[i-1]===b[j-1]?0:1;
      row[j]=Math.min(p1[j]+1,row[j-1]+1,p1[j-1]+c);
      if(i>1&&j>1&&a[i-1]===b[j-2]&&a[i-2]===b[j-1])row[j]=Math.min(row[j],p2[j-2]+1);
      if(row[j]<low)low=row[j];
    }
    if(low>max)return max+1;
    p2=p1;p1=row;
  }
  return p1[b.length];
}
// The words the bills being searched can be found by, with how many bills:
// what a title says and what the search index files a bill under. Not a word
// the search skips: "white" is two letters from "with".
let VOCAB=null;
function vocabOf(rows){
  if(VOCAB&&VOCAB.rows===rows&&VOCAB.n===rows.length&&VOCAB.gen===SIDXGEN)return VOCAB.list;
  const words=new Map(),add=(w,n)=>{if(w.length>=4&&/^[a-z]+$/.test(w)&&!STOPSET.has(w))
    words.set(w,(words.get(w)||0)+n);};
  const terms=new Set();
  for(const b of rows){
    terms.add(b.term);
    for(const w of b.hayT.split(/[^a-z]+/))add(w,1);
  }
  for(const t of terms){
    const X=SIDX[t];
    if(X)for(const k in X.w)add(k,X.w[k].length);
  }
  VOCAB={rows,n:rows.length,gen:SIDXGEN,list:words};
  return words;
}
/* HOW CLOSE. Read against 182 real words no bill has used and 36 common
   misspellings (1 October): two letters apart is a misspelling only in a
   long word -- "medicade", "fentynal" -- and in a short one it is another
   word (Haiti and hate, Kenya and keno, Amish and amass). And a word spelt
   by ear keeps how it starts: "lynching" is not "launching", nor "proton"
   "portion". So: the first two letters as they sound; then the same sound
   and one letter apart, or two in a word of eight letters or more; or
   another sound and one letter apart ("pention", "morgage"). That offered
   26 of the 36 their word, and 3 of the 182 another (photon as photo; 6
   over every term, Mormon as Morton among them).
   The second letter may differ where the sound is the same (2 October):
   "tabacco" is tobacco, the same consonants in the same order, and was
   offered nothing because its second letter is a vowel spelt by ear. */
function soundsLike(word,rows){
  const key=soundKey(word),said=asSaid(word),head=said.slice(0,2),most=word.length>=8?2:1;
  let best=null;
  for(const [v,n] of vocabOf(rows)){
    const sv=asSaid(v);
    if(sv[0]!==said[0])continue;
    const same=soundKey(v)===key;
    if(!same&&sv.slice(0,2)!==head)continue;
    const far=lettersApart(word,v,same?most:1);
    if(far>(same?most:1)||!far)continue;
    const score=[same?0:1,far,-n];
    if(!best||score[0]<best[0][0]||(score[0]===best[0][0]&&(score[1]<best[0][1]
      ||(score[1]===best[0][1]&&score[2]<best[0][2]))))best=[score,v];
  }
  return best&&best[1];
}
// A part of a search that is one plain word: not the table's, not a phrase.
const plainWord=g=>!g.exact&&g.tab==null&&!g.word.includes(" ")&&/^[a-z]+$/.test(g.word);
// The groups of a search as they are read against these bills. In each term
// where the search as typed lists nothing, a word of two letters is read as
// the start of a word. The groups handed in are the ones handed back.
function readShort(gs,rows){
  const two=gs.filter(g=>plainWord(g)&&g.word.length<3);
  if(!two.length)return gs;
  // What each part found is kept on it (recall, above), and a part's answer
  // turns on how its neighbours are read.
  const forget=()=>gs.forEach(g=>{g._f=g._w=null;});
  two.forEach(g=>{g.short=null;});
  forget();
  const seen=new Set(),found=new Set();
  for(const b of rows){
    const t=b.term||"";
    seen.add(t);
    if(!found.has(t)&&gs.every(g=>fit(b,g)))found.add(t);
  }
  const none=new Set([...seen].filter(t=>!found.has(t)));
  if(none.size){two.forEach(g=>{g.short=none;});forget();}
  return gs;
}
/* Every word any bill has used, and the names of members and towns: what
   build_search_index.py writes as sidx/words.json. A file of another
   version, or one with no words in it, is refused, and nothing is offered. */
let KNOWN=null;
function wordsAdd(data){
  if(!data||data.v!==1||typeof data.words!=="string"||!data.words)return false;
  KNOWN={set:new Set(data.words.split(" ")),starts:new Map()};
  return true;
}
// A word the bills use, or the start of one.
function knownWord(w){
  if(KNOWN.set.has(w)||KNOWN.set.has(stem(w)))return true;
  if(!KNOWN.starts.has(w)){
    let yes=false;
    for(const k of KNOWN.set)if(k.length>w.length&&k.startsWith(w)){yes=true;break;}
    KNOWN.starts.set(w,yes);
  }
  return KNOWN.starts.get(w);
}
/* For a search that lists nothing among these bills: null where there is
   nothing to offer; {need:true} where there may be and the known words have
   not been handed over (wordsAdd); or {q, read, n} -- the search to offer in
   its place, the [word typed, word offered] pairs, and how many of these
   bills it lists. The whole search is read again, so that "vacine mandate"
   is offered as the phrase "vaccine mandate". Only where every term's text
   has been read: the words a bill can be found by are half in that file. */
function spelling(gs,rows){
  const odd=gs.filter(g=>plainWord(g)&&g.word.length>=5&&!rows.some(b=>fit(b,g)));
  if(!odd.length)return null;
  for(const b of rows)if(!b.term||!SIDX[b.term])return null;
  if(!KNOWN)return {need:true};
  const read=[];
  const words=gs.map(g=>{
    if(!odd.includes(g)||knownWord(g.word))return g.word;
    const v=soundsLike(g.word,rows);
    if(v)read.push([g.word,v]);
    return v||g.word;
  });
  if(!read.length)return null;
  const q=words.join(" "),again=readShort(queryGroups(q),rows);
  let n=0;
  for(const b of rows)if(again.every(g=>fit(b,g)))n++;
  return n?{q,read,n}:null;
}
// BILLMATCH:END
