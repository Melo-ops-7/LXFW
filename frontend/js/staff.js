/* 员工与后台逻辑（顾问 / 班主任 / 管理员） */
let me = null;

const MENUS = {
  '顾问': [
    ['workbench', '🏠', '工作台'], ['chat', '🤖', 'AI 业务助手'],
    ['leads', '👥', '客户管理'], ['reports', '📅', '我的日报'],
  ],
  '班主任': [
    ['workbench', '🏠', '工作台'], ['chat', '🤖', 'AI 业务助手'],
    ['leaves', '📝', '请假审批'], ['alerts', '🚨', '心理预警'],
    ['tickets', '🛠️', '反馈工单'], ['scores', '📊', '成绩管理'],
    ['reports', '📅', '我的日报'],
  ],
  '管理员': [
    ['overview', '📈', '数据总览'], ['chat', '🤖', 'AI 业务助手'],
    ['leads', '👥', '客户数据'], ['scores', '📊', '成绩数据'],
    ['alerts', '🚨', '预警数据'], ['tickets', '🛠️', '工单数据'],
    ['leaves', '📝', '请假数据'], ['users', '⚙️', '用户管理'],
    ['conversations', '💬', '对话记录'], ['system', '🩺', '系统健康'],
  ],
};

/* ---------- 登录 ---------- */
function showLogin() {
  document.getElementById('login-view').classList.remove('hidden');
  document.getElementById('app-view').classList.add('hidden');
}
function showApp() {
  document.getElementById('login-view').classList.add('hidden');
  document.getElementById('app-view').classList.remove('hidden');
  document.getElementById('sb-name').textContent = me.real_name;
  document.getElementById('sb-dept').textContent = (me.department || '') + ' · ' + me.employee_role;
  document.getElementById('sb-role').textContent = me.employee_role + '工作台';
  const menu = MENUS[me.employee_role] || MENUS['顾问'];
  document.getElementById('menu').innerHTML = menu.map(([k, icon, label], i) =>
    '<a data-page="' + k + '"' + (i === 0 ? ' class="active"' : '') + '>' + icon + ' <span>' + label + '</span></a>').join('');
  document.querySelectorAll('#menu a').forEach(a => a.onclick = () => navigate(a.dataset.page));
  navigate(menu[0][0]);
}
document.getElementById('lg-btn').onclick = async () => {
  try {
    const r = await api('/api/auth/login', { method: 'POST', noAuth: true, body: { username: document.getElementById('lg-user').value.trim(), password: document.getElementById('lg-pass').value } });
    if (r.user.user_type !== 'EMPLOYEE') { clearSession(); return toast('该账号不是员工账号，请前往学生入口', 'err'); }
    setSession(r.token, r.user); me = r.user; showApp();
  } catch (e) { toast(e.message, 'err'); }
};
document.getElementById('lg-pass').addEventListener('keydown', e => { if (e.key === 'Enter') document.getElementById('lg-btn').click(); });
document.querySelectorAll('[data-fill]').forEach(a => a.onclick = () => {
  document.getElementById('lg-user').value = a.dataset.fill;
  document.getElementById('lg-pass').value = a.dataset.fill === 'admin' ? 'admin123' : '123456';
});
document.getElementById('logout').onclick = () => { clearSession(); location.reload(); };

/* ---------- 路由 ---------- */
const pages = {};
function navigate(page) {
  document.querySelectorAll('#menu a').forEach(a => a.classList.toggle('active', a.dataset.page === page));
  pages[page]();
}
function head(title, sub) { return '<div class="page-head"><h1>' + title + '</h1><p>' + sub + '</p></div>'; }
const isAdmin = () => me.employee_role === '管理员';

