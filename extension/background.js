/**
 * FBKit — Background Service Worker (Chrome MV3)
 *
 * Maintains persistent WebSocket connection to FBKit Agent.
 * Dispatches commands from Agent → content scripts on facebook.com tabs.
 * Relays results back to Agent.
 */

const WS_BASE_URL = "ws://127.0.0.1:9222";
const AGENT_API = "http://127.0.0.1:8100";
/** Base delay for exponential reconnect (ms). */
const RECONNECT_BASE_MS = 1000;
/** Cap so recovery stays responsive when agent returns. */
const RECONNECT_MAX_MS = 30000;
const RECONNECT_JITTER_MS = 500;
const PING_INTERVAL_MS = 25000;
const EXTENSION_LIVE_ACTIONS_ENABLED = false;

let ws = null;
let pingTimer = null;
let reconnectTimer = null;
let reconnectAttempt = 0;
/** Prevents parallel connectWS from alarm + onclose + popup. */
let connectInFlight = false;
/** onclose events to ignore after intentional dispose (async close race). */
let ignoreCloseCount = 0;

async function getApiKey() {
  const data = await chrome.storage.local.get(["fbkitApiKey"]);
  return (data.fbkitApiKey || "").trim();
}

async function getProfileIdentity() {
  const data = await chrome.storage.local.get(["fbkitProfileId", "fbkitProfileName"]);
  const profileId = data.fbkitProfileId || `profile_${Math.random().toString(36).slice(2, 10)}`;
  const profileName = data.fbkitProfileName || profileId;
  if (!data.fbkitProfileId || !data.fbkitProfileName) {
    await chrome.storage.local.set({ fbkitProfileId: profileId, fbkitProfileName: profileName });
  }
  return { profileId, profileName };
}

async function buildWsUrl() {
  const apiKey = await getApiKey();
  if (!apiKey) return WS_BASE_URL;
  return `${WS_BASE_URL}?api_key=${encodeURIComponent(apiKey)}`;
}

// ─── FB UID Resolver ────────────────────────────────────────

/**
 * Read the Facebook `c_user` cookie — contains the logged-in user's UID.
 * Returns null if not logged in or cookie not accessible.
 */
let cachedFbUid = { value: null, at: 0 };
const FB_UID_CACHE_MS = 30000;

async function getFbUid(force = false) {
  const now = Date.now();
  if (!force && now - cachedFbUid.at < FB_UID_CACHE_MS) {
    return cachedFbUid.value;
  }
  try {
    const cookie = await chrome.cookies.get({
      url: "https://www.facebook.com",
      name: "c_user",
    });
    cachedFbUid = { value: cookie ? cookie.value : null, at: now };
    return cachedFbUid.value;
  } catch {
    cachedFbUid = { value: null, at: now };
    return null;
  }
}

if (chrome.cookies?.onChanged) {
  chrome.cookies.onChanged.addListener(async (changeInfo) => {
    if (changeInfo.cookie?.name === "c_user") {
      cachedFbUid = { value: null, at: 0 };
      const currentFbUid = await getFbUid(true);
      const identity = await getProfileIdentity();
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
          type: "extension_ready",
          fb_uid: currentFbUid,
          loggedIn: Boolean(currentFbUid),
          extensionLiveActionsEnabled: EXTENSION_LIVE_ACTIONS_ENABLED,
          profileId: identity.profileId,
          profileName: identity.profileName,
          url: "",
        }));
      } else {
        connectWS(false);
      }
    }
  });
}

// ─── WebSocket Connection ───────────────────────────────────

let wsConnectingSince = 0;
const CONNECTING_STALE_MS = 8000;

function clearReconnectTimer() {
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
}

function clearPingTimer() {
  if (pingTimer) {
    clearInterval(pingTimer);
    pingTimer = null;
  }
}

/**
 * Close the current socket without queuing a reconnect (used when replacing it).
 */
function disposeSocket(reason) {
  if (!ws) return;
  const socket = ws;
  ws = null;
  wsConnectingSince = 0;
  ignoreCloseCount += 1;
  try {
    if (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING) {
      socket.close(1000, reason);
    } else {
      ignoreCloseCount = Math.max(0, ignoreCloseCount - 1);
    }
  } catch {
    ignoreCloseCount = Math.max(0, ignoreCloseCount - 1);
  }
}

