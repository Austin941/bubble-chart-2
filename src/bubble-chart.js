/**
 * 泡泡圖 2.0 — ECharts 視覺化核心
 * - 泡泡圖（全市場散點）
 * - 大戶趨勢折線圖
 * - 分點明細表格
 */

let bubbleChart = null;
let holdersChart = null;

// 產業色票
const INDUSTRY_COLORS = {
  '半導體': '#3b9eff',
  '電腦及週邊設備': '#a78bfa',
  '電子零組件': '#63b3ed',
  '光電': '#38d9a9',
  '通信網路': '#4ecdc4',
  '金融保險': '#f6c90e',
  '食品工業': '#fc8181',
  '鋼鐵工業': '#f97316',
  '建材營建': '#fb923c',
  '其他': '#5d7898',
};

function getIndustryColor(industry) {
  for (const [key, color] of Object.entries(INDUSTRY_COLORS)) {
    if (industry?.includes(key)) return color;
  }
  return INDUSTRY_COLORS['其他'];
}

// ── 格式化工具 ────────────────────────────────────────────
function fmtNum(n) {
  if (n == null) return '—';
  return n >= 10000 ? `${(n/10000).toFixed(1)}萬`
       : n >= 1000  ? `${(n/1000).toFixed(1)}千`
       : String(Math.round(n));
}
function fmtPct(n) { return n == null ? '—' : `${n.toFixed(2)}%`; }
function fmtNet(n) {
  if (n == null) return '—';
  const s = fmtNum(Math.abs(n));
  return n >= 0 ? `+${s}` : `-${s}`;
}

// ─────────────────────────────────────────────────────────
// 1. 泡泡圖
// ─────────────────────────────────────────────────────────
function initBubbleChart() {
  const el = document.getElementById('bubble-chart');
  if (!el) return;
  bubbleChart = echarts.init(el, null, { renderer: 'canvas' });
  bubbleChart.on('click', onBubbleClick);
  window.addEventListener('resize', () => bubbleChart?.resize());
  redrawBubble();
}

