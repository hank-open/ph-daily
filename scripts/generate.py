#!/usr/bin/env python3
"""
Product Hunt 早报生成器
用法:
  python3 scripts/generate.py              # 生成昨日早报
  python3 scripts/generate.py 2026-07-15  # 生成指定日期早报
"""

import sys
import re
import os
import json
import subprocess
from datetime import datetime, timedelta, timezone
from urllib.request import urlopen, Request
from urllib.error import URLError

# ── 配置 ────────────────────────────────────────────────────────────────────

DECOHACK_BASE = "https://decohack.com/producthunt-daily-{date}/"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/125.0 Safari/537.36"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ── 抓取 ─────────────────────────────────────────────────────────────────────

def fetch(date_str: str) -> str:
    url = DECOHACK_BASE.format(date=date_str)
    print(f"  Fetching {url}")
    req = Request(url, headers={"User-Agent": UA})
    try:
        with urlopen(req, timeout=20) as r:
            return r.read().decode("utf-8", errors="replace")
    except URLError as e:
        raise SystemExit(f"  ✗ 抓取失败: {e}")

# ── 解析 ─────────────────────────────────────────────────────────────────────

def strip_tags(html: str) -> str:
    html = re.sub(r"<script.*?</script>", "", html, flags=re.DOTALL)
    html = re.sub(r"<style.*?</style>", "", html, flags=re.DOTALL)
    html = re.sub(r"<[^>]+>", " ", html)
    html = re.sub(r"[ \t]+", " ", html)
    return html

def parse_products(raw_text: str) -> list[dict]:
    """从纯文本中解析产品列表。"""
    products = []

    # 按编号分割产品块
    blocks = re.split(r"\n\s*(\d+)\.\s+", raw_text)
    # blocks[0] = 头部噪声, blocks[1::2] = 编号, blocks[2::2] = 内容
    pairs = list(zip(blocks[1::2], blocks[2::2]))

    for rank_str, block in pairs:
        rank = int(rank_str)
        lines = [l.strip() for l in block.split("\n") if l.strip()]
        if not lines:
            continue

        # 第一行是产品名
        name = lines[0].strip()

        # 解析字段
        def field(key):
            for l in lines:
                if l.startswith(key):
                    return l[len(key):].strip()
            return ""

        tagline  = field("标语 ：") or field("标语：")
        desc     = field("介绍 ：") or field("介绍：")
        votes_raw = field("票数 :") or field("票数：") or field("票数:")
        featured_raw = field("是否精选 ：") or field("是否精选：")

        # 票数
        votes = 0
        m = re.search(r"(\d+)", votes_raw)
        if m:
            votes = int(m.group(1))

        featured = featured_raw.strip().startswith("是")

        # 描述去掉常见噪声词
        desc = re.sub(r"\s*(产品网站|Product Hunt|关键词|立即访问|View on Product Hunt)\s*[:：].*", "", desc)
        desc = desc.strip()

        if name and votes > 0:
            products.append({
                "rank": rank,
                "name": name,
                "tagline": tagline,
                "desc": desc,
                "votes": votes,
                "featured": featured,
            })

    products.sort(key=lambda x: x["rank"])
    return products

# ── HTML 生成 ─────────────────────────────────────────────────────────────────

def e(s: str) -> str:
    """HTML 转义"""
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace('"', "&quot;"))

RANK_CLASS = {1: "gold", 2: "silver", 3: "bronze"}

def card_html(p: dict) -> str:
    cls = RANK_CLASS.get(p["rank"], "")
    badge = '<span class="badge-featured">精选</span>' if p["featured"] else ""
    return f"""  <div class="card">
    <div class="rank {cls}">{p["rank"]}</div>
    <div class="card-body">
      <div class="card-top">
        <span class="card-name">{e(p["name"])}</span>
        {badge}
        <span class="votes">{p["votes"]}</span>
      </div>
      <div class="tagline">{e(p["tagline"])}</div>
      <div class="desc">{e(p["desc"])}</div>
    </div>
  </div>"""

def table_row(p: dict) -> str:
    return f"""      <tr>
        <td>{e(p["name"])}</td>
        <td><span class="votes-sm">▲ {p["votes"]}</span></td>
        <td>{e(p["tagline"])}</td>
      </tr>"""

