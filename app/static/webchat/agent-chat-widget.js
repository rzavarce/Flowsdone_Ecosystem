(function () {
  'use strict';

  class AgentChatWidget {
    constructor(options = {}) {
      this.config = {
        wsUrl: options.wsUrl || null,
        sessionId: options.sessionId || null,
        conversationId: options.conversationId || null,
        workflowId: options.workflowId || null,
        transport: options.transport || 'rabbitmq',
        userId: options.userId || null,
        modelName: options.modelName || 'chatgpt',
        n8nWebhookUrl: options.n8nWebhookUrl || null,
        n8nWebhookPath: options.n8nWebhookPath || null,
        mode: options.mode || 'widget',
        title: options.title || 'AI Assistant',
        initialMessage: options.initialMessage || 'Hi! How can I help you today?',
        inputPlaceholder: options.inputPlaceholder || 'Type your message...',
        waitingMessage: options.waitingMessage || 'Thinking',
        waitingMessageAnimated: options.waitingMessageAnimated !== false,
        sendLabel: options.sendLabel || 'Send',
        openLabel: options.openLabel || 'Open chat',
        closeLabel: options.closeLabel || 'Close chat',
        width: options.width || '420px',
        height: options.height || '680px',
        maxHeight: options.maxHeight || '80vh',
        position: options.position || 'bottom-right',
        bottom: options.bottom || '20px',
        sideOffset: options.sideOffset || '20px',
        launcherSize: options.launcherSize || '60px',
        launcherColor: options.launcherColor || '#4F46E5',
        launcherIconColor: options.launcherIconColor || '#ffffff',
        launcherIconAccentColor: options.launcherIconAccentColor || '#111827',
        launcherIconUrl: options.launcherIconUrl || null,
        headerColor: options.headerColor || '#111827',
        headerTextColor: options.headerTextColor || '#ffffff',
        userMessageColor: options.userMessageColor || '#4F46E5',
        userMessageTextColor: options.userMessageTextColor || '#ffffff',
        botMessageColor: options.botMessageColor || '#E5E7EB',
        botMessageTextColor: options.botMessageTextColor || '#111827',
        sendButtonColor: options.sendButtonColor || '#10B981',
        animation: options.animation || 'slide-up',
        animationDuration: options.animationDuration || '280ms',
        autoOpen: Boolean(options.autoOpen) || false,
        showLauncher: options.showLauncher !== false,
        closeOnEsc: options.closeOnEsc !== false,
        focusInputOnOpen: options.focusInputOnOpen !== false,
        toastDuration: options.toastDuration || 4500,
        reconnectInterval: options.reconnectInterval || 1500,
        maxReconnectInterval: options.maxReconnectInterval || 15000,
        messages: {
          socketConnecting: 'Connecting...',
          socketConnected: 'Connected',
          socketDisconnected: 'Disconnected',
          genericError: 'Something went wrong. Please try again.',
          queuedError: 'The message could not be queued.',
          ...(options.messages || {})
        }
      };

      if (!this.config.wsUrl) this.config.wsUrl = this.buildDefaultWsUrl();
      if (!this.config.sessionId) this.config.sessionId = this.getOrCreateSessionId();
      if (!this.config.conversationId) this.config.conversationId = this.getOrCreateConversationId();

      this.isOpen = false;
      this.isLoading = false;
      this.socket = null;
      this.socketReadyPromise = null;
      this.reconnectTimer = null;
      this.reconnectDelay = this.config.reconnectInterval;
      this.pendingBubbles = new Map();

      this.injectCssVariables();
      this.init();
      this.bindGlobalEvents();

      if (this.config.autoOpen) {
        setTimeout(() => this.open(), 100);
      }
    }

    buildDefaultWsUrl() {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      return `${protocol}//${window.location.host}/ws`;
    }

    getOrCreateSessionId() {
      const key = 'agent-chat-session-id';
      let sessionId = localStorage.getItem(key);
      if (!sessionId) {
        sessionId = `webchat-${Date.now()}-${Math.random().toString(36).slice(2)}`;
        localStorage.setItem(key, sessionId);
      }
      return sessionId;
    }

    getOrCreateConversationId() {
      const key = 'agent-chat-conversation-id';
      let id = localStorage.getItem(key);
      if (!id) {
        if (window.crypto && typeof window.crypto.randomUUID === 'function') {
          id = window.crypto.randomUUID();
        } else {
          id = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
            const r = (Math.random() * 16) | 0;
            const v = c === 'x' ? r : (r & 0x3) | 0x8;
            return v.toString(16);
          });
        }
        localStorage.setItem(key, id);
      }
      return id;
    }

    init() {
      if (this.config.mode === 'fullscreen') {
        this.createChatWindow();
        return;
      }
      if (this.config.showLauncher) {
        this.createLauncher();
      }
      this.createChatWindow();
    }

    bindGlobalEvents() {
      if (!this.config.closeOnEsc) return;
      document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && this.isOpen && this.config.mode !== 'fullscreen') {
          this.close(true);
        }
      });
    }

    injectCssVariables() {
      const root = document.documentElement;
      root.style.setProperty('--agent-chat-width', this.config.width);
      root.style.setProperty('--agent-chat-height', this.config.height);
      root.style.setProperty('--agent-chat-max-height', this.config.maxHeight);
      root.style.setProperty('--agent-chat-bottom', this.config.bottom);
      root.style.setProperty('--agent-chat-side-offset', this.config.sideOffset);
      root.style.setProperty('--agent-chat-launcher-size', this.config.launcherSize);
      root.style.setProperty('--agent-chat-launcher-color', this.config.launcherColor);
      root.style.setProperty('--agent-chat-header-color', this.config.headerColor);
      root.style.setProperty('--agent-chat-header-text-color', this.config.headerTextColor);
      root.style.setProperty('--agent-chat-user-color', this.config.userMessageColor);
      root.style.setProperty('--agent-chat-user-text-color', this.config.userMessageTextColor);
      root.style.setProperty('--agent-chat-bot-color', this.config.botMessageColor);
      root.style.setProperty('--agent-chat-bot-text-color', this.config.botMessageTextColor);
      root.style.setProperty('--agent-chat-send-color', this.config.sendButtonColor);
      root.style.setProperty('--agent-chat-animation-duration', this.config.animationDuration);
    }

    ensureSocket() {
      if (this.socket && this.socket.readyState === WebSocket.OPEN) {
        return Promise.resolve(this.socket);
      }
      if (this.socketReadyPromise) {
        return this.socketReadyPromise;
      }
      this.setConnectionState(false, this.config.messages.socketConnecting);
      const url = `${this.config.wsUrl.replace(/\/$/, '')}`;
      this.socket = new WebSocket(url);

      this.socketReadyPromise = new Promise((resolve, reject) => {
        const cleanup = () => {
          this.socket.removeEventListener('open', onOpen);
          this.socket.removeEventListener('error', onError);
        };
        const onOpen = () => {
          cleanup();
          this.socketReadyPromise = null;
          this.reconnectDelay = this.config.reconnectInterval;
          this.setConnectionState(true, this.config.messages.socketConnected);
          resolve(this.socket);
        };
        const onError = () => {
          cleanup();
          this.socketReadyPromise = null;
          this.setConnectionState(false, this.config.messages.socketDisconnected);
          reject(new Error(this.config.messages.socketDisconnected));
        };
        this.socket.addEventListener('open', onOpen);
        this.socket.addEventListener('error', onError);
      });

      this.socket.addEventListener('message', (event) => {
        this.handleSocketMessage(event);
      });

      this.socket.addEventListener('close', () => {
        this.setConnectionState(false, this.config.messages.socketDisconnected);
        this.socketReadyPromise = null;
        if (this.isOpen || this.isLoading) {
          this.scheduleReconnect();
        }
      });

      return this.socketReadyPromise;
    }

    scheduleReconnect() {
      if (this.reconnectTimer) return;
      this.reconnectTimer = setTimeout(() => {
        this.reconnectTimer = null;
        if (this.isOpen) {
          this.ensureSocket().catch(() => {});
          this.reconnectDelay = Math.min(this.reconnectDelay * 1.6, this.config.maxReconnectInterval);
        }
      }, this.reconnectDelay);
    }

    setConnectionState(connected, label) {
      if (!this.container) return;
      this.container.classList.toggle('agent-chat-online', connected);
      this.container.classList.toggle('agent-chat-offline', !connected);
      const statusText = this.container.querySelector('.agent-chat-status-text');
      if (statusText && label) statusText.textContent = label;
    }

    handleSocketMessage(event) {
      let data;
      try {
        data = JSON.parse(event.data);
      } catch {
        return;
      }

      if (data.type === 'chat.queued') {
        return;
      }

      if (data.type === 'chat.response') {
        const bubble = this.pendingBubbles.get(data.requestId);
        this.replaceWaitingMessage(bubble, data.response || data.output || data.message || '');
        this.pendingBubbles.delete(data.requestId);
        this.setLoading(false);
        return;
      }

      if (data.type === 'chat.error') {
        this.showToast(data.error || this.config.messages.genericError, 'error');
        this.setLoading(false);
      }
    }

    replaceWaitingMessage(bubble, text) {
      if (bubble) {
        bubble.innerHTML = this.escapeHtml(text);
      } else {
        this.addMessage(text, 'bot');
      }
      this.scrollToBottom();
    }

    createLauncher() {
      this.launcher = document.createElement('button');
      this.launcher.className = `agent-chat-launcher agent-chat-position-${this.config.position}`;
      this.launcher.type = 'button';
      this.launcher.setAttribute('aria-label', this.config.openLabel);

      this.launcher.innerHTML = this.config.launcherIconUrl
        ? `<img src="${this.escapeAttr(this.config.launcherIconUrl)}" alt="" />`
        : this.getDefaultIcon(this.config.launcherIconColor, this.config.launcherIconAccentColor);

      this.launcher.addEventListener('click', () => {
        this.open();
      });

      document.body.appendChild(this.launcher);
    }

    createChatWindow() {
      this.container = document.createElement('section');
      this.container.className = [
        'agent-chat-widget',
        `agent-chat-position-${this.config.position}`,
        `agent-chat-animation-${this.config.animation}`,
        this.config.mode === 'fullscreen' ? 'agent-chat-widget-fullscreen' : ''
      ].filter(Boolean).join(' ');

      this.container.innerHTML = `
        <header class="agent-chat-header">
          <div>
            <div class="agent-chat-title">${this.escapeHtml(this.config.title)}</div>
            <div class="agent-chat-status">
              <span></span>
              <span class="agent-chat-status-text">${this.escapeHtml(this.config.messages.socketDisconnected)}</span>
            </div>
          </div>
          ${this.config.mode === 'fullscreen' ? '' : `<button class="agent-chat-close-btn" type="button" aria-label="${this.escapeAttr(this.config.closeLabel)}">x</button>`}
        </header>
        <main class="agent-chat-messages" aria-live="polite"></main>
        <form class="agent-chat-input-area">
          <input type="text" autocomplete="off" placeholder="${this.escapeAttr(this.config.inputPlaceholder)}" />
          <button type="submit" aria-label="${this.escapeAttr(this.config.sendLabel)}">${this.getSendIcon()}</button>
        </form>
        <div class="agent-chat-toast-container"></div>
      `;

      document.body.appendChild(this.container);

      this.messageList = this.container.querySelector('.agent-chat-messages');
      this.input = this.container.querySelector('input');
      this.button = this.container.querySelector('.agent-chat-input-area button');

      const closeButton = this.container.querySelector('.agent-chat-close-btn');
      if (closeButton) closeButton.addEventListener('click', () => this.close(true));

      const form = this.container.querySelector('form');
      form.addEventListener('submit', (event) => {
        event.preventDefault();
        this.sendMessage();
      });

      this.addMessage(this.config.initialMessage, 'bot');
    }

    async open() {
      if (this.isOpen) return;
      this.isOpen = true;
      this.container.classList.add('agent-chat-widget-open');
      if (this.launcher) this.launcher.classList.add('agent-chat-launcher-hidden');

      try {
        await this.ensureSocket();
      } catch (error) {
        this.showToast(error.message || this.config.messages.socketDisconnected, 'error');
      }

      if (this.config.focusInputOnOpen) {
        setTimeout(() => { if (this.input) this.input.focus(); }, 200);
      }
    }

    close(force = false) {
      this.isOpen = false;
      this.container.classList.remove('agent-chat-widget-open');
      if (this.launcher) this.launcher.classList.remove('agent-chat-launcher-hidden');
      if (this.reconnectTimer) {
        clearTimeout(this.reconnectTimer);
        this.reconnectTimer = null;
      }
      if (force && this.socket && this.socket.readyState === WebSocket.OPEN) {
        this.socket.close(1000, 'chat closed');
        this.socket = null;
        this.socketReadyPromise = null;
      }
      this.setConnectionState(false, this.config.messages.socketDisconnected);
    }

    async sendMessage() {
      const text = this.input.value.trim();
      if (!text || this.isLoading) return;

      if (!this.config.workflowId || !this.config.conversationId) {
        this.showToast('Missing workflowId/conversationId in AgentChatConfig', 'error');
        return;
      }

      this.setLoading(true);
      this.addMessage(text, 'user');
      this.input.value = '';

      try {
        const socket = await this.ensureSocket();

        socket.send(JSON.stringify({
          type: "chat.message",
          workflow_id: this.config.workflowId,
          conversation_id: this.config.conversationId,
          sender_id: this.config.userId || "anonymous",
          channel: "web",
          payload: { message: text },
          transport: this.config.transport || "rabbitmq",
        }));

      } catch (error) {
        this.setLoading(false);
        this.showToast(error.message || this.config.messages.genericError, 'error');
      }
    }

    setLoading(loading) {
      this.isLoading = loading;
      if (this.button) this.button.disabled = loading;
      if (!loading && this.input && this.isOpen) this.input.focus();
    }

    addMessage(text, sender = 'bot') {
      const bubble = document.createElement('div');
      bubble.className = `agent-chat-bubble agent-chat-${sender}-message`;
      bubble.innerHTML = this.escapeHtml(text);
      this.messageList.appendChild(bubble);
      this.scrollToBottom();
      return bubble;
    }

    scrollToBottom() {
      this.messageList.scrollTop = this.messageList.scrollHeight;
    }

    showToast(message, type = 'error') {
      const toastContainer = this.container.querySelector('.agent-chat-toast-container');
      const toast = document.createElement('div');
      toast.className = `agent-chat-toast agent-chat-toast-${type}`;
      toast.textContent = message;
      toastContainer.appendChild(toast);
      setTimeout(() => toast.classList.add('agent-chat-toast-visible'), 10);
      setTimeout(() => {
        toast.classList.remove('agent-chat-toast-visible');
        setTimeout(() => toast.remove(), 250);
      }, this.config.toastDuration);
    }

    getDefaultIcon(primary, accent) {
      primary = primary || '#ffffff';
      accent = accent || '#111827';
      return '<svg width="32" height="32" viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
        + '<path d="M35 40C35 33.3726 40.3726 28 47 28H73C79.6274 28 85 33.3726 85 40V60C85 66.6274 79.6274 72 73 72H55L45 82V72H47C40.3726 72 35 66.6274 35 60V40Z" fill="' + this.escapeAttr(primary) + '"/>'
        + '<circle cx="52" cy="50" r="3.5" fill="' + this.escapeAttr(accent) + '" />'
        + '<circle cx="68" cy="50" r="3.5" fill="' + this.escapeAttr(accent) + '" />'
        + '<rect x="54" y="58" width="12" height="3.5" rx="1.75" fill="' + this.escapeAttr(accent) + '" />'
        + '</svg>';
    }

    getSendIcon() {
      return '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3.4 20.4L21 12L3.4 3.6L3 10.2L14 12L3 13.8L3.4 20.4Z" fill="currentColor" /></svg>';
    }

    escapeHtml(value) {
      return String(value)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#039;');
    }

    escapeAttr(value) {
      return this.escapeHtml(value);
    }
  }

  window.AgentChat = {
    init: function(options) {
      options = options || {};
      if (window.__agentChatInstance) return window.__agentChatInstance;
      window.__agentChatInstance = new AgentChatWidget(options);
      return window.__agentChatInstance;
    },
    destroy: function() {
      if (window.__agentChatInstance) window.__agentChatInstance.close(true);
      window.__agentChatInstance = null;
    }
  };

  window.N8nChatWidget = window.AgentChat;

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      if (window.AgentChatConfig && !window.__agentChatInstance) {
        window.AgentChat.init(window.AgentChatConfig);
      }
    });
  } else {
    if (window.AgentChatConfig && !window.__agentChatInstance) {
      window.AgentChat.init(window.AgentChatConfig);
    }
  }

})();