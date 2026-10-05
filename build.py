#!/usr/bin/env python3
"""Build the fact-check site into docs/.

usage: python3 build.py [--transcripts DIR]

  reads   reports/<series>/s01eNN - <Title>.md     (one fact-check report per episode)
          transcripts/<series>/s01eNN.srt          (Whisper subtitles, to time-stamp quotes; or --transcripts DIR)
  writes  data/timestamps.json                     (quote -> time, so the site rebuilds without transcripts)
          docs/index.html, docs/<series>.html
"""
import html, json, re, sys
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TX = Path(sys.argv[sys.argv.index("--transcripts") + 1]) if "--transcripts" in sys.argv else ROOT / "transcripts"
STAMPS = ROOT / "data" / "timestamps.json"
DOCS = ROOT / "docs"

SERIES = [  # key, title, first aired, checked against, missing episodes
    ("man", "Once Upon a Time... Man", "1978", "history and archaeology", ""),
    ("space", "Once Upon a Time... Space", "1982", "astronomy and science", ""),
    ("life", "Once Upon a Time... Life", "1987", "medicine and biology", ""),
    ("americas", "Once Upon a Time... The Americas", "1991", "the history of the Americas",
     "Episode 14 (Samuel de Champlain) could not be found online and is not covered."),
    ("discoverers", "Once Upon a Time... The Discoverers", "1994", "the history of science",
     "Episode 17 (Louis Pasteur) could not be found in English or French and is not covered."),
    ("explorers", "Once Upon a Time... The Explorers", "1996", "the history of exploration",
     "Episodes 23 (Alexandra David-Néel) and 24 (Auguste Piccard) could not be found in English or French and are not covered."),
]
KINDS = ("outdated", "common", "wrong")
LABEL = {"outdated": "Outdated", "common": "Common belief then", "wrong": "Wrong in its day"}


def norm(s):
    return re.sub(r"[^a-z0-9' ]+", " ", s.lower()).split()


def load_srt(path):
    """-> list of (seconds, word) for every word in the subtitle file."""
    words = []
    if not path.exists():
        return words
    for block in path.read_text(errors="ignore").split("\n\n"):
        lines = block.strip().splitlines()
        if len(lines) < 3 or "-->" not in lines[1]:
            continue
        h, m, s = lines[1].split(" --> ")[0].replace(",", ".").split(":")
        t = int(h) * 3600 + int(m) * 60 + float(s)
        words += [(t, w) for w in norm(" ".join(lines[2:]))]
    return words


def find_time(words, quote):
    """Best fuzzy window match of the quote in the transcript; None if weak."""
    q = norm(re.sub(r"\(.*?\)|\[.*?\]", " ", quote))
    if len(q) < 2 or not words:
        return None
    toks = [w for _, w in words]
    n, best, best_i = len(q), 0.0, None
    for i in range(0, max(1, len(toks) - n + 1)):
        win = toks[i:i + n]
        if q[0] not in win and q[-1] not in win:
            continue
        r = SequenceMatcher(None, q, win).ratio()
        if r > best:
            best, best_i = r, i
    return words[best_i][0] if best_i is not None and best >= 0.55 else None


def fmt_t(t):
    return f"{int(t // 60)}:{int(t % 60):02d}"


def inline(s):
    s = html.escape(s.strip())
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    return re.sub(r"\*(.+?)\*", r"<em>\1</em>", s)


def parse(md):
    title = re.search(r"^# .*?s01e(\d+):\s*(.+)$", md, re.M)
    parts = re.split(r"^## (.+)$", md, flags=re.M)
    summary = parts[0].split("\n", 1)[1].strip() if "\n" in parts[0] else ""
    secs = {}
    for name, body in zip(parts[1::2], parts[2::2]):
        k = ("outdated" if "outdated" in name.lower() else
             "common" if "common belief" in name.lower() else
             "wrong" if "wrong" in name.lower() else "fine")
        if k == "fine":
            secs[k] = [b[2:].strip() for b in re.split(r"\n(?=- )", body.strip())
                       if b.startswith("- ")]
            continue
        items = []
        for b in re.split(r"\n\s*\n(?=- )|\n(?=- \*\*Quote)", body.strip()):
            q = re.search(r"\*\*Quote:\*\*\s*(.+?)(?=\n\s*\*\*|\Z)", b, re.S)
            if not q:
                continue
            today = re.search(r"\*\*(?:Correct today|Today)[^*]*:\*\*\s*(.+?)(?=\n\s*\*\*(?:Conf|Why)|\Z)", b, re.S)
            why = re.search(r"\*\*Why it was believed:\*\*\s*(.+?)(?=\n\s*\*\*|\Z)", b, re.S)
            conf = re.search(r"\*\*Confidence:\*\*\s*(.+)", b)
            items.append(dict(quote=" ".join(q.group(1).split()),
                              today=" ".join(today.group(1).split()) if today else "",
                              why=" ".join(why.group(1).split()) if why else "",
                              conf=(conf.group(1).strip() if conf else "").lower()))
        secs[k] = items
    return int(title.group(1)), title.group(2).strip(), summary, secs


