/**
 * FBKit — Popup Script
 * Fetches status from Agent API and updates the popup UI.
 */

const AGENT_API = "http://127.0.0.1:8100";

async function getApiHeaders() {
  const data = await chrome.storage.local.get(["fbkitApiKey"]);
  const apiKey = (data.fbkitApiKey || "").trim();
  if (!apiKey) {
    return {};
  }
  return {
    "X-API-Key": apiKey,
  };
}

async function checkStatus() {
  const agentEl = document.getElementById("agent-status");
  const fbEl = document.getElementById("fb-status");
  const taskEl = document.getElementById("task-count");
  const safetyEl = document.getElementById("safety-mode");
  const errorEl = document.getElementById("error");

  errorEl.style.display = "none";

  try {
    // Check Agent API
    const headers = await getApiHeaders();
    const res = await fetch(`${AGENT_API}/api/status`, {
      signal: AbortSignal.timeout(3000),
      headers,
    });
    const data = await res.json();

    // Agent status
    if (data.extension?.connected) {
      agentEl.innerHTML = '<span class="dot green"></span>Connected';
    } else {
      agentEl.innerHTML = '<span class="dot yellow"></span>No Extension';
    }

    // Safety mode
    if (safetyEl) {
      const isLive = data.live_actions_enabled || data.live_guard?.enabled;
      if (isLive) {
        safetyEl.innerHTML = '<span class="dot yellow"></span>Live Mode (Armed)';
      } else {
        safetyEl.innerHTML = '<span class="dot green"></span>Dry-Run (100% Safe)';
      }
    }

    // Session status
    const session = data.session || {};
    if (session.state === "break") {
      taskEl.textContent = `Break (${Math.ceil(session.remaining_s / 60)}m)`;
    } else {
      // Get pending tasks count
      try {
        const taskRes = await fetch(`${AGENT_API}/api/tasks/pending/count`, {
          signal: AbortSignal.timeout(3000),
          headers,
        });
        const taskData = await taskRes.json();
        taskEl.textContent = `${taskData.count || 0} pending`;
      } catch {
        taskEl.textContent = "—";
      }
    }

    // Check FB login via content script
    const tabs = await chrome.tabs.query({
      url: ["https://www.facebook.com/*", "https://web.facebook.com/*"],
      active: true,
    });

    const agentLoggedIn = data.extension?.sessions?.some((s) => s.logged_in && s.fb_uid);

    if (tabs.length > 0) {
      try {
        const fbState = await chrome.tabs.sendMessage(tabs[0].id, {
          method: "get_page_state",
          params: {},
        });
        if (fbState?.data?.loggedIn || agentLoggedIn) {
          fbEl.innerHTML = '<span class="dot green"></span>Logged In';
        } else {
          fbEl.innerHTML = '<span class="dot red"></span>Not Logged In';
        }
      } catch {
        if (agentLoggedIn) {
          fbEl.innerHTML = '<span class="dot green"></span>Logged In';
        } else {
          fbEl.innerHTML = '<span class="dot yellow"></span>No Content Script';
        }
      }
    } else {
      if (agentLoggedIn) {
        fbEl.innerHTML = '<span class="dot green"></span>Logged In';
      } else {
        fbEl.innerHTML = '<span class="dot yellow"></span>No FB Tab';
      }
    }

  } catch (e) {
    agentEl.innerHTML = '<span class="dot red"></span>Offline';
    fbEl.innerHTML = '<span class="dot yellow"></span>Unknown';
    taskEl.textContent = "—";
    errorEl.textContent = `Agent unreachable: ${e.message}`;
    errorEl.style.display = "block";
  }
}

// Button handlers
document.getElementById("btn-check").addEventListener("click", async () => {
  try {
    await chrome.runtime.sendMessage({ action: "reconnect_agent" });
  } catch {
    /* SW may still be waking */
  }
  await checkStatus();
});

document.getElementById("btn-dashboard").addEventListener("click", () => {
  chrome.tabs.create({ url: `${AGENT_API}/docs` });
});

// Auto-check on popup open — nudge SW reconnect first (MV3 idle).
(async () => {
  try {
    await chrome.runtime.sendMessage({ action: "reconnect_agent" });
  } catch {
    /* ignore */
  }
  await checkStatus();
  // Auto-refresh popup status while open
  setInterval(checkStatus, 3000);
})();
