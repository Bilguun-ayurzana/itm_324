# crawler.py
import time
import json
import threading
from queue import Queue
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
import networkx as nx
from utils.preprocessing import detect_language, mn_preprocess, en_preprocess

# ---------------- Data structures & config ----------------
visited = set()
pages_content = {}      # url -> {"title":..., "text":...}
links_graph = nx.DiGraph()

DEFAULT_SEED_URLS = ["https://mn.wikipedia.org/wiki/Нэвтэрхий_толь"]  # default start page
MAX_PAGES = 500
REQUEST_DELAY = 0.5
CRAWL_TIMEOUT = 5
USER_AGENT = "Mozilla/5.0 (compatible; GenericCrawler/1.0)"
NUM_WORKERS = 10
OUTPUT_PAGES_FILE = "pages.json"
OUTPUT_GRAPH_FILE = "graph.json"

_session = requests.Session()
_session.headers.update({"User-Agent": USER_AGENT})
_queue = Queue()
_lock = threading.Lock()

# ---------------- Helpers ----------------
def normalize_url(raw, base=None):
    try:
        if base:
            raw = urljoin(base, raw)
        parsed = urlparse(raw)
        if parsed.scheme not in ("http", "https"):
            return None
        return parsed._replace(fragment="").geturl()
    except Exception:
        return None

def allowed_by_robots(url):
    # Placeholder: always allow
    return True

# ---------------- Worker ----------------
def _worker():
    while True:
        item = _queue.get()
        if item is None:
            _queue.task_done()
            break

        url = normalize_url(item)
        if not url:
            _queue.task_done()
            continue

        with _lock:
            if url in visited:
                _queue.task_done()
                continue

        if not allowed_by_robots(url):
            _queue.task_done()
            continue

        try:
            resp = _session.get(url, timeout=CRAWL_TIMEOUT)
        except Exception:
            _queue.task_done()
            continue

        if resp.status_code != 200 or "text/html" not in resp.headers.get("Content-Type", ""):
            _queue.task_done()
            continue

        try:
            soup = BeautifulSoup(resp.text, "html.parser")
            page_title = soup.title.string.strip() if soup.title and soup.title.string else url
            visible_text = " ".join(list(soup.stripped_strings)[:500])
            full_text = " ".join(list(soup.stripped_strings))
        except Exception:
            _queue.task_done()
            continue

        lang = detect_language(f"{page_title} {visible_text}")
        text_proc = mn_preprocess(full_text) if lang == "mn" else en_preprocess(full_text)

        with _lock:
            pages_content[url] = {"title": page_title, "text": text_proc}
            visited.add(url)
            links_graph.add_node(url)
            print(f"[crawler] Crawled ({len(visited)}): {url}")

        # Collect links (any domain)
        for a in soup.find_all("a", href=True):
            link = normalize_url(a.get("href"), base=url)
            if not link:
                continue
            with _lock:
                links_graph.add_node(link)
                links_graph.add_edge(url, link)
                if link not in visited and (_queue.qsize() + len(visited)) < MAX_PAGES:
                    _queue.put(link)

        time.sleep(REQUEST_DELAY)
        _queue.task_done()

# ---------------- Crawl entrypoint ----------------
def crawl(seed_urls=None, max_pages=MAX_PAGES, delay=REQUEST_DELAY,
          pages_file=OUTPUT_PAGES_FILE, graph_file=OUTPUT_GRAPH_FILE,
          num_workers=NUM_WORKERS):
    global MAX_PAGES, REQUEST_DELAY, NUM_WORKERS
    if seed_urls is None:
        seed_urls = DEFAULT_SEED_URLS

    MAX_PAGES = int(max_pages)
    REQUEST_DELAY = float(delay)
    NUM_WORKERS = int(num_workers)

    with _lock:
        visited.clear()
        pages_content.clear()
        links_graph.clear()

    print(f"[crawler] Starting crawl from: {seed_urls}")
    for s in seed_urls:
        _queue.put(s)

    threads = []
    for _ in range(NUM_WORKERS):
        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        threads.append(t)

    _queue.join()

    for _ in threads:
        _queue.put(None)
    for t in threads:
        t.join()

    # Save pages.json
    try:
        with open(pages_file, "w", encoding="utf-8") as f:
            json.dump(pages_content, f, ensure_ascii=False, indent=2)
        print(f"[crawler] Saved {len(pages_content)} pages to {pages_file}")
    except Exception as e:
        print(f"[crawler] Failed to save pages file: {e}")

    # Save graph.json
    try:
        graph_dict = {node: list(links_graph.successors(node)) for node in links_graph.nodes}
        with open(graph_file, "w", encoding="utf-8") as f:
            json.dump(graph_dict, f, ensure_ascii=False, indent=2)
        print(f"[crawler] Saved graph with {len(links_graph)} nodes to {graph_file}")
    except Exception as e:
        print(f"[crawler] Failed to save graph file: {e}")

    print("[crawler] Crawl finished!")
    return pages_file, graph_file


if __name__ == "__main__":
    print("Starting crawl (standalone)...")
    crawl()
