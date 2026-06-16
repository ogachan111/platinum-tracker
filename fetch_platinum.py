import requests
from bs4 import BeautifulSoup
import re
import json
from datetime import datetime
import os

def fetch_tanaka_data():
    url = "https://gold.tanaka.co.jp/commodity/souba/d-platinum.php"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    res = requests.get(url, headers=headers, timeout=15)
    res.encoding = "utf-8"
    soup = BeautifulSoup(res.text, "html.parser")

    data = {
        "retail": None,
        "buy": None,
        "retailDiff": None,
        "buyDiff": None,
        "publishedAt": None,
        "history": []
    }

    # 価格テーブルを取得
    tables = soup.find_all("table")
    for table in tables:
        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all(["td", "th"])
            texts = [c.get_text(strip=True) for c in cells]

            # 公表日時を探す
            for t in texts:
                if re.search(r'\d{4}年\d{1,2}月\d{1,2}日', t):
                    data["publishedAt"] = t
                    break

            # 価格行を探す（数字4〜5桁がある行）
            prices = []
            for t in texts:
                t_clean = t.replace(",", "").replace("円", "").replace("−", "").replace("-", "")
                if re.match(r'^\d{4,6}$', t_clean):
                    prices.append(int(t_clean))

            if len(prices) >= 2 and prices[0] > 5000:
                if data["retail"] is None:
                    data["retail"] = prices[0]
                    data["buy"] = prices[1]

    # 前日比を探す
    text_all = soup.get_text()
    diff_matches = re.findall(r'[前日比差分]*([+\-−]?\d{1,4})円', text_all)
    diffs = []
    for m in diff_matches:
        try:
            v = int(m.replace("−", "-").replace("+", ""))
            if abs(v) < 2000:
                diffs.append(v)
        except:
            pass
    if len(diffs) >= 2:
        data["retailDiff"] = diffs[0]
        data["buyDiff"] = diffs[1]
    elif len(diffs) == 1:
        data["retailDiff"] = diffs[0]
        data["buyDiff"] = diffs[0]

    # 履歴テーブルを取得
    for table in tables:
        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all(["td", "th"])
            texts = [c.get_text(strip=True) for c in cells]
            date_str = None
            retail_val = None
            buy_val = None

            for t in texts:
                # 日付パターン
                m = re.search(r'(\d{4})[/年](\d{1,2})[/月](\d{1,2})', t)
                if m:
                    date_str = f"{m.group(1)}/{int(m.group(2)):02d}/{int(m.group(3)):02d}"

            prices = []
            for t in texts:
                t_clean = t.replace(",", "").replace("円", "")
                if re.match(r'^\d{4,6}$', t_clean):
                    prices.append(int(t_clean))

            if date_str and len(prices) >= 1:
                retail_val = prices[0]
                buy_val = prices[1] if len(prices) >= 2 else None
                data["history"].append({
                    "date": date_str,
                    "retail": retail_val,
                    "buy": buy_val
                })

    # 公表日時の整形
    if not data["publishedAt"]:
        data["publishedAt"] = datetime.now().strftime("%Y/%m/%d 09:30")

    return data

def update_html(data):
    with open("index.html", "r", encoding="utf-8") as f:
        html = f.read()

    # TANAKA_DATAブロックを置き換え
    history_json = json.dumps(data["history"], ensure_ascii=False)
    new_data_block = f"""const TANAKA_DATA = {{
  retail: {data['retail'] or 0},
  buy: {data['buy'] or 0},
  retailDiff: {data['retailDiff'] or 0},
  buyDiff: {data['buyDiff'] or 0},
  publishedAt: "{data['publishedAt']}",
  history: {history_json}
}};"""

    # 正規表現でTANAKA_DATAブロックを置き換え
    pattern = r'const TANAKA_DATA = \{[\s\S]*?\};'
    new_html = re.sub(pattern, new_data_block, html, count=1)

    # フッターの最終取得日時を更新
    now_str = datetime.now().strftime("%Y年%m月%d日 %H:%M")
    new_html = re.sub(
        r'最終取得: .+? by Claude',
        f'最終取得: {now_str} (自動更新)',
        new_html
    )

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(new_html)

    print(f"✅ 更新完了: 小売 ¥{data['retail']:,}/g, 買取 ¥{data['buy']:,}/g ({data['publishedAt']})")

if __name__ == "__main__":
    print("田中貴金属 プラチナ価格を取得中...")
    data = fetch_tanaka_data()
    print(f"取得データ: {data['retail']} / {data['buy']} ({data['publishedAt']})")
    update_html(data)
