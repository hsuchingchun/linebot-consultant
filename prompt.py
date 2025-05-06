import openai
import os

openai.api_key = os.getenv("OPENAI_API_KEY")

class Prompt:
    def __init__(self):
        self.msg_list = []

    @property
    def msg_list(self):
        return self._msg_list

    @msg_list.setter
    def msg_list(self, messages):
        self._msg_list = messages

    def generate_prompt(self):
        # 將 msg_list 轉為 ChatGPT 的 messages 格式
        chat_history = [
            {"role": "system", "content": (
                "你是一位中立且有邏輯的顧問型 AI，協助團體進行決策討論。"
                "請針對目前的討論內容，給出具體建議、提醒可能忽略的要素，或提出反思性問題。"
            )}
        ]

        for msg in self.msg_list:
            # 假設格式為 user123:訊息
            if ":" in msg:
                user, content = msg.split(":", 1)
                chat_history.append({"role": "user", "content": f"{user} 說：{content}"})

        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",  # 或 gpt-4
                messages=chat_history,
                temperature=0.7,
                max_tokens=300
            )
            return response.choices[0].message.content.strip()

        except Exception as e:
            return f"⚠️ AI 回覆發生錯誤：{str(e)}"
        