/* ---------- 工作台 ---------- */
pages.workbench = async () => {
  const main = document.getElementById('main');
  main.innerHTML = head('工作台', me.real_name + ' · ' + me.employee_role + ' · ' + (me.department || '')) + '<div id="wb"><p class="muted">加载中…</p></div>';
  try {
    if (me.employee_role === '顾问') {
      const leads = await api('/api/employee/leads?owner_employee_id=' + me.id);
      const by = s => leads.filter(l => l.status === s).length;
      document.getElementById('wb').innerHTML =
        '<div class="grid stat-grid">' +
        '<div class="card stat-card"><div class="lbl">我的客户</div><div class="num">' + leads.length + '</div></div>' +
        '<div class="card stat-card"><div class="lbl">新增意向</div><div class="num">' + by('新增意向') + '</div></div>' +
        '<div class="card stat-card"><div class="lbl">跟进中</div><div class="num">' + by('跟进中') + '</div></div>' +
        '<div class="card stat-card"><div class="lbl">已签约</div><div class="num">' + by('已签约') + '</div></div></div>' +
        '<div class="card card-pad"><div class="section-title">待跟进客户</div>' +
        (leads.filter(l => l.status !== '已签约' && l.status !== '已流失').length ?
          '<table><tr><th>客户</th><th>联系方式</th><th>状态</th><th>背景</th></tr>' +
          leads.filter(l => l.status !== '已签约' && l.status !== '已流失').slice(0, 8).map(l =>
            '<tr><td>' + esc(l.customer_name) + '</td><td>' + esc(l.contact_info || '-') + '</td><td>' + statusTag(l.status) + '</td><td class="muted">' + esc((l.background_info || '').slice(0, 40)) + '</td></tr>').join('') + '</table>'
          : '<div class="empty">暂无待跟进客户</div>') + '</div>';
    } else {
      const [leaves, alerts, tickets] = await Promise.all([
        api('/api/student/leaves?status=待审批'), api('/api/student/alerts?status=未处理'), api('/api/student/feedbacks?status=待处理')]);
      document.getElementById('wb').innerHTML =
        '<div class="grid stat-grid">' +
        '<div class="card stat-card alert"><div class="lbl">待审批请假</div><div class="num">' + leaves.length + '</div></div>' +
        '<div class="card stat-card alert"><div class="lbl">未处理心理预警</div><div class="num">' + alerts.length + '</div></div>' +
        '<div class="card stat-card"><div class="lbl">待处理工单</div><div class="num">' + tickets.length + '</div></div>' +
        '<div class="card stat-card"><div class="lbl">今日待办合计</div><div class="num">' + (leaves.length + alerts.length + tickets.length) + '</div></div></div>' +
        '<div class="card card-pad"><div class="section-title">🚨 高危预警（请优先关注）</div>' +
        (alerts.length ? '<table><tr><th>学生</th><th>触发原因</th><th>风险</th><th>时间</th></tr>' +
          alerts.map(a => '<tr><td>' + esc(a.student_name || a.student_id) + '</td><td>' + esc(a.trigger_reason) + '</td><td>' + statusTag(a.risk_level) + '</td><td class="muted">' + esc(a.create_time) + '</td></tr>').join('') + '</table>'
          : '<div class="empty">暂无未处理预警</div>') + '</div>';
    }
  } catch (e) { document.getElementById('wb').innerHTML = '<div class="empty">' + esc(e.message) + '</div>'; }
};

/* ---------- AI 业务助手 ---------- */
pages.chat = () => {
  const main = document.getElementById('main');
  main.innerHTML = head('AI 业务助手', '口语化指令：查客户 / 录客户 / 更新状态 / 写日报 / 录成绩 / 审批请假 / 处理投诉，自动携带上下文') +
    '<div class="card chat-embed" id="chat-box"></div>';
  mountChat(document.getElementById('chat-box'), {
    agent: 'employee', embedded: true,
    chips: ['帮我查一下许同学的跟进记录', '查一下待审批的请假', '把许同学状态更新为已签约', '写日报：今天跟进3位客户，邀约2场分享会'],
    welcome: '你好 ' + esc(me.real_name) + '，我是员工业务助手 🤖\n支持口语化指令：**查客户、录客户、更新客户状态、写/查日报、录/查成绩、审批请假、处理投诉**，也可以解答新人指南与组织架构问题。'
  });
};

