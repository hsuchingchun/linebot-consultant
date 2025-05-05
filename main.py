from flask import Flask, request
from linebot import LineBotApi, WebhookParser
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import os

from prompt import Prompt  # 顧問型 AI prompt 處理

app = Flask(__name__)

# Firebase 初始化
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# LINE bot 設定
line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
parser = WebhookParser(os.getenv("LINE_CHANNEL_SECRET"))

@app.route("/", methods=["POST"])
def webhook():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)
    events = parser.parse(body, signature)

    for event in events:
        if isinstance(event, MessageEvent) and isinstance(event.message, TextMessage):
            group_id = event.source.group_id or event.source.user_id
            user_id = event.source.user_id
            msg_text = event.message.text
            timestamp = datetime.now().isoformat()

            # 儲存 Firestore（按群組分類）
            db.collection("groups").document(group_id).collection("messages").add({
                "user_id": user_id,
                "text": msg_text,
                "timestamp": timestamp
            })

            # 取得群組歷史 & 產生回覆
            history_ref = db.collection("groups").document(group_id).collection("messages")
            docs = history_ref.order_by("timestamp", direction=firestore.Query.DESCENDING).limit(20).stream()
            messages = [f"{doc.to_dict()['user_id']}:{doc.to_dict()['text']}" for doc in reversed(list(docs))]

            prompt = Prompt()
            prompt.msg_list = messages
            reply = prompt.generate_prompt()  # 回傳 AI 顧問型建議

            # LINE 回覆
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=reply)
            )

    return "OK"