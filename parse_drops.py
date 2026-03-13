"""Parse markdown drop archives into JSON for the Paper Drop site."""

import json
import os
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

        # Extract the TL;DR / intro (everything before first paper header)
        paper_header_pattern = re.compile(r"^###\s+(?:\d+[.)]\s+|🔥)", re.MULTILINE)
        first_paper = paper_header_pattern.search(section)
        
        # Get intro text (TL;DR section)
        intro = section[:first_paper.start()].strip() if first_paper else section
        # Remove the day header from intro
        intro_lines = intro.split("\n")
        intro = "\n".join(intro_lines[1:]).strip() if intro_lines else ""
        
        # Get footer text (Field Pulse / Eval Landscape - after last paper)
        footer = ""
        footer_pattern = re.compile(r"^##\s+(Field Pulse|Eval Landscape|🎯|🌡️)", re.MULTILINE)
        footer_match = footer_pattern.search(section)
        if footer_match:
            footer = section[footer_match.start():].strip()

        # Clean intro and footer
        date_pattern = r"(?:—\s*)?(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}"
        for_cleanup = [
            (r"^---+\s*$", ""),
            (r"^\*?_?Papers covered.*$", ""),
            (r"^\*?_?Classics covered.*$", ""),
            (r"^Reply with a paper number.*$", ""),
            (r"^\*?(?:Eval Drop|Paper Drop)\s*[-–—]\s*\*?\s*$", ""),
            (date_pattern, ""),
        ]
        for pattern, repl in for_cleanup:
            intro = re.sub(pattern, repl, intro, flags=re.MULTILINE)
            footer = re.sub(pattern, repl, footer, flags=re.MULTILINE)
        intro = re.sub(r"\n{3,}", "\n\n", intro).strip()
        footer = re.sub(r"\n{3,}", "\n\n", footer).strip()

        # Parse individual papers with per-paper markdown
        papers = parse_papers(section, drop_type, date_iso)

        drops.append(
            {
                "date": date_iso,
                "intro": intro,
                "footer": footer,
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


def load_venue_overrides() -> dict:
    """Load venue overrides from venue_overrides.json if it exists."""
    override_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "venue_overrides.json")
    if os.path.exists(override_path):
        import json as _json
        with open(override_path) as f:
            return _json.load(f)
    return {}

_VENUE_OVERRIDES = load_venue_overrides()


def extract_venue(content: str, link: str = "") -> tuple[str, str]:
    """Extract venue from content or link. Returns (venue, cleaned_content)."""
    # Check overrides first
    for arxiv_id, override in _VENUE_OVERRIDES.items():
        if arxiv_id.startswith("_"):
            continue
        if arxiv_id in (link or "") or arxiv_id in content:
            # Remove "Actual title" lines
            content = re.sub(r"\*\*Actual title:\*\*.*$", "", content, flags=re.MULTILINE)
            content = re.sub(r"\n{3,}", "\n\n", content).strip()
            venue = override.get("venue", "")
            scores = override.get("scores")
            if scores:
                venue = f"{venue} ({scores})"
            return venue, content

    # Remove "Actual title" lines from content (metadata, not display)
    actual_match = re.search(
        r"\*\*Actual title:\*\*.*$", content, re.MULTILINE
    )
    if actual_match:
        content = content[:actual_match.start()] + content[actual_match.end():]
        content = re.sub(r"\n{3,}", "\n\n", content).strip()

    # Check for explicit venue markers in content
    venue_match = re.search(r"\*\*Venue:\*\*\s*(.+?)$", content, re.MULTILINE)
    if venue_match:
        venue = venue_match.group(1).strip()
        content = content[:venue_match.start()] + content[venue_match.end():]
        content = re.sub(r"\n{3,}", "\n\n", content).strip()
        return venue, content

    # Fallback: derive from arxiv ID year
    if link:
        arxiv_match = re.search(r"arxiv\.org/abs/(\d{2})", link)
        if arxiv_match:
            return f"arXiv 20{arxiv_match.group(1)}", content
    
    arxiv_match = re.search(r"arxiv\.org/abs/(\d{2})", content)
    if arxiv_match:
        return f"arXiv 20{arxiv_match.group(1)}", content

    # HN link
    if "news.ycombinator.com" in content or "news.ycombinator.com" in (link or ""):
        return "HN Discussion", content

    return "", content


def clean_paper_content(content: str) -> str:
    """Remove day headers, footer sections, and trailing separators from per-paper content."""
    # Remove any ## day headers that leaked in
    content = re.sub(r"^##\s+(?:Paper Drop|Eval Drop|🧪|📏).*$", "", content, flags=re.MULTILINE)
    # Remove footer sections (Eval Landscape, Field Pulse)
    content = re.sub(r"^##\s+(?:🎯|🌡️|Field Pulse|Eval Landscape).*", "", content, flags=re.MULTILINE | re.DOTALL)
    # Remove horizontal rules
    content = re.sub(r"^---+\s*$", "", content, flags=re.MULTILINE)
    # Remove "Reply with a paper number..." line
    content = re.sub(r"^Reply with a paper number.*$", "", content, flags=re.MULTILINE)
    # Remove standalone arxiv links (title already links there)
    content = re.sub(r"^\[(?:Paper|Link|Read it|arxiv|arXiv).*?\]\(https?://arxiv\.org[^\)]+\)\s*$", "", content, flags=re.MULTILINE)
    content = re.sub(r"^https?://arxiv\.org/abs/\S+\s*$", "", content, flags=re.MULTILINE)
    # Remove [NEW] / [CLASSIC] tags (shown differently in UI)
    content = re.sub(r"^\*?\[(?:NEW|CLASSIC)\]\*?\s*$", "", content, flags=re.MULTILINE)
    # Remove date references like "March 13, 2026" or "— March 13, 2026" (day header already shows date)
    content = re.sub(r"(?:—\s*)?(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}", "", content)
    # Remove "Papers covered:" and "Classics covered:" metadata
    content = re.sub(r"^(?:Papers covered|Classics covered).*$", "", content, flags=re.MULTILINE)
    # Clean up excessive blank lines
    content = re.sub(r"\n{3,}", "\n\n", content).strip()
    return content


def extract_vibe(content: str) -> tuple[int, str, str]:
    """Extract vibe check rating from content. Returns (fire_count, vibe_label, cleaned_content)."""
    vibe_match = re.search(r"\*\*Vibe check:\*\*\s*(🔥+)\s*(.*?)$", content, re.MULTILINE)
    if vibe_match:
        fires = vibe_match.group(1).count("🔥")
        label = vibe_match.group(2).strip().rstrip(".")
        # Remove the vibe check line from content
        cleaned = content[:vibe_match.start()] + content[vibe_match.end():]
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
        return fires, label, cleaned
    return 0, "", content


def extract_water_cooler(content: str) -> tuple[str, str]:
    """Extract water cooler line. Returns (quote, cleaned_content)."""
    wc_match = re.search(r"\*\*Water cooler:\*\*\s*(.*?)$", content, re.MULTILINE)
    if wc_match:
        quote = wc_match.group(1).strip().strip('"').strip('"').strip('"')
        cleaned = content[:wc_match.start()] + content[wc_match.end():]
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
        return quote, cleaned
    return "", content


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
            
            # Remove trailing --- separator
            content = re.sub(r"\n---\s*$", "", content).strip()

            headline = ""
            headline_match = re.match(r"^\*([^*]+)\*", content)
            if headline_match:
                headline = headline_match.group(1).strip()

            # Clean and extract metadata
            content = clean_paper_content(content)

            # Extract link
            link = ""
            link_match = re.search(r"\[.*?\]\((https?://[^\)]+)\)", content)
            if not link_match:
                link_match = re.search(r"(https?://arxiv\.org/abs/\S+)", content)
            if link_match:
                link = link_match.group(1)

            venue, content = extract_venue(content, link)
            fires, vibe_label, content = extract_vibe(content)
            water_cooler, content = extract_water_cooler(content)

            prefix = "paper" if drop_type == "paper_drops" else "eval"
            audio_file = f"audio/{prefix}-{date_iso}-{number}.mp3"
            script_file = f"scripts/{prefix}-{date_iso}-{number}.txt"

            result_papers.append({
                "number": number,
                "title": title,
                "headline": headline,
                "link": link,
                "vibe": fires,
                "vibe_label": vibe_label,
                "venue": venue,
                "water_cooler": water_cooler,
                "markdown": content,
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
        content = re.sub(r"\n---\s*$", "", content).strip()

        # Extract headline (first italic line)
        headline = ""
        headline_match = re.match(r"^\*([^*]+)\*", content)
        if headline_match:
            headline = headline_match.group(1).strip()

        # Clean and extract metadata
        content = clean_paper_content(content)

        # Extract link first (needed for venue)
        link = ""
        link_match = re.search(r"\[.*?\]\((https?://[^\)]+)\)", content)
        if not link_match:
            link_match = re.search(r"(https?://arxiv\.org/abs/\S+)", content)
        if link_match:
            link = link_match.group(1)

        venue, content = extract_venue(content, link)
        fires, vibe_label, content = extract_vibe(content)
        water_cooler, content = extract_water_cooler(content)

        # Build file paths
        prefix = "paper" if drop_type == "paper_drops" else "eval"
        audio_file = f"audio/{prefix}-{date_iso}-{number}.mp3"
        script_file = f"scripts/{prefix}-{date_iso}-{number}.txt"

        papers.append(
            {
                "number": number,
                "title": title,
                "headline": headline,
                "link": link,
                "vibe": fires,
                "vibe_label": vibe_label,
                "venue": venue,
                "water_cooler": water_cooler,
                "markdown": content,
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
