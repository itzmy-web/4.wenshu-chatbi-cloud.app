# 登录鉴权路由：
#   POST /api/login      账号密码登录（admin 配置）
#   POST /api/send_code  发送手机验证码（演示模式：未接短信通道，验证码回显）
#   POST /api/login_code 手机验证码登录
# verify_token 校验 X-Token 请求头
import re
import secrets
import time
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.params import Depends, Header
from pydantic import BaseModel

from app.conf.app_config import app_config
from app.core.log import logger

auth_router = APIRouter()

# 会话令牌：由登录配置（用户名+密码）派生的固定值
# 历史教训：早期版本 token 只存内存（重启即换）→ 看板页 5 分钟自动刷新 401 被踢回登录页；
# 改为文件持久化后在发布沙箱里仍不可靠（沙箱重启可能重置文件）。
# 现按配置派生：只要账号密码不变，重启 / 重新发布 / 多实例 token 恒定，浏览器会话永不失效。
import hashlib

def _load_or_create_token() -> str:
    auth = app_config.auth
    basis = f"wenshu::chatbi::{auth.username}::{auth.password}"
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:32]


_session_token: str = _load_or_create_token()

# 验证码存储：phone -> (code, 过期时间戳)；_last_send: phone -> 上次发送时间（60 秒限频）
_code_store: dict[str, tuple[str, float]] = {}
_last_send: dict[str, float] = {}
_CODE_TTL = 300      # 验证码 5 分钟有效
_SEND_INTERVAL = 60  # 同一手机号 60 秒限频


class LoginSchema(BaseModel):
    username: str
    password: str


class PhoneSchema(BaseModel):
    phone: str


class CodeLoginSchema(BaseModel):
    phone: str
    code: str


@auth_router.post("/api/login")
async def login(body: LoginSchema):
    """校验账号密码，成功则返回会话 token"""
    auth = app_config.auth
    if not auth.enable:
        return {"token": "disabled"}
    if body.username != auth.username or body.password != auth.password:
        logger.warning(f"登录失败：用户名 {body.username}")
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    logger.info(f"登录成功：用户名 {body.username}")
    return {"token": _session_token}


@auth_router.post("/api/send_code")
async def send_code(body: PhoneSchema):
    """生成并"发送"手机验证码。演示模式未接短信通道，验证码直接回显给前端"""
    phone = body.phone.strip()
    if not re.fullmatch(r"1[3-9]\d{9}", phone):
        raise HTTPException(status_code=400, detail="请输入正确的 11 位手机号")
    now = time.time()
    if now - _last_send.get(phone, 0) < _SEND_INTERVAL:
        raise HTTPException(status_code=429, detail="发送太频繁，请稍后再试")
    code = f"{secrets.randbelow(1000000):06d}"
    _code_store[phone] = (code, now + _CODE_TTL)
    _last_send[phone] = now
    logger.info(f"发送验证码：{phone} -> {code}（{_CODE_TTL // 60} 分钟内有效）")
    # TODO 接入真实短信通道（如腾讯云 SMS）后，把 demo_code 换成短信下发
    return {"ok": True, "demo_code": code,
            "message": f"演示模式：验证码 {code}（{_CODE_TTL // 60} 分钟内有效，未接入短信通道）"}


@auth_router.post("/api/login_code")
async def login_code(body: CodeLoginSchema):
    """校验手机验证码，成功则返回会话 token"""
    if not app_config.auth.enable:
        return {"token": "disabled"}
    phone = body.phone.strip()
    item = _code_store.get(phone)
    now = time.time()
    if not item or now > item[1]:
        _code_store.pop(phone, None)
        raise HTTPException(status_code=401, detail="验证码已过期，请重新获取")
    if body.code.strip() != item[0]:
        logger.warning(f"验证码登录失败：{phone}")
        raise HTTPException(status_code=401, detail="验证码错误")
    _code_store.pop(phone, None)  # 一次性使用
    logger.info(f"验证码登录成功：{phone}")
    return {"token": _session_token}


@auth_router.post("/api/guest")
async def guest_login():
    """游客登录：跳过验证直接签发会话 token（演示环境不设限制）"""
    if not app_config.auth.enable:
        return {"token": "disabled"}
    logger.info("游客登录")
    return {"token": _session_token}


async def verify_token(x_token: Optional[str] = Header(default=None)):
    """依赖项：校验请求头 X-Token 是否为本次会话签发的令牌"""
    auth = app_config.auth
    if not auth.enable:
        return
    if x_token != _session_token:
        raise HTTPException(status_code=401, detail="未登录或登录已过期")
