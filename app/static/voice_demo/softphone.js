(function () {
  "use strict";

  const config = window.VoiceDemoConfig || {};
  const statusEl = document.getElementById("sp-status");
  const statusTextEl = document.getElementById("sp-status-text");
  const callBtn = document.getElementById("sp-call-btn");
  const logEl = document.getElementById("sp-log");

  let device = null;
  let activeCall = null;

  function log(message, isError) {
    const entry = document.createElement("div");
    entry.className = "sp-log-entry" + (isError ? " sp-log-error" : "");
    const time = document.createElement("span");
    time.className = "sp-log-time";
    time.textContent = new Date().toLocaleTimeString();
    const text = document.createElement("span");
    text.textContent = message;
    entry.appendChild(time);
    entry.appendChild(text);
    logEl.appendChild(entry);
    logEl.scrollTop = logEl.scrollHeight;
  }

  function setStatus(state, text) {
    statusEl.className = "sp-status sp-status-" + state;
    statusTextEl.textContent = text;
  }

  function setCallButton(mode) {
    if (mode === "call") {
      callBtn.textContent = "Llamar a " + config.toNumber;
      callBtn.classList.remove("sp-hangup");
      callBtn.disabled = false;
    } else if (mode === "hangup") {
      callBtn.textContent = "Colgar";
      callBtn.classList.add("sp-hangup");
      callBtn.disabled = false;
    } else {
      callBtn.disabled = true;
    }
  }

  async function fetchToken() {
    const url = "/voice-demo/token?identity=" + encodeURIComponent(config.identity);
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error("token endpoint returned " + response.status);
    }
    const data = await response.json();
    return data.token;
  }

  async function initDevice() {
    setCallButton("disabled");
    setStatus("connecting", "Obteniendo token...");
    log("Solicitando Access Token al gateway...");

    const token = await fetchToken();

    device = new Twilio.Device(token, { logLevel: 1 });

    device.on("registered", () => {
      setStatus("connected", "Listo para llamar");
      log("Softphone registrado con Twilio.");
      setCallButton("call");
    });

    device.on("error", (error) => {
      log("Error del Device: " + error.message, true);
      setStatus("ready", "Error - revisa la consola");
    });

    await device.register();
  }

  function attachCallHandlers(call) {
    call.on("accept", () => {
      setStatus("in-call", "En llamada");
      log("Llamada conectada.");
      setCallButton("hangup");
    });

    call.on("disconnect", () => {
      setStatus("connected", "Listo para llamar");
      log("Llamada finalizada.");
      activeCall = null;
      setCallButton("call");
    });

    call.on("cancel", () => {
      log("Llamada cancelada.");
    });

    call.on("error", (error) => {
      log("Error en la llamada: " + error.message, true);
    });
  }

  async function placeCall() {
    setCallButton("disabled");
    setStatus("in-call", "Llamando...");
    log('Marcando ' + config.toNumber + " (esto llega al mismo webhook /webhooks/voice de una llamada real)...");

    activeCall = await device.connect({ params: { To: config.toNumber } });
    attachCallHandlers(activeCall);
  }

  function hangUp() {
    if (activeCall) {
      activeCall.disconnect();
    }
  }

  callBtn.addEventListener("click", () => {
    if (activeCall) {
      hangUp();
    } else {
      placeCall().catch((error) => log("No se pudo iniciar la llamada: " + error.message, true));
    }
  });

  initDevice().catch((error) => {
    setStatus("ready", "No se pudo inicializar");
    log("Fallo al inicializar el softphone: " + error.message, true);
  });
})();
