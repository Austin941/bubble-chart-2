/**
 * 泡泡圖 2.0 — 資料載入器
 * 從 GitHub raw 或本地 data/ 讀取 JSON，管理狀態
 */

// ── 狀態管理 ─────────────────────────────────────────────
window.APP = {
  holders: {},      // { "20250718": { date, stocks: { "2330": {...} } } }
  brokers: {},      // { "20250718": { date, stocks: { "2330": {...} } } }
  meta: {},         // { stocks: { "2330": { name, industry } } }
  dates: {
    holders: [],    // 可用的週資料日期（降序）
    brokers: [],    // 可用的日資料日期（降序）
  },
  selected: {
    date: null,
    stock: null,
  },
  callbacks: [],
};

// ── 設定：資料來源 ────────────────────────────────────────
// 本地開發時直接讀 data/ 目錄；部署後改為 GitHub Raw URL
const IS_LOCAL = location.hostname === 'localhost' || location.hostname === '127.0.0.1';
const DATA_BASE = IS_LOCAL ? './data' : './data';  // Vercel 部署後直接讀相對路徑

// ── 核心：抓取單一 JSON ───────────────────────────────────
async function fetchJSON(path) {
  const resp = await fetch(path);
  if (!resp.ok) throw new Error(`HTTP ${resp.status} ${path}`);
  
  if (path.endsWith('.gz')) {
    try {
      const ds = new DecompressionStream('gzip');
      const decompressedStream = resp.body.pipeThrough(ds);
      const text = await new Response(decompressedStream).text();
      return JSON.parse(text);
    } catch (e) {
      console.error('Decompression failed for', path, e);
      throw e;
    }
  }
  
  return resp.json();
}

// ── 發現可用日期 ─────────────────────────────────────────
async function discoverDates() {
  try {
    const index = await fetchJSON(`${DATA_BASE}/index.json`);
    APP.dates.holders = (index.holders || []).sort().reverse();
    APP.dates.brokers = (index.brokers || []).sort().reverse();
  } catch {
    // 如果 index.json 不存在，嘗試讀取最近 N 天
    console.warn('data/index.json 不存在，使用預設日期範圍');
    const dates = generateRecentDates(90);
    APP.dates.holders = dates.filter((_, i) => i % 7 === 0); // 週
    APP.dates.brokers = dates;
  }
}

// ── 載入大戶/散戶週資料 ──────────────────────────────────
async function loadHolders(dateStr) {
  if (APP.holders[dateStr]) return APP.holders[dateStr];
  try {
    const data = await fetchJSON(`${DATA_BASE}/holders/${dateStr}.json`);
    APP.holders[dateStr] = data;
    return data;
  } catch (e) {
    console.warn(`holders/${dateStr}.json 不存在：`, e.message);
    return null;
  }
}

// ── 載入分點日資料 ────────────────────────────────────────
async function loadBrokers(dateStr) {
  if (APP.brokers[dateStr]) return APP.brokers[dateStr];
  try {
    try {
      const data = await fetchJSON(`${DATA_BASE}/brokers/${dateStr}.json.gz`);
      APP.brokers[dateStr] = data;
      return data;
    } catch (e) {
      const data = await fetchJSON(`${DATA_BASE}/brokers/${dateStr}.json`);
      APP.brokers[dateStr] = data;
      return data;
    }
  } catch (e) {
    console.warn(`brokers/${dateStr} 資料不存在：`, e.message);
    return null;
  }
}

// ── 載入 meta（股票名稱/產業） ────────────────────────────
async function loadMeta() {
  try {
    const data = await fetchJSON(`${DATA_BASE}/meta/stocks.json`);
    APP.meta = data;
    return data;
  } catch {
    APP.meta = { stocks: {} };
    return APP.meta;
  }
}

// ── 取得股票名稱 ─────────────────────────────────────────
function getStockName(stockId) {
  return APP.meta?.stocks?.[stockId]?.name || stockId;
}
function getStockIndustry(stockId) {
  return APP.meta?.stocks?.[stockId]?.industry || '其他';
}

