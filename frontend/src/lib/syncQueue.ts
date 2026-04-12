import { getPendingActions, clearActions } from "./offlineStore";

export async function syncOfflineActions() {
  const actions = await getPendingActions();
  if (actions.length === 0) return;

  for (const action of actions) {
    try {
      switch (action.type) {
        case "markRead":
          await fetch("/api/mail/messages/" + action.messageId + "/flags", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ flags: ["\\Seen"] })
          });
          break;
        case "markUnread":
          await fetch("/api/mail/messages/" + action.messageId + "/flags", {
            method: "DELETE",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ flags: ["\\Seen"] })
          });
          break;
        case "delete":
          await fetch("/api/mail/messages/" + action.messageId, {
            method: "DELETE"
          });
          break;
        case "move":
          await fetch("/api/mail/messages/" + action.messageId + "/move", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ folder: action.data?.folder })
          });
          break;
        case "flag":
          await fetch("/api/mail/messages/" + action.messageId + "/flags", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ flags: ["\\Flagged"] })
          });
          break;
      }
    } catch (e) {
      console.error("Failed to sync action:", action, e);
    }
  }

  await clearActions();
}

// Auto-sync when coming back online
if (typeof window !== "undefined") {
  window.addEventListener("online", () => {
    syncOfflineActions();
  });
}
