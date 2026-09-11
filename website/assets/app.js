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
    document.getElementById('libero-count').textContent = `${count} of 40 campaigns${count === 0 ? ' · This configuration was not evaluated for this checkpoint.' : ''}`;
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
  const experimentVideos = [...document.querySelectorAll('.robot-view video')];
  experimentVideos.forEach(video => video.addEventListener('play', () => {
    experimentVideos.forEach(other => { if (other !== video) other.pause(); });
  }));
})();
