import aiofiles

async def main(page_slug: str, document: str):
    async with aiofiles.open(f"./wiki/{page_slug}.html", mode='w') as f:
        try:
            await f.write(document)
            print(f"✓ {page_slug}-article has been correctly written to disk")
        except Exception as e:
            print(f"✕ error for {page_slug}-article => {e}")
