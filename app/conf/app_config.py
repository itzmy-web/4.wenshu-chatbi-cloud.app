import os
import re
from dataclasses import dataclass
from pathlib import Path

from omegaconf import OmegaConf


# 日志配置
@dataclass
class File:
    enable: bool
    level: str
    path: str
    rotation: str
    retention: str


@dataclass
class Console:
    enable: bool
    level: str


@dataclass
class LoggingConfig:
    file: File
    console: Console


@dataclass
class LLMConfig:
    model_name: str
    api_key: str
    base_url: str


@dataclass
class EmbeddingConfig:
    # lexical = 内置词汇向量（char-ngram TF-IDF，零外部依赖）
    mode: str = "lexical"


@dataclass
class AuthConfig:
    # 是否开启登录鉴权
    enable: bool = True
    username: str = "admin"
    # A7：密码默认值已清零，必须由 .env 的 AUTH_PASSWORD 注入，缺失时启动报错
    password: str = ""


@dataclass
class AppConfig:
    logging: LoggingConfig
    llm: LLMConfig
    embedding: EmbeddingConfig
    auth: AuthConfig


def _load_env_file(env_path: Path) -> None:
    """极简 .env 解析：KEY=VALUE 行写入进程环境（不覆盖已有环境变量）。"""
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def _expand_env(text: str) -> str:
    """展开 yaml 中的 ${ENV_VAR} 占位符；缺失变量直接抛错，避免静默空值启动。"""
    pattern = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")

    def _replace(m: re.Match) -> str:
        var = m.group(1)
        val = os.environ.get(var, "")
        if not val:
            raise ValueError(f"缺少环境变量 {var}：请在项目 .env 或部署环境注入（参考 .env.example）")
        return val

    return pattern.sub(_replace, text)


# A7：优先加载项目根 .env（真实凭据只放 .env，不入源码）
_load_env_file(Path(__file__).parents[2] / '.env')

config_file = Path(__file__).parents[2] / 'conf' / 'app_config.yaml'
context = OmegaConf.create(_expand_env(config_file.read_text(encoding="utf-8")))
schema = OmegaConf.structured(AppConfig)
app_config: AppConfig = OmegaConf.to_object(OmegaConf.merge(schema, context))
