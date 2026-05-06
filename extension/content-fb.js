/**
 * FBKit — Content Script for facebook.com
 *
 * Injected automatically on facebook.com pages.
 * Handles DOM-based automation commands from background.js:
 *   - Post creation (text, image, video)
 *   - Messaging
 *   - Like, Comment, Share
 *   - Friend requests
 *   - Group actions
 *   - Profile scraping
 *
 * All actions simulate human-like interactions with random delays.
 */

// ─── Utility Helpers ────────────────────────────────────────

const EXTENSION_LIVE_ACTIONS_ENABLED = false;
// Keep every mutating router method here so live-disabled mode blocks before handler dispatch.
const MUTATING_METHODS = new Set([
  "post_text",
  "post_with_media",
  "send_message",
  "like_post",
  "comment_post",
  "share_post",
  "add_friend",
  "accept_friend",
  "join_group",
  "leave_group",
  "follow_page",
  "unfollow_page",
]);

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function randomDelay(minMs = 500, maxMs = 2000) {
  const delay = Math.floor(Math.random() * (maxMs - minMs) + minMs);
  return sleep(delay);
}

/**
 * Type text into an element character by character (human-like).
 */
async function humanType(element, text) {
  element.focus();
  await randomDelay(200, 500);

  for (const char of text) {
    // Simulate native input event
    const inputEvent = new InputEvent("input", {
      bubbles: true,
      cancelable: true,
      inputType: "insertText",
      data: char,
    });

    // For contentEditable elements (Facebook uses these)
    if (element.isContentEditable) {
      document.execCommand("insertText", false, char);
    } else {
      element.value += char;
      element.dispatchEvent(inputEvent);
    }

    // Random delay per character (40-150ms)
    const charDelay = Math.floor(Math.random() * 110 + 40);
    await sleep(charDelay);
  }

  // Dispatch change event after typing
  element.dispatchEvent(new Event("change", { bubbles: true }));
}

/**
 * Click an element with a slight delay (simulates mouse movement).
 */
async function humanClick(element) {
  await randomDelay(100, 400);
  element.scrollIntoView({ behavior: "smooth", block: "center" });
  await randomDelay(200, 600);
  element.click();
}

/**
 * Find an element by various selectors with retry.
 */
async function waitForElement(selectors, timeout = 10000) {
  const selectorList = Array.isArray(selectors) ? selectors : [selectors];
  const start = Date.now();

  while (Date.now() - start < timeout) {
    for (const selector of selectorList) {
      if (selector.startsWith("text=")) {
        const text = selector.substring(5);
        const el = findElementByText(text);
        if (el) return el;
      } else {
        const el = document.querySelector(selector);
        if (el) return el;
      }
    }
    await sleep(500);
  }
  return null;
}

/**
 * Find element containing specific text.
 */
function findElementByText(text, tag = "*") {
  const elements = document.querySelectorAll(tag);
  for (const el of elements) {
    if (el.textContent.trim().includes(text) && el.offsetParent !== null) {
      return el;
    }
  }
  return null;
}

/**
 * Resolve selectors: if strategy hints exist, prepend them before defaults.
 * This allows learned selectors to be tried first (faster, more reliable),
 * while keeping hardcoded selectors as fallback.
 *
 * @param {string[]} defaults - Hardcoded selector list
 * @param {Object} strategySelectors - Map of selectorKey → CSS selector from strategy
 * @returns {string[]} Merged selector list (strategy first, then defaults, deduped)
 */
function resolveSelectors(defaults, strategySelectors) {
  if (!strategySelectors || typeof strategySelectors !== 'object') {
    return defaults;
  }
  // Extract all strategy selector values
  const strategyValues = Object.values(strategySelectors).filter(s => typeof s === 'string');
  // Merge: strategy first, then defaults (deduped)
  const seen = new Set();
  const merged = [];
  for (const s of [...strategyValues, ...defaults]) {
    if (!seen.has(s)) {
      seen.add(s);
      merged.push(s);
    }
  }
  return merged;
}

function isDryRun(params) {
  return params?.dryRun === true || params?.dryRun === "true";
}

function shouldForceExtensionDryRun(params) {
  return !EXTENSION_LIVE_ACTIONS_ENABLED && !isDryRun(params);
}

function dryRunResult(action, details = {}) {
  const element = details.element || null;
  return {
    success: true,
    dryRun: true,
    action,
    message: `Dry run: would perform ${action}`,
    wouldClick: details.wouldClick || false,
    elementFound: Boolean(element || details.elementFound),
    selectorUsed: details.selectorUsed || null,
    safetyReason: details.safetyReason || null,
    url: window.location.href,
  };
}

function extensionSafetyDryRunResult(action, details = {}) {
  return dryRunResult(action, {
    ...details,
    safetyReason: "extension_live_actions_disabled",
  });
}

// ─── Command Handlers ───────────────────────────────────────

/**
 * Post text content to timeline or group.
 */
