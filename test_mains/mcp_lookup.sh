#!/bin/bash
# connect to an MCP server (running locally in docker) and provide a STDIO interface to it.
# requires npx (npm package runner)
npx -y "mcp-remote@latest" "http://localhost:9014/api/mcp/"