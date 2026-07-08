const ReportViewer = (() => {
  const contentEl = document.getElementById('report-content');
  const statusEl = document.getElementById('status-bar');
  const footerInfo = document.getElementById('footer-info');
  const summaryDate = document.getElementById('summary-date');
  const summaryFile = document.getElementById('summary-file');
  const summarySize = document.getElementById('summary-size');
  const summaryState = document.getElementById('summary-state');

  let currentMarkdown = '';
  let currentHtml = '';
  let currentDate = null;
  let currentFile = null;

  function setStatus(message, type = 'info') {
    const cls = {
      info: 'status-info',
      warning: 'status-warning',
      error: 'status-error',
    }[type] || 'status-info';
    statusEl.innerHTML = `<span class="${cls}">${escapeHtml(message)}</span>`;
    summaryState.textContent = message;
    summaryState.className = `summary-state ${cls}`;
  }

  function updateSummary({ date, fileName, size }) {
    summaryDate.textContent = date || '-';
    summaryFile.textContent = fileName || '未加载';
    summarySize.textContent = typeof size === 'number' ? `${size} 字符` : '-';
  }

  async function loadReport(dateStr) {
    return loadReportFile(`${dateStr}.md`, dateStr);
  }

  async function loadReportRecord(record) {
    if (!record || !record.file_name) return false;
    return loadReportFile(record.file_name, record.date || null);
  }

  async function loadReportFile(fileName, dateStr = null) {
    currentDate = dateStr || extractDate(fileName);
    currentFile = fileName;
    updateSummary({ date: currentDate, fileName });
    setStatus(`正在加载 ${fileName}`, 'info');
    footerInfo.textContent = '加载中';

    const encoded = encodeURIComponent(fileName);
    const urls = [`../output/${encoded}`, `/output/${encoded}`];
    let notFound = false;

    for (const url of urls) {
      try {
        const resp = await fetch(url);
        if (resp.ok) {
          currentMarkdown = await resp.text();
          currentHtml = window.marked ? marked.parse(currentMarkdown) : `<pre>${escapeHtml(currentMarkdown)}</pre>`;
          renderHtml(currentHtml);
          updateSummary({ date: currentDate, fileName, size: currentMarkdown.length });
          setStatus(`已加载 ${fileName}`, 'info');
          footerInfo.textContent = `${fileName} | ${currentMarkdown.length} 字符`;
          return true;
        }
        if (resp.status === 404) notFound = true;
      } catch {
        notFound = false;
      }
    }

    currentMarkdown = '';
    currentHtml = '';
    if (notFound) {
      setStatus(`未找到 ${fileName}`, 'warning');
      showPlaceholder(`未找到 <code>${escapeHtml(fileName)}</code>，请确认 output/ 中存在该文件。`);
    } else {
      setStatus('加载失败，请确认本地服务已启动。', 'error');
      showPlaceholder('无法加载报告。请使用 <code>python tools/workflow_server.py</code> 启动本地服务。');
    }
    footerInfo.textContent = '加载失败';
    return false;
  }

  function renderHtml(html) {
    contentEl.innerHTML = html;
  }

  function showPlaceholder(html) {
    contentEl.innerHTML = `<p class="placeholder">${html}</p>`;
  }

  function escapeHtml(text) {
    return String(text)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function extractDate(fileName) {
    const match = String(fileName).match(/20\d{2}-\d{2}-\d{2}/);
    return match ? match[0] : '-';
  }

  function search(keyword) {
    const countEl = document.getElementById('search-count');
    if (!keyword || !currentHtml) {
      renderHtml(currentHtml);
      countEl.textContent = '';
      return;
    }

    const escaped = keyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const regex = new RegExp(`(${escaped})`, 'gi');
    let count = 0;
    const highlighted = currentHtml.replace(/(<[^>]*>)|([^<]+)/g, (match, tag, text) => {
      if (tag) return tag;
      return text.replace(regex, (value) => {
        count += 1;
        return `<mark class="search-hl">${value}</mark>`;
      });
    });

    renderHtml(highlighted);
    countEl.textContent = count > 0 ? `${count} 个匹配` : '无匹配';
  }

  return {
    loadReport,
    loadReportFile,
    loadReportRecord,
    search,
    get currentDate() { return currentDate; },
    get currentFile() { return currentFile; },
  };
})();
