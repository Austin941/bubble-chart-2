const BASE = 'https://raw.githubusercontent.com/Austin941/bubble-chart-2/master/';

export async function fetchGithubJson(path) {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`GitHub fetch failed: ${path} (${res.status})`);
  return res.json();
}

export async function fetchGithubGz(path) {
  const { ungzip } = await import('node-gzip');
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`GitHub fetch failed: ${path} (${res.status})`);
  const buf = Buffer.from(await res.arrayBuffer());
  const decompressed = await ungzip(buf);
  return JSON.parse(decompressed.toString('utf-8'));
}
