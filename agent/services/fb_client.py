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
    connected_at: float = field(default_factory=time.time)
    _pending: dict = field(default_factory=dict)

    @property
    def uptime_s(self) -> int:
        return int(time.time() - self.connected_at)

    def to_dict(self) -> dict:
        return {
            "fb_uid": self.fb_uid,
            "logged_in": self.logged_in,
            "uptime_s": self.uptime_s,
        }


class FBClient:
    """Routes automation commands to Chrome extension(s) via WebSocket.

    Supports multiple concurrent extension sessions (multi-account).
    Commands are routed to the session matching the target fb_uid.
    Falls back to any connected session if fb_uid is not specified.
    """

    def __init__(self):
        # ws object → session
        self._sessions: dict[object, ExtensionSession] = {}
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

    def update_session(self, ws, fb_uid: str, logged_in: bool):
        """Update fb_uid / login status after extension_ready message."""
        session = self._sessions.get(ws)
        if session:
            session.fb_uid = fb_uid
            session.logged_in = logged_in
            logger.info("Extension session registered fb_uid=%s, logged_in=%s", fb_uid, logged_in)

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
        """Get the session for a specific fb_uid, or any active session."""
        if not self._sessions:
            return None
        if fb_uid:
            # Exact match first
            for session in self._sessions.values():
                if session.fb_uid == fb_uid:
                    return session
            logger.warning("No extension session for fb_uid=%s, falling back to any", fb_uid)
        # Fallback: first available session
        return next(iter(self._sessions.values()), None)

    @property
    def connected(self) -> bool:
        return bool(self._sessions)

    @property
    def active_session_count(self) -> int:
        return len(self._sessions)

    @property
    def ws_stats(self) -> dict:
        sessions = [s.to_dict() for s in self._sessions.values()]
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
            if fb_uid and session:
                self.update_session(ws, fb_uid, logged_in)
            else:
                logger.info("Extension ready (no uid yet), logged_in=%s", logged_in)
            return

        if msg_type == "login_status":
            fb_uid = data.get("uid") or data.get("fb_uid")
            logged_in = bool(data.get("loggedIn", False))
            if fb_uid and session:
                self.update_session(ws, fb_uid, logged_in)
            return

        if msg_type == "pong":
            return

        if msg_type == "ping":
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
            return {"error": "No extension connected"}

        req_id = str(uuid.uuid4())
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        session._pending[req_id] = future

        try:
            await session.ws.send(json.dumps({
                "id": req_id,
                "method": method,
                "params": params,
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


# ─── Singleton ──────────────────────────────────────────────

_client: Optional[FBClient] = None


def get_fb_client() -> FBClient:
    global _client
    if _client is None:
        _client = FBClient()
    return _client
