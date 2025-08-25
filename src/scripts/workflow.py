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
from src.utils.schema import schema_map , common_schema_without_human_input
from src.services.mcp_client import get_mcpInstance , McpClient
load_dotenv()
import json
import traceback
import sys
from src.utils.helpers import cart_formulator

def print_exception_group(exc: BaseException, indent: int = 0):
    prefix = " " * indent
    if hasattr(exc, "exceptions"):  # It's an ExceptionGroup
        print(f"{prefix}ExceptionGroup ({exc.__class__.__name__}): {exc}")
        for i, sub_e in enumerate(exc.exceptions):
            print(f"{prefix}--- Sub-exception {i+1} ---")
            print_exception_group(sub_e, indent + 4)
    else:
        print(f"{prefix}{exc.__class__.__name__}: {exc}")
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
    constants.CART : constants.PAYMENT,
}

failuer_serializer = {
    constants.SCHEDULE: constants.PRODUCT_TYPE , 
    constants.CONTACT: constants.RESERVATION,
    constants.RESERVATION: constants.PRODUCT_TYPE
}

# flow nodes
async def classifier(state:State , config):
    sessionId = config["metadata"]["thread_id"]
    try: 
        sm = SystemMessage(content = inst_map[constants.DIRECTION])
        structured_llm = llm.with_structured_output(schema_map[constants.DIRECTION])
        result =  structured_llm.invoke([sm] + state["messages"])
        print(f"Classifier direction: {result}")
        if result["direction"] == constants.BOOKING:
            # Store extracted data from user's initial message
            extracted_data = result.get("extracted_data", {})
            return {
            "current_step": constants.PRODUCT_TYPE,
            "data":{ **state.get("data", {}) ,  "sessionId": sessionId, "extracted_data": extracted_data} , 
            "client_events": []         
            }
        else:            
            return {
                "current_step": END ,
                "messages": state["messages"]  + [AIMessage(content= result.get("message" , "") )] , 
                "data":{**state.get("data", {}) ,  "sessionId": sessionId} , 
                "client_events": []
            }
            
    except Exception as e:
        print(f"Error in classifier: {e}")
        return {
            "current_step": END,
            "messages": state["messages"]  + [AIMessage(content="There was some error while processing your request , please retry." )],
            "data":{ **state.get("data", {}) ,  "sessionId": sessionId} ,
            "client_events": []
        }

