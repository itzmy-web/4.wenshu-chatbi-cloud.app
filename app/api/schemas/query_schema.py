#导入pydantic的BaseModel基类，用于定义数据验证模型
from pydantic import BaseModel

# 定义查询请求的数据模型（用于接口入参校验）
class QuerySchema(BaseModel):
    # 接收用户输入的查询字符串，会自动校验字段类型和非空
    query: str
    # 多轮追问的会话历史（近几轮）：[{question, sql, result_summary}]，首轮可缺省
    history: list[dict] = []