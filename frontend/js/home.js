/* 官网首页逻辑 */
let allProjects = [];

async function loadProjects() {
  allProjects = await api('/api/courses', { noAuth: true });
  const cats = ['全部', ...new Set(allProjects.map(p => p.category))];
  const bar = document.getElementById('proj-filter');
  bar.innerHTML = cats.map((c, i) => '<button class="chip' + (i === 0 ? ' active' : '') + '" data-cat="' + esc(c) + '">' + esc(c) + '</button>').join('');
  bar.querySelectorAll('.chip').forEach(ch => ch.onclick = () => {
    bar.querySelectorAll('.chip').forEach(x => x.classList.remove('active'));
    ch.classList.add('active');
    renderProjects(ch.dataset.cat);
  });
  renderProjects('全部');
}

function projImg(cat) {
  if (cat.includes('德国')) return 'img/germany.jpg';
  if (cat.includes('就业')) return 'img/campus.jpg';
  return 'img/singapore.jpg';
}

function renderProjects(cat) {
  const list = cat === '全部' ? allProjects : allProjects.filter(p => p.category === cat);
  document.getElementById('proj-grid').innerHTML = list.map(p =>
    '<div class="card proj-card">' +
    '<div class="proj-media"><img src="' + projImg(p.category) + '" alt="' + esc(p.category) + '" loading="lazy">' +
    '<span class="tag tag-teal">' + esc(p.category) + '</span></div>' +
    '<div class="proj-body"><h3>' + esc(p.project_name) + '</h3><div class="desc">' + esc(p.description) + '</div>' +
    '<div class="aud">适合：' + esc(p.target_audience) + '</div>' +
    '<div style="margin-top:auto"><button class="btn btn-outline btn-sm" data-detail="' + p.id + '">查看详情</button> ' +
    '<button class="btn btn-primary btn-sm" onclick="openChat();askAbout(\'' + esc(p.project_name).replace(/'/g, '') + '\')">咨询该项目</button></div></div></div>'
  ).join('') || '<div class="empty">暂无项目</div>';
  document.querySelectorAll('[data-detail]').forEach(b => b.onclick = () => {
    const p = allProjects.find(x => x.id == b.dataset.detail);
    openModal(p.project_name,
      '<div class="detail-list">' +
      '<div class="item"><span class="k">类别</span><span>' + esc(p.category) + '</span></div>' +
      '<div class="item"><span class="k">适合人群</span><span>' + esc(p.target_audience) + '</span></div>' +
      '<div class="item"><span class="k">项目详情</span><span>' + esc(p.description) + '</span></div></div>', null);
  });
}

async function loadEvents() {
  const events = await api('/api/events', { noAuth: true });
  document.getElementById('event-list').innerHTML = events.map(e =>
    '<div class="event-row"><div class="info"><h4>' + esc(e.event_name) + ' ' +
    '<span class="tag ' + (e.event_type === '线上' ? 'tag-blue' : 'tag-teal') + '">' + esc(e.event_type) + '</span></h4>' +
    '<div class="muted">🕐 ' + esc(e.start_time) + '　📍 ' + esc(e.location) + '</div></div>' +
    '<div class="muted">剩余名额 ' + e.remaining + ' / ' + e.max_participants + '</div>' +
    (e.is_full ? '<button class="btn btn-outline btn-sm" disabled>名额已满</button>'
      : '<button class="btn btn-primary btn-sm" data-reg="' + e.id + '">立即报名</button>') + '</div>'
  ).join('') || '<div class="empty">暂无活动</div>';
  document.querySelectorAll('[data-reg]').forEach(b => b.onclick = () => {
    const e = events.find(x => x.id == b.dataset.reg);
    openModal('报名：' + e.event_name,
      '<div class="form-row"><label>姓名 *</label><input name="name" placeholder="您的姓名"></div>' +
      '<div class="form-row"><label>联系方式 *</label><input name="phone" placeholder="手机号"></div>' +
      '<p class="muted">时间：' + esc(e.start_time) + '<br>地点：' + esc(e.location) + '</p>',
      async mask => {
        const name = val(mask, 'name'), phone = val(mask, 'phone');
        if (!name || !phone) throw new Error('请填写姓名与联系方式');
        const r = await api('/api/events/register', { method: 'POST', noAuth: true, body: { event_id: e.id, customer_name: name, contact_info: phone } });
        toast(r.message, 'ok');
        loadEvents();
      }, '确认报名');
  });
}

async function loadFaq() {
  const faq = await api('/api/faq', { noAuth: true });
  const show = faq.slice(0, 8);
  document.getElementById('faq-list').innerHTML = show.map((f, i) =>
    '<div class="faq-item" data-i="' + i + '"><div class="q"><span>' + esc(f.q) + '</span><span>▾</span></div><div class="a">' + esc(f.a) + '</div></div>'
  ).join('');
  document.querySelectorAll('.faq-item').forEach(el => el.onclick = () => el.classList.toggle('open'));
}

/* 智能推荐 */
document.getElementById('rc-btn').onclick = async () => {
  const age = document.getElementById('rc-age').value;
  const edu = document.getElementById('rc-edu').value;
  const intent = document.getElementById('rc-intent').value;
  const extra = document.getElementById('rc-extra').value;
  const text = document.getElementById('rc-text').value;
  const raw = [age ? age + '岁' : '', edu ? edu + (edu === '初中' || edu === '高中' ? '毕业' : '学历') : '', intent ? '意向' + intent : '', extra, text].filter(Boolean).join('，');
  const box = document.getElementById('rc-result');
  box.innerHTML = '<p class="muted">正在匹配…</p>';
  try {
    const r = await api('/api/courses/recommend', {
      method: 'POST', noAuth: true,
      body: { raw_text: raw, age: age ? +age : null, education: edu || null, intent: intent || null }
    });
    if (!r.best_match) {
      box.innerHTML = '<div class="card card-pad" style="background:var(--warn-light)">' + esc(r.message || '未匹配到合适项目') + '</div>';
      return;
    }
    box.innerHTML =
      '<div class="card card-pad" style="border-color:var(--primary)">' +
      '<div class="section-title">🎯 最优推荐：' + esc(r.best_match.project) +
      '<span class="tag tag-blue">匹配度 ' + r.best_match.score + ' 分</span></div>' +
      '<p style="color:var(--ink-2)">' + esc(r.best_match.reason) + '</p>' +
      (r.best_match.detail ? '<p class="muted" style="margin-top:8px">适合人群：' + esc(r.best_match.detail.target_audience) + '</p>' : '') +
      '<div style="margin-top:12px"><button class="btn btn-primary btn-sm" onclick="openChat();askAbout(\'' + esc(r.best_match.project).replace(/'/g, '') + '\')">咨询顾问了解详情</button></div></div>' +
      (r.matches.length > 1 ? '<p class="muted" style="margin:10px 0 6px">其他候选：' +
        r.matches.slice(1).map(m => esc(m.project) + '（' + m.score + '分）').join('、') + '</p>' : '');
  } catch (e) { box.innerHTML = '<p class="muted">匹配失败：' + esc(e.message) + '</p>'; }
};

/* 留资 */
document.getElementById('lead-btn').onclick = async () => {
  const name = document.getElementById('lead-name').value.trim();
  const phone = document.getElementById('lead-phone').value.trim();
  const note = document.getElementById('lead-note').value.trim();
  if (!name || !phone) return toast('请填写姓名与联系方式', 'err');
  try {
    const r = await api('/api/leads/public', { method: 'POST', noAuth: true, body: { customer_name: name, contact_info: phone, background_info: note || '官网表单留资' } });
    toast(r.message, 'ok');
    document.getElementById('lead-name').value = '';
    document.getElementById('lead-phone').value = '';
    document.getElementById('lead-note').value = '';
  } catch (e) { toast(e.message, 'err'); }
};

/* 智能客服 */
let chatCtl = null;
function openChat() {
  const panel = document.getElementById('chat-panel');
  panel.classList.remove('hidden');
  document.getElementById('chat-fab').classList.add('hidden');
  if (!chatCtl) {
    chatCtl = mountChat(panel, {
      agent: 'service', freshStart: true, title: '新西方智能客服', subtitle: '公司咨询 · 政策解读 · 项目推荐 · 活动报名',
      chips: ['新加坡本科班学费多少？', '德国双元制报名要求', '推荐适合我的项目', '最近有什么活动？'],
      welcome: '您好，我是新西方留学服务智能客服 🎓 请问需要帮助吗？\n我可以为您提供**留学咨询、项目推荐、政策解读与活动报名**服务，有任何问题都可以直接问我。'
    });
    panel.querySelector('[data-act="close"]').onclick = () => {
      panel.classList.add('hidden');
      document.getElementById('chat-fab').classList.remove('hidden');
    };
  }
}
function askAbout(project) {
  setTimeout(() => chatCtl && chatCtl.send('请介绍一下' + project + '的学费、学制和报名流程'), 300);
}

loadProjects().catch(e => toast(e.message, 'err'));
loadEvents().catch(e => toast(e.message, 'err'));
loadFaq().catch(() => {});

/* 打开官网 3 秒后自动弹出智能客服，主动询问是否需要帮助与留学咨询 */
setTimeout(() => {
  const panel = document.getElementById('chat-panel');
  if (panel.classList.contains('hidden')) openChat();
}, 3000);

/* 滚动浮现（渐进增强：不支持 IntersectionObserver 时内容直接可见） */
if ('IntersectionObserver' in window) {
  const io = new IntersectionObserver(entries => entries.forEach(en => {
    if (en.isIntersecting) { en.target.classList.add('in'); io.unobserve(en.target); }
  }), { threshold: 0.08 });
  document.querySelectorAll('.site-section').forEach(el => { el.classList.add('reveal'); io.observe(el); });
}