#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
patch_artspace.py — патч для ArtSpace remake.

Запуск (из папки проекта, где лежит index.html):
    python3 patch_artspace.py            # применить патч
    python3 patch_artspace.py --no-download   # без скачивания фото
    python3 patch_artspace.py --force-pages   # пересоздать live.html / collections.html

Что делает:
  1. Тема и уведомление о хранении данных запоминаются на ВСЕХ страницах
     (включая открытие через file://), смена темы — с анимацией «круговой волны».
  2. Скачивает фото Unsplash в images/photos/ и подключает по схеме
     «локальный файл → онлайн → иллюстрация», с размытым placeholder и таймаутом.
     Файлы images/orgs/*.svg получают ASCII-копии (работает на любом сервере и ОС).
  3. Возвращает «Главная» и «О проекте» в шапку/подвал, добавляет Live и Подборки.
  4. Новые страницы: live.html (ближайшие события с отсчётом) и collections.html (подборки).
  5. Новые фичи: быстрый поиск (Ctrl+K или «/»), «В календарь (.ics)» и «Поделиться»
     на странице события, «Удиви меня», конфетти после записи, полоса прокрутки,
     подсветка карточек, параллакс в hero, service worker для быстрой повторной загрузки.

Скрипт безопасно запускать повторно. Оригиналы сохраняются в .patch_backup/.
Если вы пересоберёте сайт своим генератором — просто запустите патч ещё раз.
"""
import argparse
import concurrent.futures
import pathlib
import re
import shutil
import sys
import time
import urllib.request

# ----------------------------------------------------------------------------
# Встроенные файлы
# ----------------------------------------------------------------------------
EXTRAS_JS = r'''/*
  ArtSpace — extras.js (добавлено патчем)
  Подключается после js/app.js. Содержит:
  1) надёжную загрузку картинок: локально → онлайн → иллюстрация (с таймаутом и размытым placeholder);
  2) эффекты: полоса прокрутки, подсветка карточек, параллакс в hero, конфетти после записи;
  3) быстрый поиск (Ctrl+K или «/»);
  4) инструменты на странице события: календарь (.ics) и «Поделиться»;
  5) страницы «Live» и «Подборки»;
  6) регистрация service worker (кэш для быстрой повторной загрузки, работает на http/https).
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
  const BLANK = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7';
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

  /* ---------- 1. Картинки: локально → онлайн → иллюстрация ---------- */
  function advance(img) {
    clearTimeout(img.__t);
    const list = (img.dataset.fallback || '').split('|').filter(Boolean);
    if (!list.length) {
      img.classList.remove('is-loading');
      if (img.getAttribute('src') !== BLANK) img.src = BLANK;
      return;
    }
    img.dataset.fallback = list.slice(1).join('|');
    img.classList.add('is-loading');
    img.src = list[0];
    startTimer(img);
  }
  function startTimer(img) {
    clearTimeout(img.__t);
    if (!img.dataset.fallback) return;
    img.__t = setTimeout(() => {
      if (!img.naturalWidth && img.dataset.fallback) advance(img);
    }, 6500);
  }
  const imgObserver = 'IntersectionObserver' in window
    ? new IntersectionObserver(entries => entries.forEach(en => {
        if (en.isIntersecting) { imgObserver.unobserve(en.target); startTimer(en.target); }
      }), { rootMargin: '300px' })
    : null;
  function armImage(img) {
    if (img.__armed) return;
    img.__armed = true;
    const ph = img.dataset.placeholder;
    if (ph) {
      img.style.backgroundImage = 'url("' + ph + '")';
      img.style.backgroundSize = 'cover';
      img.style.backgroundPosition = 'center';
    }
    if (img.complete) {
      if (!img.naturalWidth && img.getAttribute('src') && img.getAttribute('src') !== BLANK) advance(img);
      return;
    }
    img.classList.add('is-loading');
    img.addEventListener('load', () => { clearTimeout(img.__t); img.classList.remove('is-loading'); });
    if (imgObserver) imgObserver.observe(img); else startTimer(img);
  }
  document.addEventListener('error', ev => {
    const t = ev.target;
    if (t && t.tagName === 'IMG' && (t.dataset.fallback !== undefined || t.dataset.placeholder)) advance(t);
  }, true);
  $$('img[data-fallback], img[data-placeholder]').forEach(armImage);
  new MutationObserver(muts => muts.forEach(m => m.addedNodes.forEach(n => {
    if (n.nodeType !== 1) return;
    if (n.tagName === 'IMG' && (n.dataset.fallback !== undefined || n.dataset.placeholder)) armImage(n);
    else $$('img[data-fallback], img[data-placeholder]', n).forEach(armImage);
  }))).observe(document.body, { childList: true, subtree: true });

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
})();'''
EXTRAS_CSS = r'''/* ================= ArtSpace patch: extras ================= */

/* --- навигация: 6 пунктов и Live-индикатор --- */
@media (min-width:992px){.as-navbar .nav-link{padding:.4rem .6rem;font-size:.95rem}}
.nav-live{display:inline-flex;align-items:center;gap:.4rem}

/* --- полоса прокрутки --- */
.scroll-progress{position:fixed;inset:0 0 auto 0;height:4px;z-index:1090;pointer-events:none}
.scroll-progress i{display:block;height:100%;background:linear-gradient(90deg,var(--red),var(--yellow),var(--lime));transform-origin:0 50%;transform:scaleX(0)}

/* --- анимация смены темы --- */
::view-transition-old(root),::view-transition-new(root){animation:none;mix-blend-mode:normal}
::view-transition-old(root){z-index:1}
::view-transition-new(root){z-index:2147483646}
.theme-anim,.theme-anim *,.theme-anim *::before,.theme-anim *::after{transition:background-color .45s ease,color .45s ease,border-color .45s ease,box-shadow .45s ease,fill .45s ease,stroke .45s ease!important}
#themeToggle.is-spinning .icon{animation:theme-spin .6s cubic-bezier(.4,0,.2,1)}
@keyframes theme-spin{from{transform:rotate(-180deg) scale(.3);opacity:0}to{transform:none;opacity:1}}

