from langgraph.graph import StateGraph, END
from state import AgentState
from scoring.compare import parse_and_compare
from scoring.rate import rate_resume

workflow = StateGraph(AgentState)
workflow.add_node("compare", parse_and_compare)
workflow.add_node("rate", rate_resume)

workflow.set_entry_point("compare")
workflow.add_edge("compare", "rate")
workflow.add_edge("rate", END)

app = workflow.compile()
