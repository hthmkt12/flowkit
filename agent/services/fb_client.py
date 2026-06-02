"""FBKit — Facebook Client via Chrome Extension WebSocket bridge.

Supports MULTIPLE simultaneous extension connections (one per Chrome profile/account).
Routes commands to the correct extension based on fb_uid.

Extension → Agent flow:
  1. Extension connects WS
  2. Sends `extension_ready` with {fb_uid, loggedIn}
  3. Agent maps ws → ExtensionSession(fb_uid)
  4. Processor dispatches commands to session matching account.fb_uid
"""
import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ExtensionSession:
    ws: object                    # websockets.WebSocketServerProtocol
    fb_uid: Optional[str]         # Facebook UID, None until extension_ready
    logged_in: bool = False
    extension_live_actions_enabled: Optional[bool] = None
    profile_id: Optional[str] = None
    profile_name: Optional[str] = None
    connected_at: float = field(default_factory=time.time)
    last_seen_at: float = field(default_factory=time.time)
    _pending: dict = field(default_factory=dict)

    @property
    def uptime_s(self) -> int:
        return int(time.time() - self.connected_at)

    def to_dict(self, stale_after_s: int) -> dict:
        age_s = int(time.time() - self.last_seen_at)
        stale = age_s > stale_after_s
        return {
            "fb_uid": self.fb_uid,
            "logged_in": self.logged_in,
            "extension_live_actions_enabled": self.extension_live_actions_enabled,
            "profile_id": self.profile_id,
            "profile_name": self.profile_name,
            "uptime_s": self.uptime_s,
            "last_seen_age_s": age_s,
            "stale": stale,
            "health": "stale" if stale else "online",
        }


