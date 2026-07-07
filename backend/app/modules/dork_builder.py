"""
Builds ready-to-click search engine URLs ("dorks") for a given subject.
This never performs the search itself - it only constructs URLs the
investigator opens in their own browser, using only public search engines.
"""
from urllib.parse import quote, quote_plus

SEARCH_ENGINES = {
    "Google": "https://www.google.com/search?q={q}",
    "Bing": "https://www.bing.com/search?q={q}",
    "DuckDuckGo": "https://duckduckgo.com/?q={q}",
    "Yandex": "https://yandex.com/search/?text={q}",
}

REVERSE_IMAGE_ENGINES = {
    "Google Images (upload manually)": "https://images.google.com/",
    "Google Lens (by image URL)": "https://lens.google.com/uploadbyurl?url={url}",
    "TinEye (by image URL)": "https://tineye.com/search?url={url}",
    "Yandex Images (by image URL)": "https://yandex.com/images/search?rpt=imageview&url={url}",
    "Bing Visual Search": "https://www.bing.com/images/search?q=imgurl:{url}&view=detailv2&iss=sbi",
}


def _links_for_query(query: str) -> list[dict]:
    q = quote_plus(query)
    return [{"engine": name, "query": query, "url": tpl.format(q=q)} for name, tpl in SEARCH_ENGINES.items()]


def build_dorks(subject: str, subject_type: str) -> dict:
    subject = subject.strip()
    out = {"subject": subject, "subject_type": subject_type, "groups": []}

    if subject_type == "name":
        queries = [
            f'"{subject}"',
            f'"{subject}" site:linkedin.com',
            f'"{subject}" site:facebook.com',
            f'"{subject}" resume OR CV filetype:pdf',
            f'"{subject}" contact OR email OR phone',
        ]
    elif subject_type == "username":
        queries = [
            f'"{subject}"',
            f'intext:"{subject}" site:reddit.com',
            f'intext:"{subject}" site:github.com',
            f'inurl:"{subject}"',
            f'"{subject}" forum OR profile',
        ]
    elif subject_type == "email":
        queries = [
            f'"{subject}"',
            f'"{subject}" site:pastebin.com',
            f'"{subject}" filetype:pdf OR filetype:xlsx OR filetype:csv',
            f'intext:"{subject}"',
        ]
    elif subject_type == "domain":
        queries = [
            f'site:{subject}',
            f'site:{subject} filetype:pdf',
            f'site:{subject} inurl:admin OR inurl:login',
            f'"{subject}" -site:{subject}',
            f'link:{subject}',
        ]
    elif subject_type == "phone":
        queries = [
            f'"{subject}"',
            f'"{subject}" site:facebook.com OR site:linkedin.com',
            f'"{subject}" contact OR signature',
        ]
    else:
        queries = [f'"{subject}"']

    out["groups"].append({"label": f"Web search dorks for {subject_type}", "links": []})
    for query in queries:
        out["groups"][-1]["links"].append({"query": query, "engines": _links_for_query(query)})

    return out


def build_reverse_image_links(image_url: str) -> dict:
    encoded = quote(image_url, safe="")
    links = []
    for name, tpl in REVERSE_IMAGE_ENGINES.items():
        url = tpl.format(url=encoded) if "{url}" in tpl else tpl
        links.append({"engine": name, "url": url})
    return {"image_url": image_url, "links": links}
