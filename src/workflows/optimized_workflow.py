"""
Optimized and modular workflow implementation
"""
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, END
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from src.utils.states import State
from src.utils import constants
from src.handlers.workflow_handlers import WorkflowHandlers

load_dotenv()


class OptimizedWorkflow:
    """Streamlined workflow with clear separation of concerns"""
    
    def __init__(self):
        self.memory = MemorySaver()
        self.llm = ChatOpenAI(model="gpt-4o")
        self.handlers = WorkflowHandlers(self.llm)
        self.graph = StateGraph(State)
        self._setup_graph()
    
    def _setup_graph(self):
        """Setup the optimized workflow graph"""
        # Add nodes with clear responsibilities
        self.graph.add_node(constants.DIRECTION, self.handlers.handle_direction_classification)
        self.graph.add_node(constants.INFO_COLLECTOR, self.handlers.handle_unified_info_collection)
        self.graph.add_node(constants.SCHEDULE, self.handlers.handle_schedule_booking)
        self.graph.add_node(constants.RESERVATION, self.handlers.handle_reservation)
        self.graph.add_node(constants.CONTACT, self.handlers.handle_contact_submission)
        self.graph.add_node(constants.CART, self.handlers.handle_cart_summary)
        self.graph.add_node(constants.FAILURE_HANDLER, self.handlers.handle_failure)
        
        # Set entry point
        self.graph.set_entry_point(constants.DIRECTION)
        
        # Add streamlined conditional edges
        self.graph.add_conditional_edges(
            constants.DIRECTION,
            self._route_direction,
            [constants.INFO_COLLECTOR, END]
        )
        
        self.graph.add_conditional_edges(
            constants.INFO_COLLECTOR,
            self._route_info_collection,
            [constants.SCHEDULE, constants.INFO_COLLECTOR, constants.FAILURE_HANDLER, END]
        )
        
        self.graph.add_conditional_edges(
            constants.SCHEDULE,
            self._route_schedule,
            [constants.RESERVATION, constants.FAILURE_HANDLER]
        )
        
        self.graph.add_conditional_edges(
            constants.RESERVATION,
            self._route_reservation,
            [constants.INFO_COLLECTOR, constants.FAILURE_HANDLER]
        )
        
        self.graph.add_conditional_edges(
            constants.CONTACT,
            self._route_contact,
            [constants.CART, constants.FAILURE_HANDLER]
        )
        
        self.graph.add_conditional_edges(
            constants.CART,
            self._route_cart,
            [constants.DIRECTION, END, constants.CART]
        )
        
        self.graph.add_conditional_edges(
            constants.FAILURE_HANDLER,
            self._route_failure,
            [END, constants.INFO_COLLECTOR, constants.DIRECTION]
        )
    
    def _route_direction(self, state: State) -> str:
        """Route after direction classification"""
        current_step = state.get("current_step", END)
        if current_step == constants.PRODUCT_TYPE:
            # Set the step for info collector to handle product type
            state["current_step"] = constants.PRODUCT_TYPE
            return constants.INFO_COLLECTOR
        return current_step
    
    def _route_info_collection(self, state: State) -> str:
        """Route after info collection based on current step and state"""
        if state.get("failure_step", False):
            return constants.FAILURE_HANDLER
        
        current_step = state.get("current_step", END)
        
        # If we're still in info collection mode, continue there
        if current_step in {constants.PRODUCT_TYPE, constants.SCHEDULE_INFO, constants.CONTACT_INFO}:
            return constants.INFO_COLLECTOR
        
        return current_step
    
    def _route_schedule(self, state: State) -> str:
        """Route after schedule booking"""
        if state.get("failure_step", False):
            return constants.FAILURE_HANDLER
        return state.get("current_step", END)
    
    def _route_reservation(self, state: State) -> str:
        """Route after reservation"""
        if state.get("failure_step", False):
            return constants.FAILURE_HANDLER
        
        current_step = state.get("current_step", END)
        if current_step == constants.CONTACT_INFO:
            # Set the step for info collector to handle contact info
            state["current_step"] = constants.CONTACT_INFO
            return constants.INFO_COLLECTOR
        
        return current_step
    
    def _route_contact(self, state: State) -> str:
        """Route after contact submission"""
        if state.get("failure_step", False):
            return constants.FAILURE_HANDLER
        return state.get("current_step", END)
    
    def _route_cart(self, state: State) -> str:
        """Route after cart summary"""
        if state.get("failure_step", False):
            return constants.FAILURE_HANDLER
        return state.get("current_step", END)
    
    def _route_failure(self, state: State) -> str:
        """Route after failure handling"""
        current_step = state.get("current_step", END)
        
        # If we're going back to info collection steps, route through info collector
        if current_step in {constants.PRODUCT_TYPE, constants.SCHEDULE_INFO, constants.CONTACT_INFO}:
            return constants.INFO_COLLECTOR
        
        return current_step
    
    def compile(self):
        """Compile the workflow graph"""
        return self.graph.compile(self.memory)
    
    def compile_for_langsmith(self):
        """Compile without memory for LangSmith"""
        return self.graph.compile()


# Create the optimized workflow instance
optimized_workflow = OptimizedWorkflow()
compiled_graph = optimized_workflow.compile()
langsmith_graph = optimized_workflow.compile_for_langsmith()