/* ---------- 客户管理 / 客户数据 ---------- */
pages.leads = async () => {
  const main = document.getElementById('main');
  main.innerHTML = head(isAdmin() ? '客户数据' : '客户管理', '意向客户录入、查询、跟进与状态流转（新增意向 → 跟进中 → 已签约 / 已流失）') +
    '<div class="card card-pad"><div class="toolbar">' +
    '<input id="ld-kw" placeholder="搜索姓名 / 背景关键词">' +
    '<select id="ld-status"><option value="">全部状态</option><option>新增意向</option><option>跟进中</option><option>已签约</option><option>已流失</option></select>' +
    (isAdmin() ? '' : '<label style="display:flex;align-items:center;gap:6px;font-size:13px;color:var(--ink-2)"><input type="checkbox" id="ld-mine" style="width:auto" checked>只看我的</label>') +
    '<button class="btn btn-outline btn-sm" id="ld-search">查询</button>' +
    '<button class="btn btn-primary btn-sm" id="ld-add">＋ 录入客户</button></div>' +
    '<div class="table-wrap" id="ld-list"></div></div>';
  const load = async () => {
    const kw = document.getElementById('ld-kw').value.trim();
    const st = document.getElementById('ld-status').value;
    const mine = document.getElementById('ld-mine');
    let q = '/api/employee/leads?';
    if (kw) q += 'keyword=' + encodeURIComponent(kw) + '&';
    if (st) q += 'status=' + encodeURIComponent(st) + '&';
    if (mine && mine.checked) q += 'owner_employee_id=' + me.id;
    const rows = await api(q);
    document.getElementById('ld-list').innerHTML = rows.length ?
      '<table><tr><th>ID</th><th>客户</th><th>联系方式</th><th>状态</th><th>负责员工</th><th>更新时间</th><th>操作</th></tr>' +
      rows.map(l => '<tr><td>' + l.id + '</td><td><b>' + esc(l.customer_name) + '</b><div class="muted">' + esc((l.background_info || '').slice(0, 30)) + '</div></td><td>' + esc(l.contact_info || '-') + '</td><td>' + statusTag(l.status) + '</td><td>' + esc(l.owner_name || l.owner_employee_id) + '</td><td class="muted">' + esc(l.update_time) + '</td>' +
        '<td style="white-space:nowrap"><button class="btn btn-outline btn-sm" data-view="' + l.id + '">详情</button> ' +
        '<select data-st="' + l.id + '" style="width:auto;padding:4px 8px;font-size:12px">' +
        ['新增意向', '跟进中', '已签约', '已流失'].map(s => '<option' + (s === l.status ? ' selected' : '') + '>' + s + '</option>').join('') + '</select></td></tr>').join('') + '</table>'
      : '<div class="empty">暂无客户记录</div>';
    document.querySelectorAll('[data-view]').forEach(b => b.onclick = () => leadDetail(+b.dataset.view));
    document.querySelectorAll('[data-st]').forEach(sel => sel.onchange = async () => {
      try {
        const r = await api('/api/employee/leads/' + sel.dataset.st + '/status', { method: 'POST', body: { status: sel.value } });
        toast(r.message, 'ok'); load();
      } catch (e) { toast(e.message, 'err'); load(); }
    });
  };
  document.getElementById('ld-search').onclick = load;
  document.getElementById('ld-kw').addEventListener('keydown', e => { if (e.key === 'Enter') load(); });
  const mine = document.getElementById('ld-mine');
  if (mine) mine.onchange = load;
  document.getElementById('ld-add').onclick = () => {
    openModal('录入意向客户',
      '<div class="form-row"><label>客户姓名 *</label><input name="name" placeholder="如：王家长"></div>' +
      '<div class="form-row"><label>联系方式</label><input name="phone" placeholder="手机号"></div>' +
      '<div class="form-row"><label>背景信息</label><textarea name="bg" rows="3" placeholder="年龄、学历、意向、预算等"></textarea></div>',
      async mask => {
        const name = val(mask, 'name');
        if (!name) throw new Error('请填写客户姓名');
        const r = await api('/api/employee/leads', { method: 'POST', body: { customer_name: name, contact_info: val(mask, 'phone') || null, background_info: val(mask, 'bg') || null, owner_employee_id: me.id } });
        toast(r.message, 'ok'); load();
      }, '录入');
  };
  load().catch(e => toast(e.message, 'err'));
};

async function leadDetail(id) {
  const l = await api('/api/employee/leads/' + id);
  const hist = Array.isArray(l.follow_up_history) ? l.follow_up_history : [];
  const mask = openModal('客户档案：' + l.customer_name,
    '<div class="detail-list">' +
    '<div class="item"><span class="k">联系方式</span><span>' + esc(l.contact_info || '-') + '</span></div>' +
    '<div class="item"><span class="k">当前状态</span><span>' + statusTag(l.status) + '</span></div>' +
    '<div class="item"><span class="k">背景信息</span><span>' + esc(l.background_info || '-') + '</span></div>' +
    '<div class="item"><span class="k">创建时间</span><span>' + esc(l.create_time) + '</span></div></div>' +
    '<div class="section-title" style="margin-top:16px">跟进历史</div>' +
    (hist.length ? '<div class="timeline">' + hist.map(h => '<div class="t-item"><div class="t-time">' + esc(h.time || '') + ' · ' + esc(h.by || '') + '</div><div>' + esc(h.note || '') + '</div></div>').join('') + '</div>' : '<p class="muted">暂无跟进记录</p>') +
    '<div class="form-row" style="margin-top:14px"><label>新增跟进记录</label><textarea name="note" rows="2" placeholder="本次沟通要点…"></textarea></div>' +
    '<button class="btn btn-primary btn-sm" data-follow>保存跟进</button>', null);
  mask.querySelector('[data-follow]').onclick = async () => {
    const note = val(mask, 'note');
    if (!note) return toast('请填写跟进内容', 'err');
    hist.push({ time: new Date().toLocaleString('zh-CN'), by: me.real_name, note });
    try {
      await api('/api/employee/leads/' + id, { method: 'PUT', body: { follow_up_history: JSON.stringify(hist) } });
      toast('跟进记录已保存', 'ok'); mask.remove();
    } catch (e) { toast(e.message, 'err'); }
  };
}