// ── 合併當日大戶+分點資料 ────────────────────────────────
function mergeData(holdersDate, brokersDate) {
  const hData = APP.holders[holdersDate];
  const bData = APP.brokers[brokersDate];
  if (!hData) return [];

  const result = [];
  const hStocks = hData.stocks || {};
  const bStocks = bData?.stocks || {};

  for (const [sid, hInfo] of Object.entries(hStocks)) {
    const bInfo = bStocks[sid];
    result.push({
      id:             sid,
      name:           getStockName(sid),
      industry:       getStockIndustry(sid),
      whale_pct:      hInfo.whale_pct ?? 0,
      retail_pct:     hInfo.retail_pct ?? 0,
      mid_pct:        hInfo.mid_pct ?? 0,
      big_vs_retail:  hInfo.big_vs_retail ?? 0,
      whale_holders:  hInfo.whale_holders ?? 0,
      retail_holders: hInfo.retail_holders ?? 0,
      total_holders:  hInfo.total_holders ?? 0,
      broker_net:     bInfo?.summary?.net ?? 0,
      broker_buy:     bInfo?.summary?.total_buy ?? 0,
      broker_sell:    bInfo?.summary?.total_sell ?? 0,
      _holders:       hInfo,
      _brokers:       bInfo || null,
    });
  }
  return result;
}

// ── 取得某股票的歷史大戶走勢 ──────────────────────────────
async function getHolderHistory(stockId) {
  const history = [];
  for (const dateStr of APP.dates.holders.slice(0, 52)) { // 最多 52 週
    const data = await loadHolders(dateStr);
    if (data?.stocks?.[stockId]) {
      const s = data.stocks[stockId];
      history.push({
        date:       dateStr,
        whale_pct:  s.whale_pct,
        retail_pct: s.retail_pct,
        mid_pct:    s.mid_pct,
      });
    }
  }
  return history.reverse(); // 時間升序
}

// ── 填充日期選單 ─────────────────────────────────────────
function populateDateSelect() {
  const sel = document.getElementById('date-select');
  sel.innerHTML = '';
  const dates = APP.dates.holders;
  if (!dates.length) {
    sel.innerHTML = '<option>無資料</option>';
    return;
  }
  dates.slice(0, 30).forEach((d, i) => {
    const opt = document.createElement('option');
    opt.value = d;
    opt.textContent = formatDate(d);
    if (i === 0) opt.selected = true;
    sel.appendChild(opt);
  });
}

// ── 日期格式化 ───────────────────────────────────────────
function formatDate(dateStr) {
  if (!dateStr || dateStr.length < 8) return dateStr;
  return `${dateStr.slice(0,4)}/${dateStr.slice(4,6)}/${dateStr.slice(6,8)}`;
}

// ── 產生最近 N 天（fallback） ────────────────────────────
function generateRecentDates(n) {
  const dates = [];
  const d = new Date();
  for (let i = 1; i <= n; i++) {
    d.setDate(d.getDate() - 1);
    if (d.getDay() !== 0 && d.getDay() !== 6) { // 排除週末
      dates.push(d.toISOString().slice(0,10).replace(/-/g,''));
    }
  }
  return dates;
}

// ── 主初始化 ─────────────────────────────────────────────
async function initData() {
  showLoading(true);
  try {
    await Promise.all([discoverDates(), loadMeta()]);
    populateDateSelect();

    const latestHolders = APP.dates.holders[0];
    const latestBrokers = APP.dates.brokers[0];

    if (latestHolders) {
      await loadHolders(latestHolders);
      APP.selected.date = latestHolders;
    }
    if (latestBrokers) {
      await loadBrokers(latestBrokers);
    }

    // 更新頁首日期標籤
    const label = document.getElementById('update-label');
    if (label) {
      const maxDate = [latestHolders, latestBrokers].filter(Boolean).sort().reverse()[0];
      label.textContent = `最後更新：${formatDate(maxDate || '—')}`;
    }

    // 觸發圖表初始化
    APP.callbacks.forEach(cb => cb());

  } catch (e) {
    console.error('資料初始化失敗：', e);
  } finally {
    showLoading(false);
  }
}

function showLoading(show) {
  const el = document.getElementById('loading-overlay');
  if (el) el.classList.toggle('hidden', !show);
}

// DOM Ready
document.addEventListener('DOMContentLoaded', initData);