async function handlePostText(params) {
  const { content, targetType, targetId, _strategy } = params;
  const stSelectors = _strategy?.selectors;

  if (isDryRun(params)) {
    return dryRunResult("post_text", {
      wouldClick: "composer and post button",
      selectorUsed: "post composer",
    });
  }

  if (shouldForceExtensionDryRun(params)) {
    return extensionSafetyDryRunResult("post_text", {
      wouldClick: "composer and post button",
      selectorUsed: "post composer",
    });
  }

  try {
    // Navigate to target if needed
    if (targetType === "GROUP" && targetId) {
      window.location.href = `https://www.facebook.com/groups/${targetId}`;
      await sleep(3000);
    }

    // Click the composer ("What's on your mind?")
    const composerSelectors = resolveSelectors([
      '[aria-label="Create a post"]',
      '[aria-label="What\'s on your mind?"]',
      '[name="xhpc_message_text"]',
      'div[role="button"][tabindex="0"]',
    ], stSelectors);

    const composer = await waitForElement(composerSelectors, 10000);

    if (!composer) {
      return { error: "Could not find post composer" };
    }

    if (isDryRun(params)) {
      return dryRunResult("post_text", {
        element: composer,
        wouldClick: "composer",
        selectorUsed: "post composer",
      });
    }

    await humanClick(composer);
    await randomDelay(1000, 2000);

    // Wait for the expanded composer/dialog
    const textAreaSelectors = resolveSelectors([
      'div[contenteditable="true"][role="textbox"]',
      'div[aria-label="What\'s on your mind?"][contenteditable="true"]',
      'div[data-lexical-editor="true"]',
    ], stSelectors);

    const textArea = await waitForElement(textAreaSelectors, 8000);

    if (!textArea) {
      return { error: "Could not find text input in composer" };
    }

    // Type the content
    await humanType(textArea, content);
    await randomDelay(1000, 3000);

    // Click Post button
    const postBtnSelectors = resolveSelectors([
      'div[aria-label="Post"]',
      'div[aria-label="Đăng"]',
      'span:has-text("Post")',
    ], stSelectors);

    const postBtn = await waitForElement(postBtnSelectors, 5000);

    // Fallback: find by text
    const submitBtn = postBtn || findElementByText("Post", "div[role='button']")
                               || findElementByText("Đăng", "div[role='button']");

    if (!submitBtn) {
      return { error: "Could not find Post button" };
    }

    await humanClick(submitBtn);
    await randomDelay(2000, 4000);

    return { success: true, message: "Post created" };

  } catch (e) {
    return { error: `Post failed: ${e.message}` };
  }
}

/**
 * Send a message via Facebook Messenger.
 */
async function handleSendMessage(params) {
  const { recipientName, recipientUid, content } = params;

  if (isDryRun(params)) {
    return dryRunResult("send_message", {
      wouldClick: "message input and Enter send",
      selectorUsed: "messenger message input",
    });
  }

  if (shouldForceExtensionDryRun(params)) {
    return extensionSafetyDryRunResult("send_message", {
      wouldClick: "message input and Enter send",
      selectorUsed: "messenger message input",
    });
  }

  try {
    // Navigate to Messenger
    if (recipientUid) {
      window.location.href = `https://www.facebook.com/messages/t/${recipientUid}`;
    } else {
      window.location.href = "https://www.facebook.com/messages/new";
    }
    await sleep(3000);

    // If no uid, search for recipient
    if (!recipientUid && recipientName) {
      const searchInput = await waitForElement([
        'input[aria-label="To"]',
        'input[placeholder="To"]',
        'input[type="text"]',
      ], 8000);

      if (searchInput) {
        if (isDryRun(params)) {
          return dryRunResult("send_message", {
            element: searchInput,
            wouldClick: "recipient search",
            selectorUsed: "messenger recipient search",
          });
        }

        await humanType(searchInput, recipientName);
        await randomDelay(1500, 3000);

        // Click first suggestion
        const suggestion = await waitForElement([
          'ul[role="listbox"] li',
          'div[role="option"]',
        ], 5000);

        if (suggestion) {
          await humanClick(suggestion);
          await randomDelay(1000, 2000);
        }
      }
    }

    // Type message
    const msgInput = await waitForElement([
      'div[aria-label="Message"][contenteditable="true"]',
      'div[role="textbox"][contenteditable="true"]',
      'div[aria-label="Aa"][contenteditable="true"]',
    ], 8000);

    if (!msgInput) {
      return { error: "Could not find message input" };
    }

    if (isDryRun(params)) {
      return dryRunResult("send_message", {
        element: msgInput,
        wouldClick: "message input and Enter send",
        selectorUsed: "messenger message input",
      });
    }

    await humanType(msgInput, content);
    await randomDelay(500, 1500);

    // Press Enter to send
    msgInput.dispatchEvent(new KeyboardEvent("keydown", {
      key: "Enter", code: "Enter", keyCode: 13, bubbles: true,
    }));

    await randomDelay(1000, 2000);

    return { success: true, message: "Message sent" };

  } catch (e) {
    return { error: `Message failed: ${e.message}` };
  }
}

/**
 * Like/React to a post.
 */
