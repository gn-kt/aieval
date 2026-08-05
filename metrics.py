from prometheus_client import Counter, Gauge, Histogram

task_created_total = Counter(
    "rag_task_created_total",
    "Total number of RAG tasks created",
    ["status"],
)

task_duration_seconds = Histogram(
    "rag_task_duration_seconds",
    "RAG task processing duration in seconds",
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0],
)

active_websocket_connections = Gauge(
    "rag_ws_connections_active",
    "Number of active WebSocket connections",
)