/* ---------- 日报 ---------- */
pages.reports = async () => {
  const main = document.getElementById('main');
  main.innerHTML = head('员工日报', '口述 / 写入日报，默认当天日期') +
    '<div class="grid" style="grid-template-columns:380px 1fr">' +
    '<div class="card card-pad"><div class="section-title">写日报</div>' +
    '<div class="form-row"><label>日期（可选，默认今天）</label><input id="rp-date" type="date"></div>' +
    '<div class="form-row"><label>日报内容 *</label><textarea id="rp-content" rows="5" placeholder="今日工作进展、关键产出、风险…"></textarea></div>' +
    '<button class="btn btn-primary" id="rp-btn" style="width:100%">提交日报</button></div>' +
    '<div class="card card-pad"><div class="section-title">日报列表' +
    (isAdmin() ? '<label style="font-size:12px;display:flex;gap:6px;align-items:center"><input type="checkbox" id="rp-all" style="width:auto" checked>全员</label>' : '') +
    '</div><div class="table-wrap" id="rp-list"></div></div></div>';
  const load = async () => {
    const all = document.getElementById('rp-all');
    const q = '/api/employee/reports' + (all && !all.checked ? '?employee_id=' + me.id : (isAdmin() ? '' : '?employee_id=' + me.id));
    const rows = await api(q);
    document.getElementById('rp-list').innerHTML = rows.length ?
      '<table><tr><th>日期</th><th>员工</th><th>内容</th></tr>' +
      rows.map(r => '<tr><td style="white-space:nowrap">' + esc(r.report_date) + '</td><td>' + esc(r.employee_name || r.employee_id) + '</td><td>' + esc(r.content) + '</td></tr>').join('') + '</table>'
      : '<div class="empty">暂无日报</div>';
  };
  document.getElementById('rp-btn').onclick = async () => {
    const content = document.getElementById('rp-content').value.trim();
    if (!content) return toast('请填写日报内容', 'err');
    try {
      const r = await api('/api/employee/reports', { method: 'POST', body: { employee_id: me.id, report_date: document.getElementById('rp-date').value || null, content } });
      toast(r.message, 'ok');
      document.getElementById('rp-content').value = '';
      load();
    } catch (e) { toast(e.message, 'err'); }
  };
  const all = document.getElementById('rp-all');
  if (all) all.onchange = load;
  load().catch(e => toast(e.message, 'err'));
};

/* ---------- 请假审批 / 请假数据 ---------- */
pages.leaves = async () => {
  const main = document.getElementById('main');
  const canApprove = me.employee_role !== '顾问';
  main.innerHTML = head(canApprove ? '请假审批' : '请假数据', '审批结论由人工确认后落库') +
    '<div class="card card-pad"><div class="toolbar">' +
    '<select id="lv-status"><option value="">全部状态</option><option>待审批</option><option>已通过</option><option>已驳回</option></select>' +
    '<button class="btn btn-outline btn-sm" id="lv-search">查询</button></div>' +
    '<div class="table-wrap" id="lv-list"></div></div>';
  const load = async () => {
    const st = document.getElementById('lv-status').value;
    const rows = await api('/api/student/leaves' + (st ? '?status=' + encodeURIComponent(st) : ''));
    document.getElementById('lv-list').innerHTML = rows.length ?
      '<table><tr><th>ID</th><th>学生</th><th>起止时间</th><th>事由</th><th>状态</th><th>审批人</th>' + (canApprove ? '<th>操作</th>' : '') + '</tr>' +
      rows.map(r => '<tr><td>' + r.id + '</td><td>' + esc(r.student_name || r.student_id) + '</td><td>' + esc(r.start_time || '-') + '<br>~ ' + esc(r.end_time || '-') + '</td><td>' + esc(r.reason || '-') + '</td><td>' + statusTag(r.status) + '</td><td>' + esc(r.approver_id || '-') + '</td>' +
        (canApprove ? '<td style="white-space:nowrap">' + (r.status === '待审批' ?
          '<button class="btn btn-ok btn-sm" data-ok="' + r.id + '">通过</button> <button class="btn btn-danger btn-sm" data-no="' + r.id + '">驳回</button>' : '-') + '</td>' : '') + '</tr>').join('') + '</table>'
      : '<div class="empty">暂无请假记录</div>';
    const act = async (id, approved) => {
      try {
        const r = await api('/api/student/leave/approve', { method: 'POST', body: { leave_id: id, approver_id: me.id, approved } });
        toast(r.message, 'ok'); load();
      } catch (e) { toast(e.message, 'err'); }
    };
    document.querySelectorAll('[data-ok]').forEach(b => b.onclick = () => act(+b.dataset.ok, true));
    document.querySelectorAll('[data-no]').forEach(b => b.onclick = () => act(+b.dataset.no, false));
  };
  document.getElementById('lv-search').onclick = load;
  load().catch(e => toast(e.message, 'err'));
};

