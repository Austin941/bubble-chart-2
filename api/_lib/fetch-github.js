import zlib from 'zlib';
import { promisify } from 'util';
import fs from 'fs';
import path from 'path';

const gunzip = promisify(zlib.gunzip);
const BASE = 'https://raw.githubusercontent.com/Austin941/bubble-chart-2/master/';

export async function fetchGithubJson(filePath) {
  const localPath = path.resolve(process.cwd(), filePath);
  if (fs.existsSync(localPath)) {
    const content = fs.readFileSync(localPath, 'utf-8');
    return JSON.parse(content);
  }
  const res = await fetch(`${BASE}${filePath}`);
  if (!res.ok) throw new Error(`Fetch failed: ${filePath} (${res.status})`);
  return res.json();
}

export async function fetchGithubGz(filePath) {
  const localPath = path.resolve(process.cwd(), filePath);
  if (fs.existsSync(localPath)) {
    const buf = fs.readFileSync(localPath);
    const decompressed = await gunzip(buf);
    return JSON.parse(decompressed.toString('utf-8'));
  }
  const res = await fetch(`${BASE}${filePath}`);
  if (!res.ok) throw new Error(`Fetch failed: ${filePath} (${res.status})`);
  const buf = Buffer.from(await res.arrayBuffer());
  const decompressed = await gunzip(buf);
  return JSON.parse(decompressed.toString('utf-8'));
}
