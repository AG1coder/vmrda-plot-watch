/* VMRDA plot-price visualizations — NYTimes-style data graphics.
   Reads window.SNAPSHOT / window.SNAPSHOT_HISTORY / window.MAPDATA.
   Cross-linked: clicking a mandal in the picker highlights it everywhere. */
(function () {
  const S = window.SNAPSHOT;
  const MAP = window.MAPDATA || { coords: {}, coastline: [] };
  if (!S) return;

  const DISTRICT_COLORS = {
    visakhapatnam: '#31517c',
    anakapalli: '#b07d2b',
    vizianagaram: '#6a8f5f'
  };
  const DISTRICT_LABELS = {
    visakhapatnam: 'Visakhapatnam',
    anakapalli: 'Anakapalli',
    vizianagaram: 'Vizianagaram'
  };
  const HEAT = d3.interpolateRgb('#ffd9a6', '#e27ea8');
  const INK = '#121212', MUTED = '#6c6c6c', LINE = '#e5e5e5';

  const fmt = new Intl.NumberFormat('en-IN');
  const inr = (v) => '₹' + fmt.format(Math.round(v));

  let selectedKey = null;

  const usable = () =>
    Object.values(S.mandals)
      .filter(m => m.n >= 3)
      .sort((a, b) => b.median_psqyd - a.median_psqyd);
  const region = () => S.region;

  // ---- tooltip ------------------------------------------------------------
  function tooltip() {
    let el = document.getElementById('vv-tip');
    if (!el) { el = document.createElement('div'); el.id = 'vv-tip'; el.className = 'tooltip'; document.body.appendChild(el); }
    return el;
  }
  function moveTip(ev, html) {
    const t = tooltip(); t.innerHTML = html; t.style.opacity = 1;
    const w = t.offsetWidth, h = t.offsetHeight;
    let x = ev.clientX + 14, y = ev.clientY + 14;
    if (x + w > window.innerWidth - 10) x = ev.clientX - w - 14;
    if (y + h > window.innerHeight - 10) y = ev.clientY - h - 14;
    t.style.left = x + 'px'; t.style.top = y + 'px';
  }
  function hideTip() { tooltip().style.opacity = 0; }

  function widthOf(sel) {
    const el = document.querySelector(sel);
    return el && el.clientWidth > 200 ? el.clientWidth : 900;
  }

  function tipFor(m) {
    return `<div class="tt">${m.label}</div>
      median <b>${inr(m.median_psqyd)}</b>/sq yd · average ${inr(m.avg_psqyd)}<br>
      typical range <b>${inr(m.p10_psqyd)} – ${inr(m.p90_psqyd)}</b><br>
      <span class="tt-r">${m.n} listing(s) · ${DISTRICT_LABELS[m.district]}</span>`;
  }

  // =====================================================================
  // 1) MAP
  // =====================================================================
  // =====================================================================
  // 1) MAP  (real OpenStreetMap base via Leaflet)
  // =====================================================================
  let leafMap = null;
  const markers = {};

  function renderMap() {
    const container = document.getElementById('chart-map');
    if (!container) return;
    if (typeof L === 'undefined') {
      container.innerHTML = '<div class="detail-hint">Map needs internet access (Leaflet + OpenStreetMap tiles).</div>';
      return;
    }
    const mandals = usable();
    const col = d3.scaleSequential(HEAT)
      .domain([d3.min(mandals, m => m.p10_psqyd), d3.max(mandals, m => m.p90_psqyd)]);
    const maxN = d3.max(mandals, m => m.n) || 1;
    const r = d3.scaleSqrt().domain([3, maxN]).range([15, 32]);

    // center on the VMRDA belt
    leafMap = L.map(container, { scrollWheelZoom: false, zoomControl: true, attributionControl: true })
      .setView([17.85, 83.22], 10);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 18,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(leafMap);

    mandals.forEach(m => {
      const c = MAP.coords[m.key];
      if (!c) return;
      const mm = L.circleMarker([c[0], c[1]], {
        radius: r(m.n),
        color: '#2b2b2b', weight: 2.4,
        fillColor: col(m.median_psqyd), fillOpacity: 1
      }).addTo(leafMap);
      mm.bindTooltip(
        `<b>${m.label}</b><br>` +
        `median <b>${inr(m.median_psqyd)}</b>/sq yd &middot; avg ${inr(m.avg_psqyd)}<br>` +
        `range ${inr(m.p10_psqyd)} &ndash; ${inr(m.p90_psqyd)}<br>` +
        `<span style="color:#888">n=${m.n} &middot; ${DISTRICT_LABELS[m.district]}</span>`,
        { sticky: true });
      mm.on('click', () => select(m.key));
      markers[m.key] = mm;
    });

    // heat legend
    const legend = L.control({ position: 'bottomleft' });
    legend.onAdd = function () {
      const div = L.DomUtil.create('div', 'vv-legend');
      div.innerHTML = `<span>cheaper</span><div class="swatch" style="background:linear-gradient(90deg,${HEAT(0)},${HEAT(0.5)},${HEAT(1)})"></div><span>pricier</span>`;
      return div;
    };
    legend.addTo(leafMap);
  }

  function highlightMap() {
    if (!leafMap) return;
    Object.entries(markers).forEach(([k, mm]) => {
      const on = selectedKey === k;
      mm.setStyle({ fillOpacity: (!selectedKey || on) ? 0.85 : 0.15, weight: on ? 3 : 2 });
      if (on) mm.bringToFront();
    });
  }
  function short(label) {
    return label.replace(' (GVMC)', '').replace(' city', '').replace(' (airport)', '');
  }

  // =====================================================================
  // 2) SELECTOR + DETAIL
  // =====================================================================
  function renderPicker() {
    const host = document.getElementById('mandal-picker');
    if (!host) return;
    const mandals = usable();
    host.innerHTML = '';
    const regionChip = document.createElement('button');
    regionChip.className = 'chip'; regionChip.textContent = 'Region average';
    regionChip.onclick = () => select(null);
    host.appendChild(regionChip);
    mandals.forEach(m => {
      const b = document.createElement('button');
      b.className = 'chip'; b.dataset.key = m.key; b.textContent = short(m.label);
      b.onclick = () => select(m.key);
      host.appendChild(b);
    });
  }

  function select(key) {
    selectedKey = key;
    document.querySelectorAll('#mandal-picker .chip').forEach(c => {
      c.classList.toggle('on', c.dataset.key === key || (!key && c.textContent.startsWith('Region')));
    });
    renderDetail();
    highlightDumbbell();
    highlightMap();
    highlightTrend();
  }

  function renderDetail() {
    const host = document.getElementById('mandal-detail');
    if (!host) return;
    if (!selectedKey) { host.innerHTML = '<div class="d-hint">Region-wide average asking price: <b>' + inr(region().avg_psqyd) + '</b>/sq yd across ' + region().n + ' sampled listings. Pick a mandal to compare.</div>'; return; }
    const m = S.mandals[selectedKey];
    if (!m) return;
    const diff = ((m.median_psqyd - region().avg_psqyd) / region().avg_psqyd) * 100;
    const pct = m.median_psqyd / region().avg_psqyd;
    host.innerHTML = `
      <div class="d-name">${m.label} <span style="color:${DISTRICT_COLORS[m.district]};font-size:12px">· ${DISTRICT_LABELS[m.district]}</span></div>
      <div class="d-meta">${m.n} listings sampled</div>
      <div class="d-grid">
        <div class="d-cell"><div class="lbl2">Median</div><div class="val2">${inr(m.median_psqyd)}</div></div>
        <div class="d-cell"><div class="lbl2">Average</div><div class="val2">${inr(m.avg_psqyd)}</div></div>
        <div class="d-cell"><div class="lbl2">Typical range</div><div class="val2" style="font-size:15px">${inr(m.p10_psqyd)} – ${inr(m.p90_psqyd)}</div></div>
        <div class="d-cell"><div class="lbl2">vs region avg</div><div class="val2" style="font-size:15px;color:${diff >= 0 ? '#8a1c1c' : '#31517c'}">${diff >= 0 ? '+' : ''}${diff.toFixed(0)}%</div></div>
      </div>
      <div class="vsbar"><div class="fill" style="width:${Math.min(100, pct * 100)}%"></div><div class="mark" style="left:100%"></div></div>
      <div class="vs-note">Bar shows this mandal's median as a share of the region average (black tick = region average = 100%).</div>`;
  }

  // =====================================================================
  // 3) DUMBBELL (ranked range + median + avg)
  // =====================================================================
  let dumbbellRows = null;

  function buildDumbLegend() {
    const host = document.getElementById('dumb-legend');
    if (!host) return;
    let dist = ['visakhapatnam', 'anakapalli', 'vizianagaram']
      .map(d => `<span class="item"><span class="sw" style="background:${DISTRICT_COLORS[d]}"></span>${DISTRICT_LABELS[d]}</span>`).join('');
    dist += `<span class="item"><span class="dot" style="background:#333"></span>median</span>`;
    dist += `<span class="item"><span class="sw" style="display:inline-block;width:9px;height:9px;border-radius:50%;background:#fff;border:1.5px solid ${DISTRICT_COLORS.anakapalli}"></span>average</span>`;
    dist += `<span class="item"><span class="sw" style="background:#bdb9b1;height:4px;border-radius:2px"></span>10th–90th pct</span>`;
    host.innerHTML = dist;
  }

  function renderDumbbell() {
    const container = document.getElementById('chart-dumbbell');
    if (!container) return;
    const mandals = usable();
    const width = widthOf('#chart-dumbbell');
    const margin = { top: 30, right: 96, bottom: 46, left: 150 };
    const rowH = 42;
    const height = mandals.length * rowH + margin.top + margin.bottom;
    const innerW = width - margin.left - margin.right;
    const innerH = height - margin.top - margin.bottom;
    const allMax = d3.max(mandals, m => m.p90_psqyd) * 1.06 || 1;

    const svg = d3.select(container).append('svg')
      .attr('viewBox', `0 0 ${width} ${height}`).attr('preserveAspectRatio', 'xMidYMid meet');
    const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);

    const x = d3.scaleLinear().domain([0, allMax]).range([0, innerW]);
    const y = d3.scaleBand().domain(mandals.map(m => m.key)).range([0, innerH]).padding(0.3);

    // light horizontal banding
    g.selectAll('rect.band').data(mandals).enter().append('rect').attr('class', 'band')
      .attr('x', 0).attr('y', d => y(d.key) - rowH / 2).attr('width', innerW).attr('height', rowH)
      .attr('fill', (d, i) => i % 2 ? '#fafaf8' : 'none');

    // vertical ticks + labels below the plot
    const ticks = [0, 10000, 25000, 50000, 75000, 100000].filter(t => t <= allMax);
    g.append('g').selectAll('line').data(ticks).enter().append('line')
      .attr('x1', d => x(d)).attr('x2', d => x(d)).attr('y1', 0).attr('y2', innerH)
      .attr('stroke', '#eceae4');
    g.append('g').selectAll('text').data(ticks).enter().append('text')
      .attr('x', d => x(d)).attr('y', innerH + 22).attr('text-anchor', 'middle')
      .attr('font-family', 'Helvetica, Arial').attr('font-size', 10.5).attr('fill', MUTED)
      .text(d => d ? '₹' + (d / 1000) + 'k' : '₹0');

    // value column: divider + header + per-row values
    g.append('line').attr('x1', innerW + 10).attr('x2', innerW + 10).attr('y1', -18).attr('y2', innerH)
      .attr('stroke', '#dcd9d2');
    g.append('text').attr('x', innerW + 18).attr('y', -8)
      .attr('font-family', 'Helvetica, Arial').attr('font-size', 9.5)
      .attr('letter-spacing', '0.06em').attr('fill', MUTED).text('MEDIAN ₹/SQ YD');

    dumbbellRows = mandals.map(m => {
      const row = g.append('g').attr('data-key', m.key)
        .attr('transform', `translate(0,${y(m.key)})`);
      // mandal label rail
      row.append('text').attr('x', -12).attr('y', 0).attr('dy', '0.35em')
        .attr('text-anchor', 'end').attr('font-family', 'Helvetica, Arial')
        .attr('font-size', 13).attr('fill', INK).text(short(m.label));
      // band (p10-p90)
      row.append('line')
        .attr('x1', x(m.p10_psqyd)).attr('x2', x(m.p90_psqyd)).attr('y1', 0).attr('y2', 0)
        .attr('stroke', '#bdb9b1').attr('stroke-width', 4).attr('stroke-linecap', 'round')
        .style('cursor', 'pointer');
      // average ring (hollow) + median dot (filled)
      row.append('circle').attr('cx', x(m.avg_psqyd)).attr('cy', 0).attr('r', 4.5)
        .attr('fill', '#fff').attr('stroke', DISTRICT_COLORS[m.district]).attr('stroke-width', 1.8);
      row.append('circle').attr('class', 'dot').attr('cx', x(m.median_psqyd)).attr('cy', 0).attr('r', 5.5)
        .attr('fill', DISTRICT_COLORS[m.district]).style('cursor', 'pointer');
      // value in the dedicated right-hand column (never touches the line)
      row.append('text').attr('x', innerW + 18).attr('y', 0).attr('dy', '0.35em')
        .attr('font-family', 'Helvetica, Arial').attr('font-size', 12.5).attr('font-weight', 600)
        .attr('fill', INK).style('font-feature-settings', '"tnum"').text(inr(m.median_psqyd));
      row.on('mousemove', (ev) => moveTip(ev, tipFor(m))).on('mouseleave', hideTip)
        .on('click', () => select(m.key));
      return m;
    });
  }

  function highlightDumbbell() {
    if (!dumbbellRows) return;
    d3.selectAll('#chart-dumbbell g[data-key]').each(function (d) {
      const on = selectedKey && this.getAttribute('data-key') === selectedKey;
      d3.select(this).style('opacity', (!selectedKey || on) ? 1 : 0.28);
      if (on) d3.select(this).raise();
    });
  }

  // =====================================================================
  // 4) AFFORDABILITY — what a fixed budget buys
  // =====================================================================
  function renderAfford(budgetLakh) {
    const container = document.getElementById('chart-afford');
    if (!container) return;
    const budget = budgetLakh * 100000;
    const mandals = usable();
    const width = widthOf('#chart-afford');
    const margin = { top: 14, right: 64, bottom: 26, left: 150 };
    const height = mandals.length * 30 + margin.top + margin.bottom;
    const innerW = width - margin.left - margin.right;
    const innerH = height - margin.top - margin.bottom;
    const data = mandals
      .map(m => ({ m, sqyd: budget / m.median_psqyd }))
      .sort((a, b) => b.sqyd - a.sqyd);

    const svg = d3.select(container).append('svg')
      .attr('viewBox', `0 0 ${width} ${height}`).attr('preserveAspectRatio', 'xMidYMid meet');
    const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);

    const x = d3.scaleLinear().domain([0, d3.max(data, d => d.sqyd) * 1.08]).range([0, innerW]);
    const y = d3.scaleBand().domain(data.map(d => d.m.key)).range([0, innerH]).padding(0.35);

    const row = g.selectAll('g').data(data).enter().append('g')
      .attr('transform', d => `translate(0,${y(d.m.key)})`);
    row.append('text').attr('x', -10).attr('y', 0).attr('dy', '0.35em').attr('text-anchor', 'end')
      .attr('font-family', 'Helvetica, Arial').attr('font-size', 12).attr('fill', INK)
      .text(d => short(d.m.label));
    row.append('rect').attr('x', 0).attr('y', -y.bandwidth() / 2 + 2).attr('height', y.bandwidth() - 4)
      .attr('width', d => Math.max(2, x(d.sqyd)))
      .attr('fill', d => DISTRICT_COLORS[d.m.district])
      .attr('rx', 2).style('cursor', 'pointer');
    row.append('text').attr('x', d => x(d.sqyd) + 6).attr('y', 0).attr('dy', '0.35em')
      .attr('font-family', 'Helvetica, Arial').attr('font-size', 11).attr('fill', INK)
      .text(d => Math.round(d.sqyd) + ' sq yd');
    row.on('mousemove', (ev, d) => moveTip(ev,
      `<div class="tt">${d.m.label}</div>₹${budgetLakh} lakh buys roughly <b>${Math.round(d.sqyd)} sq yd</b><br>
       at its median price of ${inr(d.m.median_psqyd)}/sq yd`)).on('mouseleave', hideTip);

    g.append('text').attr('x', innerW / 2).attr('y', innerH + 18).attr('text-anchor', 'middle')
      .attr('font-family', 'Helvetica, Arial').attr('font-size', 11).attr('fill', MUTED)
      .text(`Square yards of open plot buyable with ₹${budgetLakh} lakh`);
    const maxLbl = data[0].sqyd;
    g.append('text').attr('x', x(maxLbl) + 6).attr('y', -2)
      .attr('font-family', 'Helvetica, Arial').attr('font-size', 11).attr('fill', MUTED)
      .text(Math.round(maxLbl) + ' sq yd ≈ ' + (Math.round(maxLbl / 4840 * 10) / 10) + ' acre');
  }

  // =====================================================================
  // 5) STRIPS — every listing
  // =====================================================================
  function renderStrips() {
    const container = document.getElementById('chart-strips');
    if (!container) return;
    const mandals = usable().slice(0, 10);
    const width = widthOf('#chart-strips');
    const margin = { top: 14, right: 18, bottom: 44, left: 150 };
    const height = mandals.length * 56 + margin.top + margin.bottom;
    const all = mandals.flatMap(m => m.sample_listings || []);
    const xMax = d3.max(all, l => l.price_per_sqyd) * 1.05;
    const svg = d3.select(container).append('svg')
      .attr('viewBox', `0 0 ${width} ${height}`).attr('preserveAspectRatio', 'xMidYMid meet');
    const innerW = width - margin.left - margin.right;
    const innerH = height - margin.top - margin.bottom;
    const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);
    const x = d3.scaleLinear().domain([0, xMax]).range([0, innerW]);
    const y = d3.scaleBand().domain(mandals.map(m => m.key)).range([0, innerH]).padding(0.5);
    const ticks = [0, 10000, 25000, 50000, 75000, 100000].filter(t => t <= xMax);
    g.append('g').selectAll('line').data(ticks).enter().append('line')
      .attr('x1', d => x(d)).attr('x2', d => x(d)).attr('y1', 0).attr('y2', innerH).attr('stroke', '#eee');
    g.append('g').selectAll('text').data(ticks).enter().append('text')
      .attr('x', d => x(d)).attr('y', innerH + 22).attr('text-anchor', 'middle')
      .attr('font-family', 'Helvetica, Arial').attr('font-size', 10.5).attr('fill', MUTED)
      .text(d => d ? '₹' + (d / 1000) + 'k' : '₹0');
    mandals.forEach(m => {
      const row = g.append('g').attr('transform', `translate(0,${y(m.key)})`);
      row.append('text').attr('x', -10).attr('y', 0).attr('dy', '0.35em').attr('text-anchor', 'end')
        .attr('font-family', 'Helvetica, Arial').attr('font-size', 12).attr('fill', INK)
        .text(short(m.label));
      row.append('circle').attr('cx', x(m.median_psqyd)).attr('cy', 0).attr('r', 5)
        .attr('fill', 'none').attr('stroke', '#444').attr('stroke-width', 1.6).attr('class', 'med');
      (m.sample_listings || []).forEach(l => {
        row.append('circle').attr('cx', x(l.price_per_sqyd)).attr('cy', 0).attr('r', 4)
          .attr('fill', DISTRICT_COLORS[m.district]).attr('fill-opacity', 0.65)
          .style('cursor', 'pointer')
          .on('mousemove', e => moveTip(e,
            `<div class="tt">${l.locality || m.label}</div>${inr(l.price_per_sqyd)}/sq yd · total ${inr(l.price_inr)}<br><span class="tt-r">${l.area_sqyd.toFixed(0)} sq yd</span>`))
          .on('mouseleave', hideTip);
      });
    });
  }

  // =====================================================================
  // 6) TREND — region median over months, with selected-mandal overlay
  // =====================================================================
  function renderTrend() {
    const container = document.getElementById('chart-trend');
    if (!container) return;
    const series = window.SNAPSHOT_HISTORY || [];
    const width = widthOf('#chart-trend');
    const margin = { top: 24, right: 20, bottom: 44, left: 70 };
    const height = 300;
    const innerW = width - margin.left - margin.right;
    const innerH = height - margin.top - margin.bottom;
    const svg = d3.select(container).append('svg')
      .attr('viewBox', `0 0 ${width} ${height}`).attr('preserveAspectRatio', 'xMidYMid meet');
    const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);
    // Release the DOM element reference for the overlay re-renders
    container.__trend = { g, innerW, innerH, series, x: null, y: null, svg };
    if (!series.length) return;

    const dom = series.map(s => s.period);
    const xs = d3.scalePoint().domain(dom).range([0, innerW]).padding(0.4);
    const vals = series.map(s => s.value);
    const ymax = selectedKey && S.mandals[selectedKey] ? d3.max([...vals, S.mandals[selectedKey].median_psqyd]) : d3.max(vals);
    const y = d3.scaleLinear().domain([0, ymax * 1.12]).range([innerH, 0]);
    g.selectAll('*').remove();
    container.__trend.x = xs; container.__trend.y = y;

    g.append('g').selectAll('line').data(y.ticks(4)).enter().append('line')
      .attr('x1', 0).attr('x2', innerW).attr('y1', y).attr('y2', y).attr('stroke', '#eee');
    g.append('g').selectAll('text').data(y.ticks(4)).enter().append('text')
      .attr('x', -6).attr('y', y).attr('dy', '0.32em').attr('text-anchor', 'end')
      .attr('font-family', 'Helvetica, Arial').attr('font-size', 10).attr('fill', MUTED)
      .text(d => '₹' + (d / 1000) + 'k');

    const line = d3.line().x(d => xs(d.period)).y(d => y(d.value));
    if (series.length > 1) {
      g.append('path').datum(series).attr('fill', 'none').attr('stroke', '#0d4f6e')
        .attr('stroke-width', 3).attr('d', line);
    }
    g.selectAll('.pt').data(series).enter().append('circle').attr('class', 'pt')
      .attr('cx', d => xs(d.period)).attr('cy', d => y(d.value)).attr('r', 4.5)
      .attr('fill', '#fff').attr('stroke', '#0d4f6e').attr('stroke-width', 2);
    g.selectAll('.pv').data(series).enter().append('text').attr('class', 'pv')
      .attr('x', d => xs(d.period)).attr('y', d => y(d.value) - 10).attr('text-anchor', 'middle')
      .attr('font-family', 'Helvetica, Arial').attr('font-size', 11).attr('fill', INK)
      .text(d => inr(d.value));
    g.selectAll('.px').data(series).enter().append('text').attr('class', 'px')
      .attr('x', d => xs(d.period)).attr('y', innerH + 20).attr('text-anchor', 'middle')
      .attr('font-family', 'Helvetica, Arial').attr('font-size', 11).attr('fill', MUTED)
      .text(d => d.period);

    if (series.length < 2) {
      g.append('text').attr('x', innerW / 2).attr('y', innerH - 46).attr('text-anchor', 'middle')
        .attr('font-family', 'Helvetica, Arial').attr('font-size', 12.5).attr('fill', MUTED)
        .text('This is the first snapshot — the trend line begins here and grows each month.');
    }
  }

  function highlightTrend() {
    const c = document.getElementById('chart-trend');
    if (!c || !c.__trend || !selectedKey) return;
    const t = c.__trend; const m = S.mandals[selectedKey]; if (!m) return;
    const { svg, innerW, innerH } = t;
    d3.selectAll('#chart-trend .sel-g').remove();
    const g = svg.append('g').attr('class', 'sel-g').attr('transform', `translate(${t.x ? 0 : 70},0)`);
    // simply draw a dashed reference at the selected mandal's median value
    g.append('line').attr('x1', 0).attr('x2', innerW).attr('y1', t.y(m.median_psqyd)).attr('y2', t.y(m.median_psqyd))
      .attr('stroke', DISTRICT_COLORS[m.district]).attr('stroke-dasharray', '3,3').attr('opacity', 0.6);
    g.append('text').attr('x', innerW - 6).attr('y', t.y(m.median_psqyd) - 6).attr('text-anchor', 'end')
      .attr('font-family', 'Helvetica, Arial').attr('font-size', 11).attr('fill', DISTRICT_COLORS[m.district])
      .text(short(m.label) + ' · ' + inr(m.median_psqyd));
  }

  // =====================================================================
  function init() {
    const steps = [
      ['map', renderMap], ['picker', renderPicker], ['detail', renderDetail],
      ['dumb-legend', buildDumbLegend], ['dumbbell', renderDumbbell],
      ['afford', () => renderAfford(50)],
      ['strips', renderStrips], ['trend', renderTrend]
    ];
    steps.forEach(([name, fn]) => { try { fn(); } catch (e) { console.error('render[' + name + ']', e && e.stack || e); } });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
