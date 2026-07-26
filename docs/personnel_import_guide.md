# 医护药人员资料收集与批量导入指引

> 空白模板：[人员批量导入模板.xlsx](templates/人员批量导入模板.xlsx)  
> 模板不含真实个人信息，可以纳入版本管理；**填写后的副本禁止提交 Git 或发送到聊天。**

## 1. 当前系统范围

| 人员 | 当前处理方式 | 与 CA/监管的关系 |
| :-- | :-- | :-- |
| 医生 | 本人先登录医生端一次，再按授权手机号批量补录档案 | 姓名、身份证须匹配放心签个人证书；监管还要求诊疗科目和科室编码 |
| 审方药师 | 可由管理员批量创建运营后台账号并加密录入身份证 | 姓名、身份证须匹配放心签个人证书和处方审方主体 |
| 护士 | 仅收集花名册，当前不导入 | 当前没有护士角色；天津平台护理类接口不属于本院对接范围 |

不得把护士账号创建为 `pharmacist`、`admin` 或借用他人账号。将来启用护理业务时，应先实现独立
`nurse` 角色、权限、业务接口和审计规则，再导入护士。

## 2. 医生必备材料

每名医生一行，至少收集：

1. 本人微信绑定手机号；
2. 姓名、18 位身份证号；
3. 医师资格证号、医师执业证号；
4. 科室名称、职称；
5. 天津监管诊疗科目编码/名称、科室类别编码；
6. 医务审核结论、放心签个人证书名单核对结果。

诊疗科目只能从字典 3.1 选择，科室类别只能从字典 3.2 选择，并且必须落在医院许可范围内。
当前生产预检允许的诊疗科目范围为内科 `03*`、妇产科 `05*`、中医科 `50*`。

医生批量补录前，必须由本人在医生端使用手机号授权登录一次，使系统生成与微信 `openid` 绑定的
待审核档案。禁止为了导入而伪造 `openid` 或共用手机号。

## 3. 药师必备材料

每名审方药师至少收集：

1. 唯一登录用户名（建议使用内部工号）；
2. 姓名、18 位身份证号；
3. 启用状态、资质审核结论；
4. 放心签个人证书名单核对结果。

药学资格证号、执业药师注册证号、部门和职称建议同时收集用于医院内部资质留档，但当前
`staff` 表只写入用户名、姓名、身份证密文、角色和启用状态。

初始密码不填入人员表。批量导入时应为每人生成不同的强密码，通过受控渠道逐人分发，不得在日志、
Git、聊天或普通邮件中出现。当前版本尚未提供药师自助改密，随机初始密码必须按正式账号凭据保管；
不得把它当作可公开的临时口令。

## 4. 敏感文件交接

填写后的工作簿建议命名为 `人员批量导入-YYYYMMDD.xlsx`，通过单位批准的加密渠道传输，并放到生产
服务器独立目录，例如：

```bash
install -d -m 700 /opt/qiubei-health/secure-import
chmod 600 /opt/qiubei-health/secure-import/人员批量导入-YYYYMMDD.xlsx
```

不要把文件放进 `/opt/qiubei-health/backend` Git 工作区。导入完成并留存导入审计摘要后，按医院
个人信息管理制度转入加密档案或安全删除临时副本。

## 5. 导入程序的安全规则

导入程序为 `backend/scripts/import_personnel.py`，具有以下约束：

- 默认是只读 `dry-run`，没有 `--apply` 时不会写库或生成密码；
- 医生按本人首次微信登录时授权的手机号匹配，找不到时只报工作表行号，不创建假 `openid`；
- 药师按登录用户名幂等新增或更新，已有药师不会重置密码；
- 身份证、姓名、手机号和密码均不在控制台、错误信息或审计详情中输出；
- 拒绝超过 10MB、异常压缩结构、公式单元格和被 Excel 转成数字的身份证/证书号；
- 新药师随机初始密码只写入新建的 `0600` 独立文件，禁止覆盖既有凭据文件；
- 正式导入要求 `DEBUG=false`、`DOCTOR_AUTO_APPROVE=false`、有效 `ENCRYPTION_KEY`，
  并使用统一社会信用代码二次确认目标机构；
- 护士工作表只统计行数，本次不会创建护士账号。
- 正式写入会在操作审计中保存工作簿 SHA-256 和人数汇总，不保存人员明细。

## 6. 生产执行命令

先把已复核工作簿放到 Git 工作区之外。下面的目录只允许 root 访问：

```bash
install -d -m 700 /opt/qiubei-health/secure-import
chmod 600 /opt/qiubei-health/secure-import/人员批量导入-YYYYMMDD.xlsx

cd /opt/qiubei-health/backend
dc() {
  docker compose -f docker-compose.yml -f docker-compose.prod.yml "$@"
}
```

生产 `.env` 必须先确认：

```dotenv
DEBUG=false
DOCTOR_AUTO_APPROVE=false
ENCRYPTION_KEY=<现有正式 Fernet 密钥；已有加密数据时禁止直接更换>
```

第一次只读预检。使用临时只读挂载，因此工作簿不会进入 API 常驻容器：

```bash
dc run --rm --no-deps \
  -v /opt/qiubei-health/secure-import:/secure-import:ro \
  api python -m scripts.import_personnel \
  /secure-import/人员批量导入-YYYYMMDD.xlsx
```

只有输出 `OK 预检通过` 和 `DRY-RUN 完成`，且没有 `[ERROR]`，才能正式导入。正式导入需要可写挂载，
用于创建药师随机初始密码文件：

```bash
dc run --rm --no-deps \
  -v /opt/qiubei-health/secure-import:/secure-import:rw \
  api python -m scripts.import_personnel \
  /secure-import/人员批量导入-YYYYMMDD.xlsx \
  --apply \
  --confirm-organ-id 91120116MACJA9PX45 \
  --credentials-out /secure-import/药师初始密码-YYYYMMDD.csv
```

默认只补录医生资料，不自动通过医生终审。如果医务已经逐行复核了表中的“医务审核结论”和
“CA 名单核对”，可在正式命令末尾增加：

```text
--approve-doctors
```

导入程序不会回显凭据文件路径或内容。执行后由 root 在服务器核对其权限，再通过单位批准的受控渠道
逐人分发：

```bash
stat -c '%a %U:%G %n' /opt/qiubei-health/secure-import/药师初始密码-YYYYMMDD.csv
```

预期权限为 `600`。分发完成后按医院账号凭据管理制度加密归档或安全删除，不得提交 Git。

## 7. 后续执行顺序

1. 医务、药事分别填写并复核表格；
2. 6 名医生本人先在医生端完成首次手机号授权登录；
3. 使用批量导入程序做只读校验，输出行号和非敏感错误，不输出身份证或密码；
4. 修正至 `0 ERROR` 后执行正式导入；
5. 在生产容器运行 `python -m scripts.tj_preflight`，医生和药师检查必须为 `PASS`；
6. 先选 1 名医生、1 名药师分别完成放心签真实双录；
7. 双录成功后再开启首张处方三方签章联调。
