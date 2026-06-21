"""微信支付下单（M2）。mock 五元组；真实接入替换 prepay()。"""
import time
import uuid

from ..schemas.order import PrepayOut


def prepay(order_id: int, fee_fen: int) -> PrepayOut:
    """返回 wx.requestPayment 所需五元组。

    阶段二 mock：返回占位参数（前端 dev 走 /pay/mock 直接成功）。
    正式：调微信支付 V3 JSAPI 下单拿 prepay_id，再按规则签名生成五元组。
    """
    return PrepayOut(
        timeStamp=str(int(time.time())),
        nonceStr=uuid.uuid4().hex,
        package="prepay_id=mock_" + uuid.uuid4().hex[:12],
        signType="RSA",
        paySign="MOCK_SIGN",
        order_id=order_id,
    )
