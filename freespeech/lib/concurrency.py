import asyncio
import concurrent.futures
from typing import Any, Callable


async def run_in_thread_pool(func: Callable[..., Any], *args: Any) -> Any:
    with concurrent.futures.ThreadPoolExecutor() as pool:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(pool, func, *args)


async def run_in_process_pool(func: Callable[..., Any], *args: Any) -> Any:
    with concurrent.futures.ThreadPoolExecutor() as pool:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(pool, func, *args)
