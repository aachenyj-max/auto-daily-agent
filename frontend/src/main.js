document.addEventListener('DOMContentLoaded', () => {
  const datePicker = document.getElementById('date-picker');
  const btnPrev = document.getElementById('btn-prev');
  const btnNext = document.getElementById('btn-next');
  const btnToday = document.getElementById('btn-today');
  const btnReload = document.getElementById('btn-reload');
  const btnClearSearch = document.getElementById('btn-clear-search');
  const btnGenerate = document.getElementById('btn-generate');
  const btnRefreshList = document.getElementById('btn-refresh-list');
  const btnArchiveCurrent = document.getElementById('btn-archive-current');
  const btnRestoreCurrent = document.getElementById('btn-restore-current');
  const btnFollowup = document.getElementById('btn-followup');
  const searchInput = document.getElementById('search-input');
  const recentList = document.getElementById('recent-list');
  const openReportLink = document.getElementById('open-report-link');
  const promptInput = document.getElementById('generate-prompt');
  const followupInput = document.getElementById('followup-input');
  const followupTarget = document.getElementById('followup-target');
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
  let pollTimer = null;
  let selectedReport = null;
  let reportMap = new Map();

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
      const li = document.createElement('li');
      const link = document.createElement('a');
      link.href = '#';
      link.textContent = fileName;
      if (fileName === ReportViewer.currentFile) link.classList.add('active');
      link.addEventListener('click', event => {
        event.preventDefault();
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

  function setSelectedReport(record) {
    selectedReport = record || null;
    if (!selectedReport) {
      selectedReportMeta.textContent = '未选中管理对象';
      followupTarget.textContent = '当前未绑定报告';
      btnArchiveCurrent.disabled = true;
      btnRestoreCurrent.disabled = true;
      btnFollowup.disabled = true;
      return;
    }

    selectedReportMeta.textContent = `${selectedReport.title} | ${selectedReport.report_type} | ${selectedReport.status}`;
    followupTarget.textContent = `基于：${selectedReport.file_name}`;
    btnArchiveCurrent.disabled = selectedReport.status === 'archived';
    btnRestoreCurrent.disabled = selectedReport.status !== 'archived';
    btnFollowup.disabled = false;
  }

  function renderManagedReports(items) {
    managedReportList.innerHTML = '';
    reportMap = new Map(items.map(item => [item.report_id, item]));
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

  async function submitGenerate() {
    const prompt = promptInput.value.trim();
    if (!prompt) {
      promptInput.focus();
      jobPanel.hidden = false;
      jobStep.textContent = 'input';
      jobMessage.textContent = '请输入生成需求。';
      jobProgress.style.width = '0%';
      jobTask.textContent = '';
      return;
    }

    btnGenerate.disabled = true;
    btnGenerate.textContent = '生成中';
    jobPanel.hidden = false;
    jobStep.textContent = 'queued';
    jobMessage.textContent = '正在创建任务';
    jobProgress.style.width = '4%';
    jobTask.textContent = '';

    try {
      const data = await postJson('/api/reports/generate', { prompt, use_llm: true });
      pollJob(data.job_id);
    } catch (error) {
      btnGenerate.disabled = false;
      btnGenerate.textContent = '生成';
      jobStep.textContent = 'error';
      jobMessage.textContent = error.message;
      jobProgress.style.width = '100%';
    }
  }

  async function submitFollowup() {
    if (!selectedReport) {
      followupInput.focus();
      return;
    }
    const message = followupInput.value.trim();
    if (!message) {
      followupInput.focus();
      return;
    }

    btnFollowup.disabled = true;
    jobPanel.hidden = false;
    jobStep.textContent = 'queued';
    jobMessage.textContent = '正在创建 follow-up 任务';
    jobProgress.style.width = '6%';
    jobTask.textContent = '';

    try {
      const data = await postJson('/api/reports/followup', {
        report_id: selectedReport.report_id,
        message,
        use_llm: true,
      });
      pollJob(data.job_id);
    } catch (error) {
      btnFollowup.disabled = false;
      jobStep.textContent = 'error';
      jobMessage.textContent = error.message;
      jobProgress.style.width = '100%';
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
    btnGenerate.disabled = false;
    btnGenerate.textContent = '生成';
    btnFollowup.disabled = !selectedReport;
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
          if (job.output_name) {
            await ReportViewer.loadReportFile(job.output_name);
            updateOpenReportLink(job.output_name);
            saveRecent(job.output_name);
            updateRecentUI();
          }
          if (job.report_record) {
            setSelectedReport(job.report_record);
          }
          followupInput.value = '';
          await loadManagedReports(false);
        }

        if (['failed', 'needs_input', 'refused'].includes(job.status)) {
          finishPolling();
          await loadManagedReports(false);
        }
      } catch (error) {
        finishPolling();
        jobStep.textContent = 'error';
        jobMessage.textContent = error.message;
        jobProgress.style.width = '100%';
      }
    }, 1200);
  }

  document.querySelectorAll('.quick-prompt').forEach(button => {
    button.addEventListener('click', () => {
      promptInput.value = button.dataset.prompt || '';
      promptInput.focus();
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
  loadManagedReports();
  setSelectedReport(null);

  btnPrev.addEventListener('click', () => shiftDate(-1));
  btnNext.addEventListener('click', () => shiftDate(1));
  btnToday.addEventListener('click', () => setDate(todayStr()));
  btnReload.addEventListener('click', reloadCurrent);
  btnClearSearch.addEventListener('click', clearSearch);
  btnGenerate.addEventListener('click', submitGenerate);
  btnRefreshList.addEventListener('click', () => loadManagedReports(false));
  btnArchiveCurrent.addEventListener('click', () => archiveCurrentReport());
  btnRestoreCurrent.addEventListener('click', () => restoreCurrentReport());
  btnFollowup.addEventListener('click', submitFollowup);

  [filterKeyword, filterStatus, filterType, filterDateFrom, filterDateTo].forEach(element => {
    const eventName = element.tagName === 'INPUT' && element.type === 'text' ? 'input' : 'change';
    element.addEventListener(eventName, () => loadManagedReports(true));
  });

  datePicker.addEventListener('change', event => {
    if (event.target.value) setDate(event.target.value);
  });

  promptInput.addEventListener('keydown', event => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      submitGenerate();
    }
  });

  followupInput.addEventListener('keydown', event => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      submitFollowup();
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
