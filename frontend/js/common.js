/* 新西方留学服务 前端公共库：API 封装 / 会话 / Toast / Markdown / 聊天组件 */
const API_BASE = '';

/* 会话按端作用域隔离：官网(service) / 学生端(student) / 员工端(staff)
 * 三端各自持有独立登录态，互不覆盖、互不挤下线 */
const PAGE_SCOPE = (() => {
  const p = location.pathname.toLowerCase();
  if (p.endsWith('student.html')) return 'student';
  if (p.endsWith('staff.html')) return 'staff';
  return 'service';
})();
const TOKEN_KEY = 'yj_token_' + PAGE_SCOPE;
const USER_KEY = 'yj_user_' + PAGE_SCOPE;
/* 清理旧版三端共用的键，避免残留干扰 */
localStorage.removeItem('yj_token');
localStorage.removeItem('yj_user');

function getToken() { return localStorage.getItem(TOKEN_KEY) || ''; }
function getUser() { try { return JSON.parse(localStorage.getItem(USER_KEY) || 'null'); } catch { return null; } }
function setSession(token, user) { localStorage.setItem(TOKEN_KEY, token); localStorage.setItem(USER_KEY, JSON.stringify(user)); }
function clearSession() { localStorage.removeItem(TOKEN_KEY); localStorage.removeItem(USER_KEY); }
function guestKey() {
  let k = localStorage.getItem('yj_guest');
  if (!k) { k = Math.random().toString(36).slice(2) + Date.now().toString(36); localStorage.setItem('yj_guest', k); }
  return k;
}

async function api(path, { method = 'GET', body, noAuth = false } = {}) {
  const headers = { 'Content-Type': 'application/json' };
  if (!noAuth && getToken()) headers['Authorization'] = 'Bearer ' + getToken();
  const resp = await fetch(API_BASE + path, { method, headers, body: body ? JSON.stringify(body) : undefined });
  let data = null;
  try { data = await resp.json(); } catch { /* ignore */ }
  if (!resp.ok) {
    const msg = (data && (data.detail || data.message)) || ('请求失败(' + resp.status + ')');
    if (resp.status === 401 && !noAuth) { clearSession(); }
    throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
  }
  return data;
}

function toast(msg, type = 'info') {
  let box = document.getElementById('toast-box');
  if (!box) { box = document.createElement('div'); box.id = 'toast-box'; document.body.appendChild(box); }
  const el = document.createElement('div');
  el.className = 'toast toast-' + type;
  el.textContent = msg;
  box.appendChild(el);
  setTimeout(() => el.remove(), 3200);
}

function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

/* 轻量 Markdown 渲染（标题/加粗/列表/表格/代码块） */
function md(text) {
  const lines = String(text ?? '').split('\n');
  let html = '', inCode = false, codeBuf = [], listType = null, tableBuf = [];
  const closeList = () => { if (listType) { html += '</' + listType + '>'; listType = null; } };
  const flushTable = () => {
    if (!tableBuf.length) return;
    const rows = tableBuf.filter(r => !/^\s*\|?[\s:|-]+\|?\s*$/.test(r));
    let t = '<table>';
    rows.forEach((r, i) => {
      const cells = r.replace(/^\||\|$/g, '').split('|').map(c => inline(c.trim()));
      t += '<tr>' + cells.map(c => (i === 0 ? '<th>' : '<td>') + c + (i === 0 ? '</th>' : '</td>')).join('') + '</tr>';
    });
    html += t + '</table>'; tableBuf = [];
  };
  const inline = s => esc(s)
    .replace(/\*\*(.+?)\*\*/g, '<b>$1</b>')
    .replace(/`([^`]+)`/g, '<code>$1</code>');
  for (const raw of lines) {
    if (raw.trim().startsWith('```')) {
      if (inCode) { html += '<pre>' + esc(codeBuf.join('\n')) + '</pre>'; codeBuf = []; inCode = false; }
      else { closeList(); flushTable(); inCode = true; }
      continue;
    }
    if (inCode) { codeBuf.push(raw); continue; }
    if (/^\s*\|.*\|\s*$/.test(raw)) { closeList(); tableBuf.push(raw); continue; }
    flushTable();
    const h = raw.match(/^(#{1,4})\s+(.*)/);
    if (h) { closeList(); html += '<h' + h[1].length + '>' + inline(h[2]) + '</h' + h[1].length + '>'; continue; }
    const ul = raw.match(/^\s*[-*]\s+(.*)/);
    const ol = raw.match(/^\s*\d+[.、]\s+(.*)/);
    if (ul || ol) {
      const want = ul ? 'ul' : 'ol';
      if (listType !== want) { closeList(); html += '<' + want + '>'; listType = want; }
      html += '<li>' + inline((ul || ol)[1]) + '</li>'; continue;
    }
    closeList();
    if (raw.trim() === '') { html += '<br>'; continue; }
    html += '<p>' + inline(raw) + '</p>';
  }
  if (inCode) html += '<pre>' + esc(codeBuf.join('\n')) + '</pre>';
  closeList(); flushTable();
  return html;
}

function statusTag(s) {
  const map = {
    '待审批': 'tag-orange', '已通过': 'tag-green', '已驳回': 'tag-red',
    '待处理': 'tag-orange', '处理中': 'tag-blue', '已解决': 'tag-green',
    '未处理': 'tag-red', '跟进中': 'tag-blue', '已解除': 'tag-green',
    '新增意向': 'tag-blue', '已签约': 'tag-green', '已流失': 'tag-gray',
    '正常': 'tag-green', '禁用': 'tag-red', '已报名': 'tag-green',
    '高': 'tag-red', '中': 'tag-orange', '低': 'tag-green',
  };
  return '<span class="tag ' + (map[s] || 'tag-gray') + '">' + esc(s) + '</span>';
}

