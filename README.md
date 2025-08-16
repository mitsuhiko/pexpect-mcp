# pexpect-mcp

An [MCP](https://modelcontextprotocol.io/) (Model Context Protocol) server that
provides remote pexpect session control for debugging and process interaction.

## Overview

This MCP server enables AI assistants to execute Python code with pexpect
functionality, allowing for interactive debugging sessions with tools like
LLDB, GDB, and other command-line utilities that require programmatic
interaction.

In some sense this is less of a pexpect MCP as one that is just maintaining
a stateful Python session.

## Installation

```bash
uv tool install git+https://github.com/mitsuhiko/pexpect-mcp
```

## Usage

### As an MCP Server

Add to your Claude Code configuration:

```json
{
  "mcpServers": {
    "pexpect": {
      "command": "pexpect-mcp"
    }
  }
}
```

### Tool Usage

The server provides a single tool: `pexpect_tool`

**Parameters:**
- `code` (string): Python code to execute with pexpect support
- `timeout` (optional int): Timeout in seconds (default: 30)

**Example Usage:**

```python
# Start a debugging session
child = pexpect.spawn('lldb ./my-program')
child.expect('(lldb)')

# Run the program
child.sendline('run')
child.expect('(lldb)')
print(child.before.decode())

# Get backtrace
child.sendline('bt')
child.expect('(lldb)')
print(child.before.decode())
```

## Demo

The repository includes a demo with a buggy C program (`demo-buggy.c`) that can
be debugged using LLDB through the pexpect interface. This demonstrates the
server's capability for interactive debugging sessions.

```
The program `./demo-buggy` crashes when executed. Use LLDB to:

- Start the program under the debugger
- Identify where and why it crashes
- Examine variables, memory, and call stack
- Report the root cause of the crash
```

## Requirements

- Python ≥ 3.12.1
- pexpect ≥ 4.9.0
- mcp ≥ 1.13.0

## License

See LICENSE file for details.
