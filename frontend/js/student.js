/* 学生端逻辑 */
let me = null;

/* ---------- 登录 ---------- */
function showLogin() {
  document.getElementById('login-view').classList.remove('hidden');
  document.getElementById('app-view').classList.add('hidden');
}
function showApp() {
  document.getElementById('login-view').classList.add('hidden');
  document.getElementById('app-view').classList.remove('hidden');
  document.getElementById('sb-name').textContent = me.real_name;
  document.getElementById('sb-dept').textContent = me.department || '';
  navigate('home');
}
document.getElementById('lg-btn').onclick = async () => {
  try {
    const r = await api('/api/auth/login', { method: 'POST', noAuth: true, body: { username: document.getElementById('lg-user').value.trim(), password: document.getElementById('lg-pass').value } });
    if (r.user.user_type !== 'STUDENT') { clearSession(); return toast('该账号不是学生账号，请前往员工入口', 'err'); }
    setSession(r.token, r.user); me = r.user; showApp();
  } catch (e) { toast(e.message, 'err'); }
};
document.getElementById('lg-pass').addEventListener('keydown', e => { if (e.key === 'Enter') document.getElementById('lg-btn').click(); });
document.querySelectorAll('[data-fill]').forEach(a => a.onclick = () => {
  document.getElementById('lg-user').value = a.dataset.fill;
  document.getElementById('lg-pass').value = '123456';
});
document.getElementById('logout').onclick = () => { clearSession(); location.reload(); };

/* ---------- 路由 ---------- */
const pages = {};
function navigate(page) {
  document.querySelectorAll('#menu a').forEach(a => a.classList.toggle('active', a.dataset.page === page));
  pages[page]();
}
document.querySelectorAll('#menu a').forEach(a => a.onclick = () => navigate(a.dataset.page));

function head(title, sub) {
  return '<div class="page-head"><h1>' + title + '</h1><p>' + sub + '</p></div>';
}

/* ---------- 首页总览 ---------- */
const MOODS = [
  { v: 1, e: '😄', t: '很好' },
  { v: 2, e: '🙂', t: '还不错' },
  { v: 3, e: '😐', t: '一般' },
  { v: 4, e: '😞', t: '很低落' }
];

function renderMood(mood) {
  const box = document.getElementById('mood-box');
  if (!box) return;
  const todayLabel = mood.today ? '今日已打卡：' + MOODS[mood.today - 1].t + '（可点击修改）' : '点击按钮，记录今天的心情';
  box.innerHTML =
    '<div class="card card-pad mood-board"><div class="section-title">今天心情怎么样？<span class="muted">' + todayLabel + '</span></div>' +
    '<div class="mood-options">' + MOODS.map(m =>
      '<button class="mood-btn' + (mood.today === m.v ? ' selected' : '') + '" data-mood="' + m.v + '">' +
      '<span class="e">' + m.e + '</span><span class="t">' + m.t + '</span></button>').join('') + '</div>' +
    '<p class="muted" style="margin-top:10px">心情记录仅用于老师更好地关心你。连续几天情绪低落时，班主任会主动来陪伴你。</p>' +
    (mood.streak >= 3 ? '<p class="mood-care">最近连续 ' + mood.streak + ' 天心情低落，老师会多关心你。别一个人扛着，随时找老师聊聊 ❤️</p>' : '') + '</div>';
  box.querySelectorAll('[data-mood]').forEach(b => b.onclick = async () => {
    try {
      const r = await api('/api/student/mood', { method: 'POST', body: { student_id: me.id, mood: +b.dataset.mood } });
      toast(r.message, 'ok');
      const fresh = await api('/api/student/mood');
      renderMood(fresh);
    } catch (e) { toast(e.message, 'err'); }
  });
}