async function handleLikePost(params) {
  const { postUrl, reaction, _strategy } = params;
  const stSelectors = _strategy?.selectors;

  if (isDryRun(params)) {
    return dryRunResult("like_post", {
      wouldClick: reaction && reaction !== 'LIKE' ? "reaction button" : "like button",
      selectorUsed: "post like button",
    });
  }

  if (shouldForceExtensionDryRun(params)) {
    return extensionSafetyDryRunResult("like_post", {
      wouldClick: reaction && reaction !== 'LIKE' ? "reaction button" : "like button",
      selectorUsed: "post like button",
    });
  }

  try {
    if (postUrl) {
      window.location.href = postUrl;
      await sleep(3500);
    }

    // FB 2024: like button has aria-label + aria-pressed="false"
    const likeSelectors = resolveSelectors([
      'div[aria-label="Like"][aria-pressed]',
      'div[aria-label="Thích"][aria-pressed]',
      'div[aria-label="Like"]',
      'div[aria-label="Thích"]',
      'div[data-testid="like_def"]',
      '[data-reaction-type]',
    ], stSelectors);

    const likeBtn = await waitForElement(likeSelectors, 10000);

    if (!likeBtn) {
      return { error: "Could not find Like button — post may not be loaded" };
    }

    // Check already liked (aria-pressed="true") — skip if so
    if (likeBtn.getAttribute('aria-pressed') === 'true') {
      return { success: true, message: "Already reacted" };
    }

    if (isDryRun(params)) {
      return dryRunResult("like_post", {
        element: likeBtn,
        wouldClick: reaction && reaction !== 'LIKE' ? "reaction button" : "like button",
        selectorUsed: "post like button",
      });
    }

    const REACTION_LABEL_MAP = {
      LOVE: ['Love', 'Yêu thích'],
      HAHA: ['Haha'],
      WOW: ['Wow'],
      SAD: ['Sad', 'Buồn'],
      ANGRY: ['Angry', 'Phẫn nộ'],
    };

    if (reaction && reaction !== 'LIKE') {
      // Hold hover to reveal reaction bar
      likeBtn.dispatchEvent(new MouseEvent('mouseenter', { bubbles: true }));
      likeBtn.dispatchEvent(new MouseEvent('mouseover', { bubbles: true }));
      await randomDelay(1500, 2500);

      const labels = REACTION_LABEL_MAP[reaction] || [reaction];
      let reactionBtn = null;
      for (const label of labels) {
        reactionBtn = await waitForElement(
          [`div[aria-label="${label}"]`, `span[aria-label="${label}"]`], 2000
        );
        if (reactionBtn) break;
      }

      if (reactionBtn) {
        await humanClick(reactionBtn);
      } else {
        // Fallback to plain Like
        await humanClick(likeBtn);
      }
    } else {
      await humanClick(likeBtn);
    }

    await randomDelay(800, 2000);
    return { success: true, message: `Reacted: ${reaction || 'LIKE'}` };

  } catch (e) {
    return { error: `Like failed: ${e.message}` };
  }
}

/**
 * Comment on a post.
 */
async function handleCommentPost(params) {
  const { postUrl, comment, _strategy } = params;
  const stSelectors = _strategy?.selectors;

  if (isDryRun(params)) {
    return dryRunResult("comment_post", {
      wouldClick: "comment input and Enter submit",
      selectorUsed: "comment input",
    });
  }

  if (shouldForceExtensionDryRun(params)) {
    return extensionSafetyDryRunResult("comment_post", {
      wouldClick: "comment input and Enter submit",
      selectorUsed: "comment input",
    });
  }

  try {
    if (postUrl) {
      window.location.href = postUrl;
      await sleep(3500);
    }

    // Click Comment button to expand section (FB 2024 uses span > div[role=button])
    const triggerSelectors = resolveSelectors([
      'div[aria-label="Leave a comment"]',
      'div[aria-label="Để lại bình luận"]',
    ], stSelectors);

    const commentTrigger = await waitForElement(triggerSelectors, 3000) ||
      findElementByText('Comment', 'div[role="button"]') ||
      findElementByText('Bình luận', 'div[role="button"]');

    if (commentTrigger) {
      if (isDryRun(params)) {
        return dryRunResult("comment_post", {
          element: commentTrigger,
          wouldClick: "comment trigger",
          selectorUsed: "comment trigger",
        });
      }

      await humanClick(commentTrigger);
      await randomDelay(800, 1500);
    }

    // FB 2024 comment box selectors
    const inputSelectors = resolveSelectors([
      'div[aria-label="Write a comment"][contenteditable="true"]',
      'div[aria-label="Write a comment…"][contenteditable="true"]',
      'div[aria-label="Viết bình luận"][contenteditable="true"]',
      'div[aria-label="Viết bình luận…"][contenteditable="true"]',
      'div[data-lexical-editor="true"][contenteditable="true"]',
      'div[contenteditable="true"][role="textbox"]',
    ], stSelectors);

    const commentInput = await waitForElement(inputSelectors, 10000);

    if (!commentInput) {
      return { error: "Could not find comment input" };
    }

    if (isDryRun(params)) {
      return dryRunResult("comment_post", {
        element: commentInput,
        wouldClick: "comment input and Enter submit",
        selectorUsed: "comment input",
      });
    }

    await humanClick(commentInput);
    await randomDelay(300, 700);
    await humanType(commentInput, comment);
    await randomDelay(600, 1500);

    // Press Enter to submit
    commentInput.dispatchEvent(new KeyboardEvent('keydown', {
      key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true, cancelable: true,
    }));

    await randomDelay(1200, 2500);
    return { success: true, message: 'Comment posted' };

  } catch (e) {
    return { error: `Comment failed: ${e.message}` };
  }
}

