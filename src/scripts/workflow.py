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

def info_collector(state:State):
    print('info collector triggered' , state)

    sm = ""
    current_step = state.get("current_step" , "")
    print('before condition' , current_step)
    if current_step in {constants.PRODUCT_TYPE, constants.SCHEDULE_INFO , constants.CONTACT_INFO}:
        sm = SystemMessage(content=inst_map[current_step])
        schema = schema_map[current_step]
        if(current_step == constants.SCHEDULE_INFO):
            schema = schema_map[current_step](state["data"]["product_type"])
            print("current schema " , schema)
            structured_llm = llm.with_structured_output(schema)
        elif current_step == constants.CONTACT_INFO:
            schema = schema_map[current_step](adult_count=state["data"]["schedule_info"]["pessanger_count"]["adult"] , child_count=state["data"]["schedule_info"]["pessanger_count"]["children"])
            print("current schema " , schema)
            structured_llm = llm.with_structured_output(schema)
        else:
            structured_llm = llm.with_structured_output(schema)
        
        
        response = structured_llm.invoke([sm] + state["messages"])
        
        print('response from ai' , response)
        
        if response.get("human_input"):
            print('Triggering interrupt' , response["message"])
            user_input = interrupt(value=response["message"])
            return {
                "messages":[HumanMessage(content=user_input)] ,
                "executionFlow": state.get("executionFlow", []) + [f"{current_step} retry"],
                "data": state.get("data") or {}
            }
        else:
            return {
                "current_step": flow_serializer[current_step] ,
                "data":{
                    **(state.get("data") or {}),
                    current_step:response[current_step]
                }
            }
            
    return {
        "current_step":END
    }

def router_next(state:State):
    current_step = state.get("current_step", "direction")
    print(f"Routing decision: current_step = {current_step} {state}" )
    
    if(state.get("failure_step" , False)):
        return constants.FAILURE_HANDLER
    
    return current_step

def failure_handler(state:State):
    print("failure triggered")
    current_step = state["current_step"]
    prompt = failure_instruction_prompt.format(step=state["current_step"] , error="network error")
    sm = SystemMessage(content=prompt)
    structuredllm = llm.with_structured_output(schema_map[constants.FAILURE_HANDLER])
    response = structuredllm.invoke([sm] + state["messages"])
    print("response from failure llm : " , response)    
    if response["end"]:
        return {
            "messages":[AIMessage(content=response["message"])] , 
            "current_step":constants.DIRECTION,
            "failure_step": False
        }
    if response["human_input"]:
        print('Triggering interrupt' , response["message"])
        user_input = interrupt(value=response["message"])
        return {
            "messages":[HumanMessage(content=user_input)],
            "executionFlow": state.get("executionFlow", []) + [f"{current_step} {constants.FAILURE_HANDLER} retry"] 
        }
    else:
        return {
            "current_step": failuer_serializer[current_step],
            "messages": [AIMessage(content=response["message"])] , 
            "failure_step": False
        }
       
    
