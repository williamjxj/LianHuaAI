import os
from dotenv import load_dotenv
from openai import OpenAI

# 加载 .env 环境变量
load_dotenv()

client = OpenAI(
    api_key=os.getenv("DASHSCOPE_API_KEY"),  # openai 库也接受非 OpenAI 的 key
    base_url=os.getenv("OPENAI_COMPATIBLE_BASE_URL"),
)
completion = client.chat.completions.create(
    model="qwen3.7-plus",
    messages=[{'role': 'user', 'content': '你是谁？'}]
)
print(completion.choices[0].message.content)