/* ---------- 心理预警 ---------- */
pages.alerts = async () => {
  const main = document.getElementById('main');
  main.innerHTML = head('心理预警', '情绪分值 ≥70 自动高危预警；心情打卡连续3天低落→关注级、连续5天→高危，均通知班主任') +
    '<div class="card card-pad"><div class="toolbar">' +
    '<select id="al-status"><option value="">全部状态</option><option>未处理</option><option>跟进中</option><option>已解除</option></select>' +
    '<button class="btn btn-outline btn-sm" id="al-search">查询</button></div>' +
    '<div class="table-wrap" id="al-list"></div></div>';
  const load = async () => {
    const st = document.getElementById('al-status').value;
    const rows = await api('/api/student/alerts' + (st ? '?status=' + encodeURIComponent(st) : ''));
    document.getElementById('al-list').innerHTML = rows.length ?
      '<table><tr><th>ID</th><th>学生</th><th>触发原因</th><th>风险</th><th>状态</th><th>跟进老师</th><th>时间</th><th>操作</th></tr>' +
      rows.map(a => '<tr><td>' + a.id + '</td><td>' + esc(a.student_name || a.student_id) + '</td><td class="reason-cell">' + esc(a.trigger_reason) + '</td><td>' + statusTag(a.risk_level) + '</td><td>' + statusTag(a.status) + '</td><td>' + esc(a.teacher_name || '-') + '</td><td class="muted">' + esc(a.create_time) + '</td>' +
        '<td style="white-space:nowrap">' + (a.status !== '已解除' ?
          '<button class="btn btn-outline btn-sm" data-follow="' + a.id + '">跟进</button> <button class="btn btn-ok btn-sm" data-clear="' + a.id + '">解除</button> ' : '') +
        '<button class="btn btn-outline btn-sm" data-psy="' + a.student_id + '">画像</button></td></tr>').join('') + '</table>'
      : '<div class="empty">暂无预警记录</div>';
    const setStatus = async (id, status) => {
      try {
        const r = await api('/api/student/alerts/' + id + '/status', { method: 'POST', body: { status, teacher_id: me.id } });
        toast(r.message, 'ok'); load();
      } catch (e) { toast(e.message, 'err'); }
    };
    document.querySelectorAll('[data-follow]').forEach(b => b.onclick = () => setStatus(+b.dataset.follow, '跟进中'));
    document.querySelectorAll('[data-clear]').forEach(b => b.onclick = () => setStatus(+b.dataset.clear, '已解除'));
    document.querySelectorAll('[data-psy]').forEach(b => b.onclick = async () => {
      try {
        const p = await api('/api/student/psych-profile?student_id=' + b.dataset.psy);
        openModal('学生心理画像（ID ' + b.dataset.psy + '）',
          '<div class="detail-list">' +
          '<div class="item"><span class="k">最新情绪</span><span>' + esc(p.latest_emotion_tag || '-') + '（' + (p.emotion_score ?? '-') + '分）</span></div>' +
          '<div class="item"><span class="k">最近交互</span><span>' + esc(p.last_interaction_time || '-') + '</span></div>' +
          '<div class="item"><span class="k">历史条数</span><span>' + (p.emotion_history || []).length + '</span></div></div>' +
          '<div class="section-title" style="margin-top:14px">最近情绪记录</div>' +
          '<div class="timeline">' + (p.emotion_history || []).slice(-8).reverse().map(h =>
            '<div class="t-item"><div class="t-time">' + esc(h.time) + '</div><div>' + esc(h.tag) + ' · ' + h.score + '分</div></div>').join('') + '</div>', null);
      } catch (e) { toast(e.message, 'err'); }
    });
  };
  document.getElementById('al-search').onclick = load;
  load().catch(e => toast(e.message, 'err'));
};

/* ---------- 反馈工单 ---------- */
pages.tickets = async () => {
  const main = document.getElementById('main');
  main.innerHTML = head('反馈工单', '解决后状态置为「已解决」并自动标记已通知学生') +
    '<div class="card card-pad"><div class="toolbar">' +
    '<select id="tk-status"><option value="">全部状态</option><option>待处理</option><option>处理中</option><option>已解决</option></select>' +
    '<button class="btn btn-outline btn-sm" id="tk-search">查询</button></div>' +
    '<div class="table-wrap" id="tk-list"></div></div>';
  const load = async () => {
    const st = document.getElementById('tk-status').value;
    const rows = await api('/api/student/feedbacks' + (st ? '?status=' + encodeURIComponent(st) : ''));
    document.getElementById('tk-list').innerHTML = rows.length ?
      '<table><tr><th>ID</th><th>学生</th><th>内容</th><th>状态</th><th>解决方案</th><th>已通知</th><th>操作</th></tr>' +
      rows.map(t => '<tr><td>' + t.id + '</td><td>' + esc(t.student_name || t.student_id) + '</td><td>' + esc(t.content) + (t.detail ? '<div class="muted">' + esc(t.detail) + '</div>' : '') + '</td><td>' + statusTag(t.status) + '</td><td>' + esc(t.solution || '-') + '</td><td>' + (t.is_notified ? '<span class="tag tag-green">是</span>' : '<span class="tag tag-gray">否</span>') + '</td>' +
        '<td>' + (t.status !== '已解决' ? '<button class="btn btn-primary btn-sm" data-resolve="' + t.id + '">解决</button>' : '-') + '</td></tr>').join('') + '</table>'
      : '<div class="empty">暂无工单</div>';
    document.querySelectorAll('[data-resolve]').forEach(b => b.onclick = () => {
      openModal('解决工单 #' + b.dataset.resolve,
        '<div class="form-row"><label>解决方案 *</label><textarea name="sol" rows="3" placeholder="处理结果说明，将同步通知学生"></textarea></div>',
        async mask => {
          const sol = val(mask, 'sol');
          if (!sol) throw new Error('请填写解决方案');
          const r = await api('/api/student/feedback/' + b.dataset.resolve + '/resolve', { method: 'POST', body: { solution: sol } });
          toast(r.message, 'ok'); load();
        }, '确认解决');
    });
  };
  document.getElementById('tk-search').onclick = load;
  load().catch(e => toast(e.message, 'err'));
};

