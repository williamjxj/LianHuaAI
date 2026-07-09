import os
from zai import ZhipuAiClient
from dotenv import load_dotenv

load_dotenv()

api_key=os.getenv('ZHIPU_API_KEY')

client = ZhipuAiClient(api_key=api_key)  # 请填写您自己的 API Key

response = client.chat.completions.create(
    model="glm-5.2",
    messages=[
        {"role": "system", "content": "你是一名资深的全栈软件工程师，擅长前端开发、后端架构设计以及现代 Web 技术栈"},
        {"role": "user", "content": "帮我设计并编写一个个人博客网站，包含首页、文章列表、文章详情页，使用 React + Node.js 技术栈"}
    ],
    thinking={
        "type": "enabled"    # 启用深度思考模式
    },
    reasoning_effort="max",  # 推理程度
    max_tokens=65536,          # 最大输出 tokens
    temperature=1.0           # 控制输出的随机性
)

# 获取完整回复
print(response.choices[0].message)