HEAD = '''<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fredoka:wght@500;600&family=Figtree:ital,wght@0,400;0,600;0,700;1,400&display=swap">
<link rel="stylesheet" href="style.css">
'''


def series_page(key, series, years, topic, missing, eps, stamps):
    n = {k: sum(len(e[k]) for e in eps) for k in KINDS}
    n_clean = sum(1 for e in eps if not any(e[k] for k in KINDS))

    def claim(it, kind, ep):
        t = it["t"]
        when = (f'<span class="ts" title="Time in the episode">{t}</span>' if t
                else '<span class="ts none" title="Could not locate the exact moment">—:—</span>')
        conf = it["conf"].split()[0].strip(".,()") if it["conf"] else ""
        return f'''<li class="claim {kind}">
  <div class="claim-meta"><span class="tag">{LABEL[kind]}</span><span class="where">E{ep:02d} · {when}</span>{f'<span class="conf">{html.escape(conf)} confidence</span>' if conf else ''}</div>
  <blockquote>{inline(it["quote"])}</blockquote>
  <p class="today"><span class="lbl">Today</span>{inline(it["today"])}</p>
  {f'<p class="why"><span class="lbl">Why it was believed</span>{inline(it["why"])}</p>' if it.get("why") else ''}
</li>'''

    def tkey(i):
        return tuple(int(x) for x in i["t"].split(":")) if i["t"] else (999, 0)

    body = []
    for e in eps:
        pairs = sorted([(i, k) for k in KINDS for i in e[k]], key=lambda p: tkey(p[0]))
        claims = [claim(i, k, e["n"]) for i, k in pairs]
        c = len(claims)
        fine = "".join(f"<li>{inline(x)}</li>" for x in e["fine"])
        body.append(f'''<section class="ep" id="e{e["n"]:02d}">
  <header class="ep-head"><span class="ep-no">Episode {e["n"]}</span><h2>{html.escape(e["title"])}</h2>
  <span class="ep-count {'zero' if not c else ''}">{c or 'No'} issue{'s' if c != 1 else ''}</span></header>
  <p class="summary">{inline(e["summary"])}</p>
  {f'<ol class="claims">{"".join(claims)}</ol>' if claims else '<p class="clean">Nothing outdated or wrong was found in this episode.</p>'}
  {f'<details class="fine"><summary>Simplified but fine ({len(e["fine"])})</summary><ul>{fine}</ul></details>' if fine else ''}
</section>''')
    index = "".join(
        f'<a href="#e{e["n"]:02d}" class="{"has" if any(e[k] for k in KINDS) else ""}"><b>{e["n"]}</b>{html.escape(e["title"])}'
        f'<i>{sum(len(e[k]) for k in KINDS) or ""}</i></a>' for e in eps)
    return HEAD.format(title=f"{html.escape(series)} Fact Check",
                       desc=f"Episode-by-episode fact check of {html.escape(series)} ({years}).") + f'''<body>
<div class="wrap">
  <a class="back" href="./">← All six series</a>
  <p class="kicker">Fact check · first aired {years}</p>
  <h1>{html.escape(series)}</h1>
  <p class="lede">Every episode transcribed and checked against what we know today about {html.escape(topic)}. Each point shows the episode, the moment it is said, and the exact line from the English dub (or the original French, where no English upload exists).</p>
  <p class="key watch">Watch the episodes on the official <a href="https://www.youtube.com/@onceuponatimechannel">Hello Maestro YouTube channel</a>.</p>
  <div class="tally"><span class="o"><b>{n["outdated"]}</b>outdated by later research</span><span class="c"><b>{n["common"]}</b>common beliefs of the time</span><span class="w"><b>{n["wrong"]}</b>wrong even when it aired</span><span><b>{n_clean}</b>episodes with nothing to flag</span></div>
  <p class="key"><strong>Outdated</strong>: matched what was known at the time, but newer research changed the picture. <strong>Common belief then</strong>: specialists already knew better, but textbooks and popular books of the day still said it. <strong>Wrong in its day</strong>: a careful writer could have got it right from ordinary references; often a slip in a number, a name or the dubbing. Plain simplifications for children are not counted; they are listed under each episode. <a href="./#method">How this was made</a>.</p>
  {f'<p class="key missing">{html.escape(missing)}</p>' if missing else ''}
  <div class="filters" role="group" aria-label="Show">
    <button type="button" data-f="all" aria-pressed="true">All points</button>
    <button type="button" data-f="outdated" aria-pressed="false">Outdated only</button>
    <button type="button" data-f="common" aria-pressed="false">Common belief only</button>
    <button type="button" data-f="wrong" aria-pressed="false">Wrong in its day only</button>
  </div>
  <nav class="index" aria-label="Episodes">{index}</nav>
  {"".join(body)}
  <footer>Quotes come from machine transcripts of the official uploads and may contain small transcription errors; timestamps are approximate and left blank where the line could not be located. These checks were made with AI assistance and can be wrong: see <a href="./#method">methodology</a> and <a href="https://github.com/shivan2418/once-upon-a-time-fact-check/issues">report a mistake</a>. Checked October 2026.</footer>
</div>
<script>
document.querySelectorAll('.filters button').forEach(b => b.addEventListener('click', () => {{
  document.querySelectorAll('.filters button').forEach(x => x.setAttribute('aria-pressed', x === b));
  if (b.dataset.f === 'all') delete document.body.dataset.only; else document.body.dataset.only = b.dataset.f;
}}));
</script>
''', n, n_clean


