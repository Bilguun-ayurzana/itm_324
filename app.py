# app.py
from flask import Flask, request, render_template
import threading, os, json, math
from ranking import build_countvec, search_query, compute_pagerank_from_json
from utils.preprocessing import mn_preprocess, en_preprocess, detect_language
from markupsafe import Markup
from crawler import crawl

app = Flask(__name__)
PAGES_FILE = "pages.json"
GRAPH_FILE = "graph.json"

_pages_mtime = 0.0
_pages_content = {}
_urls = []
_corpus = []
_vectorizer = None
_count_matrix = None
_pagerank_scores = {}

_crawl_in_progress = False
_crawl_message = ""

def build_index(force=False):
    global _pages_mtime, _pages_content, _urls, _corpus, _vectorizer, _count_matrix, _pagerank_scores
    mtime = os.path.getmtime(PAGES_FILE) if os.path.exists(PAGES_FILE) else 0.0
    if not force and mtime==_pages_mtime and _vectorizer and _count_matrix is not None:
        return
    if os.path.exists(PAGES_FILE):
        with open(PAGES_FILE, encoding="utf-8") as f:
            _pages_content = json.load(f)
    _urls = list(_pages_content.keys())
    _corpus = []
    for page in _pages_content.values():
        if isinstance(page, dict):
            text = page.get("text", "")
        else:
            text = str(page)
        lang = detect_language(text)
        _corpus.append(mn_preprocess(text) if lang=="mn" else en_preprocess(text))
    _vectorizer, _count_matrix = build_countvec(_corpus)
    _pagerank_scores = compute_pagerank_from_json(GRAPH_FILE)
    _pages_mtime = mtime

def get_snippet(page_dict, query, snippet_len=200):
    if not page_dict:
        return ""
    if isinstance(page_dict, dict):
        text = page_dict.get("text","")
    else:
        text = str(page_dict)
    text_lower = text.lower()
    query_lower = query.lower()
    start = text_lower.find(query_lower)
    if start == -1:
        start = 0
    snippet = text[start:start+snippet_len]
    highlighted = snippet.replace(query, f'<mark style="background:yellow;">{query}</mark>')
    return Markup(highlighted)

def precision_at_k(relevant, retrieved, k):
    retrieved_k = retrieved[:k]
    if not retrieved_k: return 0.0
    return sum(1 for doc in retrieved_k if doc in relevant) / len(retrieved_k)

def recall_at_k(relevant, retrieved, k):
    retrieved_k = retrieved[:k]
    if not relevant: return 0.0
    return sum(1 for doc in retrieved_k if doc in relevant) / len(relevant)

def f1_score(precision, recall):
    if precision + recall == 0: return 0.0
    return 2 * (precision * recall) / (precision + recall)

def ndcg_at_k(relevant, retrieved, k):
    dcg = 0.0
    for i, doc in enumerate(retrieved[:k], start=1):
        rel = 1 if doc in relevant else 0
        dcg += rel / math.log2(i+1)
    ideal_rels = [1]*min(len(relevant), k)
    idcg = sum([rel / math.log2(i+1) for i, rel in enumerate(ideal_rels, start=1)])
    return dcg / idcg if idcg>0 else 0.0

@app.route("/pages")
def pages_route():
    build_index()
    pages_dict = {}
    for url, page in _pages_content.items():
        if isinstance(page, dict):
            text = page.get("text","")
        else:
            text = str(page)
        snippet = text[:250] + ("..." if len(text)>250 else "")
        pages_dict[url] = snippet
    return render_template("pages.html", pages=pages_dict)

@app.route("/", methods=["GET","POST"])
def index_route():
    global _crawl_in_progress, _crawl_message
    build_index()
    results=[]
    query=""
    metrics = {}

    if request.method=="POST":
        if "seed" in request.form:
            seed = request.form.get("seed","").strip()
            if seed:
                _crawl_in_progress = True
                _crawl_message = f"Crawling started from: {seed}"

                def _crawl_thread():
                    crawl([seed])
                    build_index(force=True) 
                    global _crawl_in_progress, _crawl_message
                    _crawl_in_progress = False
                    _crawl_message = f"Crawling finished from: {seed}"

                threading.Thread(target=_crawl_thread, daemon=True).start()

        elif "query" in request.form:
            query=request.form.get("query","").strip()
            if query and _vectorizer:
                results=search_query(
                    query=query,
                    urls=_urls,
                    count_matrix=_count_matrix,
                    vectorizer=_vectorizer,
                    pages=_pages_content,
                    pagerank_scores=_pagerank_scores,
                    alpha=0.85,
                    top_k=20
                )
                for r in results:
                    page_data = _pages_content.get(r["url"], {})
                    r["title"] = page_data.get("title", r["url"]) if isinstance(page_data, dict) else r["url"]
                    r["snippet"] = get_snippet(page_data, query)

                retrieved_urls = [r["url"] for r in results]
                relevant_urls = retrieved_urls[:3]
                k = min(10,len(retrieved_urls))
                p = precision_at_k(relevant_urls, retrieved_urls, k)
                r_score = recall_at_k(relevant_urls, retrieved_urls, k)
                f1 = f1_score(p,r_score)
                ndcg = ndcg_at_k(relevant_urls, retrieved_urls, k)
                metrics = {"precision": round(p,4), "recall": round(r_score,4),
                           "f1": round(f1,4), "ndcg": round(ndcg,4)}

    crawl_message = _crawl_message if _crawl_in_progress or _crawl_message else ""

    return render_template("index.html", results=results, query=query,
                           crawl_message=crawl_message, metrics=metrics)


if __name__=="__main__":
    build_index()
    app.run(debug=True, host="0.0.0.0", port=5000)