def info_collector(state:State):
    current_step = state.get("current_step" , "")
    print(f"Info collector - step: {current_step}")
    
    sm = ""
    if current_step in {constants.PRODUCT_TYPE, constants.SCHEDULE_INFO , constants.CONTACT_INFO}:
        sm = SystemMessage(content=f"{inst_map[current_step]}")
        schema = schema_map[current_step]
        if(current_step == constants.SCHEDULE_INFO):
            schema = schema_map[current_step](state["data"]["product_type"])
            structured_llm = llm.with_structured_output(schema)
            sm = SystemMessage(content=inst_map[current_step](state["data"]["product_type"]))
            
        elif current_step == constants.CONTACT_INFO:
            schema = schema_map[current_step](adult_count=state["data"]["schedule_info"]["pessanger_count"]["adult"] , child_count=state["data"]["schedule_info"]["pessanger_count"]["children"])
            structured_llm = llm.with_structured_output(schema)
        else:
            structured_llm = llm.with_structured_output(schema)
        
        response = structured_llm.invoke([sm] + state["messages"])
        print(f"Info collector response: {response}")
        
        if response.get("human_input"):
            print(f"Triggering interrupt: {response['message']}")
            user_input = interrupt(value=response["message"])
            return {
                "messages": state["messages"]  + [HumanMessage(content=user_input) , AIMessage(content=response["message"])] ,
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
    print(f"Router - current step: {current_step}")
    
    if(state.get("failure_step" , False)):
        return constants.FAILURE_HANDLER
    
    return current_step

def failure_handler(state:State):
    print("Failure handler triggered")
    current_step = state["current_step"]
    error = state["data"][current_step].get("statusMessage" , "Unknown error occurred")
    prompt = failure_instruction_prompt.format(step=state["current_step"] , error=error)
    sm = SystemMessage(content=prompt)
    structuredllm = llm.with_structured_output(schema_map[constants.FAILURE_HANDLER])
    response = structuredllm.invoke([sm] + state["messages"])
    print(f"Failure handler response: {response}")    
    if response["end"]:
        return {
            "messages": [AIMessage(content=response["message"])] , 
            "current_step":constants.DIRECTION,
            "failure_step": False
        }
    if response["isStandby"]:
        return {
            "current_step": END,
            "messages": [AIMessage(content=response["message"] , client_events=[{
                    "type": "client_event",
                    "event": "redirect_to_standby",
                    "payload": {"product_type": state["data"].get("product_type" , "")}
                }])], 
            "failure_step": False,
            "client_events":[{
                    "type": "client_event",
                    "event": "redirect_to_standby",
                    "payload": {"product_type": state["data"].get("product_type" , "")}
                }]
        }
    if response["human_input"]:
        print(f"Triggering interrupt: {response['message']}")
        user_input = interrupt(value=response["message"])
        return {
            "messages":state["messages"]  + [HumanMessage(content=user_input)],
            "executionFlow": state.get("executionFlow", []) + [f"{current_step} {constants.FAILURE_HANDLER} retry"],
            "failure_step": False  # Clear failure step to avoid infinite loop
        }
    else:
        data = state["data"]
        if current_step == constants.RESERVATION: 
            data[constants.SCHEDULE_INFO] = {}
            data[constants.SCHEDULE] = {}
        else:
            data[failuer_serializer[current_step]] = {**state["data"].get("cart", {})}
            
        return {
            "current_step": failuer_serializer[current_step],
            "messages": [AIMessage(content=response["message"])] ,
            "data": data, 
            "failure_step": False,
        }
       
    
# Application nodes
async def schedule(state: State , config):
    sessionId = config["metadata"]["thread_id"]
    print("Starting schedule step")
    currentState = state
    mcp_client: McpClient = await get_mcpInstance()
    current_step = state.get("current_step")
    print(f"Current step: {current_step}")

    # Ensure 'schedule' dict exists
    if "schedule" not in currentState["data"]:
        currentState["data"]["schedule"] = {}

    
    data = state.get("data", {})
    isBundle = data.get("product_type") == constants.BUNDLE
    scheduleData = data.get("schedule_info", {})
    print(f"Is Bundle: {isBundle}")

    isSchedule = False
    session_id = sessionId

    def parse_if_str(result):
        if isinstance(result, str):
            try:
                import json
                return json.loads(result)
            except Exception as e:
                print(f"JSON parse error: {e}")
                return {}
        return result

    def has_schedule_id(result):
        result = parse_if_str(result)
        return isinstance(result, dict) and result.get("scheduleId")

    if not isBundle:
        print("Processing non-bundle schedule")
        scheduleObj = {
            "airportid": scheduleData.get("airportid"),
            "direction": scheduleData.get("direction"),
            "traveldate": scheduleData.get("traveldate"),
            "flightId": scheduleData.get("flightId"),
            "sessionid": session_id
        }
        print(f"Schedule request payload: {scheduleObj}")

        try:
            schedule_result = await mcp_client.invoke_tool("schedule", scheduleObj)
            print(f"Schedule result: {schedule_result}")
            isSchedule = has_schedule_id(schedule_result)
            currentState["data"]["schedule"] = json.loads(schedule_result)            
        except Exception as e:
             print(f"Error invoking schedule tool: {e}")
             traceback.print_exc()  # Logs full traceback to console
             if hasattr(e, 'exceptions'):
                for i, sub in enumerate(e.exceptions, start=1):
                    print(f"Sub-exception {i}: {type(sub).__name__} - {sub}")
                    if hasattr(sub, '__traceback__'):
                        traceback.print_tb(sub.__traceback__)
    else:
        print("Processing bundle schedule (arrival + departure)")

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
            "sessionid": sessionId  
        }

        print(f"Arrival payload: {arrivalObj}")
        print(f"Departure payload: {departureObj}")

        arrival_result, departure_result = None, None

        try:
            arrival_result = await mcp_client.invoke_tool("schedule", arrivalObj)
            print(f"Arrival result: {arrival_result}")
        except Exception as e:
            print(f"Error in arrival schedule: {e}")

        try:
            departure_result = await mcp_client.invoke_tool("schedule", departureObj)
            print(f"Departure result: {departure_result}")
        except Exception as e:
            print(f"Error in departure schedule: {e}")

        if has_schedule_id(arrival_result) and has_schedule_id(departure_result):
            isSchedule = True
        else:
            print("Either arrival or departure schedule is missing scheduleId")

            currentState["data"]["schedule"] = {"arrival":{} , "departure":{}}
        if has_schedule_id(arrival_result):
            currentState["data"]["schedule"]["arrival"] = arrival_result            
        if has_schedule_id(departure_result):
            currentState["data"]["schedule"]["departure"] = departure_result            

    if isSchedule:
        print("Schedule step successful - proceeding to next step")
        return {**currentState , "current_step": flow_serializer[current_step]}
    
    print("Schedule step failed")
    return { **currentState , "failure_step": True , }

