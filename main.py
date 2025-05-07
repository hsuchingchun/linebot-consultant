from flask import Flask, request
from linebot import LineBotApi, WebhookParser
from linebot.models import MessageEvent, TextMessage, TextSendMessage, SourceGroup, SourceRoom
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import os
import json

from prompt import Prompt  # 顧問型 AI prompt 處理

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

# LINE bot 設定
line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
parser = WebhookParser(os.getenv("LINE_CHANNEL_SECRET"))

#route 為 Line Webhook 接 GCP 網址後面要加的 /callback (可自己設定)
@app.route("/callback", methods=["POST"])
def webhook():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)
    events = parser.parse(body, signature)

    for event in events:
        if isinstance(event, MessageEvent) and isinstance(event.message, TextMessage):
            # 判斷對話來源：群組 / 聊天室 / 一對一
            if isinstance(event.source, SourceGroup):
                source_id = event.source.group_id
            elif isinstance(event.source, SourceRoom):
                source_id = event.source.room_id
            else:
                source_id = event.source.user_id  # 一對一私訊

            user_id = event.source.user_id
            msg_text = event.message.text
            timestamp = datetime.now().isoformat()

            # 儲存 Firestore（按來源 ID 分類）
            db.collection("groups").document(source_id).collection("messages").add({
                "user_id": user_id,
                "text": msg_text,
                "timestamp": timestamp
            })

            # 取得最近 20 則訊息 & 產生 AI 回覆
            history_ref = db.collection("groups").document(source_id).collection("messages")
            docs = history_ref.order_by("timestamp", direction=firestore.Query.DESCENDING).limit(20).stream()
            messages = [f"{doc.to_dict()['user_id']}:{doc.to_dict()['text']}" for doc in reversed(list(docs))]

            prompt = Prompt()
            prompt.msg_list = messages
            reply = prompt.generate_prompt()  # 顧問型 AI 回覆

            # LINE 回覆
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=reply)
            )

    return "OK"
