import asyncio
from fastapi import BackgroundTasks, FastAPI

app = FastAPI()

async def logging_task():
    print("Background task started!")
    await asyncio.sleep(10)  # Delay for 10 seconds
    # Write your logging code here
    print("Background task completed!")

@app.get("/")
def read_root(background_tasks: BackgroundTasks):
    background_tasks.add_task(logging_task)
    return {"Hello": "FastAPI"}
