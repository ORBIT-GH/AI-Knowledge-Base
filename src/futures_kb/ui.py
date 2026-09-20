"""Dependency-free web control panel for the local knowledge base."""

from __future__ import annotations


def render_ui() -> str:
    return '''<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AI Knowledge Base Control</title>
  <style>
    :root { color-scheme: light; font-family: "Microsoft YaHei", system-ui, sans-serif; }
    body { margin: 0; background: #f4f7fb; color: #162033; }
    main { max-width: 1120px; margin: 0 auto; padding: 32px 20px 64px; }
    h1 { margin: 0 0 8px; font-size: 30px; }
    .muted { color: #60708a; }
    .toolbar { display: flex; gap: 10px; align-items: center; margin: 24px 0; flex-wrap: wrap; }
    button { border: 0; border-radius: 8px; padding: 10px 16px; cursor: pointer; background: #1769e0; color: white; font-weight: 600; }
    button.secondary { background: #e4ebf5; color: #22324b; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; }
    .card { background: white; border: 1px solid #dfe6ef; border-radius: 14px; padding: 18px; box-shadow: 0 8px 28px rgba(23, 52, 88, .06); }
    .card h2 { margin: 0 0 12px; font-size: 20px; }
    .metric { display: flex; justify-content: space-between; gap: 10px; padding: 7px 0; border-bottom: 1px solid #eef2f7; }
    .metric:last-child { border-bottom: 0; }
    select, input { box-sizing: border-box; width: 100%; padding: 10px; border: 1px solid #cfd9e8; border-radius: 8px; background: white; }
    .api-key { max-width: 260px; }
    .actions { display: flex; gap: 8px; margin-top: 12px; }
    .status { padding: 10px 14px; border-radius: 8px; background: #eef5ff; color: #245a9f; }
    .error { background: #fff0f0; color: #a52323; }
  </style>
</head>
<body>
<main>
  <h1>AI Knowledge Base 控制台</h1>
  <div class="muted">FuturesIntelTool → AI-Knowledge-Base → OpenClaw</div>
  <div class="toolbar">
    <button onclick="loadContracts()">刷新合约</button>
    <button class="secondary" onclick="refreshSource()">刷新数据源</button>
    <input id="apiKey" class="api-key" type="password" placeholder="API Key（未设置可留空）" autocomplete="off">
    <button class="secondary" onclick="saveApiKey()">保存 Key</button>
    <span id="status" class="status">正在加载...</span>
  </div>
  <section>
    <h2>合约管理</h2>
    <div id="contracts" class="grid"></div>
  </section>
</main>
<script>
const statusEl = document.getElementById('status');
const contractsEl = document.getElementById('contracts');
const apiKeyEl = document.getElementById('apiKey');
apiKeyEl.value = sessionStorage.getItem('aiKbApiKey') || '';
function apiKey() {
  return apiKeyEl.value.trim();
}
function saveApiKey() {
  sessionStorage.setItem('aiKbApiKey', apiKey());
  statusEl.textContent = 'API Key 已保存到当前浏览器会话';
  loadContracts();
}
function headers() {
  const value = { 'Content-Type': 'application/json' };
  const key = apiKey();
  if (key) value['X-API-Key'] = key;
  return value;
}
async function request(url, options = {}) {
  const response = await fetch(url, { ...options, headers: { ...headers(), ...(options.headers || {}) } });
  const text = await response.text();
  let payload = null;
  try { payload = text ? JSON.parse(text) : null; } catch { payload = { detail: text }; }
  if (!response.ok) throw new Error(payload?.detail || response.statusText);
  return payload;
}
function option(contract, selected) {
  const suffix = contract.is_main ? '（当前主力）' : '';
  return `<option value="${contract.contract}" ${selected === contract.contract ? 'selected' : ''}>${contract.contract}${suffix} · OI ${contract.open_interest ?? '-'}</option>`;
}
function render(data) {
  statusEl.textContent = `配置：${data.config_path || '-'}`;
  statusEl.classList.remove('error');
  contractsEl.innerHTML = data.products.map(product => {
    const options = product.available_contracts.map(item => option(item, product.override_contract || product.main_contract)).join('');
    return `<article class="card">
      <h2>${product.name} ${product.symbol}</h2>
      <div class="metric"><span>实际主力</span><strong>${product.main_contract || '-'}</strong></div>
      <div class="metric"><span>主力日期</span><strong>${product.main_contract_date || '-'}</strong></div>
      <div class="metric"><span>当前覆盖</span><strong>${product.override_contract || '自动主力'}</strong></div>
      <label>选择合约</label>
      <select id="contract-${product.symbol}">${options || '<option value="">暂无可用合约</option>'}</select>
      <div class="actions">
        <button onclick="saveContract('${product.symbol}')">保存覆盖</button>
        <button class="secondary" onclick="setAutomatic('${product.symbol}')">恢复自动主力</button>
      </div>
    </article>`;
  }).join('') || '<div class="card">没有配置品种</div>';
}
async function loadContracts() {
  try { render(await request('/api/v1/contracts')); }
  catch (error) { statusEl.textContent = error.message; statusEl.classList.add('error'); }
}
async function saveContract(symbol) {
  const contract = document.getElementById(`contract-${symbol}`).value;
  try {
    await request(`/api/v1/contracts/${symbol}`, { method: 'PUT', body: JSON.stringify({ contract }) });
    await loadContracts();
  } catch (error) { statusEl.textContent = error.message; statusEl.classList.add('error'); }
}
async function setAutomatic(symbol) {
  try {
    await request(`/api/v1/contracts/${symbol}`, { method: 'PUT', body: JSON.stringify({ contract: null }) });
    await loadContracts();
  } catch (error) { statusEl.textContent = error.message; statusEl.classList.add('error'); }
}
async function refreshSource() {
  const today = new Date().toLocaleDateString('sv-SE');
  statusEl.textContent = '正在刷新 FuturesIntelTool...';
  try {
    const result = await request(`/api/v1/crawlers/SH/run?trade_date=${today}`, { method: 'POST' });
    statusEl.textContent = `刷新状态：${result.status}${result.skipped ? '（数据已新鲜）' : ''}`;
  } catch (error) { statusEl.textContent = error.message; statusEl.classList.add('error'); }
}
loadContracts();
</script>
</body>
</html>'''
