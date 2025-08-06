from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import add_messages, StateGraph, END
from langgraph.types import Command, interrupt
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.graph import add_messages 
from src.utils.states import State
from langchain_core.messages import HumanMessage , AIMessage , SystemMessage
from src.utils.instructions import inst_map , failure_instruction_prompt , cart_summary_instruction_prompt
import src.utils.constants as constants
from src.utils.schema import schema_map
from src.services.mcp_client import get_mcpInstance , McpClient
load_dotenv()
import json
import traceback
import sys
from typing import Union

def print_exception_group(exc: BaseException, indent: int = 0):
    prefix = " " * indent
    if hasattr(exc, "exceptions"):  # It's an ExceptionGroup
        print(f"{prefix}🔍 ExceptionGroup ({exc.__class__.__name__}): {exc}")
        for i, sub_e in enumerate(exc.exceptions):
            print(f"{prefix}--- Sub-exception {i+1} ---")
            print_exception_group(sub_e, indent + 4)
    else:
        print(f"{prefix}⚠️ {exc.__class__.__name__}: {exc}")
        traceback.print_exception(type(exc), exc, exc.__traceback__, file=sys.stdout)

        
memory = MemorySaver()

llm = ChatOpenAI(model="gpt-4o")

graph = StateGraph(State)

memory = MemorySaver()



flow_serializer = {
    constants.PRODUCT_TYPE : constants.SCHEDULE_INFO , 
    constants.SCHEDULE_INFO : constants.SCHEDULE,
    constants.SCHEDULE : constants.RESERVATION,
    constants.RESERVATION : constants.CONTACT_INFO , 
    constants.CONTACT_INFO : constants.CONTACT , 
    constants.CONTACT : constants.CART,
}

failuer_serializer = {
    constants.SCHEDULE: constants.SCHEDULE_INFO , 
    constants.CONTACT: constants.CONTACT_INFO,
    constants.RESERVATION: constants.SCHEDULE_INFO
}

# flow nodes
async def classifier(state:State):
    try: 
        sm = SystemMessage(content = inst_map[constants.DIRECTION])
        structured_llm = llm.with_structured_output(schema_map[constants.DIRECTION])
        result =  structured_llm.invoke([sm] + state["messages"])
        print("direction : " , result)
        if result["direction"] == constants.BOOKING:
            return {
            "current_step": constants.PRODUCT_TYPE,
            }
        else:            
            return {
                "current_step": END ,
                "messages": [AIMessage(content= result.get("message" , ""))]
            }
            
    except Exception as e:
        print(f"Error in direction: {e}")
        return {
            "current_step": END,
            "messages": [AIMessage(content="There was some error while processing your request , please retry.")]
        }

def info_collector(state: State):
    print('info collector triggered', state)

    current_step = state.get("current_step", "")
    print('before condition', current_step)
    
    if current_step in {constants.PRODUCT_TYPE, constants.SCHEDULE_INFO, constants.CONTACT_INFO}:
        sm = SystemMessage(content=inst_map[current_step])
        schema = schema_map[current_step]
        
        # Handle different schema types based on current step
        if current_step == constants.SCHEDULE_INFO:
            schema = schema_map[current_step](state["data"]["product_type"])
            print("current schema", schema)
            structured_llm = llm.with_structured_output(schema)
        elif current_step == constants.CONTACT_INFO:
            # Fixed: Use correct field name 'passengers' instead of 'pessanger_count'
            schedule_info = state["data"]["schedule_info"]
            passenger_count = schedule_info.get("passengers", schedule_info.get("pessanger_count", {}))
            adult_count = passenger_count.get("adult", 1) if isinstance(passenger_count, dict) else 1
            child_count = passenger_count.get("children", 0) if isinstance(passenger_count, dict) else 0
            
            schema = schema_map[current_step](adult_count=adult_count, child_count=child_count)
            print("current schema", schema)
            structured_llm = llm.with_structured_output(schema)
        else:
            structured_llm = llm.with_structured_output(schema)
        
        response = structured_llm.invoke([sm] + state["messages"])
        print('response from ai', response)
        
        if response.get("human_input"):
            print('Triggering interrupt', response["message"])
            user_input = interrupt(value=response["message"])
            return {
                "messages": [HumanMessage(content=user_input)],
                "executionFlow": state.get("executionFlow", []) + [f"{current_step} retry"],
                "data": state.get("data") or {}
            }
        else:
            # Enhanced data handling with validation
            updated_data = state.get("data") or {}
            updated_data[current_step] = response[current_step]
            
            # Add validation tracking
            if "validation_errors" not in updated_data:
                updated_data["validation_errors"] = []
            
            return {
                "current_step": flow_serializer[current_step],
                "data": updated_data,
                "executionFlow": state.get("executionFlow", []) + [current_step]
            }
            
    return {
        "current_step": END
    }

