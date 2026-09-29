/* "Llamar" tab of the demo page: a browser softphone (Twilio Voice JS SDK)
   that calls the agent's real voice channel through the same /webhooks/voice
   as a phone call. The token (and the number to dial) only comes with a
   valid demo link: GET /voice-demo/token?share=... | ?test_token=... */
(function () {
  "use strict";

  const SDK_URL = "https://cdn.jsdelivr.net/npm/@twilio/voice-sdk@2/dist/twilio.min.js";

  const TEXT = {
    ready: "Listo para llamar",
    loading: "Preparando la llamada…",
    connecting: "Llamando…",
    inCall: "En llamada",
    ended: "Llamada finalizada",
    muted: "Micrófono silenciado",
    micDenied: "Necesitamos permiso para usar el micrófono. Actívalo en el candado de la barra de direcciones y vuelve a intentarlo.",
    failed: "No se pudo completar la llamada. Inténtalo de nuevo en unos segundos.",
    unavailable: "La llamada no está disponible ahora mismo.",
  };

  function el(id) {
    return document.getElementById(id);
  }

  function loadSdk() {
    if (window.Twilio && window.Twilio.Device) return Promise.resolve();
    return new Promise(function (resolve, reject) {
      const script = document.createElement("script");
      script.src = SDK_URL;
      script.onload = function () { resolve(); };
      script.onerror = function () { reject(new Error("sdk")); };
      document.head.appendChild(script);
    });
  }

  function formatNumber(number) {
    // +16014944500 -> +1 601 494 4500 ; other lengths are grouped in threes.
    const digits = number.replace(/[^\d]/g, "");
    if (number.startsWith("+1") && digits.length === 11) {
      return "+1 " + digits.slice(1, 4) + " " + digits.slice(4, 7) + " " + digits.slice(7);
    }
    return number.replace(/(\+\d{2})(\d{3})(\d{3})(\d+)/, "$1 $2 $3 $4");
  }

  const VoiceDemo = {
    /**
     * Ask the gateway whether this link can call; if so, show the "Llamar" tab.
     * @param {{shareToken?: string|null, testToken?: string|null, onAvailable?: function}} options
     */
    init: async function (options) {
      this.options = options || {};
      this.identity = this.storedIdentity();
      let data;
      try {
        data = await this.fetchToken();
      } catch (e) {
        return; // no voice for this link: the tab stays hidden
      }
      this.token = data.token;
      this.toNumber = data.to_number;
      this.bindUi();
      if (typeof this.options.onAvailable === "function") this.options.onAvailable(this.toNumber);
    },

    /**
     * The caller's identity, kept in localStorage so every call from this
     * browser is the same contact (and the name staff give it sticks).
     * @returns {string}
     */
    storedIdentity: function () {
      const key = "fd-voice-demo-identity";
      let identity = null;
      try { identity = localStorage.getItem(key); } catch (e) { /* no storage */ }
      if (!identity || !/^demo-[a-z0-9]{8}$/.test(identity)) {
        identity = "demo-" + Math.random().toString(36).slice(2, 10).padEnd(8, "0");
        try { localStorage.setItem(key, identity); } catch (e) { /* no storage: one per page load */ }
      }
      return identity;
    },

    fetchToken: async function () {
      const params = new URLSearchParams({ identity: this.identity });
      if (this.options.shareToken) params.set("share", this.options.shareToken);
      else if (this.options.testToken) params.set("test_token", this.options.testToken);
      const response = await fetch("/voice-demo/token?" + params.toString(), { cache: "no-store" });
      if (!response.ok) throw new Error("token " + response.status);
      return response.json();
    },

    bindUi: function () {
      const self = this;
      const alt = el("call-alt-number");
      if (alt) {
        alt.textContent = formatNumber(this.toNumber);
        alt.href = "tel:" + this.toNumber;
      }
      el("call-start").addEventListener("click", function () { self.start(); });
      el("call-hangup").addEventListener("click", function () { self.hangUp(); });
      el("call-mute").addEventListener("click", function () { self.toggleMute(); });
      window.addEventListener("beforeunload", function () { self.hangUp(); });
      this.setState("ready");
    },

    setState: function (state, message) {
      this.state = state;
      const panel = el("call-panel");
      panel.dataset.state = state;
      el("call-status").textContent = message || TEXT[state] || "";
      const inCall = state === "connecting" || state === "inCall";
      el("call-start").hidden = inCall;
      el("call-start").disabled = state === "loading";
      el("call-hangup").hidden = !inCall;
      el("call-mute").hidden = state !== "inCall";
      el("call-timer").hidden = state !== "inCall";
      if (state !== "inCall") this.stopTimer();
    },

    start: async function () {
      const self = this;
      this.setState("loading");
      try {
        await loadSdk();
        if (!this.device) {
          this.device = new window.Twilio.Device(this.token, { codecPreferences: ["opus", "pcmu"], logLevel: 1 });
          this.device.on("tokenWillExpire", async function () {
            try {
              const data = await self.fetchToken();
              self.token = data.token;
              self.device.updateToken(data.token);
            } catch (e) { /* the call in progress keeps going; the next one will fail and say so */ }
          });
          this.device.on("error", function (error) { self.fail(error); });
        }
        this.setState("connecting");
        this.call = await this.device.connect({ params: { To: this.toNumber } });
        this.call.on("accept", function () {
          self.setState("inCall");
          self.startTimer();
        });
        this.call.on("disconnect", function () {
          self.call = null;
          self.setState("ended");
          setTimeout(function () { if (self.state === "ended") self.setState("ready"); }, 3000);
        });
        this.call.on("cancel", function () {
          self.call = null;
          self.setState("ready");
        });
        this.call.on("error", function (error) { self.fail(error); });
      } catch (error) {
        this.fail(error);
      }
    },

    fail: function (error) {
      const code = error && (error.code || (error.originalError && error.originalError.code));
      const denied = code === 31401 || code === 31208 || (error && error.name === "NotAllowedError");
      if (this.call) {
        try { this.call.disconnect(); } catch (e) { /* already gone */ }
        this.call = null;
      }
      this.setState("error", denied ? TEXT.micDenied : error && error.message === "sdk" ? TEXT.unavailable : TEXT.failed);
      el("call-start").hidden = false;
      el("call-start").disabled = false;
    },

    hangUp: function () {
      if (this.call) this.call.disconnect();
    },

    toggleMute: function () {
      if (!this.call) return;
      const muted = !this.call.isMuted();
      this.call.mute(muted);
      const button = el("call-mute");
      button.setAttribute("aria-pressed", String(muted));
      button.querySelector("span").textContent = muted ? "Activar micrófono" : "Silenciar";
      el("call-status").textContent = muted ? TEXT.muted : TEXT.inCall;
    },

    startTimer: function () {
      const started = Date.now();
      const timer = el("call-timer");
      const tick = function () {
        const seconds = Math.floor((Date.now() - started) / 1000);
        timer.textContent = String(Math.floor(seconds / 60)).padStart(2, "0") + ":" + String(seconds % 60).padStart(2, "0");
      };
      tick();
      this.timer = setInterval(tick, 1000);
    },

    stopTimer: function () {
      if (this.timer) clearInterval(this.timer);
      this.timer = null;
    },
  };

  window.FlowsdoneVoiceDemo = VoiceDemo;
})();
