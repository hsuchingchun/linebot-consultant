import os
import openai

openai.api_key = os.getenv("OPENAI_API_KEY")
assistant_id = os.getenv("ASSISTANT_ID") 

def ask_assistant(message_list: list[str]) -> str:
    """
    將群組對話列表傳給 Assistant 做資訊整合
    """

    # 1. 建立對話 thread
    thread = openai.beta.threads.create()

    # 2. 把每則訊息加入 thread
    for msg in message_list:
        openai.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=msg
        )

    # 3. 呼叫 assistant 進行 run
    run = openai.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=assistant_id
    )

    # 4. 等待 assistant 完成（同步輪詢）
    while True:
        run_status = openai.beta.threads.runs.retrieve(
            thread_id=thread.id,
            run_id=run.id,
        )
        if run_status.status == "completed":
            break
        elif run_status.status in ["failed", "cancelled", "expired"]:
            raise Exception(f"🛑 Assistant failed: {run_status.status}")

    # 5. 抓取 Assistant 的回覆
    messages = openai.beta.threads.messages.list(thread_id=thread.id)
    for message in reversed(messages.data):
        if message.role == "assistant":
            return message.content[0].text.value

    return "（目前無可用回應）"