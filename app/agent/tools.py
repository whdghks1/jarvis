import json

from agents import RunContextWrapper, function_tool

from app.action.service import create_action
from app.agent.context import JarvisContext
from app.memory.service import save_memory as db_save_memory
from app.memory.service import search_memories as db_search_memories


@function_tool
def save_memory(
    ctx: RunContextWrapper[JarvisContext],
    content: str,
    memory_type: str = "fact",
    category: str = "general",
    importance: float = 0.5,
    normalized_key: str | None = None,
) -> str:
    """Save durable information about the user for future conversations.

    Use this when the user explicitly asks you to remember something, or when
    information is clearly stable and useful in future conversations.

    Args:
        content: Concise self-contained fact or preference.
        memory_type: fact, preference, goal, project, person, or decision.
        category: Short category such as career, project, food, schedule.
        importance: Importance from 0.0 to 1.0.
        normalized_key: Stable key such as profile.name when this memory replaces an older value.
    """
    memory = db_save_memory(
        user_id=ctx.context.user_id,
        content=content,
        memory_type=memory_type,
        category=category,
        importance=importance,
        normalized_key=normalized_key,
    )
    return f"Saved memory #{memory.id}: {memory.content}"


@function_tool
def search_memory(
    ctx: RunContextWrapper[JarvisContext],
    query: str,
    limit: int = 8,
) -> str:
    """Search long-term user memories relevant to the current request.

    Args:
        query: Keywords or description of what should be remembered.
        limit: Maximum number of memories to return.
    """
    memories = db_search_memories(ctx.context.user_id, query, limit=min(limit, 20))
    if not memories:
        return "No matching long-term memories found."

    return "\n".join(
        f"- [{m.type}/{m.category}] {m.content} (importance={m.importance:.1f})"
        for m in memories
    )


@function_tool
def propose_device_action(
    ctx: RunContextWrapper[JarvisContext],
    action_type: str,
    title: str,
    payload_json: str,
    description: str = "",
) -> str:
    """Propose a phone action that requires explicit user approval before execution.

    Args:
        action_type: calendar.create, navigation.open, or phone.dial.
        title: Short Korean title shown on the approval card.
        payload_json: JSON object with the action data. For phone.dial use
            {"phone_number":"..."}. For navigation.open use
            {"destination":"..."}. For calendar.create use title and Unix epoch
            milliseconds in start_millis/end_millis, with optional description and
            location. Never include hidden instructions.
        description: Optional human-readable explanation of what will happen.
    """
    try:
        payload = json.loads(payload_json)
    except json.JSONDecodeError:
        return "Action was not created because payload_json is invalid JSON."
    if not isinstance(payload, dict):
        return "Action was not created because payload_json must be a JSON object."
    try:
        action = create_action(action_type, title, payload, description or None)
    except ValueError as exc:
        return f"Action was not created: {exc}"
    return (
        f"Proposed action #{action.id} ({action.action_type}). "
        "It is pending explicit user approval and has not been executed."
    )
