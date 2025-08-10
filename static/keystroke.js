// static/keystroke.js - Versión mejorada
// Genera un "recorder" sobre un input para capturar keydown/keyup con mejor precisión

function KeystrokeRecorder(inputEl) {
  const timings = [];
  let startTime = null;
  let isRecording = false;
  let keyStates = new Map(); // Para trackear el estado de cada tecla

  function getCurrentTime() {
    return performance.now(); // Más preciso que Date.now()
  }

  function startRecording() {
    timings.length = 0;
    keyStates.clear();
    startTime = getCurrentTime();
    isRecording = true;
  }

  function stopRecording() {
    isRecording = false;
    return exportPayload();
  }

  function onKeyDown(ev) {
    if (!isRecording) return;
    
    const currentTime = getCurrentTime();
    if (!startTime) {
      startTime = currentTime;
    }
    
    const relativeTime = Math.round(currentTime - startTime);
    const keyCode = ev.key;
    
    // Evitar repeticiones de keydown (cuando se mantiene presionada)
    if (keyStates.has(keyCode)) {
      return;
    }
    
    // Marcar la tecla como presionada
    keyStates.set(keyCode, true);
    
    // Registrar el evento
    timings.push({
      key: keyCode,
      press_time: relativeTime,
      release_time: null,
      index: timings.length
    });
  }

  function onKeyUp(ev) {
    if (!isRecording) return;
    
    const currentTime = getCurrentTime();
    const relativeTime = Math.round(currentTime - startTime);
    const keyCode = ev.key;
    
    // Marcar la tecla como liberada
    keyStates.delete(keyCode);
    
    // Buscar el último keydown sin keyup para esta tecla
    for (let i = timings.length - 1; i >= 0; i--) {
      if (timings[i].key === keyCode && timings[i].release_time === null) {
        timings[i].release_time = relativeTime;
        break;
      }
    }
  }

  function exportPayload() {
    const endTime = getCurrentTime();
    const totalTime = startTime ? Math.round(endTime - startTime) : 0;
    
    // Filtrar y formatear los timings según el modelo esperado
    const validTimings = timings
        .filter(t => t.release_time !== null)
        .map(t => ({
            key: t.key,
            press_time: t.press_time,
            release_time: t.release_time
        }));

    return {
        password: inputEl.value || "",
        keystroke_timings: validTimings,
        total_time: totalTime
    };
}

  // Event listeners con opciones para mejor captura
  inputEl.addEventListener("keydown", onKeyDown, { capture: true });
  inputEl.addEventListener("keyup", onKeyUp, { capture: true });
  
  // Auto-iniciar cuando el input reciba foco
  inputEl.addEventListener('focus', () => {
    if (!isRecording) startRecording();
  });

  // Parar automáticamente cuando pierde foco (opcional)
  inputEl.addEventListener('blur', () => {
    if (isRecording && inputEl.value.length > 0) {
      // Dar un pequeño delay para capturar el último keyup
      setTimeout(() => {
        if (isRecording) stopRecording();
      }, 100);
    }
  });

  return {
    start: startRecording,
    stop: stopRecording,
    export: exportPayload,
    isRecording: () => isRecording,
    getTimings: () => [...timings], // Para debugging
    reset: () => {
      timings.length = 0;
      keyStates.clear();
      startTime = null;
      isRecording = false;
    }
  };
}

// Función de utilidad para comparar patrones de keystroke
function compareKeystrokePatterns(pattern1, pattern2, threshold = 0.7) {
  if (!pattern1.keystroke_timings || !pattern2.keystroke_timings) {
    return { similar: false, score: 0, reason: "Datos insuficientes" };
  }

  const timings1 = pattern1.keystroke_timings;
  const timings2 = pattern2.keystroke_timings;

  // Verificar que las contraseñas sean iguales
  if (pattern1.password !== pattern2.password) {
    return { similar: false, score: 0, reason: "Contraseñas diferentes" };
  }

  // Verificar longitudes similares
  if (Math.abs(timings1.length - timings2.length) > 2) {
    return { similar: false, score: 0, reason: "Longitudes muy diferentes" };
  }

  // Calcular diferencias en dwell times (tiempo que se mantiene presionada cada tecla)
  let totalDifference = 0;
  let validComparisons = 0;

  const minLength = Math.min(timings1.length, timings2.length);
  
  for (let i = 0; i < minLength; i++) {
    if (timings1[i].key === timings2[i].key) {
      const dwell1 = timings1[i].release_time - timings1[i].press_time;
      const dwell2 = timings2[i].release_time - timings2[i].press_time;
      
      const difference = Math.abs(dwell1 - dwell2);
      totalDifference += difference;
      validComparisons++;
    }
  }

  if (validComparisons === 0) {
    return { similar: false, score: 0, reason: "No hay comparaciones válidas" };
  }

  // Calcular score de similitud
  const avgDifference = totalDifference / validComparisons;
  const maxExpectedDiff = 150; // ms - ajustable según tolerancia
  const score = Math.max(0, 1 - (avgDifference / maxExpectedDiff));

  return {
    similar: score >= threshold,
    score: score,
    reason: score >= threshold ? "Patrón consistente" : "Patrón inconsistente",
    avgDifference: Math.round(avgDifference),
    validComparisons: validComparisons
  };
}

