# -*- coding: utf-8 -*-
"""채널에 새로 올라온 편을 카탈로그(index.html 의 DATA)에 넣는다.

GitHub Actions 가 매일 실행한다. 서버(개인 yt-dlp 서버)가 없어도 되도록,
여기서는 유튜브 RSS 만 읽는다. 브라우저가 아니므로 CORS 제약이 없다.
분류 규칙은 PC 에서 카탈로그를 만들 때 쓴 것과 동일(tools/classifier_config.json).
"""
import json, os, re, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
INDEX = os.path.join(ROOT, "index.html")
SW = os.path.join(ROOT, "sw.js")
CHANNEL = "UCstI8HwGQsHdqLDgyH0PImw"
RSS = f"https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL}"

CFG = json.load(open(os.path.join(HERE, "classifier_config.json"), encoding="utf-8"))
GAZ, THEME, REGION, OVER, W = CFG["gaz"], CFG["theme"], CFG["region"], CFG["over"], CFG["W"]


def hits(text, aliases):
    n = 0
    for a in aliases:
        if isinstance(a, dict):
            n += len(re.findall(a["re"], text))
        else:
            n += text.count(a)
    return n


def split_title(t):
    """맨 뒤 해시태그를 떼고 대괄호 태그와 본문을 분리."""
    s = re.sub(r"(#\S+\s*)+$", "", t).strip()
    tag = " ".join(re.findall(r"\[([^\]]+)\]", s))
    return re.sub(r"\[[^\]]*\]", " ", s), tag


def country_of(title):
    body, tag = split_title(title)
    tag_hits = {c: hits(tag, al) for c, al in GAZ.items()}
    scores = {}
    for c, al in GAZ.items():
        s = W["bracket"] * tag_hits[c] + W["title"] * hits(body, al)
        if s:
            scores[c] = s
    if not scores:
        return None
    # 미국이 본문에서만 잡혔고 다른 나라도 있으면 행위자로 보고 제외
    if "미국" in scores and not tag_hits.get("미국") and len(scores) >= 2:
        del scores["미국"]
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    second = ranked[1][1] if len(ranked) > 1 else 0
    return ranked[0][0] if (second == 0 or ranked[0][1] >= W["dom"] * second) else None


def best_of(title, table):
    best, bs = None, 0
    for k, kws in table.items():
        s = sum(title.count(w) for w in kws)
        if s > bs:
            best, bs = k, s
    return best if bs else None


def bucket_of(label):
    if label in GAZ:    return "국가"
    if label in THEME:  return "주제"
    if label in REGION: return "지역"
    return "기타"


def assign(title):
    for sub, label in OVER:
        if sub in title:
            return bucket_of(label), label
    th, c = best_of(title, THEME), country_of(title)
    if th and not c: return "주제", th
    if c:            return "국가", c
    if th:           return "주제", th
    rg = best_of(title, REGION)
    if rg:           return "지역", rg
    return "기타", "기타"


def main():
    req = urllib.request.Request(RSS, headers={"User-Agent": "Mozilla/5.0 (compatible; catalog-updater)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        xml = r.read().decode("utf-8", "replace")

    entries = re.findall(r"<entry>(.*?)</entry>", xml, re.S)
    if not entries:
        print("RSS 에 항목이 없습니다 — 형식이 바뀌었을 수 있음. 변경 없이 종료.")
        return 0

    html = open(INDEX, encoding="utf-8").read()
    m = re.search(r"const BASE = (\[.*?\]);\n", html, re.S)
    if not m:
        print("BASE 배열을 찾지 못했습니다 — 중단", file=sys.stderr)
        return 1
    data = json.loads(m.group(1))
    have = {d["y"] for d in data if d.get("y")}

    added = []
    for e in entries:
        vid = re.search(r"<yt:videoId>([^<]+)</yt:videoId>", e)
        ttl = re.search(r"<title>(.*?)</title>", e, re.S)
        pub = re.search(r"<published>([^<]+)</published>", e)
        if not (vid and ttl):
            continue
        vid, title = vid.group(1).strip(), ttl.group(1).strip()
        if not vid or vid in have:
            continue
        # RSS 는 &amp; 같은 엔티티를 쓴다
        for a, b in (("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&#39;", "'")):
            title = title.replace(a, b)
        date = pub.group(1)[:10] if pub else ""
        b, l = assign(title)
        data.append({"b": b, "l": l, "d": date, "s": date.replace("-", ""),
                     "t": title, "y": vid, "k": "yt"})
        have.add(vid)
        added.append((date, b, l, title))

    if not added:
        print("새 영상 없음 — 변경 없이 종료.")
        return 0

    data.sort(key=lambda d: d.get("s") or "99999999")
    new_line = "const BASE = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n"
    open(INDEX, "w", encoding="utf-8").write(html[:m.start()] + new_line + html[m.end():])

    # 에셋이 바뀌었으므로 서비스워커 캐시 버전을 올린다(안 올리면 기기가 옛 파일을 계속 쓴다)
    sw = open(SW, encoding="utf-8").read()
    mv = re.search(r"globe-radio-v(\d+)", sw)
    if mv:
        sw = sw.replace(mv.group(0), f"globe-radio-v{int(mv.group(1)) + 1}")
        open(SW, "w", encoding="utf-8").write(sw)

    print(f"새 영상 {len(added)}편 추가 (총 {len(data)}편)")
    for date, b, l, t in added:
        print(f"  {date}  {b}/{l}  {t[:60]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
