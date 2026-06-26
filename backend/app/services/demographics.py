"""身份证人口学解析：从 18 位身份证号提取省份 / 年龄 / 性别。

身份证结构：前 6 位行政区划码（前 2 位为省级），第 7-14 位出生日期 YYYYMMDD，
第 17 位性别（奇男偶女）。省份名采用 datav geojson 全称，便于前端地图直接匹配。
"""
from datetime import date

# 省级行政区划码（前 2 位）→ 省份全称（与 public/geo/china.json 的 properties.name 对齐）
PROVINCE_BY_CODE = {
    "11": "北京市", "12": "天津市", "13": "河北省", "14": "山西省", "15": "内蒙古自治区",
    "21": "辽宁省", "22": "吉林省", "23": "黑龙江省",
    "31": "上海市", "32": "江苏省", "33": "浙江省", "34": "安徽省", "35": "福建省",
    "36": "江西省", "37": "山东省",
    "41": "河南省", "42": "湖北省", "43": "湖南省", "44": "广东省", "45": "广西壮族自治区", "46": "海南省",
    "50": "重庆市", "51": "四川省", "52": "贵州省", "53": "云南省", "54": "西藏自治区",
    "61": "陕西省", "62": "甘肃省", "63": "青海省", "64": "宁夏回族自治区", "65": "新疆维吾尔自治区",
    "71": "台湾省", "81": "香港特别行政区", "82": "澳门特别行政区",
}

# 年龄分桶（含下界，闭区间）：(label, lo, hi)；hi=None 表示无上界
AGE_BUCKETS = [
    ("≤17 岁", 0, 17), ("18-29 岁", 18, 29), ("30-39 岁", 30, 39),
    ("40-49 岁", 40, 49), ("50-59 岁", 50, 59), ("≥60 岁", 60, None),
]


def _age_from_birth(y: int, m: int, d: int, today: date) -> int | None:
    try:
        born = date(y, m, d)
    except ValueError:
        return None
    age = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
    return age if 0 <= age <= 120 else None


def parse_id_card(id_no: str | None, today: date | None = None) -> dict | None:
    """解析身份证。返回 {province, age, gender}（字段可能为 None），无法解析返回 None。"""
    if not id_no or len(id_no) != 18:
        return None
    today = today or date.today()
    province = PROVINCE_BY_CODE.get(id_no[:2])
    age = _age_from_birth(int(id_no[6:10]), int(id_no[10:12]), int(id_no[12:14]), today) \
        if id_no[6:14].isdigit() else None
    gender = None
    if id_no[16:17].isdigit():
        gender = "男" if int(id_no[16]) % 2 else "女"
    if province is None and age is None:
        return None
    return {"province": province, "age": age, "gender": gender}


def age_bucket(age: int) -> str | None:
    for label, lo, hi in AGE_BUCKETS:
        if age >= lo and (hi is None or age <= hi):
            return label
    return None
