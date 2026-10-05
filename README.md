# Once Upon a Time… then and now

A fan-made, episode-by-episode fact check of six of Albert Barillé's *Once Upon a Time…* series:
*Man* (1978), *Space* (1982), *Life* (1987), *The Americas* (1991), *The Discoverers* (1994) and *The Explorers* (1996).

**Read it here: https://shivan2418.github.io/once-upon-a-time-fact-check/**

We love these series and still recommend them: watch them free on the official [Hello Maestro YouTube channel](https://www.youtube.com/@onceuponatimechannel). They were also made decades ago, so this is a companion for watching them today: every point quotes the line, gives the timestamp, and says what we know now. Each point is labelled *Outdated* (later research changed it), *Common belief then* (specialists knew better, popular books didn't) or *Wrong in its day*.

## How it was made

Episodes from the official [Hello Maestro YouTube](https://www.youtube.com/@onceuponatimechannel) uploads were transcribed with Whisper (large-v3-turbo, via whisper.cpp), then each transcript was read in full and fact-checked by Anthropic's Claude, with quotes verified word for word against the transcript and matched back to subtitle timings. The results were reviewed and corrected by hand where we found problems, but they are AI-assisted and can contain mistakes. See the [methodology](https://shivan2418.github.io/once-upon-a-time-fact-check/#method) on the site.

## Repository layout

- `reports/<series>/s01eNN - <Title>.md`: one fact-check report per episode (the source of truth)
- `data/timestamps.json`: the time in the episode for each quoted line
- `build.py`: builds the site into `docs/` (`python3 build.py`; pass `--transcripts DIR` to recompute timestamps from `.srt` files)
- `docs/`: the published GitHub Pages site

Transcripts and videos are not included.

## Corrections

Found a mistake? Please [open an issue](https://github.com/shivan2418/once-upon-a-time-fact-check/issues) with the series, episode and point, ideally with a source.

Not affiliated with Procidis or Hello Maestro. *Once Upon a Time…* is created by Albert Barillé and produced by Procidis.
