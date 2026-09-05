import os

buffer_limit = int(os.environ.get("LOGBORG_BUFFER_LIMIT", "2"))
incoming_chunks = ["request-1", "request-2", "request-3", "request-4"]

print("SERVICE STARTED")
print(f"BUFFER LIMIT: {buffer_limit}")

if len(incoming_chunks) > buffer_limit:
    raise RuntimeError(
        f"Stream buffer overflow: {len(incoming_chunks)} chunks > limit {buffer_limit}"
    )

if (
    os.environ.get("LOGBORG_ADAPTIVE_TEST") == "1"
    and buffer_limit == 8
    and os.environ.get("LOGBORG_MEMORY_MODE") != "sandbox"
):
    raise RuntimeError("Out of memory: memory exhausted")

print("TRAFFIC STABLE")
print("HEALTH CHECK: PASS")
