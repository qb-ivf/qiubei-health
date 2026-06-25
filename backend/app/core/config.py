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

    # —— 敏感字段加密（身份证/手机号，PRD §2.4） ——
    ENCRYPTION_KEY: str = ""  # Fernet key（base64 32B）；空则开发回退（勿用于生产）

    # —— 微信登录 / 支付 ——
    WX_PATIENT_APPID: str = ""
    WX_PATIENT_SECRET: str = ""
    WX_DOCTOR_APPID: str = ""
    WX_DOCTOR_SECRET: str = ""
    WX_APPID: str = ""           # 发起支付的小程序 AppID（患者端，须在商户平台关联 WX_MCHID）
    WX_MCHID: str = ""           # 微信支付商户号
    WX_API_V3_KEY: str = ""      # APIv3 密钥（32 位，回调/敏感信息解密）
    WX_MCH_CERT_SERIAL: str = ""        # 商户 API 证书序列号
    WX_MCH_PRIVATE_KEY_PATH: str = ""   # 商户 API 私钥 apiclient_key.pem 路径（相对 backend/ 或绝对路径）
    WX_PAY_NOTIFY_URL: str = ""         # 支付结果回调地址（公网 HTTPS）；空则支付走 mock 回退
    WX_PAY_PUBLIC_KEY_PATH: str = ""    # 微信支付公钥 pub_key.pem 路径（公钥模式回调验签，新商户用）
    WX_PAY_PUBLIC_KEY_ID: str = ""      # 微信支付公钥ID（PUB_KEY_ID_...，可选，留存备用）

    # —— CORS（生产收敛；逗号分隔的允许来源，空=不允许跨域；小程序非浏览器不受影响） ——
    CORS_ORIGINS: str = ""

    # —— 医生白名单（开发期自动通过；生产置 False，走 admin 终审） ——
    DOCTOR_AUTO_APPROVE: bool = True

    # —— 腾讯云短信（验证码；留空走开发模式打印验证码） ——
    TENCENT_SMS_SECRET_ID: str = ""
    TENCENT_SMS_SECRET_KEY: str = ""
    TENCENT_SMS_SDK_APP_ID: str = ""
    TENCENT_SMS_SIGN: str = ""          # 短信签名内容
    TENCENT_SMS_TEMPLATE_ID: str = ""   # 验证码模板 ID
    TENCENT_SMS_REGION: str = "ap-guangzhou"

    # —— 合规网关（卫健委 / CA） ——
    GOV_REPORT_URL: str = ""
    GOV_APP_SECRET: str = ""
    CA_SIGN_URL: str = ""

    # —— 对象存储（资质/录制/处方 PDF，15 年归档） ——
    OSS_BUCKET: str = ""


settings = Settings()