# Application nodes
async def schedule(state: State):
    print("🔄 [schedule] Starting schedule step...")
    currentState = state
    mcp_client: McpClient = await get_mcpInstance()
    current_step = state.get("current_step")
    print(f"ℹ️ [schedule] Current step: {current_step}")

    # Ensure 'schedule' dict exists
    if "schedule" not in currentState["data"]:
        currentState["data"]["schedule"] = {}

    
    data = state.get("data", {})
    isBundle = data.get("product_type") == constants.BUNDLE
    scheduleData = data.get("schedule_info", {})
    print(f"🧳 [schedule] Is Bundle: {isBundle}")

    isSchedule = False
    session_id = "00009223581026309436128527"

    def parse_if_str(result):
        if isinstance(result, str):
            try:
                import json
                return json.loads(result)
            except Exception as e:
                print(f"❌ [schedule] JSON parse error: {e}")
                return {}
        return result

    def has_schedule_id(result):
        result = parse_if_str(result)
        return isinstance(result, dict) and result.get("scheduleId")

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

        try:
            schedule_result = await mcp_client.invoke_tool("schedule", scheduleObj)
            print(f"✅ [schedule] Schedule result: {schedule_result}")
            isSchedule = has_schedule_id(schedule_result)
            currentState["data"]["schedule"] = schedule_result            
        except Exception as e:
             traceback.print_exc()  # Logs full traceback to console
             if hasattr(e, 'exceptions'):
                for i, sub in enumerate(e.exceptions, start=1):
                    print(f"↪️ Sub-exception {i}: {type(sub).__name__} - {sub}")
                    if hasattr(sub, '__traceback__'):
                        traceback.print_tb(sub.__traceback__)


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
            "sessionid": "00081400083250224448591690"  # TODO: extract to config
        }

        print(f"📦 [schedule] Arrival payload: {arrivalObj}")
        print(f"📦 [schedule] Departure payload: {departureObj}")

        arrival_result, departure_result = None, None

        try:
            arrival_result = await mcp_client.invoke_tool("schedule", arrivalObj)
            print(f"✅ [schedule] Arrival result: {arrival_result}")
        except Exception as e:
            print(f"❌ [schedule] Error in arrival schedule: {e}")

        try:
            departure_result = await mcp_client.invoke_tool("schedule", departureObj)
            print(f"✅ [schedule] Departure result: {departure_result}")
        except Exception as e:
            print(f"❌ [schedule] Error in departure schedule: {e}")

        if has_schedule_id(arrival_result) and has_schedule_id(departure_result):
            isSchedule = True
        else:
            print("⚠️ [schedule] Either arrival or departure schedule is missing scheduleId.")

            currentState["data"]["schedule"] = {"arrival":{} , "departure":{}}
        if has_schedule_id(arrival_result):
            currentState["data"]["schedule"]["arrival"] = arrival_result            
        if has_schedule_id(departure_result):
            currentState["data"]["schedule"]["departure"] = departure_result            

    if isSchedule:
        print("✅ [schedule] Schedule step successful. Proceeding to next step.")
        return {**currentState , "current_step": flow_serializer[current_step]}

    print("❌ [schedule] Schedule step failed.")
    return { **currentState , "failure_step": True , }


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

        # 🧍‍♂️ Get passenger counts
        passengers = schedule_info.get("pessanger_count", {})
        adult_tickets = passengers.get("adult", 0)
        child_tickets = passengers.get("children", 0)

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
                "sessionid": "00081400083250224448591690"
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
                "sessionid": "00081400083250224448591690"
            }

        print(f"📦 [reservation] Payload: {reservation_data}")

        # 🚀 Call MCP tool
        reservation_result = await mcp_client.invoke_tool("reservation", reservation_data)
        print(f"✅ [reservation] Result: {reservation_result}")

        data["reservation"] = json.loads(reservation_result)
        if data["reservation"].get("cartitemid"):
            # 🔁 Proceed to next step
            return {
                "data": data,
                "current_step": flow_serializer[current_step],
            }
        else:
            return {
            **state,
            "failure_step": True
            }
    except Exception as e:
        print(f"❌ [reservation] Error during reservation: {e.__class__.__name__}: {e}")
        print_exception_group(e)

        return {
            **state,
            "failure_step": True
        }
        
