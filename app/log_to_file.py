import aiofiles
import arrow


async def write(filename: str, msg: str):
    async with aiofiles.open(f"./logs/{filename}.log", mode='a') as f:
        try:
            now = arrow.utcnow()
            ts = now.to('local').format('YYYY-MM-DD HH:mm:ss')
            line = f"{ts} :: {msg}"

            await f.write(line)
            print(f"✓ msg appended to {filename}")

        except Exception as e:
            print(f"✕ error while updating log {filename} => {e}")


async def main(filename: str, msg: str, sem):
    if sem is not None:
        async with sem:
            await write(filename, msg)
            
    else:
        await write(filename, msg)
