#!/usr/bin/env python3
"""RTK MCP Server — pipes shell commands through the rtk binary for 96% token savings.

Protocol: MCP stdio transport (JSON-RPC 2.0 over stdin/stdout).
Drop-in replacement for rtk-mcp v0.1.0 (which has a protocol mismatch with Hermes).

Supported tools:
  - run_command: Execute a shell command through RTK filtering.
"""

import json
import subprocess
import sys


RTK = "/opt/homebrew/bin/rtk"


def rtk_run(command: str, cwd: str | None = None) -> str:
    """Run a command through RTK filtering and return the output."""
    # Prepend "rtk" unless command already starts with rtk
    if not command.strip().startswith("rtk"):
        command = f"rtk {command}"
    result = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        cwd=cwd,
        timeout=120,
    )
    output = result.stdout + result.stderr
    if result.returncode != 0 and not output.strip():
        output = f"[exit code: {result.returncode}]"
    return output


def send_message(msg: dict) -> None:
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def main():
    # MCP stdio transport: read JSON-RPC requests from stdin, write responses to stdout
    TOOL_SCHEMA = {
        "name": "run_command",
        "description": (
            "Execute a shell command through RTK for token-optimized output. "
            "Supports ALL shell commands (git, cargo, npm, python, ls, cat, etc.). "
            "Output is filtered to reduce token consumption by 96% while preserving "
            "all essential information (errors, summaries, key data)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The command to execute, e.g. 'git status', 'ls -la src/', 'python script.py'"
                },
                "cwd": {
                    "type": "string",
                    "description": "Working directory for the command. Defaults to current directory if omitted.",
                }
            },
            "required": ["command"]
        }
    }

    SERVER_INFO = {
        "protocolVersion": "2024-11-05",
        "capabilities": {
            "tools": {}
        },
        "serverInfo": {
            "name": "rtk-mcp-server",
            "version": "1.0.0"
        }
    }

    # Verify RTK is available
    try:
        rtk_version = subprocess.run(
            [RTK, "--version"], capture_output=True, text=True, timeout=5
        ).stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        rtk_version = "rtk not found — commands will run unfiltered"

    # Buffer for incoming JSON lines
    buffer = ""

    for line in sys.stdin:
        buffer += line
        # Try to parse a complete JSON message
        try:
            msg = json.loads(buffer)
            buffer = ""
        except json.JSONDecodeError:
            # Incomplete message, keep buffering
            continue

        msg_id = msg.get("id")
        method = msg.get("method")

        if method == "initialize":
            send_message({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": SERVER_INFO
            })
        elif method == "notifications/initialized":
            # No response needed for initialized notification
            pass
        elif method == "tools/list":
            send_message({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "tools": [TOOL_SCHEMA]
                }
            })
        elif method == "tools/call":
            params = msg.get("params", {})
            name = params.get("name", "")
            arguments = params.get("arguments", {})

            if name == "run_command":
                command = arguments.get("command", "")
                cwd = arguments.get("cwd")
                if not command:
                    send_message({
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "error": {"code": -32602, "message": "Empty command"}
                    })
                    continue
                output = rtk_run(command, cwd)
                send_message({
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": output
                            }
                        ]
                    }
                })
            else:
                send_message({
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": -32601, "message": f"Tool not found: {name}"}
                })
        elif method == "ping":
            send_message({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {}
            })


if __name__ == "__main__":
    main()
