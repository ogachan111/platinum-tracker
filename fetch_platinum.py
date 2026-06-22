import requests
from bs4 import BeautifulSoup
import re
import json
from datetime import datetime

def fetch_tanaka_data():
    url = "https://gold.tanaka.co.jp/commodity/souba/d-platinum.php"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    res = requests.get(url, headers=headers, timeout=15)
    res.encoding = "utf-8"
    soup = BeautifulSoup(res.text, "html.parser")

    data = {"retail": None, "buy": None, "retailDiff": None, "buyDiff": None, "publishedAt": None, "history": []}

    # ── 公表日時の取得（修正版）──
    # サイトの形式: "地金価格2026年06月19日 09:30公表(日本時間)"
    full_text = soup.get_text()
    m = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日\s*(\d{2}:\d{2})公表', full_text)
    if m:
        data["publishedAt"] = f"{m.group(1)}/{int(m.group(2)):02d}/{int(m.group(3)):02d} {m.group(4)}"
        print(f"✅ 公表日時取得: {data['publishedAt']}")
    else:
        # フォールバック: 実行日の09:30を使用
        data["publishedAt"] = datetime.now().strftime("%Y/%m/%d") + " 09:30"
        print(f"⚠️ 公表日時が取得できなかったためフォールバック: {data['publishedAt']}")

    tables = soup.find_all("table")

    # ── 本日の小売・買取価格と前日比を取得 ──
    for table in tables:
        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all(["td", "th"])
            texts = [c.get_text(strip=True) for c in cells]
            full = " ".join(texts)

            if "店頭小売価格" in full or "小売" in full:
                prices = re.findall(r'([\d,]+)\s*円', full)
                diffs = re.findall(r'([+\-−][\d,]+)\s*円', full)
                if prices:
                    p = int(prices[0].replace(",", ""))
                    if 5000 < p < 50000 and data["retail"] is None:
                        data["retail"] = p
                if diffs and data["retailDiff"] is None:
                    data["retailDiff"] = int(diffs[0].replace(",","").replace("−","-").replace("+",""))

            if "店頭買取価格" in full or "買取" in full:
                prices = re.findall(r'([\d,]+)\s*円', full)
                diffs = re.findall(r'([+\-−][\d,]+)\s*円', full)
                if prices:
                    p = int(prices[0].replace(",", ""))
                    if 5000 < p < 50000 and data["buy"] is None:
                        data["buy"] = p
                if diffs and data["buyDiff"] is None:
                    data["buyDiff"] = int(diffs[0].replace(",","").replace("−","-").replace("+",""))

    # ── 履歴データを取得 ──
    history_data = {}
    for table in tables:
        rows = table.find_all("tr")
        if len(rows) < 10:
            continue

        header_row = rows[0]
        headers_text = [th.get_text(strip=True) for th in header_row.find_all(["th","td"])]
        months = []
        for h in headers_text:
            m = re.search(r'(\d{4})年\s*(\d{1,2})月', h)
            if m:
                months.append((int(m.group(1)), int(m.group(2))))

        if not months:
            continue

        for row in rows[1:]:
            cells = row.find_all(["td","th"])
            if not cells:
                continue
            day_text = cells[0].get_text(strip=True).replace("日","")
            try:
                day = int(day_text)
            except:
                continue

            for i, cell in enumerate(cells[1:]):
                if i >= len(months):
                    break
                year, month = months[i]
                price_text = cell.get_text(strip=True).replace(",","").replace("円","")
                if price_text and price_text != "-" and price_text != "－":
                    try:
                        price = int(price_text)
                        if 3000 < price < 100000:
                            date_key = f"{year}/{month:02d}/{day:02d}"
                            history_data[date_key] = price
                    except:
                        pass

    sorted_dates = sorted(history_data.keys(), reverse=True)[:60]

    # ── フォールバック処理（履歴の買取値を埋める前に当日値を確定）──
    if data["retail"] is None and sorted_dates:
        data["retail"] = history_data[sorted_dates[0]]
    if data["retailDiff"] is None:
        data["retailDiff"] = 0
    if data["buyDiff"] is None:
        data["buyDiff"] = 0
    if data["buy"] is None and data["retail"]:
        data["buy"] = data["retail"] - 423

    # ── 売買差額（当日の小売-買取）。買取の履歴はサイトに無いため差額から推定 ──
    spread = (data["retail"] - data["buy"]) if (data["retail"] and data["buy"]) else 423
    data["history"] = [
        {"date": d, "retail": history_data[d], "buy": history_data[d] - spread}
        for d in sorted_dates
    ]

    return data

def update_html(data):
    with open("index.html", "r", encoding="utf-8") as f:
        html = f.read()

    history_json = json.dumps(data["history"], ensure_ascii=False)

    new_data_block = f"""const TANAKA_DATA = {{
  retail: {data['retail'] or 0},
  buy: {data['buy'] or 0},
  retailDiff: {data['retailDiff'] or 0},
  buyDiff: {data['buyDiff'] or 0},
  publishedAt: "{data['publishedAt']}",
  history: {history_json}
}};"""

    pattern = r'const TANAKA_DATA = \{[\s\S]*?\};'
    new_html = re.sub(pattern, new_data_block, html, count=1)

    now_str = datetime.now().strftime("%Y年%m月%d日 %H:%M")
    # フッターの「最終取得: …」を次のタグ直前まで置換（カッコの有無に関わらず一致）
    new_html = re.sub(r'最終取得:[^<]*', f'最終取得: {now_str} （自動更新）', new_html)

    pub_date = data['publishedAt'][:10] if data['publishedAt'] else now_str[:10]
    new_html = re.sub(r'<span class="status-label">[^<]*</span>', f'<span class="status-label">{pub_date}</span>', new_html)

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(new_html)

    print(f"✅ 更新完了: 小売 ¥{data['retail']:,}/g, 買取 ¥{data['buy']:,}/g ({data['publishedAt']})")
    print(f"   前日比: {data['retailDiff']:+d}円, 履歴件数: {len(data['history'])}件")

if __name__ == "__main__":
    print("田中貴金属 プラチナ価格を取得中...")
    data = fetch_tanaka_data()
    print(f"取得データ: 小売={data['retail']}, 買取={data['buy']}, 前日比={data['retailDiff']}, 公表={data['publishedAt']}")
    update_html(data)
