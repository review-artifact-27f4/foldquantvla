(() => {
  'use strict';
  const tabs = [...document.querySelectorAll('.result-tabs a')];
  const tablist = document.querySelector('.result-tabs');
  const panels = tabs.map(tab => document.querySelector(tab.getAttribute('href')));
  const panelIds = panels.map(panel => panel.id);

  function selectTab(id, focus = false) {
    if (!panelIds.includes(id)) return;
    tabs.forEach((tab, index) => {
      const selected = panels[index].id === id;
      tab.setAttribute('aria-selected', String(selected));
      tab.tabIndex = selected ? 0 : -1;
      panels[index].hidden = !selected;
      if (selected && focus) tab.focus();
    });
  }
  tablist.setAttribute('role', 'tablist');
  tabs.forEach((tab, index) => {
    tab.setAttribute('role', 'tab');
    tab.setAttribute('aria-controls', panels[index].id);
    panels[index].setAttribute('role', 'tabpanel');
    panels[index].setAttribute('aria-labelledby', tab.id);
    panels[index].tabIndex = 0;
    tab.addEventListener('click', event => {
      event.preventDefault();
      selectTab(panels[index].id);
      history.replaceState(null, '', `#${panels[index].id}`);
    });
    tab.addEventListener('keydown', event => {
      let next;
      if (event.key === 'ArrowRight') next = (index + 1) % tabs.length;
      if (event.key === 'ArrowLeft') next = (index + tabs.length - 1) % tabs.length;
      if (event.key === 'Home') next = 0;
      if (event.key === 'End') next = tabs.length - 1;
      if (next === undefined) return;
      event.preventDefault();
      selectTab(panels[next].id, true);
      history.replaceState(null, '', `#${panels[next].id}`);
    });
  });
  document.documentElement.classList.add('tabs-ready');
  function revealHash() {
    const id = location.hash.slice(1);
    if (panelIds.includes(id)) selectTab(id);
    if (id === 'campaign-details') {
      selectTab('libero');
      document.getElementById(id).open = true;
    }
  }
  selectTab(panelIds.includes(location.hash.slice(1)) ? location.hash.slice(1) : 'jetson');
  revealHash();
  window.addEventListener('hashchange', revealHash);

  const benchmarkTabs = [...document.querySelectorAll('.benchmark-tabs button')];
  const benchmarkPanels = [...document.querySelectorAll('.benchmark-panel')];
  function selectBenchmark(id, focus = false) {
    benchmarkTabs.forEach(tab => {
      const selected = tab.dataset.benchmark === id;
      tab.setAttribute('aria-selected', String(selected));
      tab.tabIndex = selected ? 0 : -1;
      if (selected && focus) tab.focus();
    });
    benchmarkPanels.forEach(panel => { panel.hidden = panel.id !== id; });
  }
  if (benchmarkTabs.length) {
    const benchmarkTablist = document.querySelector('.benchmark-tabs');
    benchmarkTablist.hidden = false;
    benchmarkTablist.setAttribute('role', 'tablist');
    benchmarkTabs.forEach((tab, index) => {
      tab.setAttribute('role', 'tab');
      tab.setAttribute('aria-controls', tab.dataset.benchmark);
      const panel = document.getElementById(tab.dataset.benchmark);
      panel.setAttribute('role', 'tabpanel');
      tab.addEventListener('click', () => selectBenchmark(tab.dataset.benchmark));
      tab.addEventListener('keydown', event => {
        let next;
        if (event.key === 'ArrowRight') next = (index + 1) % benchmarkTabs.length;
        if (event.key === 'ArrowLeft') next = (index + benchmarkTabs.length - 1) % benchmarkTabs.length;
        if (event.key === 'Home') next = 0;
        if (event.key === 'End') next = benchmarkTabs.length - 1;
        if (next === undefined) return;
        event.preventDefault();
        selectBenchmark(benchmarkTabs[next].dataset.benchmark, true);
      });
    });
    document.documentElement.classList.add('benchmark-tabs-ready');
    selectBenchmark('benchmark-n17');
  }

  const desktopSelect = document.getElementById('desktop-model');
  function filterDesktop() {
    document.querySelectorAll('.desktop-model').forEach(panel => {
      panel.hidden = panel.dataset.model !== desktopSelect.value;
    });
  }
  desktopSelect.addEventListener('change', filterDesktop);
  filterDesktop();

  const modelSelect = document.getElementById('libero-model');
  const configSelect = document.getElementById('libero-config');
  const campaignRows = [...document.querySelectorAll('#campaign-details tbody tr')];
  function filterLibero() {
    const model = modelSelect.value;
    const config = configSelect.value;
    let count = 0;
    campaignRows.forEach(row => {
      const match = (model === 'all' || row.dataset.model === model) && (config === 'all' || row.dataset.config === config);
      row.hidden = !match;
      if (match) count += 1;
    });
    document.querySelectorAll('.success-card').forEach(card => {
      card.hidden = model !== 'all' && card.dataset.model !== model;
      let visible = 0;
      card.querySelectorAll('.success-row').forEach(row => {
        const match = config === 'all' ? row.dataset.core === 'true' : row.dataset.config === config;
        row.hidden = !match;
        if (match) visible += 1;
      });
      if (!visible) card.hidden = true;
    });
    document.getElementById('libero-count').textContent = `${count} of ${campaignRows.length} campaigns${count === 0 ? ' · This configuration was not evaluated for this checkpoint.' : ''}`;
  }
  modelSelect.addEventListener('change', filterLibero);
  configSelect.addEventListener('change', filterLibero);
  document.querySelectorAll('.enhanced-control').forEach(control => { control.hidden = false; });
  filterLibero();

  const copyButton = document.getElementById('copy-citation');
  const status = document.getElementById('copy-status');
  copyButton.hidden = false;
  copyButton.addEventListener('click', async () => {
    const code = document.getElementById('bibtex');
    try {
      if (!navigator.clipboard?.writeText) throw new Error('Clipboard unavailable');
      await navigator.clipboard.writeText(code.textContent);
      copyButton.textContent = 'Copied';
      status.textContent = 'Citation copied to clipboard.';
    } catch {
      const selection = window.getSelection();
      const range = document.createRange();
      range.selectNodeContents(code);
      selection.removeAllRanges();
      selection.addRange(range);
      status.textContent = 'Citation selected. Press Ctrl+C or Command+C to copy.';
    }
  });
  document.querySelectorAll('.chart-row, .success-row').forEach(row => {
    row.addEventListener('blur', () => row.classList.remove('tooltip-dismissed'));
    row.addEventListener('mouseleave', () => row.classList.remove('tooltip-dismissed'));
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') document.querySelectorAll('.chart-row, .success-row').forEach(row => row.classList.add('tooltip-dismissed'));
  });
  const experimentVideos = [...document.querySelectorAll('.robot-card video')];
  const robotTabs = [...document.querySelectorAll('.robot-task-tabs button')];
  const robotPanels = [...document.querySelectorAll('.robot-trial')];
  function selectRobotTask(id, focus = false) {
    robotTabs.forEach(tab => {
      const selected = tab.dataset.robotTask === id;
      tab.setAttribute('aria-selected', String(selected));
      tab.tabIndex = selected ? 0 : -1;
      if (selected && focus) tab.focus();
    });
    robotPanels.forEach(panel => { panel.hidden = panel.id !== id; });
  }
  if (robotTabs.length) {
    const taskList = document.querySelector('.robot-task-tabs');
    taskList.hidden = false;
    taskList.setAttribute('role', 'tablist');
    robotTabs.forEach((tab, index) => {
      tab.setAttribute('role', 'tab');
      tab.setAttribute('aria-controls', tab.dataset.robotTask);
      const panel = document.getElementById(tab.dataset.robotTask);
      panel.setAttribute('role', 'tabpanel');
      panel.setAttribute('aria-labelledby', tab.id);
      tab.addEventListener('click', () => selectRobotTask(tab.dataset.robotTask));
      tab.addEventListener('keydown', event => {
        let next;
        if (event.key === 'ArrowRight') next = (index + 1) % robotTabs.length;
        if (event.key === 'ArrowLeft') next = (index + robotTabs.length - 1) % robotTabs.length;
        if (event.key === 'Home') next = 0;
        if (event.key === 'End') next = robotTabs.length - 1;
        if (next === undefined) return;
        event.preventDefault();
        selectRobotTask(robotTabs[next].dataset.robotTask, true);
      });
    });
    document.documentElement.classList.add('robot-tabs-ready');
    selectRobotTask(robotTabs[0].dataset.robotTask);
  }
  experimentVideos.forEach(video => video.addEventListener('play', () => {
    experimentVideos.forEach(other => { if (other !== video) other.pause(); });
  }));
})();
