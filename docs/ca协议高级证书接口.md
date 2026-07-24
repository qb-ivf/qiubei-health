
## 高级证书接口
>通过实名认证的实时人脸活体检测以及意愿问题进行比对，证明客户为本人并且知情愿意签署。

> 项目实现与部署说明见 [fangxinqian_ca_integration.md](fangxinqian_ca_integration.md)。
> 注意：本文档只覆盖 CA 协议双录和结果查询，不包含处方 PDF 文档签署、医院电子印章、签后文件下载及验签接口。

##### 接口信息

| 描述   | 值    |
|--------------| ---|
| 请求地址  |https://identity.fangxinqian.cn/face/v1/agreement/dualrecording/ca |
| 请求方式  |POST |
| Content-Type | application/json|
| <br>Headers  | token=您申请获得的token<br>fxq-nonce=请求流水号 nonce（保证唯一性）<br>fxq-sign= 签名信息 sign<br>(详情请查看"请求签名规则") |


##### 请求参数
 
|   参数名称    | 类型 | 必选|             参数说明              |
|:---------:| :---: | :---: |:-----------------------------:|
| name | String | 是 | 姓名 |
| idNo | String | 是 | 身份证号 |
| redirectUrl | String | 是 | 智能鉴证核验通过后跳转地址 |
| userId|String | 是 | 接入方自定义的用户唯一标识 |
| orderNo | String | 是 | 订单号 |




 
##### 请求示例

```json
{
  "name": "张三",
  "idNo": "121212200001011212",
  "redirectUrl": "https：//www.fangxinqian.cn",
  "userId": "fxq123456",
  "orderNo": "fxq123456"
}
```


##### 响应示例

```json
{
    "code": 10000,
    "data": {
        "verifyId": "U_2026xxxxxxxxxxxx42016",
        "agreementUrl": "https://identity.fangxinqian.cn/faceIntegrate?faceType=2&verifyId=U_2026xxxxxxxxxxxx42016&rd=h930eF1K"
    },
    "msg": "成功",
    "tradeNo": "3bb4xxxxxxxxxxxxxx5ce4"
}
```
##### 响应参数 

|参数名称|类型|参数说明|
|:-----  |:-----|-----                           |
|code |int   |状态码值，10000代表接口请求成功  |
|data |object   |返回人脸识别h5链接，此链接有效期为2min  |
|msg |string   |返回消息  |
|tradeNo |string   |交易单号  |

##### data 

|参数名称|类型|参数说明|
|:-----  |:-----|-----                           |
|verifyId |string   | 核验ID |
|agreementUrl |string   | CA协议阅读及智能双录地址 |

> H5 双录核验结果跳转:

示例：https://mobile.fangxinqian.cn/cafaceresult?code=0&msg=ASR%E8%AF%86%E5%88%AB%E4%B8%BA%E8%82%AF%E5%AE%9A%E5%9B%9E%E7%AD%94&orderNo=fxq123456&verifyId=U_202607xxxxxxx164928

##### 响应参数 

|参数名称|类型|参数说明|
|:-----  |:-----|-----                           |
|code |string  |人脸核身结果的返回码 0：人脸核身成功，其他错误码：失败|
|msg |string |返回消息|
|orderNo |string |订单号|
|verifyId |string |核验ID||

#### 查询核身结果
>业务在完成认证后，可以通过服务端调用此接口获取智能鉴证相关数据。此数据有效期为三天。由于存储为异步行为，因此会有延迟，可以加个轮询判断视频文件是否存在，建议轮询3 次，每次 10s，没拉取到视频文件的情况下进行重试

##### 1.您须要在前端完成刷脸的回调后，再来调用查询核身结果接口获取刷脸视频和照片。

##### 接口信息

| 描述   |                                                     值                                                     |
| :----: |:---------------------------------------------------------------------------------------------------------:|
| 请求地址  | https://identity.fangxinqian.cn/face/v1/dualrecording/result |
| 请求方式  |                                                    POST                                                    |
| <br>Headers  |        token=您申请获得的token<br>fxq-nonce=请求流水号 nonce（保证唯一性）<br>fxq-sign= 签名信息 sign<br>(详情请查看"请求签名规则")        |