CSS = """
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", sans-serif;
      background: #f5f5f0; color: #1a1a1a;
      padding: 32px 16px 64px; line-height: 1.6;
    }
    .container { max-width: 760px; margin: 0 auto; }
    .header { text-align: center; margin-bottom: 40px; }
    .header .logo { font-size: 28px; font-weight: 800; color: #da552f; letter-spacing: -0.5px; }
    .header .logo span { color: #1a1a1a; }
    .header .date { font-size: 14px; color: #888; margin-top: 6px; letter-spacing: 0.5px; }
    .header h1 { font-size: 22px; font-weight: 700; margin-top: 12px; color: #1a1a1a; }
    .section-title {
      font-size: 12px; font-weight: 700; text-transform: uppercase;
      letter-spacing: 1.5px; color: #999; margin: 40px 0 16px;
      padding-bottom: 8px; border-bottom: 1px solid #e5e5e0;
    }
    .card {
      background: #fff; border-radius: 12px; padding: 20px 22px;
      margin-bottom: 12px; display: flex; gap: 16px; align-items: flex-start;
      border: 1px solid #eee; transition: box-shadow 0.15s;
    }
    .card:hover { box-shadow: 0 4px 16px rgba(0,0,0,0.08); }
    .rank { font-size: 22px; font-weight: 800; color: #da552f; min-width: 32px; padding-top: 2px; }
    .rank.gold   { color: #f5a623; }
    .rank.silver { color: #9b9b9b; }
    .rank.bronze { color: #c07840; }
    .card-body { flex: 1; }
    .card-top { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-bottom: 4px; }
    .card-name { font-size: 17px; font-weight: 700; color: #1a1a1a; }
    .badge-featured {
      font-size: 11px; font-weight: 600; background: #fff3ee; color: #da552f;
      border: 1px solid #ffd0be; border-radius: 4px; padding: 1px 7px;
    }
    .votes { margin-left: auto; font-size: 13px; font-weight: 700; color: #da552f; white-space: nowrap; }
    .votes::before { content: "▲ "; }
    .tagline { font-size: 14px; font-weight: 600; color: #444; margin-bottom: 6px; }
    .desc { font-size: 13.5px; color: #666; line-height: 1.65; }
    table {
      width: 100%; border-collapse: collapse; background: #fff;
      border-radius: 12px; overflow: hidden; border: 1px solid #eee; font-size: 13.5px;
    }
    thead tr { background: #fafaf8; }
    th {
      text-align: left; padding: 10px 16px; font-size: 11px; font-weight: 700;
      text-transform: uppercase; letter-spacing: 1px; color: #999; border-bottom: 1px solid #eee;
    }
    td { padding: 11px 16px; border-bottom: 1px solid #f2f2f0; vertical-align: top; }
    tr:last-child td { border-bottom: none; }
    tr:hover td { background: #fafaf8; }
    td:first-child { font-weight: 700; color: #1a1a1a; }
    td .votes-sm { color: #da552f; font-weight: 700; }
    footer { text-align: center; font-size: 12px; color: #bbb; margin-top: 48px; }
    footer a { color: #bbb; }
"""

def build_html(date_str: str, products: list[dict]) -> str:
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    date_cn = dt.strftime("%-Y年%-m月%-d日")

    featured = [p for p in products if p["featured"]][:12]
    others   = [p for p in products if not p["featured"] or p["rank"] > 12][:8]

    cards = "\n".join(card_html(p) for p in featured)
    rows  = "\n".join(table_row(p) for p in others) if others else ""
    others_section = f"""
  <div class="section-title">值得关注</div>
  <table>
    <thead><tr><th>产品</th><th>票数</th><th>一句话</th></tr></thead>
    <tbody>
{rows}
    </tbody>
  </table>""" if others else ""

    top_name = featured[0]["name"] if featured else ""
    top_votes = featured[0]["votes"] if featured else 0

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Product Hunt 早报 · {date_cn}</title>
  <style>{CSS}</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div class="logo">Product<span>Hunt</span> 早报</div>
    <div class="date">{date_cn} · Top Products Launching Today</div>
    <h1>今日精选 {len(featured)} 款产品</h1>
  </div>

  <div class="section-title">今日榜单</div>
{cards}
{others_section}

  <footer>
    数据来源：Product Hunt · <a href="https://decohack.com">decohack.com</a>
    &nbsp;·&nbsp; 生成于 {datetime.now().strftime("%Y-%m-%d")}
  </footer>
