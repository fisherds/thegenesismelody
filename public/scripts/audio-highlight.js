(function () {
  'use strict';

  let cues = [];
  let currentGroup = [];
  let mainEl = null;

  function buildCues() {
    const els = document.querySelectorAll('.gm-cue[data-t-start]');
    cues = Array.from(els).map(el => ({
      start: parseFloat(el.dataset.tStart),
      end:   parseFloat(el.dataset.tEnd),
      el:    el,
    })).sort((a, b) => a.start - b.start);
  }

  // Binary search: find one cue whose [start, end] window contains `time`
  function findOneCue(time) {
    let lo = 0, hi = cues.length - 1;
    while (lo <= hi) {
      const mid = (lo + hi) >> 1;
      if      (cues[mid].end   <= time) lo = mid + 1;
      else if (cues[mid].start >  time) hi = mid - 1;
      else return cues[mid];
    }
    return lo < cues.length ? cues[lo] : null;
  }

  // Return all cues that share the exact same [start, end] as the primary match.
  // Scripture verses have 5-8 spans all at the same timestamp — this highlights them all.
  function findGroup(time) {
    const primary = findOneCue(time);
    if (!primary) return [];
    return cues.filter(c => c.start === primary.start && c.end === primary.end);
  }

  function setHighlight(group) {
    const newSet  = new Set(group);
    const oldSet  = new Set(currentGroup);

    currentGroup.forEach(c => { if (!newSet.has(c)) c.el.classList.remove('gm-reading'); });
    group.forEach(c        => { if (!oldSet.has(c)) c.el.classList.add('gm-reading'); });
    currentGroup = group;

    if (!mainEl) return;
    if (group.length > 0) {
      mainEl.classList.add('gm-reading-active');
      // Scroll the first element of the group into view if needed
      const rect = group[0].el.getBoundingClientRect();
      const navH = 70;
      if (rect.top < navH || rect.bottom > window.innerHeight - 60) {
        group[0].el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    } else {
      mainEl.classList.remove('gm-reading-active');
    }
  }

  function clearHighlight() {
    currentGroup.forEach(c => c.el.classList.remove('gm-reading'));
    currentGroup = [];
    if (mainEl) mainEl.classList.remove('gm-reading-active');
  }

  document.addEventListener('DOMContentLoaded', function () {
    mainEl = document.querySelector('main');
    buildCues();
    if (!cues.length) return;

    const audio = document.getElementById('gm-audio');
    if (!audio) return;

    audio.addEventListener('timeupdate', function () {
      setHighlight(findGroup(audio.currentTime));
    });

    audio.addEventListener('pause',  clearHighlight);
    audio.addEventListener('ended',  clearHighlight);
    audio.addEventListener('seeked', function () {
      setHighlight(findGroup(audio.currentTime));
    });

    cues.forEach(function (cue) {
      cue.el.style.cursor = 'pointer';
      cue.el.addEventListener('click', function (e) {
        e.stopPropagation();
        setHighlight(findGroup(cue.start));
        audio.addEventListener('seeked', function () {
          audio.play().catch(function () {});
        }, { once: true });
        audio.currentTime = cue.start;
      });
    });
  });
})();
