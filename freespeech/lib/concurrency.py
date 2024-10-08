import asyncio
import concurrent.futures
from typing import Any, Callable


async def run_in_thread_pool(func: Callable[..., Any], *args: Any) -> Any:
    loop = asyncio.get_running_loop()
    with concurrent.futures.ThreadPoolExecutor() as pool:
        return await loop.run_in_executor(pool, func, *args)


async def run_in_process_pool(func: Callable[..., Any]) -> Any:
    loop = asyncio.get_running_loop()
    with concurrent.futures.ProcessPoolExecutor() as pool:
        return await loop.run_in_executor(pool, func)