async def reservation(state: State , config):
    sessionId = config["metadata"]["thread_id"]
    print("Executing reservation step")

    mcp_client = await get_mcpInstance()
    current_step = state.get("current_step", "")
    data = state.get("data", {})

    product_type = data.get("product_type")
    schedule_info = data.get("schedule_info", {})
    schedule_data = data.get("schedule", {})

    try:
        # Parse schedule_data if it's a JSON string
        if isinstance(schedule_data, str):
            schedule_data = json.loads(schedule_data)

        # Parse nested arrival/departure if they're strings
        if isinstance(schedule_data.get("arrival"), str):
            schedule_data["arrival"] = json.loads(schedule_data["arrival"])
        if isinstance(schedule_data.get("departure"), str):
            schedule_data["departure"] = json.loads(schedule_data["departure"])

        # Get passenger counts
        passengers = schedule_info.get("pessanger_count", {})
        adult_tickets = passengers.get("adult", 0)
        child_tickets = passengers.get("children", 0)

        # Build reservation payload
        if product_type == constants.BUNDLE:
            reservation_data = {
                "adulttickets": adult_tickets,
                "childtickets": child_tickets,
                "scheduleData": {
                    "A": {"scheduleId": schedule_data.get("arrival", {}).get("scheduleId", 0)},
                    "D": {"scheduleId": schedule_data.get("departure", {}).get("scheduleId", 0)}
                },
                "productid": product_type,
                "sessionid": sessionId
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
                "sessionid": sessionId
            }

        print(f"Reservation payload: {reservation_data}")

        # Call MCP tool
        reservation_result = await mcp_client.invoke_tool("reservation", reservation_data)
        print(f"Reservation result: {reservation_result}")

        data["reservation"] = json.loads(reservation_result)
        if data["reservation"]["isStandBy"]:
            return {
            "data":data,
            "failure_step": True
            }
        elif data["reservation"]["data"].get("cartitemid"):
            # Proceed to next step
            return {
                "data": data,
                "current_step": flow_serializer[current_step],
            }
        else:
            return {
            "data":data,
            "failure_step": True
            }
    except Exception as e:
        print(f"Error during reservation: {e.__class__.__name__}: {e}")
        print_exception_group(e)

        return {
            **state,
            "failure_step": True
        }
        