function redrawBubble() {
  if (!bubbleChart) return;
  const holdersDate = APP.selected.date || APP.dates.holders[0];
  const brokersDate = APP.dates.brokers.find(d => d <= (holdersDate || '99999999')) || APP.dates.brokers[0];

  const rawData = mergeData(holdersDate, brokersDate);
  const filtered = filterData(rawData);
  const { x: xKey, y: yKey, size: sizeKey } = getAxisConfig();

  // 按產業分組
  const byIndustry = {};
  filtered.forEach(d => {
    const ind = d.industry || '其他';
    if (!byIndustry[ind]) byIndustry[ind] = [];
    byIndustry[ind].push(d);
  });

  // 計算泡泡大小比例
  const sizeValues = filtered.map(d => d[sizeKey] || 0);
  const maxSize = Math.max(...sizeValues, 1);

  const series = Object.entries(byIndustry).map(([industry, items]) => ({
    name: industry,
    type: 'scatter',
    symbolSize: d => Math.max(8, Math.sqrt((d[3] / maxSize) * 2500)),
    data: items.map(d => [
      d[xKey] ?? 0,
      d[yKey] ?? 0,
      d.id,
      d[sizeKey] ?? 0,
      d.name,
      d,
    ]),
    itemStyle: {
      color: getIndustryColor(industry),
      opacity: 0.82,
      borderColor: 'rgba(255,255,255,0.15)',
      borderWidth: 1,
    },
    emphasis: {
      itemStyle: { opacity: 1, borderWidth: 2, borderColor: '#fff' },
      scale: true,
    },
  }));

  // 標記線（X / Y 軸中線）
  const midX = filtered.length ? filtered.reduce((s, d) => s + (d[xKey] ?? 0), 0) / filtered.length : 0;
  const midY = 0;

  const option = {
    backgroundColor: 'transparent',
    animation: true,
    animationDuration: 600,
    animationEasing: 'cubicOut',

    tooltip: {
      trigger: 'item',
      className: 'echarts-tooltip-custom',
      formatter: params => {
        const d = params.data[5];
        if (!d) return '';
        const netCls = d.broker_net >= 0 ? '#38d9a9' : '#fc8181';
        return `
          <div style="font-size:1rem;font-weight:700;margin-bottom:6px">
            ${d.id} ${d.name}
          </div>
          <div style="color:#a0b4d0;font-size:.78rem;margin-bottom:8px">${d.industry}</div>
          <table style="width:100%;border-collapse:collapse;font-size:.82rem">
            <tr><td style="color:#5d7898;padding:2px 0">大戶持股</td><td style="text-align:right;color:#3b9eff">${fmtPct(d.whale_pct)}</td></tr>
            <tr><td style="color:#5d7898">散戶持股</td><td style="text-align:right;color:#fc8181">${fmtPct(d.retail_pct)}</td></tr>
            <tr><td style="color:#5d7898">分點淨買超</td><td style="text-align:right;color:${netCls}">${fmtNet(d.broker_net)}</td></tr>
            <tr><td style="color:#5d7898">股東人數</td><td style="text-align:right">${fmtNum(d.total_holders)}</td></tr>
          </table>
          <div style="margin-top:8px;font-size:.72rem;color:#3b9eff">點擊查看詳細分點</div>
        `;
      },
    },

    legend: {
      show: Object.keys(byIndustry).length <= 12,
      bottom: 8,
      textStyle: { color: '#5d7898', fontSize: 11 },
      icon: 'circle',
      itemWidth: 10,
      itemHeight: 10,
    },

    xAxis: {
      name: getAxisLabel(xKey),
      nameLocation: 'middle',
      nameGap: 30,
      nameTextStyle: { color: '#5d7898', fontSize: 11 },
      axisLine: { lineStyle: { color: 'rgba(99,179,237,.15)' } },
      splitLine: { lineStyle: { color: 'rgba(99,179,237,.06)' } },
      axisLabel: { color: '#5d7898', fontSize: 11 },
    },

    yAxis: {
      name: getAxisLabel(yKey),
      nameLocation: 'middle',
      nameGap: 50,
      nameTextStyle: { color: '#5d7898', fontSize: 11 },
      axisLine: { lineStyle: { color: 'rgba(99,179,237,.15)' } },
      splitLine: { lineStyle: { color: 'rgba(99,179,237,.06)' } },
      axisLabel: { color: '#5d7898', fontSize: 11 },
    },

    grid: { top: 30, right: 30, bottom: 60, left: 70 },
    series,
  };

  bubbleChart.setOption(option, true);

  // 更新計數
  const countEl = document.getElementById('stock-count');
  if (countEl) countEl.textContent = `顯示 ${filtered.length} / ${rawData.length} 支股票`;
}

// ── 點擊泡泡 ─────────────────────────────────────────────
async function onBubbleClick(params) {
  const d = params?.data?.[5];
  if (!d) return;
  APP.selected.stock = d.id;

  // 切到大戶趨勢頁
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  document.getElementById('tab-holders')?.classList.add('active');
  document.getElementById('view-holders')?.classList.add('active');

  document.getElementById('holders-title').textContent = `${d.id} ${d.name} — 大戶/散戶趨勢`;
  renderHoldersTrend(d.id, d.name);
  renderBrokersTable(d.id, d.name, d._brokers);
}

