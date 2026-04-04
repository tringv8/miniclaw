"""
ArXiv Search Script
Usage:
    python search_arxiv.py "<query>" [max_results]
    python search_arxiv.py "LLM reasoning" 5
    python search_arxiv.py "2512.08769"     # Tra cứu theo paper ID

Output gồm: tiêu đề, tác giả, ngày đăng, DOI (nếu có), abstract.
"""

import sys
import ssl
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime

BASE_URL = "http://export.arxiv.org/api/query"
NS = {
    "atom":   "http://www.w3.org/2005/Atom",
    "arxiv":  "http://arxiv.org/schemas/atom",
}

def search(query: str, max_results: int = 5) -> list[dict]:
    cleaned = query.strip().lower().replace("arxiv:", "")
    is_id = len(cleaned) <= 15 and "." in cleaned and cleaned.replace(".", "").replace("/", "").replace("v", "").isdigit()

    params = {"id_list": cleaned, "max_results": max_results} if is_id else {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }

    url = f"{BASE_URL}?{urllib.parse.urlencode(params)}"
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    try:
        with urllib.request.urlopen(url, timeout=15, context=ssl_ctx) as r:
            root = ET.fromstring(r.read().decode("utf-8"))
    except Exception as e:
        print(f"[LỖI] Không kết nối được ArXiv API: {e}", file=sys.stderr)
        sys.exit(1)

    papers = []
    for entry in root.findall("atom:entry", NS):
        title   = (entry.findtext("atom:title",     default="", namespaces=NS) or "").strip()
        abstract= (entry.findtext("atom:summary",   default="", namespaces=NS) or "").strip()
        pub_raw = (entry.findtext("atom:published", default="", namespaces=NS) or "").strip()
        doi     = (entry.findtext("arxiv:doi",      default="", namespaces=NS) or "").strip()

        authors = [
            (a.findtext("atom:name", default="", namespaces=NS) or "").strip()
            for a in entry.findall("atom:author", NS)
        ]

        # Link trang abstract trên arxiv
        abs_url = next(
            (lk.get("href", "") for lk in entry.findall("atom:link", NS)
             if lk.get("rel") == "alternate"),
            ""
        )

        try:
            date = datetime.fromisoformat(pub_raw.replace("Z", "+00:00")).strftime("%Y-%m-%d")
        except Exception:
            date = pub_raw[:10]

        papers.append({
            "title":    title,
            "authors":  authors,
            "date":     date,
            "doi":      f"https://doi.org/{doi}" if doi else "",
            "link":     abs_url,
            "abstract": abstract,
        })

    return papers


def print_results(papers: list[dict], query: str):
    print(f"\n=== KẾT QUẢ TÌM KIẾM: \"{query}\" ({len(papers)} bài) ===\n")
    for i, p in enumerate(papers, 1):
        print(f"[{i}] {p['title']}")
        print(f"    Tác giả : {', '.join(p['authors'][:4])}{'...' if len(p['authors']) > 4 else ''}")
        print(f"    Ngày    : {p['date']}")
        print(f"    Link    : {p['link']}")
        if p['doi']:
            print(f"    DOI     : {p['doi']}")
        print(f"    Abstract:")
        # In full abstract để bot tóm tắt
        print(f"    {p['abstract']}")
        print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    query = sys.argv[1]
    max_results = int(sys.argv[2]) if len(sys.argv) >= 3 else 5
    papers = search(query, max_results)
    if papers:
        print_results(papers, query)
    else:
        print("Không tìm thấy kết quả nào.")
