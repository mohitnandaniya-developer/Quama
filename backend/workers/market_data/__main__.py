"""CLI entrypoint for the Angel One market-data worker."""

from __future__ import annotations

import asyncio

from workers.market_data.angel_one_worker import main

if __name__ == "__main__":
    asyncio.run(main())