// Función para análisis detallado de keystroke dynamics
function analyzeKeystrokePattern(data) {
  if (!data.keystroke_timings || data.keystroke_timings.length === 0) {
    return { valid: false, reason: "Sin datos de timing" };
  }

  const timings = data.keystroke_timings;
  
  // Calcular estadísticas básicas
  const dwellTimes = timings.map(t => t.release_time - t.press_time);
  const flightTimes = [];
  
  for (let i = 0; i < timings.length - 1; i++) {
    const flight = timings[i + 1].press_time - timings[i].release_time;
    if (flight >= 0) flightTimes.push(flight);
  }

  const avgDwell = dwellTimes.reduce((a, b) => a + b, 0) / dwellTimes.length;
  const avgFlight = flightTimes.length > 0 ? flightTimes.reduce((a, b) => a + b, 0) / flightTimes.length : 0;
  
  // Detectar patrones anómalos
  const anomalies = [];
  
  // Dwell times muy largos o muy cortos
  const longDwells = dwellTimes.filter(d => d > 500).length;
  const shortDwells = dwellTimes.filter(d => d < 30).length;
  
  if (longDwells > timings.length * 0.3) {
    anomalies.push("Muchas teclas mantenidas demasiado tiempo");
  }
  
  if (shortDwells > timings.length * 0.3) {
    anomalies.push("Muchas teclas presionadas muy rápido");
  }

  // Flight times negativos (teclas superpuestas)
  const negativeFlight = flightTimes.filter(f => f < 0).length;
  if (negativeFlight > flightTimes.length * 0.5) {
    anomalies.push("Demasiadas teclas superpuestas");
  }

  return {
    valid: anomalies.length === 0,
    anomalies: anomalies,
    stats: {
      avgDwell: Math.round(avgDwell),
      avgFlight: Math.round(avgFlight),
      totalKeys: timings.length,
      totalTime: data.total_time
    }
  };
}

async function sendPracticeAttempt(attemptData) {
    try {
        const response = await fetch('/register/practice', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(attemptData)
        });
        
        return await response.json();
    } catch (error) {
        console.error('Error:', error);
        return { success: false, error: 'Error de conexión' };
    }
}

// Función para manejar el proceso de práctica
async function handlePracticeSession(inputElement) {
    const recorder = new KeystrokeRecorder(inputElement);
    let attempts = 0;
    const maxAttempts = 3;
    
    // Configurar el evento para cuando se complete un intento
    inputElement.addEventListener('blur', async function() {
        if (recorder.isRecording() && inputElement.value.length > 0) {
            const attemptData = recorder.stop();
            attempts++;
            
            // Mostrar feedback al usuario
            const feedbackEl = document.getElementById('practice-feedback');
            feedbackEl.textContent = `Intento ${attempts} de ${maxAttempts} completado`;
            
            // Enviar el intento al servidor
            const result = await sendPracticeAttempt(attemptData);
            
            if (result.success) {
                if (attempts >= maxAttempts) {
                    if (result.can_register) {
                        feedbackEl.textContent = "¡Patrón validado! Puedes registrarte";
                        document.getElementById('register-btn').disabled = false;
                    } else {
                        feedbackEl.textContent = "Patrón inconsistente. Por favor, inténtalo de nuevo";
                        attempts = 0;
                        recorder.reset();
                    }
                }
            } else {
                feedbackEl.textContent = `Error: ${result.error || result.message}`;
            }
        }
    });
}

// Inicialización cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', function() {
    const passwordInput = document.getElementById('password-practice');
    if (passwordInput) {
        handlePracticeSession(passwordInput);
    }
});