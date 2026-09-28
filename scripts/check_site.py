from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PAGES = [ROOT / name for name in ("index.html", "privacy.html", "terms.html", "accessibility.html")]


class AuditParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.links = []
        self.remote_assets = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if "id" in values:
            self.ids.append(values["id"])
        if tag == "a" and "href" in values:
            self.links.append((values["href"], values.get("target"), values.get("rel", "")))
        if tag == "script" or (tag == "link" and values.get("rel") == "stylesheet"):
            target = values.get("src") or values.get("href")
            if target and target.startswith(("http://", "https://")):
                self.remote_assets.append(target)


def audit_page(path):
    source = path.read_text(encoding="utf-8")
    parser = AuditParser()
    parser.feed(source)
    duplicates = sorted({item for item in parser.ids if parser.ids.count(item) > 1})
    if duplicates:
        raise SystemExit(f"{path.name}: duplicate ids: {', '.join(duplicates)}")
    if parser.remote_assets:
        raise SystemExit(f"{path.name}: remote runtime assets: {', '.join(parser.remote_assets)}")
    for href, target, rel in parser.links:
        parsed = urlparse(href)
        if target == "_blank" and "noopener" not in rel.split():
            raise SystemExit(f"{path.name}: external tab lacks noopener: {href}")
        if parsed.scheme or href.startswith(("#", "mailto:", "tel:")):
            continue
        local = (path.parent / parsed.path).resolve()
        if not local.exists():
            raise SystemExit(f"{path.name}: broken local link: {href}")
    return source, parser


index, index_parser = audit_page(PAGES[0])
for page in PAGES[1:]:
    audit_page(page)

required_ids = {"home", "citing", "library", "notes", "research", "mental-health", "organization", "study-tips", "campus", "calendar"}
missing_ids = required_ids - set(index_parser.ids)
if missing_ids:
    raise SystemExit("Missing index sections: " + ", ".join(sorted(missing_ids)))

for stale in ("Spring 2026", "font-awesome", "fonts.googleapis.com", "top students swear by"):
    if stale.lower() in index.lower():
        raise SystemExit(f"Stale or prohibited marker remains: {stale}")

for required in ("Last checked 29 September 2026", "not affiliated with, sponsored by or endorsed", "call 911"):
    if required.lower() not in index.lower():
        raise SystemExit(f"Required disclosure missing: {required}")

scripts = re.findall(r"<script>(.*?)</script>", index, flags=re.DOTALL)
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as handle:
    handle.write("\n".join(scripts))
    script_path = Path(handle.name)
try:
    node = shutil.which("node")
    bundled_node = Path("/Users/tanisha/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node")
    if not node and bundled_node.exists():
        node = str(bundled_node)
    if not node:
        raise SystemExit("Node.js is required for JavaScript syntax validation")
    subprocess.run([node, "--check", str(script_path)], check=True, capture_output=True, text=True)
finally:
    script_path.unlink(missing_ok=True)

print(f"Warrior Hub checks passed: {len(PAGES)} pages, {len(index_parser.links)} index links")
