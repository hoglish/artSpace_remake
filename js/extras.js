/*
  ArtSpace — extras.js (добавлено патчем)
  Подключается после js/app.js. Содержит:
  1) эффекты: полоса прокрутки, подсветка карточек, параллакс в hero, конфетти после записи;
  2) быстрый поиск (Ctrl+K или «/»);
  3) инструменты на странице события: календарь (.ics) и «Поделиться»;
  4) страницы «Live» и «Подборки»;
  5) регистрация service worker (кэш для быстрой повторной загрузки, работает на http/https).
*/
(function () {
  'use strict';

  const AS = window.AS || {};
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const page = document.body.dataset.page;
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const finePointer = matchMedia('(hover: hover) and (pointer: fine)').matches;
  const esc = AS.esc || (s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])));
  const MONTHS_SHORT = ['янв', 'фев', 'мар', 'апр', 'мая', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'];
  const hasData = typeof EVENTS !== 'undefined' && AS.cardHtml;
  const startOf = AS.startOf || (e => new Date(e.date + 'T' + e.time + ':00'));

  /* ---------- 0. Дополнительные иконки в спрайт ---------- */
  (function addIcons() {
    if ($('#i-bolt')) return;
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('aria-hidden', 'true');
    svg.style.display = 'none';
    svg.innerHTML =
      '<symbol id="i-bolt" viewBox="0 0 24 24"><path d="M13 2 4 14h7l-1 8 9-12h-7z"/></symbol>' +
      '<symbol id="i-clock" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></symbol>' +
      '<symbol id="i-shuffle" viewBox="0 0 24 24"><path d="M16 3h5v5M4 20 21 3M21 16v5h-5M15 15l6 6M4 4l5 5"/></symbol>' +
      '<symbol id="i-download" viewBox="0 0 24 24"><path d="M12 3v12m-5-5 5 5 5-5M5 21h14"/></symbol>' +
      '<symbol id="i-grid" viewBox="0 0 24 24"><path d="M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z"/></symbol>' +
      '<symbol id="i-arrow" viewBox="0 0 24 24"><path d="M5 12h14m-6-6 6 6-6 6"/></symbol>';
    document.body.prepend(svg);
  })();
  const ic = (n, c = '') => `<svg class="icon ${c}" aria-hidden="true"><use href="#i-${n}"></use></svg>`;

  /* ---------- 2. Эффекты ---------- */
  // 2.1 полоса прокрутки
  (function progress() {
    const bar = document.createElement('div');
    bar.className = 'scroll-progress';
    bar.setAttribute('aria-hidden', 'true');
    bar.innerHTML = '<i></i>';
    document.body.prepend(bar);
    const fill = bar.firstChild;
    let raf = 0;
    const upd = () => {
      raf = 0;
      const h = document.documentElement.scrollHeight - innerHeight;
      fill.style.transform = 'scaleX(' + (h > 0 ? Math.min(1, scrollY / h) : 0) + ')';
    };
    addEventListener('scroll', () => { if (!raf) raf = requestAnimationFrame(upd); }, { passive: true });
    upd();
  })();

  // 2.2 подсветка карточек за курсором и параллакс постеров в hero
  if (finePointer && !reduce) {
    let raf = 0, lastEv = null;
    document.addEventListener('pointermove', ev => {
      lastEv = ev;
      if (raf) return;
      raf = requestAnimationFrame(() => {
        raf = 0;
        const t = lastEv.target;
        const card = t.closest && t.closest('.event-card');
        if (card) {
          const r = card.getBoundingClientRect();
          card.style.setProperty('--mx', (lastEv.clientX - r.left) + 'px');
          card.style.setProperty('--my', (lastEv.clientY - r.top) + 'px');
        }
        const hero = t.closest && t.closest('.hero');
        if (hero) {
          const col = $('.hero__collage', hero);
          if (col) {
            const r = hero.getBoundingClientRect();
            col.style.setProperty('--mx', ((lastEv.clientX - r.left) / r.width - 0.5) * 2);
            col.style.setProperty('--my', ((lastEv.clientY - r.top) / r.height - 0.5) * 2);
          }
        }
      });
    }, { passive: true });
    const hero = $('.hero');
    if (hero) hero.addEventListener('pointerleave', () => {
      const col = $('.hero__collage', hero);
      if (col) { col.style.setProperty('--mx', 0); col.style.setProperty('--my', 0); }
    });
  }

  // 2.3 конфетти
  function confetti() {
    if (reduce) return;
    const c = document.createElement('canvas');
    c.className = 'confetti';
    c.setAttribute('aria-hidden', 'true');
    document.body.append(c);
    const dpr = Math.min(devicePixelRatio || 1, 2);
    c.width = innerWidth * dpr; c.height = innerHeight * dpr;
    const ctx = c.getContext('2d');
    const colors = ['#ff4b26', '#2b3fe0', '#ffc933', '#f4a6c0', '#bdeb3a', '#ffffff'];
    const P = Array.from({ length: 150 }, () => ({
      x: innerWidth / 2 + (Math.random() - 0.5) * 180, y: innerHeight * 0.35,
      vx: (Math.random() - 0.5) * 14, vy: -Math.random() * 13 - 4,
      w: 6 + Math.random() * 7, h: 4 + Math.random() * 6,
      r: Math.random() * 6, vr: (Math.random() - 0.5) * 0.4,
      c: colors[(Math.random() * colors.length) | 0]
    }));
    let last = performance.now();
    (function frame(now) {
      const dt = Math.min(32, now - last) / 16; last = now;
      ctx.clearRect(0, 0, c.width, c.height);
      let alive = 0;
      P.forEach(p => {
        p.vy += 0.35 * dt; p.vx *= 0.995; p.x += p.vx * dt; p.y += p.vy * dt; p.r += p.vr * dt;
        if (p.y < innerHeight + 30) alive++;
        ctx.save(); ctx.translate(p.x * dpr, p.y * dpr); ctx.rotate(p.r);
        ctx.fillStyle = p.c; ctx.fillRect(-p.w / 2 * dpr, -p.h / 2 * dpr, p.w * dpr, p.h * dpr);
        ctx.restore();
      });
      if (alive) requestAnimationFrame(frame); else c.remove();
    })(last);
  }
  AS.confetti = confetti;
  if (page === 'tickets' && new URLSearchParams(location.search).get('new')) setTimeout(confetti, 400);

  /* ---------- 3. Быстрый поиск (Ctrl+K, «/») ---------- */
  function initCmdk() {
    if (typeof EVENTS === 'undefined' || typeof HTMLDialogElement === 'undefined') return;
    const norm = s => String(s).toLowerCase().replace(/ё/g, 'е');
    const PAGES = [
      ['index.html', 'Главная'], ['catalog.html', 'Каталог событий'], ['live.html', 'Live — ближайшие события'],
      ['collections.html', 'Подборки'], ['organizers.html', 'Организаторы'], ['reviews.html', 'Отзывы'],
      ['favorites.html', 'Избранное'], ['tickets.html', 'Мои записи'], ['about.html', 'О проекте'],
      ['contacts.html', 'Контакты'], ['privacy.html', 'Конфиденциальность и условия']
    ];
    const all = [];
    EVENTS.forEach(e => all.push({
      t: e.title, s: CATEGORIES[e.category] + ' · ' + e.venue + ', ' + e.city, href: 'product.html?id=' + e.id, k: 'Событие',
      hay: norm([e.title, e.venue, e.city, e.organizer, CATEGORIES[e.category], e.short].join(' ')), date: e.date + e.time
    }));
    Array.from(new Set(EVENTS.map(e => e.organizer))).forEach(o => all.push({
      t: o, s: 'События организатора', href: 'catalog.html?organizer=' + encodeURIComponent(o), k: 'Организатор', hay: norm(o)
    }));
    PAGES.forEach(p => all.push({ t: p[1], s: p[0], href: p[0], k: 'Страница', hay: norm(p[1] + ' ' + p[0]) }));

    const dlg = document.createElement('dialog');
    dlg.className = 'cmdk';
    dlg.setAttribute('aria-label', 'Быстрый поиск');
    dlg.innerHTML =
      '<form class="cmdk__box" autocomplete="off"><div class="cmdk__bar">' + ic('search') +
      '<input class="cmdk__input" type="search" placeholder="Событие, организатор, город или страница…" aria-label="Поиск по сайту" aria-controls="cmdk-list">' +
      '<kbd>Esc</kbd></div><ul class="cmdk__list" id="cmdk-list" role="listbox"></ul>' +
      '<p class="cmdk__hint"><kbd>↑</kbd><kbd>↓</kbd> выбрать · <kbd>Enter</kbd> открыть · <kbd>Ctrl</kbd>+<kbd>K</kbd> или <kbd>/</kbd> — поиск в любой момент</p></form>';
    document.body.append(dlg);
    const input = $('.cmdk__input', dlg), list = $('.cmdk__list', dlg);
    let items = [], idx = 0;

    const KIND_RANK = { 'Событие': 0, 'Организатор': 1, 'Страница': 2 };
    const rank = (i, q) => KIND_RANK[i.k] - (norm(i.t).startsWith(q) ? 0.5 : 0);
    function results(q) {
      q = norm(q).trim();
      if (!q) {
        const soon = all.filter(i => i.k === 'Событие').sort((a, b) => a.date.localeCompare(b.date)).slice(0, 5);
        return soon.concat(all.filter(i => i.href === 'live.html' || i.href === 'collections.html'));
      }
      const tokens = q.split(/\s+/);
      return all.filter(i => tokens.every(t => i.hay.includes(t)))
        .sort((a, b) => rank(a, q) - rank(b, q) || a.t.localeCompare(b.t, 'ru'))
        .slice(0, 8);
    }
    function render() {
      items = results(input.value);
      idx = Math.min(idx, Math.max(0, items.length - 1));
      list.innerHTML = items.length
        ? items.map((i, n) => '<li role="option" id="cmdk-' + n + '" aria-selected="' + (n === idx) + '"><a href="' + esc(i.href) + '"><span class="cmdk__kind">' + i.k + '</span><span class="cmdk__t">' + esc(i.t) + '</span><span class="cmdk__s">' + esc(i.s) + '</span></a></li>').join('')
        : '<li class="cmdk__empty">Ничего не найдено. Попробуйте другое слово.</li>';
      input.setAttribute('aria-activedescendant', items.length ? 'cmdk-' + idx : '');
    }
    function mark() {
      $$('li[role=option]', list).forEach((li, n) => li.setAttribute('aria-selected', n === idx));
      input.setAttribute('aria-activedescendant', 'cmdk-' + idx);
      const cur = $('#cmdk-' + idx, list);
      if (cur) cur.scrollIntoView({ block: 'nearest' });
    }
    input.addEventListener('input', () => { idx = 0; render(); });
    input.addEventListener('keydown', ev => {
      if (ev.key === 'ArrowDown') { ev.preventDefault(); idx = (idx + 1) % Math.max(1, items.length); mark(); }
      else if (ev.key === 'ArrowUp') { ev.preventDefault(); idx = (idx - 1 + items.length) % Math.max(1, items.length); mark(); }
      else if (ev.key === 'Enter') { ev.preventDefault(); if (items[idx]) location.href = items[idx].href; }
    });
    $('form', dlg).addEventListener('submit', ev => ev.preventDefault());
    list.addEventListener('mousemove', ev => {
      const li = ev.target.closest('li[role=option]');
      if (li) { const n = +li.id.replace('cmdk-', ''); if (n !== idx) { idx = n; mark(); } }
    });
    dlg.addEventListener('click', ev => { if (ev.target === dlg) dlg.close(); });
    function open() {
      if (dlg.open) return;
      input.value = ''; idx = 0; render();
      dlg.showModal(); input.focus();
    }
    document.addEventListener('keydown', ev => {
      const tag = (document.activeElement && document.activeElement.tagName) || '';
      const typing = /INPUT|TEXTAREA|SELECT/.test(tag) || (document.activeElement && document.activeElement.isContentEditable);
      if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === 'k') { ev.preventDefault(); dlg.open ? dlg.close() : open(); }
      else if (ev.key === '/' && !typing && !ev.ctrlKey && !ev.metaKey && !ev.altKey) { ev.preventDefault(); open(); }
    });
    const bar = $('.order-lg-last');
    if (bar) {
      const b = document.createElement('button');
      b.type = 'button'; b.id = 'cmdkBtn'; b.className = 'icon-btn';
      b.setAttribute('aria-label', 'Поиск по сайту (Ctrl+K)'); b.title = 'Поиск (Ctrl+K или /)';
      b.innerHTML = ic('search');
      b.addEventListener('click', open);
      bar.prepend(b);
    }
  }
  initCmdk();

  /* ---------- 4. Страница события: календарь и «Поделиться» ---------- */
  function icsEscape(s) { return String(s).replace(/\\/g, '\\\\').replace(/;/g, '\\;').replace(/,/g, '\\,').replace(/\n/g, '\\n'); }
  function icsStamp(d) {
    const p = n => String(n).padStart(2, '0');
    return d.getFullYear() + p(d.getMonth() + 1) + p(d.getDate()) + 'T' + p(d.getHours()) + p(d.getMinutes()) + '00';
  }
  function downloadIcs(e) {
    const start = startOf(e), end = new Date(start.getTime() + 2 * 3600e3);
    const lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//ArtSpace//RU', 'CALSCALE:GREGORIAN', 'BEGIN:VEVENT',
      'UID:' + e.id + '-' + e.date + '@artspace', 'DTSTAMP:' + icsStamp(new Date()), 'DTSTART:' + icsStamp(start), 'DTEND:' + icsStamp(end),
      'SUMMARY:' + icsEscape(e.title), 'LOCATION:' + icsEscape(e.address), 'DESCRIPTION:' + icsEscape(e.short), 'END:VEVENT', 'END:VCALENDAR'];
    const blob = new Blob([lines.join('\r\n')], { type: 'text/calendar;charset=utf-8' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob); a.download = e.id + '.ics';
    document.body.append(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  }
  async function shareLink(e) {
    const url = location.href;
    if (navigator.share) { try { await navigator.share({ title: e.title, text: e.short, url }); return; } catch (_) { /* отмена */ } }
    try { await navigator.clipboard.writeText(url); AS.toast && AS.toast('Ссылка скопирована'); }
    catch (_) { window.prompt('Скопируйте ссылку:', url); }
  }
  function initProductTools() {
    const e = hasData && eventById(new URLSearchParams(location.search).get('id'));
    const host = $('#event-fav');
    if (!e || !host || $('.pt-tools')) return;
    const box = document.createElement('div');
    box.className = 'pt-tools';
    box.innerHTML =
      '<button type="button" class="btn btn-outline-primary btn-sm" data-pt="ics">' + ic('download', 'icon--sm') + ' В календарь</button>' +
      '<button type="button" class="btn btn-outline-primary btn-sm" data-pt="share">' + ic('share', 'icon--sm') + ' Поделиться</button>';
    host.after(box);
    box.addEventListener('click', ev => {
      const b = ev.target.closest('[data-pt]');
      if (!b) return;
      if (b.dataset.pt === 'ics') { downloadIcs(e); AS.toast && AS.toast('Файл календаря скачан'); }
      else shareLink(e);
    });
  }
  if (page === 'product') initProductTools();

  /* ---------- 5. Live ---------- */
  const DUR = e => (e.category === 'painting' || (e.format !== 'online' && (e.category === 'photography' || e.category === 'contemporary'))) ? 240 : 150;
  function stateOf(e, now) {
    const s = startOf(e).getTime(), en = s + DUR(e) * 60000;
    if (now >= en) return 'past';
    if (now >= s) return 'live';
    return (s - now) < 48 * 3600e3 ? 'soon' : 'later';
  }
  function fmtLeft(ms) {
    ms = Math.max(0, ms);
    const d = Math.floor(ms / 864e5), h = Math.floor(ms % 864e5 / 36e5), m = Math.floor(ms % 36e5 / 6e4), s = Math.floor(ms % 6e4 / 1e3);
    if (d > 0) return 'через ' + d + ' д ' + h + ' ч';
    if (h > 0) return 'через ' + h + ' ч ' + m + ' мин';
    return 'через ' + m + ' мин ' + String(s).padStart(2, '0') + ' с';
  }
  const pad = n => String(Math.max(0, n)).padStart(2, '0');

  function initLive() {
    if (!hasData || !$('#live-now')) return;
    const f = { city: $('#lv-city'), online: $('#lv-online'), seats: $('#lv-seats') };
    Array.from(new Set(EVENTS.map(e => e.city))).sort((a, b) => a.localeCompare(b, 'ru')).forEach(c => {
      const o = document.createElement('option'); o.value = c; o.textContent = c; f.city.append(o);
    });
    let sig = '';

    const visible = now => EVENTS.filter(e => {
      if (f.city.value && e.city !== f.city.value) return false;
      if (f.online.checked && e.format !== 'online') return false;
      if (f.seats.checked && AS.seatsLeft(e) === 0) return false;
      return stateOf(e, now) !== 'past';
    }).sort((a, b) => startOf(a) - startOf(b));

    function liveCard(e, i, st) {
      const chip = st === 'live'
        ? '<span class="tag tag--live"><span class="live-dot live-dot--sm"></span>Идёт сейчас</span>'
        : '<span class="tag tag--count" data-countdown="' + startOf(e).getTime() + '"></span>';
      return AS.cardHtml(e)
        .replace('<div class="event-card__labels">', '<div class="event-card__labels">' + chip)
        .replace('<div class="col-12 col-md-6 col-xl-4">', '<div class="col-12 col-md-6 col-xl-4 anim-in" style="--i:' + i + '">');
    }
    function nextCard(e, st, now) {
      const s = startOf(e).getTime(), dur = DUR(e) * 60000;
      const seats = AS.seatsInfo(e);
      const target = st === 'live' ? s + dur : s;
      const kicker = st === 'live'
        ? '<span class="live-dot"></span> Идёт сейчас · до конца ≈'
        : '<span class="live-dot live-dot--idle"></span> Следующее событие · начало через';
      const prog = st === 'live'
        ? '<div class="progress live-next__prog" role="progressbar" aria-label="Прошло времени" aria-valuemin="0" aria-valuemax="100" aria-valuenow="' + Math.round((now - s) / dur * 100) + '"><div class="progress-bar" style="width:' + Math.round((now - s) / dur * 100) + '%"></div></div>' : '';
      return '<div class="live-next__poster"><img src="images/posters/' + e.id + '.svg" alt="" width="600" height="400"></div>' +
        '<div class="live-next__body"><p class="live-next__kicker">' + kicker + '</p>' +
        '<div class="countdown" role="timer" data-target="' + target + '">' +
        ['d:дней', 'h:часов', 'm:минут', 's:секунд'].map(u => { const p = u.split(':'); return '<div class="countdown__cell"><span class="countdown__num" data-u="' + p[0] + '">00</span><span class="countdown__lbl">' + p[1] + '</span></div>'; }).join('') +
        '</div>' + prog +
        '<h2 class="live-next__title"><a href="product.html?id=' + e.id + '">' + esc(e.title) + '</a></h2>' +
        '<p class="live-next__meta">' + ic('calendar', 'icon--sm') + ' ' + AS.dayLabel(e.date) + ', ' + e.time + ' &nbsp; ' + ic('pin', 'icon--sm') + ' ' + esc(e.venue) + ', ' + esc(e.city) + '</p>' +
        '<div class="d-flex flex-wrap gap-2 align-items-center"><a class="btn btn-primary" href="order.html?id=' + e.id + '">' + (seats.left === 0 ? 'Мест нет' : 'Записаться') + '</a>' +
        '<a class="btn btn-outline-light" href="product.html?id=' + e.id + '">Подробнее</a>' +
        (seats.text ? '<span class="seats ' + seats.cls + ' live-next__seats">' + seats.text + '</span>' : '') + '</div></div>';
    }
    function render() {
      const now = Date.now(), list = visible(now);
      const live = list.filter(e => stateOf(e, now) === 'live');
      const soon = list.filter(e => stateOf(e, now) === 'soon');
      const later = list.filter(e => stateOf(e, now) === 'later').slice(0, 10);
      sig = list.map(e => e.id + stateOf(e, now)).join(',') + '|' + f.city.value + f.online.checked + f.seats.checked;

      const first = live[0] || soon[0] || later[0];
      const host = $('#live-next');
      host.hidden = !first;
      if (first) host.innerHTML = nextCard(first, stateOf(first, now), now);

      $('#live-now').innerHTML = live.map((e, i) => liveCard(e, i, 'live')).join('');
      $('#live-now-empty').hidden = live.length > 0;
      $('#live-soon').innerHTML = soon.map((e, i) => liveCard(e, i, 'soon')).join('');
      $('#live-soon-empty').hidden = soon.length > 0;
      $('#live-timeline').innerHTML = later.map((e, i) => {
        const d = new Date(e.date + 'T12:00:00');
        return '<li class="tl-item anim-in" style="--i:' + i + '"><div class="tl-date"><b>' + d.getDate() + '</b><span>' + MONTHS_SHORT[d.getMonth()] + '</span></div>' +
          '<div class="tl-body"><a href="product.html?id=' + e.id + '">' + esc(e.title) + '</a><span class="text-muted-2">' + e.time + ' · ' + esc(e.venue) + ', ' + esc(e.city) + '</span></div>' +
          '<span class="tag tag--count" data-countdown="' + startOf(e).getTime() + '"></span>' +
          '<a class="btn btn-outline-primary btn-sm" href="order.html?id=' + e.id + '">Записаться</a></li>';
      }).join('');
      $('#live-later-empty').hidden = later.length > 0;
      $('#live-empty').hidden = list.length > 0;
      $('#live-count').textContent = list.length ? 'В расписании: ' + list.length + ' ' + AS.plural(list.length, ['событие', 'события', 'событий']) : '';
      tick();
    }
    function tick() {
      const now = Date.now();
      $$('[data-countdown]').forEach(el => {
        const left = +el.dataset.countdown - now;
        el.textContent = left > 0 ? fmtLeft(left) : 'начинается';
      });
      const cd = $('.countdown');
      if (cd) {
        let ms = Math.max(0, +cd.dataset.target - now);
        const v = { d: Math.floor(ms / 864e5), h: Math.floor(ms % 864e5 / 36e5), m: Math.floor(ms % 36e5 / 6e4), s: Math.floor(ms % 6e4 / 1e3) };
        $$('.countdown__num', cd).forEach(n => {
          const t = pad(v[n.dataset.u]);
          if (n.textContent !== t) {
            n.textContent = t;
            if (!reduce) { n.classList.remove('tick'); void n.offsetWidth; n.classList.add('tick'); }
          }
        });
      }
    }
    // перерисовываем списки только когда изменился состав/состояния
    setInterval(() => {
      if (document.hidden) return;
      const now = Date.now(), list = visible(now);
      const s2 = list.map(e => e.id + stateOf(e, now)).join(',') + '|' + f.city.value + f.online.checked + f.seats.checked;
      if (s2 !== sig) render(); else tick();
    }, 1000);
    document.addEventListener('visibilitychange', () => { if (!document.hidden) { render(); } });
    Object.values(f).forEach(el => el.addEventListener('change', render));
    window.addEventListener('storage', render);

    // «Удиви меня»
    const sbtn = $('#lv-surprise'), sbox = $('#lv-surprise-box');
    function surpriseHtml(e, final) {
      return '<img class="surprise__img" src="images/posters/' + e.id + '.svg" alt="" width="160" height="107">' +
        '<div class="surprise__text"><p class="surprise__kicker">' + (final ? 'Ваш вечер:' : 'Подбираем…') + '</p>' +
        '<p class="surprise__title">' + esc(e.title) + '</p>' +
        '<p class="surprise__meta">' + AS.dayLabel(e.date) + ', ' + e.time + ' · ' + esc(e.venue) + ', ' + esc(e.city) + '</p>' +
        (final ? '<div class="d-flex flex-wrap gap-2"><a class="btn btn-primary btn-sm" href="product.html?id=' + e.id + '">Посмотреть</a><button type="button" class="btn btn-outline-primary btn-sm" id="lv-again">Ещё вариант</button></div>' : '') + '</div>';
    }
    function surprise() {
      const now = Date.now();
      const pool = EVENTS.filter(e => stateOf(e, now) !== 'past' && AS.seatsLeft(e) > 0);
      if (!pool.length) { AS.toast && AS.toast('Сейчас нет подходящих событий', 'info'); return; }
      const pick = pool[Math.floor(Math.random() * pool.length)];
      const total = reduce ? 1 : 14;
      sbox.hidden = false;
      let n = 0;
      (function step() {
        const final = n === total - 1;
        const e = final ? pick : pool[Math.floor(Math.random() * pool.length)];
        sbox.innerHTML = surpriseHtml(e, final);
        sbox.classList.toggle('is-final', final);
        n++;
        if (!final) setTimeout(step, 55 + n * 16);
        else { const a = $('a', sbox); if (a) a.focus({ preventScroll: true }); }
      })();
    }
    if (sbtn) sbtn.addEventListener('click', surprise);
    if (sbox) sbox.addEventListener('click', ev => { if (ev.target.id === 'lv-again') surprise(); });
    render();
  }
  if (page === 'live') initLive();

  /* ---------- 6. Подборки ---------- */
  function initCollections() {
    if (!hasData || !$('#col-tiles')) return;
    const now = () => Date.now();
    const dFrom = e => Math.round((new Date(e.date + 'T12:00:00') - new Date(isoOffset(0) + 'T12:00:00')) / 864e5);
    const COLS = [
      { id: 'weekend', title: 'На выходные', icon: 'calendar', c: 'var(--yellow)', text: 'Что посмотреть в ближайшую субботу и воскресенье.', test: e => { const d = new Date(e.date + 'T12:00:00').getDay(); return (d === 6 || d === 0) && dFrom(e) <= 9; } },
      { id: 'free', title: 'Бесплатно', icon: 'check', c: 'var(--lime)', text: 'Выставки и лекции, на которые не нужно покупать билет — достаточно записаться.', test: e => e.price === 0 },
      { id: 'family', title: 'С детьми', icon: 'heart', c: 'var(--pink)', text: 'События с меткой «Для всей семьи»: кукольный театр, мастерские и концерты для любого возраста.', test: e => e.labels.indexOf('family') > -1 },
      { id: 'online', title: 'Не выходя из дома', icon: 'bolt', c: '#9fd4ff', text: 'Онлайн-трансляции и мастер-классы: нужен только интернет.', test: e => e.format === 'online' },
      { id: 'budget', title: 'До 1 000 ₽', icon: 'ticket', c: 'var(--yellow)', text: 'Недорогие события: культурный вечер без больших трат.', test: e => e.price > 0 && e.price <= 1000 },
      { id: 'hits', title: 'Хиты афиши', icon: 'star', c: 'var(--red)', text: 'То, что выбирают чаще всего: хиты и самые популярные события.', test: e => e.labels.indexOf('hit') > -1 || e.popularity >= 90 },
      { id: 'last', title: 'Последние места', icon: 'clock', c: 'var(--lime)', text: 'Мест почти не осталось — решайтесь, пока есть возможность.', test: e => { const l = AS.seatsLeft(e); return l > 0 && l <= 15; } },
      { id: 'date', title: 'На свидание', icon: 'heart', c: 'var(--pink)', text: 'Вечерние офлайн-события для двоих: музыка, театр, живопись.', test: e => e.format !== 'online' && ['music', 'theatre', 'painting'].indexOf(e.category) > -1 && e.time >= '18:00' && e.price >= 900 }
    ];
    const upcoming = e => startOf(e).getTime() + DUR(e) * 60000 > now();
    const eventsOf = c => EVENTS.filter(e => upcoming(e) && c.test(e)).sort((a, b) => startOf(a) - startOf(b));
    const tiles = $('#col-tiles'), grid = $('#col-grid');
    let current = '';

    function renderTiles() {
      tiles.innerHTML = COLS.map((c, i) => {
        const n = eventsOf(c).length;
        return '<div class="col-6 col-md-4 col-xl-3 anim-in" style="--i:' + i + '"><button type="button" class="col-tile" data-col="' + c.id + '" style="--c:' + c.c + '" aria-pressed="' + (c.id === current) + '">' +
          '<span class="col-tile__icon">' + ic(c.icon) + '</span><span class="col-tile__title">' + c.title + '</span>' +
          '<span class="col-tile__count">' + n + ' ' + AS.plural(n, ['событие', 'события', 'событий']) + '</span></button></div>';
      }).join('');
    }
    function select(id, push) {
      const c = COLS.find(x => x.id === id) || COLS[0];
      current = c.id;
      $$('.col-tile', tiles).forEach(b => b.setAttribute('aria-pressed', b.dataset.col === current));
      const list = eventsOf(c);
      $('#col-title').textContent = c.title;
      $('#col-text').textContent = c.text;
      $('#col-count').textContent = list.length ? list.length + ' ' + AS.plural(list.length, ['событие', 'события', 'событий']) : '';
      grid.innerHTML = list.map((e, i) => AS.cardHtml(e).replace('<div class="col-12 col-md-6 col-xl-4">', '<div class="col-12 col-md-6 col-xl-4 anim-in" style="--i:' + i + '">')).join('');
      $('#col-empty').hidden = list.length > 0;
      $('#col-random').hidden = list.length < 2;
      if (push) history.replaceState(null, '', '#' + c.id);
    }
    tiles.addEventListener('click', ev => {
      const b = ev.target.closest('[data-col]');
      if (!b) return;
      select(b.dataset.col, true);
      $('#col-result').scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' });
    });
    $('#col-random').addEventListener('click', () => {
      const cards = $$('.event-card', grid);
      if (!cards.length) return;
      cards.forEach(c => c.classList.remove('is-picked'));
      const pick = cards[Math.floor(Math.random() * cards.length)];
      pick.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'center' });
      pick.classList.add('is-picked');
      setTimeout(() => pick.classList.remove('is-picked'), 2600);
    });
    window.addEventListener('hashchange', () => select(location.hash.slice(1), false));
    window.addEventListener('storage', () => { renderTiles(); select(current, false); });
    const start = COLS.find(c => c.id === location.hash.slice(1)) || COLS.find(c => eventsOf(c).length) || COLS[0];
    current = start.id;
    renderTiles();
    select(start.id, false);
  }
  if (page === 'collections') initCollections();

  /* ---------- 7. Service worker (быстрый повторный заход, офлайн-кэш) ---------- */
  if ('serviceWorker' in navigator && (location.protocol === 'https:' || location.hostname === 'localhost' || location.hostname === '127.0.0.1')) {
    window.addEventListener('load', () => navigator.serviceWorker.register('sw.js').catch(() => {}));
  }
})();