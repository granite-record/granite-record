# Spanish to proofread

Every Spanish entry still marked draft: those on `dev`, and those on the branches not yet in it.

- **Every row** is in [`proofread.csv`](proofread.csv) beside this page, one row a draft, sorted by place on the site. It opens in a spreadsheet.
- **To correct and pass entries**, use the proofreader's own sheet: `python3 src/ops/translations.py --sheet es.csv --drafts` gives it, and `--take es.csv` brings the corrections back. That sheet holds `dev`'s drafts only; a branch's drafts join it once the branch is in `dev`.
- **Generated** from `src/pages/lang/es.json` on each branch, by key, on 30 October 2026. Where a branch changes an entry `dev` already has, the branch's words are the row.

| Where the words come from | Drafts |
|---|---|
| `dev` | 5052 |
| `cohesion`, the cohesion batch, for 11 November | 16 |
| `guides`, the guides batch, held to 4 November | 15 |
| `live/session`, the live layer (live/page and live/session), from about 3 November | 65 |
| **All** | **5117** |

## By place on the site

| Place | Drafts | From a branch |
|---|---|---|
| A how-to guide: attend-a-hearing | 48 |  |
| A how-to guide: boating | 58 |  |
| A how-to guide: building-permits | 59 |  |
| A how-to guide: car-insurance | 62 | 1 |
| A how-to guide: child-care-scholarship | 51 | 1 |
| A how-to guide: consumer-rights | 48 | 1 |
| A how-to guide: contact-your-legislators | 29 |  |
| A how-to guide: disability-help | 65 |  |
| A how-to guide: discrimination | 52 | 1 |
| A how-to guide: domestic-violence-help | 64 |  |
| A how-to guide: election-worker | 95 | 9 |
| A how-to guide: file-for-unemployment | 45 | 1 |
| A how-to guide: fishing-license | 58 |  |
| A how-to guide: food-and-health-assistance | 50 |  |
| A how-to guide: group | 12 |  |
| A how-to guide: health-insurance | 83 | 1 |
| A how-to guide: heating-and-electric-help | 57 |  |
| A how-to guide: help | 7 | 2 |
| A how-to guide: homelessness-help | 60 |  |
| A how-to guide: homeowners-insurance | 45 |  |
| A how-to guide: how-to-vote | 80 | 4 |
| A how-to guide: hunting-license | 61 |  |
| A how-to guide: landlord-duties | 57 |  |
| A how-to guide: medicare-and-social-security | 120 | 6 |
| A how-to guide: motorcycle-license | 61 |  |
| A how-to guide: new-to-new-hampshire | 45 |  |
| A how-to guide: passport | 75 |  |
| A how-to guide: property-tax-abatement | 63 |  |
| A how-to guide: property-tax-bill | 72 |  |
| A how-to guide: property-tax-relief | 51 |  |
| A how-to guide: public-records | 48 |  |
| A how-to guide: read-a-bill | 46 |  |
| A how-to guide: real-id | 40 |  |
| A how-to guide: register-a-car | 45 |  |
| A how-to guide: renew-drivers-license | 56 |  |
| A how-to guide: renters-insurance | 38 |  |
| A how-to guide: report-a-road-problem | 47 |  |
| A how-to guide: run-for-office | 65 | 1 |
| A how-to guide: said | 20 |  |
| A how-to guide: storms-and-emergencies | 64 |  |
| A how-to guide: submit-testimony | 39 |  |
| A how-to guide: task | 147 |  |
| A how-to guide: tenant-rights | 63 |  |
| A how-to guide: testifying | 76 |  |
| A how-to guide: tour-the-state-house | 44 |  |
| A how-to guide: town-warrant-article | 54 |  |
| A how-to guide: trash-and-recycling | 46 |  |
| A how-to guide: using-this-site | 45 |  |
| A how-to guide: vanity-and-special-plates | 97 | 2 |
| A how-to guide: vital-records | 52 |  |
| A how-to guide: wage-rights | 60 | 2 |
| A how-to guide: who-to-contact | 62 |  |
| A how-to guide: your-representatives | 27 |  |
| A Learn page: administrative-rules | 55 |  |
| A Learn page: all | 1 |  |
| A Learn page: all_pages | 1 |  |
| A Learn page: and | 1 |  |
| A Learn page: cacr | 31 |  |
| A Learn page: city-and-town-government | 94 |  |
| A Learn page: county-government | 73 |  |
| A Learn page: ends | 8 |  |
| A Learn page: general-court | 62 |  |
| A Learn page: governor-and-council | 42 |  |
| A Learn page: how-a-bill-becomes-law | 101 |  |
| A Learn page: lang_note | 1 |  |
| A Learn page: legislative-year | 14 |  |
| A Learn page: local-government | 43 |  |
| A Learn page: next | 1 |  |
| A Learn page: or | 1 |  |
| A Learn page: org_day | 1 |  |
| A Learn page: other | 1 |  |
| A Learn page: pages_label | 1 |  |
| A Learn page: prev | 1 |  |
| A Learn page: probate | 5 |  |
| A Learn page: rc | 5 |  |
| A Learn page: seats | 12 |  |
| A Learn page: state-agencies | 31 |  |
| A Learn page: state-house-and-branches | 66 |  |
| A Learn page: state-symbols | 205 |  |
| A Learn page: term | 19 |  |
| A Learn page: the-constitution | 29 |  |
| A Learn page: the-courts | 21 |  |
| A Learn page: the_house | 1 |  |
| A Learn page: the_senate | 1 |  |
| A Learn page: veto | 7 |  |
| An English page, to a reader who chose Spanish | 3 |  |
| Coming up (the week's meetings) | 59 | 1 |
| Coming up: a kind of meeting | 9 |  |
| Finding Your Representatives: the worked example | 26 |  |
| Live Now and the session pages: the day's votes | 36 | 36 |
| Live Now: which meetings are streaming | 14 | 14 |
| Settings | 10 |  |
| Settings: Your town | 78 |  |
| The box for reporting a mistake in the translation | 18 |  |
| The district map, on the Officials page's My Town tab | 80 | 2 |
| The footer | 14 |  |
| The Glossary page, and the pop-up on a term | 114 |  |
| The header | 8 |  |
| The home page | 16 |  |
| The home page's cards | 8 |  |
| The home page's Latest Activity: a committee's recommendation | 6 |  |
| The home page's Latest Activity: an interim study report | 4 |  |
| The home page's Latest Activity: what a sitting did with a bill | 46 |  |
| The home page's Recent Session Days: the floor sessions' players | 8 | 3 |
| The home page's status box | 11 |  |
| The home page's webinar box | 4 | 1 |
| The home page, under Coming up: a warning that the data is stale | 4 |  |
| The how-to guides, around the guide's own words | 44 | 2 |
| The Learn page on the legislative year | 188 |  |
| The members-elect: the Officials page's Members-Elect tab, and Your Town | 7 |  |
| The Officials page's Legislators tab: a party's name | 10 |  |
| The Officials page's Legislators tab: the House seating chart | 11 |  |
| The Officials page's Legislators tab: the line under the seating chart | 3 |  |
| The Officials page's Legislators tab: the roster | 21 | 1 |
| The Officials page's Legislators tab: who holds the seats | 11 |  |
| The Officials page's tabs: each office and who holds it | 122 |  |
| The Officials page: its title, its tabs' names and their headings | 20 |  |
| The Officials page: what Find Your Town finds, and the roster by county | 18 |  |
| The Resources page's Learn and Official Sources tabs | 93 |  |
| The search box | 2 |  |
| The search box's results | 42 |  |

## The branches' drafts, in full

Not yet in `dev`, so not in the proofreader's sheet. Each is in the CSV as well.

### `cohesion`: the cohesion batch, for 11 November (15)

| Place | Key | English | Spanish (draft) |
|---|---|---|---|
| A how-to guide: child-care-scholarship | `guide.child-care-scholarship.the-scholarship-is-paid-to-the` | The scholarship is paid to the provider, so the provider must be enrolled with the Department to accept it. Ask a provider you are considering whether it is. The Department&rsquo;s free Child Care Search, linked from the same page as the scholarship, shows providers&rsquo; quality ratings, licensing history and services, and Child Care Aware of New Hampshire helps families find care for free: call 1-855-393-1731, extension 2531, weekdays 8:00&nbsp;AM to 5:00&nbsp;PM. | La beca se paga al proveedor, así que el proveedor debe estar inscrito con el Departamento para aceptarla. Pregúntele a un proveedor que esté considerando si lo está. La búsqueda gratuita de cuidado infantil del Departamento (Child Care Search), enlazada desde la misma página que la beca, muestra la calificación de calidad, el historial de licencias y los servicios de cada proveedor, y Child Care Aware of New Hampshire ayuda gratis a las familias a encontrar cuidado: llame al 1-855-393-1731, extensión 2531, de lunes a viernes de 8:00&nbsp;a.&nbsp;m. a 5:00&nbsp;p.&nbsp;m. |
| A how-to guide: discrimination | `guide.discrimination.the-commission-also-takes-complaints-of` | The Commission also takes complaints of discrimination in K-12 public schools, and offers mediation. Submit a complaint from its website, or call (603) 271-2767, Monday through Friday, 8:00&nbsp;AM to 4:00&nbsp;PM; its office is at 57 Regional Drive, Suite 8, in Concord. | La Comisión también recibe quejas por discriminación en las escuelas públicas de K-12, y ofrece mediación. Presente una queja desde su sitio web, o llame al (603) 271-2767, de lunes a viernes, de 8:00&nbsp;a.&nbsp;m. a 4:00&nbsp;p.&nbsp;m.; su oficina está en 57 Regional Drive, Suite 8, en Concord. |
| A how-to guide: file-for-unemployment | `guide.file-for-unemployment.new-hampshire-employment-securitys` | New Hampshire Employment Security&rsquo;s unemployment hotline, (603) 271-7700, answers questions on weekdays from 8:00&nbsp;AM to 4:30&nbsp;PM. Its NH Works offices help in person, with claims and with finding work. | La línea de desempleo de New Hampshire Employment Security, (603) 271-7700, responde preguntas de lunes a viernes de 8:00&nbsp;a.&nbsp;m. a 4:30&nbsp;p.&nbsp;m. Sus oficinas NH Works ayudan en persona, con las solicitudes y con la búsqueda de trabajo. |
| A how-to guide: help | `guide.help.adrc.aging-and-disability-resource-centers` | <b>Aging and Disability Resource Centers</b> (formerly ServiceLink), a Department of Health and Human Services program with local resource centers: free counseling for older adults, adults with disabilities and caregivers, on benefits, applications, housing, Medicare and Medicaid, with no eligibility requirement. Call 1-866-634-9412, weekdays 8:30&nbsp;AM to 4:30&nbsp;PM. | <b>Aging and Disability Resource Centers</b> (centros de recursos para el envejecimiento y la discapacidad, antes ServiceLink), un programa del Departamento de Salud y Servicios Humanos con centros de recursos locales: orientación gratuita para adultos mayores, adultos con discapacidades y cuidadores, sobre beneficios, solicitudes, vivienda, Medicare y Medicaid, sin requisitos para recibirla. Llame al 1-866-634-9412, de lunes a viernes de 8:30&nbsp;a.&nbsp;m. a 4:30&nbsp;p.&nbsp;m. |
| A how-to guide: help | `guide.help.lawyer.the-new-hampshire-bar-associations` | <b>The New Hampshire Bar Association&rsquo;s Lawyer Referral Service</b> refers you to a lawyer who handles your kind of problem, for an administrative fee. Call 603-229-0002, weekdays 9:00&nbsp;AM to 3:30&nbsp;PM, or ask online. | <b>El servicio de referencia de abogados (Lawyer Referral Service) del Colegio de Abogados de New Hampshire</b> lo remite a un abogado que se ocupa de su tipo de problema, por una cuota administrativa. Llame al 603-229-0002, de lunes a viernes de 9:00&nbsp;a.&nbsp;m. a 3:30&nbsp;p.&nbsp;m., o consulte en línea. |
| A how-to guide: how-to-vote | `guide.how-to-vote.send-the-absentee-ballot-application-to` | Send the absentee ballot application to your town or city clerk, not the state, with the proof of identity the form asks for. The deadline to ask by mail is noon the day before the election, and to ask and vote in person at the clerk&rsquo;s office, 5:00&nbsp;PM the day before. A mailed ballot must reach your clerk by 5:00&nbsp;PM on election day, so ask for it more than two weeks ahead. | Envíe la solicitud de boleta de voto en ausencia al secretario de su municipio o ciudad, no al estado, con la prueba de identidad que pide el formulario. El plazo para pedirla por correo es el mediodía del día anterior a la elección, y para pedirla y votar en persona en la oficina del secretario, las 5:00&nbsp;p.&nbsp;m. del día anterior. Una boleta enviada por correo debe llegar a su secretario a más tardar a las 5:00&nbsp;p.&nbsp;m. del día de la elección, así que pídala con más de dos semanas de anticipación. |
| A how-to guide: medicare-and-social-security | `guide.medicare-and-social-security.apply-to-the-department-of-health` | Apply to the Department of Health and Human Services through NH Easy, under Medicare beneficiary assistance; its Customer Service Center answers at 1-844-ASK-DHHS (1-844-275-3447), Monday through Friday, 8:00&nbsp;AM to 4:00&nbsp;PM. Medicare advises applying even if you do not think you qualify. | Presente su solicitud al Departamento de Salud y Servicios Humanos a través de NH Easy, en la asistencia para beneficiarios de Medicare; su Centro de Servicio al Cliente atiende en el 1-844-ASK-DHHS (1-844-275-3447), de lunes a viernes, de 8:00&nbsp;a.&nbsp;m. a 4:00&nbsp;p.&nbsp;m. Medicare aconseja presentar la solicitud aunque crea que no reúne los requisitos. |
| A how-to guide: medicare-and-social-security | `guide.medicare-and-social-security.medicare-part-a-and-part-b` | Medicare Part A and Part B are signed up for through the Social Security Administration, not through Medicare. The easiest way is online, with a my Social Security account, if you are 65 or older. You can also call Social Security at 1-800-772-1213, Monday through Friday, 8:00&nbsp;AM to 7:00&nbsp;PM (TTY 1-800-325-0778), and make an appointment. | La inscripción en la Parte A y la Parte B de Medicare se hace a través de la Administración del Seguro Social, no a través de Medicare. La forma más fácil es en línea, con una cuenta my Social Security, si tiene 65 años o más. También puede llamar al Seguro Social al 1-800-772-1213, de lunes a viernes, de 8:00&nbsp;a.&nbsp;m. a 7:00&nbsp;p.&nbsp;m. (TTY 1-800-325-0778), y pedir una cita. |
| A how-to guide: run-for-office | `guide.run-for-office.to-run-in-a-partys-primary` | To run in a party&rsquo;s primary you must be a registered member of that party. File a declaration of candidacy, with a statement of financial interests, between the first Wednesday in June and the Friday of the following week. In 2026 that was June 3 to June 12. A filing on the last day must be made in person by the candidate, by 5:00&nbsp;PM. | Para postularse en las primarias de un partido debe ser miembro inscrito de ese partido. Presente una declaración de candidatura, con una declaración de intereses financieros, entre el primer miércoles de junio y el viernes de la semana siguiente. En 2026 fue del 3 al 12 de junio. Si se inscribe el último día, debe hacerlo el propio candidato en persona, a más tardar a las 5:00&nbsp;p.&nbsp;m. |
| A how-to guide: wage-rights | `guide.wage-rights.file-your-claim-online-with-the` | File your claim online with the Department&rsquo;s wage claim form. Its office answers at 603-271-3176, Monday through Friday, 8:00&nbsp;AM to 4:30&nbsp;PM; mail and hearings stay at 95 Pleasant Street, Spaulding Building, in Concord. | Presente su reclamo en línea con el formulario de reclamo de salario del Departamento. Su oficina atiende en el 603-271-3176, de lunes a viernes, de 8:00&nbsp;a.&nbsp;m. a 4:30&nbsp;p.&nbsp;m.; el correo y las audiencias siguen en 95 Pleasant Street, Spaulding Building, en Concord. |
| Coming up (the week's meetings) | `cal.coming` | Coming Up | Próximamente |
| The home page's Recent Session Days: the floor sessions' players | `sess.play` | Play the recording | Reproducir la grabación |
| The home page's Recent Session Days: the floor sessions' players | `sess.play_house` | Play the recording of the House floor session, {date} | Reproducir la grabación de la sesión plenaria de la Cámara, {date} |
| The home page's Recent Session Days: the floor sessions' players | `sess.play_senate` | Play the recording of the Senate floor session, {date} | Reproducir la grabación de la sesión plenaria del Senado, {date} |
| The home page's webinar box | `web.when` | Free webinar &middot; Tuesday, November 10, 6:30&nbsp;PM | Seminario web gratuito &middot; martes 10 de noviembre, 6:30&nbsp;p.&nbsp;m. |

### `guides`: the guides batch, held to 4 November (12)

| Place | Key | English | Spanish (draft) |
|---|---|---|---|
| A how-to guide: election-worker | `guide.election-worker.a-write-in-for-someone-whose` | A write-in for someone whose name is already printed on the ballot counts as a vote for that candidate, as long as the voter did not vote for too many people for that office. A voter who filled in the oval beside a candidate and also wrote the same name in gets one vote for that candidate, not two (<a href="/laws/659#s64-a">RSA 659:64-a</a>). | Un voto por escrito por alguien cuyo nombre ya está impreso en la boleta cuenta como un voto por ese candidato, siempre que el votante no haya votado por más personas de las permitidas para ese cargo. Un votante que llenó el óvalo junto a un candidato y además escribió el mismo nombre obtiene un voto para ese candidato, no dos (<a href="/laws/659#s64-a">RSA 659:64-a</a>). |
| A how-to guide: election-worker | `guide.election-worker.after-the-polls-close-the-votes-2` | <b>After the polls close.</b> The votes are counted in public and the count is not stopped until it is finished. If a ballot is marked for an office in a way that cannot readily be counted, or the officials counting disagree about it, they vote, and the ballot is counted for that office the way the majority decides. If no way of counting it gets a majority, that part of the ballot is not counted. The counting documents are open for public review when the results are announced, and a machine&rsquo;s printed results are posted within 60 minutes of the last ballot. The moderator announces the final count, and the clerk prepares the election return in front of the other officials, signs it, and sends a copy to the Secretary of State by 8:00 a.m. the next day. The other copy is kept by the clerk, open to the public. | <b>Después del cierre de la votación.</b> Los votos se cuentan en público y el conteo no se detiene hasta terminar. Si una boleta está marcada para un cargo de una forma que no se puede contar con facilidad, o los funcionarios que cuentan no están de acuerdo sobre ella, votan, y la boleta se cuenta para ese cargo como decida la mayoría. Si ninguna forma de contarla obtiene mayoría, esa parte de la boleta no se cuenta. Los documentos del conteo están disponibles para revisión pública cuando se anuncian los resultados, y los resultados impresos de una máquina se publican dentro de los 60 minutos de la última boleta. El moderador anuncia el conteo final, y el secretario prepara el acta de resultados frente a los demás funcionarios, la firma y envía una copia a la Secretaría de Estado antes de las 8:00 a.m. del día siguiente. El secretario guarda la otra copia, abierta al público. |
| A how-to guide: election-worker | `guide.election-worker.ballot-law-commission-rsa-665` | Ballot Law Commission, RSA 665 | Comisión de Leyes Electorales (Ballot Law Commission), RSA 665 |
| A how-to guide: election-worker | `guide.election-worker.can-a-ballot-with-an-unclear` | Can a ballot with an unclear mark, or a write-in, still count? | ¿Puede contar una boleta con una marca que no está clara, o con un voto por escrito? |
| A how-to guide: election-worker | `guide.election-worker.how-a-recount-runs-the-secretary` | <b>How a recount runs.</b> The Secretary of State publishes its recount procedures; those for state primaries describe it this way. Every recount is open to the public, and its time and place are posted on the Secretary of State&rsquo;s website. At least one team of two people counts each race. Across the table from them sits each candidate, or one person for the candidate, with other observers standing behind; cameras show every ballot and the tally sheet on screens facing the candidates, and do not record. Each box is opened in front of them and shown empty. The ballots are sorted into piles, in a race for one seat one for each candidate and piles for undervotes, overvotes and write-ins, and counted out loud in sets of 25, each set checked by the second counter. A candidate may challenge how any ballot is counted, without giving a reason; the Secretary of State rules on it, and a ballot still disputed is kept with a memo of the ruling in case of an appeal. The Secretary of State compares the recount with the election night results and declares the result. A candidate the recount declares did not win may appeal the Secretary of State&rsquo;s rulings on the protested ballots to the Ballot Law Commission, by a written appeal filed with the Secretary of State within 3 days of that declaration. The commission reviews those rulings and cannot order a second recount. | <b>Cómo se hace un recuento.</b> La Secretaría de Estado publica sus procedimientos de recuento; los de las primarias estatales lo describen así. Todo recuento está abierto al público, y su hora y lugar se publican en el sitio web de la Secretaría de Estado. Al menos un equipo de dos personas cuenta cada contienda. Al otro lado de la mesa se sienta cada candidato, o una persona en su nombre, y otros observadores se quedan de pie detrás; unas cámaras muestran cada boleta y la hoja de conteo en pantallas frente a los candidatos, y no graban. Cada caja se abre frente a ellos y se muestra vacía. Las boletas se separan en pilas, en una contienda por un solo puesto una por cada candidato y pilas para los votos en blanco (undervotes), los votos de más (overvotes) y los votos por escrito (write-ins), y se cuentan en voz alta en grupos de 25, cada grupo comprobado por el segundo contador. Un candidato puede impugnar cómo se cuenta cualquier boleta, sin dar una razón; la Secretaría de Estado decide, y una boleta que sigue en disputa se guarda con una nota de la decisión por si hay una apelación. La Secretaría de Estado compara el recuento con los resultados de la noche de la elección y declara el resultado. Un candidato que, según el recuento, no ganó puede apelar las decisiones de la Secretaría de Estado sobre las boletas impugnadas ante la Comisión de Leyes Electorales (Ballot Law Commission), con una apelación por escrito presentada ante la Secretaría de Estado dentro de los 3 días siguientes a esa declaración. La comisión revisa esas decisiones y no puede ordenar un segundo recuento. |
| A how-to guide: election-worker | `guide.election-worker.if-the-race-is-recounted-a` | If the race is recounted, a candidate may protest how any ballot is counted, and the Secretary of State rules on it (<a href="/laws/660#s5">RSA 660:5</a>). A candidate the recount declares did not win may appeal those rulings to the Ballot Law Commission, by a written appeal filed with the Secretary of State within 3 days of the declaration (<a href="/laws/665#s8">RSA 665:8</a>). After a primary recount, the commission&rsquo;s decision is final. After a general election recount, it can be appealed to the Supreme Court on questions of law only for presidential elector, governor, executive councilor, and town, city or ward offices. For state representative, state senator and Congress it cannot, because each house judges the elections of its own members (<a href="/laws/665#s16">RSA 665:16</a>). | Si la contienda se vuelve a contar, un candidato puede impugnar cómo se cuenta cualquier boleta, y la Secretaría de Estado decide (<a href="/laws/660#s5">RSA 660:5</a>). Un candidato que, según el recuento, no ganó puede apelar esas decisiones ante la Comisión de Leyes Electorales, con una apelación por escrito presentada ante la Secretaría de Estado dentro de los 3 días siguientes a la declaración (<a href="/laws/665#s8">RSA 665:8</a>). Después de un recuento de una primaria, la decisión de la comisión es definitiva. Después de un recuento de una elección general, puede apelarse ante la Corte Suprema en cuestiones de derecho solo para elector presidencial, gobernador, consejero ejecutivo y cargos de municipio, ciudad o distrito. Para representante estatal, senador estatal y el Congreso no se puede, porque cada cámara juzga las elecciones de sus propios miembros (<a href="/laws/665#s16">RSA 665:16</a>). |
| A how-to guide: election-worker | `guide.election-worker.it-can-the-laws-section-on` | It can. The law&rsquo;s section on unclear marks is headed &ldquo;Determining Intention of Voter&rdquo;. It says a ballot marked for an office in a way that cannot readily be counted is counted as a majority of the officials counting decide, and only if no way of counting it gets a majority is it left uncounted for that office (<a href="/laws/659#s64">RSA 659:64</a>). | Puede. La sección de la ley sobre las marcas que no están claras se titula &ldquo;Determinación de la intención del votante&rdquo; (Determining Intention of Voter). Dice que una boleta marcada para un cargo de una forma que no se puede contar con facilidad se cuenta como decida la mayoría de los funcionarios que cuentan, y solo si ninguna forma de contarla obtiene mayoría queda sin contar para ese cargo (<a href="/laws/659#s64">RSA 659:64</a>). |
| A how-to guide: election-worker | `guide.election-worker.on-election-night-the-election-officials` | On election night, the election officials counting the votes. If a ballot is marked for an office in a way that cannot readily be counted, or they disagree about it, they vote, and it is counted the way the majority decides. If no way of counting it gets a majority, that part of the ballot is not counted (<a href="/laws/659#s64">RSA 659:64</a>, <a href="/laws/659#s65">659:65</a>). | La noche de la elección, los funcionarios electorales que cuentan los votos. Si una boleta está marcada para un cargo de una forma que no se puede contar con facilidad, o no están de acuerdo sobre ella, votan, y se cuenta como decida la mayoría. Si ninguna forma de contarla obtiene mayoría, esa parte de la boleta no se cuenta (<a href="/laws/659#s64">RSA 659:64</a>, <a href="/laws/659#s65">659:65</a>). |
| A how-to guide: election-worker | `guide.election-worker.who-decides-how-to-count-a` | Who decides how to count a ballot whose mark is unclear? | ¿Quién decide cómo contar una boleta cuya marca no está clara? |
| A how-to guide: how-to-vote | `guide.how-to-vote.a-certified-copy-of-a-new` | A certified copy of a New Hampshire birth or other vital record is free when it is only for registering to vote: fill in the application for a free certified copy and file it, with proof of identity, with your town or city clerk. That copy can be used only to register to vote, and you must surrender it to the election official who takes your registration. For a record from another state, the Secretary of State points to the CDC&rsquo;s National Center for Health Statistics for how to get vital records from each state. | Una copia certificada de un acta de nacimiento u otro registro vital de New Hampshire es gratuita cuando es solo para inscribirse para votar: llene la solicitud de una copia certificada gratuita y preséntela, con prueba de identidad, ante el secretario de su municipio o ciudad. Esa copia solo puede usarse para inscribirse para votar, y debe entregarla al funcionario electoral que recibe su inscripción, quien se la queda. Para un registro de otro estado, la Secretaría de Estado remite al Centro Nacional de Estadísticas de Salud (National Center for Health Statistics) de los CDC para saber cómo obtener registros vitales de cada estado. |
| A how-to guide: how-to-vote | `guide.how-to-vote.ask-your-clerk-with-your-permission` | Ask your clerk: with your permission, local election officials may be able to check New Hampshire voter, motor vehicle and vital records to help prove your qualifications. Being registered now, or before, in any New Hampshire town or city proves your age and citizenship. For certain voters, vital records may help prove citizenship or a name change, and, for certain voters who have obtained a New Hampshire driver&rsquo;s license or non-driver ID, motor vehicle records may help prove citizenship, age, domicile or a name change. | Pregúntele a su secretario: con su permiso, los funcionarios electorales locales quizá puedan consultar los registros de votantes, de vehículos motorizados y vitales de New Hampshire para ayudarle a probar que reúne los requisitos. Estar inscrito ahora, o haberlo estado antes, en cualquier municipio o ciudad de New Hampshire prueba su edad y su ciudadanía. Para ciertos votantes, los registros vitales pueden ayudar a probar la ciudadanía o un cambio de nombre y, para ciertos votantes que hayan obtenido una licencia de conducir o una identificación de no conductor de New Hampshire, los registros de vehículos motorizados pueden ayudar a probar la ciudadanía, la edad, el domicilio o un cambio de nombre. |
| A how-to guide: how-to-vote | `guide.how-to-vote.this-changed-in-2026-and-the` | <b>This changed in 2026, and the courts are still involved.</b> What you may use as proof has changed more than once this year and may change again before the election. The Secretary of State's page is the official word: check it before you go. On October 24, 2026 it still said that if you lack the documents to prove your citizenship, you may sign a qualified voter affidavit instead, subject to the penalties for voter fraud. A court order of May 28, 2026 allowed this again. The affidavit covers citizenship and nothing else: you still need proof of identity, age and domicile. | <b>Esto cambió en 2026, y los tribunales siguen interviniendo.</b> Lo que puede usar como prueba ha cambiado más de una vez este año y puede volver a cambiar antes de la elección. La página de la Secretaría de Estado es la fuente oficial: consúltela antes de ir. El 24 de octubre de 2026 seguía diciendo que, si le faltan los documentos para probar su ciudadanía, puede firmar en su lugar una declaración jurada de votante calificado (qualified voter affidavit), sujeta a las sanciones por fraude electoral. Una orden judicial del 28 de mayo de 2026 volvió a permitirlo. La declaración jurada cubre la ciudadanía y nada más: sigue necesitando pruebas de identidad, edad y domicilio. |

### `live/session`: the live layer (live/page and live/session), from about 3 November (65)

| Place | Key | English | Spanish (draft) |
|---|---|---|---|
| A how-to guide: car-insurance | `guide.car-insurance.the-financial-responsibility-law-decides` | The <b>financial responsibility law</b> decides when the state requires proof that you can pay for damage you cause: after a crash you had to report and had no insurance for, or after certain convictions (steps 2 and 3). | La <b>ley de responsabilidad financiera</b> (financial responsibility law) decide cuándo el estado exige una prueba de que usted puede pagar los daños que cause: después de un choque que tuvo que reportar y para el que no tenía seguro, o después de ciertas condenas (pasos 2 y 3). |
| A how-to guide: consumer-rights | `guide.consumer-rights.if-a-seller-tells-you-that` | If a seller tells you that you have won something, with words such as &ldquo;Congratulations&rdquo; or &ldquo;You have won&rdquo;, the law requires the prize to be yours without any obligation, delivered at no cost to you within 10 days. A &ldquo;prize&rdquo; that asks you to pay a handling, registration, redemption or delivery fee, or to buy something first, is not one the law allows. Do not pay, and report it (step 5). | Si un vendedor le dice que ganó algo, con palabras como &ldquo;Felicidades&rdquo; o &ldquo;Usted ganó&rdquo;, la ley exige que el premio sea suyo sin ninguna obligación, entregado sin costo para usted dentro de los 10 días. Un &ldquo;premio&rdquo; que le pide pagar una cuota de manejo, de inscripción, de canje o de envío, o comprar algo primero, no es uno que la ley permita. No pague, y denúncielo (paso 5). |
| A how-to guide: health-insurance | `guide.health-insurance.medicaid-or-medicare-may-cover-you` | Medicaid or Medicare may cover you (step 8). | Medicaid o Medicare pueden cubrirle (paso 8). |
| A how-to guide: medicare-and-social-security | `guide.medicare-and-social-security.help-with-the-costs-comes-from` | <b>Help with the costs</b> comes from two programs: the state&rsquo;s <b>Medicare Savings Programs</b>, which help pay Medicare premiums and, for some people, other costs; and the federal <b>Extra Help</b> program, which pays part of the cost of drug coverage. Step 6 says who qualifies and how to apply. | <b>La ayuda con los costos</b> viene de dos programas: los <b>Programas de Ahorros de Medicare</b> del estado, que ayudan a pagar las primas de Medicare y, para algunas personas, otros costos; y el programa federal de <b>Ayuda Adicional</b>, que paga parte del costo de la cobertura de medicamentos. El paso 6 dice quién reúne los requisitos y cómo solicitarlos. |
| A how-to guide: medicare-and-social-security | `guide.medicare-and-social-security.through-social-security-many-people-are` | Through Social Security. Many people are enrolled automatically (step 2). | A través del Seguro Social. Muchas personas quedan inscritas automáticamente (paso 2). |
| A how-to guide: medicare-and-social-security | `guide.medicare-and-social-security.you-add-a-drug-plan-to` | You add a drug plan to Original Medicare, or get it in a Medicare Advantage Plan with drug coverage, on Medicare.gov (step 5). | Agrega un plan de medicamentos a Medicare Original, o lo obtiene en un Plan Medicare Advantage con cobertura de medicamentos, en Medicare.gov (paso 5). |
| A how-to guide: medicare-and-social-security | `guide.medicare-and-social-security.you-choose-one-on-medicare-gov` | You choose one on Medicare.gov (step 5). | Se elige en Medicare.gov (paso 5). |
| A how-to guide: vanity-and-special-plates | `guide.vanity-and-special-plates.a-special-plate-show-that-you` | A special plate: show that you qualify | Una placa especial: demuestre que reúne los requisitos |
| A how-to guide: vanity-and-special-plates | `guide.vanity-and-special-plates.for-a-special-plate-find-yours` | For a special plate, find yours in the table in step 4: who may have it and what it costs. | Para una placa especial, búsquela en la tabla del paso 4: quién puede tenerla y cuánto cuesta. |
| A how-to guide: wage-rights | `guide.wage-rights.if-you-were-not-paid-file` | If you were not paid: file a wage claim | Si no le pagaron: presente un reclamo de salarios |
| Live Now and the session pages: the day's votes | `votes.budget` | Live votes reached today's limit on queries and stop until tomorrow. | Las votaciones en vivo alcanzaron el límite de consultas de hoy y se detienen hasta mañana. |
| Live Now and the session pages: the day's votes | `votes.connect` | Votes last read at {time}; the General Court's database could not be reached since. | Votaciones leídas por última vez a las {time}; desde entonces no se ha podido acceder a la base de datos de la Legislatura. |
| Live Now and the session pages: the day's votes | `votes.dated` | The day's page: | La página del día: |
| Live Now and the session pages: the day's votes | `votes.day_over` | Reading stopped for the day at {time}. | La lectura se detuvo por hoy a las {time}. |
| Live Now and the session pages: the day's votes | `votes.encrypt` | Live votes are off: the database asks for an encrypted connection this site's reader cannot make. | Las votaciones en vivo están desactivadas: la base de datos exige una conexión cifrada que el lector de este sitio no puede establecer. |
| Live Now and the session pages: the day's votes | `votes.ends` | Every vote reaches this page with tomorrow morning's record. | Cada votación llega a esta página con el registro de mañana por la mañana. |
| Live Now and the session pages: the day's votes | `votes.ends_morning` | Every vote reaches this page with this morning's record. | Cada votación llega a esta página con el registro de esta mañana. |
| Live Now and the session pages: the day's votes | `votes.head_house` | House roll calls today | Votaciones nominales de la Cámara hoy |
| Live Now and the session pages: the day's votes | `votes.head_house_day` | House roll calls of {day} | Votaciones nominales de la Cámara del {day} |
| Live Now and the session pages: the day's votes | `votes.head_senate` | Senate roll calls today | Votaciones nominales del Senado hoy |
| Live Now and the session pages: the day's votes | `votes.head_senate_day` | Senate roll calls of {day} | Votaciones nominales del Senado del {day} |
| Live Now and the session pages: the day's votes | `votes.in_record` | The night's record holds {day}'s roll calls. | El registro de la noche contiene las votaciones nominales del {day}. |
| Live Now and the session pages: the day's votes | `votes.login` | Votes last read at {time}; the database has refused the published login since. | Votaciones leídas por última vez a las {time}; desde entonces la base de datos ha rechazado el acceso publicado. |
| Live Now and the session pages: the day's votes | `votes.names_follow` | names follow | los nombres llegarán después |
| Live Now and the session pages: the day's votes | `votes.names_in` | names: in | nombres: completos |
| Live Now and the session pages: the day's votes | `votes.no_outcome` | outcome not yet in the docket | resultado aún no anotado en el registro de trámites |
| Live Now and the session pages: the day's votes | `votes.none_day` | No roll calls read on {day}. | No se leyeron votaciones nominales el {day}. |
| Live Now and the session pages: the day's votes | `votes.none_today` | No roll calls read today. | Hoy no se ha leído ninguna votación nominal. |
| Live Now and the session pages: the day's votes | `votes.none_yet` | No roll calls read yet today (read at {time}). | Aún no se ha leído ninguna votación nominal hoy (leído a las {time}). |
| Live Now and the session pages: the day's votes | `votes.not_read` | Not read since {time}. | Sin leer desde las {time}. |
| Live Now and the session pages: the day's votes | `votes.off` | Live votes were turned off by this site at {time}. | Este sitio desactivó las votaciones en vivo a las {time}. |
| Live Now and the session pages: the day's votes | `votes.outcome` | {outcome}, clerk's docket | {outcome}, según el registro de trámites |
| Live Now and the session pages: the day's votes | `votes.overlay_head` | Read during the day | Leído durante el día |
| Live Now and the session pages: the day's votes | `votes.overlay_why` | These roll calls were read from the General Court's database and are not in the night's record yet. The record replaces them. | Estas votaciones nominales se leyeron de la base de datos de la Legislatura y aún no están en el registro de la noche. El registro las reemplaza. |
| Live Now and the session pages: the day's votes | `votes.provisional` | provisional | provisional |
| Live Now and the session pages: the day's votes | `votes.provisional_at` | provisional · read at {time} | provisional · leído a las {time} |
| Live Now and the session pages: the day's votes | `votes.provisional_line` | Provisional: the night's record replaces this tomorrow morning; excusals settle days later. | Provisional: el registro de la noche lo reemplaza mañana por la mañana; las excusas se resuelven días después. |
| Live Now and the session pages: the day's votes | `votes.query` | Votes last read at {time}; a query has failed since. | Votaciones leídas por última vez a las {time}; desde entonces ha fallado una consulta. |
| Live Now and the session pages: the day's votes | `votes.read` | Read from the General Court's database at {time}. | Leído de la base de datos de la Legislatura a las {time}. |
| Live Now and the session pages: the day's votes | `votes.saved_at` | saved at {time} | guardada a las {time} |
| Live Now and the session pages: the day's votes | `votes.senate_after` | The Senate enters its roll calls after it rises. | El Senado anota sus votaciones nominales después de levantar la sesión. |
| Live Now and the session pages: the day's votes | `votes.senate_line` | Senate names follow once the Senate enters them, usually that afternoon or the next day. | Los nombres del Senado se añaden cuando el Senado los registra, normalmente esa tarde o al día siguiente. |
| Live Now and the session pages: the day's votes | `votes.today_day` | Roll calls of {day}, as read during the day | Votaciones nominales del {day}, según se leyeron durante el día |
| Live Now and the session pages: the day's votes | `votes.today_house` | The House today | La Cámara hoy |
| Live Now and the session pages: the day's votes | `votes.today_senate` | The Senate today | El Senado hoy |
| Live Now and the session pages: the day's votes | `votes.unfetched` | The live votes could not be fetched at {time}; this page asks again. | No se pudieron obtener las votaciones en vivo a las {time}; esta página volverá a intentarlo. |
| Live Now: which meetings are streaming | `live.at` | scheduled for {time} | programada para las {time} |
| Live Now: which meetings are streaming | `live.cal_h` | On today's calendar | En el calendario de hoy |
| Live Now: which meetings are streaming | `live.checked` | Checked {time} | Comprobado a las {time} |
| Live Now: which meetings are streaming | `live.no_stream_house` | No House session stream found right now (checked {time}) | No se encontró ninguna transmisión de la sesión de la Cámara en este momento (consultado a las {time}) |
| Live Now: which meetings are streaming | `live.no_stream_senate` | No Senate session stream found right now (checked {time}) | No se encontró ninguna transmisión de la sesión del Senado en este momento (consultado a las {time}) |
| Live Now: which meetings are streaming | `live.none_found` | No stream found right now (checked {time}) | No se encontró ninguna transmisión en este momento (comprobado a las {time}) |
| Live Now: which meetings are streaming | `live.nostream_h` | On today's calendar, no stream found (checked {time}) | En el calendario de hoy, sin transmisión encontrada (comprobado a las {time}) |
| Live Now: which meetings are streaming | `live.off` | Live status is turned off | La comprobación en vivo está desactivada |
| Live Now: which meetings are streaming | `live.on_youtube` | On YouTube | En YouTube |
| Live Now: which meetings are streaming | `live.play` | Play the live stream | Reproducir la transmisión en vivo |
| Live Now: which meetings are streaming | `live.since` | Live since {time} | En vivo desde las {time} |
| Live Now: which meetings are streaming | `live.stale` | Live status has not been checked since {time} | El estado en vivo no se ha comprobado desde las {time} |
| Live Now: which meetings are streaming | `live.stale_never` | Live status has not been checked yet today | El estado en vivo aún no se ha comprobado hoy |
| Live Now: which meetings are streaming | `live.unavailable` | Live status is not available | El estado en vivo no está disponible |
| The district map, on the Officials page's My Town tab | `map.fit` | Fit | Ajustar |
| The district map, on the Officials page's My Town tab | `map.fit_all` | Fit the whole map | Ver todo el mapa |
| The how-to guides, around the guide's own words | `guides.rec_none` | No bill has changed it since {year}, and none now before the General Court would. | Ningún proyecto de ley la ha cambiado desde {year}, y ninguno de los que están ahora ante la Legislatura la cambiaría. |
| The how-to guides, around the guide's own words | `guides.rec_since` | Laws that changed it since {year}, newest first: | Leyes que la cambiaron desde {year}, de la más reciente a la más antigua: |
| The Officials page's Legislators tab: the roster | `roster.fit` | Fit | Ajustar |
