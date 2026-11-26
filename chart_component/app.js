/* SPHQ Studio chart component */
(function () {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const COLORS = { strategy: "#00c2a8", spy: "#9aa4b2", policy: "#f0a43a", sma: "#f0b90b" };
  const state = { payload: null, view: "growth", range: "max", log: true, chart: null, ro: null };

  function fmtPct(v, digits) {
    if (v == null || !isFinite(v)) return "—";
    return (v * 100).toFixed(digits == null ? 1 : digits) + "%";
  }
  function fmtX(v) {
    if (v == null || !isFinite(v)) return "—";
    return v.toFixed(2) + "x";
  }
  function fmtDate(time) {
    if (!time) return "";
    if (typeof time === "string") {
      const d = new Date(time + "T00:00:00Z");
      return d.getUTCDate() + " " + MONTHS[d.getUTCMonth()] + " " + d.getUTCFullYear();
    }
    if (time.year) return time.day + " " + MONTHS[time.month - 1] + " " + time.year;
    return "";
  }
  function isoDate(d) {
    return d.getUTCFullYear() + "-" + String(d.getUTCMonth() + 1).padStart(2, "0") + "-" + String(d.getUTCDate()).padStart(2, "0");
  }
  function timeKey(time) {
    if (typeof time === "string") return time;
    if (time && time.year) {
      return time.year + "-" + String(time.month).padStart(2, "0") + "-" + String(time.day).padStart(2, "0");
    }
    return "";
  }
  function lastTime(series) {
    return series && series.length ? series[series.length - 1].time : null;
  }
  function pctFormat() {
    return { type: "custom", formatter: (v) => (v * 100).toFixed(0) + "%", minMove: 0.001 };
  }
  function tickLabel(time) {
    let d;
    if (typeof time === "string") d = new Date(time + "T00:00:00Z");
    else if (time && time.year) d = new Date(Date.UTC(time.year, time.month - 1, time.day));
    else if (typeof time === "number") d = new Date(time * 1000);
    else return "";
    if (isNaN(d.getTime())) return "";
    const month = d.getUTCMonth();
    const year = d.getUTCFullYear();
    if (month !== 0 && state.range !== "1y") return "";
    return month === 0 ? String(year) : MONTHS[month] + " '" + String(year).slice(-2);
  }

  function setFrameHeight() {
    const h = 610;
    window.parent.postMessage({ isStreamlitMessage: true, type: "streamlit:setFrameHeight", height: h }, "*");
  }

  function toast(message) {
    const el = $("chartNote");
    if (!el) return;
    const old = el.textContent;
    el.textContent = message;
    setTimeout(() => { el.textContent = old; }, 2200);
  }

  /* ------------------------------------------------------------------ */
  /* chart                                                               */
  /* ------------------------------------------------------------------ */
  function createChart() {
    const el = $("chart");
    if (!el) return null;
    if (state.ro) {
      state.ro.disconnect();
      state.ro = null;
    }
    if (state.chart) {
      try { state.chart.remove(); } catch (e) { /* ignore */ }
      state.chart = null;
    }
    el.innerHTML = "";
    const chart = LightweightCharts.createChart(el, {
      width: el.clientWidth,
      height: el.clientHeight,
      layout: {
        background: { type: LightweightCharts.ColorType.Solid, color: "#0b0e11" },
        textColor: "#8b96a8",
        fontSize: 10,
        fontFamily: "Inter, Segoe UI, system-ui, sans-serif",
        attributionLogo: true,
      },
      grid: { vertLines: { color: "#141a23" }, horzLines: { color: "#141a23" } },
      crosshair: {
        mode: LightweightCharts.CrosshairMode.Normal,
        vertLine: { color: "#3a4556", width: 1, style: LightweightCharts.LineStyle.Dashed, labelBackgroundColor: "#1c2330" },
        horzLine: { color: "#3a4556", width: 1, style: LightweightCharts.LineStyle.Dashed, labelBackgroundColor: "#1c2330" },
      },
      rightPriceScale: { borderColor: "#232b38", scaleMargins: { top: 0.12, bottom: 0.08 } },
      timeScale: {
        borderColor: "#232b38", timeVisible: false, secondsVisible: false,
        rightOffset: 4, barSpacing: 5, minBarSpacing: 0.02,
        tickMarkFormatter: tickLabel,
      },
      handleScroll: { mouseWheel: true, pressedMouseMove: true, horzTouchDrag: true, vertTouchDrag: false },
      handleScale: { axisPressedMouseMove: true, mouseWheel: true, pinch: true },
      localization: {
        priceFormatter: state.view === "signals" ? (v) => v.toFixed(2) : (v) => (v * 100).toFixed(0) + "%",
      },
      watermark: {
        visible: true, text: "SPHQ STUDIO", color: "rgba(255,255,255,.025)",
        fontSize: 46, fontFamily: "Inter, Segoe UI, sans-serif", horzAlign: "center", vertAlign: "center",
      },
    });
    state.chart = chart;
    state.ro = new ResizeObserver(() => {
      if (!state.chart) return;
      const box = $("chart");
      state.chart.applyOptions({ width: box.clientWidth, height: box.clientHeight });
      applyRange();
    });
    state.ro.observe(el);
    return chart;
  }

  function setRangeByIndex(startIdx, endIdx) {
    if (!state.chart) return;
    const ts = state.chart.timeScale();
    const n = Math.max(1, endIdx - startIdx + 1);
    const padBars = Math.max(8, Math.min(120, Math.round(n * 0.03)));
    const width = Math.max(120, ts.width());
    const spacing = Math.max(0.02, Math.min(5, width / (n + 2 * padBars)));
    ts.applyOptions({ barSpacing: spacing, rightOffset: 0 });
    ts.setVisibleLogicalRange({ from: startIdx - padBars, to: endIdx + padBars });
  }

  function applyRange() {
    if (!state.chart || !state.payload) return;
    const series = state.payload.growth.strategy;
    if (!series.length) return;
    let startIdx = 0;
    const endIdx = series.length - 1;
    if (state.range !== "max") {
      const years = state.range === "5y" ? 5 : state.range === "3y" ? 3 : 1;
      const last = lastTime(series);
      const end = new Date(last + "T00:00:00Z");
      const start = new Date(Date.UTC(end.getUTCFullYear() - years, end.getUTCMonth(), end.getUTCDate()));
      const startStr = isoDate(start);
      const found = series.findIndex((d) => d.time >= startStr);
      if (found >= 0) startIdx = found;
    }
    setRangeByIndex(startIdx, endIdx);
  }

  function addBaseline(chart, series, value, title) {
    series.createPriceLine({
      price: value, color: "#3a4556", lineWidth: 1,
      lineStyle: LightweightCharts.LineStyle.Dashed, axisLabelVisible: false, title: title || "",
    });
  }

  function renderGrowth(chart) {
    const p = state.payload;
    const s = chart.addLineSeries({ color: COLORS.strategy, lineWidth: 2, priceLineVisible: false, lastValueVisible: true, title: "Quality trend" });
    const b = chart.addLineSeries({ color: COLORS.spy, lineWidth: 1.2, priceLineVisible: false, lastValueVisible: true, title: "SPY" });
    const w = chart.addLineSeries({ color: COLORS.policy, lineWidth: 1.4, lineStyle: LightweightCharts.LineStyle.Dashed, priceLineVisible: false, lastValueVisible: true, title: "Policy" });
    s.setData(p.growth.strategy);
    b.setData(p.growth.spy);
    w.setData(p.growth.policy);
    addBaseline(chart, s, 1.0, "1.0x");
    chart.priceScale("right").applyOptions({ mode: state.log ? LightweightCharts.PriceScaleMode.Logarithmic : LightweightCharts.PriceScaleMode.Normal });
    chart.applyOptions({ localization: { priceFormatter: (v) => v.toFixed(2) + "x" } });
    chart.subscribeCrosshairMove((param) => {
      if (!param.time) { setGrowthLegend(); return; }
      const sv = param.seriesData.get(s), bv = param.seriesData.get(b), wv = param.seriesData.get(w);
      $("legend").innerHTML =
        "<span style='color:" + COLORS.strategy + "'>Quality</span> <b>" + fmtX(sv && sv.value) + "</b>" +
        " · <span style='color:" + COLORS.spy + "'>SPY</span> <b>" + fmtX(bv && bv.value) + "</b>" +
        " · <span style='color:" + COLORS.policy + "'>Policy</span> <b>" + fmtX(wv && wv.value) + "</b>" +
        " · <span class='muted'>" + fmtDate(param.time) + "</span>";
    });
    setGrowthLegend();
  }

  function setGrowthLegend() {
    const f = state.payload.growth.final;
    $("legend").innerHTML =
      "<span style='color:" + COLORS.strategy + "'>Quality</span> <b>" + fmtX(f.strategy) + "</b>" +
      " · <span style='color:" + COLORS.spy + "'>SPY</span> <b>" + fmtX(f.spy) + "</b>" +
      " · <span style='color:" + COLORS.policy + "'>Policy</span> <b>" + fmtX(f.policy) + "</b>";
  }

  function renderDrawdown(chart) {
    const p = state.payload;
    const s = chart.addBaselineSeries({
      baseValue: { type: "price", price: 0 },
      topLineColor: "rgba(0,194,168,.9)", topFillColor1: "rgba(0,194,168,.08)", topFillColor2: "rgba(0,194,168,.02)",
      bottomLineColor: COLORS.strategy, bottomFillColor1: "rgba(0,194,168,.04)", bottomFillColor2: "rgba(0,194,168,.24)",
      lineWidth: 1.6, priceLineVisible: false, lastValueVisible: true, title: "Quality trend",
      priceFormat: pctFormat(),
    });
    const b = chart.addLineSeries({ color: COLORS.spy, lineWidth: 1.1, priceLineVisible: false, lastValueVisible: true, title: "SPY", priceFormat: pctFormat() });
    const w = chart.addLineSeries({ color: COLORS.policy, lineWidth: 1.2, lineStyle: LightweightCharts.LineStyle.Dashed, priceLineVisible: false, lastValueVisible: true, title: "Policy", priceFormat: pctFormat() });
    s.setData(p.drawdown.strategy);
    b.setData(p.drawdown.spy);
    w.setData(p.drawdown.policy);
    chart.applyOptions({ localization: { priceFormatter: (v) => (v * 100).toFixed(0) + "%" } });
    chart.subscribeCrosshairMove((param) => {
      if (!param.time) { setDrawdownLegend(); return; }
      const sv = param.seriesData.get(s), bv = param.seriesData.get(b), wv = param.seriesData.get(w);
      $("legend").innerHTML =
        "<span style='color:" + COLORS.strategy + "'>Quality</span> <b>" + fmtPct(sv && sv.value) + "</b>" +
        " · <span style='color:" + COLORS.spy + "'>SPY</span> <b>" + fmtPct(bv && bv.value) + "</b>" +
        " · <span style='color:" + COLORS.policy + "'>Policy</span> <b>" + fmtPct(wv && wv.value) + "</b>" +
        " · <span class='muted'>" + fmtDate(param.time) + "</span>";
    });
    setDrawdownLegend();
  }

  function setDrawdownLegend() {
    const m = state.payload.drawdown.max;
    $("legend").innerHTML =
      "Max drawdown · <span style='color:" + COLORS.strategy + "'>Quality</span> <b>" + fmtPct(m.strategy) + "</b>" +
      " · <span style='color:" + COLORS.spy + "'>SPY</span> <b>" + fmtPct(m.spy) + "</b>" +
      " · <span style='color:" + COLORS.policy + "'>Policy</span> <b>" + fmtPct(m.policy) + "</b>";
  }

  function renderExposure(chart) {
    const p = state.payload;
    const s = chart.addAreaSeries({
      lineColor: COLORS.strategy, topColor: "rgba(0,194,168,.28)", bottomColor: "rgba(0,194,168,.02)",
      lineWidth: 1.4, priceLineVisible: false, lastValueVisible: true, title: "Invested",
      priceFormat: pctFormat(),
    });
    const w = chart.addLineSeries({ color: COLORS.policy, lineWidth: 1.2, lineStyle: LightweightCharts.LineStyle.Dashed, priceLineVisible: false, lastValueVisible: false, title: "Policy target", priceFormat: pctFormat() });
    s.setData(p.exposure.strategy);
    w.setData(p.exposure.policy);
    chart.applyOptions({ localization: { priceFormatter: (v) => (v * 100).toFixed(0) + "%" } });
    chart.subscribeCrosshairMove((param) => {
      if (!param.time) { setExposureLegend(); return; }
      const sv = param.seriesData.get(s), wv = param.seriesData.get(w);
      $("legend").innerHTML =
        "Invested <b>" + fmtPct(sv && sv.value) + "</b>" +
        " · Policy target <b>" + fmtPct(wv && wv.value) + "</b>" +
        " · <span class='muted'>" + fmtDate(param.time) + "</span>";
    });
    setExposureLegend();
  }

  function setExposureLegend() {
    $("legend").innerHTML =
      "Average invested <b>" + fmtPct(state.payload.exposure.average) + "</b>" +
      " · Policy target <b>" + fmtPct(state.payload.params.weight / 100) + "</b>";
  }

  function renderSignals(chart) {
    const p = state.payload;
    const candles = chart.addCandlestickSeries({
      upColor: "#26a69a", downColor: "#ef5350", borderVisible: false,
      wickUpColor: "#26a69a", wickDownColor: "#ef5350",
      priceLineVisible: true, priceLineColor: "#4c8dff", priceLineStyle: LightweightCharts.LineStyle.Dotted,
      priceFormat: { type: "price", precision: 2, minMove: 0.01 },
    });
    const sma = chart.addLineSeries({ color: COLORS.sma, lineWidth: 1.6, priceLineVisible: false, lastValueVisible: true, title: "SMA" });
    candles.setData(p.signals.candles);
    sma.setData(p.signals.sma);
    const markers = p.signals.trades.map((t) => ({
      time: t.execDate,
      position: t.action === "buy" ? "belowBar" : "aboveBar",
      color: t.action === "buy" ? "#26a69a" : "#ef5350",
      shape: t.action === "buy" ? "arrowUp" : "arrowDown",
      text: "",
      size: 1,
    }));
    candles.setMarkers(markers);
    const tradeByDate = {};
    for (const t of p.signals.trades) tradeByDate[t.execDate] = t;
    chart.applyOptions({ localization: { priceFormatter: (v) => v.toFixed(2) } });
    chart.subscribeCrosshairMove((param) => {
      if (!param.time) { setSignalsLegend(); return; }
      const c = param.seriesData.get(candles), a = param.seriesData.get(sma);
      if (c) {
        const trade = tradeByDate[timeKey(param.time)];
        const tradeText = trade
          ? " · <span style='color:" + (trade.action === "buy" ? "#26a69a" : "#ef5350") + "'>" +
            trade.action.toUpperCase() + " @ " + trade.price.toFixed(2) + "</span>"
          : "";
        $("legend").innerHTML =
          "O <b>" + c.open.toFixed(2) + "</b> H <b>" + c.high.toFixed(2) + "</b> L <b>" + c.low.toFixed(2) +
          "</b> C <b>" + c.close.toFixed(2) + "</b> · SMA <b>" + (a ? a.value.toFixed(2) : "—") +
          "</b>" + tradeText + " · <span class='muted'>" + fmtDate(param.time) + "</span>";
      } else {
        setSignalsLegend();
      }
    });
    setSignalsLegend();
  }

  function setSignalsLegend() {
    const p = state.payload;
    const last = p.signals.candles[p.signals.candles.length - 1];
    const lastSma = p.signals.sma[p.signals.sma.length - 1];
    $("legend").innerHTML =
      "SPHQ <b>" + (last ? last.close.toFixed(2) : "—") + "</b>" +
      " · SMA <b>" + (lastSma ? lastSma.value.toFixed(2) : "—") + "</b>" +
      " · <span style='color:" + COLORS.strategy + "'>" + p.signals.trades.filter((t) => t.action === "buy").length + " buys</span>" +
      " / <span style='color:#ef5350'>" + p.signals.trades.filter((t) => t.action === "sell").length + " sells</span>";
  }

  function renderRolling(chart) {
    const p = state.payload;
    const s = chart.addLineSeries({ color: COLORS.strategy, lineWidth: 1.8, priceLineVisible: false, lastValueVisible: true, title: "Quality trend", priceFormat: pctFormat() });
    const b = chart.addLineSeries({ color: COLORS.spy, lineWidth: 1.1, priceLineVisible: false, lastValueVisible: true, title: "SPY", priceFormat: pctFormat() });
    s.setData(p.rolling.strategy);
    b.setData(p.rolling.spy);
    addBaseline(chart, s, 0, "0%");
    chart.applyOptions({ localization: { priceFormatter: (v) => (v * 100).toFixed(0) + "%" } });
    chart.subscribeCrosshairMove((param) => {
      if (!param.time) { setRollingLegend(); return; }
      const sv = param.seriesData.get(s), bv = param.seriesData.get(b);
      $("legend").innerHTML =
        "<span style='color:" + COLORS.strategy + "'>Quality</span> <b>" + fmtPct(sv && sv.value) + "</b>" +
        " · <span style='color:" + COLORS.spy + "'>SPY</span> <b>" + fmtPct(bv && bv.value) + "</b>" +
        " · <span class='muted'>" + fmtDate(param.time) + "</span>";
    });
    setRollingLegend();
  }

  function setRollingLegend() {
    const r = state.payload.rolling.summary;
    $("legend").innerHTML =
      "Median <b>" + fmtPct(r.strategy["Median"]) + "</b>" +
      " · Worst <b>" + fmtPct(r.strategy["Worst"]) + "</b>" +
      " · Best <b>" + fmtPct(r.strategy["Best"]) + "</b>" +
      " · <span class='muted'>" + r.windows.toLocaleString() + " windows</span>";
  }

  function render() {
    const p = state.payload;
    if (!p || !window.LightweightCharts) return;
    const chart = createChart();
    if (!chart) return;

    const view = state.view;
    const titles = {
      growth: "Growth of $1",
      drawdown: "Drawdown from peak",
      exposure: "Strategy exposure",
      signals: "SPHQ candlesticks, SMA and executed trades",
      rolling: "Rolling 24-month return",
    };
    const notes = {
      growth: state.log ? "Log scale · all series start at 1" : "Linear scale · all series start at 1",
      drawdown: "Negative values are declines from the previous peak",
      exposure: "Share of the portfolio invested in SPHQ; policy target is dashed",
      signals: "Green ▲ = buy · red ▼ = sell · adjusted OHLC",
      rolling: "Overlapping 504-trading-day returns; windows are not independent",
    };
    $("chartTitle").textContent = titles[view] || "";
    $("chartNote").textContent = notes[view] || "";
    $("logBtn").style.display = view === "growth" ? "" : "none";
    $("viewNote").textContent =
      view === "growth" ? "All series start at 1" :
      view === "signals" ? "Green ▲ buy · red ▼ sell" :
      view === "drawdown" ? "Peak-to-trough" :
      view === "exposure" ? "All-in or all-cash" : "24-month horizon";
    $("strategySub").textContent = p.params.sma + "-day quality trend · " + p.params.cost.toFixed(0) + " bps · t+" + p.params.lag;

    if (view === "growth") renderGrowth(chart);
    else if (view === "drawdown") renderDrawdown(chart);
    else if (view === "exposure") renderExposure(chart);
    else if (view === "signals") renderSignals(chart);
    else renderRolling(chart);

    $("dataDate").textContent = p.meta.sample.replace(" to ", "–");
    $("statsLine").textContent =
      "CAGR " + fmtPct(p.metrics.CAGR, 2) + " · Vol " + fmtPct(p.metrics.Volatility, 2) +
      " · Sharpe " + p.metrics.Sharpe.toFixed(2) + " · Beta " + p.metrics.Beta.toFixed(2) +
      " · Max DD " + fmtPct(p.metrics.MaxDrawdown, 2);
    applyRange();
  }

  /* ------------------------------------------------------------------ */
  /* controls / boot                                                     */
  /* ------------------------------------------------------------------ */
  function bind() {
    document.querySelectorAll("#viewbar button").forEach((b) => {
      b.addEventListener("click", () => {
        if (state.view === b.dataset.view) return;
        document.querySelectorAll("#viewbar button").forEach((x) => x.classList.remove("active"));
        b.classList.add("active");
        state.view = b.dataset.view;
        render();
      });
    });
    document.querySelectorAll("#rangeGroup button").forEach((b) => {
      b.addEventListener("click", () => {
        if (state.range === b.dataset.range) return;
        document.querySelectorAll("#rangeGroup button").forEach((x) => x.classList.remove("active"));
        b.classList.add("active");
        state.range = b.dataset.range;
        applyRange();
      });
    });
    $("logBtn").addEventListener("click", () => {
      state.log = !state.log;
      $("logBtn").classList.toggle("active", state.log);
      if (state.chart && state.view === "growth") {
        state.chart.priceScale("right").applyOptions({
          mode: state.log ? LightweightCharts.PriceScaleMode.Logarithmic : LightweightCharts.PriceScaleMode.Normal,
        });
        $("chartNote").textContent = (state.log ? "Log scale" : "Linear scale") + " · all series start at 1";
      }
    });
    window.addEventListener("resize", () => {
      if (state.chart) {
        const el = $("chart");
        state.chart.applyOptions({ width: el.clientWidth, height: el.clientHeight });
      }
    });
    $("logBtn").classList.toggle("active", state.log);
  }

  function applyPayload(payload) {
    state.payload = payload;
    render();
  }

  window.addEventListener("message", (event) => {
    const data = event.data;
    if (!data || data.type !== "streamlit:render") return;
    const payload = data.args && data.args.payload;
    if (payload) applyPayload(payload);
  });

  function boot() {
    window.parent.postMessage({ isStreamlitMessage: true, type: "streamlit:componentReady", apiVersion: 1 }, "*");
    setFrameHeight();
    bind();
    const el = $("chart");
    if (el && !el.dataset.ready) {
      el.dataset.ready = "1";
      el.innerHTML = '<div class="loading">Loading strategy…</div>';
    }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
