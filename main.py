from flask import Flask, request
from linebot import LineBotApi, WebhookParser
from linebot.models import MessageEvent, TextMessage, TextSendMessage, SourceGroup, SourceRoom
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import os
import json

from prompt import ask_assistant  # ✅ 使用 ChatCompletion 的 ask_assistant 函式

app = Flask(__name__)

# ====== Firebase 初始化 ======
def get_firebase_credentials_from_env():
    firebase_credentials = os.getenv("FIREBASE_CREDENTIALS")
    service_account_info = json.loads(firebase_credentials)
    print("✅ 成功從環境變數讀取 Firebase 金鑰")
    return credentials.Certificate(service_account_info)

firebase_cred = get_firebase_credentials_from_env()
firebase_admin.initialize_app(firebase_cred)
db = firestore.client()

# ====== LINE Bot 初始化 ======
line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
parser = WebhookParser(os.getenv("LINE_CHANNEL_SECRET"))

# ====== Webhook 路由入口 ======
@app.route("/callback", methods=["POST"])
def webhook():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)
    events = parser.parse(body, signature)

    for event in events:
        if isinstance(event, MessageEvent) and isinstance(event.message, TextMessage):
            # 取得來源 ID
            if isinstance(event.source, SourceGroup):
                source_id = event.source.group_id
            elif isinstance(event.source, SourceRoom):
                source_id = event.source.room_id
            else:
                source_id = event.source.user_id

            user_id = event.source.user_id
            msg_text = event.message.text
            timestamp = datetime.now().isoformat()

            # 儲存使用者訊息
            db.collection("groups").document(source_id).collection("messages").add({
                "user_id": user_id,
                "text": msg_text,
                "timestamp": timestamp,
                "from": "user"
            })

            # 讀取最近 20 筆訊息
            history_ref = db.collection("groups").document(source_id).collection("messages")
            docs = list(history_ref.order_by("timestamp", direction=firestore.Query.DESCENDING).limit(20).stream())
            docs_reversed = list(reversed(docs))

            # 取得所有使用者訊息與不同使用者 ID
            user_msgs = [doc for doc in docs_reversed if doc.to_dict().get("from") == "user"]
            user_ids = set(doc.to_dict().get("user_id") for doc in user_msgs)

            # 條件：至少三則使用者訊息，且來自三位不同使用者
            # 先測試兩個
            if len(user_msgs) >= 2 and len(user_ids) >= 2:
                # 將訊息轉換成 ChatCompletion 格式
                messages = []
                for doc in docs_reversed:
                    data = doc.to_dict()
                    role = "user" if data.get("from") == "user" else "assistant"
                    user = data.get("user_id", "unknown")
                    text = data.get("text", "")

                    # 確保 content 是字串
                    content = f"{user}: {text}" if isinstance(text, str) else str(text)
                    messages.append({"role": role, "content": content})

                try:
                    reply = ask_assistant(messages)

                    # 儲存 AI 回覆
                    db.collection("groups").document(source_id).collection("messages").add({
                        "user_id": "sumi_AI",  # 可換成 nomi_AI 等
                        "text": reply,
                        "timestamp": datetime.now().isoformat(),
                        "from": "assistant"
                    })

                    # 回覆到 LINE
                    line_bot_api.reply_message(
                        event.reply_token,
                        TextSendMessage(text=reply)
                    )

                except Exception as e:
                    print(f"❌ AI 回應失敗：{e}")
                    line_bot_api.reply_message(
                        event.reply_token,
                        TextSendMessage(text="⚠️ AI 回應失敗，請稍後再試。")
                    )

    return "OK"

# ====== 啟動伺服器 ======
if __name__ == "__main__":
    port = int(os.getenv('PORT', 8080))
    print(f"🚀 應用程式啟動中，監聽埠號 {port}...")
    app.run(host='0.0.0.0', port=port)
