import os

memory_mode = os.environ.get("LOGBORG_MEMORY_MODE", "normal")

print("SERVICE STARTED")
print(f"MEMORY MODE: {memory_mode}")

if memory_mode != "sandbox":
    raise RuntimeError("Out of memory: memory exhausted")

print("MEMORY STABLE")
print("HEALTH CHECK: PASS")
