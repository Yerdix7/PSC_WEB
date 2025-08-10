// static/keystroke.js
// Genera un "recorder" sobre un input para capturar keydown/keyup y exportar JSON compatible con tu API.

function KeystrokeRecorder(inputEl) {
  const timings = [];
  let t0 = null;
  let lastUpTime = null;

  function now() {
    return Date.now();
  }

  function onKeyDown(ev) {
    if (!t0) { t0 = now(); lastUpTime = t0; }
    const t = now() - t0;
    // Evitamos duplicar keydown si el SO repite
    const last = timings.length ? timings[timings.length-1] : null;
    if (last && last.key === ev.key && last.release_time === null) {
      return;
    }
    timings.push({
      key: ev.key,
      press_time: t,
      release_time: null
    });
  }

  function onKeyUp(ev) {
    if (!t0) return;
    const t = now() - t0;
    // busca el último sin release de la misma tecla
    for (let i = timings.length - 1; i >= 0; i--) {
      if (timings[i].key === ev.key && timings[i].release_time === null) {
        timings[i].release_time = t;
        break;
      }
    }
    lastUpTime = t;
  }

  inputEl.addEventListener("keydown", onKeyDown);
  inputEl.addEventListener("keyup", onKeyUp);

  function exportPayload() {
    const total_time = lastUpTime ?? 0;
    // Filtra entradas corruptas (sin release)
    const clean = timings.filter(x => x.release_time !== null);
    return {
      password: inputEl.value || "",
      keystroke_timings: clean,
      total_time
    };
  }

  return {
    export: exportPayload
  };
}
