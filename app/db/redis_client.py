import redis.asyncio as redis

# Redis client setup
redis_client = redis.Redis(
    host="",
    port=6379,
    password="",
    db=10,
    socket_timeout=3,  # milliseconds to seconds
    decode_responses=True
)
