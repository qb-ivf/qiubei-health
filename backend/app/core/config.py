"""全局配置（pydantic-settings，从 .env 读取）。"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "Qiubei SaaS Backend"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"

    # —— 数据库（PRD §1.2：MySQL 部署于 VPC 私有子网） ——
    DATABASE_URL: str = "mysql+aiomysql://root:root@localhost:3306/qiubei?charset=utf8mb4"
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_RECYCLE: int = 1800

    # —— Redis（信令在线状态、号源锁、排队队列） ——
    REDIS_URL: str = "redis://localhost:6379/0"

    # —— JWT 鉴权（PRD §2.4） ——
    JWT_SECRET: str = "CHANGE_ME_IN_PROD"
    JWT_ALG: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440

    # —— 腾讯云 TRTC（PRD §2.3，密钥仅存服务端） ——
    TRTC_SDKAPPID: int = 0
    TRTC_SECRETKEY: str = ""
    TRTC_SIG_EXPIRE: int = 7200  # 120 分钟

    # —— 微信支付 ——
    WX_APPID: str = ""
    WX_MCHID: str = ""
    WX_API_V3_KEY: str = ""

    # —— 合规网关（卫健委 / CA） ——
    GOV_REPORT_URL: str = ""
    GOV_APP_SECRET: str = ""
    CA_SIGN_URL: str = ""

    # —— 对象存储（资质/录制/处方 PDF，15 年归档） ——
    OSS_BUCKET: str = ""


settings = Settings()
