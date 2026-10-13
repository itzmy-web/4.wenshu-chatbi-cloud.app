import os

# 清理代理环境变量：WorkBuddy 沙箱/本机可能注入 HTTP(S)_PROXY，
# 会导致 langchain 底层 httpx 走代理连不上 LLM 端点（Connection error）
for _k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
    os.environ.pop(_k, None)

from langchain.chat_models import init_chat_model
from app.conf.app_config import app_config

# 构建langchain模型对象
llm = init_chat_model(
    model=app_config.llm.model_name,
    api_key=app_config.llm.api_key,
    base_url=app_config.llm.base_url,
    temperature=0)