</div>
</body>
</html>"""

# ── index.html 更新 ───────────────────────────────────────────────────────────

def update_index(entries: list[dict]):
    """按日期倒序更新 index.html，entries = [{date, filename, top3}]"""
    entries.sort(key=lambda x: x["date"], reverse=True)

    rows = ""
    for en in entries:
        dt = datetime.strptime(en["date"], "%Y-%m-%d")
        month_day = dt.strftime("%m · %d")
        date_cn = dt.strftime("%-Y年%-m月%-d日")
        top3 = en.get("top3", "")
        rows += f"""    <a class="entry" href="{en['filename']}">
      <div class="entry-date">{month_day}</div>
      <div class="entry-info">
        <div class="entry-title">{date_cn}</div>
        <div class="entry-sub">{e(top3)}</div>
      </div>
      <div class="entry-arrow">›</div>
    </a>\n"""

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Product Hunt 早报</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", sans-serif;
      background: #f5f5f0; color: #1a1a1a;
      padding: 48px 16px 80px; line-height: 1.6;
    }}
    .container {{ max-width: 600px; margin: 0 auto; }}
    .header {{ text-align: center; margin-bottom: 48px; }}
    .logo {{ font-size: 32px; font-weight: 800; color: #da552f; letter-spacing: -0.5px; }}
    .logo span {{ color: #1a1a1a; }}
    .subtitle {{ font-size: 14px; color: #888; margin-top: 8px; }}
    .section-title {{
      font-size: 12px; font-weight: 700; text-transform: uppercase;
      letter-spacing: 1.5px; color: #999; margin-bottom: 14px;
      padding-bottom: 8px; border-bottom: 1px solid #e5e5e0;
    }}
    .list {{ display: flex; flex-direction: column; gap: 10px; }}
    .entry {{
      display: flex; align-items: center; gap: 16px;
      background: #fff; border: 1px solid #eee; border-radius: 12px;
      padding: 16px 20px; text-decoration: none; color: inherit;
      transition: box-shadow 0.15s;
    }}
    .entry:hover {{ box-shadow: 0 4px 16px rgba(0,0,0,0.08); }}
    .entry-date {{ font-size: 13px; font-weight: 700; color: #da552f; white-space: nowrap; }}
    .entry-info {{ flex: 1; }}
    .entry-title {{ font-size: 15px; font-weight: 700; color: #1a1a1a; }}
    .entry-sub {{ font-size: 12.5px; color: #888; margin-top: 2px; }}
    .entry-arrow {{ font-size: 16px; color: #ccc; }}
    footer {{ text-align: center; font-size: 12px; color: #bbb; margin-top: 48px; }}
    footer a {{ color: #bbb; }}
  </style>
</head>
<body>
<div class="container">
  <div class="header">
    <div class="logo">Product<span>Hunt</span> 早报</div>
    <div class="subtitle">每日追踪 Product Hunt 热榜 · 中文速读</div>
  </div>
  <div class="section-title">归档</div>
  <div class="list">
{rows}  </div>
  <footer>数据来源：Product Hunt · <a href="https://decohack.com">decohack.com</a></footer>
</div>
</body>
</html>"""

    path = os.path.join(ROOT, "index.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  ✓ index.html 已更新（{len(entries)} 条归档）")

# ── 扫描现有归档 ──────────────────────────────────────────────────────────────

def scan_existing() -> list[dict]:
    """扫描 ROOT 下已有的 ph_daily_YYYYMMDD.html 文件"""
    entries = []
    for fname in os.listdir(ROOT):
        m = re.match(r"ph_daily_(\d{4})(\d{2})(\d{2})\.html$", fname)
        if m:
            date_str = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
            # 尝试从文件中抽取 top3 产品名
            path = os.path.join(ROOT, fname)
            top3 = extract_top3(path)
            entries.append({"date": date_str, "filename": fname, "top3": top3})
    return entries

def extract_top3(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            content = f.read()
        names = re.findall(r'class="card-name">([^<]+)<', content)
        return " · ".join(names[:3]) + ("…" if len(names) > 3 else "")
    except Exception:
        return ""

# ── Git 操作 ──────────────────────────────────────────────────────────────────

def git_push(date_str: str, filename: str):
    cmds = [
        ["git", "-C", ROOT, "add", filename, "index.html"],
        ["git", "-C", ROOT, "commit", "-m", f"feat: Product Hunt 早报 {date_str}"],
        ["git", "-C", ROOT, "push"],
    ]
    for cmd in cmds:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  ✗ {' '.join(cmd)}\n{result.stderr.strip()}")
            return False
        print(f"  ✓ {' '.join(cmd[2:])}")
    return True

# ── 主流程 ────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) > 1:
        date_str = sys.argv[1]
    else:
        # 默认取昨天（PH 北京时间当天=美国前一天发布）
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        date_str = yesterday.strftime("%Y-%m-%d")

    print(f"\n📅 生成 {date_str} 早报")

    filename = f"ph_daily_{date_str.replace('-', '')}.html"
    out_path = os.path.join(ROOT, filename)

    if os.path.exists(out_path):
        print(f"  ℹ {filename} 已存在，跳过抓取")
    else:
        # 1. 抓取
        html_raw = fetch(date_str)
        text = strip_tags(html_raw)

        # 2. 解析
        products = parse_products(text)
        if not products:
            raise SystemExit("  ✗ 未解析到任何产品，请检查 decohack 页面是否已更新")
        print(f"  ✓ 解析到 {len(products)} 款产品")

        # 3. 生成 HTML
        page = build_html(date_str, products)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(page)
        print(f"  ✓ 生成 {filename}")

    # 4. 更新 index.html
    entries = scan_existing()
    update_index(entries)

    # 5. 提交并推送
    print("  Git push...")
    ok = git_push(date_str, filename)
    if ok:
        print(f"\n✅ 发布完成 → https://hank-open.github.io/ph-daily/\n")
    else:
        print("\n⚠️  HTML 已生成但 push 失败，请手动执行 git push\n")

if __name__ == "__main__":
    main()
