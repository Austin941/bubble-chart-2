import { setCors } from '../../_lib/cors.js';
import { setCacheHeader } from '../../_lib/cache.js';
import { fetchGithubGz } from '../../_lib/fetch-github.js';

export default async function handler(req, res) {
  setCors(res);
  if (req.method === 'OPTIONS') return res.status(200).end();

  const { date, broker = '法人-外資', sort = 'net', limit = '20', dir = 'desc' } = req.query;
  const targetDate = date || new Date().toISOString().slice(0,10).replace(/-/g,'');

  try {
    const data = await fetchGithubGz(`data/brokers/${targetDate}.json.gz`);

    const ranking = [];
    for (const [sid, stockData] of Object.entries(data.stocks)) {
      const allBrokers = [...(stockData.top_buy || []), ...(stockData.top_sell || [])];
      const matched = allBrokers.filter(b => b.broker_name.includes(broker));
      if (matched.length === 0) continue;

      const seen = new Set();
      let totalBuy = 0, totalSell = 0, totalNet = 0;
      const matchedLabels = [];
      for (const b of matched) {
        if (!seen.has(b.broker_name)) {
          seen.add(b.broker_name);
          matchedLabels.push(b.broker_name);
          totalBuy += b.buy; totalSell += b.sell; totalNet += b.net;
        }
      }
      ranking.push({ sid, buy: totalBuy, sell: totalSell, net: totalNet, matched_labels: matchedLabels });
    }

    const sortKey = sort === 'buy' ? 'buy' : sort === 'sell' ? 'sell' : 'net';
    ranking.sort((a, b) => dir === 'asc' ? a[sortKey] - b[sortKey] : b[sortKey] - a[sortKey]);
    const top = ranking.slice(0, parseInt(limit)).map((r, i) => ({ rank: i+1, ...r }));

    setCacheHeader(res, targetDate);
    return res.json({ date: targetDate, broker_query: broker, ranking: top });
  } catch (e) {
    return res.status(500).json({ error: e.message });
  }
}
