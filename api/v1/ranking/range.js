import { setCors } from '../../_lib/cors.js';
import { setCacheHeader } from '../../_lib/cache.js';
import { fetchGithubJson, fetchGithubGz } from '../../_lib/fetch-github.js';

function getWeekKey(d) {
  // ISO week string: YYYY-Www
  const date = new Date(d);
  const thursday = new Date(date);
  thursday.setDate(date.getDate() - ((date.getDay() + 6) % 7) + 3);
  const year = thursday.getFullYear();
  const week = Math.ceil(((thursday - new Date(year, 0, 1)) / 86400000 + 1) / 7);
  return `${year}-W${String(week).padStart(2,'0')}`;
}

function dateRange(from, to) {
  const dates = [];
  for (let d = new Date(from.slice(0,4)+'-'+from.slice(4,6)+'-'+from.slice(6,8)); 
       d <= new Date(to.slice(0,4)+'-'+to.slice(4,6)+'-'+to.slice(6,8)); 
       d.setDate(d.getDate()+1)) {
    dates.push(d.toISOString().slice(0,10).replace(/-/g,''));
  }
  return dates;
}

function aggregateByBroker(allRecords, broker) {
  // allRecords: [{sid, name, buy, sell, net}]
  const map = {};
  for (const r of allRecords) {
    if (!r.name.includes(broker)) continue;
    if (!map[r.sid]) map[r.sid] = { sid: r.sid, buy: 0, sell: 0, net: 0, matched_labels: new Set() };
    map[r.sid].buy += r.buy;
    map[r.sid].sell += r.sell;
    map[r.sid].net += r.net;
    map[r.sid].matched_labels.add(r.name);
  }
  return Object.values(map).map(v => ({ ...v, matched_labels: [...v.matched_labels] }));
}

export default async function handler(req, res) {
  setCors(res);
  if (req.method === 'OPTIONS') return res.status(200).end();

  const { from, to, broker = '法人-外資', sort = 'net', limit = '20', dir = 'desc' } = req.query;
  if (!from || !to) return res.status(400).json({ error: 'from and to are required' });

  try {
    const dates = dateRange(from, to);
    const diffDays = dates.length;
    let allRecords = [];

    if (diffDays > 90) {
      // 讀月彙整
      const months = [...new Set(dates.map(d => d.slice(0,6)))];
      const files = await Promise.all(months.map(m => fetchGithubJson(`data/brokers/agg/monthly/${m}.json`).catch(() => null)));
      for (const file of files.filter(Boolean)) {
        for (const [sid, brokers] of Object.entries(file.stocks)) {
          for (const b of brokers) allRecords.push({ sid, ...b });
        }
      }
    } else if (diffDays > 22) {
      // 讀週彙整
      const weeks = [...new Set(dates.map(d => getWeekKey(d.slice(0,4)+'-'+d.slice(4,6)+'-'+d.slice(6,8))))];
      const files = await Promise.all(weeks.map(w => fetchGithubJson(`data/brokers/agg/weekly/${w}.json`).catch(() => null)));
      for (const file of files.filter(Boolean)) {
        for (const [sid, brokers] of Object.entries(file.stocks)) {
          for (const b of brokers) allRecords.push({ sid, ...b });
        }
      }
    } else {
      // 直接並行抓每日 .json.gz
      const files = await Promise.all(dates.map(d => fetchGithubGz(`data/brokers/${d}.json.gz`).catch(() => null)));
      for (const file of files.filter(Boolean)) {
        for (const [sid, stockData] of Object.entries(file.stocks)) {
          const all = [...(stockData.top_buy||[]), ...(stockData.top_sell||[])];
          for (const b of all) allRecords.push({ sid, name: b.broker_name, buy: b.buy, sell: b.sell, net: b.net });
        }
      }
    }

    const ranking = aggregateByBroker(allRecords, broker);
    const sortKey = sort === 'buy' ? 'buy' : sort === 'sell' ? 'sell' : 'net';
    ranking.sort((a, b) => dir === 'asc' ? a[sortKey] - b[sortKey] : b[sortKey] - a[sortKey]);
    const top = ranking.slice(0, parseInt(limit)).map((r, i) => ({ rank: i+1, ...r }));

    setCacheHeader(res, to);
    return res.json({ from, to, broker_query: broker, ranking: top });
  } catch (e) {
    return res.status(500).json({ error: e.message });
  }
}
