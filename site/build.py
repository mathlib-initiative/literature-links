"""Build the Annotation Format Map, this repository's GitHub Pages site.

The page's design, wording and script are in index.template.html. Its data comes from this checkout:
the schema, the examples as the checker reads them, and the version from CHANGELOG.md.

usage: python3 site/build.py <output folder>
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "src"))

from literature_links import discovery  # noqa: E402

REPOSITORY = "https://github.com/mathlib-initiative/literature-links"


def examples() -> list[dict]:
    """Each example file in the page's order: its text, and what a reader gets from it after folder defaults."""
    folder = ROOT / "examples" / "companion"
    collection = discovery.collect([folder], root=folder)
    if collection.problems:
        raise SystemExit(f"the examples have problems: {collection.problems}")
    records: dict[Path, list[discovery.Record]] = {}
    for record in collection.records:
        records.setdefault(record.path, []).append(record)

    def entry(path: Path) -> dict:
        rows = records.get(path, [])
        kind = "defaults" if path.name == discovery.DEFAULTS else "json" if path.suffix.lower() == ".json" else "jsonl"
        return {"path": path.relative_to(folder).as_posix(), "kind": kind, "text": path.read_text(encoding="utf-8"),
                "records": [row.annotation for row in rows],
                "defaults": [file.relative_to(folder).as_posix() for file in rows[0].defaults] if rows else []}

    files = [*collection.files, *folder.rglob(discovery.DEFAULTS)]
    return [entry(path) for path in sorted(files, key=lambda path: (path.parent != folder,
                                                                    path.name != discovery.DEFAULTS, path.as_posix()))]


def version_lines(changelog: str) -> tuple[str, str]:
    """The page's version and the line saying what it shows, from the changelog's first heading."""
    heading = re.search(r"(?m)^## (.+?)\s*$", changelog)
    release = re.fullmatch(r"(\d\S*) \((\d{4}-\d{2}-\d{2})\)", heading[1]) if heading else None
    name = f'<a href="{REPOSITORY}">mathlib-initiative/literature-links</a>'
    if release is None:
        return "unreleased", f"The <code>main</code> branch of {name}, ahead of its last release."
    version, day = release.groups()
    return version, f'{name} <a href="{REPOSITORY}/releases/tag/v{version}">v{version}</a>, released {day}.'


def embedded(value: object) -> str:
    """JSON that can sit inside a script element, which the first ``</script`` would end."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")


def render() -> str:
    """The page, with every field of the template filled in."""
    version, provenance = version_lines((ROOT / "CHANGELOG.md").read_text(encoding="utf-8"))
    schema = json.loads((ROOT / "schema" / "companion.schema.json").read_text(encoding="utf-8"))
    page = (HERE / "index.template.html").read_text(encoding="utf-8")
    for field, value in (("@@VERSION@@", version), ("@@PROVENANCE@@", provenance),
                         ("@@SCHEMA@@", embedded(schema)), ("@@EXAMPLES@@", embedded(examples()))):
        if page.count(field) != 1:
            raise SystemExit(f"index.template.html should hold {field} once")
        page = page.replace(field, value)
    return page


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__.strip().splitlines()[-1], file=sys.stderr)
        return 2
    out = Path(argv[0])
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(render(), encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