async function connectWS(force = false) {
  if (connectInFlight && !force) return;

  if (ws) {
    const state = ws.readyState;
    if (state === WebSocket.OPEN && !force) return;
    if (state === WebSocket.CONNECTING && !force) {
      if (Date.now() - wsConnectingSince < CONNECTING_STALE_MS) return;
    }
  }

  connectInFlight = true;
  clearReconnectTimer();
  clearPingTimer();
  disposeSocket(force ? "force reconnect" : "stale connecting");

  let socket;
  try {
    const wsUrl = await buildWsUrl();
    wsConnectingSince = Date.now();
    socket = new WebSocket(wsUrl);
    ws = socket;
  } catch (e) {
    console.error("[FBKit] WS create error:", e.message);
    connectInFlight = false;
    scheduleReconnect();
    return;
  }

  socket.onopen = async () => {
    if (ws !== socket) return;
    console.log("[FBKit] Connected to Agent");
    connectInFlight = false;
    clearReconnectTimer();
    reconnectAttempt = 0;
    wsConnectingSince = 0;

    const fbUid = await getFbUid(true);
    const profileIdentity = await getProfileIdentity();
    if (ws !== socket || socket.readyState !== WebSocket.OPEN) return;
    socket.send(JSON.stringify({
      type: "extension_ready",
      fb_uid: fbUid,
      loggedIn: !!fbUid,
      extensionLiveActionsEnabled: EXTENSION_LIVE_ACTIONS_ENABLED,
      profileId: profileIdentity.profileId,
      profileName: profileIdentity.profileName,
      url: "",
    }));

    clearPingTimer();
    pingTimer = setInterval(async () => {
      if (ws !== socket || socket.readyState !== WebSocket.OPEN) return;
      const currentFbUid = await getFbUid();
      const identity = await getProfileIdentity();
      if (ws !== socket || socket.readyState !== WebSocket.OPEN) return;
      socket.send(JSON.stringify({
        type: "ping",
        fb_uid: currentFbUid,
        loggedIn: !!currentFbUid,
        extensionLiveActionsEnabled: EXTENSION_LIVE_ACTIONS_ENABLED,
        profileId: identity.profileId,
        profileName: identity.profileName,
      }));
    }, PING_INTERVAL_MS);
  };

  socket.onmessage = async (event) => {
    if (ws !== socket) return;
    let data;
    try {
      data = JSON.parse(event.data);
    } catch {
      return;
    }
    if (data.type === "pong") return;
    if (data.id && data.method) {
      const result = await dispatchToContentScript(data);
      if (ws === socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ id: data.id, ...result }));
      }
    }
  };

  socket.onclose = () => {
    if (ignoreCloseCount > 0) {
      ignoreCloseCount -= 1;
      if (ws === socket) {
        ws = null;
        wsConnectingSince = 0;
        clearPingTimer();
      }
      return;
    }
    if (ws === socket) {
      ws = null;
      wsConnectingSince = 0;
      clearPingTimer();
    }
    connectInFlight = false;
    console.log("[FBKit] Disconnected from Agent");
    scheduleReconnect();
  };

  socket.onerror = () => {
    // onclose follows; avoid double scheduleReconnect here
    console.error("[FBKit] WS error");
  };
}

function scheduleReconnect() {
  if (reconnectTimer) return;
  reconnectAttempt += 1;
  const exp = Math.min(
    RECONNECT_MAX_MS,
    RECONNECT_BASE_MS * (2 ** Math.min(reconnectAttempt - 1, 5)),
  );
  const delay = exp + Math.floor(Math.random() * RECONNECT_JITTER_MS);
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    connectWS(false);
  }, delay);
}

// ─── Command Dispatcher ─────────────────────────────────────

async function dispatchToContentScript(command) {
  const { method, params } = command;

  try {
    if (params?.expectedFbUid) {
      const currentFbUid = await getFbUid();
      if (currentFbUid !== params.expectedFbUid) {
        return {
          error: "Facebook account changed before dispatch",
          expectedFbUid: params.expectedFbUid,
          currentFbUid,
        };
      }
    }

    // Find a Facebook tab
    const tabs = await chrome.tabs.query({
      url: ["https://www.facebook.com/*", "https://web.facebook.com/*"],
    });

    if (tabs.length === 0) {
      return { error: "No Facebook tab open" };
    }

    const tab = tabs[0];

    // For navigation commands, handle in background
    if (method === "navigate") {
      await chrome.tabs.update(tab.id, { url: params.url });
      // Wait for page load
      await new Promise(resolve => setTimeout(resolve, 3000));
      return { success: true };
    }

    // For check_login, use simple script injection
    if (method === "check_login") {
      const results = await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: () => {
          const loggedIn = !!document.querySelector('[aria-label="Your profile"]')
            || !!document.querySelector('[aria-label="Account"]')
            || !!document.querySelector('[aria-label="Tài khoản"]')
            || !!document.querySelector('[aria-label="Trang cá nhân của bạn"]')
            || !!document.querySelector('[aria-label="Menu tài khoản"]')
            || !!document.querySelector('[data-pagelet="ProfileBrowser"]')
            || !!document.querySelector('[role="banner"] [role="button"] img[alt]');
          return {
            loggedIn,
            url: window.location.href,
            title: document.title,
          };
        },
      });
      return results[0]?.result || { error: "Script execution failed" };
    }

    // Send message to content script for DOM-based actions
    const response = await chrome.tabs.sendMessage(tab.id, {
      method,
      params,
    });

    return response || { error: "No response from content script" };

  } catch (e) {
    return { error: `Dispatch failed: ${e.message}` };
  }
}