/**
 * Send friend request.
 */
async function handleAddFriend(params) {
  const { profileUrl } = params;

  if (isDryRun(params)) {
    return dryRunResult("add_friend", {
      wouldClick: "add friend button",
      selectorUsed: "add friend button",
    });
  }

  if (shouldForceExtensionDryRun(params)) {
    return extensionSafetyDryRunResult("add_friend", {
      wouldClick: "add friend button",
      selectorUsed: "add friend button",
    });
  }

  try {
    if (profileUrl) {
      window.location.href = profileUrl;
      await sleep(3000);
    }

    const addBtn = await waitForElement([
      'div[aria-label="Add friend"]',
      'div[aria-label="Add Friend"]',
      'div[aria-label="Thêm bạn bè"]',
      'div[aria-label="Kết bạn"]',
    ], 8000);

    if (!addBtn) {
      return { error: "Could not find Add Friend button" };
    }

    if (isDryRun(params)) {
      return dryRunResult("add_friend", {
        element: addBtn,
        wouldClick: "add friend button",
        selectorUsed: "add friend button",
      });
    }

    await humanClick(addBtn);
    await randomDelay(1000, 2000);

    return { success: true, message: "Friend request sent" };

  } catch (e) {
    return { error: `Add friend failed: ${e.message}` };
  }
}

/**
 * Scrape basic profile info.
 */
async function handleScrapeProfile(params) {
  const { profileUrl } = params;

  try {
    if (profileUrl) {
      window.location.href = profileUrl;
      await sleep(3000);
    }

    const name = document.querySelector('h1')?.textContent?.trim() || "";
    const bio = document.querySelector('[data-pagelet="ProfileTilesBio"]')?.textContent?.trim() || "";

    return {
      success: true,
      data: {
        name,
        bio,
        url: window.location.href,
      },
    };

  } catch (e) {
    return { error: `Scrape failed: ${e.message}` };
  }
}

/**
 * Get current page state.
 */
function handleGetPageState() {
  const loggedIn = !!document.querySelector('[aria-label="Your profile"]')
                || !!document.querySelector('[aria-label="Account"]');
  return {
    success: true,
    data: {
      loggedIn,
      url: window.location.href,
      title: document.title,
    },
  };
}

/**
 * Post with Media (Images/Videos/Reels).
 * Supports TIMELINE, GROUP, PAGE, and REEL targets.
 */