##### 请求参数
 
| 参数名称   | 类型 | 必选|   参数说明  |
| :----: | :---: | :---: |:-------:|
| orderNo  |String|  是  | 获取核验链接的订单号 |
| getFile | String | 否 | 是否需要音视频文件，1-返回视频和照片，2-返回照片，3-返回视频，其他不返回。不传默认为2 |
| getDetails | String | 否 | 是否需要详细信息，1：需要 |
| getPhotos | String | 否 | 是否需要返回多张刷脸图片,1-需要 |


##### 返回示例
```
{
	"code": 10000,
	"data": {
		"faceCode": "0",
        "faceMsg": "请求成功",
		"orderNo": "hhr123456",
		"liveRate": "99",
		"similarity": "96.0",
		"occurredTime": "2025-11-05 11:10:17",
        "phone":"/9j/4AAQSkZJRgABAgAAAQABAAD/2wB******",
		"willFullUserVideo": null,
		"aiRiskList": null,
		"willPhoto": null
	},
	"msg": "成功",
	"tradeNo": "eae0aec194f24bd59e640c90147d1b68"
}
```
##### 响应参数 
|参数名称|类型|参数说明|
|:-----  |:-----:|-----                           |
|code |int   |状态码值，10000代表成功 |
|data |object   |返回数据  |
|msg  |string   |返回消息  |
|tradeNo |string   |交易单号  |


##### data参数 
|参数名称|类型|参数说明|
|:-----  |:-----|-----                           |
|faceCode |string   | 获取核验链接状态码，0代表成功，其余具体状态码查看[详情](#xiangqing)   |
|faceMsg |string   | 获取核验链接结果详细信息 |
| orderNo | String | 智能鉴证订单号 |
| liveRate | String | 活体检测得分 |
| similarity | String | 人脸比对得分 |
| occurredTime | String | 进行刷脸的时间 |
| photo | String | 进行人脸的照片 |
| willFullUserVideo | String | 全流程智能鉴证含字幕视频 ，getFile 传 1 或者 3才有 |
| aiRiskList | String | AI 标签去重列表，多个标签根据逗号分隔 |
| willPhoto | String | 多张图片 base64 信息，getPhotos 传 1 才有 |


<a id="xiangqing"></a>

##### faceCode状态码说明
|参数名称|参数说明|
|:-----  |----- |
| 0      | 成功 |   
| 1101   | 参数不合法 |
| 1103   | IP 未加入白名单 |
| 1104   | SECRET 错误 |
| 1107   | 参数不合法 |
| 1506   | 请求频率过高，请稍后再试 |
| 1601   | 请求体参数过大 |
| 1602   | 请求体参数错误(文本内容参数) |
| 2001   | appId 不存在 |
| 2002   | 已经过有效期 |
| 2003   | 试用版最大次数已超 |
| 2013   | 请求参数异常(tts 参数) |
| 2015   | 风控:用户信息不合法 |
| 2016   | 风控:文件格式不合法 |
| 6010   | 意愿表达结果查询不到 |
| 6011   |  TTS 服务异常 |
| 9999   | 服务内部错误 |
| 3001   | 人脸多次移出框内 |
| 3002   | 人脸长时间不在框内 |
| 3003   | 人脸比对不通过 |
| 3004   | 活体检测不通过|
| 3005   | 比对时视频出现多张脸 |
| 3006   | 中途存在换脸 |
| 3100   | 多次检测到风险标签 |
| 6006   | 意愿结果识别失败 |
| 6001   | 回答阶段未唇动 |
| 6002   | 回答阶段未睁眼 |
| 6003   | 意愿结果识别为否定回答 |
| 6004   | 用户长时间未回复 |
| 6005 | 用户反复要求重新播报 |






