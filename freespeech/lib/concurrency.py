import asyncio
import concurrent.futures
from typing import Any, Callable

THREAD_POOL = concurrent.futures.ThreadPoolExecutor()
PROCESS_POOL = concurrent.futures.ProcessPoolExecutor()


async def run_in_thread_pool(func: Callable[..., Any], *args: Any) -> Any:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(THREAD_POOL, func, *args)


async def run_in_process_pool(func: Callable[..., Any]) -> Any:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(PROCESS_POOL, func)
