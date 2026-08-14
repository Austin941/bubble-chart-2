// Local automated tester for Vercel Serverless Functions
import fs from 'fs';
import path from 'path';

// Mock response object
function createMockRes() {
  const headers = {};
  let statusCode = 200;
  let responseData = null;

  return {
    headers,
    statusCode,
    responseData,
    setHeader(k, v) {
      headers[k] = v;
    },
    status(code) {
      this.statusCode = code;
      return this;
    },
    json(data) {
      this.responseData = data;
      return this;
    },
    end() {
      return this;
    }
  };
}

async function runTests() {
  console.log("=== 🚀 Testing Vercel API Endpoints Locally ===\n");

  let passed = 0;
  let total = 0;

  function assert(name, condition, detail = "") {
    total++;
    if (condition) {
      console.log(`✅ [PASS] ${name}`);
      passed++;
    } else {
      console.error(`❌ [FAIL] ${name} ${detail ? `-> ${detail}` : ''}`);
    }
  }

  // Test 1: Trend API (System A)
  try {
    const trendHandler = (await import('../api/v1/stock/[sid]/trend.js')).default;
    const req = {
      method: 'GET',
      query: { sid: '2330', days: '30' }
    };
    const res = createMockRes();
    await trendHandler(req, res);

    assert("Trend API responds with status 200", res.statusCode === 200);
    assert("Trend API sets CORS header", res.headers['Access-Control-Allow-Origin'] === '*');
    assert("Trend API returns sid 2330", res.responseData?.sid === '2330');
    assert("Trend API returns brokers map", typeof res.responseData?.brokers === 'object');
    
    // Check if institutional or real broker exists
    const brokerKeys = Object.keys(res.responseData?.brokers || {});
    assert("Trend API contains broker records", brokerKeys.length > 0, `Found ${brokerKeys.length} brokers`);
    assert("Trend API includes '法人-外資'", '法人-外資' in (res.responseData?.brokers || {}));
  } catch (e) {
    assert("Trend API execution", false, e.message);
  }

  // Test 2: Single-day Ranking API (System B1)
  try {
    const rankingHandler = (await import('../api/v1/ranking/index.js')).default;
    const req = {
      method: 'GET',
      query: { date: '20260812', broker: '法人-外資', limit: '5' }
    };
    const res = createMockRes();
    await rankingHandler(req, res);

    assert("Ranking API (Single day) responds with status 200", res.statusCode === 200);
    assert("Ranking API sets CORS header", res.headers['Access-Control-Allow-Origin'] === '*');
    assert("Ranking API returns array of rankings", Array.isArray(res.responseData?.ranking));
    assert("Ranking API respects limit 5", res.responseData?.ranking?.length <= 5);
    
    if (res.responseData?.ranking?.length > 0) {
      const top1 = res.responseData.ranking[0];
      assert("Ranking item has required fields (sid, buy, sell, net, rank)", 
        'sid' in top1 && 'buy' in top1 && 'sell' in top1 && 'net' in top1 && 'rank' in top1);
    }
  } catch (e) {
    assert("Ranking API execution", false, e.message);
  }

  // Test 3: Specific Broker Ranking (e.g. 凱基台北 vs 凱基)
  try {
    const rankingHandler = (await import('../api/v1/ranking/index.js')).default;
    
    // Test 凱基台北
    const req1 = { method: 'GET', query: { date: '20260812', broker: '凱基台北', limit: '5' } };
    const res1 = createMockRes();
    await rankingHandler(req1, res1);
    assert("Ranking API supports specific branch '凱基台北'", res1.statusCode === 200);

    // Test 			凱基 general
    const req2 = { method: 'GET', query: { date: '20260812', broker: '凱基', limit: '5' } };
    const res2 = createMockRes();
    await rankingHandler(req2, res2);
    assert("Ranking API supports fuzzy aggregation '凱基'", res2.statusCode === 200);
  } catch (e) {
    assert("Specific Broker Ranking execution", false, e.message);
  }

  // Test 4: Range Ranking API (System B2)
  try {
    const rangeHandler = (await import('../api/v1/ranking/range.js')).default;
    const req = {
      method: 'GET',
      query: { from: '20260804', to: '20260812', broker: '法人-外資', limit: '5' }
    };
    const res = createMockRes();
    await rangeHandler(req, res);

    assert("Range Ranking API responds with status 200", res.statusCode === 200);
    assert("Range Ranking returns ranking list", Array.isArray(res.responseData?.ranking));
    assert("Range Ranking respects limit", (res.responseData?.ranking?.length || 0) <= 5);
  } catch (e) {
    assert("Range Ranking API execution", false, e.message);
  }

  console.log(`\n=== 📊 Test Summary: ${passed}/${total} passed ===`);
  if (passed === total) {
    console.log("🎉 All API pipelines and signal checks are 100% functional!");
  }
}

runTests();
