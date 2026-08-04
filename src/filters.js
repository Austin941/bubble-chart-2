/**
 * 泡泡圖 2.0 — 篩選邏輯
 * 搜尋、軸線切換、日期切換
 */

let _searchKeyword = '';
let _xAxis = 'whale_pct';
let _yAxis = 'broker_net';
let _sizeAxis = 'total_holders';

// ── 搜尋 ─────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  const searchInput = document.getElementById('search-input');
  searchInput?.addEventListener('input', e => {
    _searchKeyword = e.target.value.trim().toLowerCase();
    redrawBubble();
  });

  // 軸線切換
  document.getElementById('x-axis-select')?.addEventListener('change', e => {
    _xAxis = e.target.value;
    redrawBubble();
  });
  document.getElementById('y-axis-select')?.addEventListener('change', e => {
    _yAxis = e.target.value;
    redrawBubble();
  });
  document.getElementById('size-select')?.addEventListener('change', e => {
    _sizeAxis = e.target.value;
    redrawBubble();
  });

  // 日期切換
  document.getElementById('date-select')?.addEventListener('change', async e => {
    const dateStr = e.target.value;
    APP.selected.date = dateStr;
    // 嘗試載入最近日期的分點資料
    const brokerDate = APP.dates.brokers.find(d => d <= dateStr) || APP.dates.brokers[0];
    if (brokerDate) await loadBrokers(brokerDate);
    await loadHolders(dateStr);
    redrawBubble();
  });

  // 標籤頁切換
  document.querySelectorAll('.nav-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
      btn.classList.add('active');
      const viewId = `view-${btn.dataset.view}`;
      document.getElementById(viewId)?.classList.add('active');
    });
  });

  // 直接搜尋分點排行
  const brokerSearchBtn = document.getElementById('broker-search-btn');
  const brokerSearchInput = document.getElementById('broker-search-input');
  if (brokerSearchBtn && brokerSearchInput) {
    const doBrokerSearch = async () => {
      const q = brokerSearchInput.value.trim();
      if (!q) return;
      const dateStr = APP.selected.date || APP.dates.brokers[0];
      if (!dateStr) return;
      
      const bData = APP.brokers[dateStr];
      if (!bData) {
        alert("目前尚無當日分點資料");
        return;
      }
      
      const stockInfo = bData.stocks?.[q];
      if (!stockInfo) {
        // 如果是名稱，嘗試反查代號
        const matchedId = Object.keys(APP.meta?.stocks || {}).find(id => APP.meta.stocks[id].name === q || id === q);
        if (matchedId && bData.stocks?.[matchedId]) {
          renderBrokersTable(matchedId, APP.meta.stocks[matchedId].name, bData.stocks[matchedId]);
        } else {
          alert(`找不到 ${q} 的當日分點資料。`);
        }
      } else {
        renderBrokersTable(q, getStockName(q), stockInfo);
      }
    };
    brokerSearchBtn.addEventListener('click', doBrokerSearch);
    brokerSearchInput.addEventListener('keypress', e => {
      if (e.key === 'Enter') doBrokerSearch();
    });
  }
});

// ── 過濾資料 ─────────────────────────────────────────────
function filterData(data) {
  if (!_searchKeyword) return data;
  return data.filter(d =>
    d.id.toLowerCase().includes(_searchKeyword) ||
    d.name.toLowerCase().includes(_searchKeyword)
  );
}

// ── 取得目前設定 ─────────────────────────────────────────
function getAxisConfig() {
  return { x: _xAxis, y: _yAxis, size: _sizeAxis };
}

function getAxisLabel(key) {
  const labels = {
    whale_pct:      '大戶持股 (%)',
    retail_pct:     '散戶持股 (%)',
    big_vs_retail:  '大戶 − 散戶差值',
    broker_net:     '分點淨買超（張）',
    total_holders:  '股東人數',
    whale_holders:  '千張大戶人數',
  };
  return labels[key] || key;
}