async def contact(state: State):
    mcp_client = await get_mcpInstance()
    current_step = state["current_step"]
    print('📞 [contact] Executing contact step...')

    # Parse reservation JSON string to dict
    reservation = state["data"]["reservation"]

    # Access first adult's contact info
    contact_info = state["data"]["contact_info"]["passengerDetails"]["adults"][0]
    
    contact_payload = {
        "cartitemid": reservation["cartitemid"],
        "email": contact_info["email"],
        "firstname": contact_info["firstname"],
        "lastname": contact_info["lastname"],
        "phone": state["data"]["contact_info"]["contact"]["phone"],  # fallback from main contact
        "title": contact_info["title"],
        "sessionid":"00081400083250224448591690"
    }

    print("📦 [contact] Payload:", contact_payload)

    try:
        contact_response = await mcp_client.invoke_tool("contact", contact_payload)
        print("✅ [contact] Response:", contact_response)
        cart = state["data"].get("cart", {})
        cartItems = {
         **cart,
        contact_payload["cartitemid"]:{
            "product":state["data"]["product_type"],
            "Passengers": state["data"]["reservation"]["ticketsrequested"],
            "amount":state["data"]["reservation"]["retail"]
        }
        }
        data = state['data']
        data = {
            **data,
            "cart": cartItems
        }
        return {
            **state,
            "current_step": flow_serializer[current_step],
            "data": data
        }

    except Exception as e:
        print(f"❌ [contact] Error: {e.__class__.__name__}: {e}")
        traceback.print_exc()  # Logs full traceback to console

        # For TaskGroup or ExceptionGroup (Python 3.11+), drill into nested errors
        if hasattr(e, 'exceptions'):
            for i, sub in enumerate(e.exceptions, start=1):
                print(f"↪️ Sub-exception {i}: {type(sub).__name__} - {sub}")
                if hasattr(sub, '__traceback__'):
                    traceback.print_tb(sub.__traceback__)

        return {
            **state,
            "failure_step": True
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
    except Exception as e:
        print("❌ [show_cart] Failed to format cart summary prompt:", e)
        raise ValueError("Prompt formatting failed due to cart content issue.")

    sm = SystemMessage(content=prompt)

    # Call structured LLM
    structuredllm = llm.with_structured_output(schema_map.get(current_step))
    try:
        response = structuredllm.invoke([sm] + state.get("messages", []))
    except Exception as e:
        print("❌ [show_cart] Error invoking structured LLM:", e)
        raise

    print("✅ [show_cart] Response from LLM:", response)

    # Handle human input interrupt
    if response.get("human_input"):
        print("🛑 [show_cart] Triggering interrupt:", response["message"])
        user_input = interrupt(value=response["message"])
        return {
            "messages": [HumanMessage(content=user_input)],
            "executionFlow": state.get("executionFlow", []) + [f"{current_step} {constants.FAILURE_HANDLER} retry"],
        }

    # Handle end or direction transitions
    direction = response.get("direction")
    if direction == "end":
        return {
            "messages": [AIMessage(content=response["message"])],
            "current_step": END,
        }
    elif direction == "direction":
        return {
            "messages": [AIMessage(content=response["message"])],
            "current_step": constants.DIRECTION,
        }

    # Default fallback
    return {
        "messages": [AIMessage(content="Cart processed, but no clear next step. Please continue.")],
        "current_step": current_step,
    }


graph.add_node(constants.DIRECTION , classifier)
graph.add_node(constants.PRODUCT_TYPE , info_collector)
graph.add_node(constants.SCHEDULE , schedule)
graph.add_node(constants.SCHEDULE_INFO , info_collector)
graph.add_node(constants.RESERVATION , reservation)
graph.add_node(constants.CONTACT , contact)
graph.add_node(constants.CONTACT_INFO , info_collector)
graph.add_node(constants.FAILURE_HANDLER , failure_handler)
graph.add_node(constants.CART , show_cart)

graph.set_entry_point(constants.DIRECTION)

graph.add_conditional_edges(constants.DIRECTION , router_next , [constants.PRODUCT_TYPE ,END])
graph.add_conditional_edges(constants.PRODUCT_TYPE , router_next , [constants.SCHEDULE_INFO , constants.PRODUCT_TYPE , END])
graph.add_conditional_edges(constants.SCHEDULE_INFO , router_next , [constants.SCHEDULE , constants.SCHEDULE_INFO , END ])
graph.add_conditional_edges(constants.SCHEDULE , router_next , [constants.RESERVATION , constants.FAILURE_HANDLER])
graph.add_conditional_edges(constants.RESERVATION , router_next , [constants.CONTACT_INFO , constants.FAILURE_HANDLER])
graph.add_conditional_edges(constants.CONTACT_INFO , router_next , [constants.CONTACT , constants.CONTACT_INFO ])
graph.add_conditional_edges(constants.CONTACT , router_next , [constants.FAILURE_HANDLER , END , constants.CART])
graph.add_conditional_edges(constants.CART , router_next , [constants.DIRECTION , END , constants.CART])
graph.add_conditional_edges(constants.FAILURE_HANDLER , router_next , [END , constants.CONTACT , constants.SCHEDULE , constants.RESERVATION])


compiled_graph = graph.compile(memory)

langsmith_graph = graph.compile()

