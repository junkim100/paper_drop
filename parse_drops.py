"""Parse markdown drop archives into JSON for the Paper Drop site."""

import json
import re
from pathlib import Path

import fire


def parse_drop_markdown(md_text: str, drop_type: str) -> list[dict]:
    """Parse a markdown file containing daily drops into structured JSON.

    Expected markdown format:
    ---
    ## Paper Drop - March 13, 2026

    Some digest text here...

    ### 1. Paper Title
    *Catchy Headline*

    Summary or notes about the paper...

    ### 2. Another Paper Title
    *Another Headline*

    More notes...

    ---
    ## Paper Drop - March 12, 2026
    ...
    """
    drops = []

    # Split by day sections (## headers with dates)
    day_pattern = re.compile(r"^## .+?[-–—]\s*(\w+ \d{1,2},?\s*\d{4})", re.MULTILINE)
    day_matches = list(day_pattern.finditer(md_text))

    if not day_matches:
        # Try alternative format: ## YYYY-MM-DD
        day_pattern = re.compile(r"^## .*?(\d{4}-\d{2}-\d{2})", re.MULTILINE)
        day_matches = list(day_pattern.finditer(md_text))

    for i, match in enumerate(day_matches):
        date_str = match.group(1).strip()
        start = match.start()
        end = day_matches[i + 1].start() if i + 1 < len(day_matches) else len(md_text)
        section = md_text[start:end].strip()

        # Parse date
        date_iso = parse_date(date_str)
        if not date_iso:
            continue

        # Extract markdown (the full section)
        markdown = section

        # Parse individual papers (### numbered headers)
        papers = parse_papers(section, drop_type, date_iso)

        drops.append(
            {
                "date": date_iso,
                "markdown": markdown,
                "papers": papers,
            }
        )

    return drops


def parse_date(date_str: str) -> str | None:
    """Convert various date formats to ISO YYYY-MM-DD."""
    import datetime

    # Already ISO format
    if re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        return date_str

    # Month Day, Year or Month Day Year
    for fmt in ["%B %d, %Y", "%B %d %Y", "%b %d, %Y", "%b %d %Y"]:
        try:
            dt = datetime.datetime.strptime(date_str, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue

    return None


def parse_papers(section: str, drop_type: str, date_iso: str) -> list[dict]:
    """Extract individual papers from a day section."""
    papers = []

    # Try numbered format first: ### 1. Title or ### 1) Title
    paper_pattern = re.compile(r"^###\s+(\d+)[.)]\s+(.+?)$", re.MULTILINE)
    paper_matches = list(paper_pattern.finditer(section))

    # If no numbered papers, try emoji format: ### 🔥🔥🔥 Title (auto-number them)
    if not paper_matches:
        paper_pattern = re.compile(r"^###\s+(?:🔥+\s+)?(.+?)$", re.MULTILINE)
        all_matches = list(paper_pattern.finditer(section))
        # Filter out known non-paper headers
        skip = {"TL;DR", "Field Pulse", "Eval Landscape", "TL;DR (read this if nothing else)"}
        paper_matches = []
        counter = 0
        for m in all_matches:
            title = m.group(1).strip()
            if any(s in title for s in skip):
                continue
            counter += 1
            # Store as a fake match with number injected
            paper_matches.append((counter, title, m.start(), m.end()))

        # Reprocess with the alternate format
        result_papers = []
        for i, (number, title, start_pos, end_pos) in enumerate(paper_matches):
            next_start = paper_matches[i + 1][2] if i + 1 < len(paper_matches) else len(section)
            content = section[end_pos:next_start].strip()

            headline = ""
            headline_match = re.match(r"^\*([^*]+)\*", content)
            if headline_match:
                headline = headline_match.group(1).strip()

            prefix = "paper" if drop_type == "paper_drops" else "eval"
            audio_file = f"audio/{prefix}-{date_iso}-{number}.mp3"
            script_file = f"scripts/{prefix}-{date_iso}-{number}.txt"

            result_papers.append({
                "number": number,
                "title": title,
                "headline": headline,
                "audio": audio_file,
                "script": script_file,
            })
        return result_papers

    for i, match in enumerate(paper_matches):
        number = int(match.group(1))
        title = match.group(2).strip()

        # Get the content between this paper and the next
        start = match.end()
        end = (
            paper_matches[i + 1].start() if i + 1 < len(paper_matches) else len(section)
        )
        content = section[start:end].strip()

        # Extract headline (first italic line)
        headline = ""
        headline_match = re.match(r"^\*([^*]+)\*", content)
        if headline_match:
            headline = headline_match.group(1).strip()

        # Build file paths
        prefix = "paper" if drop_type == "paper_drops" else "eval"
        audio_file = f"audio/{prefix}-{date_iso}-{number}.mp3"
        script_file = f"scripts/{prefix}-{date_iso}-{number}.txt"

        papers.append(
            {
                "number": number,
                "title": title,
                "headline": headline,
                "audio": audio_file,
                "script": script_file,
            }
        )

    return papers


def convert(
    paper_drops_md: str = "~/openclaw/memory/paper_drops.md",
    eval_drops_md: str = "~/openclaw/memory/eval_drops.md",
    output_dir: str = "data",
):
    """Convert markdown drop archives to JSON.

    Args:
        paper_drops_md: Path to paper_drops.md file.
        eval_drops_md: Path to eval_drops.md file.
        output_dir: Directory to write JSON output files.
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    for md_path_str, drop_type, json_name in [
        (paper_drops_md, "paper_drops", "paper_drops.json"),
        (eval_drops_md, "eval_drops", "eval_drops.json"),
    ]:
        md_path = Path(md_path_str).expanduser()
        if md_path.exists():
            md_text = md_path.read_text(encoding="utf-8")
            drops = parse_drop_markdown(md_text, drop_type)
            print(
                f"Parsed {len(drops)} days from {md_path} ({sum(len(d['papers']) for d in drops)} papers)"
            )
        else:
            print(f"Warning: {md_path} not found, writing empty array")
            drops = []

        out_file = output_path / json_name
        out_file.write_text(
            json.dumps(drops, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"Wrote {out_file}")


if __name__ == "__main__":
    fire.Fire(convert)
