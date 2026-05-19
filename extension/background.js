/**
 * FBKit — Background Service Worker (Chrome MV3)
 *
 * Maintains persistent WebSocket connection to FBKit Agent.
 * Dispatches commands from Agent → content scripts on facebook.com tabs.
 * Relays results back to Agent.
 */

const WS_BASE_URL = "ws://127.0.0.1:9222";
const AGENT_API = "http://127.0.0.1:8100";
const RECONNECT_DELAY_MS = 3000;
const RECONNECT_JITTER_MS = 2000;
const PING_INTERVAL_MS = 25000;
const EXTENSION_LIVE_ACTIONS_ENABLED = false;

let ws = null;
let pingTimer = null;
let reconnectTimer = null;
let reconnectAttempt = 0;

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
async function getFbUid() {
  try {
    const cookie = await chrome.cookies.get({
      url: "https://www.facebook.com",
      name: "c_user",
    });
    return cookie ? cookie.value : null;
  } catch {
    return null;
  }
}

// ─── WebSocket Connection ───────────────────────────────────

async function connectWS() {
  if (ws && ws.readyState <= 1) return;

  try {
    const wsUrl = await buildWsUrl();
    ws = new WebSocket(wsUrl);
  } catch (e) {
    console.error("[FBKit] WS create error:", e.message);
    scheduleReconnect();
    return;
  }

  ws.onopen = async () => {
    console.log("[FBKit] Connected to Agent");
    clearTimeout(reconnectTimer);
    reconnectAttempt = 0;

    // Announce ourselves with FB UID (from c_user cookie)
    const fbUid = await getFbUid();
    const profileIdentity = await getProfileIdentity();
    ws.send(JSON.stringify({
      type: "extension_ready",
      fb_uid: fbUid,
      loggedIn: !!fbUid,
      extensionLiveActionsEnabled: EXTENSION_LIVE_ACTIONS_ENABLED,
      profileId: profileIdentity.profileId,
      profileName: profileIdentity.profileName,
      url: "",
    }));

    // Start ping keepalive
    clearInterval(pingTimer);
    pingTimer = setInterval(async () => {
      if (ws && ws.readyState === 1) {
        const currentFbUid = await getFbUid();
        ws.send(JSON.stringify({
          type: "ping",
          fb_uid: currentFbUid,
          loggedIn: !!currentFbUid,
          extensionLiveActionsEnabled: EXTENSION_LIVE_ACTIONS_ENABLED,
          profileId: profileIdentity.profileId,
          profileName: profileIdentity.profileName,
        }));
      }
    }, PING_INTERVAL_MS);
  };

  ws.onmessage = async (event) => {
    let data;
    try {
      data = JSON.parse(event.data);
    } catch {
      return;
    }

    // Handle pong (keepalive response)
    if (data.type === "pong") return;

    // Dispatch command to content script
    if (data.id && data.method) {
      const result = await dispatchToContentScript(data);
      ws.send(JSON.stringify({
        id: data.id,
        ...result,
      }));
    }
  };

  ws.onclose = () => {
    console.log("[FBKit] Disconnected from Agent");
    clearInterval(pingTimer);
    ws = null;
    scheduleReconnect();
  };

  ws.onerror = (e) => {
    console.error("[FBKit] WS error:", e.message || "unknown");
  };
}

function scheduleReconnect() {
  clearTimeout(reconnectTimer);
  reconnectAttempt += 1;
  const jitter = Math.floor(Math.random() * RECONNECT_JITTER_MS);
  const delay = RECONNECT_DELAY_MS + jitter + Math.min(reconnectAttempt * 500, 5000);
  reconnectTimer = setTimeout(connectWS, delay);
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
            || !!document.querySelector('[data-pagelet="ProfileBrowser"]');
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

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "telemetry") {
    chrome.storage.session.set({
      lastActivity: Date.now(),
      sessionId: `fbkit_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
    });
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

// Listen for messages from content script (e.g. to use debugger)
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
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

// Reconnect on service worker activation
connectWS();
