# src/controllers/workflow_controller.py
from langchain_core.messages import HumanMessage
from langgraph.types import Command
from src.scripts.workflow import compiled_graph

class Chat:
    def __init__(self, message: str, checkpoint_id: str | int | None = None):
        self.message = message
        self.checkpoint_id = checkpoint_id
        self.config = {"configurable": {"thread_id": checkpoint_id}}

    async def run(self) -> str:
        snapshot = compiled_graph.get_state(self.config)

        if snapshot.next:
            print("[Workflow] Resuming graph with message:", self.message)
            result = await compiled_graph.ainvoke(Command(resume=self.message), config=self.config)
        else:
            print("[Workflow] Starting new graph with message:", self.message)
            result = await compiled_graph.ainvoke({"messages": [HumanMessage(content=self.message)]}, config=self.config)

        return result