/* ---------- 成绩管理 ---------- */
pages.scores = async () => {
  const main = document.getElementById('main');
  main.innerHTML = head('成绩管理', '录入与查询学生成绩') +
    '<div class="grid" style="grid-template-columns:360px 1fr">' +
    '<div class="card card-pad"><div class="section-title">录入成绩</div>' +
    '<div class="form-row"><label>学生 *</label><select id="sc-student"></select></div>' +
    '<div class="form-row"><label>课程名称 *</label><input id="sc-course" placeholder="如：英语（预科）"></div>' +
    '<div class="form-row"><label>成绩 *</label><input id="sc-score" type="number" step="0.1" placeholder="如：88.5"></div>' +
    '<div class="form-row"><label>学期</label><input id="sc-term" placeholder="如：2026秋季"></div>' +
    '<button class="btn btn-primary" id="sc-btn" style="width:100%">录入</button></div>' +
    '<div class="card card-pad"><div class="section-title">成绩记录</div>' +
    '<div class="toolbar"><input id="sc-kw" placeholder="按课程名称筛选"><button class="btn btn-outline btn-sm" id="sc-search">查询</button></div>' +
    '<div class="table-wrap" id="sc-list"></div></div></div>';
  const students = await api('/api/employee/students');
  document.getElementById('sc-student').innerHTML = students.map(s => '<option value="' + s.id + '">' + esc(s.real_name) + '（' + esc(s.department || '') + '）</option>').join('');
  const load = async () => {
    const kw = document.getElementById('sc-kw').value.trim();
    const rows = await api('/api/employee/scores' + (kw ? '?course_name=' + encodeURIComponent(kw) : ''));
    document.getElementById('sc-list').innerHTML = rows.length ?
      '<table><tr><th>学生</th><th>课程</th><th>成绩</th><th>学期</th><th>录入时间</th></tr>' +
      rows.map(r => '<tr><td>' + esc(r.student_name || r.student_id) + '</td><td>' + esc(r.course_name) + '</td><td><b>' + r.score + '</b></td><td>' + esc(r.semester || '-') + '</td><td class="muted">' + esc(r.create_time) + '</td></tr>').join('') + '</table>'
      : '<div class="empty">暂无成绩记录</div>';
  };
  document.getElementById('sc-btn').onclick = async () => {
    const course = document.getElementById('sc-course').value.trim();
    const score = document.getElementById('sc-score').value;
    if (!course || score === '') return toast('请填写课程与成绩', 'err');
    try {
      const r = await api('/api/employee/scores', { method: 'POST', body: { student_id: +document.getElementById('sc-student').value, course_name: course, score: +score, semester: document.getElementById('sc-term').value.trim() || null } });
      toast(r.message, 'ok');
      document.getElementById('sc-course').value = ''; document.getElementById('sc-score').value = '';
      load();
    } catch (e) { toast(e.message, 'err'); }
  };
  document.getElementById('sc-search').onclick = load;
  load().catch(e => toast(e.message, 'err'));
};

