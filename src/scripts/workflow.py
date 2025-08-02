from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import add_messages, StateGraph, END
from langgraph.types import Command, interrupt
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.graph import add_messages 
from src.utils.states import State
from langchain_core.messages import HumanMessage , AIMessage , SystemMessage
from src.utils.instructions import inst_map , failure_instruction_prompt
import src.utils.constants as constants
from src.utils.schema import schema_map

load_dotenv()

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
    constants.CONTACT : END
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
        print('curren step schema' , schema_map[current_step])
        sm = SystemMessage(content=inst_map[current_step])
        structured_llm = llm.with_structured_output(schema_map[current_step])
        response = structured_llm.invoke([sm] + state["messages"])
        
        print('response from ai' , response)
        
        if response["human_input"]:
            print('Triggering interrupt' , response["message"])
            user_input = interrupt(value=response["message"])
            return {
                "messages":[HumanMessage(content=user_input)] ,
                "executionFlow": state.get("executionFlow", []) + [f"{current_step} retry"] 
            }
        else:
            return {
                "current_step": flow_serializer[current_step] ,
                "messages": [AIMessage(content=response["message"])]
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
    print("after structure" , )
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
def schedule(state:State):
    current_step = state["current_step"]
    print('schedule executed')
    isSchedule = False
    if isSchedule:
        return {
        "current_step":flow_serializer[current_step]
        }
    return {
        "failure_step":True
    }

def reservation(state:State):
    current_step = state["current_step"]
    print('schedule executed')

    isSchedule = True
    if isSchedule:
        return {
        "current_step":flow_serializer[current_step]
        }
    return {
        "failure_step":True
    }

def contact(state:State):
    current_step = state["current_step"]
    print('schedule executed')

    isContact = True
    if isContact:
        return {
        "current_step":flow_serializer[current_step]
        }
    return {
        "failure_step":True
    }

def cancel_cart(state:State):
    current_step = state["current_step"]
    print('schedule executed')

    isCanceled = True
    if isCanceled:
        return {
        "current_step":flow_serializer[current_step]
        }
        
    return {
        "failure_step":True
    }



graph.add_node(constants.DIRECTION , classifier)
graph.add_node(constants.PRODUCT_TYPE , info_collector)
graph.add_node(constants.SCHEDULE , schedule)
graph.add_node(constants.SCHEDULE_INFO , info_collector)
graph.add_node(constants.RESERVATION , reservation)
graph.add_node(constants.CONTACT , contact)
graph.add_node(constants.CONTACT_INFO , info_collector)
graph.add_node(constants.FAILURE_HANDLER , failure_handler)

graph.set_entry_point(constants.DIRECTION)

graph.add_conditional_edges(constants.DIRECTION , router_next , [constants.PRODUCT_TYPE ,END])
graph.add_conditional_edges(constants.PRODUCT_TYPE , router_next , [constants.SCHEDULE_INFO , constants.PRODUCT_TYPE , END])
graph.add_conditional_edges(constants.SCHEDULE_INFO , router_next , [constants.SCHEDULE , constants.SCHEDULE_INFO , END ])
graph.add_conditional_edges(constants.SCHEDULE , router_next , [constants.RESERVATION , constants.FAILURE_HANDLER])
graph.add_conditional_edges(constants.RESERVATION , router_next , [constants.CONTACT_INFO , constants.FAILURE_HANDLER])
graph.add_conditional_edges(constants.CONTACT , router_next , [constants.FAILURE_HANDLER , END])
graph.add_conditional_edges(constants.CONTACT_INFO , router_next , [constants.CONTACT , constants.CONTACT_INFO ])
graph.add_conditional_edges(constants.FAILURE_HANDLER , router_next , [END , constants.CONTACT , constants.SCHEDULE , constants.RESERVATION])


compiled_graph = graph.compile(memory)

langsmith_graph = graph.compile()

