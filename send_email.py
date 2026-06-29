import smtplib
import os
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

DATA_FILE = "data.json"


def load_data():
    """data.json を読む。読めない場合は None。"""
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️ data.json が読めません: {e}")
        return None


def _smtp_send(subject, html_body):
    gmail_user = os.environ.get("GMAIL_USER")
    gmail_password = os.environ.get("GMAIL_APP_PASSWORD")
    notify_email = os.environ.get("NOTIFY_EMAIL")

    if not all([gmail_user, gmail_password, notify_email]):
        print("⚠️ 環境変数が設定されていません")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = gmail_user
    msg["To"] = notify_email
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(gmail_user, gmail_password)
            server.sendmail(gmail_user, notify_email, msg.as_string())
        print(f"✅ メール送信完了 → {notify_email}")
        print(f"   件名: {subject}")
    except Exception as e:
        print(f"❌ メール送信失敗: {e}")


def send_alert_email(reason, last_checked):
    """取得失敗時の警告メール。誤った価格を送らず、異常そのものを知らせる。"""
    subject = "⚠️【プラチナ相場】価格の自動取得に失敗しました"
    html_body = f"""
    <html>
    <body style="font-family: sans-serif; background: #f5f5f5; padding: 20px;">
        <div style="max-width: 480px; margin: 0 auto; background: #fff; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
            <div style="background: #3a1414; padding: 20px; text-align: center;">
                <h1 style="color: #FF6B6B; margin: 0; font-size: 20px;">⚠️ 価格の自動取得に失敗</h1>
                <p style="color: #c98; margin: 6px 0 0; font-size: 12px;">プラチナ価格相場 自動更新</p>
            </div>
            <div style="padding: 24px; color:#333;">
                <p style="font-size:14px; line-height:1.7; margin:0 0 14px;">
                    田中貴金属からの価格取得に失敗したため、今回はメールでの価格通知を見送りました。<br>
                    アプリの表示は<strong>前回取得分</strong>のままになっています。
                </p>
                <div style="background:#f6f6f6; border-radius:8px; padding:12px 14px; font-size:12px; color:#666; line-height:1.8;">
                    <div>原因: {reason}</div>
                    <div>最終確認: {last_checked}</div>
                </div>
                <p style="font-size:12px; color:#888; line-height:1.7; margin:16px 0 0;">
                    田中貴金属のサイト構造が変わった可能性があります。
                    数日続く場合は <code>fetch_platinum.py</code> の見直しが必要です。
                </p>
                <div style="text-align: center; margin-top: 20px;">
                    <a href="https://ogachan111.github.io/platinum-tracker/"
                       style="background: #4ECDC4; color: #fff; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: bold;">
                        アプリを開く
                    </a>
                </div>
            </div>
            <div style="background: #f9f9f9; padding: 12px; text-align: center;">
                <p style="color: #aaa; font-size: 10px; margin: 0;">データ出典: 田中貴金属工業株式会社</p>
            </div>
        </div>
    </body>
    </html>
    """
    _smtp_send(subject, html_body)


def send_price_email(data):
    """通常の価格通知メール（従来デザインを踏襲）。"""
    retail = data["retail"]
    buy = data["buy"]
    diff = data.get("retailDiff", 0)
    published = data.get("publishedAt", "不明")

    diff_str = f"+{diff:,}" if diff >= 0 else f"{diff:,}"
    diff_mark = "▲" if diff > 0 else "▼" if diff < 0 else "－"
    diff_color = "#4ECDC4" if diff > 0 else "#FF6B6B" if diff < 0 else "#888"

    subject = f"【プラチナ相場】{published} ¥{retail:,}/g ({diff_mark}{abs(diff):,}円)"

    html_body = f"""
    <html>
    <body style="font-family: sans-serif; background: #f5f5f5; padding: 20px;">
        <div style="max-width: 480px; margin: 0 auto; background: #fff; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
            <div style="background: #070B17; padding: 20px; text-align: center;">
                <h1 style="color: #4ECDC4; margin: 0; font-size: 22px;">プラチナ価格相場</h1>
                <p style="color: #6B7FA3; margin: 4px 0 0; font-size: 12px;">田中貴金属工業 {published} 公表</p>
            </div>
            <div style="padding: 24px;">
                <div style="text-align: center; margin-bottom: 20px;">
                    <p style="color: #888; font-size: 12px; margin: 0 0 4px;">店頭小売価格（税込）</p>
                    <p style="font-size: 42px; font-weight: bold; color: #111; margin: 0;">¥{retail:,}<span style="font-size:16px; color:#888;">/g</span></p>
                    <p style="font-size: 16px; color: {diff_color}; margin: 8px 0 0;">{diff_mark} 前日比 {diff_str} 円</p>
                </div>
                <hr style="border: none; border-top: 1px solid #eee; margin: 16px 0;">
                <div style="display: flex; justify-content: space-between;">
                    <div style="text-align: center; flex: 1;">
                        <p style="color: #888; font-size: 11px; margin: 0 0 4px;">店頭買取価格</p>
                        <p style="font-size: 18px; font-weight: bold; color: #111; margin: 0;">¥{buy:,}/g</p>
                    </div>
                    <div style="text-align: center; flex: 1;">
                        <p style="color: #888; font-size: 11px; margin: 0 0 4px;">売買差額</p>
                        <p style="font-size: 18px; font-weight: bold; color: #111; margin: 0;">{retail - buy:,} 円</p>
                    </div>
                </div>
                <div style="text-align: center; margin-top: 20px;">
                    <a href="https://ogachan111.github.io/platinum-tracker/"
                       style="background: #4ECDC4; color: #fff; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: bold;">
                        アプリで詳細を見る
                    </a>
                </div>
            </div>
            <div style="background: #f9f9f9; padding: 12px; text-align: center;">
                <p style="color: #aaa; font-size: 10px; margin: 0;">データ出典: 田中貴金属工業株式会社</p>
            </div>
        </div>
    </body>
    </html>
    """
    _smtp_send(subject, html_body)


def _price_ok(data):
    r, b = data.get("retail"), data.get("buy")
    return isinstance(r, int) and 3000 <= r <= 60000 and isinstance(b, int) and 3000 <= b <= 60000


if __name__ == "__main__":
    print("メール通知を送信中...")
    data = load_data()

    if data is None:
        send_alert_email("data.json が読み込めませんでした", "不明")
    elif data.get("status") == "error" or not _price_ok(data):
        reason = data.get("error") or "取得値が妥当ではありません"
        send_alert_email(reason, data.get("lastChecked", "不明"))
    else:
        print(f"価格データ: 小売¥{data['retail']:,}, 買取¥{data['buy']:,}, 前日比{data.get('retailDiff', 0):+,}円")
        send_price_email(data)
