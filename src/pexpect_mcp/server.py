import signal
import sys
import traceback
from io import StringIO
from typing import Any, Dict, Optional

import pexpect
from mcp.server.fastmcp import FastMCP


mcp = FastMCP("pexpect-mcp")

# Global timeout setting (can be overridden by tool caller)
TIMEOUT = 12
# Default pexpect timeout (2 seconds less than hard timeout to avoid signal timeout)
DEFAULT_PEXPECT_TIMEOUT = TIMEOUT - 2

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
        timeout: Optional timeout in seconds. If not provided, uses global TIMEOUT (default 10s).
        DONT WRITE COMMENTS

    Example:
        child = pexpect.spawn('lldb ./mytool')
        child.expect("(lldb)")

    Returns:
        The result of the code execution or an error message.

    When asked to dump out a pexpect transcript, make sure to dump with uv --script dependency info
    so the user can run it with "uv run session.py"
    """
    if not code:
        return "No code provided"

    global pexpect_session, session_globals, TIMEOUT

    # Use provided timeout or global default
    actual_timeout = timeout if timeout is not None else TIMEOUT
    # Use shorter timeout for pexpect operations
    pexpect_timeout = (
        min(actual_timeout - 2, DEFAULT_PEXPECT_TIMEOUT) if actual_timeout > 2 else 1
    )

    # Set up print capture
    captured_output = StringIO()
    original_print = print

    def captured_print(*args, **kwargs):
        # Print to our capture buffer
        kwargs_copy = kwargs.copy()
        kwargs_copy["file"] = captured_output
        original_print(*args, **kwargs_copy)
        # Also print to stdout for debugging if needed
        original_print(*args, **kwargs)

    # Set up the execution environment
    local_vars = session_globals.copy()
    local_vars["pexpect"] = pexpect
    local_vars["print"] = captured_print  # Inject our custom print function

    # If we have an active session, make it available as 'child'
    if pexpect_session is not None:
        local_vars["child"] = pexpect_session
        # Set default timeout for pexpect operations
        pexpect_session.timeout = pexpect_timeout

    # Set up signal alarm for timeout
    old_handler = signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(actual_timeout)

    try:
        # Try to execute as an expression first
        result = eval(code, {"__builtins__": __builtins__}, local_vars)
        _update_globals(local_vars, pexpect_timeout)

        # Format the response
        return _format_response(result, captured_output.getvalue())

    except SyntaxError:
        # If it's not an expression, try executing as a statement
        try:
            exec(code, {"__builtins__": __builtins__}, local_vars)
            _update_globals(local_vars, pexpect_timeout)
            return _format_response(
                "Code executed successfully", captured_output.getvalue()
            )

        except Exception as exec_error:
            return _format_response(f"Error: {exec_error}", captured_output.getvalue())

    except TimeoutError as timeout_error:
        # Format timeout error with traceback
        tb = traceback.format_exc()
        error_msg = f"Timeout Error: {timeout_error}\n\nTraceback:\n{tb}"
        return _format_response(error_msg, captured_output.getvalue())

    except Exception as eval_error:
        return _format_response(f"Error: {eval_error}", captured_output.getvalue())

    finally:
        # Always clean up the alarm and restore old handler
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


def _format_response(result, log_output):
    """Format the response with RESULT, LOG, and BUFFER sections."""
    response_parts = [
        safe_str(result) if result is not None else "",
        "---",
        log_output.strip() if log_output else "(no output)",
    ]

    return "\n".join(response_parts)


def _update_globals(local_vars, pexpect_timeout):
    global pexpect_session
    for key, value in local_vars.items():
        if key not in [
            "__builtins__",
            "pexpect",
            "print",
        ]:  # Don't persist the custom print function
            session_globals[key] = value
            # If a 'child' variable was created/modified, update our session
            if key == "child" and isinstance(value, pexpect.spawn):
                pexpect_session = value
                # Set default timeout for the new session
                pexpect_session.timeout = pexpect_timeout


def main():
    """Main entry point for the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
