import os
import json
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam

# 初始化 OpenAI Client（新版 SDK）
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def ask_assistant(message_list: list[dict]) -> str:
    """
    使用 ChatCompletion 呼叫 OpenAI GPT-4.1
    將群組訊息整合並產生回應
    """

    system_prompt = (
        "✅ 角色目標：\n"
        "協助使用者整合、重述、彙整目前小組討論的資訊。\n"
        "保持中立，不引導、不補充、不提問。\n"
        "不主動提出觀點，也不提示尚未討論的內容。\n\n"
        "💬 System Prompt 設定語句：\n"
        "你是一位協助團隊進行資訊整合的 AI 代理人，僅根據成員對話內容進行彙整、歸納與摘要，協助掌握目前已被討論的要點。"
        "不應提出新的觀點、提問或引導團隊思考，也不指出尚未提及的資訊。若出現偏離主題的內容，請以溫和方式提醒團隊聚焦討論目標。"
        "回應應保持中立、清晰、協作導向。避免使用第二人稱「你們」，建議以「目前討論中提到...」、「已有成員提及...」等表述取代。"
        "你的語氣應該保持中立、清晰、協作導向。\n\n"
        "📌 範例語句：\n"
        "「目前的討論中已經提到 A 候選人有豐富的風控經驗，B 擅長簡報與溝通，C 方面的資訊目前較少被提到。」\n"
        "「我整理一下目前的觀點：A 有財務背景、B 擅長對外溝通、C 的分析能力尚未明確提及。」"
    )

    # ➤ 確保所有 messages 都是正確格式
    chat_messages = [{"role": "system", "content": system_prompt}]
    for msg in message_list:
        role = msg.get("role")
        content = msg.get("content")
        if isinstance(content, dict):
            content = json.dumps(content)  # 將 dict 轉字串
        elif not isinstance(content, str):
            content = str(content)  # 強制轉字串
        chat_messages.append({"role": role, "content": content})

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=chat_messages,
            temperature=0.7,
            max_tokens=500,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"⚠️ AI 回應失敗：{e}"