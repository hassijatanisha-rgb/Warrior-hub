from concurrent.futures import ThreadPoolExecutor, as_completed
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = set()

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        href = dict(attrs).get("href", "")
        if href.startswith(("http://", "https://")):
            self.links.add(href)


def check(url):
    request = Request(url, headers={"User-Agent": "WarriorHub-LinkCheck/1.0"})
    try:
        with urlopen(request, timeout=15) as response:
            return url, response.status, response.geturl()
    except HTTPError as error:
        return url, error.code, error.geturl()
    except (URLError, TimeoutError, OSError) as error:
        return url, None, str(error)


root = Path(__file__).resolve().parents[1]
parser = LinkParser()
parser.feed((root / "index.html").read_text(encoding="utf-8"))

results = []
with ThreadPoolExecutor(max_workers=8) as pool:
    futures = [pool.submit(check, url) for url in sorted(parser.links)]
    for future in as_completed(futures):
        results.append(future.result())

broken = []
uncertain = []
for url, status, detail in sorted(results):
    if status in {404, 410}:
        broken.append((url, status, detail))
    elif status is None or status >= 400:
        uncertain.append((url, status, detail))

print(f"Checked {len(results)} external links")
for url, status, detail in broken:
    print(f"BROKEN {status} {url} -> {detail}")
for url, status, detail in uncertain:
    print(f"UNVERIFIED {status or '-'} {url} -> {detail}")
if broken:
    raise SystemExit(1)