pages.home = async () => {
  const main = document.getElementById('main');
  main.innerHTML = head('你好，' + esc(me.real_name) + ' 👋', '这里是你的留学服务总览') + '<div id="ov"><p class="muted">加载中…</p></div>';
  try {
    const [ov, mood] = await Promise.all([
      api('/api/student/overview?student_id=' + me.id),
      api('/api/student/mood')
    ]);
    const pending = ov.leaves.filter(l => l.status === '待审批').length;
    const openTickets = ov.feedbacks.filter(t => t.status !== '已解决').length;
    document.getElementById('ov').innerHTML =
      '<div id="mood-box"></div>' +
      '<div class="grid stat-grid" style="grid-template-columns:repeat(3,1fr)">' +
      '<div class="card stat-card"><div class="lbl">待审批请假</div><div class="num">' + pending + '<small> 条</small></div></div>' +
      '<div class="card stat-card"><div class="lbl">成绩记录</div><div class="num">' + ov.scores.length + '<small> 条</small></div></div>' +
      '<div class="card stat-card"><div class="lbl">进行中工单</div><div class="num">' + openTickets + '<small> 条</small></div></div></div>' +
      '<div class="grid" style="grid-template-columns:1fr 1fr">' +
      '<div class="card card-pad"><div class="section-title">最近成绩</div>' +
      (ov.scores.length ? '<table><tr><th>课程</th><th>成绩</th><th>学期</th></tr>' + ov.scores.slice(0, 5).map(s => '<tr><td>' + esc(s.course_name) + '</td><td><b>' + s.score + '</b></td><td>' + esc(s.semester || '-') + '</td></tr>').join('') + '</table>' : '<div class="empty">暂无成绩</div>') + '</div>' +
      '<div class="card card-pad"><div class="section-title">快捷服务</div>' +
      '<div style="display:flex;flex-direction:column;gap:10px">' +
      '<button class="btn btn-outline" data-go="leave">📝 提交请假申请</button>' +
      '<button class="btn btn-outline" data-go="feedback">🛠️ 提交售后反馈</button>' +
      '<button class="btn btn-outline" data-go="chat">💬 和智能管家聊聊</button></div></div></div>';
    renderMood(mood);
    document.querySelectorAll('[data-go]').forEach(b => b.onclick = () => navigate(b.dataset.go));
  } catch (e) { document.getElementById('ov').innerHTML = '<div class="empty">' + esc(e.message) + '</div>'; }
};

/* ---------- 智能管家 ---------- */
pages.chat = () => {
  const main = document.getElementById('main');
  main.innerHTML = head('智能管家', '请假 · 查成绩 · 反馈 · 心理关怀 · 升学咨询，对话自动携带上下文') +
    '<div class="card chat-embed" id="chat-box"></div>';
  mountChat(document.getElementById('chat-box'), {
    agent: 'student', embedded: true,
    chips: ['我明天要请假一天，家里有事', '查一下我的成绩', '我最近压力有点大', '我想了解专升本项目'],
    welcome: '你好 ' + esc(me.real_name) + '，我是你的留学智能管家 🏠\n可以帮你**请假、查成绩、提交反馈**，也可以陪你聊聊心情、解答升学问题。'
  });
};

/* ---------- 请假 ---------- */
pages.leave = async () => {
  const main = document.getElementById('main');
  main.innerHTML = head('请假申请', '未填写时间时，系统自动从事由中解析（支持「明天/后天/半天/三天」等）') +
    '<div class="grid" style="grid-template-columns:380px 1fr">' +
    '<div class="card card-pad"><div class="section-title">新建请假</div>' +
    '<div class="form-row"><label>开始时间（可选）</label><input id="lv-start" type="datetime-local"></div>' +
    '<div class="form-row"><label>结束时间（可选）</label><input id="lv-end" type="datetime-local"></div>' +
    '<div class="form-row"><label>请假事由 *</label><textarea id="lv-reason" rows="3" placeholder="如：我明天要请假一天，家里有事"></textarea></div>' +
    '<button class="btn btn-primary" id="lv-btn" style="width:100%">提交申请</button></div>' +
    '<div class="card card-pad"><div class="section-title">我的请假记录</div><div class="table-wrap" id="lv-list"></div></div></div>';
  const load = async () => {
    const rows = await api('/api/student/leaves');
    document.getElementById('lv-list').innerHTML = rows.length ?
      '<table><tr><th>ID</th><th>类型</th><th>起止时间</th><th>事由</th><th>状态</th></tr>' +
      rows.map(r => '<tr><td>' + r.id + '</td><td>' + esc(r.service_type) + '</td><td>' + esc(r.start_time || '-') + '<br>~ ' + esc(r.end_time || '-') + '</td><td>' + esc(r.reason || '-') + '</td><td>' + statusTag(r.status) + '</td></tr>').join('') + '</table>'
      : '<div class="empty">暂无请假记录</div>';
  };
  document.getElementById('lv-btn').onclick = async () => {
    const reason = document.getElementById('lv-reason').value.trim();
    if (!reason) return toast('请填写请假事由', 'err');
    const fmt = v => v ? v.replace('T', ' ') + ':00' : null;
    try {
      const r = await api('/api/student/leave', { method: 'POST', body: { student_id: me.id, reason, start_time: fmt(document.getElementById('lv-start').value), end_time: fmt(document.getElementById('lv-end').value) } });
      toast(r.message, 'ok');
      document.getElementById('lv-reason').value = '';
      load();
    } catch (e) { toast(e.message, 'err'); }
  };
  load().catch(e => toast(e.message, 'err'));
};