def router_next(state:State):
    current_step = state.get("current_step", "direction")
    print(f"Routing decision: current_step = {current_step} {state}" )
    
    if(state.get("failure_step" , False)):
        return constants.FAILURE_HANDLER
    
    return current_step

def failure_handler(state: State):
    print("failure triggered")
    current_step = state["current_step"]
    
    # Get more specific error information
    error_details = state.get("data", {}).get("validation_errors", ["network error"])
    error_message = error_details[0] if error_details else "network error"
    
    prompt = failure_instruction_prompt.format(step=current_step, error=error_message)
    sm = SystemMessage(content=prompt)
    structuredllm = llm.with_structured_output(schema_map[constants.FAILURE_HANDLER])
    response = structuredllm.invoke([sm] + state["messages"])
    print("response from failure llm:", response)    
    
    if response["end"]:
        return {
            "messages": [AIMessage(content=response["message"])], 
            "current_step": constants.DIRECTION,
            "failure_step": False,
            "data": {**(state.get("data") or {}), "validation_errors": []}  # Clear errors
        }
    
    if response["human_input"]:
        print('Triggering interrupt', response["message"])
        user_input = interrupt(value=response["message"])
        return {
            "messages": [HumanMessage(content=user_input)],
            "executionFlow": state.get("executionFlow", []) + [f"{current_step} {constants.FAILURE_HANDLER} retry"],
            "failure_step": False  # Reset failure state for retry
        }
    else:
        return {
            "current_step": failuer_serializer[current_step],
            "messages": [AIMessage(content=response["message"])], 
            "failure_step": False,
            "executionFlow": state.get("executionFlow", []) + [f"{current_step} {constants.FAILURE_HANDLER} resolved"]
        }
       
    
