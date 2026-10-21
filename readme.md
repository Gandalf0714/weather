# 观云台：Python 天气预测与可视化

一个完整的 Python 机器学习天气项目：从公开气象 API 获取并缓存数据，用 pandas 完成清洗和特征工程，用 scikit-learn 训练、验证和持久化模型，再通过 Flask 提供交互式可视化页面。

> 原仓库的 2022 年版代码和数据保留在 `基于Python的天气预测和可视化/`，作为历史参考。当前可运行版本位于根目录与 `weather_app/`。

## 已实现功能

- 实时天气：温度、体感、湿度、风速、气压、AQI、PM2.5、UV、日出日落。
- 逐小时预报：未来 24 小时温度、天气状态和降水概率。
- 近期实况：最近 7 天最高/最低温折线图及明细表。
- Python ML 预测：对未来 7 天最高温、最低温、AQI 和天气类型进行预测。
- 模型评估：按时间顺序切分训练集/验证集，展示各目标 MAE 和天气分类准确率。
- 模型持久化：每个城市独立保存 joblib 模型，默认 30 天内复用。
- 全国天气：34 个省级行政区代表城市的温度、天气、AQI 和 PM2.5。
- 城市搜索、摄氏/华氏切换、响应式布局、加载/错误/缓存状态。
- 命令行训练、强制重训、历史数据导出与生产服务入口。

## 技术架构

```text
浏览器
  │  /api/weather /api/predict /api/china
  ▼
Flask 路由 ────── Open-Meteo 客户端 ────── 实时/历史/空气质量 API
  │                         │
  │                         └── data/cache（响应缓存）
  ▼
WeatherModelService
  ├── pandas：清洗、日期周期特征、1/7 日滞后、7/30 日滚动均值
  ├── RandomForestRegressor：最高温、最低温、AQI
  ├── RandomForestClassifier：晴/多云/雾/雨/雪/雷暴
  ├── 后 20% 时间段验证：MAE + accuracy
  └── data/models（joblib 模型）
```

所有预测特征都来自预测日之前的数据。训练/验证按时间顺序拆分，没有随机打乱，避免未来信息泄漏。

## 快速开始

要求 Python 3.10 或更高版本。

Windows 可以直接双击根目录的 `start_weather.bat`。脚本会在需要时创建虚拟环境、安装依赖、启动服务并打开浏览器。命令窗口必须保持开启，关闭窗口会停止网站。

也可以手动启动：

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

浏览器打开 <http://127.0.0.1:5000>。首次点击“训练并预测”会下载约三年的城市历史数据并训练模型，通常需要 10–30 秒；之后会直接复用本地模型。

生产运行：

```powershell
python manage.py run --host 0.0.0.0 --port 5000
```

## 命令行

训练指定城市并输出未来 7 天预测：

```powershell
python manage.py train --city 南京
python manage.py train --city 北京 --force
```

导出清洗后的训练数据：

```powershell
python manage.py export --city 南京 --output data/nanjing_history.csv
```

## 测试

测试使用合成时序数据，不依赖网络：

```powershell
pytest -q
pytest --cov=weather_app --cov-report=term-missing
```

## 目录说明

```text
app.py                         开发服务入口
manage.py                      生产运行、训练、导出命令
requirements.txt               Python 依赖
weather_app/
  __init__.py                  Flask application factory
  config.py                    环境与缓存配置
  routes.py                    页面与 JSON API
  services/
    locations.py               城市与省会坐标
    weather_client.py          数据获取、校验、缓存与降级
  ml/
    features.py                特征工程与天气分类
    model_service.py           训练、验证、持久化、递归预测
  templates/index.html         页面结构
  static/styles.css            响应式视觉样式
  static/app.js                交互、图表与 API 调用
tests/                         单元与接口测试
基于Python的天气预测和可视化/    原始项目归档
```

## 配置

通过环境变量调整运行行为：

| 变量 | 默认值 | 用途 |
|---|---:|---|
| `WEATHER_DATA_DIR` | `data/` | 缓存和模型目录 |
| `WEATHER_HTTP_TIMEOUT` | `20` | 上游请求超时秒数 |
| `WEATHER_CACHE_TTL` | `1800` | 实时响应缓存秒数 |
| `WEATHER_MODEL_MAX_AGE_DAYS` | `30` | 模型最大复用天数 |
| `WEATHER_HISTORY_YEARS` | `3` | 训练历史年数 |

## 数据与预测边界

- 数据源是 Open-Meteo，使用时应遵守其服务条款；本项目不需要 API Key。
- 机器学习输出用于课程实验和趋势分析，不应代替官方预警或专业气象服务。
- 7 天递归预测越靠后不确定性越高。页面展示的温度区间是基于验证集 MAE 的直观误差带，并非严格置信区间。