async function handlePostWithMedia(params) {
  const { content, mediaPaths, targetType, targetId } = params;

  if (isDryRun(params)) {
    return dryRunResult("post_with_media", {
      wouldClick: targetType === 'REEL' ? "reel file upload and publish" : "composer and media upload",
      selectorUsed: targetType === 'REEL' ? "reel file input" : "media post composer",
    });
  }

  if (shouldForceExtensionDryRun(params)) {
    return extensionSafetyDryRunResult("post_with_media", {
      wouldClick: targetType === 'REEL' ? "reel file upload and publish" : "composer and media upload",
      selectorUsed: targetType === 'REEL' ? "reel file input" : "media post composer",
    });
  }

  try {
    // ─── REEL Upload Flow ──────────────────────────────────
    if (targetType === 'REEL') {
      // Strategy 1: use /reels/create direct URL (works for personal profiles & pages)
      // Strategy 2: navigate to page then click Create Reel button
      const reelsCreateUrl = targetId
        ? `https://www.facebook.com/reels/create?source_ref=profile_reels&actor_id=${targetId}`
        : 'https://www.facebook.com/reels/create';

      window.location.href = reelsCreateUrl;
      await sleep(5000);

      // If redirect didn't land on creator, try finding the button
      if (!window.location.href.includes('reels/create') && !window.location.href.includes('reel')) {
        if (targetId) {
          window.location.href = `https://www.facebook.com/${targetId}`;
          await sleep(4000);
        }

        const reelBtn = await waitForElement([
          'div[aria-label="Create a Reel"]',
          'div[aria-label="Create reel"]',
          'div[aria-label="Tạo thước phim"]',
          'div[aria-label="Thước phim"]',
        ], 8000) ||
          findElementByText('Reel', 'div[role="button"]') ||
          findElementByText('Thước phim', 'div[role="button"]');

        if (!reelBtn) {
          return { error: 'Could not find Reel creation button' };
        }

        if (isDryRun(params)) {
          return dryRunResult("post_with_media", {
            element: reelBtn,
            wouldClick: "create reel button",
            selectorUsed: "create reel button",
          });
        }

        await humanClick(reelBtn);
        await sleep(4000);
      }

      // Find file input (Reels creator shows an upload area)
      const fileInput = await waitForElement([
        'input[type="file"][accept*="video"]',
        'input[type="file"][accept*="mp4"]',
        'input[type="file"]',
      ], 12000);

      if (!fileInput) {
        return { error: 'Could not find file input for Reel upload' };
      }

      if (isDryRun(params)) {
        return dryRunResult("post_with_media", {
          element: fileInput,
          wouldClick: "reel file upload and publish",
          selectorUsed: "reel file input",
        });
      }

      fileInput.id = 'fbkit-reel-input';

      const setFileResult = await new Promise((resolve) => {
        chrome.runtime.sendMessage({
          action: 'set_file_input',
          selector: '#fbkit-reel-input',
          filePaths: mediaPaths,
        }, resolve);
      });

      if (setFileResult && setFileResult.error) {
        return { error: `Failed to set reel file: ${setFileResult.error}` };
      }

      // Wait for video to process/upload (progress bar)
      await sleep(12000);

      // Add description
      if (content) {
        const textArea = await waitForElement([
          'div[contenteditable="true"][role="textbox"]',
          'div[data-lexical-editor="true"][contenteditable="true"]',
          'textarea[placeholder]',
        ], 10000);
        if (textArea) {
          await humanClick(textArea);
          await humanType(textArea, content);
          await sleep(1500);
        }
      }

      // Next (some flows have a Next step)
      const nextBtn = await waitForElement([
        'div[aria-label="Next"]',
        'div[aria-label="Tiếp"]',
      ], 4000);
      if (nextBtn) {
        await humanClick(nextBtn);
        await sleep(3000);
      }

      // Publish
      const publishBtn = await waitForElement([
        'div[aria-label="Publish"]',
        'div[aria-label="Đăng"]',
        'div[aria-label="Share"]',
        'div[aria-label="Chia sẻ"]',
      ], 8000) ||
        findElementByText('Publish', 'div[role="button"]') ||
        findElementByText('Đăng', 'div[role="button"]');

      if (!publishBtn) {
        return { error: 'Could not find Publish button for Reel' };
      }

      await humanClick(publishBtn);
      await sleep(6000);
      return { success: true, message: 'Reel published' };
    }

    // ─── TIMELINE / GROUP / PAGE Upload Flow ──────────────────
    // Navigate to target if needed
    if (targetType === "GROUP" && targetId) {
      window.location.href = `https://www.facebook.com/groups/${targetId}`;
      await sleep(3000);
    } else if (targetType === "PAGE" && targetId) {
      window.location.href = `https://www.facebook.com/${targetId}`;
      await sleep(3000);
    }

    // Click the composer
    const composer = await waitForElement([
      '[aria-label="Create a post"]',
      '[aria-label="What\'s on your mind?"]',
      'div[role="button"][tabindex="0"]',
    ], 10000);

    if (!composer) {
      return { error: "Could not find post composer" };
    }

    if (isDryRun(params)) {
      return dryRunResult("post_with_media", {
        element: composer,
        wouldClick: "composer and media upload",
        selectorUsed: "media post composer",
      });
    }

    await humanClick(composer);
    await randomDelay(1500, 2500);

    // Click "Photo/Video" attachment option
    const photoVideoBtn = await waitForElement([
      'div[aria-label="Photo/video"]',
      'div[aria-label="Photo/Video"]',
      'div[aria-label="Ảnh/video"]',
      'text=Photo/video',
      'text=Ảnh/video',
    ], 5000);

    if (photoVideoBtn) {
      await humanClick(photoVideoBtn);
      await randomDelay(1000, 2000);
    }

    // Find the file input
    const fileInput = await waitForElement([
      'input[type="file"][accept*="image"],input[type="file"][accept*="video"]',
      'input[type="file"]',
    ], 8000);

    if (!fileInput) {
      return { error: "Could not find file input for media upload" };
    }

    fileInput.id = "fbkit-media-input";

    // Use debugger to set files
    const setFileResult = await new Promise((resolve) => {
      chrome.runtime.sendMessage({
        action: "set_file_input",
        selector: "#fbkit-media-input",
        filePaths: mediaPaths
      }, resolve);
    });

    if (setFileResult && setFileResult.error) {
      return { error: `Failed to set media via debugger: ${setFileResult.error}` };
    }

    // Wait for media to process
    await sleep(5000);

    // Type the content/caption
    if (content) {
      const textArea = await waitForElement([
        'div[contenteditable="true"][role="textbox"]',
        'div[aria-label="What\'s on your mind?"][contenteditable="true"]',
        'div[data-lexical-editor="true"]',
      ], 8000);

      if (textArea) {
        await humanType(textArea, content);
        await randomDelay(1000, 2000);
      }
    }

    // Wait for upload indicator to disappear (media processing)
    await sleep(3000);

    // Click Post button
    const postBtn = await waitForElement([
      'div[aria-label="Post"]',
      'div[aria-label="Đăng"]',
    ], 5000);

    const submitBtn = postBtn || findElementByText("Post", "div[role='button']")
                              || findElementByText("Đăng", "div[role='button']");

    if (!submitBtn) {
      return { error: "Could not find Post button" };
    }

    await humanClick(submitBtn);
    await randomDelay(3000, 5000);

    return { success: true, message: `Media post created (${targetType})` };

  } catch (e) {
    return { error: `Post with media failed: ${e.message}` };
  }
}

/**
 * Share a post to timeline or group.
 */
