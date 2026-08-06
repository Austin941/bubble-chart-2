import * as duckdb from 'https://cdn.jsdelivr.net/npm/@duckdb/duckdb-wasm@1.28.0/+esm';

let db = null;
let conn = null;
let chartInstance = null;

async function initDuckDB() {
    const loadingEl = document.getElementById('history-loading');
    loadingEl.style.display = 'flex';
    
    try {
        const JSDELIVR_BUNDLES = duckdb.getJsDelivrBundles();
        const bundle = await duckdb.selectBundle(JSDELIVR_BUNDLES);
        
        const worker_url = URL.createObjectURL(
            new Blob([`importScripts("${bundle.mainWorker}");`], { type: 'text/javascript' })
        );
        
        const worker = new Worker(worker_url);
        const logger = new duckdb.ConsoleLogger();
        db = new duckdb.AsyncDuckDB(logger, worker);
        await db.instantiate(bundle.mainModule, bundle.pthreadWorker);
        URL.revokeObjectURL(worker_url);
        
        conn = await db.connect();
        
        // Register the remote parquet file
        // Handle different environments (local vs GitHub Pages)
        let basePath = window.location.pathname;
        if (basePath.endsWith('index.html')) basePath = basePath.replace('index.html', '');
        if (!basePath.endsWith('/')) basePath += '/';
        const parquetUrl = window.location.origin + basePath + 'data/brokers_history.parquet';
        
        // Register file URL to DuckDB virtual filesystem
        await db.registerFileURL('history.parquet', parquetUrl, duckdb.DuckDBDataProtocol.HTTP, false);
        
        console.log('DuckDB Initialized successfully');
    } catch (e) {
        console.error('Failed to init DuckDB:', e);
        alert('載入歷史資料庫失敗，請確認檔案路徑是否正確。');
    } finally {
        loadingEl.style.display = 'none';
    }
}

async function queryHistory(stockId, brokerName) {
    if (!conn) {
        await initDuckDB();
    }
    
    document.getElementById('history-title').textContent = `查詢中...`;
    
    try {
        const query = `
            SELECT date, buy, sell, net 
            FROM 'history.parquet' 
            WHERE stock_id = '${stockId}' 
              AND broker_name LIKE '%${brokerName}%'
            ORDER BY date ASC
        `;
        
        const result = await conn.query(query);
        const rows = result.toArray().map(r => r.toJSON());
        
        if (rows.length === 0) {
            document.getElementById('history-title').textContent = `找不到 ${stockId} 與 ${brokerName} 的歷史資料`;
            renderChart([], []);
            return;
        }
        
        const stockName = window.APP?.meta?.stocks?.[stockId]?.name || stockId;
        document.getElementById('history-title').textContent = `${stockName} (${stockId}) - ${brokerName} 歷史買賣超趨勢`;
        
        const dates = rows.map(r => r.date);
        const netValues = rows.map(r => r.net);
        
        renderChart(dates, netValues);
        
    } catch (e) {
        console.error(e);
        document.getElementById('history-title').textContent = `查詢失敗`;
    }
}

function renderChart(labels, data) {
    const ctx = document.getElementById('history-chart-canvas').getContext('2d');
    
    if (chartInstance) {
        chartInstance.destroy();
    }
    
    // Default color based on net value
    const backgroundColors = data.map(v => v >= 0 ? 'rgba(235, 64, 52, 0.7)' : 'rgba(52, 235, 95, 0.7)');
    const borderColors = data.map(v => v >= 0 ? 'rgb(235, 64, 52)' : 'rgb(52, 235, 95)');

    // eslint-disable-next-line no-undef
    chartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: '淨買賣超 (張)',
                data: data,
                backgroundColor: backgroundColors,
                borderColor: borderColors,
                borderWidth: 1,
                borderRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    labels: { color: '#a3aed0' }
                }
            },
            scales: {
                y: {
                    ticks: { color: '#a3aed0' },
                    grid: { color: 'rgba(255,255,255,0.05)' }
                },
                x: {
                    ticks: { color: '#a3aed0' },
                    grid: { color: 'rgba(255,255,255,0.05)' }
                }
            }
        }
    });
}

document.addEventListener('DOMContentLoaded', () => {
    const searchBtn = document.getElementById('history-search-btn');
    if (searchBtn) {
        searchBtn.addEventListener('click', () => {
            const stockId = document.getElementById('history-stock-input').value.trim();
            const brokerName = document.getElementById('history-broker-input').value.trim();
            
            if (!stockId || !brokerName) {
                alert('請輸入股票代號與分點名稱');
                return;
            }
            queryHistory(stockId, brokerName);
        });
    }
});