// ─────────────────────────────────────────────────────────
// 2. 大戶趨勢折線圖
// ─────────────────────────────────────────────────────────
async function renderHoldersTrend(stockId, stockName) {
  const el = document.getElementById('holders-chart');
  if (!el) return;
  if (!holdersChart) {
    holdersChart = echarts.init(el, null, { renderer: 'canvas' });
    window.addEventListener('resize', () => holdersChart?.resize());
  }

  holdersChart.showLoading({
    text: '載入歷史資料…',
    color: '#3b9eff',
    textColor: '#5d7898',
    maskColor: 'rgba(8,12,20,.8)',
  });

  const history = await getHolderHistory(stockId);
  holdersChart.hideLoading();

  if (!history.length) {
    holdersChart.setOption({ title: { text: '無歷史資料', textStyle: { color: '#5d7898' } } });
    return;
  }

  const dates   = history.map(h => formatDate(h.date));
  const whales  = history.map(h => h.whale_pct);
  const retails = history.map(h => h.retail_pct);
  const mids    = history.map(h => h.mid_pct);

  holdersChart.setOption({
    backgroundColor: 'transparent',
    animation: true,
    tooltip: {
      trigger: 'axis',
      className: 'echarts-tooltip-custom',
      formatter: params => {
        const d = params[0].axisValue;
        return `<b>${d}</b><br>` + params.map(p =>
          `<span style="color:${p.color}">●</span> ${p.seriesName}：${fmtPct(p.value)}`
        ).join('<br>');
      },
    },
    legend: {
      data: ['千張大戶', '散戶', '中小戶'],
      top: 8,
      textStyle: { color: '#5d7898', fontSize: 11 },
    },
    xAxis: {
      type: 'category',
      data: dates,
      axisLabel: { color: '#5d7898', fontSize: 10, rotate: 30 },
      axisLine: { lineStyle: { color: 'rgba(99,179,237,.15)' } },
    },
    yAxis: {
      type: 'value',
      name: '持股比例 (%)',
      nameTextStyle: { color: '#5d7898', fontSize: 11 },
      axisLabel: { color: '#5d7898', fontSize: 11 },
      splitLine: { lineStyle: { color: 'rgba(99,179,237,.06)' } },
    },
    grid: { top: 50, right: 30, bottom: 60, left: 65 },
    series: [
      {
        name: '千張大戶', type: 'line', data: whales,
        smooth: true, symbol: 'circle', symbolSize: 5,
        lineStyle: { color: '#3b9eff', width: 2.5 },
        itemStyle: { color: '#3b9eff' },
        areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [{ offset: 0, color: 'rgba(59,158,255,.25)' }, { offset: 1, color: 'rgba(59,158,255,.02)' }] } },
      },
      {
        name: '散戶', type: 'line', data: retails,
        smooth: true, symbol: 'circle', symbolSize: 5,
        lineStyle: { color: '#fc8181', width: 2 },
        itemStyle: { color: '#fc8181' },
        areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [{ offset: 0, color: 'rgba(252,129,129,.2)' }, { offset: 1, color: 'rgba(252,129,129,.02)' }] } },
      },
      {
        name: '中小戶', type: 'line', data: mids,
        smooth: true, symbol: 'circle', symbolSize: 4,
        lineStyle: { color: '#f6c90e', width: 1.5, type: 'dashed' },
        itemStyle: { color: '#f6c90e' },
      },
    ],
  });
}

// ─────────────────────────────────────────────────────────
// 3. 分點明細表格
// ─────────────────────────────────────────────────────────
function renderBrokersTable(stockId, stockName, brokersData) {
  document.getElementById('brokers-title').textContent = `${stockId} ${stockName} — 分點進出明細`;

  const fillTable = (tableId, rows, isNet) => {
    const tbody = document.querySelector(`#${tableId} tbody`);
    if (!tbody) return;
    if (!rows?.length) {
      tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--text-300);padding:20px">無資料</td></tr>';
      return;
    }
    tbody.innerHTML = rows.map(r => {
      const net = r.net ?? (r.buy - r.sell);
      const cls = net >= 0 ? 'net-pos' : 'net-neg';
      return `<tr>
        <td>${r.broker_id || '—'}</td>
        <td>${r.broker_name || '—'}</td>
        <td>${fmtNum(r.buy)}</td>
        <td>${fmtNum(r.sell)}</td>
        <td class="${cls}">${fmtNet(net)}</td>
      </tr>`;
    }).join('');
  };

  fillTable('table-buy',  brokersData?.top_buy,  false);
  fillTable('table-sell', brokersData?.top_sell, true);
}

// ── 全域 redrawBubble 供 filters.js 呼叫 ─────────────────
window.redrawBubble = redrawBubble;

// ── 初始化 ────────────────────────────────────────────────
APP.callbacks.push(initBubbleChart);
