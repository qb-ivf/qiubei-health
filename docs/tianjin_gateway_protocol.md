# 天津监管平台网关协议实现细则（SDK 逆向确认版）

> 来源：对官方 Java SDK `ngari-supervision-1.7-SNAPSHOT.jar`（归档于 [docs/specs/tianjin/](specs/tianjin/)）的字节码逆向分析（`javap -c`），并用 SDK 本体生成黄金测试向量。
> **本文以 SDK 实现为准**——规范 PDF 1.1 节的文字描述（"k=v& 拼接、requestBody 参与签名"）与 SDK 实际实现**不一致**，联调必须按本文写。
> 供 S1 阶段 `backend/app/services/tj_gateway.py` + `backend/app/utils/sm_crypto.py` 开发与单测对拍使用。

---

## 一、请求组装完整流程（`openapi.Client.execute` 逆向还原）

```
1. bodyJson   = JSON 序列化业务参数（最外层是数组，如 [ {...} ]），UTF-8
2. encrypted  = SM4_CBC_Encrypt(
                    key = hex_decode(appSecret),        # appSecret 本身是 32 位 hex 字符串 → 16 字节密钥
                    iv  = hex_decode("abcd0863ef9087ced675985321bedf67"),   # 固定 IV，硬编码在 SDK 中
                    padding = PKCS7,
                    plaintext = bodyJson.encode("utf-8")
                )
                → 输出为【小写 hex 字符串】（不是 Base64！）
3. X-Content-MD5 = SM3(encrypted)                        # 名字叫 MD5，实际是 SM3，输出【大写 hex】
4. 组装请求头：
     X-Service-Id      = his.provinceDataUploadService   # Request 构造时设置
     X-Service-Method  = <方法名>
     X-Ca-Key          = appKey
     X-Ca-Nonce        = uuid4()
     X-Ca-Timestamp    = 毫秒时间戳
     X-Content-MD5     = 见第 3 步
5. 签名串 signStr：
     - 取参与签名的头：所有 X-Ca-* 开头的头 + [X-Service-Id, X-Service-Method,
       X-Ca-Key, X-Ca-Nonce, X-Ca-Timestamp, X-Content-MD5]（SIGN_HEADER_LIST）
     - 放入 TreeMap（按 key 字典序排序）
     - 每项拼为 `lowercase(key):value`（键转小写，冒号分隔，值为空则只留 `key:`）
     - 用 `&` 连接
     ⚠️ requestBody 不直接参与签名——密文通过 X-Content-MD5 间接绑定
6. X-Ca-Signature         = SM3(signStr)                 # 大写 hex
   X-Ca-Signature-Headers = 参与签名头的小写名，按字典序逗号连接
7. POST <网关地址>/openapi/api
     Content-Type: application/json
     HTTP body = encrypted（第 2 步的 hex 字符串本体，原样作为 body，不再包 JSON）
```

### 响应处理

```json
{ "code": 200, "body": { "msgCode": 200, "msg": "请求成功" } }
```
- 外层 `code`：HTTP 层（40001 参数错 / 40004 密钥不匹配 / 40007 IP 白名单 / 40010 签名不合法 / 40011 请求过期 / -1 系统繁忙）。
- `body.msgCode`：业务层（200 成功；-99 必输字段为空，msg 用 `|` 列字段名；-98 数据为空；-1 具体失败文案）。
- 重试策略：`-1(系统繁忙)/40011/网络超时/5xx` → 可自动重试；`-99/-1(业务)/40001` → 数据问题，进失败列表待人工修复后重报。

### 文件上传（api/uploadFile）

SDK 走 `Client.executeNoEncode`：**不做 SM4 加密**，body 为明文 JSON（`[{fileName, contentBase64, size, type}]`），`X-Content-MD5 = SM3(明文 body)`，其余头与签名规则相同；方法名传 `upload`，地址为 `api/uploadFile`（以联调实测为准）。

### 其他确认事项

- SDK 配置四元组：`apiUrl / appKey / appSecret / encodingAesKey`。其中 **encodingAesKey 在 SM4 路径未被使用**（遗留 AES 参数），我方实现可忽略。
- appSecret 演示值 `bbf1dd188b8b4629853f06f118d11e4a`（32 hex 字符）→ 印证平台分配的正式 appSecret 也应是 32 位 hex；若拿到的不是 32 hex，先找平台确认。
- SDK 内置演示网关：`http://192.168.30.79:8080/openapi/api`（内网示例）；规范截图显示测试网关形如 `http://imssp.wsjk.tj.gov.cn/net-diag-service/test-openapi/api`，正式地址以平台"秘钥生成及管理"页为准。
- 供应商为纳里健康（ngari），jar 内含全部接口的实体类（`openapi/mode/*.class`），字段名可用 `javap -p` 查看，作为规范 PDF 之外的第二核对来源。

