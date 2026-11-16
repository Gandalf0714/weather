"""Chinese city presets and geocoding helpers."""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Location:
    name: str
    province: str
    latitude: float
    longitude: float
    timezone: str = "Asia/Shanghai"

    def to_dict(self):
        return asdict(self)


# Province-level capital coordinates are also used by the nationwide view.
CAPITALS = (
    Location("北京", "北京", 39.9042, 116.4074),
    Location("天津", "天津", 39.0842, 117.2010),
    Location("石家庄", "河北", 38.0428, 114.5149),
    Location("太原", "山西", 37.8706, 112.5489),
    Location("呼和浩特", "内蒙古", 40.8426, 111.7492),
    Location("沈阳", "辽宁", 41.8057, 123.4315),
    Location("长春", "吉林", 43.8171, 125.3235),
    Location("哈尔滨", "黑龙江", 45.8038, 126.5350),
    Location("上海", "上海", 31.2304, 121.4737),
    Location("南京", "江苏", 32.0603, 118.7969),
    Location("杭州", "浙江", 30.2741, 120.1551),
    Location("合肥", "安徽", 31.8206, 117.2272),
    Location("福州", "福建", 26.0745, 119.2965),
    Location("南昌", "江西", 28.6820, 115.8579),
    Location("济南", "山东", 36.6512, 117.1201),
    Location("郑州", "河南", 34.7466, 113.6254),
    Location("武汉", "湖北", 30.5928, 114.3055),
    Location("长沙", "湖南", 28.2282, 112.9388),
    Location("广州", "广东", 23.1291, 113.2644),
    Location("南宁", "广西", 22.8170, 108.3665),
    Location("海口", "海南", 20.0440, 110.1999),
    Location("重庆", "重庆", 29.5630, 106.5516),
    Location("成都", "四川", 30.5728, 104.0668),
    Location("贵阳", "贵州", 26.6470, 106.6302),
    Location("昆明", "云南", 25.0389, 102.7183),
    Location("拉萨", "西藏", 29.6520, 91.1721),
    Location("西安", "陕西", 34.3416, 108.9398),
    Location("兰州", "甘肃", 36.0611, 103.8343),
    Location("西宁", "青海", 36.6171, 101.7782),
    Location("银川", "宁夏", 38.4872, 106.2309),
    Location("乌鲁木齐", "新疆", 43.8256, 87.6168),
    Location("台北", "台湾", 25.0330, 121.5654),
    Location("香港", "香港", 22.3193, 114.1694),
    Location("澳门", "澳门", 22.1987, 113.5439),
)

LOCATION_INDEX = {item.name: item for item in CAPITALS}
DEFAULT_LOCATION = LOCATION_INDEX["南京"]


def find_preset(query):
    """Return exact or fuzzy preset matches without making a network call."""
    normalized = (query or "").strip().lower()
    if not normalized:
        return list(CAPITALS[:8])
    exact = LOCATION_INDEX.get(normalized)
    if exact:
        return [exact]
    return [
        item
        for item in CAPITALS
        if normalized in item.name.lower() or normalized in item.province.lower()
    ]