// ─── Human-like Telemetry ───────────────────────────────────
// Keep session alive — periodically update session storage
// to mimic an active user (prevents Facebook from detecting
// inactive extension behavior).

chrome.alarms.create("telemetry", { periodInMinutes: 5 });
// MV3 service workers sleep; wake + ensure agent WS at least every minute.
chrome.alarms.create("ws-keepalive", { periodInMinutes: 1 });

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "telemetry") {
    chrome.storage.session.set({
      lastActivity: Date.now(),
      sessionId: `fbkit_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
    });
  }
  if (alarm.name === "ws-keepalive" || alarm.name === "telemetry") {
    connectWS(false);
  }
});

// ─── Lifecycle ──────────────────────────────────────────────

// Connect on install/startup
chrome.runtime.onInstalled.addListener(() => {
  console.log("[FBKit] Installed");
  connectWS();
});

chrome.runtime.onStartup.addListener(() => {
  connectWS();
});

// Unpacked MV3 service workers can start without firing install/startup events
// during local demo relaunches, so connect when the worker script is evaluated.
connectWS();

chrome.storage.onChanged.addListener((changes, area) => {
  if (area !== "local" || !changes.fbkitApiKey) return;
  if (ws && ws.readyState === 1) {
    ws.close(1000, "API key changed");
  } else {
    connectWS();
  }
});

// Listen for messages from content script (safety telemetry / debugger).
let lastPageStateWireKey = "";

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.action === "reconnect_agent") {
    connectWS(true);
    sendResponse({ ok: true });
    return true;
  }

  if (message.type === "page_state") {
    // Content-script traffic wakes the SW — ensure WS is up before drop.
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      connectWS(false);
    }
    if (ws && ws.readyState === WebSocket.OPEN) {
      getFbUid().then((fbUid) => {
        const payload = {
          type: "page_state",
          fb_uid: fbUid,
          loggedIn: Boolean(message.loggedIn),
          checkpointWarning: Boolean(message.checkpointWarning),
          loginWarning: Boolean(message.loginWarning),
          url: String(message.url || ""),
        };
        const key = [payload.fb_uid, payload.loggedIn, payload.checkpointWarning, payload.loginWarning, payload.url].join("|");
        if (key === lastPageStateWireKey) return;
        lastPageStateWireKey = key;
        ws.send(JSON.stringify(payload));
      }).catch(() => {});
    }
    return false;
  }

  if (message.action === "set_file_input") {
    const tabId = sender.tab.id;
    const { selector, filePaths } = message;

    // Attach debugger and set file input
    (async () => {
      try {
        await chrome.debugger.attach({ tabId: tabId }, "1.3");

        // Find the node using Runtime.evaluate and DOM.requestNode
        const evalResult = await chrome.debugger.sendCommand({ tabId: tabId }, "Runtime.evaluate", {
          expression: `document.querySelector('${selector}')`
        });

        if (!evalResult.result || evalResult.result.subtype === "null") {
          throw new Error("File input not found");
        }

        const nodeResult = await chrome.debugger.sendCommand({ tabId: tabId }, "DOM.requestNode", {
          objectId: evalResult.result.objectId
        });

        // Set the file paths
        await chrome.debugger.sendCommand({ tabId: tabId }, "DOM.setFileInputFiles", {
          nodeId: nodeResult.nodeId,
          files: filePaths
        });

        await chrome.debugger.detach({ tabId: tabId });
        sendResponse({ success: true });
      } catch (err) {
        console.error("Debugger error:", err);
        try { await chrome.debugger.detach({ tabId: tabId }); } catch (e) {}
        sendResponse({ error: err.message });
      }
    })();
    return true; // Keep message channel open for async response
  }
});

// ─── Content Script Keepalive Port ──────────────────────────
chrome.runtime.onConnect.addListener((port) => {
  if (port.name === "fbkit_keepalive") {
    // Content script on Facebook tab is active — ensure agent WS is healthy
    connectWS(false);
  }
});

// ─── Facebook Tab Navigation / Switch Listeners ─────────────
if (chrome.tabs?.onActivated) {
  chrome.tabs.onActivated.addListener(async (activeInfo) => {
    try {
      const tab = await chrome.tabs.get(activeInfo.tabId);
      if (tab?.url && /facebook\.com/i.test(tab.url)) {
        connectWS(false);
      }
    } catch {
      /* tab might have closed */
    }
  });
}

if (chrome.tabs?.onUpdated) {
  chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
    if (changeInfo.status === "complete" && tab.url && /facebook\.com/i.test(tab.url)) {
      connectWS(false);
    }
  });
}

// Reconnect on service worker activation
connectWS();
