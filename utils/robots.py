import urllib.robotparser as robotparser

USER_AGENT = "Mozilla/5.0 (compatible; SimpleCrawler/1.0)"
robots_cache = {}

def allowed_by_robots(url):
    from urllib.parse import urlparse
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"

    if base not in robots_cache:
        rp = robotparser.RobotFileParser()
        rp.set_url(base + "/robots.txt")
        try:
            rp.read()
        except:
            pass
        robots_cache[base] = rp

    try:
        return robots_cache[base].can_fetch(USER_AGENT, url)
    except:
        return True