/* --- картинки: размытый placeholder и плавное появление --- */
img[data-placeholder]{background-color:var(--sunk)}
img[data-fallback],img[data-placeholder]{transition:filter .6s ease}
img.is-loading{filter:blur(10px) saturate(.75)}

/* --- hero: параллакс (свойство translate не конфликтует с transform) --- */
.hero__poster[data-fallback]{transition:transform .25s ease,translate .3s ease,filter .6s ease}
.hero__poster:nth-child(1){translate:calc(var(--mx,0)*-12px) calc(var(--my,0)*-9px)}
.hero__poster:nth-child(2){translate:calc(var(--mx,0)*14px) calc(var(--my,0)*-6px)}
.hero__poster:nth-child(3){translate:calc(var(--mx,0)*-7px) calc(var(--my,0)*10px)}

/* --- карточки: подсветка за курсором --- */
@media (hover:hover){
  .event-card::after{content:"";position:absolute;inset:0;pointer-events:none;opacity:0;transition:opacity .25s;background:radial-gradient(260px circle at var(--mx,50%) var(--my,50%),rgba(255,255,255,.3),transparent 65%)}
  .event-card:hover::after{opacity:1}
}
.event-card.is-picked{animation:picked 2.6s ease}
@keyframes picked{0%,100%{outline:0 solid transparent}15%,70%{outline:4px solid var(--red);outline-offset:4px}}
.tag--last{animation:last-pulse 2.2s ease-in-out infinite}
@keyframes last-pulse{0%,100%{transform:scale(1)}50%{transform:scale(1.07)}}

/* --- появление блоков по очереди --- */
.anim-in{animation:anim-in .55s cubic-bezier(.2,.8,.2,1) both;animation-delay:calc(var(--i,0)*70ms)}
@keyframes anim-in{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:none}}

/* --- конфетти --- */
.confetti{position:fixed;inset:0;width:100vw;height:100vh;z-index:3000;pointer-events:none}

/* --- страница события: инструменты --- */
.pt-tools{display:flex;flex-wrap:wrap;gap:.5rem;margin-top:.75rem}