def main():
    stamps = json.loads(STAMPS.read_text()) if STAMPS.exists() else {}
    cards = []
    total = {k: 0 for k in KINDS}
    n_eps = 0
    for key, series, years, topic, missing in SERIES:
        eps = []
        for f in sorted((ROOT / "reports" / key).glob("s01e*.md")):
            n, t, summary, secs = parse(f.read_text())
            words = load_srt(TX / key / f"s01e{n:02d}.srt") if TX else []
            for k in KINDS:
                for it in secs.get(k, []):
                    sk = f"{key}|{n}|{it['quote']}"
                    if words:
                        quoted = re.match(r'\s*"(.+?)"', it["quote"])
                        tt = find_time(words, quoted.group(1) if quoted else it["quote"])
                        stamps[sk] = fmt_t(tt) if tt is not None else None
                    it["t"] = stamps.get(sk)
            eps.append(dict(n=n, title=t, summary=summary, **{k: secs.get(k, []) for k in KINDS + ("fine",)}))
        page, n, n_clean = series_page(key, series, years, topic, missing, eps, stamps)
        (DOCS / f"{key}.html").write_text(page)
        for k in KINDS:
            total[k] += n[k]
        n_eps += len(eps)
        cards.append((key, series, years, topic, len(eps), n, n_clean))
        located = sum(1 for e in eps for k in KINDS for i in e[k] if i["t"])
        print(f"docs/{key}.html: {len(eps)} episodes, {n['outdated']}/{n['common']}/{n['wrong']}, {located}/{sum(n.values())} timestamped")
    STAMPS.write_text(json.dumps(stamps, indent=0, ensure_ascii=False, sort_keys=True))
    (DOCS / "index.html").write_text(index_page(cards, total, n_eps))
    print(f"docs/index.html: {n_eps} episodes, {sum(total.values())} points")


