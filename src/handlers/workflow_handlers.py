"""
Optimized, modular workflow handlers
"""
from typing import Dict, Any
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.types import interrupt
from langgraph.graph import END

from src.utils.states import State
from src.utils import constants
from src.utils.instructions import inst_map, failure_instruction_prompt, cart_summary_instruction_prompt
from src.utils.schema import schema_map
from src.services.validation_service import ValidationService
from src.services.state_manager import WorkflowStateManager
from src.services.api_service import ApiService


class WorkflowHandlers:
    """Optimized workflow handlers with clear separation of concerns"""
    
    def __init__(self, llm):
        self.llm = llm
        self.flow_map = {
            constants.PRODUCT_TYPE: constants.SCHEDULE_INFO,
            constants.SCHEDULE_INFO: constants.SCHEDULE,
            constants.SCHEDULE: constants.RESERVATION,
            constants.RESERVATION: constants.CONTACT_INFO,
            constants.CONTACT_INFO: constants.CONTACT,
            constants.CONTACT: constants.CART,
        }
        self.failure_recovery_map = {
            constants.SCHEDULE: constants.SCHEDULE_INFO,
            constants.CONTACT: constants.CONTACT_INFO,
            constants.RESERVATION: constants.SCHEDULE_INFO
        }
    
    async def handle_direction_classification(self, state: State) -> Dict[str, Any]:
        """Handle initial direction classification"""
        try:
            state = WorkflowStateManager.initialize_data(state)
            
            sm = SystemMessage(content=inst_map[constants.DIRECTION])
            structured_llm = self.llm.with_structured_output(schema_map[constants.DIRECTION])
            result = structured_llm.invoke([sm] + state["messages"])
            
            if result["direction"] == constants.BOOKING:
                return WorkflowStateManager.create_success_response(state, constants.PRODUCT_TYPE)
            else:
                return {
                    "current_step": END,
                    "messages": [AIMessage(content=result.get("message", ""))]
                }
                
        except Exception as e:
            error_msg = "I'm having trouble understanding your request. Please try again."
            return {
                "current_step": END,
                "messages": [AIMessage(content=error_msg)]
            }
    
    def handle_unified_info_collection(self, state: State) -> Dict[str, Any]:
        """Unified handler for all info collection steps"""
        current_step = state.get("current_step", "")
        
        if current_step not in {constants.PRODUCT_TYPE, constants.SCHEDULE_INFO, constants.CONTACT_INFO}:
            return {"current_step": END}
        
        try:
            # Check retry limit
            if WorkflowStateManager.should_exit_on_retry_limit(state):
                return {
                    "current_step": constants.FAILURE_HANDLER,
                    "failure_step": True
                }
            
            # Get schema and prepare LLM
            schema = self._get_schema_for_step(state, current_step)
            sm = SystemMessage(content=inst_map[current_step])
            structured_llm = self.llm.with_structured_output(schema)
            
            response = structured_llm.invoke([sm] + state["messages"])
            
            if response.get("human_input"):
                return WorkflowStateManager.create_retry_response(state, response["message"])
            else:
                # Validate the collected data
                is_valid, errors = self._validate_step_data(current_step, response.get(current_step, {}))
                
                if not is_valid:
                    error_message = f"Please correct the following:\n" + "\n".join(f"• {err}" for err in errors)
                    return WorkflowStateManager.create_retry_response(state, error_message)
                
                # Update state with validated data
                state = WorkflowStateManager.update_step_data(state, current_step, response[current_step])
                next_step = self.flow_map.get(current_step, END)
                
                return WorkflowStateManager.create_success_response(state, next_step)
                
        except Exception as e:
            return WorkflowStateManager.create_failure_response(state, f"Error processing {current_step}: {str(e)}")
    
    async def handle_schedule_booking(self, state: State) -> Dict[str, Any]:
        """Handle schedule booking with API calls"""
        try:
            data = state.get("data", {})
            product_type = data.get("product_type")
            schedule_info = data.get("schedule_info", {})
            session_id = state.get("session_id", "00009223581026309436128527")
            
            if product_type == constants.BUNDLE:
                success, result, error = await ApiService.call_bundle_schedule_api(
                    schedule_info.get("arrival", {}),
                    schedule_info.get("departure", {}),
                    session_id
                )
            else:
                success, result, error = await ApiService.call_schedule_api(schedule_info, session_id)
            
            if success:
                state = WorkflowStateManager.update_step_data(state, "schedule", result)
                next_step = self.flow_map.get(constants.SCHEDULE, END)
                return WorkflowStateManager.create_success_response(state, next_step)
            else:
                return WorkflowStateManager.create_failure_response(state, error or "Schedule booking failed")
                
        except Exception as e:
            return WorkflowStateManager.create_failure_response(state, f"Schedule booking error: {str(e)}")
    
    async def handle_reservation(self, state: State) -> Dict[str, Any]:
        """Handle reservation creation"""
        try:
            data = state.get("data", {})
            product_type = data.get("product_type")
            schedule_info = data.get("schedule_info", {})
            schedule_result = data.get("schedule", {})
            session_id = state.get("session_id", "00081400083250224448591690")
            
            # Build reservation payload
            reservation_payload = ApiService.build_reservation_payload(
                product_type, schedule_info, schedule_result, session_id
            )
            
            success, result, error = await ApiService.call_reservation_api(reservation_payload)
            
            if success:
                state = WorkflowStateManager.update_step_data(state, "reservation", result)
                next_step = self.flow_map.get(constants.RESERVATION, END)
                return WorkflowStateManager.create_success_response(state, next_step)
            else:
                return WorkflowStateManager.create_failure_response(state, error or "Reservation failed")
                
        except Exception as e:
            return WorkflowStateManager.create_failure_response(state, f"Reservation error: {str(e)}")
    
    async def handle_contact_submission(self, state: State) -> Dict[str, Any]:
        """Handle contact information submission"""
        try:
            data = state.get("data", {})
            contact_info = data.get("contact_info", {})
            reservation_result = data.get("reservation", {})
            session_id = state.get("session_id", "00081400083250224448591690")
            
            # Build contact payload
            contact_payload = ApiService.build_contact_payload(contact_info, reservation_result, session_id)
            
            success, result, error = await ApiService.call_contact_api(contact_payload)
            
            if success:
                # Update cart
                cart = data.get("cart", {})
                cart_item_id = contact_payload["cartitemid"]
                
                cart[cart_item_id] = {
                    "product": data.get("product_type"),
                    "passengers": reservation_result.get("ticketsrequested", 1),
                    "amount": reservation_result.get("retail", "0.00"),
                    "contact": contact_payload
                }
                
                state = WorkflowStateManager.update_step_data(state, "cart", cart)
                state = WorkflowStateManager.update_step_data(state, "contact", result)
                
                next_step = self.flow_map.get(constants.CONTACT, END)
                return WorkflowStateManager.create_success_response(state, next_step)
            else:
                return WorkflowStateManager.create_failure_response(state, error or "Contact submission failed")
                
        except Exception as e:
            return WorkflowStateManager.create_failure_response(state, f"Contact submission error: {str(e)}")
    
    def handle_cart_summary(self, state: State) -> Dict[str, Any]:
        """Handle cart summary and next steps"""
        try:
            cart = state.get("data", {}).get("cart", {})
            
            if not cart:
                message = "Your cart is currently empty. Let's start by adding some items!"
                return WorkflowStateManager.create_success_response(state, constants.PRODUCT_TYPE, message)
            
            # Generate cart summary
            prompt = cart_summary_instruction_prompt.format(cart=cart)
            sm = SystemMessage(content=prompt)
            structured_llm = self.llm.with_structured_output(schema_map[constants.CART])
            response = structured_llm.invoke([sm] + state.get("messages", []))
            
            if response.get("human_input"):
                return WorkflowStateManager.create_retry_response(state, response["message"])
            else:
                direction = response.get("direction", "end")
                if direction == "direction":
                    return WorkflowStateManager.create_success_response(state, constants.DIRECTION, response["message"])
                else:
                    return {
                        "messages": [AIMessage(content=response["message"])],
                        "current_step": END
                    }
                    
        except Exception as e:
            return WorkflowStateManager.create_failure_response(state, f"Cart summary error: {str(e)}")
    
    def handle_failure(self, state: State) -> Dict[str, Any]:
        """Enhanced failure handler with recovery options"""
        try:
            current_step = state.get("current_step", "")
            errors = WorkflowStateManager.get_current_errors(state)
            error_message = errors[0] if errors else "An unexpected error occurred"
            
            prompt = failure_instruction_prompt.format(step=current_step, error=error_message)
            sm = SystemMessage(content=prompt)
            structured_llm = self.llm.with_structured_output(schema_map[constants.FAILURE_HANDLER])
            response = structured_llm.invoke([sm] + state["messages"])
            
            if response["end"]:
                state = WorkflowStateManager.clear_validation_errors(state)
                return WorkflowStateManager.create_success_response(state, constants.DIRECTION, response["message"])
            
            if response["human_input"]:
                return WorkflowStateManager.create_retry_response(state, response["message"])
            else:
                # Determine recovery step
                recovery_step = self.failure_recovery_map.get(current_step, constants.PRODUCT_TYPE)
                state = WorkflowStateManager.clear_validation_errors(state)
                return WorkflowStateManager.create_success_response(state, recovery_step, response["message"])
                
        except Exception as e:
            return {
                "current_step": END,
                "messages": [AIMessage(content="I'm experiencing technical difficulties. Please try again later.")]
            }
    
    def _get_schema_for_step(self, state: State, step: str):
        """Get appropriate schema for the current step"""
        if step == constants.SCHEDULE_INFO:
            product_type = state.get("data", {}).get("product_type")
            return schema_map[step](product_type)
        elif step == constants.CONTACT_INFO:
            schedule_info = state.get("data", {}).get("schedule_info", {})
            passengers = schedule_info.get("passengers", schedule_info.get("pessanger_count", {}))
            adult_count = passengers.get("adult", 1) if isinstance(passengers, dict) else 1
            child_count = passengers.get("children", 0) if isinstance(passengers, dict) else 0
            return schema_map[step](adult_count=adult_count, child_count=child_count)
        else:
            return schema_map[step]
    
    def _validate_step_data(self, step: str, data: Dict[str, Any]) -> tuple[bool, list[str]]:
        """Validate data for specific step"""
        if step == constants.PRODUCT_TYPE:
            return ValidationService.validate_product_type(data)
        elif step == constants.SCHEDULE_INFO:
            product_type = data.get("product_type")
            if product_type == constants.BUNDLE:
                return ValidationService.validate_bundle_schedule(data)
            else:
                return ValidationService.validate_schedule_info(data)
        elif step == constants.CONTACT_INFO:
            return ValidationService.validate_contact_info(data)
        else:
            return True, []
