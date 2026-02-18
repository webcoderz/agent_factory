import asyncio

async def execute_tasks_parallel(ctx, ledger, tasks, handler_map, max_concurrency: int = 4):
    sem = asyncio.Semaphore(max_concurrency)

    async def run_one(task):
        async with sem:
            handler = handler_map[task.kind]
            return task, await handler(ctx, task, ledger)

    pairs = await asyncio.gather(*[run_one(t) for t in tasks])
    for task, evidence_list in pairs:
        ledger.add_evidence(task.id, evidence_list)