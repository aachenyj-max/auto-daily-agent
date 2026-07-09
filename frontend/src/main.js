document.addEventListener('DOMContentLoaded', () => {
  const datePicker = document.getElementById('date-picker');
  const btnPrev = document.getElementById('btn-prev');
  const btnNext = document.getElementById('btn-next');
  const btnToday = document.getElementById('btn-today');
  const btnReload = document.getElementById('btn-reload');
  const btnClearSearch = document.getElementById('btn-clear-search');
  const btnAgentSend = document.getElementById('btn-agent-send');
  const btnNewChat = document.getElementById('btn-new-chat');
  const btnClearChat = document.getElementById('btn-clear-chat');
  const btnRefreshList = document.getElementById('btn-refresh-list');
  const btnArchiveCurrent = document.getElementById('btn-archive-current');
  const btnRestoreCurrent = document.getElementById('btn-restore-current');
  const searchInput = document.getElementById('search-input');
  const recentList = document.getElementById('recent-list');
  const openReportLink = document.getElementById('open-report-link');
  const agentInput = document.getElementById('agent-input');
  const agentThread = document.getElementById('agent-thread');
  const agentContext = document.getElementById('agent-context');
  const chatTitle = document.getElementById('chat-title');
  const selectedReportMeta = document.getElementById('selected-report-meta');
  const modelStatus = document.getElementById('model-status');
  const jobPanel = document.getElementById('job-panel');
  const jobStep = document.getElementById('job-step');
  const jobMessage = document.getElementById('job-message');
  const jobProgress = document.getElementById('job-progress');
  const jobTask = document.getElementById('job-task');
  const managedReportList = document.getElementById('managed-report-list');
  const filterKeyword = document.getElementById('filter-keyword');
  const filterStatus = document.getElementById('filter-status');
  const filterType = document.getElementById('filter-type');
  const filterDateFrom = document.getElementById('filter-date-from');
  const filterDateTo = document.getElementById('filter-date-to');

  const STORAGE_KEY = 'auto_daily_recent';
  const CHAT_STORAGE_KEY = 'auto_daily_agent_chats';
  const DRAFT_CHAT_KEY = 'draft:new-task';
  let pollTimer = null;
  let selectedReport = null;
  let reportMap = new Map();
  let reportByFileName = new Map();
  let activeSubmission = null;
  let pendingClarification = null;
  let currentConversationKey = DRAFT_CHAT_KEY;
  const greetingCache = new Map();

  function todayStr() {
    return formatDate(new Date());
  }

  function formatDate(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  }

  function updateOpenReportLink(fileName) {
    openReportLink.href = `../output/${encodeURIComponent(fileName)}`;
  }

  function updateNavButtons() {
    btnNext.disabled = datePicker.value >= todayStr();
  }

  function getRecent() {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY)) || [];
    } catch {
      return [];
    }
  }

  function saveRecent(fileName) {
    const list = getRecent().filter(item => item !== fileName);
    list.unshift(fileName);
    if (list.length > 30) list.length = 30;
    localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
  }

  function updateRecentUI() {
    const list = getRecent();
    recentList.innerHTML = '';
    if (list.length === 0) {
      recentList.innerHTML = '<li class="empty-recent">暂无记录</li>';
      return;
    }

    list.forEach(fileName => {
      const record = reportByFileName.get(fileName);
      const li = document.createElement('li');
      const link = document.createElement('a');
      link.href = '#';
      link.textContent = record?.title || fileName;
      if (record?.title && record.title !== fileName) {
        link.title = fileName;
      }
      if (fileName === ReportViewer.currentFile) link.classList.add('active');
      link.addEventListener('click', async event => {
        event.preventDefault();
        const managedRecord = reportByFileName.get(fileName);
        if (managedRecord) {
          await openManagedReport(managedRecord);
          return;
        }
        ReportViewer.loadReportFile(fileName);
        updateOpenReportLink(fileName);
        saveRecent(fileName);
        updateRecentUI();
        clearSearch();
      });
      li.appendChild(link);
      recentList.appendChild(li);
    });
  }

  function clearSearch() {
    searchInput.value = '';
    ReportViewer.search('');
  }

  function setDate(dateStr) {
    datePicker.value = dateStr;
    updateOpenReportLink(`${dateStr}.md`);
    updateNavButtons();
    ReportViewer.loadReport(dateStr);
    saveRecent(`${dateStr}.md`);
    updateRecentUI();
    clearSearch();
  }

  function shiftDate(offset) {
    const current = datePicker.value || todayStr();
    const date = new Date(`${current}T00:00:00`);
    date.setDate(date.getDate() + offset);
    const max = new Date();
    max.setDate(max.getDate() + 1);
    if (date >= max) return;
    setDate(formatDate(date));
  }

  function reloadCurrent() {
    const file = ReportViewer.currentFile || `${datePicker.value || todayStr()}.md`;
    ReportViewer.loadReportFile(file);
    updateOpenReportLink(file);
    clearSearch();
  }

  function getStoredConversations() {
    try {
      return JSON.parse(localStorage.getItem(CHAT_STORAGE_KEY)) || {};
    } catch {
      return {};
    }
  }

  function saveStoredConversations(conversations) {
    localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(conversations));
  }

  function getConversationMessages(key = currentConversationKey) {
    const conversations = getStoredConversations();
    return Array.isArray(conversations[key]) ? conversations[key] : [];
  }

  function saveConversationMessages(messages, key = currentConversationKey) {
    const conversations = getStoredConversations();
    conversations[key] = messages.slice(-80);
    saveStoredConversations(conversations);
  }

  function reportSubject(record) {
    if (!record) return '';
    const scope = record.scope || {};
    const series = Array.isArray(scope.series) ? scope.series.filter(Boolean) : [];
    const brands = Array.isArray(scope.brands) ? scope.brands.filter(Boolean) : [];
    if (series.length >= 2 && record.report_type === 'compare') return series.slice(0, 2).join(' vs ');
    return series[0] || brands[0] || record.title || record.file_name || '当前报告';
  }

  function ruleGreeting(record) {
    if (!record) {
      return '告诉我你想生成哪类日报：品牌、车型、对比、价格筛选或市场总览。';
    }
    const subject = reportSubject(record);
    switch (record.report_type) {
      case 'brand':
        return `当前基于「${subject}」品牌日报。你可以继续追问销量结构、车型表现、价格区间或购买建议。`;
      case 'series':
        return `当前基于「${subject}」车型报告。你可以继续追问配置差异、价格走势、竞品对比或购买建议。`;
      case 'compare':
        return `当前基于「${subject}」对比报告。你可以继续追问优劣势、适合人群、价格配置或最终推荐。`;
      case 'filtered':
        return '当前基于筛选报告。你可以继续收窄预算、车身类型、能源形式或品牌范围。';
      case 'market':
        return '当前基于市场总览日报。你可以继续追问细分市场、品牌排名、价格带变化或购买窗口。';
      default:
        return `当前基于「${subject}」。你可以继续追问关键结论、风险点、车型对比或购买建议。`;
    }
  }

  function defaultConversationMessage(text = null, meta = '') {
    if (selectedReport) {
      return {
        role: 'assistant',
        text: text || ruleGreeting(selectedReport),
        meta: meta || '开场白',
        time: nowTimeText(),
        kind: 'greeting',
      };
    }
    return {
      role: 'assistant',
      text: text || ruleGreeting(null),
      meta: meta || '开场白',
      time: nowTimeText(),
      kind: 'greeting',
    };
  }

  function nowTimeText() {
    const date = new Date();
    return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;
  }

  function renderConversation(messages) {
    agentThread.innerHTML = '';
    const visibleMessages = messages.length ? messages : [defaultConversationMessage()];
    visibleMessages.forEach(item => renderAgentMessage(item.role, item.text, item.meta || '', item.time || ''));
    agentThread.scrollTop = agentThread.scrollHeight;
  }

  function isReplaceableGreeting(messages) {
    if (!messages.length) return true;
    if (messages.length !== 1) return false;
    const only = messages[0];
    if (only.kind === 'greeting') return true;
    if (only.role !== 'assistant') return false;
    const text = only.text || '';
    const meta = only.meta || '';
    return (
      meta.includes('开场白') ||
      meta.includes('规则模板') ||
      text === '输入新任务，或先在左侧选择一份报告后继续追问。' ||
      text.startsWith('已切换到 ')
    );
  }

  function renderAndStoreGreeting(greeting, meta = '开场白') {
    const message = defaultConversationMessage(greeting, meta);
    saveConversationMessages([message]);
    renderConversation([message]);
  }

  function renderAgentMessage(role, text, meta = '', time = '') {
    const message = document.createElement('div');
    message.className = `agent-message agent-message-${role}`;

    const roleLabel = document.createElement('span');
    roleLabel.className = 'agent-message-role';
    roleLabel.textContent = role === 'user' ? '你' : role === 'system' ? '系统' : 'Agent';

    const body = document.createElement('div');
    body.className = 'agent-message-body';
    body.textContent = text;

    message.appendChild(roleLabel);
    message.appendChild(body);

    const metaText = [meta, time].filter(Boolean).join(' | ');
    if (metaText) {
      const metaEl = document.createElement('span');
      metaEl.className = 'agent-message-meta';
      metaEl.textContent = metaText;
      message.appendChild(metaEl);
    }

    agentThread.appendChild(message);
  }

  function appendAgentMessage(role, text, meta = '') {
    const messages = getConversationMessages();
    messages.push({ role, text, meta, time: nowTimeText() });
    saveConversationMessages(messages);
    renderConversation(messages);
  }

  function getReportConversationKey(record) {
    return record?.report_id ? `report:${record.report_id}` : DRAFT_CHAT_KEY;
  }

  function setConversationKey(key) {
    currentConversationKey = key || DRAFT_CHAT_KEY;
    const messages = getConversationMessages();
    if (isReplaceableGreeting(messages)) {
      renderAndStoreGreeting(ruleGreeting(selectedReport), '规则模板');
    } else {
      renderConversation(messages);
    }
    refreshGreetingForCurrentContext();
  }

  async function refreshGreetingForCurrentContext() {
    const key = currentConversationKey;
    const existingMessages = getConversationMessages(key);
    if (!isReplaceableGreeting(existingMessages)) return;

    const cacheKey = selectedReport ? getReportConversationKey(selectedReport) : DRAFT_CHAT_KEY;
    if (greetingCache.has(cacheKey)) {
      if (key === currentConversationKey && isReplaceableGreeting(getConversationMessages(key))) {
        renderAndStoreGreeting(greetingCache.get(cacheKey).greeting, greetingCache.get(cacheKey).meta);
      }
      return;
    }

    if (!selectedReport) {
      greetingCache.set(cacheKey, { greeting: ruleGreeting(null), meta: '规则模板' });
      if (key === currentConversationKey && isReplaceableGreeting(getConversationMessages(key))) {
        renderAndStoreGreeting(ruleGreeting(null), '规则模板');
      }
      return;
    }

    const reportId = selectedReport.report_id;
    try {
      const data = await postJson('/api/reports/greeting', {
        mode: 'report',
        report_id: reportId,
      });
      const meta = data.llm_used ? 'LLM 开场白' : '规则模板';
      greetingCache.set(cacheKey, { greeting: data.greeting || ruleGreeting(selectedReport), meta });
      if (key === currentConversationKey && selectedReport?.report_id === reportId && isReplaceableGreeting(getConversationMessages(key))) {
        renderAndStoreGreeting(greetingCache.get(cacheKey).greeting, meta);
      }
    } catch {
      greetingCache.set(cacheKey, { greeting: ruleGreeting(selectedReport), meta: '规则模板' });
      if (key === currentConversationKey && selectedReport?.report_id === reportId && isReplaceableGreeting(getConversationMessages(key))) {
        renderAndStoreGreeting(ruleGreeting(selectedReport), '规则模板');
      }
    }
  }

  function clearCurrentConversation() {
    saveConversationMessages([]);
    renderConversation([]);
  }

  function startNewConversation() {
    pendingClarification = null;
    activeSubmission = null;
    selectedReport = null;
    setSelectedReport(null);
    managedReportList.querySelectorAll('.is-selected').forEach(item => {
      item.classList.remove('is-selected');
    });
    recentList.querySelectorAll('a.active').forEach(item => {
      item.classList.remove('active');
    });
    agentInput.value = '';
    agentInput.focus();
  }

  function migrateDraftConversation(targetKey) {
    if (!targetKey || targetKey === DRAFT_CHAT_KEY) return;
    const conversations = getStoredConversations();
    const draftMessages = Array.isArray(conversations[DRAFT_CHAT_KEY]) ? conversations[DRAFT_CHAT_KEY] : [];
    if (!draftMessages.length) return;
    const targetMessages = Array.isArray(conversations[targetKey]) ? conversations[targetKey] : [];
    conversations[targetKey] = [...targetMessages, ...draftMessages].slice(-80);
    conversations[DRAFT_CHAT_KEY] = [];
    saveStoredConversations(conversations);
  }

  function updateAgentPlaceholder() {
    if (pendingClarification) {
      agentInput.placeholder = '回答上面的问题，例如：小米YU7';
      return;
    }
    if (selectedReport) {
      agentInput.placeholder = '基于当前报告继续提问，例如：只看20万以内车型，再生成购买建议版';
      return;
    }
    agentInput.placeholder = '例如：生成今天小鹏汽车日报，重点分析 MONA M03';
  }

  function buildClarificationMessage(pending, answer) {
    return [
      `原始需求：${pending.originalPrompt}`,
      `Agent追问：${pending.question}`,
      `用户补充：${answer}`,
      '请基于上述补充信息继续完成受控日报任务。',
    ].join('\n');
  }

  function setSelectedReport(record) {
    selectedReport = record || null;
    if (!selectedReport) {
      selectedReportMeta.textContent = '未选中管理对象';
      agentContext.textContent = '新任务模式';
      chatTitle.textContent = '新任务';
      setConversationKey(DRAFT_CHAT_KEY);
      btnArchiveCurrent.disabled = true;
      btnRestoreCurrent.disabled = true;
      updateAgentPlaceholder();
      return;
    }

    selectedReportMeta.textContent = `${selectedReport.title} | ${selectedReport.report_type} | ${selectedReport.status}`;
    agentContext.textContent = `基于当前报告：${selectedReport.file_name}`;
    chatTitle.textContent = selectedReport.file_name;
    setConversationKey(getReportConversationKey(selectedReport));
    btnArchiveCurrent.disabled = selectedReport.status === 'archived';
    btnRestoreCurrent.disabled = selectedReport.status !== 'archived';
    updateAgentPlaceholder();
  }

  function renderManagedReports(items) {
    managedReportList.innerHTML = '';
    reportMap = new Map(items.map(item => [item.report_id, item]));
    reportByFileName = new Map(items.map(item => [item.file_name, item]).filter(([fileName]) => fileName));
    updateRecentUI();
    if (!items.length) {
      managedReportList.innerHTML = '<li class="managed-empty">没有匹配的报告</li>';
      setSelectedReport(null);
      return;
    }

    items.forEach(record => {
      const li = document.createElement('li');
      li.className = `managed-report-item ${record.status === 'archived' ? 'is-archived' : ''}`;
      if (selectedReport && selectedReport.report_id === record.report_id) {
        li.classList.add('is-selected');
      }

      const meta = [
        record.date || '-',
        record.report_type,
        ...(record.scope?.brands || []),
        ...(record.scope?.series || []),
      ].filter(Boolean).join(' | ');

      li.innerHTML = `
        <button class="managed-report-main" type="button" data-view-id="${record.report_id}">
          <span class="managed-report-title">${record.title || record.file_name}</span>
          <span class="managed-report-meta">${meta}</span>
          <span class="managed-report-excerpt">${record.summary?.excerpt || ''}</span>
        </button>
        <div class="managed-report-actions">
          <span class="report-badge">${record.status}</span>
          <button class="btn btn-secondary btn-small" type="button" data-view-id="${record.report_id}">查看</button>
          ${
            record.status === 'archived'
              ? `<button class="btn btn-secondary btn-small" type="button" data-restore-id="${record.report_id}">恢复</button>`
              : `
                <button class="btn btn-secondary btn-small" type="button" data-archive-id="${record.report_id}">归档</button>
                <button class="btn btn-danger btn-small" type="button" data-delete-id="${record.report_id}">删除</button>
              `
          }
        </div>
      `;
      managedReportList.appendChild(li);
    });

    managedReportList.querySelectorAll('[data-view-id]').forEach(button => {
      button.addEventListener('click', async () => {
        const record = reportMap.get(button.dataset.viewId);
        if (!record) return;
        await openManagedReport(record);
      });
    });

    managedReportList.querySelectorAll('[data-archive-id]').forEach(button => {
      button.addEventListener('click', async event => {
        event.stopPropagation();
        await archiveCurrentReport(button.dataset.archiveId);
      });
    });

    managedReportList.querySelectorAll('[data-delete-id]').forEach(button => {
      button.addEventListener('click', async event => {
        event.stopPropagation();
        await archiveCurrentReport(button.dataset.deleteId);
      });
    });

    managedReportList.querySelectorAll('[data-restore-id]').forEach(button => {
      button.addEventListener('click', async event => {
        event.stopPropagation();
        await restoreCurrentReport(button.dataset.restoreId);
      });
    });
  }

  async function openManagedReport(record) {
    const ok = await ReportViewer.loadReportRecord(record);
    if (!ok) return;
    updateOpenReportLink(record.file_name);
    saveRecent(record.file_name);
    updateRecentUI();
    clearSearch();
    setSelectedReport(record);
    datePicker.value = record.date || datePicker.value;
    updateNavButtons();
    await loadManagedReports(false);
  }

  function filtersToQuery() {
    const query = new URLSearchParams();
    if (filterKeyword.value.trim()) query.set('keyword', filterKeyword.value.trim());
    if (filterStatus.value) query.set('status', filterStatus.value);
    if (filterType.value) query.set('report_type', filterType.value);
    if (filterDateFrom.value) query.set('date_from', filterDateFrom.value);
    if (filterDateTo.value) query.set('date_to', filterDateTo.value);
    query.set('page', '1');
    query.set('page_size', '50');
    return query.toString();
  }

  async function loadManagedReports(resetSelection = true) {
    managedReportList.innerHTML = '<li class="managed-empty">正在加载报告列表...</li>';
    try {
      const resp = await fetch(`/api/reports/list?${filtersToQuery()}`);
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error || '加载报告列表失败');
      renderManagedReports(data.items || []);

      if (resetSelection) {
        if (selectedReport) {
          const fresh = (data.items || []).find(item => item.report_id === selectedReport.report_id);
          setSelectedReport(fresh || null);
        } else if (data.items && data.items.length) {
          setSelectedReport(data.items[0]);
        } else {
          setSelectedReport(null);
        }
      }
    } catch (error) {
      managedReportList.innerHTML = `<li class="managed-empty">${error.message}</li>`;
    }
  }

  async function loadRecentReportTitles() {
    try {
      const resp = await fetch('/api/reports/list?status=&page=1&page_size=500');
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error || '加载报告标题失败');
      reportByFileName = new Map((data.items || []).map(item => [item.file_name, item]).filter(([fileName]) => fileName));
      updateRecentUI();
    } catch {
      updateRecentUI();
    }
  }

  async function postJson(url, payload) {
    const resp = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || '请求失败');
    return data;
  }

  async function archiveCurrentReport(reportId = null) {
    const targetId = reportId || selectedReport?.report_id;
    if (!targetId) return;
    await postJson('/api/reports/archive', { report_ids: [targetId], reason: 'manual archive from workbench' });
    if (selectedReport && selectedReport.report_id === targetId) {
      selectedReport.status = 'archived';
      setSelectedReport(selectedReport);
    }
    await loadManagedReports(false);
  }

  async function restoreCurrentReport(reportId = null) {
    const targetId = reportId || selectedReport?.report_id;
    if (!targetId) return;
    await postJson('/api/reports/restore', { report_ids: [targetId] });
    if (selectedReport && selectedReport.report_id === targetId) {
      selectedReport.status = 'active';
      setSelectedReport(selectedReport);
    }
    await loadManagedReports(false);
  }

  function setJobState(job) {
    jobPanel.hidden = false;
    jobStep.textContent = job.step || job.status || 'running';
    const generation = job.generation || job.result?.generation;
    const workflowNotes = job.workflow_notes || job.result?.workflow_notes || [];
    const riskNotes = job.risk_notes || job.result?.risk_notes || [];
    const qualityIssues = job.quality_issues || job.result?.quality_issues || [];
    let message = job.message || '';

    if (generation) {
      if (generation.llm_used) {
        message = `${message} | 已使用正文 LLM`;
      } else if (generation.llm_requested && generation.llm_fallback_reason) {
        message = `${message} | 已回退：${generation.llm_fallback_reason}`;
      }
    }
    if (job.status === 'needs_input') {
      message = `需要确认：${job.message || '请补充信息后继续。'}`;
    }
    if (job.status === 'refused') {
      message = `已拒绝：${job.message || '请求超出安全边界。'}`;
    }
    if (workflowNotes.length) {
      message = `${message}\n工作流说明：${workflowNotes.join('；')}`;
    }
    if (riskNotes.length) {
      message = `${message}\n风险提示：${riskNotes.join('；')}`;
    }
    if (qualityIssues.length) {
      message = `${message}\n质量检查：${qualityIssues.join('；')}`;
    }

    jobMessage.textContent = message;
    jobProgress.style.width = `${Math.max(0, Math.min(100, job.progress || 0))}%`;
    if (job.output_name) {
      jobTask.textContent = `生成文件：${job.output_name}`;
    } else if (job.status === 'needs_input' || job.status === 'refused') {
      jobTask.textContent = job.message || '';
    } else {
      jobTask.textContent = '';
    }
  }

  async function submitAgentMessage() {
    const message = agentInput.value.trim();
    if (!message) {
      agentInput.focus();
      jobPanel.hidden = false;
      jobStep.textContent = 'input';
      jobMessage.textContent = '请输入要发送给 Agent 的内容。';
      jobProgress.style.width = '0%';
      jobTask.textContent = '';
      return;
    }

    appendAgentMessage('user', message);
    agentInput.value = '';
    btnAgentSend.disabled = true;
    btnAgentSend.textContent = '处理中';
    jobPanel.hidden = false;
    jobStep.textContent = 'queued';
    jobMessage.textContent = '正在创建任务';
    jobProgress.style.width = '6%';
    jobTask.textContent = '';

    try {
      const pending = pendingClarification;
      const sourceReportId = pending ? pending.sourceReportId : selectedReport?.report_id || null;
      const submittedMessage = pending ? buildClarificationMessage(pending, message) : message;
      const endpoint = sourceReportId ? '/api/reports/followup' : '/api/reports/generate';
      const payload = sourceReportId
        ? { report_id: sourceReportId, message: submittedMessage, use_llm: true }
        : { prompt: submittedMessage, use_llm: true };

      activeSubmission = {
        originalPrompt: pending?.originalPrompt || message,
        sourceReportId,
        userMessage: message,
      };
      pendingClarification = null;
      updateAgentPlaceholder();
      appendAgentMessage('assistant', sourceReportId ? '已收到，我会基于当前报告继续处理。' : '已收到，我会按新任务处理。');

      const data = await postJson(endpoint, payload);
      pollJob(data.job_id);
    } catch (error) {
      btnAgentSend.disabled = false;
      btnAgentSend.textContent = '发送';
      jobStep.textContent = 'error';
      jobMessage.textContent = error.message;
      jobProgress.style.width = '100%';
      appendAgentMessage('assistant', `任务创建失败：${error.message}`);
    }
  }

  async function loadLlmStatus() {
    if (!modelStatus) return;
    try {
      const resp = await fetch('/api/llm/status');
      const status = await resp.json();
      if (!resp.ok) throw new Error(status.error || '无法读取大模型状态');
      const workflow = status.workflow || {};
      const report = status.report || status;
      if (workflow.configured && report.configured) {
        modelStatus.textContent = `大模型已配置：工作流 ${workflow.model} | 正文 ${report.model}`;
        modelStatus.classList.remove('model-status-warning');
      } else {
        const missing = [];
        if (!workflow.configured) missing.push('工作流');
        if (!report.configured) missing.push('正文');
        modelStatus.textContent = `大模型未完整配置（${missing.join('、')}），必要时会回退规则模板`;
        modelStatus.classList.add('model-status-warning');
      }
    } catch (error) {
      modelStatus.textContent = `大模型状态未知：${error.message}`;
      modelStatus.classList.add('model-status-warning');
    }
  }

  function finishPolling() {
    clearInterval(pollTimer);
    btnAgentSend.disabled = false;
    btnAgentSend.textContent = '发送';
  }

  function pollJob(jobId) {
    clearInterval(pollTimer);
    pollTimer = setInterval(async () => {
      try {
        const resp = await fetch(`/api/reports/jobs/${encodeURIComponent(jobId)}`);
        const job = await resp.json();
        if (!resp.ok) throw new Error(job.error || '查询任务失败');
        setJobState(job);

        if (job.status === 'done') {
          finishPolling();
          pendingClarification = null;
          updateAgentPlaceholder();
          if (job.output_name) {
            await ReportViewer.loadReportFile(job.output_name);
            updateOpenReportLink(job.output_name);
            saveRecent(job.output_name);
            updateRecentUI();
            appendAgentMessage('assistant', `报告已生成：${job.output_name}`);
          }
          if (job.report_record) {
            if (activeSubmission && !activeSubmission.sourceReportId) {
              migrateDraftConversation(getReportConversationKey(job.report_record));
            }
            setSelectedReport(job.report_record);
          }
          await loadManagedReports(false);
        }

        if (['failed', 'needs_input', 'refused'].includes(job.status)) {
          finishPolling();
          if (job.status === 'needs_input') {
            pendingClarification = {
              question: job.message || '请补充信息后继续。',
              originalPrompt: activeSubmission?.originalPrompt || job.prompt || '',
              sourceReportId: job.source_report_id || activeSubmission?.sourceReportId || null,
            };
            appendAgentMessage('assistant', pendingClarification.question, '需要你确认');
            updateAgentPlaceholder();
            agentInput.focus();
          } else if (job.status === 'refused') {
            appendAgentMessage('assistant', job.message || '请求超出安全边界，已拒绝。');
          } else {
            appendAgentMessage('assistant', job.message || '任务失败。');
          }
          await loadManagedReports(false);
        }
      } catch (error) {
        finishPolling();
        jobStep.textContent = 'error';
        jobMessage.textContent = error.message;
        jobProgress.style.width = '100%';
        appendAgentMessage('assistant', `任务查询失败：${error.message}`);
      }
    }, 1200);
  }

  document.querySelectorAll('.quick-prompt').forEach(button => {
    button.addEventListener('click', () => {
      pendingClarification = null;
      agentInput.value = button.dataset.prompt || '';
      updateAgentPlaceholder();
      agentInput.focus();
    });
  });

  const today = todayStr();
  datePicker.value = today;
  datePicker.max = today;
  filterDateTo.max = today;
  filterDateFrom.max = today;
  updateOpenReportLink(`${today}.md`);
  updateNavButtons();
  loadLlmStatus();
  ReportViewer.loadReport(today);
  saveRecent(`${today}.md`);
  updateRecentUI();
  loadRecentReportTitles();
  loadManagedReports();
  setSelectedReport(null);

  btnPrev.addEventListener('click', () => shiftDate(-1));
  btnNext.addEventListener('click', () => shiftDate(1));
  btnToday.addEventListener('click', () => setDate(todayStr()));
  btnReload.addEventListener('click', reloadCurrent);
  btnClearSearch.addEventListener('click', clearSearch);
  btnAgentSend.addEventListener('click', submitAgentMessage);
  btnNewChat.addEventListener('click', startNewConversation);
  btnClearChat.addEventListener('click', clearCurrentConversation);
  btnRefreshList.addEventListener('click', () => loadManagedReports(false));
  btnArchiveCurrent.addEventListener('click', () => archiveCurrentReport());
  btnRestoreCurrent.addEventListener('click', () => restoreCurrentReport());

  [filterKeyword, filterStatus, filterType, filterDateFrom, filterDateTo].forEach(element => {
    const eventName = element.tagName === 'INPUT' && element.type === 'text' ? 'input' : 'change';
    element.addEventListener(eventName, () => loadManagedReports(true));
  });

  datePicker.addEventListener('change', event => {
    if (event.target.value) setDate(event.target.value);
  });

  agentInput.addEventListener('keydown', event => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      submitAgentMessage();
    }
  });

  let searchTimer = null;
  searchInput.addEventListener('input', () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      ReportViewer.search(searchInput.value.trim());
    }, 300);
  });

  document.addEventListener('keydown', event => {
    if ((event.ctrlKey || event.metaKey) && event.key === 'k') {
      event.preventDefault();
      searchInput.focus();
      searchInput.select();
    }
    if (event.key === 'ArrowLeft') {
      event.preventDefault();
      shiftDate(-1);
    }
    if (event.key === 'ArrowRight') {
      event.preventDefault();
      shiftDate(1);
    }
  });
});
