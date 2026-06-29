import requests
from bs4 import BeautifulSoup
import re
import json
import os
from datetime import datetime

DATA_FILE = "data.json"

def fetch_tanaka_data():
    url = "https://gold.tanaka.co.jp/commodity/souba/d-platinum.php"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    res = requests.get(url, headers=headers, timeout=15)
    res.encoding = "utf-8"
    soup = BeautifulSoup(res.text, "html.parser")

    data = {"retail": None, "buy": None, "retailDiff": None, "buyDiff": None, "publishedAt": None, "history": []}

    # ── 公表日時の取得 ──
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


# ──────────────────────────────────────────────────────────────
#  ここから下が今回の改修ぶん（取得本体 fetch_tanaka_data は無改造）
# ──────────────────────────────────────────────────────────────

def load_prev():
    """前回の data.json を読む（無ければ None）。取得失敗時の“前回良好データ”保持に使う。"""
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def is_valid(data):
    """スクレイプ結果が妥当か検証。1つでも外れたら「取得失敗」とみなす。"""
    if not data:
        return False, "データが None"
    r, b = data.get("retail"), data.get("buy")
    if not isinstance(r, int) or not (3000 <= r <= 60000):
        return False, f"小売価格が異常: {r}"
    if not isinstance(b, int) or not (3000 <= b <= 60000):
        return False, f"買取価格が異常: {b}"
    if not data.get("history"):
        return False, "履歴が空"
    return True, ""


def merge_buy_history(data, prev):
    """買取の過去推移を“誠実”にする。
    - 当日の買取は実値（今回スクレイプ値）。
    - 過去に実値として記録済みの日付はその実値を維持。
    - それ以外の日付は『小売 − 当日の売買差額』で推定し、buyEstimated=True を付ける。
    これにより、運用を続けるほど実値の買取履歴が積み上がっていく。
    """
    today = data["publishedAt"][:10]
    spread = data["retail"] - data["buy"]

    real = {}
    if prev and isinstance(prev.get("history"), list):
        for r in prev["history"]:
            if r.get("buyEstimated") is False and isinstance(r.get("buy"), int):
                real[r["date"]] = r["buy"]
    real[today] = data["buy"]  # 当日は必ず実値

    out = []
    for r in data["history"]:
        d = r["date"]
        if d in real:
            out.append({"date": d, "retail": r["retail"], "buy": real[d], "buyEstimated": False})
        else:
            out.append({"date": d, "retail": r["retail"], "buy": r["retail"] - spread, "buyEstimated": True})
    return out


def write_data_json(out):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    print("田中貴金属 プラチナ価格を取得中...")
    now_str = datetime.now().strftime("%Y/%m/%d %H:%M")
    prev = load_prev()

    data = None
    fetch_error = ""
    try:
        data = fetch_tanaka_data()
        print(f"取得データ: 小売={data['retail']}, 買取={data['buy']}, 前日比={data['retailDiff']}, 公表={data['publishedAt']}")
    except Exception as e:
        fetch_error = f"取得処理で例外: {e}"
        print(f"❌ {fetch_error}")

    ok, reason = is_valid(data)
    if ok:
        history = merge_buy_history(data, prev)
        real_cnt = sum(1 for h in history if not h["buyEstimated"])
        out = {
            "status": "ok",
            "error": "",
            "lastChecked": now_str,
            "retail": data["retail"],
            "buy": data["buy"],
            "retailDiff": data["retailDiff"],
            "buyDiff": data["buyDiff"],
            "publishedAt": data["publishedAt"],
            "history": history,
        }
        write_data_json(out)
        print(f"✅ data.json 更新: 小売 ¥{data['retail']:,}/g, 買取 ¥{data['buy']:,}/g ({data['publishedAt']})")
        print(f"   前日比: {data['retailDiff']:+d}円, 履歴 {len(history)}件（うち買取実値 {real_cnt}件）")
    else:
        # 取得失敗：前回の良好データを保持しつつ status=error にする（画面は前回値を表示、メールは警告）
        msg = fetch_error or f"取得値が妥当でない（{reason}）"
        base = prev if prev else {
            "retail": 0, "buy": 0, "retailDiff": 0, "buyDiff": 0,
            "publishedAt": "不明", "history": []
        }
        out = dict(base)
        out["status"] = "error"
        out["error"] = msg
        out["lastChecked"] = now_str
        write_data_json(out)
        print(f"⚠️ 取得失敗のため status=error で記録: {msg}")
        print("   （価格・履歴は前回取得分を保持しました）")