async function handleSharePost(params) {
  const { postUrl, comment, targetType } = params;

  if (isDryRun(params)) {
    return dryRunResult("share_post", {
      wouldClick: "share button",
      selectorUsed: "share button",
    });
  }

  if (shouldForceExtensionDryRun(params)) {
    return extensionSafetyDryRunResult("share_post", {
      wouldClick: "share button",
      selectorUsed: "share button",
    });
  }

  try {
    if (postUrl) {
      window.location.href = postUrl;
      await sleep(3500);
    }

    // FB 2024: Share button label varies by locale and post type
    const shareBtn = await waitForElement([
      'div[aria-label="Share"][role="button"]',
      'div[aria-label="Chia sẻ"][role="button"]',
      'div[aria-label="Send this to friends or post it on your timeline."]',
      'span[aria-label="Share"]',
    ], 10000);

    if (!shareBtn) {
      return { error: "Could not find Share button" };
    }

    if (isDryRun(params)) {
      return dryRunResult("share_post", {
        element: shareBtn,
        wouldClick: "share button",
        selectorUsed: "share button",
      });
    }

    await humanClick(shareBtn);
    await randomDelay(1000, 2000);

    // FB 2024 shows a menu with options
    // Find "Share to Feed" or "Share now"
    const menuItem = await waitForElement([
      'div[role="menuitem"]',
    ], 5000);

    if (!menuItem) {
      return { error: "Share menu did not open" };
    }

    // Choose the right share target
    let targetOption;
    if (targetType === 'GROUP' && params.targetId) {
      // "Share to a Group"
      targetOption = findElementByText('Share to a Group', 'div[role="menuitem"]')
                  || findElementByText('Chia sẻ lên Nhóm', 'div[role="menuitem"]');
    }

    if (!targetOption) {
      // Default: Share to Feed / Share now
      targetOption = findElementByText('Share to Feed', 'div[role="menuitem"]')
                  || findElementByText('Share now', 'div[role="menuitem"]')
                  || findElementByText('Chia sẻ lên Bảng tin', 'div[role="menuitem"]')
                  || findElementByText('Chia sẻ ngay', 'div[role="menuitem"]')
                  || menuItem; // fallback first item
    }

    await humanClick(targetOption);
    await randomDelay(1500, 2500);

    // If dialog opened (Share to Feed), add comment then post
    if (comment) {
      const textArea = await waitForElement([
        'div[contenteditable="true"][role="textbox"]',
        'div[data-lexical-editor="true"][contenteditable="true"]',
      ], 4000);
      if (textArea) {
        await humanClick(textArea);
        await humanType(textArea, comment);
        await randomDelay(800, 1500);
      }
    }

    // Submit
    const postBtn = findElementByText('Post', 'div[role="button"]')
                 || findElementByText('Đăng', 'div[role="button"]')
                 || await waitForElement([
                      'div[aria-label="Post"]',
                      'div[aria-label="Share"]',
                      'div[aria-label="Đăng"]',
                    ], 3000);

    if (postBtn) {
      await humanClick(postBtn);
    }

    await randomDelay(2000, 4000);
    return { success: true, message: 'Post shared' };

  } catch (e) {
    return { error: `Share failed: ${e.message}` };
  }
}

/**
 * Accept a pending friend request.
 */
async function handleAcceptFriend(params) {
  if (isDryRun(params)) {
    return dryRunResult("accept_friend", {
      wouldClick: "confirm friend request button",
      selectorUsed: "friend confirm button",
    });
  }

  if (shouldForceExtensionDryRun(params)) {
    return extensionSafetyDryRunResult("accept_friend", {
      wouldClick: "confirm friend request button",
      selectorUsed: "friend confirm button",
    });
  }

  try {
    // Navigate to friend requests page
    window.location.href = "https://www.facebook.com/friends/requests";
    await sleep(3000);

    // Find "Confirm" or "Accept" button
    const confirmBtn = await waitForElement([
      'div[aria-label="Confirm"]',
      'div[aria-label="Xác nhận"]',
      'text=Confirm',
      'text=Xác nhận',
    ], 8000);

    if (!confirmBtn) {
      return { error: "No pending friend requests found" };
    }

    if (isDryRun(params)) {
      return dryRunResult("accept_friend", {
        element: confirmBtn,
        wouldClick: "confirm friend request button",
        selectorUsed: "friend confirm button",
      });
    }

    await humanClick(confirmBtn);
    await randomDelay(1000, 2000);

    return { success: true, message: "Friend request accepted" };

  } catch (e) {
    return { error: `Accept friend failed: ${e.message}` };
  }
}

/**
 * Join a Facebook group.
 */
async function handleJoinGroup(params) {
  const { groupUrl } = params;

  if (isDryRun(params)) {
    return dryRunResult("join_group", {
      wouldClick: "join group button",
      selectorUsed: "join group button",
    });
  }

  if (shouldForceExtensionDryRun(params)) {
    return extensionSafetyDryRunResult("join_group", {
      wouldClick: "join group button",
      selectorUsed: "join group button",
    });
  }

  try {
    if (groupUrl) {
      window.location.href = groupUrl;
      await sleep(3000);
    }

    const joinBtn = await waitForElement([
      'div[aria-label="Join group"]',
      'div[aria-label="Join Group"]',
      'div[aria-label="Tham gia nhóm"]',
      'text=Join group',
      'text=Tham gia nhóm',
    ], 8000);

    if (!joinBtn) {
      return { error: "Could not find Join Group button (may already be a member)" };
    }

    if (isDryRun(params)) {
      return dryRunResult("join_group", {
        element: joinBtn,
        wouldClick: "join group button",
        selectorUsed: "join group button",
      });
    }

    await humanClick(joinBtn);
    await randomDelay(1500, 3000);

    // Handle possible "Answer questions" dialog
    const answerBtn = await waitForElement([
      'text=Answer Questions',
      'text=Trả lời câu hỏi',
    ], 3000);

    if (answerBtn) {
      // Group requires answers — just submit blank if allowed
      const submitBtn = await waitForElement([
        'div[aria-label="Submit"]',
        'text=Submit',
        'text=Gửi',
      ], 5000);
      if (submitBtn) {
        await humanClick(submitBtn);
      }
    }

    await randomDelay(1000, 2000);
    return { success: true, message: "Group join request sent" };

  } catch (e) {
    return { error: `Join group failed: ${e.message}` };
  }
}

