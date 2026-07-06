document.addEventListener('DOMContentLoaded', () => {
  const datePicker = document.getElementById('date-picker');
  const btnPrev = document.getElementById('btn-prev');
  const btnNext = document.getElementById('btn-next');
  const btnToday = document.getElementById('btn-today');
  const btnReload = document.getElementById('btn-reload');
  const btnClearSearch = document.getElementById('btn-clear-search');
  const btnGenerate = document.getElementById('btn-generate');
  const searchInput = document.getElementById('search-input');
  const recentList = document.getElementById('recent-list');
  const openReportLink = document.getElementById('open-report-link');
  const promptInput = document.getElementById('generate-prompt');
  const apiKeyInput = document.getElementById('api-key-input');
  const useLlmParser = document.getElementById('use-llm-parser');
  const jobPanel = document.getElementById('job-panel');
  const jobStep = document.getElementById('job-step');
  const jobMessage = document.getElementById('job-message');
  const jobProgress = document.getElementById('job-progress');
  const jobTask = document.getElementById('job-task');

  const STORAGE_KEY = 'auto_daily_recent';
  let pollTimer = null;

  function todayStr() {
    return formatDate(new Date());
  }

  function formatDate(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
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

  function clearSearch() {
    searchInput.value = '';
    ReportViewer.search('');
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

  function setJobState(job) {
    jobPanel.hidden = false;
    jobStep.textContent = job.step || job.status || 'running';
    jobMessage.textContent = job.message || '';
    jobProgress.style.width = `${Math.max(0, Math.min(100, job.progress || 0))}%`;
    if (job.parsed_task) {
      jobTask.textContent = JSON.stringify(job.parsed_task, null, 2);
    }
  }

  async function submitGenerate() {
    const prompt = promptInput.value.trim();
    if (!prompt) {
      promptInput.focus();
      jobPanel.hidden = false;
      jobStep.textContent = 'input';
      jobMessage.textContent = '请输入生成需求';
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
      const payload = {
        prompt,
        api_key: apiKeyInput.value.trim() || undefined,
        use_llm: useLlmParser.checked,
      };
      const resp = await fetch('/api/reports/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error || '任务创建失败');
      pollJob(data.job_id);
    } catch (error) {
      btnGenerate.disabled = false;
      btnGenerate.textContent = '生成';
      jobStep.textContent = 'error';
      jobMessage.textContent = error.message;
      jobProgress.style.width = '100%';
    }
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
          clearInterval(pollTimer);
          btnGenerate.disabled = false;
          btnGenerate.textContent = '生成';
          if (job.output_name) {
            await ReportViewer.loadReportFile(job.output_name);
            updateOpenReportLink(job.output_name);
            saveRecent(job.output_name);
            updateRecentUI();
          }
        }

        if (job.status === 'failed') {
          clearInterval(pollTimer);
          btnGenerate.disabled = false;
          btnGenerate.textContent = '生成';
        }
      } catch (error) {
        clearInterval(pollTimer);
        btnGenerate.disabled = false;
        btnGenerate.textContent = '生成';
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
  updateOpenReportLink(`${today}.md`);
  updateNavButtons();
  ReportViewer.loadReport(today);
  saveRecent(`${today}.md`);
  updateRecentUI();

  btnPrev.addEventListener('click', () => shiftDate(-1));
  btnNext.addEventListener('click', () => shiftDate(1));
  btnToday.addEventListener('click', () => setDate(todayStr()));
  btnReload.addEventListener('click', reloadCurrent);
  btnClearSearch.addEventListener('click', clearSearch);
  btnGenerate.addEventListener('click', submitGenerate);

  datePicker.addEventListener('change', event => {
    if (event.target.value) setDate(event.target.value);
  });

  promptInput.addEventListener('keydown', event => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      submitGenerate();
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