/* ============ 聊天组件 ============
 * mountChat(container, {agent, title, subtitle, chips, embedded})
 * 上下文由后端 conversation_id 自动续接；支持重置。
 */
function mountChat(container, opts) {
  const { agent, title = '智能助手', subtitle = '', chips = [], embedded = false, freshStart = false } = opts;
  container.innerHTML =
    (embedded ? '' : '<div class="chat-head"><div><div class="t">' + esc(title) + '</div><div class="s">' + esc(subtitle) + '</div></div>' +
      '<div><button data-act="reset" title="重置上下文">⟳</button> <button data-act="close" title="收起">✕</button></div></div>') +
    '<div class="chat-body"></div>' +
    (chips.length ? '<div class="chat-chips">' + chips.map(c => '<button data-chip="' + esc(c) + '">' + esc(c) + '</button>').join('') + '</div>' : '') +
    '<div class="chat-input"><textarea placeholder="输入消息，Enter 发送…"></textarea><button class="btn btn-primary">发送</button></div>';
  const body = container.querySelector('.chat-body');
  const input = container.querySelector('textarea');
  const sendBtn = container.querySelector('.chat-input .btn');

  function addMsg(role, content, isMd) {
    const el = document.createElement('div');
    el.className = 'msg msg-' + role;
    if (isMd) el.innerHTML = md(content); else el.textContent = content;
    body.appendChild(el);
    body.scrollTop = body.scrollHeight;
    return el;
  }
  function sysMsg(t) { addMsg('sys', t); }

  async function send(text) {
    text = (text || input.value).trim();
    if (!text) return;
    input.value = '';
    addMsg('user', text);
    sendBtn.disabled = true;
    const tip = addMsg('ai', '');
    tip.innerHTML = '<span class="typing"><i></i><i></i><i></i></span>';
    try {
      const payload = { message: text };
      if (agent === 'service' && !getToken()) payload.session_key = guestKey();
      const data = await api('/api/chat/' + agent, { method: 'POST', body: payload, noAuth: agent === 'service' && !getToken() });
      tip.innerHTML = md(data.reply);
      if (data.degraded) sysMsg('当前为降级应答模式');
    } catch (e) {
      tip.innerHTML = '';
      tip.textContent = '发送失败：' + e.message;
    }
    sendBtn.disabled = false;
    body.scrollTop = body.scrollHeight;
    input.focus();
  }

  sendBtn.onclick = () => send();
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
  });
  container.querySelectorAll('[data-chip]').forEach(b => b.onclick = () => send(b.dataset.chip));
  const resetBtn = container.querySelector('[data-act="reset"]');
  if (resetBtn) resetBtn.onclick = async () => {
    try {
      const payload = agent === 'service' && !getToken() ? { session_key: guestKey() } : {};
      await api('/api/chat/reset?agent_type=' + agent, { method: 'POST', body: payload, noAuth: agent === 'service' && !getToken() });
      body.innerHTML = ''; sysMsg('上下文已重置，开始新对话');
    } catch (e) { toast(e.message, 'err'); }
  };
  const closeBtn = container.querySelector('[data-act="close"]');
  if (closeBtn) closeBtn.onclick = () => container.classList.add('hidden');

  // freshStart：刷新页面即开启新对话（重置上下文，不加载历史）；否则载入历史续接
  (async () => {
    if (freshStart) {
      try {
        const payload = agent === 'service' && !getToken() ? { session_key: guestKey() } : {};
        await api('/api/chat/reset?agent_type=' + agent, { method: 'POST', body: payload, noAuth: agent === 'service' && !getToken() });
      } catch { /* 重置失败不阻塞欢迎语 */ }
      addMsg('ai', opts.welcome || '你好，我是' + title + '，请问有什么可以帮您？', true);
      return;
    }
    try {
      const q = agent === 'service' && !getToken() ? '&session_key=' + guestKey() : '';
      const rows = await api('/api/chat/history?agent_type=' + agent + '&limit=30' + q, { noAuth: agent === 'service' && !getToken() });
      rows.forEach(r => {
        if (r.user_input === '[上下文已重置]') { sysMsg('—— 上下文已重置 ——'); return; }
        addMsg('user', r.user_input);
        if (r.ai_reply) addMsg('ai', r.ai_reply, true);
      });
    } catch { /* 首次无历史 */ }
    if (!body.children.length) {
      addMsg('ai', opts.welcome || '你好，我是' + title + '，请问有什么可以帮您？', true);
    }
  })();

  return { send, addMsg, sysMsg };
}

/* 弹窗 */
function openModal(title, innerHtml, onOk, okText = '确定') {
  const mask = document.createElement('div');
  mask.className = 'modal-mask';
  mask.innerHTML = '<div class="modal"><h3>' + esc(title) + '</h3><div class="modal-content">' + innerHtml +
    '</div><div class="modal-actions"><button class="btn btn-outline" data-x>取消</button>' +
    (onOk ? '<button class="btn btn-primary" data-ok>' + esc(okText) + '</button>' : '') + '</div></div>';
  document.body.appendChild(mask);
  mask.querySelector('[data-x]').onclick = () => mask.remove();
  mask.onclick = e => { if (e.target === mask) mask.remove(); };
  if (onOk) mask.querySelector('[data-ok]').onclick = async () => {
    try { await onOk(mask); mask.remove(); } catch (e) { toast(e.message, 'err'); }
  };
  return mask;
}

function val(mask, name) { const el = mask.querySelector('[name="' + name + '"]'); return el ? el.value.trim() : ''; }