/**
 * Leave a Facebook group.
 */
async function handleLeaveGroup(params) {
  const { groupUrl } = params;

  if (isDryRun(params)) {
    return dryRunResult("leave_group", {
      wouldClick: "joined menu and leave confirmation",
      selectorUsed: "joined button",
    });
  }

  if (shouldForceExtensionDryRun(params)) {
    return extensionSafetyDryRunResult("leave_group", {
      wouldClick: "joined menu and leave confirmation",
      selectorUsed: "joined button",
    });
  }

  try {
    if (groupUrl) {
      window.location.href = groupUrl;
      await sleep(3000);
    }

    // Look for the "Joined" button or triple-dot menu
    const joinedBtn = await waitForElement([
      'div[aria-label="Joined"]',
      'div[aria-label="Đã tham gia"]',
      'text=Joined',
      'text=Đã tham gia',
    ], 8000);

    if (!joinedBtn) {
      return { error: "Could not find Joined button — may not be a member" };
    }

    if (isDryRun(params)) {
      return dryRunResult("leave_group", {
        element: joinedBtn,
        wouldClick: "joined menu and leave confirmation",
        selectorUsed: "joined button",
      });
    }

    await humanClick(joinedBtn);
    await randomDelay(1000, 2000);

    // Click "Leave group"
    const leaveBtn = await waitForElement([
      'text=Leave group',
      'text=Rời nhóm',
      'div[role="menuitem"]',
    ], 5000);

    if (leaveBtn) {
      await humanClick(leaveBtn);
      await randomDelay(1000, 2000);

      // Confirm dialog
      const confirmBtn = await waitForElement([
        'div[aria-label="Leave Group"]',
        'text=Leave Group',
        'text=Rời nhóm',
      ], 3000);
      if (confirmBtn) {
        await humanClick(confirmBtn);
      }
    }

    await randomDelay(1500, 3000);
    return { success: true, message: "Left group" };

  } catch (e) {
    return { error: `Leave group failed: ${e.message}` };
  }
}

/**
 * Follow a Facebook page.
 */
async function handleFollowPage(params) {
  const { pageUrl } = params;

  if (isDryRun(params)) {
    return dryRunResult("follow_page", {
      wouldClick: "follow button",
      selectorUsed: "follow button",
    });
  }

  if (shouldForceExtensionDryRun(params)) {
    return extensionSafetyDryRunResult("follow_page", {
      wouldClick: "follow button",
      selectorUsed: "follow button",
    });
  }

  try {
    if (pageUrl) {
      window.location.href = pageUrl;
      await sleep(3000);
    }

    const followBtn = await waitForElement([
      'div[aria-label="Follow"]',
      'div[aria-label="Theo dõi"]',
      'text=Follow',
      'text=Theo dõi',
    ], 8000);

    if (!followBtn) {
      return { error: "Could not find Follow button (may already be following)" };
    }

    if (isDryRun(params)) {
      return dryRunResult("follow_page", {
        element: followBtn,
        wouldClick: "follow button",
        selectorUsed: "follow button",
      });
    }

    await humanClick(followBtn);
    await randomDelay(1500, 3000);

    return { success: true, message: "Page followed" };

  } catch (e) {
    return { error: `Follow page failed: ${e.message}` };
  }
}

/**
 * Unfollow a Facebook page.
 */
async function handleUnfollowPage(params) {
  const { pageUrl } = params;

  if (isDryRun(params)) {
    return dryRunResult("unfollow_page", {
      wouldClick: "following menu and unfollow option",
      selectorUsed: "following button",
    });
  }

  if (shouldForceExtensionDryRun(params)) {
    return extensionSafetyDryRunResult("unfollow_page", {
      wouldClick: "following menu and unfollow option",
      selectorUsed: "following button",
    });
  }

  try {
    if (pageUrl) {
      window.location.href = pageUrl;
      await sleep(3000);
    }

    const followingBtn = await waitForElement([
      'div[aria-label="Following"]',
      'div[aria-label="Đang theo dõi"]',
      'text=Following',
      'text=Đang theo dõi',
    ], 8000);

    if (!followingBtn) {
      return { error: "Could not find Following button" };
    }

    if (isDryRun(params)) {
      return dryRunResult("unfollow_page", {
        element: followingBtn,
        wouldClick: "following menu and unfollow option",
        selectorUsed: "following button",
      });
    }

    await humanClick(followingBtn);
    await randomDelay(1000, 2000);

    const unfollowBtn = await waitForElement([
      'text=Unfollow',
      'text=Bỏ theo dõi',
      'div[role="menuitem"]',
    ], 5000);

    if (unfollowBtn) {
      await humanClick(unfollowBtn);
    }

    await randomDelay(1500, 3000);
    return { success: true, message: "Page unfollowed" };

  } catch (e) {
    return { error: `Unfollow page failed: ${e.message}` };
  }
}