async def contact(state: State , config):

    try:
        sessionId = config["metadata"]["thread_id"]
        mcp_client = await get_mcpInstance()
        current_step = state["current_step"]
        print("Executing contact step")

        # Parse reservation JSON string to dict
        reservation = state["data"]["reservation"]

        # Access first adult's contact info
        contact_info = state["data"]["contact_info"]["contact"]
        
        contact_payload = {
            "cartitemid": reservation["cartitemid"],
            "email": contact_info["email"],
            "firstname": contact_info["firstName"],
            "lastname": contact_info["lastName"],
            "phone": contact_info["phone"],  # fallback from main contact
            "title": contact_info.get("title" , "MR"),
            "sessionid":sessionId
        }

        print(f"Contact payload: {contact_payload}")

        contact_response = await mcp_client.invoke_tool("contact", contact_payload)
        print(f"Contact response: {contact_response}")
        cart = state["data"].get("cart", {})
        # structured_llm = llm.with_structured_output(common_schema_without_human_input)
        # response = structured_llm.invoke([SystemMessage(content=inst_map["summarize"])] + state["messages"])
        intermidateData = {
            "contact_info": state["data"].get("contact_info", {}),
            "contact": state["data"].get("contact", {}),
            "sessionId": state["data"].get("sessionId", sessionId),
            "reservation": state["data"].get("reservation", {}),
            "product_type": state["data"].get("product_type", ""),
            "schedule_info": state["data"].get("schedule_info", {}),
            "schedule": state["data"].get("schedule", {}),
        }
        cartItems = {
            contact_payload["cartitemid"]:{
                "summary":{
                "product":state["data"]["product_type"],
                "Passengers": state["data"]["reservation"]["ticketsrequested"],
                "amount":state["data"]["reservation"]["retail"] , 
                } , 
                "intermidiate": intermidateData
            }}
        
        data = {"cart": {**state["data"].get("cart", {}) , **cartItems}}
        obi_cart = cart_formulator(cartItems)
        return {
            **state,
            "current_step": flow_serializer[current_step],
            "data": data,
            "messages":[],
            "client_events":[{
                    "type": "client_event",
                    "event": "add_to_cart",
                    "payload": {"cart": obi_cart}
                }]
        }

    except Exception as e:
        print(f"Error in contact: {e.__class__.__name__}: {e}")
        traceback.print_exc()  # Logs full traceback to console

        # For TaskGroup or ExceptionGroup (Python 3.11+), drill into nested errors
        if hasattr(e, 'exceptions'):
            for i, sub in enumerate(e.exceptions, start=1):
                print(f"Sub-exception {i}: {type(sub).__name__} - {sub}")
                if hasattr(sub, '__traceback__'):
                    traceback.print_tb(sub.__traceback__)

        return {
            **state,
            "failure_step": True
        }
        
def show_cart(state: State):
    current_step = state.get("current_step", "")
    print("Running cart summary")

    # Extract cart safely
    cart = state.get("data", {}).get("cart", {})

    # Check if cart is present
    if not cart:
        print("Cart is missing or empty")
        return {
            "messages": state["messages"] + [AIMessage(content="Your cart is currently empty. Please add items before proceeding.")],
            "current_step": current_step,
        }

    # Prepare LLM prompt
    try:
        prompt = cart_summary_instruction_prompt.format(cart = list(cart_item["summary"] for cart_item in cart.values()))
    except Exception as e:
        print(f"Failed to format cart summary prompt: {e}")
        raise ValueError("Prompt formatting failed due to cart content issue.")

    sm = SystemMessage(content=prompt)

    # Call structured LLM
    structuredllm = llm.with_structured_output(schema_map.get(current_step))
    try:
        response = structuredllm.invoke([sm] + state.get("messages", []))
    except Exception as e:
        print(f"Error invoking structured LLM: {e}")
        raise

    print(f"Cart summary response: {response}")

    # Handle human input interrupt
    if response.get("human_input"):
        print(f"Triggering interrupt: {response['message']}")
        user_input = interrupt(value=response["message"])
        return {
            "messages": state["messages"]  + [ AIMessage(content=response["message"] , client_events=[{
                    "type": "client_event",
                    "event": "add_to_cart",
                    "payload": {"cart": cart_formulator(state["data"]["cart"])}
                }]) , HumanMessage(content=user_input) ],
            "executionFlow": state.get("executionFlow", []) + [f"{current_step} {constants.FAILURE_HANDLER} retry"],
        }

    # Handle end or direction transitions
    direction = response.get("direction")
    if direction == "end":
        return {
            "messages": state["messages"]  + [AIMessage(content=response["message"] )],
            "current_step": END,
            "client_events": []
            
        }
    elif direction == "direction":
        return {
            "messages": state["messages"]  + [AIMessage(content=response["message"] )],
            "current_step": constants.PRODUCT_TYPE,
            "client_events": []
            
        }
    elif direction == "payment":
        return {
            "messages": state["messages"]  + [AIMessage(content=response["message"] )],
            "current_step": END , 
            "client_events": [{
                    "type": "client_event",
                    "event": "navigate_to_summary",
                    "payload": {}
            }]
        }

    # Default fallback
    return {
        "messages": state["messages"]  + [AIMessage(content="Cart processed, but no clear next step. Please continue.")],
        "current_step": current_step,
        "client_events": []
        
    }