---

## 二、黄金测试向量（由官方 SDK 生成，Python 单测必须逐字节对上）

生成条件：`appSecret = bbf1dd188b8b4629853f06f118d11e4a`，IV 固定如上。

| # | 项目 | 输入 | 期望输出 |
| :-: | :-- | :-- | :-- |
| V1 | SM3 标准向量 | `"abc"` | `66C7F0F462EEEDD9D1F2D46BDC10E4E24167C4875CF2F7A2297DA02B8F4BA8E0`（与 GB/T 32905 一致，输出大写 hex） |
| V2 | SM4-CBC 加密 | 明文 `[1]` | `49a9a1cb6403aa7ca5d7be3287b0dc6b`（小写 hex） |
| V3 | SM4-CBC 加密 | 明文 `[{"organID":"12345678901234567X","unitID":"U0001","organName":"天津逑贝互联网医院"}]`（UTF-8） | `bda12c065d493fcb45851a847d58648fdcb5dc17fc8c2f895ad2e2394bfdc309c977b99228aa51fa2aeabe25d28af20bf7658673dc1f8a2c9e7ab7de50311bdfba0d8a0c84ad3dd9a41c1635ec80d121fa0b5ef611139a6d23c4644480fb68a6` |
| V4 | X-Content-MD5 | V2 的密文串 | `F7DCA75A3D6083A0E4FD0BA219FFE8AC10E35AE45FD8A91F90A9CDAB5A0ED056` |
| V5 | 签名串 | 头：X-Ca-Key=`ngari5fd5ad2196834aa7`、X-Ca-Nonce=`8d708068-0a36-47d3-8ff4-011fdace7d63`、X-Ca-Timestamp=`1718185594026`、X-Content-MD5=V4、X-Service-Id=`his.provinceDataUploadService`、X-Service-Method=`uploadDrugCatalogue` | `x-ca-key:ngari5fd5ad2196834aa7&x-ca-nonce:8d708068-0a36-47d3-8ff4-011fdace7d63&x-ca-timestamp:1718185594026&x-content-md5:F7DCA75A3D6083A0E4FD0BA219FFE8AC10E35AE45FD8A91F90A9CDAB5A0ED056&x-service-id:his.provinceDataUploadService&x-service-method:uploadDrugCatalogue` |
| V6 | X-Ca-Signature | SM3(V5) | `A07C0B67CE2996DF9416A5BE7EB7F4E8EAF40F31D46423A1FA9ECEA188C7627A` |
| V7 | X-Ca-Signature-Headers | 同上头集合 | `x-ca-key,x-ca-nonce,x-ca-timestamp,x-content-md5,x-service-id,x-service-method` |

> 复现方法：解包 jar 后编写小型 Java runner 调用 `openapi.util.SM4Utils.encryptNationalSerAlgorithmCBC` 与 `openapi.util.SM3Util.encode`（无第三方依赖），`javac -encoding UTF-8 -cp <jar解包目录> Vectors.java` 即可运行；需要新增向量时照此生成。

## 三、Python 实现要点（S1 对照清单）

- [ ] `gmssl` 库：`sm4.CryptSM4`（`ENCRYPT` 模式 + CBC）+ `sm3.sm3_hash`。注意 gmssl 的 `crypt_cbc` 自带 PKCS7 填充，输出 bytes → `.hex()` 得小写 hex，与 V2/V3 对拍。
- [ ] SM3 输出：`sm3_hash` 返回小写 hex，**需 `.upper()`** 与 SDK 的大写输出一致（V1/V4/V6）。
- [ ] 签名串组装：`sorted(headers)` + `f"{k.lower()}:{v}"` + `"&".join`，X-Ca-Signature-Headers 为小写键名逗号连接（V5/V7）。
- [ ] HTTP body 直接发 hex 密文字符串（`content=encrypted`），不要再 `json.dumps`。
- [ ] 单测文件建议：`backend/tests/test_tj_gateway.py`，把 V1–V7 全部写成断言。
