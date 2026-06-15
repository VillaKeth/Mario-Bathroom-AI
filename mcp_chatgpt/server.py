"""FastMCP server exposing ChatGPT-via-browser as tools."""
from mcp.server.fastmcp import FastMCP

from mcp_chatgpt.browser import get_session, NotLoggedIn, Challenge

mcp = FastMCP("chatgpt")


def _err(msg: str) -> dict:
    return {"error": msg, "response": {"text": "", "images": [], "timed_out": False}}


@mcp.tool()
async def chatgpt_new_thread(prompt: str) -> dict:
    """Start a new ChatGPT conversation. Returns {thread_id, response:{text,images,timed_out}}."""
    try:
        return await get_session().new_thread(prompt)
    except NotLoggedIn as e:
        return _err(str(e))
    except Challenge as e:
        return _err(str(e))


@mcp.tool()
async def chatgpt_send(thread_id: str, prompt: str) -> dict:
    """Send a follow-up in an existing thread. Returns {response:{text,images,timed_out}}."""
    try:
        return await get_session().send(thread_id, prompt)
    except NotLoggedIn as e:
        return _err(str(e))
    except Challenge as e:
        return _err(str(e))


@mcp.tool()
async def chatgpt_close_thread(thread_id: str) -> dict:
    """Close a thread's tab. Returns {ok: bool}."""
    return await get_session().close_thread(thread_id)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