/* ---------- 管理员：数据总览 ---------- */
pages.overview = async () => {
  const main = document.getElementById('main');
  main.innerHTML = head('数据总览', '客户 · 成绩 · 预警 · 工单 · 对话全域数据') + '<div id="ov-box"><p class="muted">加载中…</p></div>';
  const o = await api('/api/admin/overview');
  const byStatus = Object.fromEntries(o.leads_by_status.map(x => [x.status, x.n]));
  document.getElementById('ov-box').innerHTML =
    '<div class="grid stat-grid">' +
    '<div class="card stat-card"><div class="lbl">学生 / 员工</div><div class="num">' + o.students + ' <small>/ ' + o.employees + '</small></div></div>' +
    '<div class="card stat-card"><div class="lbl">意向客户</div><div class="num">' + o.leads_total + '</div></div>' +
    '<div class="card stat-card alert"><div class="lbl">未处理高危预警</div><div class="num">' + o.high_alerts + '</div></div>' +
    '<div class="card stat-card"><div class="lbl">待审批请假</div><div class="num">' + o.pending_leaves + '</div></div>' +
    '<div class="card stat-card"><div class="lbl">待处理工单</div><div class="num">' + o.pending_tickets + '</div></div>' +
    '<div class="card stat-card"><div class="lbl">成绩记录</div><div class="num">' + o.scores_total + '</div></div>' +
    '<div class="card stat-card"><div class="lbl">活动 / 报名</div><div class="num">' + o.events + ' <small>/ ' + o.registrations + '</small></div></div>' +
    '<div class="card stat-card"><div class="lbl">对话沉淀</div><div class="num">' + o.conversations + '</div></div></div>' +
    '<div class="grid" style="grid-template-columns:1fr 1fr">' +
    '<div class="card card-pad"><div class="section-title">客户状态分布</div>' +
    ['新增意向', '跟进中', '已签约', '已流失'].map(s => {
      const n = byStatus[s] || 0; const pct = o.leads_total ? Math.round(n / o.leads_total * 100) : 0;
      return '<div style="margin-bottom:10px"><div style="display:flex;justify-content:space-between;font-size:13px"><span>' + s + '</span><span>' + n + '（' + pct + '%）</span></div><div class="score-bar"><div class="bar" style="max-width:none"><i style="width:' + pct + '%;background:var(--primary)"></i></div></div></div>';
    }).join('') + '</div>' +
    '<div class="card card-pad"><div class="section-title">今日运营</div><div class="detail-list">' +
    '<div class="item"><span class="k">今日日报</span><span>' + o.reports_today + ' 份</span></div>' +
    '<div class="item"><span class="k">开放预警</span><span>' + o.open_alerts + ' 条</span></div>' +
    '<div class="item"><span class="k">活动报名</span><span>' + o.registrations + ' 人次</span></div>' +
    '<div class="item"><span class="k">对话记录</span><span>' + o.conversations + ' 条</span></div></div>' +
    '<p class="muted" style="margin-top:12px">智能报告（客户经营分析 / 心理健康周报等）为 P2 规划能力。</p></div></div>';
};

/* ---------- 管理员：用户管理 ---------- */
pages.users = async () => {
  const main = document.getElementById('main');
  main.innerHTML = head('用户管理', '统一用户表 sys_user：学生 / 员工（顾问 / 班主任 / 管理员）') +
    '<div class="card card-pad"><div class="toolbar">' +
    '<select id="us-type"><option value="">全部类型</option><option value="STUDENT">学生</option><option value="EMPLOYEE">员工</option></select>' +
    '<button class="btn btn-outline btn-sm" id="us-search">查询</button>' +
    '<button class="btn btn-primary btn-sm" id="us-add">＋ 新增用户</button></div>' +
    '<div class="table-wrap" id="us-list"></div></div>';
  const load = async () => {
    const t = document.getElementById('us-type').value;
    const rows = await api('/api/admin/users' + (t ? '?user_type=' + t : ''));
    document.getElementById('us-list').innerHTML =
      '<table><tr><th>ID</th><th>用户名</th><th>姓名</th><th>类型</th><th>角色</th><th>部门</th><th>状态</th><th>操作</th></tr>' +
      rows.map(u => '<tr><td>' + u.id + '</td><td>' + esc(u.username) + '</td><td>' + esc(u.real_name) + '</td><td>' + (u.user_type === 'STUDENT' ? '<span class="tag tag-teal">学生</span>' : '<span class="tag tag-blue">员工</span>') + '</td><td>' + esc(u.employee_role || '-') + '</td><td>' + esc(u.department || '-') + '</td><td>' + statusTag(u.status) + '</td>' +
        '<td>' + (u.username === 'admin' ? '-' : '<button class="btn btn-outline btn-sm" data-toggle="' + u.id + '" data-st="' + u.status + '">' + (u.status === '正常' ? '禁用' : '启用') + '</button>') + '</td></tr>').join('') + '</table>';
    document.querySelectorAll('[data-toggle]').forEach(b => b.onclick = async () => {
      try {
        await api('/api/admin/users/' + b.dataset.toggle + '/status', { method: 'POST', body: { status: b.dataset.st === '正常' ? '禁用' : '正常' } });
        toast('状态已更新', 'ok'); load();
      } catch (e) { toast(e.message, 'err'); }
    });
  };
  document.getElementById('us-search').onclick = load;
  document.getElementById('us-add').onclick = () => {
    openModal('新增用户',
      '<div class="form-grid">' +
      '<div class="form-row"><label>用户名 *</label><input name="username"></div>' +
      '<div class="form-row"><label>初始密码 *</label><input name="password" value="123456"></div>' +
      '<div class="form-row"><label>真实姓名 *</label><input name="real_name"></div>' +
      '<div class="form-row"><label>用户类型 *</label><select name="user_type"><option value="STUDENT">学生</option><option value="EMPLOYEE">员工</option></select></div>' +
      '<div class="form-row"><label>员工角色</label><select name="employee_role"><option value="">（学生不填）</option><option>顾问</option><option>班主任</option><option>管理员</option></select></div>' +
      '<div class="form-row"><label>部门</label><input name="department"></div>' +
      '<div class="form-row full"><label>联系方式</label><input name="contact_info"></div></div>',
      async mask => {
        const body = { username: val(mask, 'username'), password: val(mask, 'password'), real_name: val(mask, 'real_name'), user_type: val(mask, 'user_type'), employee_role: val(mask, 'employee_role') || null, department: val(mask, 'department') || null, contact_info: val(mask, 'contact_info') || null };
        if (!body.username || !body.password || !body.real_name) throw new Error('请填写必填项');
        await api('/api/admin/users', { method: 'POST', body });
        toast('用户已创建', 'ok'); load();
      }, '创建');
  };
  load().catch(e => toast(e.message, 'err'));
};

