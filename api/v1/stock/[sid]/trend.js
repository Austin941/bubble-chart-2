import { setCors } from '../../../_lib/cors.js';
import { setCacheHeader } from '../../../_lib/cache.js';
import { fetchGithubJson } from '../../../_lib/fetch-github.js';

export default async function handler(req, res) {
  setCors(res);
  if (req.method === 'OPTIONS') return res.status(200).end();

  const { sid } = req.query;
  const { days = '30', from, to, broker, type = 'all' } = req.query;

  try {
    const data = await fetchGithubJson(`data/brokers/history/${sid}.json`);

    let filtered = data;
    if (from && to) {
      filtered = data.filter(d => d.date >= from && d.date <= to);
    } else {
      const cutoff = new Date();
      cutoff.setDate(cutoff.getDate() - parseInt(days));
      const cutoffStr = cutoff.toISOString().slice(0,10).replace(/-/g,'');
      filtered = data.filter(d => d.date >= cutoffStr);
    }

    const result = {};
    for (const dayData of filtered) {
      for (const b of dayData.brokers) {
        const isVirtual = b.name.startsWith('法人-') || b.name.startsWith('信用-');
        if (type === 'virtual' && !isVirtual) continue;
        if (type === 'real' && isVirtual) continue;
        if (broker && !b.name.includes(broker)) continue;

        if (!result[b.name]) result[b.name] = [];
        result[b.name].push({ date: dayData.date, buy: b.buy, sell: b.sell, net: b.net });
      }
    }

    setCacheHeader(res, filtered[0]?.date);
    return res.json({ sid, range: { from: filtered.at(-1)?.date, to: filtered[0]?.date }, brokers: result });
  } catch (e) {
    return res.status(500).json({ error: e.message });
  }
}
