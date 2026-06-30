# AGENTS.md

When writing Python scripts, do not use argument parsing by default. If code needs configurable values, set them as constants near the top of the file like an SDK. Add argument parsing only when explicitly requested.

## Project Notes

- For laptop edge deployments, browser API calls should stay same-origin through the laptop proxy. Use `VITE_EDGE_MODE=true`; reserve `VITE_EDGE_MODE=false` with `VITE_API_URL=<pc-origin>` for direct operator-web development only. See `agents_docs/troubleshooting/origin_routing.md`.
- Do not store laptop LAN IPs in `laptop/.env`. Use `npm run laptop` / `npm --prefix laptop run start` so `laptop/scripts/start-laptop-stack.mjs` detects the current LAN IP on macOS or Windows and passes `LAPTOP_LAN_HOST` plus `EDGE_PUBLIC_ORIGIN` to Docker Compose for that run.
- Do not use `EXPO_PUBLIC_API_BASE`, `EXPO_PUBLIC_SIGNALING_URL`, or `EXPO_PUBLIC_UPLOAD_URL` for Expo phone routing. The operator QR/deep link must carry the selected laptop origin, and the app derives API, WebSocket, upload, and certificate URLs from that origin at runtime.
- For Expo phone app validation, run TypeScript from `laptop/apps/camera-mobile` directly with `npx tsc --noEmit`; do not rely on the parent `npm --prefix laptop run typecheck:camera` wrapper until it is fixed. See `agents_docs/troubleshooting/expo_phone_app.md`.
- Laptop-local footage storage is controlled by EdgeRelay. Prefer the host storage agent for normal laptop folders that are not Docker-mounted; keep Docker volume storage as fallback/backward compatibility. See `agents_docs/setup/host_storage_agent.md` and `agents_docs/setup/laptop_storage.md`.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

When the user types `/graphify`, invoke the `skill` tool with `skill: "graphify"` before doing anything else.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
