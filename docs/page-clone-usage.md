# Page Clone usage

This worktree implements a bounded, read-only source-page reader plus an operator-review draft flow. It does not create a Facebook page or publish automatically.

## 1. Create a source scrape task

`POST /api/tasks`

```json
{
  "account_id": "ACCOUNT_ID",
  "task_type": "SCRAPE_PAGE_CLONE",
  "payload": {
    "sourceUrl": "https://www.facebook.com/source-page",
    "maxPosts": 25,
    "candidateLimit": 8,
    "maxMediaPerPost": 10,
    "deadlineSeconds": 30,
    "downloadMedia": false
  }
}
```

The source URL must be an HTTPS Facebook page URL. Values above the limits are rejected. Set `downloadMedia: true` only when local image caching is wanted; downloads are restricted to HTTPS Facebook media hosts, no redirects, image content, and bounded sizes. The task requires the account's exact, fresh, logged-in `fb_uid` session.

## 2. Review evidence

Read `GET /api/tasks/{task_id}` after the task reaches `COMPLETED`. The durable result is redacted: source URLs, IDs, permalinks, media URLs, and tokens are not stored raw.

## 3. Create local drafts

`POST /api/tasks/{task_id}/page-clone-drafts`

```json
{
  "account_id": "ACCOUNT_ID",
  "target_id": "DESTINATION_PAGE_ID_OR_SLUG",
  "selected_post_indexes": [0, 2]
}
```

This creates local `DRAFT` posts only. It requires a completed Page Clone task, matching account, and 1–8 selected posts.

## 4. Queue a reviewed draft

`POST /api/posts/{post_id}/queue`

The draft is atomically claimed to prevent duplicate queueing. The resulting `POST_TEXT` task passes through the existing safety gate and is dry-run by default. Live publishing requires all existing global auth, live-arm, and approval controls.

With `downloadMedia: false`, media is metadata-only. With it enabled, allowlisted images and MP4 videos are cached under `MEDIA_DIR`; selected drafts become `IMAGE` or `VIDEO` posts. Facebook upload remains behind the existing dry-run/live approval gates.
