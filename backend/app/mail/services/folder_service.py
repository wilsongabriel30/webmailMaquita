"""Folder service — list folders, detect special folders, unread counts."""
from app.mail.clients.imap_client import list_folders as imap_list_folders

SPECIAL_FOLDERS = {
    "inbox": "INBOX",
    "sent": ["Sent", "Sent Messages", "Sent Items"],
    "drafts": ["Drafts", "Draft"],
    "trash": ["Trash", "Deleted Items", "Deleted Messages"],
    "junk": ["Junk", "Spam", "Junk E-mail"],
    "archive": ["Archive"],
}


def detect_folder_type(name: str, flags: list[str]) -> str:
    name_lower = name.lower()
    if name_lower == "inbox":
        return "inbox"
    for ftype, names in SPECIAL_FOLDERS.items():
        if ftype == "inbox":
            continue
        flag_name = ftype.capitalize()
        if flag_name in flags:
            return ftype
        if isinstance(names, list) and name_lower in [n.lower() for n in names]:
            return ftype
    return "folder"


async def get_folders(imap) -> list[dict]:
    """Get folders with type detection."""
    raw_folders = await imap_list_folders(imap)
    result = []
    for f in raw_folders:
        f["type"] = detect_folder_type(f["name"], f["flags"])
        result.append(f)
    # Sort: special folders first in standard order, then alphabetical
    order = {"inbox": 0, "drafts": 1, "sent": 2, "junk": 3, "trash": 4, "archive": 5, "folder": 6}
    result.sort(key=lambda x: (order.get(x["type"], 6), x["name"]))
    return result
