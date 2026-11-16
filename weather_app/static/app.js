(function () {
  "use strict";

  const state = {
    city: localStorage.getItem("weather-city") || "南京",
    unit: localStorage.getItem("weather-unit") || "C",
    dashboard: null,
    prediction: null,
    china: null,
    chinaSortAscending: true,
    activeView: "overview",
  };

  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => Array.from(document.querySelectorAll(selector));

  const WEATHER = {
    0: ["晴", "clear", "☀"],
    1: ["晴间多云", "clear", "◒"],
    2: ["多云", "cloudy", "☁"],
    3: ["阴", "cloudy", "☁"],
    45: ["雾", "cloudy", "≋"], 48: ["雾凇", "cloudy", "≋"],
    51: ["毛毛雨", "rain", "☂"], 53: ["毛毛雨", "rain", "☂"], 55: ["强毛毛雨", "rain", "☂"],
    56: ["冻毛毛雨", "rain", "☂"], 57: ["强冻毛毛雨", "rain", "☂"],
    61: ["小雨", "rain", "☂"], 63: ["中雨", "rain", "☂"], 65: ["大雨", "rain", "☂"],
    66: ["冻雨", "rain", "☂"], 67: ["强冻雨", "rain", "☂"],
    71: ["小雪", "snow", "❄"], 73: ["中雪", "snow", "❄"], 75: ["大雪", "snow", "❄"], 77: ["霰", "snow", "❄"],
    80: ["阵雨", "rain", "☂"], 81: ["中阵雨", "rain", "☂"], 82: ["强阵雨", "rain", "☂"],
    85: ["阵雪", "snow", "❄"], 86: ["强阵雪", "snow", "❄"],
    95: ["雷暴", "storm", "ϟ"], 96: ["雷暴伴冰雹", "storm", "ϟ"], 99: ["强雷暴伴冰雹", "storm", "ϟ"],
  };

  function weatherMeta(code) {
    return WEATHER[Number(code)] || ["天气变化", "cloudy", "☁"];
  }

  function conditionGlyph(condition) {
    if (condition.includes("雷")) return "ϟ";
    if (condition.includes("雪")) return "❄";
    if (condition.includes("雨")) return "☂";
    if (condition.includes("雾")) return "≋";
    if (condition.includes("云") || condition.includes("阴")) return "☁";
    return "☀";
  }

  function aqiMeta(value) {
    const aqi = Number(value);
    if (!Number.isFinite(aqi)) return { label: "--", level: 1 };
    if (aqi <= 50) return { label: "优", level: 1 };
    if (aqi <= 100) return { label: "良", level: 2 };
    if (aqi <= 150) return { label: "轻度", level: 3 };
    if (aqi <= 200) return { label: "中度", level: 4 };
    if (aqi <= 300) return { label: "重度", level: 5 };
    return { label: "严重", level: 6 };
  }

  function temperature(value, digits = 0) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) return "--°";
    const converted = state.unit === "F" ? numeric * 9 / 5 + 32 : numeric;
    return `${converted.toFixed(digits)}°`;
  }

  function escapeHTML(value) {
    return String(value ?? "").replace(/[&<>'"]/g, (char) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
    })[char]);
  }

  function shortDate(value, withWeekday = true) {
    const date = new Date(`${String(value).slice(0, 10)}T00:00:00`);
    return new Intl.DateTimeFormat("zh-CN", {
      month: "numeric", day: "numeric", ...(withWeekday ? { weekday: "short" } : {}),
    }).format(date);
  }

  function timeLabel(value) {
    const hour = String(value).slice(11, 16);
    return hour === "00:00" ? "明日" : hour;
  }

  function windDirection(degrees) {
    if (!Number.isFinite(Number(degrees))) return "";
    const directions = ["北", "东北", "东", "东南", "南", "西南", "西", "西北"];
    return directions[Math.round(Number(degrees) / 45) % 8];
  }

  async function fetchJSON(url, options = {}) {
    const response = await fetch(url, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
    let body;
    try { body = await response.json(); } catch (_error) { body = {}; }
    if (!response.ok) throw new Error(body.error || `请求失败 (${response.status})`);
    return body;
  }

  function setLoading(visible, title = "正在加载", detail = "连接气象服务") {
    const overlay = $("#loading-overlay");
    overlay.hidden = !visible;
    $("#loading-title").textContent = title;
    $("#loading-detail").textContent = detail;
  }

  let toastTimer;
  function showToast(message) {
    const toast = $("#toast");
    toast.textContent = message;
    toast.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { toast.hidden = true; }, 4200);
  }

  function setStatus(message, error = false) {
    $("#data-status").textContent = message;
    $(".live-dot").classList.toggle("error", error);
  }

  async function loadDashboard({ silent = false } = {}) {
    if (!silent) setLoading(true, `正在读取${state.city}天气`, "同步实时、逐小时与历史观测");
    setStatus("正在连接气象数据...");
    try {
      state.dashboard = await fetchJSON(`/api/weather?city=${encodeURIComponent(state.city)}`);
      state.city = state.dashboard.location.name;
      localStorage.setItem("weather-city", state.city);
      renderDashboard();
      const staleText = state.dashboard.stale ? " · 使用缓存" : "";
      setStatus(`${state.dashboard.source} 实时数据${staleText}`);
      $("#updated-at").textContent = `更新 ${new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })}`;
    } catch (error) {
      setStatus("气象数据连接失败", true);
      showToast(error.message);
    } finally {
      setLoading(false);
    }
  }

  function renderDashboard() {
    const { current, hourly, observed_history: history, forecast_reference: reference, location } = state.dashboard;
    const [condition, scene, glyph] = weatherMeta(current.weather_code);
    const aqi = aqiMeta(current.air_us_aqi);
    const currentDay = reference[0] || {};
    const isNight = Number(current.is_day) === 0;

    $("#current-location").textContent = `${location.name} · ${location.province}`;
    $("#footer-location").textContent = `${location.name}站`;
    $("#current-temperature").textContent = temperature(current.temperature_2m);
    $("#current-condition").textContent = `${glyph} ${condition}`;
    $("#feels-like").textContent = `体感 ${temperature(current.apparent_temperature)}`;
    $("#humidity").textContent = `${Math.round(current.relative_humidity_2m ?? 0)}%`;
    $("#wind").textContent = `${windDirection(current.wind_direction_10m)} ${Math.round(current.wind_speed_10m ?? 0)} km/h`;
    $("#pressure").textContent = `${Math.round(current.surface_pressure ?? 0)} hPa`;
    $("#aqi").textContent = `${Math.round(current.air_us_aqi ?? 0)} · ${aqi.label}`;
    $("#weather-summary").textContent = summaryText(current, currentDay, condition);
    $("#daily-rain").textContent = `${Number(currentDay.precipitation_sum ?? current.precipitation ?? 0).toFixed(1)} mm`;
    $("#daily-uv").textContent = uvLabel(currentDay.uv_index_max);
    $("#sun-time").textContent = `${String(currentDay.sunrise || "--").slice(11, 16)} / ${String(currentDay.sunset || "--").slice(11, 16)}`;
    $("#pm25").textContent = `${Number(current.air_pm2_5 ?? 0).toFixed(1)} μg/m³`;

    const stage = $("#weather-stage");
    stage.className = `weather-stage weather-${isNight ? "night" : scene}`;
    renderHourly(hourly);
    renderHistory(history);
    refreshIcons();
  }

  function summaryText(current, daily, condition) {
    const rain = Number(daily.precipitation_probability_max ?? 0);
    const cloud = Number(current.cloud_cover ?? 0);
    if (rain >= 60) return `${condition}，今天降水可能性较高，出行请留意临近预报。`;
    if (Number(current.wind_speed_10m) >= 30) return `${condition}，风力较强，户外活动注意防风。`;
    if (cloud <= 25) return `${condition}，云量较少，昼夜温差可能较明显。`;
    return `${condition}，今日降水概率 ${Math.round(rain)}%，体感温度 ${temperature(current.apparent_temperature)}。`;
  }

  function uvLabel(value) {
    const uv = Number(value);
    if (!Number.isFinite(uv)) return "--";
    if (uv < 3) return `${uv.toFixed(1)} · 弱`;
    if (uv < 6) return `${uv.toFixed(1)} · 中等`;
    if (uv < 8) return `${uv.toFixed(1)} · 强`;
    return `${uv.toFixed(1)} · 很强`;
  }

  function renderHourly(rows) {
    $("#hourly-strip").innerHTML = rows.map((row, index) => {
      const meta = weatherMeta(row.weather_code);
      return `<article class="hour-card">
        <span class="time">${index === 0 ? "现在" : escapeHTML(timeLabel(row.time))}</span>
        <span class="weather-glyph" title="${escapeHTML(meta[0])}">${meta[2]}</span>
        <strong>${temperature(row.temperature_2m)}</strong>
        <small>${Math.round(row.precipitation_probability ?? 0)}%</small>
      </article>`;
    }).join("");
  }

  function renderHistory(rows) {
    if (!rows.length) return;
    $("#history-chart").innerHTML = createLineChart(rows);
    $("#history-table").innerHTML = rows.map((row) => `<tr>
      <td>${escapeHTML(shortDate(row.time))}</td>
      <td>${escapeHTML(weatherMeta(row.weather_code)[0])}</td>
      <td>${temperature(row.temperature_2m_max, 1)}</td>
      <td>${temperature(row.temperature_2m_min, 1)}</td>
      <td>${Number(row.precipitation_sum ?? 0).toFixed(1)} mm</td>
      <td>${Number(row.wind_speed_10m_max ?? 0).toFixed(1)} km/h</td>
    </tr>`).join("");
  }

  function createLineChart(rows) {
    const width = 900, height = 290, left = 55, right = 25, top = 22, bottom = 44;
    const values = rows.flatMap((row) => [Number(row.temperature_2m_max), Number(row.temperature_2m_min)]).filter(Number.isFinite);
    const minValue = Math.floor(Math.min(...values) / 5) * 5 - 5;
    const maxValue = Math.ceil(Math.max(...values) / 5) * 5 + 5;
    const x = (index) => left + index * (width - left - right) / Math.max(rows.length - 1, 1);
    const y = (value) => top + (maxValue - value) * (height - top - bottom) / Math.max(maxValue - minValue, 1);
    const points = (key) => rows.map((row, index) => `${x(index)},${y(Number(row[key]))}`).join(" ");
    const grid = Array.from({ length: 5 }, (_, index) => {
      const value = minValue + index * (maxValue - minValue) / 4;
      const position = y(value);
      return `<line class="chart-grid" x1="${left}" y1="${position}" x2="${width - right}" y2="${position}"/><text class="chart-axis-label" x="4" y="${position + 4}">${value.toFixed(0)}°</text>`;
    }).join("");
    const labels = rows.map((row, index) => `<text class="chart-axis-label" text-anchor="middle" x="${x(index)}" y="${height - 12}">${escapeHTML(shortDate(row.time, false))}</text>`).join("");
    const dots = rows.map((row, index) => `<circle class="chart-dot-high" cx="${x(index)}" cy="${y(Number(row.temperature_2m_max))}" r="4"/><circle class="chart-dot-low" cx="${x(index)}" cy="${y(Number(row.temperature_2m_min))}" r="4"/>`).join("");
    return `<svg viewBox="0 0 ${width} ${height}" aria-hidden="true">${grid}<polyline class="chart-high" points="${points("temperature_2m_max")}"/><polyline class="chart-low" points="${points("temperature_2m_min")}"/>${dots}${labels}</svg>`;
  }

  async function runPrediction(force = false) {
    const button = $("#train-button");
    button.disabled = true;
    setLoading(true, force ? "正在重新训练模型" : "正在训练或加载模型", "获取三年历史数据并执行时序验证，首次约需 10–30 秒");
    try {
      state.prediction = await fetchJSON("/api/predict", {
        method: "POST",
        body: JSON.stringify({ city: state.city, retrain: force }),
      });
      renderPrediction();
      showToast(state.prediction.cached_model ? "已使用本地训练模型完成预测" : "模型训练完成并已保存");
    } catch (error) {
      const banner = $("#model-banner");
      banner.className = "model-banner error";
      banner.querySelector("strong").textContent = "模型运行失败";
      banner.querySelector("p").textContent = error.message;
      showToast(error.message);
    } finally {
      button.disabled = false;
      setLoading(false);
    }
  }

  function renderPrediction() {
    const { metrics, model, predictions, cached_model: cached } = state.prediction;
    const banner = $("#model-banner");
    banner.className = "model-banner ready";
    banner.querySelector("strong").textContent = cached ? "已载入本地模型" : "训练与验证完成";
    banner.querySelector("p").textContent = `模型训练至 ${model.training_end}，预测不会使用未来观测数据。`;
    const metricValues = [`${metrics.mae_high}°C`, `${metrics.mae_low}°C`, metrics.mae_aqi, `${(metrics.weather_accuracy * 100).toFixed(1)}%`];
    $$("#model-metrics strong").forEach((element, index) => { element.textContent = metricValues[index]; });
    $("#ml-forecast").innerHTML = predictions.map((row) => {
      const aqi = aqiMeta(row.aqi);
      return `<article class="forecast-card">
        <span class="date">${escapeHTML(shortDate(row.date))}</span>
        <div class="weather-glyph">${conditionGlyph(row.condition)}</div>
        <span class="condition">${escapeHTML(row.condition)}</span>
        <div class="range"><strong>${temperature(row.temperature_max, 1)}</strong><span>${temperature(row.temperature_min, 1)}</span></div>
        <small>高温区间 ${temperature(row.temperature_max_interval[0], 1)}–${temperature(row.temperature_max_interval[1], 1)}</small>
        <div class="aqi-chip aqi-${aqi.level}">AQI ${Math.round(row.aqi)} · ${aqi.label}</div>
      </article>`;
    }).join("");
    $("#model-algorithm").textContent = model.algorithm;
    $("#model-range").textContent = `${model.training_start} – ${model.training_end}`;
    $("#model-samples").textContent = `${model.training_samples} 训练 / ${model.validation_samples} 验证`;
    $("#model-features").textContent = `${model.features} 项`;
    $("#model-details").hidden = false;
  }

  async function loadChina() {
    if (state.china) return;
    setLoading(true, "正在读取全国天气", "批量同步省级行政区代表城市观测");
    try {
      const payload = await fetchJSON("/api/china");
      state.china = payload.locations;
      renderChina();
    } catch (error) {
      showToast(error.message);
    } finally {
      setLoading(false);
    }
  }

  function renderChina() {
    const validAqi = state.china.filter((item) => Number.isFinite(Number(item.us_aqi)));
    const cleanest = [...validAqi].sort((a, b) => a.us_aqi - b.us_aqi)[0];
    const worst = [...validAqi].sort((a, b) => b.us_aqi - a.us_aqi)[0];
    const warmest = [...state.china].sort((a, b) => b.temperature_2m - a.temperature_2m)[0];
    const summaries = [cleanest ? `${cleanest.name} · ${Math.round(cleanest.us_aqi)}` : "--", worst ? `${worst.name} · ${Math.round(worst.us_aqi)}` : "--", warmest ? `${warmest.name} · ${temperature(warmest.temperature_2m)}` : "--"];
    $$("#china-summary strong").forEach((element, index) => { element.textContent = summaries[index]; });

    $("#province-grid").innerHTML = state.china.map((item) => {
      const meta = aqiMeta(item.us_aqi);
      return `<article class="province-cell aqi-${meta.level}" title="${escapeHTML(item.name)}：${escapeHTML(weatherMeta(item.weather_code)[0])}">
        <strong>${escapeHTML(item.province)}</strong><span>${Math.round(item.us_aqi ?? 0)}</span><small>${escapeHTML(item.name)} · ${temperature(item.temperature_2m)}</small>
      </article>`;
    }).join("");
    renderChinaTable();
  }

  function renderChinaTable() {
    const rows = [...state.china].sort((a, b) => state.chinaSortAscending ? a.us_aqi - b.us_aqi : b.us_aqi - a.us_aqi);
    $("#china-table").innerHTML = rows.map((item) => {
      const aqi = aqiMeta(item.us_aqi);
      return `<tr><td>${escapeHTML(item.province)}</td><td>${escapeHTML(item.name)}</td><td>${escapeHTML(weatherMeta(item.weather_code)[0])}</td><td>${temperature(item.temperature_2m, 1)}</td><td><span class="aqi-chip aqi-${aqi.level}">${Math.round(item.us_aqi ?? 0)} · ${aqi.label}</span></td><td>${Number(item.pm2_5 ?? 0).toFixed(1)} μg/m³</td></tr>`;
    }).join("");
  }

  function switchView(view) {
    state.activeView = view;
    $$(".nav-tab").forEach((tab) => {
      const active = tab.dataset.view === view;
      tab.classList.toggle("active", active);
      tab.setAttribute("aria-selected", String(active));
    });
    $$("[data-view-panel]").forEach((panel) => {
      const active = panel.dataset.viewPanel === view;
      panel.hidden = !active;
      panel.classList.toggle("active", active);
    });
    if (view === "china") loadChina();
  }

  let searchTimer;
  async function searchCities(query) {
    const results = $("#search-results");
    if (!query.trim()) { results.hidden = true; return; }
    try {
      const payload = await fetchJSON(`/api/locations?q=${encodeURIComponent(query)}`);
      results.innerHTML = payload.locations.length ? payload.locations.map((location) => `<button class="search-result" type="button" role="option" data-city="${escapeHTML(location.name)}"><span>${escapeHTML(location.name)}</span><small>${escapeHTML(location.province)}</small></button>`).join("") : `<div class="empty-state">未找到匹配城市</div>`;
      results.hidden = false;
      $("#city-search").setAttribute("aria-expanded", "true");
    } catch (error) {
      showToast(error.message);
    }
  }

  function refreshIcons() {
    if (window.lucide) window.lucide.createIcons({ attrs: { "stroke-width": 1.8 } });
  }

  function bindEvents() {
    $$(".nav-tab").forEach((tab) => tab.addEventListener("click", () => switchView(tab.dataset.view)));
    $("#refresh-button").addEventListener("click", () => loadDashboard());
    $("#train-button").addEventListener("click", (event) => runPrediction(event.shiftKey));
    $("#unit-toggle").addEventListener("click", () => {
      state.unit = state.unit === "C" ? "F" : "C";
      localStorage.setItem("weather-unit", state.unit);
      $$("#unit-toggle span").forEach((span) => span.classList.toggle("active", span.textContent.includes(state.unit)));
      if (state.dashboard) renderDashboard();
      if (state.prediction) renderPrediction();
      if (state.china) renderChina();
    });
    $("#city-search").addEventListener("input", (event) => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => searchCities(event.target.value), 260);
    });
    $("#search-results").addEventListener("click", (event) => {
      const option = event.target.closest("[data-city]");
      if (!option) return;
      state.city = option.dataset.city;
      state.prediction = null;
      $("#city-search").value = state.city;
      $("#search-results").hidden = true;
      $("#city-search").setAttribute("aria-expanded", "false");
      loadDashboard();
    });
    document.addEventListener("click", (event) => {
      if (!event.target.closest("#search-shell")) $("#search-results").hidden = true;
    });
    $("#sort-aqi").addEventListener("click", () => {
      state.chinaSortAscending = !state.chinaSortAscending;
      renderChinaTable();
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    $("#city-search").value = state.city;
    $$("#unit-toggle span").forEach((span) => span.classList.toggle("active", span.textContent.includes(state.unit)));
    bindEvents();
    refreshIcons();
    loadDashboard();
  });
})();
