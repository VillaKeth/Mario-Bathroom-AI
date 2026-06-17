"""FastMCP server exposing ChatGPT-via-browser as tools."""
from mcp.server.fastmcp import FastMCP

from mcp_chatgpt.browser import get_session, NotLoggedIn, Challenge

mcp = FastMCP("chatgpt")


def _err(msg: str) -> dict:
    return {"error": msg, "response": {"text": "", "images": [], "timed_out": False}}


@mcp.tool()
async def chatgpt_new_thread(prompt: str, account: str = "default", provider: str = "chatgpt") -> dict:
    """Start a new ChatGPT conversation. Returns {thread_id, response:{text,images,timed_out}}.

    `account` selects which logged-in profile to use (e.g. "default", "work").
    Each account must be logged in once via `python -m mcp_chatgpt._login_oneshot <provider> <account>`.
    `provider` selects which site to use (e.g. "chatgpt"); defaults to "chatgpt".
    """
    try:
        return await get_session(provider).new_thread(prompt, account=account)
    except NotLoggedIn as e:
        return _err(str(e))
    except Challenge as e:
        return _err(str(e))


@mcp.tool()
async def chatgpt_send(thread_id: str, prompt: str, account: str = "default", provider: str = "chatgpt") -> dict:
    """Send a follow-up in an existing thread. Returns {response:{text,images,timed_out}}.

    `account` must match the account the thread was created under (used only when
    the tab needs reopening by URL).
    `provider` selects which site to use (e.g. "chatgpt"); defaults to "chatgpt".
    """
    try:
        return await get_session(provider).send(thread_id, prompt, account=account)
    except NotLoggedIn as e:
        return _err(str(e))
    except Challenge as e:
        return _err(str(e))


@mcp.tool()
async def chatgpt_close_thread(thread_id: str, provider: str = "chatgpt") -> dict:
    """Close a thread's tab. Returns {ok: bool}."""
    return await get_session(provider).close_thread(thread_id)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