# Application nodes
async def schedule(state: State):
    print("🔄 [schedule] Starting schedule step...")
    currentState = state
    mcp_client: McpClient = await get_mcpInstance()
    current_step = state.get("current_step")
    print(f"ℹ️ [schedule] Current step: {current_step}")

    # Ensure 'schedule' dict exists in data
    if not currentState.get("data"):
        currentState["data"] = {}
    if "schedule" not in currentState["data"]:
        currentState["data"]["schedule"] = {}

    data = state.get("data", {})
    isBundle = data.get("product_type") == constants.BUNDLE
    scheduleData = data.get("schedule_info", {})
    print(f"🧳 [schedule] Is Bundle: {isBundle}")

    isSchedule = False
    session_id = state.get("session_id", "00009223581026309436128527")  # Use session from state

    def parse_if_str(result):
        if isinstance(result, str):
            try:
                import json
                return json.loads(result)
            except Exception as e:
                print(f"❌ [schedule] JSON parse error: {e}")
                # Add to validation errors
                if "validation_errors" not in currentState["data"]:
                    currentState["data"]["validation_errors"] = []
                currentState["data"]["validation_errors"].append(f"JSON parse error: {e}")
                return {}
        return result

    def has_schedule_id(result):
        result = parse_if_str(result)
        return isinstance(result, dict) and result.get("scheduleId")

    try:
        if not isBundle:
            print("✈️ [schedule] Processing NON-BUNDLE schedule...")
            scheduleObj = {
                "airportid": scheduleData.get("airportid"),
                "direction": scheduleData.get("direction"),
                "traveldate": scheduleData.get("traveldate"),
                "flightId": scheduleData.get("flightId"),
                "sessionid": session_id
            }
            print(f"📦 [schedule] Schedule request payload: {scheduleObj}")

            schedule_result = await mcp_client.invoke_tool("schedule", scheduleObj)
            print(f"✅ [schedule] Schedule result: {schedule_result}")
            isSchedule = has_schedule_id(schedule_result)
            currentState["data"]["schedule"] = schedule_result            

        else:
            print("🔗 [schedule] Processing BUNDLE schedule (arrival + departure)...")

            arrivalObj = {
                "airportid": scheduleData.get("arrival", {}).get("airportid"),
                "direction": scheduleData.get("arrival", {}).get("direction"),
                "traveldate": scheduleData.get("arrival", {}).get("traveldate"),
                "flightId": scheduleData.get("arrival", {}).get("flightId"),
                "sessionid": session_id
            }

            departureObj = {
                "airportid": scheduleData.get("departure", {}).get("airportid"),
                "direction": scheduleData.get("departure", {}).get("direction"),
                "traveldate": scheduleData.get("departure", {}).get("traveldate"),
                "flightId": scheduleData.get("departure", {}).get("flightId"),
                "sessionid": session_id
            }

            print(f"📦 [schedule] Arrival payload: {arrivalObj}")
            print(f"📦 [schedule] Departure payload: {departureObj}")

            arrival_result = await mcp_client.invoke_tool("schedule", arrivalObj)
            departure_result = await mcp_client.invoke_tool("schedule", departureObj)
            
            print(f"✅ [schedule] Arrival result: {arrival_result}")
            print(f"✅ [schedule] Departure result: {departure_result}")

            if has_schedule_id(arrival_result) and has_schedule_id(departure_result):
                isSchedule = True
                currentState["data"]["schedule"] = {
                    "arrival": arrival_result,
                    "departure": departure_result
                }
            else:
                print("⚠️ [schedule] Either arrival or departure schedule is missing scheduleId.")
                currentState["data"]["schedule"] = {"arrival": arrival_result or {}, "departure": departure_result or {}}

        if isSchedule:
            print("✅ [schedule] Schedule step successful. Proceeding to next step.")
            return {
                **currentState, 
                "current_step": flow_serializer[current_step],
                "executionFlow": state.get("executionFlow", []) + [current_step]
            }

    except Exception as e:
        print(f"❌ [schedule] Exception occurred: {e}")
        print_exception_group(e)
        
        # Add error to validation_errors
        if "validation_errors" not in currentState["data"]:
            currentState["data"]["validation_errors"] = []
        currentState["data"]["validation_errors"].append(f"Schedule API error: {str(e)}")

    print("❌ [schedule] Schedule step failed.")
    return {
        **currentState, 
        "failure_step": True,
        "executionFlow": state.get("executionFlow", []) + [f"{current_step} failed"]
    }