/* ---------- 管理员：对话记录 ---------- */
pages.conversations = async () => {
  const main = document.getElementById('main');
  main.innerHTML = head('对话记录', '各 Agent 对话沉淀，情绪标签作为心理画像原料') +
    '<div class="card card-pad"><div class="toolbar">' +
    '<select id="cv-agent"><option value="">全部 Agent</option><option value="student">学生管家</option><option value="employee">员工助手</option><option value="service">客服</option></select>' +
    '<button class="btn btn-outline btn-sm" id="cv-search">查询</button></div>' +
    '<div class="table-wrap" id="cv-list"></div></div>';
  const load = async () => {
    const a = document.getElementById('cv-agent').value;
    const rows = await api('/api/admin/conversations?limit=100' + (a ? '&agent_type=' + a : ''));
    const names = { student: '学生管家', employee: '员工助手', service: '客服' };
    document.getElementById('cv-list').innerHTML = rows.length ?
      '<table><tr><th>ID</th><th>用户</th><th>Agent</th><th>用户输入</th><th>AI 回复</th><th>情绪</th><th>时间</th></tr>' +
      rows.map(r => '<tr><td>' + r.id + '</td><td>' + esc(r.user_id) + '</td><td><span class="tag tag-blue">' + (names[r.agent_type] || r.agent_type) + '</span></td><td style="max-width:220px">' + esc((r.user_input || '').slice(0, 60)) + '</td><td style="max-width:260px" class="muted">' + esc((r.ai_reply || '').slice(0, 80)) + '</td><td>' + (r.emotion_tag ? statusTag(r.emotion_tag === '高危' ? '高' : r.emotion_tag === '负面' ? '中' : '低') + ' ' + esc(r.emotion_tag) : '-') + '</td><td class="muted">' + esc(r.create_time) + '</td></tr>').join('') + '</table>'
      : '<div class="empty">暂无对话记录</div>';
  };
  document.getElementById('cv-search').onclick = load;
  load().catch(e => toast(e.message, 'err'));
};

/* ---------- 管理员：系统健康 ---------- */
pages.system = async () => {
  const main = document.getElementById('main');
  main.innerHTML = head('系统健康', '后端 / 数据库 / Dify 集成状态') + '<div id="sys-box"><p class="muted">检测中…</p></div>';
  try {
    const [h, s] = await Promise.all([api('/api/health', { noAuth: true }), api('/api/admin/system')]);
    const agentNames = { student: '留学生智能管家', employee: '员工业务助手', service: '客服与活动' };
    document.getElementById('sys-box').innerHTML =
      '<div class="grid stat-grid">' +
      '<div class="card stat-card"><div class="lbl">后端服务</div><div class="num" style="font-size:20px;color:var(--ok)">● ' + esc(h.status) + '</div></div>' +
      '<div class="card stat-card"><div class="lbl">数据库</div><div class="num" style="font-size:20px;color:var(--ok)">● ' + esc(s.database) + '</div></div>' +
      '<div class="card stat-card"><div class="lbl">工具鉴权</div><div class="num" style="font-size:20px">' + esc(s.tool_api_key) + '</div></div>' +
      '<div class="card stat-card"><div class="lbl">降级策略</div><div class="num" style="font-size:15px">正则兜底 + 本地FAQ</div></div></div>' +
      '<div class="card card-pad"><div class="section-title">Dify Agent 集成状态</div>' +
      '<table><tr><th>Agent</th><th>API Key</th><th>说明</th></tr>' +
      Object.entries(s.dify_agents).map(([k, v]) => '<tr><td>' + agentNames[k] + '</td><td>' + (v === '已配置' ? '<span class="tag tag-green">已配置</span>' : '<span class="tag tag-orange">未配置</span>') + '</td><td class="muted">' + (v === '已配置' ? '对话经 Dify 编排（意图分类 + 知识库 + 工具调用）' : '对话降级为后端本地规则应答，配置 backend/.env 后重启生效') + '</td></tr>').join('') + '</table>' +
      '<p class="muted" style="margin-top:12px">Dify 应用导入与知识库配置见项目 dify/ 与 docs/Dify接入指南.md。</p></div>';
  } catch (e) { document.getElementById('sys-box').innerHTML = '<div class="empty">' + esc(e.message) + '</div>'; }
};

/* ---------- 启动 ---------- */
(async () => {
  if (getToken()) {
    try {
      me = await api('/api/auth/me');
      if (me.user_type === 'EMPLOYEE') { showApp(); return; }
    } catch { /* token 失效 */ }
    clearSession();
  }
  showLogin();
})();