class FBClient:
    """Routes automation commands to Chrome extension(s) via WebSocket.

    Supports multiple concurrent extension sessions (multi-account).
    Commands with a target fb_uid require an exact matching session.
    Commands without a target fb_uid fall back to any connected session.
    """

    def __init__(self, stale_after_s: int = 60):
        # ws object → session
        self._sessions: dict[object, ExtensionSession] = {}
        self._stale_after_s = stale_after_s
        # Connection stats
        self._total_connects = 0
        self._total_disconnects = 0

    # ─── Session Management ──────────────────────────────────

    def set_extension(self, ws, fb_uid: Optional[str] = None) -> ExtensionSession:
        """Called when a new extension WS connects."""
        session = ExtensionSession(ws=ws, fb_uid=fb_uid)
        self._sessions[ws] = session
        self._total_connects += 1
        logger.info("Extension connected #%d (fb_uid=%s)", self._total_connects, fb_uid or "unknown")
        return session

    def update_session(
        self,
        ws,
        fb_uid: Optional[str],
        logged_in: bool,
        extension_live_actions_enabled: Optional[bool] = None,
        profile_id: Optional[str] = None,
        profile_name: Optional[str] = None,
    ):
        """Update fb_uid / login status after extension_ready message."""
        session = self._sessions.get(ws)
        if session:
            session.fb_uid = fb_uid
            session.logged_in = logged_in
            session.extension_live_actions_enabled = extension_live_actions_enabled
            session.profile_id = profile_id
            session.profile_name = profile_name
            session.last_seen_at = time.time()
            logger.info("Extension session registered fb_uid=%s, logged_in=%s", fb_uid, logged_in)

    def _refresh_session_identity(self, ws, data: dict) -> bool:
        """Refresh heartbeat only when current Facebook identity is known.

        Older extension heartbeats did not include the current c_user cookie. Once a
        session is bound to a fb_uid, accepting identity-less keepalives could make
        an old UID look fresh after the browser profile switches Facebook accounts.
        """
        session = self._sessions.get(ws)
        if not session:
            return False

        has_uid = "fb_uid" in data or "uid" in data
        has_login_state = "loggedIn" in data
        if not has_uid and not has_login_state:
            if session.fb_uid:
                logger.warning("Ignoring identity-less heartbeat for fb_uid=%s", session.fb_uid)
                return False
            session.last_seen_at = time.time()
            return True

        fb_uid = data.get("fb_uid") if "fb_uid" in data else data.get("uid")
        logged_in = bool(data.get("loggedIn", bool(fb_uid)))
        if not logged_in:
            fb_uid = None
        self.update_session(
            ws,
            fb_uid,
            logged_in,
            data.get("extensionLiveActionsEnabled"),
            data.get("profileId"),
            data.get("profileName"),
        )
        return True

    def clear_extension(self, ws):
        """Called when extension disconnects."""
        session = self._sessions.pop(ws, None)
        if session:
            self._total_disconnects += 1
            # Cancel all pending requests for this session
            for req_id, future in list(session._pending.items()):
                if not future.done():
                    future.set_exception(ConnectionError("Extension disconnected"))
            session._pending.clear()
            logger.warning(
                "Extension disconnected (fb_uid=%s), cancelled %d pending requests",
                session.fb_uid or "unknown",
                len(session._pending),
            )

    def get_session_for(self, fb_uid: Optional[str] = None) -> Optional[ExtensionSession]:
        """Get an exact fb_uid session, or any session only when no fb_uid is requested."""
        if not self._sessions:
            return None
        if fb_uid:
            matches = [session for session in self._sessions.values() if session.fb_uid == fb_uid]
            fresh_matches = [session for session in matches if not self._is_stale(session)]
            if fresh_matches:
                return max(fresh_matches, key=lambda session: session.last_seen_at)
            if matches:
                logger.warning("All extension sessions for fb_uid=%s are stale", fb_uid)
                return None
            logger.warning("No extension session for fb_uid=%s", fb_uid)
            return None
        # Fallback: first available session
        for session in self._sessions.values():
            if not self._is_stale(session):
                return session
        return None

    def _is_stale(self, session: ExtensionSession) -> bool:
        return (time.time() - session.last_seen_at) > self._stale_after_s

    def session_live_guard_enabled(self, fb_uid: Optional[str] = None) -> bool:
        """Return True only when the selected extension reports live guard enabled."""
        session = self.get_session_for(fb_uid)
        return bool(session and session.extension_live_actions_enabled is True)

    @property
    def connected(self) -> bool:
        return bool(self._sessions)

    @property
    def has_fresh_session(self) -> bool:
        return any(not self._is_stale(session) for session in self._sessions.values())

    @property
    def active_session_count(self) -> int:
        return len(self._sessions)

    @property
    def ws_stats(self) -> dict:
        sessions = [s.to_dict(self._stale_after_s) for s in self._sessions.values()]
        return {
            "connected": self.connected,
            "session_count": len(sessions),
            "sessions": sessions,
            "total_connects": self._total_connects,
            "total_disconnects": self._total_disconnects,
        }

    # ─── Message Handling ─────────────────────────────────────

    async def handle_message(self, ws, data: dict):
        """Handle incoming message from an extension."""
        msg_type = data.get("type")
        session = self._sessions.get(ws)

        if msg_type == "extension_ready":
            fb_uid = data.get("fb_uid") or data.get("uid")
            logged_in = bool(data.get("loggedIn", False))
            extension_live_actions_enabled = data.get("extensionLiveActionsEnabled")
            profile_id = data.get("profileId")
            profile_name = data.get("profileName")
            if fb_uid and session:
                self.update_session(ws, fb_uid, logged_in, extension_live_actions_enabled, profile_id, profile_name)
            else:
                logger.info("Extension ready (no uid yet), logged_in=%s", logged_in)
            return

        if msg_type == "login_status":
            fb_uid = data.get("uid") or data.get("fb_uid")
            logged_in = bool(data.get("loggedIn", False))
            extension_live_actions_enabled = data.get("extensionLiveActionsEnabled")
            profile_id = data.get("profileId")
            profile_name = data.get("profileName")
            if fb_uid and session:
                self.update_session(ws, fb_uid, logged_in, extension_live_actions_enabled, profile_id, profile_name)
            return

        if msg_type == "pong":
            self._refresh_session_identity(ws, data)
            return

        if msg_type == "ping":
            self._refresh_session_identity(ws, data)
            try:
                await ws.send(json.dumps({"type": "pong"}))
            except Exception:
                pass
            return

        # Response to a pending command
        req_id = data.get("id")
        if req_id and session and req_id in session._pending:
            future = session._pending[req_id]
            if not future.done():
                future.set_result(data)
            return

    # ─── Command Sending ──────────────────────────────────────

    async def _send(
        self,
        method: str,
        params: dict,
        fb_uid: Optional[str] = None,
        timeout: float = 120,
    ) -> dict:
        """Send command to the correct extension session and wait for response."""
        session = self.get_session_for(fb_uid)
        if session is None:
            if fb_uid and any(s.fb_uid == fb_uid for s in self._sessions.values()):
                return {"error": "Extension session is stale"}
            return {"error": "No extension connected"}

        req_id = str(uuid.uuid4())
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        session._pending[req_id] = future
        routed_params = {**params, "expectedFbUid": fb_uid} if fb_uid else params

        try:
            await session.ws.send(json.dumps({
                "id": req_id,
                "method": method,
                "params": routed_params,
            }))
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            return {"error": f"Timeout ({timeout}s) waiting for {method}"}
        except Exception as e:
            return {"error": str(e)}
        finally:
            session._pending.pop(req_id, None)

    # ─── High-level Facebook Commands ───────────────────────

    async def check_login(self, fb_uid: str = None) -> dict:
        return await self._send("check_login", {}, fb_uid=fb_uid)

    @staticmethod
    def _with_strategy(params: dict, strategy: dict | None = None) -> dict:
        if strategy:
            return {**params, "_strategy": strategy}
        return params

    async def navigate(self, url: str, fb_uid: str = None) -> dict:
        return await self._send("navigate", {"url": url}, fb_uid=fb_uid)

    async def post_text(self, content: str, target_type: str = "TIMELINE",
                        target_id: str = None, fb_uid: str = None,
                        strategy: dict | None = None,
                        dry_run: bool = False) -> dict:
        return await self._send("post_text", self._with_strategy({
            "content": content,
            "targetType": target_type,
            "targetId": target_id,
            "dryRun": dry_run,
        }, strategy), fb_uid=fb_uid, timeout=60)

    async def post_with_media(self, content: str, media_paths: list[str],
                                target_type: str = "TIMELINE",
                                target_id: str = None, fb_uid: str = None,
                                strategy: dict | None = None,
                                dry_run: bool = False) -> dict:
        return await self._send("post_with_media", self._with_strategy({
            "content": content,
            "mediaPaths": media_paths,
            "targetType": target_type,
            "targetId": target_id,
            "dryRun": dry_run,
        }, strategy), fb_uid=fb_uid, timeout=300)

    async def send_message(self, recipient_name: str, content: str,
                             recipient_uid: str = None,
                             media_path: str = None, fb_uid: str = None,
                             strategy: dict | None = None,
                             dry_run: bool = False) -> dict:
        return await self._send("send_message", self._with_strategy({
            "recipientName": recipient_name,
            "recipientUid": recipient_uid,
            "content": content,
            "mediaPath": media_path,
            "dryRun": dry_run,
        }, strategy), fb_uid=fb_uid, timeout=60)

    async def like_post(self, post_url: str, reaction: str = "LIKE",
                        fb_uid: str = None, strategy: dict | None = None,
                        dry_run: bool = False) -> dict:
        return await self._send("like_post", self._with_strategy({
            "postUrl": post_url,
            "reaction": reaction,
            "dryRun": dry_run,
        }, strategy), fb_uid=fb_uid)

    async def comment_post(self, post_url: str, comment: str,
                           fb_uid: str = None, strategy: dict | None = None,
                           dry_run: bool = False) -> dict:
        return await self._send("comment_post", self._with_strategy({
            "postUrl": post_url,
            "comment": comment,
            "dryRun": dry_run,
        }, strategy), fb_uid=fb_uid)

    async def share_post(self, post_url: str, comment: str = "",
                          target_type: str = "TIMELINE",
                          target_id: str = None, fb_uid: str = None,
                          strategy: dict | None = None,
                          dry_run: bool = False) -> dict:
        return await self._send("share_post", self._with_strategy({
            "postUrl": post_url,
            "comment": comment,
            "targetType": target_type,
            "targetId": target_id,
            "dryRun": dry_run,
        }, strategy), fb_uid=fb_uid)

    async def add_friend(self, profile_url: str, fb_uid: str = None,
                         strategy: dict | None = None,
                         dry_run: bool = False) -> dict:
        return await self._send(
            "add_friend",
            self._with_strategy({
                "profileUrl": profile_url,
                "dryRun": dry_run,
            }, strategy),
            fb_uid=fb_uid,
        )

    async def accept_friend(self, request_url: str = None, fb_uid: str = None,
                            strategy: dict | None = None,
                            dry_run: bool = False) -> dict:
        return await self._send(
            "accept_friend",
            self._with_strategy({
                "requestUrl": request_url,
                "dryRun": dry_run,
            }, strategy),
            fb_uid=fb_uid,
        )

    async def join_group(self, group_url: str, fb_uid: str = None,
                         strategy: dict | None = None,
                         dry_run: bool = False) -> dict:
        return await self._send(
            "join_group",
            self._with_strategy({
                "groupUrl": group_url,
                "dryRun": dry_run,
            }, strategy),
            fb_uid=fb_uid,
        )

    async def leave_group(self, group_url: str, fb_uid: str = None,
                          strategy: dict | None = None,
                          dry_run: bool = False) -> dict:
        return await self._send(
            "leave_group",
            self._with_strategy({
                "groupUrl": group_url,
                "dryRun": dry_run,
            }, strategy),
            fb_uid=fb_uid,
        )

    async def follow_page(self, page_url: str, fb_uid: str = None,
                          strategy: dict | None = None,
                          dry_run: bool = False) -> dict:
        return await self._send(
            "follow_page",
            self._with_strategy({
                "pageUrl": page_url,
                "dryRun": dry_run,
            }, strategy),
            fb_uid=fb_uid,
        )

    async def unfollow_page(self, page_url: str, fb_uid: str = None,
                            strategy: dict | None = None,
                            dry_run: bool = False) -> dict:
        return await self._send(
            "unfollow_page",
            self._with_strategy({
                "pageUrl": page_url,
                "dryRun": dry_run,
            }, strategy),
            fb_uid=fb_uid,
        )

    async def scrape_profile(self, profile_url: str, fb_uid: str = None,
                             strategy: dict | None = None) -> dict:
        return await self._send(
            "scrape_profile",
            self._with_strategy({"profileUrl": profile_url}, strategy),
            fb_uid=fb_uid,
        )

    async def scrape_group(self, group_url: str, fb_uid: str = None,
                           strategy: dict | None = None) -> dict:
        return await self._send(
            "scrape_group",
            self._with_strategy({"groupUrl": group_url}, strategy),
            fb_uid=fb_uid,
        )

    async def get_page_state(self, fb_uid: str = None) -> dict:
        return await self._send("get_page_state", {}, fb_uid=fb_uid)

    async def get_post_metrics(self, external_post_id: str, fb_uid: str = None) -> dict:
        return await self._send("get_post_metrics", {"externalPostId": external_post_id}, fb_uid=fb_uid)


# ─── Singleton ──────────────────────────────────────────────

_client: Optional[FBClient] = None


def get_fb_client() -> FBClient:
    global _client
    if _client is None:
        _client = FBClient()
    return _client
