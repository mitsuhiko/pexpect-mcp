import signal
import sys
import traceback
from typing import Any, Dict, Optional

import pexpect
from mcp.server.fastmcp import FastMCP


mcp = FastMCP("pexpect-mcp")

# Global timeout setting (can be overridden by tool caller)
TIMEOUT = 15

pexpect_session: Optional[pexpect.spawn] = None
session_globals: Dict[str, Any] = {}


class TimeoutError(Exception):
    """Raised when pexpect operation times out."""

    pass


def timeout_handler(signum, frame):
    """Signal handler for timeout."""
    raise TimeoutError("Operation timed out after {} seconds".format(TIMEOUT))


def safe_str(obj: Any) -> str:
    """Safely convert object to string, handling bytes and other types."""
    if isinstance(obj, bytes):
        try:
            return obj.decode("utf-8", errors="replace")
        except:
            return repr(obj)
    return str(obj)


@mcp.tool()
def pexpect_tool(code: str, timeout: Optional[int] = None) -> str:
    """Execute Python code in a pexpect session. Can spawn processes and interact with them.

    Args:
        code: Python code to execute. Use 'child' variable to interact with the spawned process.
        The pexpect library is already imported.  Use `pexpect.spawn(...)` to spawn something.
        timeout: Optional timeout in seconds. If not provided, uses global TIMEOUT (default 15s).

    Example:
        child = pexpect.spawn('lldb ./mytool')
        child.expect("(lldb)")

    Returns:
        The result of the code execution or an error message.

    Remember that this is a full Python interpreter.  You can use any
    Python code here to debug and inspect it.
    """
    if not code:
        return "No code provided"

    global pexpect_session, session_globals, TIMEOUT

    # Use provided timeout or global default
    actual_timeout = timeout if timeout is not None else TIMEOUT

    # Set up the execution environment
    local_vars = session_globals.copy()
    local_vars["pexpect"] = pexpect
    # Set default timeout for new pexpect sessions
    local_vars["PEXPECT_TIMEOUT"] = actual_timeout

    # If we have an active session, make it available as 'child'
    if pexpect_session is not None:
        local_vars["child"] = pexpect_session
        # Set default timeout for pexpect operations
        pexpect_session.timeout = actual_timeout

    # Set up signal alarm for timeout
    old_handler = signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(actual_timeout)

    try:
        # Try to execute as an expression first
        result = eval(code, {"__builtins__": __builtins__}, local_vars)
        _update_globals(local_vars, actual_timeout)

        # Return the result
        if result is not None:
            return safe_str(result)
        else:
            return "Code executed successfully"

    except SyntaxError:
        # If it's not an expression, try executing as a statement
        try:
            exec(code, {"__builtins__": __builtins__}, local_vars)
            _update_globals(local_vars, actual_timeout)
            return "Code executed successfully"

        except Exception as exec_error:
            return f"Error: {exec_error}"

    except TimeoutError as timeout_error:
        # Format timeout error with traceback
        tb = traceback.format_exc()
        return f"Timeout Error: {timeout_error}\n\nTraceback:\n{tb}"

    except Exception as eval_error:
        return f"Error: {eval_error}"

    finally:
        # Always clean up the alarm and restore old handler
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


def _update_globals(local_vars, spawn_timeout):
    for key, value in local_vars.items():
        if key not in ["__builtins__", "pexpect"]:
            session_globals[key] = value
            # If a 'child' variable was created/modified, update our session
            if key == "child" and isinstance(value, pexpect.spawn):
                pexpect_session = value
                # Set default timeout for the new session
                pexpect_session.timeout = spawn_timeout


def main():
    """Main entry point for the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
