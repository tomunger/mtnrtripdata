# Services

Use the command:

    docker compose --env-file .env -f deploy/postgres.yaml up -d

`--env-file` should define `NEO4J_PASSWORD`

## neo4j MCP

A neo4j MCP is included in the set of docker containers.  This may be access from Claude with this
configuration.  Requires 'npm' and Node.

    {
        "mcpServers": {
            "mountaineers": {
            "command": "npx",
            "args": ["-y", "mcp-remote@latest", "http://localhost:9014/api/mcp/"]
            }
        }
    }