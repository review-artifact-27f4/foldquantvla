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
  if (tablist) tablist.setAttribute('role', 'tablist');
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
  if (tabs.length) document.documentElement.classList.add('tabs-ready');
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
  const benchmarkPanels = [...document.querySelectorAll('.benchmark-panels .benchmark-panel')];
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

  const latencyTabs = [...document.querySelectorAll('.latency-tabs button')];
  if (latencyTabs.length) {
    const latencyList = document.querySelector('.latency-tabs');
    const selectLatency = (id, focus = false) => {
      latencyTabs.forEach(tab => {
        const selected = tab.dataset.latency === id;
        tab.setAttribute('aria-selected', String(selected));
        tab.tabIndex = selected ? 0 : -1;
        const latencyPanel = document.getElementById(tab.dataset.latency);
        latencyPanel.classList.toggle('is-inactive', !selected);
        latencyPanel.setAttribute('aria-hidden', String(!selected));
        latencyPanel.inert = !selected;
        if (selected && focus) tab.focus();
      });
    };
    latencyList.hidden = false;
    latencyList.setAttribute('role', 'tablist');
    latencyTabs.forEach((tab, index) => {
      tab.setAttribute('role', 'tab');
      tab.setAttribute('aria-controls', tab.dataset.latency);
      const panel = document.getElementById(tab.dataset.latency);
      panel.setAttribute('role', 'tabpanel');
      panel.setAttribute('aria-labelledby', tab.id);
      tab.addEventListener('click', () => selectLatency(tab.dataset.latency));
      tab.addEventListener('keydown', event => {
        let next;
        if (event.key === 'ArrowRight') next = (index + 1) % latencyTabs.length;
        if (event.key === 'ArrowLeft') next = (index + latencyTabs.length - 1) % latencyTabs.length;
        if (next === undefined) return;
        event.preventDefault();
        selectLatency(latencyTabs[next].dataset.latency, true);
      });
    });
    document.documentElement.classList.add('latency-tabs-ready');
    const hashTab = latencyTabs.find(tab => tab.dataset.latency === location.hash.slice(1));
    selectLatency(hashTab ? hashTab.dataset.latency : 'jetson');
  }

  document.querySelectorAll('select[data-family-group]').forEach(select => {
    const group = select.dataset.familyGroup;
    const panels = [...document.querySelectorAll(`.family-panel[data-family-group="${group}"]`)];
    const show = () => panels.forEach(panel => { const off = panel.dataset.family !== select.value; panel.classList.toggle('is-inactive', off); panel.setAttribute('aria-hidden', String(off)); panel.inert = off; });
    select.closest('.family-switch').hidden = false;
    select.addEventListener('change', show);
    show();
  });
  if (document.querySelector('select[data-family-group]')) document.documentElement.classList.add('family-ready');

  const desktopSelect = document.getElementById('desktop-model');
  function filterDesktop() {
    document.querySelectorAll('.desktop-model').forEach(panel => {
      panel.hidden = panel.dataset.model !== desktopSelect.value;
    });
  }
  if (desktopSelect) {
    desktopSelect.addEventListener('change', filterDesktop);
    filterDesktop();
  }

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
  if (modelSelect && configSelect) {
  modelSelect.addEventListener('change', filterLibero);
  configSelect.addEventListener('change', filterLibero);
  document.querySelectorAll('.enhanced-control').forEach(control => { control.hidden = false; });
  filterLibero();
  }

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
  // Real-robot comparison: task tabs; every engine of the active task starts together, holds its last frame, restarts when all end.
  document.querySelectorAll('.robot-compare').forEach(block => {
    const tabs = [...block.querySelectorAll('.compare-task-tabs button')];
    const tasks = [...block.querySelectorAll('.compare-task')];
    let active = null;
    const sync = task => {
      // Multi-scene tasks show one scene row at a time; only that row's videos play.
      const rows = [...task.querySelectorAll('.compare-grid')];
      const sceneButtons = [...task.querySelectorAll('.compare-scene-tabs button')];
      let row = rows[0];
      let videos = [...row.querySelectorAll('video')];
      let done = new Set();
      let timer = null;
      const restart = () => {
        if (active !== task) return;
        done = new Set();
        videos.forEach(v => { v.currentTime = 0; v.play().catch(() => {}); });
      };
      rows.forEach(r => r.querySelectorAll('video').forEach(v => v.addEventListener('ended', () => {
        if (r !== row) return;
        done.add(v);
        if (done.size === videos.length) setTimeout(restart, 800);
      })));
      task._restart = () => {
        clearTimeout(timer);
        const current = row;
        const wait = () => { if (current !== row) return; videos.every(v => v.readyState >= 3) ? restart() : (timer = setTimeout(wait, 150)); };
        wait();
      };
      const showScene = n => {
        row = rows.find(r => r.dataset.scene === n) || rows[0];
        rows.forEach(r => {
          r.hidden = r !== row;
          if (r !== row) r.querySelectorAll('video').forEach(v => v.pause());
        });
        sceneButtons.forEach(b => b.setAttribute('aria-pressed', String(b === sceneButtons[rows.indexOf(row)])));
        videos = [...row.querySelectorAll('video')];
      };
      sceneButtons.forEach(b => b.addEventListener('click', () => { showScene(b.dataset.scene); if (active === task) task._restart(); }));
      if (sceneButtons.length) showScene(sceneButtons[0].dataset.scene);
    };
    tasks.forEach(sync);
    const select = id => {
      tabs.forEach(t => t.setAttribute('aria-selected', String(t.dataset.taskPanel === id)));
      tasks.forEach(task => {
        const on = task.id === id;
        task.classList.toggle('is-inactive', !on);
        task.inert = !on;
        task.querySelectorAll('video').forEach(v => { if (!on) v.pause(); });
        if (on) { active = task; task._restart(); }
      });
    };
    const bar = block.querySelector('.compare-task-tabs');
    if (bar) { bar.hidden = false; bar.setAttribute('role', 'tablist'); }
    tabs.forEach(t => { t.setAttribute('role', 'tab'); t.addEventListener('click', () => select(t.dataset.taskPanel)); });
    block.classList.add('compare-ready');
    tasks.forEach(task => task.querySelectorAll('video').forEach(v => { v.autoplay = false; v.pause(); }));
    new IntersectionObserver((entries, obs) => {
      if (entries.some(e => e.isIntersecting)) { select(tasks[0].id); obs.disconnect(); }
    }, { threshold: 0.2 }).observe(block);
  });
  const experimentVideos = [];
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
