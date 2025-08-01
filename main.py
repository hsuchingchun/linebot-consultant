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
@app.route("/callback", methods=["POST"])
def webhook():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)
    events = parser.parse(body, signature)

    for event in events:
        if isinstance(event, MessageEvent) and isinstance(event.message, TextMessage):
            if isinstance(event.source, SourceGroup):
                source_id = event.source.group_id
            elif isinstance(event.source, SourceRoom):
                source_id = event.source.room_id
            else:
                source_id = event.source.user_id

            user_id = event.source.user_id
            msg_text = event.message.text
            timestamp = datetime.now().isoformat()

            # 先把使用者訊息寫入正式「messages」集合
            db.collection("groups").document(source_id).collection("messages").add({
                "user_id": user_id,
                "text": msg_text,
                "timestamp": timestamp,
                "from": "user"
            })

            # 讀取並更新「暫存區」(暫存兩則 user 訊息，key: source_id)
            temp_ref = db.collection("groups").document(source_id).collection("temp").document("pending_user_msgs")
            temp_doc = temp_ref.get()
            if temp_doc.exists:
                temp_data = temp_doc.to_dict()
                pending_msgs = temp_data.get("msgs", [])
            else:
                pending_msgs = []

            # 把新訊息加進暫存
            pending_msgs.append({"role": "user", "content": msg_text})

            # 如果暫存不足兩則，先更新暫存後不回覆
            if len(pending_msgs) < 2:
                temp_ref.set({"msgs": pending_msgs})
                # 不回覆，等第二則訊息進來再回覆
                return "OK"

            # 若已累積兩則，刪除暫存，準備送 AI
            temp_ref.delete()

            # 取出最近20筆完整歷史訊息(包含使用者與 AI)
            history_ref = db.collection("groups").document(source_id).collection("messages")
            docs = list(history_ref.order_by("timestamp", direction=firestore.Query.DESCENDING).limit(20).stream())
            docs_reversed = list(reversed(docs))

            # 轉成 ChatCompletion messages 格式，包含 system prompt + 歷史
            messages = []
            for doc in docs_reversed:
                data = doc.to_dict()
                role = "user" if data.get("from") == "user" else "assistant"
                user = data.get("user_id", "unknown")
                text = data.get("text", "")

                content = f"{user}: {text}" if isinstance(text, str) else str(text)
                messages.append({"role": role, "content": content})

            # 把剛暫存的兩則訊息放到最後(避免重複，可斟酌是否要這麼做)
            # messages.extend(pending_msgs)  # 因為剛剛訊息已存 messages collection，不用重覆加

            try:
                reply = ask_assistant(messages)

                # 儲存 AI 回覆
                db.collection("groups").document(source_id).collection("messages").add({
                    "user_id": "sumi_AI",
                    "text": reply,
                    "timestamp": datetime.now().isoformat(),
                    "from": "assistant"
                })

                # 回覆 LINE
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
