# 127.0.0.1/api/query
from fastapi import APIRouter
from fastapi.params import Depends
from starlette.responses import StreamingResponse

from app.api.dependencies import get_query_service
from app.api.routers.auth_router import verify_token
from app.api.schemas.query_schema import QuerySchema
from app.services.query_service import QueryService

query_router = APIRouter()


# 定义POST接口/api/query（需登录后携带 X-Token 请求头）
@query_router.post("/api/query")
async def query(query: QuerySchema,
                query_service: QueryService = Depends(get_query_service),
                _token: None = Depends(verify_token)):
    # 调用服务处理查询，返回SSE流式响应（携带会话历史用于多轮追问）
    return StreamingResponse(query_service.query(query.query, query.history), media_type="text/event-stream")