async def payment(state: State , config):
    mcp_client = await get_mcpInstance()
    sessionId = config["metadata"]["thread_id"]
    
    # Get cart data
    cart = state.get("data", {}).get("cart", {})
    
    if not cart:
        return {
            "messages": state["messages"] + [AIMessage(content="No items in cart to process payment.")],
            "current_step": END,
        }
    
    # Build cart items array for payment API
    cart_items = []
    total_amount = 0
    primary_contact_email = ""
    cardholder_name = ""
    
    for cart_item_id, cart_item in cart.items():
        intermediate_data = cart_item.get("intermidiate", {})
        summary_data = cart_item.get("summary", {})
        
        # Extract passenger counts
        passenger_count = intermediate_data.get("schedule_info", {}).get("pessanger_count", {})
        adult_tickets = passenger_count.get("adult", 0)
        child_tickets = passenger_count.get("children", 0)
        
        # Extract reservation data
        reservation_data = intermediate_data.get("reservation", {})
        
        # Extract contact info
        contact_info = intermediate_data.get("contact_info", {})
        primary_contact = contact_info.get("contact", {})
        
        # Get primary contact info for payment
        if not primary_contact_email and primary_contact.get("email"):
            primary_contact_email = primary_contact.get("email")
            cardholder_name = f"{primary_contact.get('firstname', '')} {primary_contact.get('lastname', '')}".strip()
        
        # Add to total amount
        item_amount = reservation_data.get("retail", summary_data.get("amount", 0))
        total_amount += item_amount
        
        # Build passengers array from contact info
        passengers = []
        
        # Add adult passengers
        for adult in contact_info.get("passengerDetails", {}).get("adults", []):
            passengers.append({
                "title": adult.get("title", "MR"),
                "firstname": adult.get("firstname", ""),
                "lastname": adult.get("lastname", ""),
                "email": adult.get("email", ""),
                "dob": adult.get("dob" , ""),
                "passengertype": "ADULT",
                "phone": primary_contact.get("phone", "")
            })
        
        # Add child passengers
        for child in contact_info.get("passengerDetails", {}).get("children", []):
            passengers.append({
                "title": child.get("title", "MASTER"),
                "firstname": child.get("firstname", ""),
                "lastname": child.get("lastname", ""),
                "dob": child.get("dob", ""),
                "passengertype": "CHILD",
                "phone": primary_contact.get("phone", "")
                
            })
        
        # Create cart item for payment
        payment_cart_item = {
            "adulttickets": adult_tickets,
            "amount": item_amount,
            "arrivalscheduleid": reservation_data.get("arrivalscheduleid", 0),
            "cartitemid": int(cart_item_id),
            "childtickets": child_tickets,
            "departurescheduleid": reservation_data.get("departurescheduleid", 0),
            "groupbooking": "N",
            "groupid": "NA",
            "infanttickets": 0,
            "optional": {
                "occasioncomment": "",
                "paddlename": "AI Agent",
                "specialoccasion": "VACATION"
            },
            "passengers": passengers,
            "primarycontact": {
                "title": primary_contact.get("title", "MR"),
                "firstname": primary_contact.get("firstname", ""),
                "lastname": primary_contact.get("lastname", ""),
                "email": primary_contact.get("email", ""),
                "phone": primary_contact.get("phone", "")
            },
            "productid": reservation_data.get("productid", summary_data.get("product", "")),
            "referencenumber": "",
            "secondarycontact": {
                "email": "",
                "firstname": "",
                "lastname": "",
                "phone": "",
                "title": "MR"
            }
        }
        
        cart_items.append(payment_cart_item)
    
    # Prepare payment state with structure expected by payment2 backend function
    paymentState = {
        "sessionid": sessionId,
        "totalAmount": total_amount,
        "cart": cart_items,
        "paymentInformation": {
            "cardholdername": cardholder_name or "AI Agent User",
            "cardholderemail": primary_contact_email or "nikunjrathi2308@gmail.com",
            "cardnumber": "4111111111111111",
            "cardtype": "VISA",
            "cvv": "123",
            "expiry": "03/26"
        }
    }
    
    print(f"Payment state: {paymentState}")
    
    try:
        # Call the payment tool
        payment_result = await mcp_client.invoke_tool("payment2", {"state":paymentState})
        print(f"Payment result: {payment_result}")
        
        # Parse the result if it's a JSON string
        if isinstance(payment_result, str):
            try:
                payment_result = json.loads(payment_result)
            except json.JSONDecodeError:
                print(f"Failed to parse payment result as JSON: {payment_result}")
                payment_result = {"error": "Invalid response format"}
        
        # Check if payment was successful
        if payment_result and not payment_result.get("error"):
            return {
                "messages": state["messages"] + [AIMessage(content=f"🎉 Payment processed successfully! Total amount: ${total_amount}. Your booking confirmation will be sent to {primary_contact_email}.")],
                "current_step": END,
            }
        else:
            error_msg = payment_result.get("error", "Unknown payment error")
            return {
                "messages": state["messages"] + [AIMessage(content=f"❌ Payment failed: {error_msg}. Please try again.")],
                "current_step": END,
            }
    except Exception as e:
        print(f"Error in payment processing: {e}")
        return {
            "messages": state["messages"] + [AIMessage(content="❌ Payment processing failed due to a technical error. Please try again later.")],
            "current_step": END,
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
graph.add_node(constants.PAYMENT , payment)

graph.set_entry_point(constants.DIRECTION)

graph.add_conditional_edges(constants.DIRECTION , router_next , [constants.PRODUCT_TYPE , constants.FAILURE_HANDLER, END])
graph.add_conditional_edges(constants.PRODUCT_TYPE , router_next , [constants.SCHEDULE_INFO , constants.PRODUCT_TYPE , constants.FAILURE_HANDLER, END])
graph.add_conditional_edges(constants.SCHEDULE_INFO , router_next , [constants.SCHEDULE , constants.SCHEDULE_INFO , constants.FAILURE_HANDLER, END ])
graph.add_conditional_edges(constants.SCHEDULE , router_next , [constants.RESERVATION , constants.FAILURE_HANDLER])
graph.add_conditional_edges(constants.RESERVATION , router_next , [constants.CONTACT_INFO , constants.FAILURE_HANDLER])
graph.add_conditional_edges(constants.CONTACT_INFO , router_next , [constants.CONTACT , constants.CONTACT_INFO , constants.FAILURE_HANDLER])
graph.add_conditional_edges(constants.CONTACT , router_next , [constants.FAILURE_HANDLER , END , constants.CART])
graph.add_conditional_edges(constants.CART , router_next , [constants.PRODUCT_TYPE , END , constants.CART, constants.PAYMENT, constants.FAILURE_HANDLER])
graph.add_conditional_edges(constants.PAYMENT , router_next , [END, constants.FAILURE_HANDLER])
graph.add_conditional_edges(constants.FAILURE_HANDLER , router_next , [END , constants.CONTACT , constants.SCHEDULE , constants.RESERVATION, constants.SCHEDULE_INFO, constants.CONTACT_INFO , constants.DIRECTION, constants.FAILURE_HANDLER])


compiled_graph = graph.compile(memory)

langsmith_graph = graph.compile()