def index_page(cards, total, n_eps):
    grid = "".join(f'''<a class="card" href="{key}.html">
  <span class="card-year">{years}</span>
  <h3>{html.escape(series.replace("Once Upon a Time... ", ""))}</h3>
  <span class="card-topic">{html.escape(topic[0].upper() + topic[1:])} · {neps} episodes</span>
  <span class="card-n"><span class="o">{n["outdated"]} outdated</span><span class="c">{n["common"]} common belief</span><span class="w">{n["wrong"]} wrong</span></span>
</a>''' for key, series, years, topic, neps, n, n_clean in cards)
    return HEAD.format(title="Once Upon a Time Fact Check",
                       desc="A fan-made, episode-by-episode fact check of six Once Upon a Time... series by Albert Barillé.") + f'''<body>
<div class="wrap">
  <p class="kicker">A fan-made fact check</p>
  <h1>Once Upon a Time… then and now</h1>
  <p class="lede big">We love these series. Albert Barillé's <em>Once Upon a Time…</em> cartoons taught a whole generation how the body works, where we came from and who went where first, and they still hold up as some of the best educational television ever made.</p>
  <p class="lede">They were also made between 1978 and 1996. Science has moved on, history has been rewritten in places, and a few things were simply wrong even then. This site is not a takedown. It is a companion: go ahead and watch the episodes (they are free on the official <a href="https://www.youtube.com/@onceuponatimechannel">Hello Maestro YouTube channel</a>), with your kids or on your own, and come here if you want to know which lines to take with a grain of salt.</p>
  <div class="tally"><span><b>{n_eps}</b>episodes checked</span><span class="o"><b>{total["outdated"]}</b>outdated</span><span class="c"><b>{total["common"]}</b>common beliefs then</span><span class="w"><b>{total["wrong"]}</b>wrong in their day</span></div>
  <h2 class="sec">The series</h2>
  <div class="cards">{grid}</div>
  <p class="key">The episodes are on the official <a href="https://www.youtube.com/@onceuponatimechannel">Hello Maestro YouTube channel</a>.</p>

  <h2 class="sec">How to read the checks</h2>
  <p>Every point quotes the line from the episode, gives a timestamp, and says what we know today. Points come in three kinds, because "it's wrong" means very different things for a cartoon from 1978:</p>
  <dl class="kinds">
    <div class="outdated"><dt>Outdated</dt><dd>Matched the science or scholarship of the day; later discoveries changed it. Nobody could have done better at the time.</dd></div>
    <div class="common"><dt>Common belief then</dt><dd>Specialists already knew better, but encyclopedias, school books and popular books still said it, so a writer would easily have repeated it. Each comes with a note on why it was believed.</dd></div>
    <div class="wrong"><dt>Wrong in its day</dt><dd>A careful writer could have got it right from ordinary references. Many of these are small slips in a date, a number or a name, and some are probably dubbing or translation errors.</dd></div>
  </dl>
  <p>Simplifications made for children ("the heart is a pump") are not counted as errors. They are listed under each episode as "simplified but fine". Each point also carries a confidence level, high or medium.</p>

  <h2 class="sec" id="method">Methodology</h2>
  <ol class="steps">
    <li><strong>Sources.</strong> We used the official uploads on the Hello Maestro YouTube channels, in the English dub. Where an episode is only available in the original French, it was checked in French and quoted in French with an English translation. A few episodes could not be found in English or French and are left out; each series page says which.</li>
    <li><strong>Transcription.</strong> Every episode was transcribed with OpenAI's open-source Whisper speech recognition model (large-v3-turbo, run locally through whisper.cpp with voice activity detection). The result is a timed transcript of the whole episode. The raw transcripts are published in the <a href="https://github.com/shivan2418/once-upon-a-time-fact-check/tree/main/transcripts">GitHub repository</a>, unedited, so you can check any quote in context.</li>
    <li><strong>Fact-checking.</strong> Each transcript was read in full by an AI model (Anthropic's Claude), a few episodes at a time, with instructions to check every claim the episode presents as fact (dates, names, numbers, how things work, who did what first), to sort each problem into the categories above, to say what is known today, to be conservative, and to treat garbled names or numbers as likely transcription errors rather than the show's fault. The checker used web searches to confirm specific dates, figures and recent findings where needed. For <em>Space</em>, only real science and history were checked, not the science-fiction plot.</li>
    <li><strong>Quotes and timestamps.</strong> Every quote had to be copied word for word from the transcript, and was then matched back to the subtitle timing to get the minute and second it is said.</li>
    <li><strong>Review.</strong> We read through the results and corrected problems we found along the way. Examples include mislabelled uploads (an episode that turned out to be a different one) and old British "billions" (a million millions) that had been flagged as wrong when they were right for the time. This was a careful read, not formal peer review.</li>
  </ol>

  <h2 class="sec">Limitations</h2>
  <ul class="limits">
    <li>The checks were produced with AI assistance and spot-checked, not written by historians or scientists. They can contain mistakes, especially points marked medium confidence.</li>
    <li>Speech recognition mishears names and numbers. Where a quote looks garbled, the show may well have said it correctly.</li>
    <li>We checked the English dub. Some "wrong" points are probably translation errors that are not in the French original.</li>
    <li>"Today" means October 2026. Science and history keep moving.</li>
  </ul>
  <p>Spotted a mistake? Please <a href="https://github.com/shivan2418/once-upon-a-time-fact-check/issues">open an issue on GitHub</a> with the episode and the point, ideally with a source. The per-episode reports the site is built from are in the repository as plain Markdown.</p>
  <footer>Not affiliated with Procidis or Hello Maestro. <em>Once Upon a Time…</em> is created by Albert Barillé and produced by Procidis; short quotes are used for commentary and criticism.</footer>
</div>
'''


main()