/* ---------- 成绩 ---------- */
pages.score = async () => {
  const main = document.getElementById('main');
  main.innerHTML = head('我的成绩', '仅展示本人成绩记录') + '<div class="card card-pad"><div class="table-wrap" id="sc-list"></div></div>';
  const rows = await api('/api/student/scores');
  document.getElementById('sc-list').innerHTML = rows.length ?
    '<table><tr><th>课程</th><th>成绩</th><th>学期</th><th>录入时间</th></tr>' +
    rows.map(r => '<tr><td>' + esc(r.course_name) + '</td><td><div class="score-bar"><b>' + r.score + '</b><div class="bar"><i style="width:' + Math.min(100, r.score) + '%;background:' + (r.score >= 85 ? 'var(--ok)' : r.score >= 60 ? 'var(--primary)' : 'var(--danger)') + '"></i></div></div></td><td>' + esc(r.semester || '-') + '</td><td class="muted">' + esc(r.create_time) + '</td></tr>').join('') + '</table>'
    : '<div class="empty">暂无成绩记录</div>';
};

/* ---------- 售后反馈 ---------- */
pages.feedback = async () => {
  const main = document.getElementById('main');
  main.innerHTML = head('售后反馈', '提交投诉与建议，老师解决后系统自动通知') +
    '<div class="grid" style="grid-template-columns:380px 1fr">' +
    '<div class="card card-pad"><div class="section-title">新建反馈</div>' +
    '<div class="form-row"><label>内容摘要 *</label><input id="fb-content" placeholder="如：宿舍空调维修慢"></div>' +
    '<div class="form-row"><label>详细说明</label><textarea id="fb-detail" rows="4" placeholder="补充具体情况…"></textarea></div>' +
    '<button class="btn btn-primary" id="fb-btn" style="width:100%">提交工单</button></div>' +
    '<div class="card card-pad"><div class="section-title">我的工单</div><div class="table-wrap" id="fb-list"></div></div></div>';
  const load = async () => {
    const rows = await api('/api/student/feedbacks');
    document.getElementById('fb-list').innerHTML = rows.length ?
      '<table><tr><th>ID</th><th>内容</th><th>状态</th><th>解决方案</th><th>已通知</th></tr>' +
      rows.map(r => '<tr><td>' + r.id + '</td><td>' + esc(r.content) + (r.detail ? '<div class="muted">' + esc(r.detail) + '</div>' : '') + '</td><td>' + statusTag(r.status) + '</td><td>' + esc(r.solution || '-') + '</td><td>' + (r.is_notified ? '<span class="tag tag-green">是</span>' : '<span class="tag tag-gray">否</span>') + '</td></tr>').join('') + '</table>'
      : '<div class="empty">暂无工单</div>';
  };
  document.getElementById('fb-btn').onclick = async () => {
    const content = document.getElementById('fb-content').value.trim();
    if (!content) return toast('请填写内容摘要', 'err');
    try {
      const r = await api('/api/student/feedback', { method: 'POST', body: { student_id: me.id, content, detail: document.getElementById('fb-detail').value.trim() || null } });
      toast(r.message, 'ok');
      document.getElementById('fb-content').value = '';
      document.getElementById('fb-detail').value = '';
      load();
    } catch (e) { toast(e.message, 'err'); }
  };
  load().catch(e => toast(e.message, 'err'));
};

/* ---------- 启动 ---------- */
(async () => {
  if (getToken()) {
    try {
      me = await api('/api/auth/me');
      if (me.user_type === 'STUDENT') { showApp(); return; }
    } catch { /* token 失效 */ }
    clearSession();
  }
  showLogin();
})();