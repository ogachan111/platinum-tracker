import smtplib
import os
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

def get_platinum_data():
    """index.htmlから最新の価格データを取得"""
    with open("index.html", "r", encoding="utf-8") as f:
        html = f.read()

    retail = re.search(r'retail:\s*(\d+)', html)
    buy = re.search(r'buy:\s*(\d+)', html)
    retail_diff = re.search(r'retailDiff:\s*(-?\d+)', html)
    published = re.search(r'publishedAt:\s*"([^"]+)"', html)

    return {
        "retail": int(retail.group(1)) if retail else 0,
        "buy": int(buy.group(1)) if buy else 0,
        "retailDiff": int(retail_diff.group(1)) if retail_diff else 0,
        "publishedAt": published.group(1) if published else "不明"
    }

def send_email(data):
    gmail_user = os.environ.get("GMAIL_USER")
    gmail_password = os.environ.get("GMAIL_APP_PASSWORD")
    notify_email = os.environ.get("NOTIFY_EMAIL")

    if not all([gmail_user, gmail_password, notify_email]):
        print("⚠️ 環境変数が設定されていません")
        return

    diff = data["retailDiff"]
    diff_str = f"+{diff:,}" if diff >= 0 else f"{diff:,}"
    diff_mark = "▲" if diff > 0 else "▼" if diff < 0 else "－"
    diff_color = "#4ECDC4" if diff > 0 else "#FF6B6B" if diff < 0 else "#888"

    subject = f"【プラチナ相場】{data['publishedAt']} ¥{data['retail']:,}/g ({diff_mark}{abs(diff):,}円)"

    html_body = f"""
    <html>
    <body style="font-family: sans-serif; background: #f5f5f5; padding: 20px;">
        <div style="max-width: 480px; margin: 0 auto; background: #fff; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
            <div style="background: #070B17; padding: 20px; text-align: center;">
                <h1 style="color: #4ECDC4; margin: 0; font-size: 22px;">プラチナ価格相場</h1>
                <p style="color: #6B7FA3; margin: 4px 0 0; font-size: 12px;">田中貴金属工業 {data['publishedAt']} 公表</p>
            </div>
            <div style="padding: 24px;">
                <div style="text-align: center; margin-bottom: 20px;">
                    <p style="color: #888; font-size: 12px; margin: 0 0 4px;">店頭小売価格（税込）</p>
                    <p style="font-size: 42px; font-weight: bold; color: #111; margin: 0;">¥{data['retail']:,}<span style="font-size:16px; color:#888;">/g</span></p>
                    <p style="font-size: 16px; color: {diff_color}; margin: 8px 0 0;">{diff_mark} 前日比 {diff_str} 円</p>
                </div>
                <hr style="border: none; border-top: 1px solid #eee; margin: 16px 0;">
                <div style="display: flex; justify-content: space-between;">
                    <div style="text-align: center; flex: 1;">
                        <p style="color: #888; font-size: 11px; margin: 0 0 4px;">店頭買取価格</p>
                        <p style="font-size: 18px; font-weight: bold; color: #111; margin: 0;">¥{data['buy']:,}/g</p>
                    </div>
                    <div style="text-align: center; flex: 1;">
                        <p style="color: #888; font-size: 11px; margin: 0 0 4px;">売買差額</p>
                        <p style="font-size: 18px; font-weight: bold; color: #111; margin: 0;">{data['retail'] - data['buy']:,} 円</p>
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

if __name__ == "__main__":
    print("メール通知を送信中...")
    data = get_platinum_data()
    print(f"価格データ: 小売¥{data['retail']:,}, 買取¥{data['buy']:,}, 前日比{data['retailDiff']:+,}円")
    send_email(data)