/* --- быстрый поиск --- */
.cmdk{padding:0;border:2px solid var(--line);border-radius:var(--radius);width:min(40rem,calc(100vw - 2rem));margin:10vh auto auto;background:var(--card);color:var(--text);box-shadow:8px 8px 0 var(--line)}
.cmdk::backdrop{background:rgba(10,10,14,.55);backdrop-filter:blur(3px)}
.cmdk[open]{animation:cmdk-in .18s ease-out}
@keyframes cmdk-in{from{opacity:0;transform:translateY(-10px) scale(.98)}to{opacity:1;transform:none}}
.cmdk__bar{display:flex;align-items:center;gap:.7rem;padding:.9rem 1rem;border-bottom:2px solid var(--line)}
.cmdk__input{flex:1;min-width:0;border:0;outline:0;background:transparent;color:var(--text);font-size:1.05rem}
.cmdk kbd{padding:.1rem .4rem;border:1.5px solid var(--line);border-radius:.3rem;font-size:.75rem;background:var(--sunk);color:var(--text)}
.cmdk__list{list-style:none;margin:0;padding:.4rem;max-height:min(22rem,55vh);overflow:auto}
.cmdk__list a{display:grid;grid-template-columns:6.2rem 1fr;gap:0 .8rem;padding:.55rem .7rem;border-radius:.4rem;color:var(--text);text-decoration:none}
.cmdk__list a .cmdk__s{grid-column:2;font-size:.85rem;color:var(--muted)}
.cmdk__kind{grid-row:span 2;align-self:center;font-size:.7rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:var(--muted)}
.cmdk__t{font-weight:600}
.cmdk__list li[aria-selected="true"] a{background:var(--yellow);color:#000}
.cmdk__list li[aria-selected="true"] .cmdk__s,.cmdk__list li[aria-selected="true"] .cmdk__kind{color:#000}
.cmdk__empty{padding:1.2rem;text-align:center;color:var(--muted)}
.cmdk__hint{margin:0;padding:.6rem 1rem;border-top:2px solid var(--line);font-size:.8rem;color:var(--muted)}

/* --- Live --- */
.live-dot{display:inline-block;width:.7rem;height:.7rem;border-radius:50%;background:var(--red);box-shadow:0 0 0 0 rgba(255,75,38,.7);animation:live-pulse 1.6s infinite;vertical-align:middle}
.live-dot--sm{width:.5rem;height:.5rem}
.live-dot--idle{background:var(--lime);animation-name:live-pulse-g}
@keyframes live-pulse{0%{box-shadow:0 0 0 0 rgba(255,75,38,.7)}70%{box-shadow:0 0 0 .7rem rgba(255,75,38,0)}100%{box-shadow:0 0 0 0 rgba(255,75,38,0)}}
@keyframes live-pulse-g{0%{box-shadow:0 0 0 0 rgba(189,235,58,.7)}70%{box-shadow:0 0 0 .7rem rgba(189,235,58,0)}100%{box-shadow:0 0 0 0 rgba(189,235,58,0)}}
.live-hero{padding:3rem 0 3.5rem;background:#0d0e13;color:#fff;border-bottom:2px solid var(--line)}
.live-hero .breadcrumb{--bs-breadcrumb-divider-color:#9aa0b5;--bs-breadcrumb-item-active-color:#fff}
.live-hero .breadcrumb a{color:#ffc933}
.live-hero h1{color:#fff}
.live-hero__badge{display:inline-flex;align-items:center;gap:.55rem;padding:.3rem .8rem;border:2px solid #fff;font-size:.8rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase}
.live-next{display:grid;grid-template-columns:5fr 7fr;margin-top:2rem;border:2px solid #fff;background:#171923;box-shadow:8px 8px 0 var(--yellow)}
.live-next__poster img{display:block;width:100%;height:100%;object-fit:cover;min-height:14rem}
.live-next__body{padding:1.6rem;display:flex;flex-direction:column;gap:1rem}
.live-next__kicker{margin:0;font-weight:700;letter-spacing:.04em;text-transform:uppercase;font-size:.85rem;color:#ffc933}
.live-next__title{margin:0;font-size:clamp(1.3rem,3vw,1.9rem)}
.live-next__title a{color:#fff;text-decoration:none}
.live-next__title a:hover{color:#ffc933}
.live-next__meta{margin:0;color:#c9ccda}
.live-next__seats{color:#ffb4a3}
.live-next__prog{height:.7rem;border:2px solid #fff;border-radius:0;background:transparent}
.live-next__prog .progress-bar{background:var(--red)}
.countdown{display:flex;flex-wrap:wrap;gap:.6rem}
.countdown__cell{min-width:4.8rem;padding:.55rem .6rem;border:2px solid #fff;text-align:center;background:rgba(255,255,255,.06)}
.countdown__num{display:block;font:800 clamp(1.7rem,5vw,2.8rem)/1 var(--font-display);font-variant-numeric:tabular-nums}
.countdown__num.tick{animation:tick-in .35s ease-out}
@keyframes tick-in{from{transform:translateY(-35%);opacity:0}to{transform:none;opacity:1}}
.countdown__lbl{display:block;margin-top:.2rem;font-size:.7rem;text-transform:uppercase;letter-spacing:.08em;color:#c9ccda}
.live-hero .btn-outline-light{--bs-btn-color:#fff;--bs-btn-border-color:#fff;--bs-btn-hover-bg:#fff;--bs-btn-hover-color:#000;box-shadow:none}
.tag--live{background:var(--red);color:#000;display:inline-flex;align-items:center;gap:.35rem}
.tag--count{background:#000;color:#fff;font-variant-numeric:tabular-nums}
.live-block{margin-top:3rem}
.live-block h2{font-size:clamp(1.3rem,3vw,1.8rem);margin-bottom:1.2rem}
.timeline{list-style:none;margin:0;padding:0;display:grid;gap:.9rem}
.tl-item{display:grid;grid-template-columns:4.2rem 1fr auto auto;gap:1rem;align-items:center;padding:.8rem 1rem;border:2px solid var(--line);background:var(--card);box-shadow:var(--shadow-sm)}
.tl-date{text-align:center;border:2px solid var(--line);background:var(--yellow);color:#000;padding:.3rem 0;line-height:1.1}
.tl-date b{display:block;font:800 1.35rem/1 var(--font-display)}
.tl-date span{font-size:.75rem;text-transform:uppercase;letter-spacing:.06em}
.tl-body{display:flex;flex-direction:column;min-width:0}
.tl-body a{font-weight:700;color:var(--text);text-decoration:none}
.tl-body a:hover{color:var(--red)}
.surprise{display:flex;gap:1rem;align-items:center;margin-top:1.2rem;padding:1rem;border:2px dashed var(--line);background:var(--card)}
.surprise.is-final{border-style:solid;box-shadow:var(--shadow-sm);animation:pop-in .45s cubic-bezier(.2,1.4,.4,1)}
@keyframes pop-in{from{transform:scale(.94);opacity:.4}to{transform:none;opacity:1}}
.surprise__img{width:9rem;max-width:30%;height:auto;border:2px solid var(--line)}
.surprise__kicker{margin:0;font-size:.75rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--muted)}
.surprise__title{margin:.1rem 0;font:700 1.15rem var(--font-display)}
.surprise__meta{margin:0 0 .6rem;color:var(--muted)}
@media (max-width:767.98px){
  .live-next{grid-template-columns:1fr}
  .live-next__poster img{max-height:13rem}
  .tl-item{grid-template-columns:4.2rem 1fr}
  .tl-item .tag,.tl-item .btn{grid-column:2;justify-self:start}
}

/* --- Подборки --- */
.col-tile{display:flex;flex-direction:column;align-items:flex-start;gap:.35rem;width:100%;height:100%;padding:1.1rem;text-align:left;border:2px solid var(--line);border-radius:var(--radius);background:var(--c);color:#000;box-shadow:var(--shadow-sm);transition:transform .15s,box-shadow .15s}
.col-tile:hover{transform:translate(-2px,-2px);box-shadow:var(--shadow)}
.col-tile[aria-pressed="true"]{transform:translate(-3px,-3px);box-shadow:var(--shadow);outline:3px solid var(--text);outline-offset:3px}
.col-tile__icon{display:inline-flex;align-items:center;justify-content:center;width:2.6rem;height:2.6rem;border:2px solid #000;border-radius:50%;background:#fff}
.col-tile__icon .icon{width:1.3rem;height:1.3rem}
.col-tile__title{font:700 1.05rem/1.2 var(--font-display)}
.col-tile__count{font-size:.85rem;font-weight:600}
.col-head{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:end;gap:1rem;margin:2.5rem 0 1.5rem}
.col-head h2{margin:0}

/* --- уважение к настройкам пользователя --- */
@media (prefers-reduced-motion:reduce){
  .anim-in,.tag--last,.live-dot,.countdown__num.tick,.surprise.is-final,.cmdk[open],#themeToggle.is-spinning .icon,.event-card.is-picked{animation:none!important}
  .hero__poster{translate:none!important}
  img.is-loading{filter:none}
}

/* --- кнопка темы: показываем только нужную иконку --- */
.theme-icon-dark{display:none}
[data-bs-theme="dark"] .theme-icon-light{display:none}
[data-bs-theme="dark"] .theme-icon-dark{display:inline-block}'''
SW_JS = r'''/* ArtSpace — service worker (добавлен патчем).
   Страницы и скрипты: сначала сеть, при отсутствии сети — кэш (правки сразу видны).
   Картинки и шрифты: сначала кэш, затем сеть — повторные заходы грузятся мгновенно. */
const V = 'artspace-v1';
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== V).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', e => {
  const r = e.request;
  if (r.method !== 'GET') return;
  const u = new URL(r.url);
  const isMedia = r.destination === 'image' || /\.(svg|jpe?g|png|webp|avif)$/i.test(u.pathname) || u.hostname === 'images.unsplash.com';
  const isFont = u.hostname === 'fonts.gstatic.com' || r.destination === 'font';
  if (isMedia || isFont) {
    e.respondWith(caches.open(V).then(c => c.match(r).then(hit => hit || fetch(r).then(res => {
      if (res && (res.ok || res.type === 'opaque')) c.put(r, res.clone());
      return res;
    }).catch(() => hit || Response.error()))));
    return;
  }
  if (u.origin === location.origin) {
    e.respondWith(fetch(r).then(res => {
      if (res.ok) { const copy = res.clone(); caches.open(V).then(c => c.put(r, copy)); }
      return res;
    }).catch(() => caches.match(r).then(h => h || caches.match('404.html') || Response.error())));
  }
});'''
SERVE_PY = r'''#!/usr/bin/env python3
"""Локальный сервер для ArtSpace: python3 serve.py [порт]
Тема, избранное и уведомление запоминаются надёжнее, чем при открытии файлов через file://."""
import http.server, os, sys, threading, webbrowser

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
os.chdir(os.path.dirname(os.path.abspath(__file__)))

class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-cache')
        super().end_headers()

srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), Handler)
url = f'http://127.0.0.1:{PORT}/index.html'
print('ArtSpace:', url, '(Ctrl+C — остановить)')
threading.Timer(0.6, lambda: webbrowser.open(url)).start()
try:
    srv.serve_forever()
except KeyboardInterrupt:
    print('\nОстановлено')'''
LIVE_MAIN = r'''<main id="main">
    <section class="live-hero" aria-labelledby="live-title">
      <div class="container">
        <nav aria-label="breadcrumb"><ol class="breadcrumb"><li class="breadcrumb-item"><a href="index.html">Главная</a></li><li class="breadcrumb-item active" aria-current="page">Live</li></ol></nav>
        <p class="live-hero__badge"><span class="live-dot" aria-hidden="true"></span> Live · обновляется каждую секунду</p>
        <h1 class="mt-3" id="live-title">Что происходит сейчас</h1>
        <p class="lead mb-0" style="max-width:40rem;color:#c9ccda">Ближайшие события с обратным отсчётом: что уже идёт, что начнётся в ближайшие часы и что запланировано дальше.</p>
        <div class="live-next" id="live-next" hidden></div>
      </div>
    </section>

    <div class="container my-4 my-lg-5">
      <form class="d-flex flex-wrap align-items-center gap-3" id="lv-filters" aria-label="Фильтры Live" onsubmit="return false">
        <div>
          <label for="lv-city" class="visually-hidden">Город</label>
          <select id="lv-city" class="form-select"><option value="">Все города</option></select>
        </div>
        <div class="form-check form-switch mb-0">
          <input class="form-check-input" type="checkbox" role="switch" id="lv-online">
          <label class="form-check-label" for="lv-online">Только онлайн</label>
        </div>
        <div class="form-check form-switch mb-0">
          <input class="form-check-input" type="checkbox" role="switch" id="lv-seats">
          <label class="form-check-label" for="lv-seats">Только с местами</label>
        </div>
        <button type="button" class="btn btn-primary ms-lg-auto" id="lv-surprise"><svg class="icon" aria-hidden="true"><use href="#i-shuffle"></use></svg> Удиви меня</button>
      </form>
      <div class="surprise" id="lv-surprise-box" hidden></div>
      <p class="fw-bold mt-4 mb-0" id="live-count" aria-live="polite"></p>

      <section class="live-block" aria-labelledby="live-now-title">
        <h2 id="live-now-title"><span class="live-dot live-dot--sm" aria-hidden="true"></span> Идёт сейчас</h2>
        <div class="row g-4" id="live-now"></div>
        <p class="text-muted-2" id="live-now-empty" hidden>Прямо сейчас ничего не идёт — загляните в раздел «Скоро».</p>
      </section>

      <section class="live-block" aria-labelledby="live-soon-title">
        <h2 id="live-soon-title">Скоро: ближайшие 48 часов</h2>
        <div class="row g-4" id="live-soon"></div>
        <p class="text-muted-2" id="live-soon-empty" hidden>В ближайшие двое суток событий нет — смотрите расписание ниже.</p>
      </section>

      <section class="live-block" aria-labelledby="live-later-title">
        <h2 id="live-later-title">Дальше по расписанию</h2>
        <ol class="timeline" id="live-timeline"></ol>
        <p class="text-muted-2" id="live-later-empty" hidden>Дальше по расписанию пока пусто.</p>
      </section>

      <div class="empty mt-5" id="live-empty" hidden>
        <span class="empty__icon" aria-hidden="true"><svg class="icon"><use href="#i-search"></use></svg></span>
        <h2 class="h5">Под ваши фильтры ничего не нашлось</h2>
        <p class="text-muted-2">Снимите часть фильтров или откройте весь каталог.</p>
        <a class="btn btn-primary" href="catalog.html">Открыть афишу</a>
      </div>
    </div>
  </main>'''
COLLECTIONS_MAIN = r'''<main id="main">
    <div class="page-head">
      <div class="container">
        <nav aria-label="breadcrumb"><ol class="breadcrumb"><li class="breadcrumb-item"><a href="index.html">Главная</a></li><li class="breadcrumb-item active" aria-current="page">Подборки</li></ol></nav>
        <h1>Подборки</h1>
        <p class="lead mb-0 text-muted-2" style="max-width:42rem">Готовые идеи на любой случай: на выходные, с детьми, бесплатно или на свидание. Выберите подборку — афиша подстроится.</p>
      </div>
    </div>

    <div class="container my-4 my-lg-5">
      <div class="row g-3" id="col-tiles" role="group" aria-label="Выбор подборки"></div>

      <section id="col-result" class="anchor-target" aria-live="polite">
        <div class="col-head">
          <div>
            <h2 id="col-title"></h2>
            <p class="text-muted-2 mb-0" id="col-text" style="max-width:40rem"></p>
          </div>
          <div class="d-flex flex-wrap align-items-center gap-3">
            <span class="fw-bold" id="col-count"></span>
            <button type="button" class="btn btn-outline-primary btn-sm" id="col-random" hidden><svg class="icon icon--sm" aria-hidden="true"><use href="#i-shuffle"></use></svg> Выбрать случайное</button>
          </div>
        </div>
        <div class="row g-4" id="col-grid"></div>
        <div class="empty" id="col-empty" hidden>
          <span class="empty__icon" aria-hidden="true"><svg class="icon"><use href="#i-search"></use></svg></span>
          <h2 class="h5">В этой подборке пока пусто</h2>
          <p class="text-muted-2">Афиша обновляется — загляните позже или выберите другую подборку.</p>
          <a class="btn btn-primary" href="catalog.html">Открыть афишу</a>
        </div>
      </section>
    </div>
  </main>'''

CSS_MARK = '/* ================= ArtSpace patch: extras ================= */'

HEAD_THEME_JS = r'''<script>
    (function () {
      var P = '__artspace__:', F = location.protocol === 'file:', t = null;
      function bag() { try { var n = window.name || ''; if (n.indexOf(P) === 0) return JSON.parse(n.slice(P.length)) || {}; } catch (e) {} return {}; }
      function ls() { try { return JSON.parse(localStorage.getItem('artspace:theme')); } catch (e) { return null; } }
      t = F ? (bag().theme || ls()) : (ls() || bag().theme);
      if (t !== 'dark' && t !== 'light') t = matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
      document.documentElement.setAttribute('data-bs-theme', t);
    })();
  </script>'''

# ----------------------------------------------------------------------------
# JS-вставки для app.js
# ----------------------------------------------------------------------------
JS_STORE = r'''/*AS-PATCH:store*/
const BAG_P='__artspace__:',BAG_KEYS=['theme','notice','favs','subscribed'],IS_FILE=location.protocol==='file:';
function bagRead(){try{const n=window.name||'';if(n.indexOf(BAG_P)===0)return JSON.parse(n.slice(BAG_P.length))||{}}catch(_){}return{}}
function bagWrite(o){try{window.name=BAG_P+JSON.stringify(o)}catch(_){}}
function lsGet(k){try{const raw=localStorage.getItem('artspace:'+k);return raw===null?undefined:JSON.parse(raw)}catch(_){return undefined}}
const Store={
get(k,f){const useBag=BAG_KEYS.indexOf(k)>-1;if(IS_FILE&&useBag){const b=bagRead();if(k in b)return b[k]}const v=lsGet(k);if(v!==undefined)return v;if(k in mem)return mem[k];if(useBag){const b=bagRead();if(k in b)return b[k]}return f},
set(k,v){mem[k]=v;let ok=false;try{localStorage.setItem('artspace:'+k,JSON.stringify(v));ok=true}catch(_){}if(BAG_KEYS.indexOf(k)>-1&&(IS_FILE||!ok)){const b=bagRead();b[k]=v;bagWrite(b);ok=true}return ok}
};'''

JS_THEME_SET = r'''/*AS-PATCH:theme*/
function applyTheme(t){const h=document.documentElement;h.setAttribute('data-bs-theme',t);Store.set('theme',t);const b=$('#themeToggle');if(b){b.setAttribute('aria-pressed',t==='dark'?'true':'false');b.setAttribute('aria-label',t==='dark'?'Включить светлую тему':'Включить тёмную тему')}const m=$('meta[name="theme-color"]');if(m)m.setAttribute('content',t==='dark'?'#14151b':'#ffc933')}
function setTheme(t,o){const h=document.documentElement;if(h.getAttribute('data-bs-theme')===t){applyTheme(t);return}if(matchMedia('(prefers-reduced-motion: reduce)').matches){applyTheme(t);return}if(document.startViewTransition&&o){const r=Math.hypot(Math.max(o.x,innerWidth-o.x),Math.max(o.y,innerHeight-o.y));const vt=document.startViewTransition(()=>applyTheme(t));vt.ready.then(()=>{h.animate({clipPath:['circle(0px at '+o.x+'px '+o.y+'px)','circle('+r+'px at '+o.x+'px '+o.y+'px)']},{duration:650,easing:'cubic-bezier(.65,0,.35,1)',pseudoElement:'::view-transition-new(root)'})}).catch(()=>{})}else{h.classList.add('theme-anim');applyTheme(t);setTimeout(()=>h.classList.remove('theme-anim'),650)}}'''

JS_THEME_INIT = r'''function initTheme(){const b=$('#themeToggle');if(!b)return;const cur=document.documentElement.getAttribute('data-bs-theme')||'light';b.setAttribute('aria-pressed',cur==='dark'?'true':'false');b.setAttribute('aria-label',cur==='dark'?'Включить светлую тему':'Включить тёмную тему');b.addEventListener('click',ev=>{const r=b.getBoundingClientRect();const x=ev.clientX||r.left+r.width/2,y=ev.clientY||r.top+r.height/2;b.classList.remove('is-spinning');void b.offsetWidth;b.classList.add('is-spinning');setTheme(document.documentElement.getAttribute('data-bs-theme')==='dark'?'light':'dark',{x:x,y:y})});window.addEventListener('storage',e=>{if(e.key==='artspace:theme'&&e.newValue){try{const t=JSON.parse(e.newValue);if(t==='dark'||t==='light'){document.documentElement.setAttribute('data-bs-theme',t);b.setAttribute('aria-pressed',t==='dark'?'true':'false')}}catch(_){}}})}'''

JS_IMG_HELPERS = r'''/*AS-PATCH:img*/
const TR_MAP={'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'yo','ж':'zh','з':'z','и':'i','й':'y','к':'k','л':'l','м':'m','н':'n','о':'o','п':'p','р':'r','с':'s','т':'t','у':'u','ф':'f','х':'kh','ц':'ts','ч':'ch','ш':'sh','щ':'shch','ъ':'','ы':'y','ь':'','э':'e','ю':'yu','я':'ya'};
const translit=s=>String(s).toLowerCase().split('').map(c=>c in TR_MAP?TR_MAP[c]:c).join('');
const ORG_SVG_SET=new Set(@@ORG_SET@@);
const orgSvg=slug=>{const a=translit(slug);return 'images/orgs/'+(ORG_SVG_SET.has(a)?a:(ORG_SVG_SET.has('tsentr-loft-art')?'tsentr-loft-art':a))+'.svg'};
const photoLocal=url=>{const m=/\/(photo-[A-Za-z0-9_-]+)/.exec(url);return m?'images/photos/'+m[1]+'.jpg':url};'''

JS_EXPOSE = r'''/*AS-PATCH:expose*/
window.AS={cardHtml,seatsLeft,seatsInfo,Store,esc,icon,dayLabel,formatDate,formatWeekday,formatPrice,plural,startOf,toast,favBtn,labelsHtml,eventById,initReveal,allReviews,reviewsOf,average,starsHtml};
'''

TR = {'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo', 'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y',
      'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u', 'ф': 'f',
      'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch', 'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'}


def translit(s):
    return ''.join(TR.get(c, c) for c in s.lower())


# ----------------------------------------------------------------------------
# Утилиты
# ----------------------------------------------------------------------------
def find_root():
    for cand in (pathlib.Path.cwd(), pathlib.Path(__file__).resolve().parent):
        if (cand / 'index.html').exists() and (cand / 'js' / 'app.js').exists():
            return cand
    sys.exit('Не найдена папка проекта: запустите скрипт там, где лежат index.html и js/app.js')


ROOT = None
BACKUP = None
REPORT = []


def read(p):
    return pathlib.Path(p).read_text(encoding='utf-8')


def write(p, text):
    with open(p, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)


def backup(p):
    p = pathlib.Path(p)
    dst = BACKUP / p.relative_to(ROOT)
    if p.exists() and not dst.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dst)


def say(msg):
    print(msg)
    REPORT.append(msg)


# ----------------------------------------------------------------------------
# 1. Картинки организаторов: чиним имена и делаем ASCII-копии
# ----------------------------------------------------------------------------
def step_org_images():
    d = ROOT / 'images' / 'orgs'
    if not d.exists():
        say('· images/orgs не найдена — пропускаю иллюстрации организаторов')
        return []
    fixed = copied = 0
    for f in list(d.iterdir()):  # имена вида #U0430... (архиватор испортил кириллицу)
        if '#U' in f.name:
            real = re.sub(r'#U([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), f.name)
            try:
                if not (d / real).exists():
                    f.rename(d / real)
                    fixed += 1
            except OSError:
                pass
    stems = set()
    for f in list(d.glob('*.svg')):
        a = translit(f.stem)
        stems.add(a)
        dst = d / (a + '.svg')
        if a != f.stem and not dst.exists():
            shutil.copy2(f, dst)
            copied += 1
    say(f'✔ images/orgs: исправлено имён {fixed}, ASCII-копий создано {copied}, всего иллюстраций {len(stems)}')
    return sorted(stems)


# ----------------------------------------------------------------------------
# 2. app.js
# ----------------------------------------------------------------------------
def step_app_js(org_stems):
    p = ROOT / 'js' / 'app.js'
    s = read(p)
    backup(p)
    done = []

    def sub_line(pattern, repl, label, marker):
        nonlocal s
        if marker in s:
            return
        new, n = re.subn(pattern, lambda m: repl, s, count=1, flags=re.M)
        if n:
            s = new
            done.append(label)
        else:
            say(f'⚠ app.js: не нашёл место для «{label}» — пропущено')

    sub_line(r'^const Store=.*$', JS_STORE, 'хранилище', '/*AS-PATCH:store*/')
    if '/*AS-PATCH:theme*/' not in s:
        new, n1 = re.subn(r'^function setTheme\(t\)\{.*$', lambda m: JS_THEME_SET, s, count=1, flags=re.M)
        new, n2 = re.subn(r'^function initTheme\(\)\{.*$', lambda m: JS_THEME_INIT, new, count=1, flags=re.M)
        if n1 and n2:
            s = new
            done.append('тема')
        else:
            say('⚠ app.js: не нашёл setTheme/initTheme — тема не пропатчена')

    if '/*AS-PATCH:img*/' not in s:
        stems = org_stems or ['tsentr-loft-art']
        helpers = JS_IMG_HELPERS.replace('@@ORG_SET@@', '[' + ','.join("'%s'" % x for x in stems) + ']')
        m = re.search(r'^function orgPhoto\(slug\)\{.*$', s, flags=re.M)
        if m:
            s = s[:m.end()] + '\n' + helpers + s[m.end():]
            old = 'src="\'+photo+\'"'
            new_attr = ('src="\'+photoLocal(photo)+\'" data-fallback="\'+photo+\'|\'+orgSvg(slug)+\'" '
                        'data-placeholder="\'+orgSvg(slug)+\'"')
            if old in s:
                s = s.replace(old, new_attr, 1)
                done.append('фото организаторов')
            else:
                say('⚠ app.js: не нашёл <img> организатора — фото не пропатчены')
        else:
            say('⚠ app.js: не нашёл orgPhoto — фото организаторов не пропатчены')

    if '/*AS-PATCH:expose*/' not in s:
        i = s.rfind('\n})();')
        if i != -1:
            s = s[:i] + '\n' + JS_EXPOSE + s[i:]
            done.append('window.AS')
        else:
            say('⚠ app.js: не нашёл конец IIFE — window.AS не добавлен (Live/Подборки не заработают)')

    write(p, s)
    say('✔ app.js: ' + (', '.join(done) if done else 'уже пропатчен'))


# ----------------------------------------------------------------------------
# 3. CSS, extras.js, sw.js, serve.py
# ----------------------------------------------------------------------------
def step_assets():
    p = ROOT / 'css' / 'custom.css'
    css = read(p)
    backup(p)
    if CSS_MARK in css:
        css = css[:css.index(CSS_MARK)].rstrip() + '\n\n'
    else:
        css = css.rstrip() + '\n\n'
    write(p, css + EXTRAS_CSS.strip() + '\n')
    write(ROOT / 'js' / 'extras.js', EXTRAS_JS)
    write(ROOT / 'sw.js', SW_JS)
    write(ROOT / 'serve.py', SERVE_PY)
    say('✔ css/custom.css, js/extras.js, sw.js, serve.py записаны')


# ----------------------------------------------------------------------------
# 4. Новые страницы
# ----------------------------------------------------------------------------
def make_page(template_html, title, desc, data_page, main_html):
    h = template_html
    h = re.sub(r'<title>.*?</title>', lambda m: f'<title>{title}</title>', h, count=1, flags=re.S)
    h = re.sub(r'(<meta name="description" content=")[^"]*(">)', lambda m: m.group(1) + desc + m.group(2), h, count=1)
    h = re.sub(r'(<meta property="og:title" content=")[^"]*(">)', lambda m: m.group(1) + title + m.group(2), h, count=1)
    h = re.sub(r'(<meta property="og:description" content=")[^"]*(">)', lambda m: m.group(1) + desc + m.group(2), h, count=1)
    h = re.sub(r'<body data-page="[^"]*">', lambda m: f'<body data-page="{data_page}">', h, count=1)
    h, n = re.subn(r'<main id="main">.*?</main>', lambda m: main_html.strip(), h, count=1, flags=re.S)
    if not n:
        raise RuntimeError('в шаблоне нет <main id="main">')
    return h


def step_pages(force):
    tpl_path = ROOT / 'favorites.html'
    if not tpl_path.exists():
        tpl_path = ROOT / 'about.html'
    tpl = read(tpl_path)
    specs = [
        ('live.html', 'Live — ближайшие события — ArtSpace',
         'Что идёт сейчас и что начнётся совсем скоро: обратный отсчёт до ближайших событий.', 'live', LIVE_MAIN),
        ('collections.html', 'Подборки — ArtSpace',
         'Подборки событий: на выходные, бесплатно, с детьми, онлайн, на свидание.', 'collections', COLLECTIONS_MAIN),
    ]
    for name, title, desc, dp, main in specs:
        p = ROOT / name
        if p.exists() and not force:
            say(f'· {name} уже есть (оставляю как есть; --force-pages — пересоздать)')
            continue
        write(p, make_page(tpl, title, desc, dp, main))
        say(f'✔ создана {name}')


# ----------------------------------------------------------------------------
# 5. Правка всех HTML: тема в <head>, меню, подвал, скрипты, фото
# ----------------------------------------------------------------------------
NAV_ITEMS = [('index.html', 'Главная'), ('catalog.html', 'Каталог'), ('live.html', 'Live'),
             ('collections.html', 'Подборки'), ('organizers.html', 'Организаторы'), ('about.html', 'О проекте')]
FOOT_ITEMS = [('index.html', 'Главная'), ('catalog.html', 'Каталог'), ('live.html', 'Live'),
              ('collections.html', 'Подборки'), ('organizers.html', 'Организаторы'), ('reviews.html', 'Отзывы')]
ACTIVE_MAP = {'product.html': 'catalog.html'}
HERO_POSTERS = ['jazz-night', 'chamber-gallery', 'hamlet-studio']


def nav_items_html(active):
    out = []
    for href, label in NAV_ITEMS:
        cls = 'nav-link' + (' active' if href == active else '')
        cur = ' aria-current="page"' if href == active else ''
        inner = ('<span class="nav-live">Live<span class="live-dot live-dot--sm" aria-hidden="true"></span></span>'
                 if href == 'live.html' else label)
        out.append(f'<li class="nav-item"><a class="{cls}"{cur} href="{href}">{inner}</a></li>')
    return '\n'.join(out)


def foot_items_html():
    return '\n'.join(f'            <li><a class="footer__link" href="{h}">{l}</a></li>' for h, l in FOOT_ITEMS)


PHOTO_ID = re.compile(r'/(photo-[A-Za-z0-9_-]+)')


def patch_html_imgs(h, poster_exists, photos):
    idx = [0]

    def repl(m):
        pre, url, post = m.group(1), m.group(2), m.group(3)
        pid = PHOTO_ID.search(url)
        if not pid:
            return m.group(0)
        photos[pid.group(1)] = url.replace('&amp;', '&')
        poster = HERO_POSTERS[idx[0] % len(HERO_POSTERS)]
        idx[0] += 1
        ph = f'images/posters/{poster}.svg'
        extra = ' fetchpriority="high"' if 'loading="eager"' in (pre + post) else ''
        remote = url.replace('&amp;', '&').replace('&', '&amp;')
        return (f'<img{pre}src="images/photos/{pid.group(1)}.jpg" data-fallback="{remote}|{ph}" '
                f'data-placeholder="{ph}"{extra}{post}>')

    return re.sub(r'<img([^>]*?)src="(https://images\.unsplash\.com/[^"]+)"([^>]*)>', repl, h)


def step_html(photos):
    stats = {'head': 0, 'nav': 0, 'foot': 0, 'script': 0, 'img': 0}
    for p in sorted(ROOT.glob('*.html')):
        h = read(p)
        orig = h
        # тема в <head>
        h, n = re.subn(r'<script>\s*\(function \(\) \{\s*try \{\s*var t = JSON\.parse\(localStorage\.getItem\(\'artspace:theme\'\)\);.*?</script>',
                       lambda m: HEAD_THEME_JS, h, count=1, flags=re.S)
        stats['head'] += n
        # меню
        active = ACTIVE_MAP.get(p.name, p.name)
        h, n = re.subn(r'(<ul class="navbar-nav[^"]*">)(.*?)(</ul>)',
                       lambda m: m.group(1) + '\n' + nav_items_html(active) + '\n        ' + m.group(3), h, count=1, flags=re.S)
        stats['nav'] += n
        # подвал
        h, n = re.subn(r'(<h2 class="footer__title text-center">Разделы</h2>\s*<ul class="list-unstyled mb-0 text-center">)(.*?)(</ul>)',
                       lambda m: m.group(1) + '\n' + foot_items_html() + '\n          ' + m.group(3), h, count=1, flags=re.S)
        stats['foot'] += n
        # скрипты
        if 'js/extras.js' not in h and 'js/app.js' in h:
            h = re.sub(r'(<script src="js/app\.js"></script>)', lambda m: m.group(1) + '\n  <script src="js/extras.js"></script>', h, count=1)
            stats['script'] += 1
        # фото
        before = h
        h = patch_html_imgs(h, None, photos)
        if h != before:
            stats['img'] += 1
        if h != orig:
            backup(p)
            write(p, h)
    say(f"✔ HTML: тема в <head> — {stats['head']}, меню — {stats['nav']}, подвал — {stats['foot']}, "
        f"extras.js — {stats['script']}, страниц с фото — {stats['img']}")


# ----------------------------------------------------------------------------
# 6. Фото: скачивание
# ----------------------------------------------------------------------------
def collect_photos(photos):
    s = read(ROOT / 'js' / 'app.js')
    for m in re.finditer(r"https://images\.unsplash\.com/[^'\"\s)]+", s):
        pid = PHOTO_ID.search(m.group(0))
        if pid:
            photos.setdefault(pid.group(1), m.group(0))


def download_one(item):
    pid, url = item
    dst = ROOT / 'images' / 'photos' / (pid + '.jpg')
    if dst.exists() and dst.stat().st_size > 5000:
        return pid, 'уже есть'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (ArtSpace patch)'})
    last = ''
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                data = r.read()
            if len(data) < 3000 or data[:2] != b'\xff\xd8':
                raise ValueError('получен не JPEG')
            tmp = dst.with_suffix('.tmp')
            tmp.write_bytes(data)
            tmp.replace(dst)
            return pid, f'ok, {len(data) // 1024} КБ'
        except Exception as e:  # noqa: BLE001
            last = f'{type(e).__name__}: {e}'
            time.sleep(1 + attempt)
    return pid, 'ОШИБКА — ' + last


def step_download(photos, enabled):
    if not photos:
        say('· фото Unsplash в проекте не найдены')
        return
    (ROOT / 'images' / 'photos').mkdir(parents=True, exist_ok=True)
    if not enabled:
        say(f'· скачивание пропущено (--no-download). Нужно файлов: {len(photos)} → images/photos/')
        return
    print(f'Скачиваю фото: {len(photos)} шт. …')
    ok = bad = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        for pid, res in ex.map(download_one, sorted(photos.items())):
            print(f'  {pid}: {res}')
            if res.startswith('ОШИБКА'):
                bad += 1
            else:
                ok += 1
    if bad:
        say(f'⚠ фото: скачано {ok}, не удалось {bad}. Сайт всё равно работает: возьмёт онлайн-версию или иллюстрацию. '
            f'Повторите запуск при рабочем интернете/VPN — скачаются только недостающие.')
    else:
        say(f'✔ фото: все {ok} файлов лежат в images/photos/')


# ----------------------------------------------------------------------------
# 7. sitemap + README
# ----------------------------------------------------------------------------
def step_misc():
    sm = ROOT / 'sitemap.xml'
    if sm.exists():
        t = read(sm)
        add = ''
        for name, prio in (('live.html', '0.6'), ('collections.html', '0.6')):
            if name not in t:
                add += f'  <url><loc>/{name}</loc><priority>{prio}</priority></url>\n'
        if add:
            backup(sm)
            write(sm, t.replace('</urlset>', add + '</urlset>'))
            say('✔ sitemap.xml: добавлены live.html и collections.html')
    rd = ROOT / 'README.md'
    mark = '## Патч v2'
    if rd.exists() and mark not in read(rd):
        backup(rd)
        write(rd, read(rd).rstrip() + '''

## Патч v2
Применён `patch_artspace.py` (повторный запуск безопасен; после пересборки сайта запустите его снова).

- **Тема и уведомление** запоминаются на всех страницах; смена темы — круговая волна из кнопки (View Transitions, с запасным вариантом).
- **Фото**: `images/photos/` (локально) → онлайн Unsplash → иллюстрация; пока грузится — размытый placeholder.
- **Новое меню**: Главная, Каталог, Live, Подборки, Организаторы, О проекте.
- **Live** (`live.html`): обратный отсчёт до ближайшего события, «идёт сейчас», «скоро», расписание, «Удиви меня».
- **Подборки** (`collections.html`): 8 готовых подборок, ссылка вида `collections.html#free`.
- **Быстрый поиск**: Ctrl+K или `/`. **Страница события**: «В календарь (.ics)», «Поделиться».
- **Анимации**: полоса прокрутки, подсветка карточек, параллакс в hero, конфетти после записи.
- **Запуск**: `python3 serve.py` (открывать через http, а не двойным кликом по файлу — тогда всё хранится надёжнее).
''')
        say('✔ README.md дополнен')


# ----------------------------------------------------------------------------
def main():
    global ROOT, BACKUP
    ap = argparse.ArgumentParser(description='Патч ArtSpace remake')
    ap.add_argument('--no-download', action='store_true', help='не скачивать фото')
    ap.add_argument('--force-pages', action='store_true', help='пересоздать live.html и collections.html')
    args = ap.parse_args()

    ROOT = find_root()
    BACKUP = ROOT / '.patch_backup'
    print(f'Проект: {ROOT}\n')

    stems = step_org_images()
    photos = {}
    step_app_js(stems)
    step_assets()
    step_pages(args.force_pages)
    step_html(photos)
    collect_photos(photos)
    step_download(photos, not args.no_download)
    step_misc()

    print('\n=== Готово ===')
    print('Запустите:  python3 serve.py   (и обновите страницу через Ctrl+F5)')


if __name__ == '__main__':
    main()
