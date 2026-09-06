from app.admin.postfix_wrapper import (
    delete_all,
    delete_one,
    flush_all,
    flush_one,
    hold_one,
    list_queue,
    release_one,
)


async def get_queue() -> list[dict]:
    return await list_queue()


async def queue_action(action: str, queue_id: str | None = None) -> bool:
    if action == "flush" and queue_id:
        return await flush_one(queue_id)
    elif action == "flush_all":
        return await flush_all()
    elif action == "delete" and queue_id:
        return await delete_one(queue_id)
    elif action == "delete_all":
        return await delete_all()
    elif action == "hold" and queue_id:
        return await hold_one(queue_id)
    elif action == "release" and queue_id:
        return await release_one(queue_id)
    else:
        raise ValueError(f"Invalid action: {action}")
