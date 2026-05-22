import { getPendingActions, clearActions, getOutboxEmails, updateOutboxStatus, removeFromOutbox } from "./offlineStore";

let isSyncing = false;

export async function syncOfflineActions() {
  const actions = await getPendingActions();
  if (actions.length === 0) return;

  for (const action of actions) {
    try {
      const base = `/api/mail/bulk-action/${encodeURIComponent(action.folder)}`;
      await fetch(base, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          uids: [action.uid],
          action: action.type === "markRead" ? "mark_read"
            : action.type === "markUnread" ? "mark_unread"
            : action.type === "flag" ? "flag"
            : action.type === "unflag" ? "unflag"
            : action.type === "delete" ? "delete"
            : action.type === "move" ? "move"
            : action.type,
          dest_folder: action.data?.folder as string | undefined,
        }),
      });
    } catch (e) {
      console.error("[Offline] Failed to sync action:", action, e);
    }
  }

  await clearActions();
}

export async function syncOutbox(): Promise<{ sent: number; failed: number }> {
  if (isSyncing) return { sent: 0, failed: 0 };
  isSyncing = true;

  let sent = 0;
  let failed = 0;

  try {
    const emails = await getOutboxEmails();
    const pending = emails.filter(e => e.status === 'pending' || (e.status === 'failed' && e.retries < 3));

    for (const email of pending) {
      await updateOutboxStatus(email.id, 'sending');
      try {
        const res = await fetch('/api/mail/send', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({
            to: email.to,
            cc: email.cc,
            bcc: email.bcc,
            subject: email.subject,
            html_body: email.html_body,
            text_body: email.text_body,
            in_reply_to: email.in_reply_to || '',
            references: email.references || '',
            attachments: email.attachments || [],
            request_read_receipt: email.request_read_receipt || false,
            request_delivery_receipt: email.request_delivery_receipt || false,
          }),
        });

        if (res.ok) {
          await removeFromOutbox(email.id);
          sent++;
        } else {
          const body = await res.json().catch(() => ({}));
          await updateOutboxStatus(email.id, 'failed', body.detail || `HTTP ${res.status}`);
          failed++;
        }
      } catch (err) {
        await updateOutboxStatus(email.id, 'failed', err instanceof Error ? err.message : 'Error de red');
        failed++;
      }
    }
  } finally {
    isSyncing = false;
  }

  return { sent, failed };
}

export async function syncAll(): Promise<{ actions: number; sent: number; failed: number }> {
  const actions = await getPendingActions();
  await syncOfflineActions();
  const { sent, failed } = await syncOutbox();
  return { actions: actions.length, sent, failed };
}

// Auto-sync when coming back online
if (typeof window !== "undefined") {
  window.addEventListener("online", () => {
    // Small delay to let network stabilize
    setTimeout(async () => {
      const result = await syncAll();
      if (result.actions > 0 || result.sent > 0) {
        window.dispatchEvent(new CustomEvent('offline-sync-complete', { detail: result }));
        window.dispatchEvent(new CustomEvent('refresh-messages'));
      }
    }, 2000);
  });
}