async def reservation(state: State):
    print("🛫 [reservation] Executing reservation step...")

    mcp_client = await get_mcpInstance()
    current_step = state.get("current_step", "")
    data = state.get("data", {})

    product_type = data.get("product_type")
    schedule_info = data.get("schedule_info", {})
    schedule_data = data.get("schedule", {})

    try:
        # 🔐 Parse schedule_data if it's a JSON string
        if isinstance(schedule_data, str):
            schedule_data = json.loads(schedule_data)

        # 🔐 Parse nested arrival/departure if they're strings
        if isinstance(schedule_data.get("arrival"), str):
            schedule_data["arrival"] = json.loads(schedule_data["arrival"])
        if isinstance(schedule_data.get("departure"), str):
            schedule_data["departure"] = json.loads(schedule_data["departure"])

        # 🧍‍♂️ Get passenger counts - handle both old and new field names
        passengers = schedule_info.get("passengers") or schedule_info.get("pessanger_count", {})
        adult_tickets = passengers.get("adult", 0) if isinstance(passengers, dict) else 1
        child_tickets = passengers.get("children", 0) if isinstance(passengers, dict) else 0

        session_id = state.get("session_id", "00081400083250224448591690")

        # 🧱 Build reservation payload
        if product_type == constants.BUNDLE:
            reservation_data = {
                "adulttickets": adult_tickets,
                "childtickets": child_tickets,
                "scheduleData": {
                    "A": {"scheduleId": schedule_data.get("arrival", {}).get("scheduleId", 0)},
                    "D": {"scheduleId": schedule_data.get("departure", {}).get("scheduleId", 0)}
                },
                "productid": product_type,
                "sessionid": session_id
            }
        else:
            schedule_id = schedule_data.get("scheduleId", 0)
            reservation_data = {
                "adulttickets": adult_tickets,
                "childtickets": child_tickets,
                "scheduleData": {
                    "A": {"scheduleId": schedule_id if product_type == constants.ARRIVAL else 0},
                    "D": {"scheduleId": schedule_id if product_type == constants.DEPARTURE else 0}
                },
                "productid": product_type,
                "sessionid": session_id
            }

        print(f"📦 [reservation] Payload: {reservation_data}")

        # 🚀 Call MCP tool
        reservation_result = await mcp_client.invoke_tool("reservation", reservation_data)
        print(f"✅ [reservation] Result: {reservation_result}")

        # Parse result if it's a string
        if isinstance(reservation_result, str):
            reservation_result = json.loads(reservation_result)

        data["reservation"] = reservation_result
        
        if reservation_result.get("cartitemid"):
            # 🔁 Proceed to next step
            return {
                "data": data,
                "current_step": flow_serializer[current_step],
                "executionFlow": state.get("executionFlow", []) + [current_step]
            }
        else:
            # Add error details
            if "validation_errors" not in data:
                data["validation_errors"] = []
            data["validation_errors"].append("Reservation failed: No cart item ID received")
            
            return {
                **state,
                "failure_step": True,
                "data": data,
                "executionFlow": state.get("executionFlow", []) + [f"{current_step} failed"]
            }
            
    except Exception as e:
        print(f"❌ [reservation] Error during reservation: {e.__class__.__name__}: {e}")
        print_exception_group(e)
        
        # Add error to validation_errors
        if "validation_errors" not in data:
            data["validation_errors"] = []
        data["validation_errors"].append(f"Reservation API error: {str(e)}")
        
        return {
            **state,
            "failure_step": True,
            "data": data,
            "executionFlow": state.get("executionFlow", []) + [f"{current_step} failed"]
        }


async def contact(state: State):
    print('📞 [contact] Executing contact step...')
    
    mcp_client = await get_mcpInstance()
    current_step = state["current_step"]
    data = state.get("data", {})

    try:
        # Parse reservation data
        reservation = data.get("reservation", {})
        if isinstance(reservation, str):
            reservation = json.loads(reservation)

        # Get contact info - handle both old and new structure
        contact_info = data.get("contact_info", {})
        
        # Handle different contact info structures
        if "passengerDetails" in contact_info:
            # Old structure with passenger details
            first_adult = contact_info["passengerDetails"]["adults"][0]
            contact_payload = {
                "cartitemid": reservation.get("cartitemid"),
                "email": first_adult.get("email"),
                "firstname": first_adult.get("firstname"),
                "lastname": first_adult.get("lastname"),
                "phone": contact_info.get("contact", {}).get("phone"),
                "title": first_adult.get("title", "Mr"),
                "sessionid": state.get("session_id", "00081400083250224448591690")
            }
        else:
            # New simplified structure
            contact_payload = {
                "cartitemid": reservation.get("cartitemid"),
                "email": contact_info.get("email"),
                "firstname": contact_info.get("firstname"),
                "lastname": contact_info.get("lastname"),
                "phone": contact_info.get("phone"),
                "title": "Mr",  # Default title
                "sessionid": state.get("session_id", "00081400083250224448591690")
            }

        print("📦 [contact] Payload:", contact_payload)

        contact_response = await mcp_client.invoke_tool("contact", contact_payload)
        print("✅ [contact] Response:", contact_response)
        
        # Update cart
        cart = data.get("cart", {})
        cart_item_id = contact_payload["cartitemid"]
        
        cartItems = {
            **cart,
            cart_item_id: {
                "product": data.get("product_type"),
                "passengers": reservation.get("ticketsrequested", 1),
                "amount": reservation.get("retail", "0.00"),
                "contact": contact_payload
            }
        }
        
        updated_data = {
            **data,
            "cart": cartItems,
            "contact": contact_response
        }
        
        return {
            **state,
            "current_step": flow_serializer[current_step],
            "data": updated_data,
            "executionFlow": state.get("executionFlow", []) + [current_step]
        }

    except Exception as e:
        print(f"❌ [contact] Error during contact: {e.__class__.__name__}: {e}")
        print_exception_group(e)
        
        # Add error to validation_errors
        if "validation_errors" not in data:
            data["validation_errors"] = []
        data["validation_errors"].append(f"Contact API error: {str(e)}")
        
        return {
            **state,
            "failure_step": True,
            "data": data,
            "executionFlow": state.get("executionFlow", []) + [f"{current_step} failed"]
        }