/**
 * Scrape group members list.
 */
async function handleScrapeGroup(params) {
  const { groupUrl } = params;

  try {
    // Navigate to group members page
    let membersUrl = groupUrl || window.location.href;
    if (!membersUrl.includes("/members")) {
      membersUrl = membersUrl.replace(/\/$/, "") + "/members";
    }
    window.location.href = membersUrl;
    await sleep(4000);

    const members = [];

    // Scroll and collect member cards
    for (let i = 0; i < 10; i++) {
      const memberEls = document.querySelectorAll(
        'div[role="listitem"] a[href*="facebook.com"],' +
        'div[role="listitem"] a[href^="/"]'
      );

      memberEls.forEach(el => {
        const name = el.textContent?.trim();
        const href = el.href || el.getAttribute("href") || "";
        if (name && href && !members.find(m => m.href === href)) {
          members.push({ name, href, uid: href.split("/").pop() || "" });
        }
      });

      // Scroll down to load more
      window.scrollBy(0, 800);
      await randomDelay(1000, 2000);
    }

    return {
      success: true,
      message: `Scraped ${members.length} members`,
      data: { members, source_url: membersUrl },
    };

  } catch (e) {
    return { error: `Scrape group failed: ${e.message}` };
  }
}

/**
 * Scrape live stream comments in real-time.
 */
async function handleScrapeLiveComments(params) {
  const { postUrl, duration } = params;

  try {
    if (postUrl) {
      window.location.href = postUrl;
      await sleep(4000);
    }

    const comments = [];
    const durationMs = (duration || 60) * 1000;
    const startTime = Date.now();

    while (Date.now() - startTime < durationMs) {
      const commentEls = document.querySelectorAll(
        'div[data-testid="UFI2Comment/root_depth_0"],' +
        'div[role="article"]'
      );

      commentEls.forEach(el => {
        const nameEl = el.querySelector('a[role="link"]');
        const textEl = el.querySelector('div[dir="auto"]');
        const name = nameEl?.textContent?.trim() || "";
        const text = textEl?.textContent?.trim() || "";

        if (name && text && !comments.find(c => c.name === name && c.text === text)) {
          comments.push({
            name,
            text,
            timestamp: new Date().toISOString(),
          });
        }
      });

      // Scroll to load new comments
      window.scrollBy(0, 300);
      await randomDelay(2000, 4000);
    }

    return {
      success: true,
      message: `Scraped ${comments.length} live comments`,
      data: { comments, source_url: postUrl || window.location.href },
    };

  } catch (e) {
    return { error: `Scrape live comments failed: ${e.message}` };
  }
}

// ─── Message Router ─────────────────────────────────────────

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  const { method, params } = message;

  // Handle async methods
  (async () => {
    let result;

    if (MUTATING_METHODS.has(method) && shouldForceExtensionDryRun(params)) {
      sendResponse(extensionSafetyDryRunResult(method, {
        wouldClick: "blocked before handler dispatch",
        selectorUsed: "message router",
      }));
      return;
    }

    switch (method) {
      case "post_text":
        result = await handlePostText(params);
        break;
      case "post_with_media":
        result = await handlePostWithMedia(params);
        break;
      case "send_message":
        result = await handleSendMessage(params);
        break;
      case "like_post":
        result = await handleLikePost(params);
        break;
      case "comment_post":
        result = await handleCommentPost(params);
        break;
      case "share_post":
        result = await handleSharePost(params);
        break;
      case "add_friend":
        result = await handleAddFriend(params);
        break;
      case "accept_friend":
        result = await handleAcceptFriend(params);
        break;
      case "join_group":
        result = await handleJoinGroup(params);
        break;
      case "leave_group":
        result = await handleLeaveGroup(params);
        break;
      case "follow_page":
        result = await handleFollowPage(params);
        break;
      case "unfollow_page":
        result = await handleUnfollowPage(params);
        break;
      case "scrape_profile":
        result = await handleScrapeProfile(params);
        break;
      case "scrape_group":
        result = await handleScrapeGroup(params);
        break;
      case "scrape_live_comments":
        result = await handleScrapeLiveComments(params);
        break;
      case "get_page_state":
        result = handleGetPageState();
        break;
      default:
        result = { error: `Unknown method: ${method}` };
    }

    sendResponse(result);
  })();

  // Return true to indicate async response
  return true;
});

// ─── Auto-report page state to background ───────────────────

(function reportState() {
  const loggedIn = !!document.querySelector('[aria-label="Your profile"]')
                || !!document.querySelector('[aria-label="Account"]');

  chrome.runtime.sendMessage({
    type: "page_state",
    data: {
      loggedIn,
      url: window.location.href,
    },
  }).catch(() => {});
})();

console.log("[FBKit] Content script loaded on:", window.location.href);
