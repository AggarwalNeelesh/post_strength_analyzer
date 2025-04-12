import redis.asyncio as redis

# Redis client setup
redis_client = redis.Redis(
    host="demoredis.birdeye.internal",
    port=6379,
    password="foobird",
    db=10,
    socket_timeout=3,  # milliseconds to seconds
    decode_responses=True
)
