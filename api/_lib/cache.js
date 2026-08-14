export function setCacheHeader(res, dateStr) {
  const today = new Date().toISOString().slice(0,10).replace(/-/g,'');
  if (dateStr && dateStr < today) {
    res.setHeader('Cache-Control', 'public, s-maxage=86400, stale-while-revalidate=604800');
  } else {
    res.setHeader('Cache-Control', 'public, s-maxage=300, stale-while-revalidate=60');
  }
}
