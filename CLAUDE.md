# fp-stats

Tracks Floatplane subscriber counts and serves charts at **fp-stats.com**. Focus is on LTT — nobody else has this long-term history, and the annotated event timeline (controversies, the channel hack) is what makes it interesting.

**Launch strategy:** build it quietly and share publicly when the next LTT controversy happens. The site must be correct, up to date, and able to survive a Reddit spike on a day nobody can predict.

Owner: Lorenz. Written with Claude Code. Explain changes in plain terms; say clearly when something affects the live server.

---

## Data

Tracked creators are in `creators.csv`: name, Floatplane ID, skip flag. A `True` skip flag means don't scrape.

When a creator leaves Floatplane, set the skip flag to stop scraping them; their history stays on the site.

On the dev machine (vega) relatively up to date data is found in /home/lorenz/fp-stats/configdata

---

## Infrastructure

**saturn**: netcup vRoot, Nürnberg, Ubuntu 24.04, 4 GB RAM, 128 GB disk. Runs Docker Compose and SWAG (nginx + Let's Encrypt). Replaced the old server `mars` in September 2026.

- Domain: `fp-stats.com` (target). `fp-stats.buzz` was briefly used in 2023 with a cobbled together quick solution for a reddit post. `fp-stats.buzz` has expired — don't use it.
- DNS points at saturn.
- SWAG is serving fp-stats.com through `EXTRA_DOMAINS=fp-stats.com, www.fp-stats.com` .
- Container timezone: `UTC`.

**saturn never has the source code — this is on purpose.** Lorenz wants to keep code handling simple. Only the dev machine (vega) holds the source. Saturn pulls the prebuilt image and runs it; it never builds. The image is built and pushed to Docker Hub (by CI, on push to `main`), and saturn's compose pulls that image.

---

## Target architecture

One container that does everything on a schedule:
1. Scrape all active creators hourly
2. Append new values to per-creator data files.
3. Render static SVG charts.
4. Write plain static HTML into the output folder.
5. SWAG serves the output folder as fp-stats.com.

If the container dies, the site keeps showing the last good version.

Expect it to run for months on end with little or no maintenance.

### Site structure
- **Front page**: LTT story. key numbers (current count, peak, 30-day change), short explanation.
- **Creators page**: links to a simple page per creator.
- **Link to blog entry**: for methodology and other more off topic stuff. I run my personal site with a blog on www.lorenz.kiwi
---

## Rules

- **Store timestamps in UTC.** Old local-time data stays as-is; new data is UTC. Convert for display only.
- **No credentials of any kind on saturn.** The Floatplane API is public; no auth needed. If the server is compromised, the attacker finds nothing but public subscriber counts.
- **Static output only.** No database, no app server, no user accounts.
- **No JavaScript frameworks.** Little or no JS at all.
- **Few dependencies, pinned versions.** Anything needing regular updates is a maintenance cost.
- **Keep the `source` column** so every data point stays traceable to its origin.
- **Downsampling is for display only.** Full-resolution data is always stored.

---

## Backups

Manual. Lorenz copies data to Google Drive roughly every two months (phone reminder). Losing a few weeks or even 2 months of data is acceptable. No automated backup in the container; nothing on saturn may hold credentials for a remote backup target. 

---

## Alerts

Lorenz already uses VisualPing to watch his sites. Maybe add some super simple JS code so when the last update was over 1 day ago a big red banner (or any big visual change) shows up. VisualPing then picks up on this and takes care of alerting Lorenz.

---

## Roadmap

**MVP:** fp-stats.com shows the LTT chart and updates by itself. Scraper → SVG chart → HTML page → single container → deployed on saturn alongside old containers.

**Before public launch:** pages for all creators, methodology page, recent-view charts, og:image previews, **alerts when data stops arriving** (silent failure is the biggest real risk).

**Later:** CDN for traffic spike protection, easier annotation workflow (ideally phone-friendly), creator comparison views.

---

## How to work here

- Plan before larger changes; check the plan against the rules above.
- Work in small steps. Commit after each working step.
- **Commit atomically** — one logical change per commit.
- **Use gitmoji for commit messages**, following the conventions in `gitmoji.md`.
- **Never add Claude or Claude Code as author or co-author.** No `Co-Authored-By` trailers; commits are authored by Lorenz alone.
- Ask when something is genuinely ambiguous — especially anything involving data.
- Update this file when a decision changes.
