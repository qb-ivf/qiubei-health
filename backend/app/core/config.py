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
    GOV_REPORT_URL: str = ""     # （旧占位，待 TJ_* 全量接管后移除）
    GOV_APP_SECRET: str = ""

    # —— 放心签：高级证书协议、智能双录与处方 PDF 签署 ——
    # ENABLED 控制是否调用放心签；DOCUMENT_SIGN_ENABLED 控制审方通过时是否真实签署 PDF；
    # REQUIRED 是生产总门禁，开启后双录与已验签 PDF 均不可绕过。
    FXQ_CA_ENABLED: bool = False
    FXQ_DOCUMENT_SIGN_ENABLED: bool = False
    FXQ_CA_REQUIRED: bool = False
    FXQ_APP_KEY: str = ""        # 开放平台应用的 AppKey/AppID（以控制台显示为准）
    FXQ_APP_SECRET: str = ""     # 仅放部署环境变量，不入 git
    FXQ_CA_REDIRECT_URL: str = ""  # 如 https://api.example.com/api/v1/ca/callback
    FXQ_COMPANY_NAME: str = ""   # 签章证书主体全称，如“天津逑贝互联网医院有限公司”
    FXQ_COMPANY_IDNO: str = ""   # 企业统一社会信用代码
    FXQ_TOKEN_URL: str = "https://identity.fangxinqian.cn/auth/v1/token"
    FXQ_REQUEST_SIGN_URL: str = "https://identity.fangxinqian.cn/auth/v1/encrypt"
    FXQ_CA_AGREEMENT_URL: str = "https://identity.fangxinqian.cn/face/v1/agreement/dualrecording/ca"
    FXQ_CA_RESULT_URL: str = "https://identity.fangxinqian.cn/face/v1/dualrecording/result"
    FXQ_PERSONAL_SEAL_URL: str = "https://restapi.fangxinqian.cn/seal/v1/personal"
    FXQ_COMPANY_SEAL_URL: str = "https://restapi.fangxinqian.cn/seal/v1/company"
    FXQ_PDF_SIGN_URL: str = "https://restapi.fangxinqian.cn/contract/v1/port/sign"
    FXQ_PDF_VERIFY_URL: str = "https://restapi.fangxinqian.cn/signature/chk/file"
    FXQ_HTTP_TIMEOUT_SECONDS: float = 15.0
    FXQ_MAX_PDF_BYTES: int = 10 * 1024 * 1024
    FXQ_SIGNED_PDF_DIR: str = ""  # 空时使用 backend/storage/prescriptions（须持久卷/备份）
    FXQ_ARCHIVE_KEY: str = ""     # 签后 PDF 加密备份专用 32B urlsafe-base64 密钥；须与备份分开保管

    # —— 天津监管平台（docs/tianjin_supervision_plan.md，密钥见平台"秘钥生成及管理"） ——
    # False：DEBUG=true 时本地模拟；DEBUG=false 时保留 pending 队列、不发送也不吞任务。
    TJ_REPORT_ENABLED: bool = False
    TJ_GATEWAY_URL: str = ""         # 形如 http://imssp.wsjk.tj.gov.cn/net-diag-service/test-openapi/api
    TJ_APP_KEY: str = ""
    TJ_APP_SECRET: str = ""          # 应为 32 位 hex（同时是 SM4 密钥）
    TJ_UNIT_ID: str = ""             # 监管平台机构 ID
    ORGAN_ID: str = ""               # 全国统一组织机构代码
    ORGAN_NAME: str = ""             # 机构登记全称

    # —— 对象存储（资质/录制/处方 PDF，15 年归档） ——
    OSS_BUCKET: str = ""


settings = Settings()
