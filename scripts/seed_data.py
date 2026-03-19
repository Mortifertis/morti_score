import asyncio

from app.db.session import AsyncSessionLocal
from app.services.seed import SeedService


async def main() -> None:
    async with AsyncSessionLocal() as session:
        result = await SeedService(session).seed_all()
        print(result)


if __name__ == "__main__":
    asyncio.run(main())
