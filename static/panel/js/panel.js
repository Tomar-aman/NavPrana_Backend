/* NavPrana admin panel — vanilla JS, no dependencies.
 *
 * Everything is wired by data attribute so markup stays declarative:
 *   data-theme-toggle    theme switch
 *   data-sidebar-toggle  collapse the desktop rail
 *   data-drawer-open/-close  mobile navigation
 *   data-popover         click-away dropdown
 *   data-bulk-form       select-all + selection counter
 *   data-confirm         confirmation before submit
 *   data-loading         busy state on submit
 *   data-autosubmit      re-submit a filter form on change
 *   data-dirty-guard     warn before leaving an edited form
 *   data-chart           SVG chart rendered from a json_script block
 */
(function () {
  'use strict';

  var root = document.documentElement;
  var $ = function (sel, ctx) { return (ctx || document).querySelector(sel); };
  var $$ = function (sel, ctx) { return Array.prototype.slice.call((ctx || document).querySelectorAll(sel)); };

  /* ---------------------------------------------------------------- theme */

  function setTheme(theme) {
    root.setAttribute('data-theme', theme);
    try { localStorage.setItem('panel-theme', theme); } catch (e) { /* private mode */ }
  }

  $$('[data-theme-toggle]').forEach(function (button) {
    button.addEventListener('click', function () {
      setTheme(root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark');
      redrawCharts();
    });
  });

  /* -------------------------------------------------------------- sidebar */

  $$('[data-sidebar-toggle]').forEach(function (button) {
    button.addEventListener('click', function () {
      var collapsed = root.classList.toggle('sidebar-collapsed');
      try { localStorage.setItem('panel-sidebar', collapsed ? 'collapsed' : 'expanded'); } catch (e) { /* noop */ }
      redrawCharts();
    });
  });

  var scrim = $('.scrim');

  function setDrawer(open) {
    root.classList.toggle('drawer-open', open);
    if (scrim) { scrim.hidden = !open; }
    document.body.style.overflow = open ? 'hidden' : '';
  }

  $$('[data-drawer-open]').forEach(function (el) {
    el.addEventListener('click', function () { setDrawer(true); });
  });
  $$('[data-drawer-close]').forEach(function (el) {
    el.addEventListener('click', function () { setDrawer(false); });
  });

  /* ------------------------------------------------------------- popovers */

  var popovers = $$('[data-popover]');

  function closePopovers(except) {
    popovers.forEach(function (popover) {
      if (popover === except) { return; }
      var panel = $('[data-popover-panel]', popover);
      var trigger = $('[data-popover-trigger]', popover);
      if (panel) { panel.hidden = true; }
      if (trigger) { trigger.setAttribute('aria-expanded', 'false'); }
    });
  }

  popovers.forEach(function (popover) {
    var trigger = $('[data-popover-trigger]', popover);
    var panel = $('[data-popover-panel]', popover);
    if (!trigger || !panel) { return; }

    trigger.addEventListener('click', function (event) {
      event.stopPropagation();
      var open = panel.hidden;
      closePopovers(popover);
      panel.hidden = !open;
      trigger.setAttribute('aria-expanded', String(open));
    });
    panel.addEventListener('click', function (event) { event.stopPropagation(); });
  });

  document.addEventListener('click', function () { closePopovers(); });
  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape') { closePopovers(); setDrawer(false); }
  });

  /* ------------------------------------------------------- flash messages */

  $$('[data-flash-close]').forEach(function (button) {
    button.addEventListener('click', function () {
      var flash = button.closest('[data-flash]');
      if (flash) { flash.remove(); }
    });
  });

  /* --------------------------------------------------------- bulk actions */

  $$('[data-bulk-form]').forEach(function (form) {
    var all = $('[data-bulk-all]', form);
    var items = $$('[data-bulk-item]', form);
    var bar = $('[data-bulk-bar]', form);
    var counter = $('[data-bulk-count]', form);
    if (!items.length) { return; }

    function sync() {
      var checked = items.filter(function (item) { return item.checked; });
      if (bar) { bar.hidden = checked.length === 0; }
      if (counter) { counter.textContent = String(checked.length); }
      if (all) {
        all.checked = checked.length === items.length;
        all.indeterminate = checked.length > 0 && checked.length < items.length;
      }
    }

    if (all) {
      all.addEventListener('change', function () {
        items.forEach(function (item) { item.checked = all.checked; });
        sync();
      });
    }
    items.forEach(function (item) { item.addEventListener('change', sync); });
    sync();
  });

  /* ------------------------------------------------- confirm + busy state */

  document.addEventListener('click', function (event) {
    var trigger = event.target.closest('[data-confirm]');
    if (!trigger) { return; }
    if (!window.confirm(trigger.getAttribute('data-confirm'))) {
      event.preventDefault();
      event.stopPropagation();
    }
  }, true);

  document.addEventListener('submit', function (event) {
    var form = event.target;
    if (form.hasAttribute('data-dirty-guard')) { form.dataset.submitting = 'true'; }

    var submitter = event.submitter;
    if (submitter && submitter.hasAttribute('data-loading')) {
      markBusy(submitter);
    } else {
      var fallback = form.querySelector('[data-loading]');
      if (fallback && fallback.tagName === 'BUTTON') { markBusy(fallback); }
    }
  });

  function markBusy(element) {
    // Re-enabled by the page navigation that follows; if validation keeps us
    // here, the fresh render clears it anyway.
    element.classList.add('is-busy');
    var label = element.getAttribute('data-loading');
    if (label && element.tagName === 'BUTTON') {
      element.dataset.originalLabel = element.innerHTML;
      element.textContent = label;
    }
    element.setAttribute('aria-busy', 'true');
  }

  $$('a[data-loading]').forEach(function (link) {
    link.addEventListener('click', function () {
      link.classList.add('is-busy');
      // Downloads never navigate, so release the state after a moment.
      window.setTimeout(function () { link.classList.remove('is-busy'); }, 2500);
    });
  });

  /* -------------------------------------------------------- filter forms */

  $$('[data-autosubmit]').forEach(function (form) {
    $$('select, input[type="date"]', form).forEach(function (field) {
      field.addEventListener('change', function () { form.submit(); });
    });
  });

  /* ---------------------------------------------------------- dirty guard */

  $$('[data-dirty-guard]').forEach(function (form) {
    var initial = new FormData(form);
    var dirty = false;

    form.addEventListener('input', function () { dirty = true; });
    form.addEventListener('change', function () { dirty = true; });
    $$('[data-dirty-ignore]', form).forEach(function (el) {
      el.addEventListener('click', function () { dirty = false; });
    });

    window.addEventListener('beforeunload', function (event) {
      if (!dirty || form.dataset.submitting === 'true') { return; }
      event.preventDefault();
      event.returnValue = '';
    });

    void initial;
  });

  /* --------------------------------------------------- permission filter */

  var permFilter = $('[data-perm-filter]');
  if (permFilter) {
    permFilter.addEventListener('input', function () {
      var term = permFilter.value.trim().toLowerCase();
      $$('[data-perm-group]').forEach(function (group) {
        var visible = 0;
        $$('[data-perm-row]', group).forEach(function (row) {
          var match = !term || row.textContent.toLowerCase().indexOf(term) !== -1;
          row.hidden = !match;
          if (match) { visible += 1; }
        });
        group.hidden = visible === 0;
        if (term && visible) { group.open = true; }
      });
    });
  }

  $$('[data-perm-toggle-all]').forEach(function (button) {
    button.addEventListener('click', function () {
      var boxes = $$('[data-perm-row]:not([hidden]) input[type="checkbox"]', button.closest('[data-perm-group]'));
      var turnOn = boxes.some(function (box) { return !box.checked; });
      boxes.forEach(function (box) { box.checked = turnOn; });
    });
  });

  /* --------------------------------------------------------- search hotkey */

  document.addEventListener('keydown', function (event) {
    if (event.key !== '/' || event.ctrlKey || event.metaKey || event.altKey) { return; }
    var tag = (event.target.tagName || '').toLowerCase();
    if (tag === 'input' || tag === 'textarea' || tag === 'select' || event.target.isContentEditable) { return; }
    var box = $('[data-hotkey-target]');
    if (box) { event.preventDefault(); box.focus(); }
  });

  /* ================================================================ charts
   * Small hand-rolled SVG charts. A library would be ~200 KB of vendored
   * minified code for four charts, and would still need re-theming on every
   * theme switch; these read the same CSS custom properties as everything
   * else, so dark mode is free.
   * ================================================================ */

  var charts = $$('[data-chart]');

  function readData(id) {
    var node = document.getElementById(id);
    if (!node) { return null; }
    try { return JSON.parse(node.textContent); } catch (e) { return null; }
  }

  function el(name, attrs, text) {
    var node = document.createElementNS('http://www.w3.org/2000/svg', name);
    Object.keys(attrs || {}).forEach(function (key) { node.setAttribute(key, attrs[key]); });
    if (text !== undefined) { node.textContent = text; }
    return node;
  }

  function money(value) {
    return '₹' + Math.round(value).toLocaleString('en-IN');
  }

  function tooltipFor(container) {
    var tip = $('.chart-tip', container);
    if (!tip) {
      tip = document.createElement('div');
      tip.className = 'chart-tip';
      container.appendChild(tip);
    }
    return tip;
  }

  function drawLineChart(container, points) {
    var width = container.clientWidth || 640;
    var height = container.clientHeight || 260;
    var pad = { top: 16, right: 12, bottom: 26, left: 56 };
    var plotW = Math.max(10, width - pad.left - pad.right);
    var plotH = Math.max(10, height - pad.top - pad.bottom);

    var svg = el('svg', { viewBox: '0 0 ' + width + ' ' + height, preserveAspectRatio: 'none' });
    var maxRevenue = Math.max.apply(null, points.map(function (p) { return p.revenue; }).concat([1]));
    var maxOrders = Math.max.apply(null, points.map(function (p) { return p.orders; }).concat([1]));
    var step = points.length > 1 ? plotW / (points.length - 1) : 0;

    var x = function (i) { return pad.left + step * i; };
    var yRevenue = function (v) { return pad.top + plotH - (v / maxRevenue) * plotH; };
    var yOrders = function (v) { return pad.top + plotH - (v / maxOrders) * plotH; };

    // Horizontal grid with revenue labels.
    for (var g = 0; g <= 4; g++) {
      var gy = pad.top + (plotH / 4) * g;
      svg.appendChild(el('line', { class: 'grid-line', x1: pad.left, y1: gy, x2: width - pad.right, y2: gy }));
      svg.appendChild(el('text', {
        class: 'axis-label', x: pad.left - 8, y: gy + 3, 'text-anchor': 'end'
      }, money(maxRevenue * (1 - g / 4))));
    }

    var linePoints = points.map(function (p, i) { return x(i) + ',' + yRevenue(p.revenue); });
    svg.appendChild(el('polygon', {
      class: 'area-fill',
      points: pad.left + ',' + (pad.top + plotH) + ' ' + linePoints.join(' ') + ' ' + x(points.length - 1) + ',' + (pad.top + plotH)
    }));
    svg.appendChild(el('polyline', { class: 'line-path', points: linePoints.join(' ') }));
    svg.appendChild(el('polyline', {
      class: 'line-path line-path--accent',
      points: points.map(function (p, i) { return x(i) + ',' + yOrders(p.orders); }).join(' ')
    }));

    var tip = tooltipFor(container);

    points.forEach(function (point, i) {
      svg.appendChild(el('circle', { class: 'point', cx: x(i), cy: yRevenue(point.revenue), r: 3 }));
      svg.appendChild(el('circle', { class: 'point point--accent', cx: x(i), cy: yOrders(point.orders), r: 2.5 }));
      svg.appendChild(el('text', {
        class: 'axis-label', x: x(i), y: height - 8, 'text-anchor': 'middle'
      }, point.label));

      var hit = el('rect', {
        class: 'hit',
        x: x(i) - step / 2, y: pad.top, width: Math.max(step, 18), height: plotH
      });
      hit.addEventListener('mouseenter', function () {
        tip.innerHTML = '';
        var head = document.createElement('strong');
        head.textContent = point.full_label;
        tip.appendChild(head);
        tip.appendChild(document.createTextNode(
          money(point.revenue) + ' · ' + point.orders + ' order' + (point.orders === 1 ? '' : 's')
        ));
        tip.style.left = x(i) + 'px';
        tip.style.top = yRevenue(point.revenue) + 'px';
        tip.classList.add('is-visible');
      });
      hit.addEventListener('mouseleave', function () { tip.classList.remove('is-visible'); });
      svg.appendChild(hit);
    });

    return svg;
  }

  function drawBarChart(container, points) {
    var width = container.clientWidth || 480;
    var height = container.clientHeight || 190;
    var pad = { top: 12, right: 8, bottom: 24, left: 30 };
    var plotW = Math.max(10, width - pad.left - pad.right);
    var plotH = Math.max(10, height - pad.top - pad.bottom);

    var svg = el('svg', { viewBox: '0 0 ' + width + ' ' + height, preserveAspectRatio: 'none' });
    var max = Math.max.apply(null, points.map(function (p) { return p.value; }).concat([1]));
    var slot = plotW / Math.max(points.length, 1);
    var barWidth = Math.max(6, Math.min(30, slot * 0.55));
    var tip = tooltipFor(container);

    for (var g = 0; g <= 2; g++) {
      var gy = pad.top + (plotH / 2) * g;
      svg.appendChild(el('line', { class: 'grid-line', x1: pad.left, y1: gy, x2: width - pad.right, y2: gy }));
      svg.appendChild(el('text', {
        class: 'axis-label', x: pad.left - 7, y: gy + 3, 'text-anchor': 'end'
      }, String(Math.round(max * (1 - g / 2)))));
    }

    points.forEach(function (point, i) {
      var barHeight = (point.value / max) * plotH;
      var bx = pad.left + slot * i + (slot - barWidth) / 2;
      var by = pad.top + plotH - barHeight;

      var rect = el('rect', {
        class: 'bar-rect', x: bx, y: by, width: barWidth, height: Math.max(barHeight, point.value ? 2 : 0)
      });
      rect.addEventListener('mouseenter', function () {
        tip.innerHTML = '';
        var head = document.createElement('strong');
        head.textContent = point.full_label;
        tip.appendChild(head);
        tip.appendChild(document.createTextNode(
          point.value + ' new customer' + (point.value === 1 ? '' : 's')
        ));
        tip.style.left = (bx + barWidth / 2) + 'px';
        tip.style.top = by + 'px';
        tip.classList.add('is-visible');
      });
      rect.addEventListener('mouseleave', function () { tip.classList.remove('is-visible'); });
      svg.appendChild(rect);

      svg.appendChild(el('text', {
        class: 'axis-label', x: bx + barWidth / 2, y: height - 7, 'text-anchor': 'middle'
      }, point.label));
    });

    return svg;
  }

  function renderChart(container) {
    var data = readData(container.getAttribute('data-chart-source'));
    if (!data) { return; }

    var key = container.getAttribute('data-chart');
    var points = data[key];
    if (!points || !points.length) { return; }

    var hasValue = points.some(function (point) {
      return (point.revenue || 0) > 0 || (point.orders || 0) > 0 || (point.value || 0) > 0;
    });
    if (!hasValue) {
      container.innerHTML = '<p class="chart__fallback">No activity recorded in this period yet.</p>';
      return;
    }

    var svg = key === 'revenue' ? drawLineChart(container, points) : drawBarChart(container, points);
    var tip = $('.chart-tip', container);
    container.innerHTML = '';
    container.appendChild(svg);
    if (tip) { container.appendChild(tip); }
  }

  function redrawCharts() {
    charts.forEach(renderChart);
  }

  if (charts.length) {
    redrawCharts();
    var resizeTimer;
    window.addEventListener('resize', function () {
      window.clearTimeout(resizeTimer);
      resizeTimer = window.setTimeout(redrawCharts, 180);
    });
  }
})();
