import os

buffer_limit = int(os.environ.get("LOGBORG_BUFFER_LIMIT", "2"))
incoming_chunks = ["request-1", "request-2", "request-3", "request-4"]

print("SERVICE STARTED")
print(f"BUFFER LIMIT: {buffer_limit}")

if len(incoming_chunks) > buffer_limit:
    raise RuntimeError(
        f"Stream buffer overflow: {len(incoming_chunks)} chunks > limit {buffer_limit}"
    )

print("TRAFFIC STABLE")
print("HEALTH CHECK: PASS")
