(function () {
  'use strict';

  let cues = [];
  let currentCue = null;
  let mainEl = null;

  function buildCues() {
    const els = document.querySelectorAll('.gm-cue[data-t-start]');
    cues = Array.from(els).map(el => ({
      start: parseFloat(el.dataset.tStart),
      end:   parseFloat(el.dataset.tEnd),
      el:    el,
    })).sort((a, b) => a.start - b.start);
  }

  function findCue(time) {
    let lo = 0, hi = cues.length - 1;
    while (lo <= hi) {
      const mid = (lo + hi) >> 1;
      if      (cues[mid].end   <= time) lo = mid + 1;
      else if (cues[mid].start >  time) hi = mid - 1;
      else return cues[mid];
    }
    return lo < cues.length ? cues[lo] : null;
  }

  function setHighlight(cue) {
    if (cue === currentCue) return;
    if (currentCue) currentCue.el.classList.remove('gm-reading');
    currentCue = cue;
    if (!cue) {
      if (mainEl) mainEl.classList.remove('gm-reading-active');
      return;
    }
    cue.el.classList.add('gm-reading');
    if (mainEl) mainEl.classList.add('gm-reading-active');

    const rect = cue.el.getBoundingClientRect();
    const navH = 70;
    if (rect.top < navH || rect.bottom > window.innerHeight - 60) {
      cue.el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }

  function clearHighlight() {
    if (currentCue) currentCue.el.classList.remove('gm-reading');
    currentCue = null;
    if (mainEl) mainEl.classList.remove('gm-reading-active');
  }

  document.addEventListener('DOMContentLoaded', function () {
    mainEl = document.querySelector('main');
    buildCues();
    if (!cues.length) return;

    const audio = document.getElementById('gm-audio');
    if (!audio) return;

    audio.addEventListener('timeupdate', function () {
      setHighlight(findCue(audio.currentTime));
    });

    audio.addEventListener('pause',  clearHighlight);
    audio.addEventListener('ended',  clearHighlight);
    audio.addEventListener('seeked', function () {
      setHighlight(findCue(audio.currentTime));
    });

    cues.forEach(function (cue) {
      cue.el.style.cursor = 'pointer';
      cue.el.addEventListener('click', function (e) {
        e.stopPropagation();
        setHighlight(cue);
        audio.addEventListener('seeked', function () {
          audio.play().catch(function () {});
        }, { once: true });
        audio.currentTime = cue.start;
      });
    });
  });
})();
