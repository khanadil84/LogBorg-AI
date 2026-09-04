import os

buffer_limit = int(os.environ.get("LOGBORG_BUFFER_LIMIT", "2"))

print("SERVICE STARTED")
print(f"BUFFER LIMIT: {buffer_limit}")

raise RuntimeError("Stream buffer overflow: unrecoverable test failure")
