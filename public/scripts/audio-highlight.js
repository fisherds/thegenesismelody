(function () {
  'use strict';

  let cues = [];
  let currentCue = null;

  // Build sorted cue list from elements annotated by the pre-processing script
  function buildCues() {
    const els = document.querySelectorAll('.gm-cue[data-t-start]');
    cues = Array.from(els).map(el => ({
      start: parseFloat(el.dataset.tStart),
      end:   parseFloat(el.dataset.tEnd),
      el:    el,
    })).sort((a, b) => a.start - b.start);
  }

  // Binary search: find the cue whose [start, end] window contains `time`
  function findCue(time) {
    let lo = 0, hi = cues.length - 1;
    while (lo <= hi) {
      const mid = (lo + hi) >> 1;
      if      (cues[mid].end   <= time) lo = mid + 1;
      else if (cues[mid].start >  time) hi = mid - 1;
      else return cues[mid];
    }
    // Between cues — return the nearest upcoming one
    return lo < cues.length ? cues[lo] : null;
  }

  function setHighlight(cue) {
    if (cue === currentCue) return;
    if (currentCue) currentCue.el.classList.remove('gm-reading');
    currentCue = cue;
    if (!cue) return;
    cue.el.classList.add('gm-reading');

    // Scroll into view if outside the visible area (accounting for fixed navbar)
    const rect = cue.el.getBoundingClientRect();
    const navH = 70;
    if (rect.top < navH || rect.bottom > window.innerHeight - 60) {
      cue.el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }

  function clearHighlight() {
    if (currentCue) currentCue.el.classList.remove('gm-reading');
    currentCue = null;
  }

  document.addEventListener('DOMContentLoaded', function () {
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
  });
})();
