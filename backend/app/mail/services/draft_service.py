"""Draft service — autosave via IMAP APPEND with controlled replacement."""
from app.mail.clients.imap_client import (
    append_message,
    fetch_message_headers,
    list_message_uids,
    uid_delete_message,
)
from app.mail.clients.smtp_client import OutgoingEmail, build_draft_message


async def save_draft(
    imap,
    email_data: OutgoingEmail,
    existing_draft_uid: int | None = None,
    drafts_folder: str = "Drafts",
) -> int | None:
    """Save or update a draft.

    Strategy: APPEND new draft, then delete old one.
    This ensures the new draft exists before the old is removed,
    preventing data loss during autosave.
    """
    raw_message = build_draft_message(email_data)

    # Append new draft
    new_uid = await append_message(imap, drafts_folder, raw_message, "\\Draft \\Seen")

    # Delete old draft if replacing
    if existing_draft_uid and new_uid:
        await uid_delete_message(imap, drafts_folder, existing_draft_uid)

    return new_uid


async def delete_draft(imap, uid: int, drafts_folder: str = "Drafts") -> bool:
    """Delete a draft by UID."""
    return await uid_delete_message(imap, drafts_folder, uid)
