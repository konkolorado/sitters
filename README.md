# Sitters

Babysit your async Python functions with `sitters` that can provide:

- timeouts
- retries
- caching
- pausing
- startup hooks
- completion hooks
- exception hooks
- timeout hooks
- cancellation hooks
- restart hooks

<details>

<summary>Run arbitrary async functions in response to your code's state</summary>

### Running hook(s) when your code is about to start

```python
import asyncio

from sitters import sit

async def on_startup():
    print("Our code is starting now!")

@sit(startup_hooks=[on_startup])
async def sleeper(sleep_s: int):
    for i in range(sleep_s):
        await asyncio.sleep(1)
        print(f"We've slept {i} seconds")

asyncio.run(sleeper(4))
```

### Running hooks when your code completes

```python
import asyncio

from sitters import sit

async def on_completion():
    print("Our code completed!")

@sit(completion_hooks=[on_completion])
async def sleeper(sleep_s: int):
    for i in range(sleep_s):
        await asyncio.sleep(1)
        print(f"We've slept {i} seconds")

asyncio.run(sleeper(4))
```

### Run hooks throughout your code's execution

```python
import asyncio

from sitters import sit

async def on_startup():
    print("Our code is starting now!")

async def on_completion():
    print("Our code completed!")

async def on_exception():
    print("Our code encountered an exception")

@sit(
    startup_hooks=[on_startup], 
    completion_hooks=[on_completion], 
    exception_hooks=[on_exception])
async def sleeper(sleep_s: int):
    for i in range(sleep_s):
        await asyncio.sleep(1)
        print(f"We've slept {i} seconds")

asyncio.run(sleeper(4))
```

The supported lifecycle events for running hooks are:
- on startup
- on completion
- on exception(s)
- on timeouts
- on cancellation
- on restarts

</details>

<details>

<summary>Control how long your code runs with timeouts</summary>

Note that tasks that timeout trigger it's timeout hooks to be run and the task
itself will return `None`.

```python
import asyncio

from sitters import sit

@sit(timeout=3)
async def sleeper(sleep_s: int):
    await asyncio.sleep(4)
    print(f"We've slept {sleep_s} seconds")

result = asyncio.run(sleeper(4))
print(result)
```

</details>

<details>

<summary>Flexibly customize your code's retry behavior using `tenacity`'s `retry` function</summary>

Note that `tenacity`'s `retry` function expects to be used as a decorator, but
here we're using that decorator's return value.

```python
import asyncio

from tenacity import retry, stop_after_attempt
from sitters import sit

TRIES = 0
RETRIES = 5

@sit(retry=retry(stop=stop_after_attempt(RETRIES)))
async def exceptional_func():
    global TRIES

    TRIES += 1
    if TRIES == RETRIES:
        return "I am complete"
    else:
        print("I am exceptional")
        raise Exception


result = asyncio.run(exceptional_func())
print(result)
```

</details>


<details>

<summary>Cache your function's results across invocations</summary>

Note that only caches types built into `cachetools` are supported.

```python
import asyncio

from cachetools import LRUCache
from sitters import sit


@sit(cache=LRUCache(maxsize=5))
async def intense_math(a: int, b: int):
    print("Im doing intense math")
    return a * b


for _ in range(5):
    result = asyncio.run(intense_math(3,5))
    print(result)
```

</details>

<details>

<summary>Support for pausing, restarting, resuming, and cancelling your code</summary>

### Sitters listen to and respond to signals send to your process

Note that Windows does not natively support signals and this functionality is
likely not to work.

```python
import asyncio
import os

from sitters import sit

@sit()
async def sleeper(sleep_s: int):
    for i in range(1, sleep_s+1):
        await asyncio.sleep(1)
        print(f"We've slept {i} seconds")

print(f"This is our process ID: {os.getpid()}")
asyncio.run(sleeper(5))
```

### Use the sitter to pause your code's execution

Take the `sitter`'s process ID and send it a `SIGUSR1`:

```bash
kill -SIGUSR1 <PID>
```

### Use the sitter to unpause your code's execution

Send your `sitter` a `SIGUSR2`:

```bash
kill -SIGUSR2 <PID>
```

### Restart your code

If you need to restart your code, send the `sitter` a `SIGHUP`:

```bash
kill -1 <PID>
```

Note that sending a `SIGHUP` will cause trigger the `sitter`'s restart hooks.

### Stop or cancel your code

If you need to stop the `sitter`, you can `CTRL-C` it or send it a `SIGTERM`:

```bash
kill -15 <PID>
```

Note that sending a kill signal will trigger the `sitter`'s cancellation hooks.

</details>