def show_cart(state: State):
    current_step = state.get("current_step", "")
    print("🛒 [show_cart] Running cart summary...")

    # Extract cart safely
    cart = state.get("data", {}).get("cart", {})

    # Check if cart is present
    if not cart:
        print("⚠️ [show_cart] Cart is missing or empty.")
        return {
            "messages": [AIMessage(content="Your cart is currently empty. Please add items before proceeding.")],
            "current_step": current_step,
        }

    # Prepare LLM prompt
    try:
        prompt = cart_summary_instruction_prompt.format(cart=cart)
        sm = SystemMessage(content=prompt)

        # Call structured LLM
        structuredllm = llm.with_structured_output(schema_map.get(current_step))
        response = structuredllm.invoke([sm] + state.get("messages", []))
        
        print("✅ [show_cart] Response from LLM:", response)

        # Handle human input interrupt
        if response.get("human_input"):
            print("🛑 [show_cart] Triggering interrupt:", response["message"])
            user_input = interrupt(value=response["message"])
            return {
                "messages": [HumanMessage(content=user_input)],
                "executionFlow": state.get("executionFlow", []) + [f"{current_step} retry"]
            }
        else:
            return {
                "messages": [AIMessage(content=response["message"])],
                "current_step": END,
                "executionFlow": state.get("executionFlow", []) + [current_step]
            }
            
    except Exception as e:
        print(f"❌ [show_cart] Error: {e.__class__.__name__}: {e}")
        print_exception_group(e)
        
        return {
            **state,
            "failure_step": True,
            "executionFlow": state.get("executionFlow", []) + [f"{current_step} failed"]
        }


# Graph setup
graph.add_node(constants.DIRECTION, classifier)
graph.add_node(constants.PRODUCT_TYPE, info_collector)
graph.add_node(constants.SCHEDULE, schedule)
graph.add_node(constants.SCHEDULE_INFO, info_collector)
graph.add_node(constants.RESERVATION, reservation)
graph.add_node(constants.CONTACT, contact)
graph.add_node(constants.CONTACT_INFO, info_collector)
graph.add_node(constants.FAILURE_HANDLER, failure_handler)
graph.add_node(constants.CART, show_cart)

graph.set_entry_point(constants.DIRECTION)

# Enhanced conditional edges with better error handling
graph.add_conditional_edges(constants.DIRECTION, router_next, [constants.PRODUCT_TYPE, END])
graph.add_conditional_edges(constants.PRODUCT_TYPE, router_next, [constants.SCHEDULE_INFO, constants.PRODUCT_TYPE, constants.FAILURE_HANDLER, END])
graph.add_conditional_edges(constants.SCHEDULE_INFO, router_next, [constants.SCHEDULE, constants.SCHEDULE_INFO, constants.FAILURE_HANDLER, END])
graph.add_conditional_edges(constants.SCHEDULE, router_next, [constants.RESERVATION, constants.FAILURE_HANDLER])
graph.add_conditional_edges(constants.RESERVATION, router_next, [constants.CONTACT_INFO, constants.FAILURE_HANDLER])
graph.add_conditional_edges(constants.CONTACT_INFO, router_next, [constants.CONTACT, constants.CONTACT_INFO, constants.FAILURE_HANDLER])
graph.add_conditional_edges(constants.CONTACT, router_next, [constants.CART, constants.FAILURE_HANDLER])
graph.add_conditional_edges(constants.CART, router_next, [constants.DIRECTION, END, constants.CART])
graph.add_conditional_edges(constants.FAILURE_HANDLER, router_next, [END, constants.CONTACT_INFO, constants.SCHEDULE_INFO, constants.PRODUCT_TYPE])

compiled_graph = graph.compile(memory)
langsmith_graph = graph.compile()

