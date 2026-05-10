# URL Corpus Quality Assessment — Part 1 (Entry-Level)

**Scope:** initial sweep of `~/Desktop/Charles URLS/` — entry-level / well-known
operator + dev blogs. Each entry rated by signal density and durability.

**Rating legend:**
- **KEEP** — substantive, durable, worth deep reading and re-reading
- **SKIM** — partial value; mine for specific items, don't read end-to-end
- **SKIP** — dead, low-signal, or product-marketing fluff

---

## KEEP — high signal

| # | Source | Owner | One-liner | Key topics |
|---|---|---|---|---|
| 1 | swyx.io/writing | Shawn Wang | 627 essays on dev strategy + "Learn in Public" | JS ecosystems, Svelte, DX, dev→founder mindset |
| 2 | sahillavingia.com/work | Sahil Lavingia (Gumroad) | "No Meetings, No Deadlines, No Full-Time Employees" | creator-economy biz model, contractor ops, profit sharing |
| 3 | world.hey.com/jason | Jason Fried (37signals/HEY) | ~50 essays — reject complexity, reject bloat | product philosophy, hiring, "go do business" |
| 4 | kalzumeus.com/archive | Patrick McKenzie (ex-Stripe) | ~200 posts 2008–2025 — THE SaaS gold mine | A/B testing, pricing, conversion, "5 hours a week" |
| 5 | danluu.com | Dan Luu | ~150 essays, deep technical | systems, latency, CPUs, debugging, "files are hard" |
| 6 | scattered-thoughts.net | Jamie Brandon | databases, SQL criticism, streaming, PL design | Droplet/Eve/Imp, WASM, Zig/Rust, distributed systems |
| 7 | julian.com | Julian Shapiro | handbooks: writing, fundraising, growth | grew Webflow, built Velocity animation engine |
| 8 | commoncog.com/blog | Cedric Chin | Calibration Case Method | competitive strategy ("7 Powers"), capital allocation |
| 9 | patio11.substack.com | Patrick McKenzie | Bits about Money newsletter | finance/tech crossover (redirect from kalzumeus) |
| 10 | patrickcollison.com | Patrick Collison (Stripe CEO) | essays on progress, technology, SV history | civilizational scope, durable references |

---

## SKIM — partial value

| Source | Why SKIM not KEEP |
|---|---|
| failory.com/cemetery | Decent startup-failure post-mortems, but oriented toward what NOT to do; low signal for learning how to succeed. Mine for cause-of-death patterns only. |

---

## SKIP — dead, generic, or product-marketing

| Source | Reason |
|---|---|
| indiehackers.com/start | Community feed, no substantive content |
| indiehackers.com/post/... | Post-listing page, not articles |
| levels.io | Product page, not content |
| nomadlist.com/about | Travel destination site, not business/coding |
| startupclass.samaltman.com | Dead domain (ERR_NAME_NOT_RESOLVED) |
| starterstory.com/ideas | Idea listing page, not articles |
| starterstory.com/business-ideas | Alphabet-soup category list |
| failory.com/blog | Connection closed (dead) |
| justinwelsh.me/articles | Solopreneur marketing fluff ("how to get 430K LinkedIn followers") |
| signalvnoise.com | "Signal v. Noise is closed" (redirects to individual blogs) |
| gabriel-weinberg.com | Dead domain (ERR_NAME_NOT_RESOLVED) |
| biteable.com/blog | Video-maker product page, not content |
| semrush.com/blog | Marketing-tool blog, generic SEO content |
| usemax.ai/blog | 404 |

---

## Key learnings extracted from KEEP tier

### Patrick McKenzie (kalzumeus.com)
- A/B testing is the most important skill for SaaS founders
- Pricing matters more than product at early stage
- "Running a software business in 5 hours a week" — micro-SaaS is real
- Conversion optimization via landing-page redesign (not marketing)
- A/Bingo: open-source split testing for Rails
- "Doubling SaaS Revenue By Changing The Pricing Model"
- "You Should Probably Send More Email Than You Do" — outbound marketing
- "Strategic SEO for Startups"
- "How To Successfully Compete With Open Source Software"

### Dan Luu (danluu.com)
- "Files are hard" — file I/O is more complex than you think
- "Against essential and accidental complexity"
- "Algorithms interviews: theory vs. practice"
- "Data alignment and caches" — low-level perf
- "Testing v. informal reasoning"
- "Given that we spend little on testing, how should we test software?"
- "A defense of boring languages" — boring beats trendy
- "Advantages of monorepos"

### Jamie Brandon (scattered-thoughts.net)
- "Against SQL" — SQL is inexpressive and under-specified
- "Internal consistency" — streaming systems can produce unboundedly wrong outputs
- "The shape of data" — take notation seriously
- "Dida" — differential dataflow for mortals
- "Query optimization works because SQL is declarative"

### Jason Fried (world.hey.com/jason)
- Reject complexity — reject bloat in products and processes
- "Go do business" — you learn by doing, not consuming content
- Reject "years of experience" requirement; prefer "years of evidence" (work samples)
- Cover letters required for hiring at Basecamp
- "A beta is like inviting guests over" — only beta at v0.99

---

## Triage stats

- KEEP: 10
- SKIM: 1
- SKIP: 14
- **Total assessed:** 25

Next: Part 2 (Intermediate / specialist) — see `url_assessment_part2_entry.md`
when generated.
