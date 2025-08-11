// static/keystroke.js - Versión mejorada y corregida

function KeystrokeRecorder(inputEl) {
  const timings = [];
  let startTime = null;
  let isRecording = false;
  let keyStates = new Map(); // Para trackear el estado de cada tecla

  function getCurrentTime() {
    return performance.now(); // Más preciso que Date.now()
  }

  function startRecording() {
    console.log('🎯 Iniciando captura de keystroke...');
    timings.length = 0;
    keyStates.clear();
    startTime = getCurrentTime();
    isRecording = true;
  }

  function stopRecording() {
    console.log('🛑 Deteniendo captura de keystroke...');
    isRecording = false;
    const payload = exportPayload();
    console.log('📊 Datos capturados:', payload);
    return payload;
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
    keyStates.set(keyCode, {
      startTime: relativeTime,
      index: timings.length
    });
    
    // Registrar el evento
    timings.push({
      key: keyCode,
      press_time: relativeTime,
      release_time: null,
      index: timings.length
    });
    
    console.log(`⌨️ KeyDown: ${keyCode} at ${relativeTime}ms`);
  }

  function onKeyUp(ev) {
    if (!isRecording) return;
    
    const currentTime = getCurrentTime();
    const relativeTime = Math.round(currentTime - startTime);
    const keyCode = ev.key;
    
    // Buscar el estado de la tecla
    const keyState = keyStates.get(keyCode);
    if (keyState) {
      // Encontrar el timing correspondiente y actualizar release_time
      const timingIndex = keyState.index;
      if (timings[timingIndex] && timings[timingIndex].release_time === null) {
        timings[timingIndex].release_time = relativeTime;
        console.log(`⌨️ KeyUp: ${keyCode} at ${relativeTime}ms (dwell: ${relativeTime - keyState.startTime}ms)`);
      }
      
      // Limpiar el estado
      keyStates.delete(keyCode);
    }
  }

  function exportPayload() {
    const endTime = getCurrentTime();
    const totalTime = startTime ? Math.round(endTime - startTime) : 0;
    
    // Filtrar y formatear los timings válidos
    const validTimings = timings
        .filter(t => t.release_time !== null && t.press_time !== null)
        .map(t => ({
            key: t.key,
            press_time: t.press_time,
            release_time: t.release_time
        }));

    console.log(`📈 Exportando: ${validTimings.length} teclas válidas de ${timings.length} totales`);
    
    return {
        password: inputEl.value || "",
        keystroke_timings: validTimings,
        total_time: totalTime
    };
  }

  // Event listeners con opciones para mejor captura
  inputEl.addEventListener("keydown", onKeyDown, { capture: true, passive: false });
  inputEl.addEventListener("keyup", onKeyUp, { capture: true, passive: false });
  
  // Eventos de input para debugging
  inputEl.addEventListener('input', () => {
    if (isRecording) {
      console.log(`📝 Input value: "${inputEl.value}" (${inputEl.value.length} chars)`);
    }
  });

  return {
    start: startRecording,
    stop: stopRecording,
    export: exportPayload,
    isRecording: () => isRecording,
    getTimings: () => [...timings], // Para debugging
    reset: () => {
      console.log('🔄 Reseteando recorder...');
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

  // Calcular diferencias en dwell times
  let totalDifference = 0;
  let validComparisons = 0;
  const minLength = Math.min(timings1.length, timings2.length);
  
  for (let i = 0; i < minLength; i++) {
    if (timings1[i].key === timings2[i].key) {
      const dwell1 = timings1[i].release_time - timings1[i].press_time;
      const dwell2 = timings2[i].release_time - timings2[i].press_time;
      
      if (dwell1 > 0 && dwell2 > 0) {
        const difference = Math.abs(dwell1 - dwell2);
        totalDifference += difference;
        validComparisons++;
      }
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
    score: Math.round(score * 100) / 100,
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
  const dwellTimes = [];
  const flightTimes = [];
  
  for (let timing of timings) {
    const dwell = timing.release_time - timing.press_time;
    if (dwell > 0) {
      dwellTimes.push(dwell);
    }
  }
  
  for (let i = 0; i < timings.length - 1; i++) {
    const flight = timings[i + 1].press_time - timings[i].release_time;
    if (flight >= 0) flightTimes.push(flight);
  }

  if (dwellTimes.length === 0) {
    return { valid: false, reason: "No hay dwell times válidos" };
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
  const negativeFlights = flightTimes.filter(f => f < 0).length;
  if (negativeFlights > flightTimes.length * 0.5) {
    anomalies.push("Demasiadas teclas superpuestas");
  }

  return {
    valid: anomalies.length === 0,
    anomalies: anomalies,
    stats: {
      avgDwell: Math.round(avgDwell),
      avgFlight: Math.round(avgFlight),
      totalKeys: timings.length,
      validDwells: dwellTimes.length,
      totalTime: data.total_time
    }
  };
}

async function sendPracticeAttempt(attemptData) {
    try {
        console.log('📤 Enviando intento de práctica:', attemptData);
        
        const response = await fetch('/register/practice', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(attemptData)
        });
        
        const result = await response.json();
        console.log('📥 Respuesta del servidor:', result);
        return result;
    } catch (error) {
        console.error('❌ Error:', error);
        return { success: false, error: 'Error de conexión' };
    }
}

// Función para manejar el proceso de práctica
async function handlePracticeSession(inputElement) {
    const recorder = new KeystrokeRecorder(inputElement);
    let attempts = 0;
    const maxAttempts = 3;
    
    // Auto-iniciar cuando el input reciba foco
    inputElement.addEventListener('focus', () => {
        if (!recorder.isRecording()) {
            recorder.start();
        }
    });
    
    // Configurar el evento para cuando se complete un intento
    inputElement.addEventListener('blur', async function() {
        if (recorder.isRecording() && inputElement.value.length > 0) {
            const attemptData = recorder.stop();
            attempts++;
            
            // Mostrar feedback al usuario
            const feedbackEl = document.getElementById('practice-feedback');
            if (feedbackEl) {
                feedbackEl.textContent = `Intento ${attempts} de ${maxAttempts} completado`;
                feedbackEl.style.color = '#007bff';
            }
            
            // Enviar el intento al servidor
            const result = await sendPracticeAttempt(attemptData);
            
            if (result.success) {
                if (attempts >= maxAttempts) {
                    if (result.can_register) {
                        if (feedbackEl) {
                            feedbackEl.textContent = "✅ ¡Patrón validado! Puedes registrarte";
                            feedbackEl.style.color = 'green';
                        }
                        const registerBtn = document.getElementById('register-btn');
                        if (registerBtn) registerBtn.disabled = false;
                    } else {
                        if (feedbackEl) {
                            feedbackEl.textContent = "❌ Patrón inconsistente. Reinicia la práctica";
                            feedbackEl.style.color = 'red';
                        }
                        attempts = 0;
                        recorder.reset();
                    }
                } else {
                    if (feedbackEl) {
                        feedbackEl.textContent = `✓ Intento ${attempts} guardado. Faltan ${maxAttempts - attempts}`;
                        feedbackEl.style.color = 'green';
                    }
                }
            } else {
                if (feedbackEl) {
                    feedbackEl.textContent = `❌ Error: ${result.error || result.message}`;
                    feedbackEl.style.color = 'red';
                }
            }
        }
    });
    
    return recorder;
}

// Debugging utilities
function debugKeystrokeData(data) {
    console.group('🔍 Keystroke Debug Data');
    console.log('Password length:', data.password?.length || 0);
    console.log('Total time:', data.total_time, 'ms');
    console.log('Timing entries:', data.keystroke_timings?.length || 0);
    
    if (data.keystroke_timings && data.keystroke_timings.length > 0) {
        console.table(data.keystroke_timings.map(t => ({
            key: t.key,
            press: t.press_time,
            release: t.release_time,
            dwell: t.release_time - t.press_time
        })));
    }
    console.groupEnd();
}

// Inicialización cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 Keystroke.js cargado');
    
    // Para la página de práctica/registro
    const passwordInput = document.getElementById('password-practice');
    if (passwordInput) {
        console.log('📝 Configurando práctica de registro');
        handlePracticeSession(passwordInput);
    }
    
    // Para la página de login
    const loginPasswordInput = document.getElementById('passwordInput');
    if (loginPasswordInput) {
        console.log('🔑 Configurando keystroke para login');
        const loginRecorder = new KeystrokeRecorder(loginPasswordInput);
        
        const loginForm = document.getElementById('loginForm');
        if (loginForm) {
            loginForm.addEventListener('submit', function(e) {
                if (loginRecorder.isRecording()) {
                    const keystrokePayload = loginRecorder.stop();
                    const keystrokeData = document.getElementById('keystrokeData');
                    if (keystrokeData) {
                        keystrokeData.value = JSON.stringify(keystrokePayload);
                        console.log('📤 Datos de keystroke agregados al login');
                    }
                }
            });
            
            loginPasswordInput.addEventListener('focus', function() {
                loginRecorder.start();
            });
        }
    }
});

// Export para uso global
window.KeystrokeRecorder = KeystrokeRecorder;
window.analyzeKeystrokePattern = analyzeKeystrokePattern;
window.compareKeystrokePatterns = compareKeystrokePatterns;
window.debugKeystrokeData = debugKeystrokeData;