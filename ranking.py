from typing import Dict, List, Optional
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import networkx as nx
import json
import os

def build_countvec(corpus: List[str], stop_words=None):
    if not corpus:
        return None, None
    vec = CountVectorizer(token_pattern=r"(?u)\b\w+\b", stop_words=stop_words)
    matrix = vec.fit_transform(corpus)
    return vec, matrix

def compute_pagerank_from_json(graph_file: str, damping: float = 0.85) -> Dict[str, float]:
    if not os.path.exists(graph_file):
        return {}
    with open(graph_file, encoding="utf-8") as f:
        data = json.load(f)
    G = nx.DiGraph()
    for src, targets in data.items():
        for t in targets:
            G.add_edge(src, t)
    if G.number_of_nodes() == 0:
        return {}
    return nx.pagerank(G, alpha=damping)

def normalize_scores(score_dict: Dict[str, float]) -> Dict[str, float]:
    if not score_dict:
        return {}
    values = list(score_dict.values())
    min_s, max_s = min(values), max(values)
    if max_s == min_s:
        return {k: 1.0 for k in score_dict}
    return {k: (v - min_s) / (max_s - min_s) for k, v in score_dict.items()}

def search_query(
    query: str,
    urls: List[str],
    count_matrix,
    vectorizer: CountVectorizer,
    pages: Dict[str, dict],
    pagerank_scores: Optional[Dict[str, float]] = None,
    alpha: float = 0.85,
    top_k: int = 20
) -> List[Dict]:
   
    if not query or not vectorizer or count_matrix is None:
        return []

    try:
        q_vec = vectorizer.transform([query])
        scores = cosine_similarity(q_vec, count_matrix).flatten()
        vec_results = {urls[i]: float(scores[i]) for i in range(len(urls)) if scores[i] > 0}
    except Exception:
        vec_results = {}

    raw_results = {}
    for url, page in pages.items():
        text = page.get("text","") if isinstance(page, dict) else str(page)
        if query in text:
            raw_results[url] = 1.0

    merged_results = vec_results.copy()
    for url, score in raw_results.items():
        if url not in merged_results:
            merged_results[url] = score

    if not merged_results and pagerank_scores:
        norm_pr = normalize_scores(pagerank_scores)
        ranked_pr = sorted(norm_pr.items(), key=lambda x: x[1], reverse=True)[:top_k]
        results = []
        for u, s in ranked_pr:
            page = pages.get(u, {})
            text = page.get("text","") if isinstance(page, dict) else str(page)
            snippet = text[:250] + ("..." if len(text) > 250 else "")
            results.append({"url": u, "score": round(s,4), "snippet": snippet})
        return results

    final_scores = {}
    if pagerank_scores:
        norm_pr = normalize_scores(pagerank_scores)
        for url in merged_results.keys():
            tf_val = merged_results.get(url,0.0)
            pr_val = norm_pr.get(url,0.0)
            final_scores[url] = alpha*tf_val + (1-alpha)*pr_val
    else:
        final_scores = merged_results

    ranked = sorted(final_scores.items(), key=lambda x:x[1], reverse=True)[:top_k]
    results = []
    for u,s in ranked:
        page = pages.get(u, {})
        text = page.get("text","") if isinstance(page, dict) else str(page)
        snippet = text[:250] + ("..." if len(text) > 250 else "")
        results.append({"url": u, "score": round(s,4), "snippet": snippet})

    return results
