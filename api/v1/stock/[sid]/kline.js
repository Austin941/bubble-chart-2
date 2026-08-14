import { setCors } from '../../../_lib/cors.js';
import { setCacheHeader } from '../../../_lib/cache.js';

export default async function handler(req, res) {
  setCors(res);
  if (req.method === 'OPTIONS') return res.status(200).end();

  const { sid } = req.query;
  const { range = '3mo', interval = '1d' } = req.query;

  if (!sid) return res.status(400).json({ error: 'sid is required' });

  // Try .TW first, then .TWO
  const suffixes = ['.TW', '.TWO'];
  let chartData = null;

  for (const suffix of suffixes) {
    try {
      const url = `https://query1.finance.yahoo.com/v8/finance/chart/${sid}${suffix}?interval=${interval}&range=${range}`;
      const resp = await fetch(url, {
        headers: {
          'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
      });
      if (resp.ok) {
        const json = await resp.json();
        if (json?.chart?.result?.[0]?.timestamp?.length > 0) {
          chartData = json.chart.result[0];
          break;
        }
      }
    } catch (e) {
      // Continue to next suffix
    }
  }

  if (!chartData) {
    return res.status(404).json({ error: `K-line data not found for ${sid}` });
  }

  const ts = chartData.timestamp || [];
  const q = chartData.indicators?.quote?.[0] || {};
  const opens = q.open || [];
  const highs = q.high || [];
  const lows = q.low || [];
  const closes = q.close || [];
  const volumes = q.volume || [];

  const klines = [];
  for (let i = 0; i < ts.length; i++) {
    if (closes[i] !== null && closes[i] !== undefined) {
      const d = new Date(ts[i] * 1000);
      const dateStr = d.toISOString().slice(0, 10);
      klines.push({
        date: dateStr,
        open: Math.round(opens[i] * 100) / 100,
        high: Math.round(highs[i] * 100) / 100,
        low: Math.round(lows[i] * 100) / 100,
        close: Math.round(closes[i] * 100) / 100,
        volume: Math.round((volumes[i] || 0) / 1000) // in 張 (lots)
      });
    }
  }

  setCacheHeader(res, klines.at(-1)?.date?.replace(/-/g, ''));
  return res.json({
    symbol: sid,
    range,
    interval,
    klines
  });
}
