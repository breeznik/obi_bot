import src.utils.constants as constants
import copy

direction_schema = {
    "title": "Classify_Schema",
    "description": "Schema for classify node",
    "type": "object",
    "properties": {
        "message":{
            "type":"string",
            "description":"AI response to human for their general query, will be skipped if the message is about booking lounge"
            },
        "direction": {
            "type": "string",
            "enum": [constants.BOOKING, "end"],
            "description": "Set to 'booking' if the user wants to book a lounge, otherwise 'end' for general queries."
        }
    },
    "required": ["direction"]
}

product_type_schema = {
    "title": "product_type_schema",
    "description": "Schema for product type",
    "type": "object",
    "properties": {
        "message":{
            "type":"string",
            "description":"AI response to human"
            },
        "product_type": {
            "type": "string",
            "enum": ["ARRIVALONLY", "DEPARTURELOUNGE" , "ARRIVALBUNDLE"],
            "description": "product type selected by user"
        }, 
         "human_input":{
                "type":"boolean",
                "description":"if inormation is not satisfied make it true to ask human again , if required info already give make it falase"
        }
    },
    "required": ["product_type","message" , "human_input"]
}

info_collector_schema = {
        "title": "info collector", 
        "description":"schema for info collector",
        "type": "object",
        "properties": {
            "message":{
                "type":"string",
                "description":"AI response to human"
            },
            "human_input":{
                "type":"boolean",
                "description":"make it true if the human input is need for information if not then make it false"
            },
           
        },
        "required":["message" , "human_input"]
}   

failure_schema = {
    "title": "failure_schema",
    "description": "Schema for failure",
    "type": "object",
    "properties": {
        "message": {
            "type": "string",
            "description": "AI response to human"
        },
        "human_input": {
            "type": "boolean",
            "description": "True if human input is needed and false if not"
        },
        "end": {
            "type": "boolean",
            "description": "True if user wants to exit the booking or end the flow"
        }
    },
    "required": ["message", "human_input", "end"]  # ✅ this is the correct way
}

common_schema = {
    "message": {
        "type": "string",
        "description": "AI response to human"
    },
    "human_input": {
        "type": "boolean",
        "description": "True if human input is needed"
    },
}

def schedule_schema(productType):
    print('schedule schema triggered ' , productType)
    isBundle = productType == constants.BUNDLE
    pessanger_count = {
        "type":"object",
        "description":"pessanger count",
        "properties":{
            "adult":{
                "type":"number",
                "description":"adult ticket count"
            },
            "children":{
                "type":"number",
                "description":"child ticket count"
            }
        },
        "required":["adult", "children"]
    }
    schedule_info_schema = {
        "type": "object",
        "description": "Schedule information object",
        "properties": {
            "airportid": {
                "type": "string",
                "description": "3-letter airport identifier (e.g., SIA or NMIA)"
            },
            "direction": {
                "type": "string",
                "enum": ["A", "D"],
                "description": "\"A\" for Arrival, \"D\" for Departure"
            },
            "traveldate": {
                "type": "string",
                "pattern": "^[0-9]{8}$",
                "description": "Date of travel in YYYYMMDD format"
            },
            "flightId": {
                "type": "string",
                "description": "Flight ID (e.g., XY123)"
            },
        },
    }
    
    if isBundle:
        # Bundle contains arrival and departure~
        properties = {
                **common_schema,
                "schedule_info": {
                "type": "object",
                "description": "Bundle with arrival and departure schedules",
                "properties": {
                    "arrival": schedule_info_schema,
                    "departure": schedule_info_schema,
                    "pessanger_count":pessanger_count
                },
                "required": ["arrival", "departure" , "pessanger_count"]
            }
        }
    else:
        # Single schedule_info
        local_schedule = copy.deepcopy(schedule_info_schema)
        local_schedule["properties"]["pessanger_count"] = pessanger_count
        local_schedule["required"] = ["airportid", "direction", "traveldate", "flightId", "pessanger_count"]

        properties = {
            **common_schema,
            "schedule_info": local_schedule
        }

    return {
        "title": "schedule_info_collector",
        "description": "Schema for schedule",
        "type": "object",
        "properties": properties,
        "required": ["message" , "schedule_info", "human_input"]
    }
    
# schedule_schema = {
#     "title": "schedule_info_collector",
#     "description": "Schema for schedule",
#     "type": "object",
#     "properties": {
#         "message": {
#             "type": "string",
#             "description": "AI response to human"
#         },
#         "human_input": {
#             "type": "boolean",
#             "description": "True if human input is needed"
#         },
#         "schedule_info": {
#             "type": "object",
#             "description": "Schedule information object",
#             "properties": {
#                 "airportid": {
#                     "type": "string",
#                     "description": "3-letter airport identifier (e.g., SIA or NMIA)"
#                 },
#                 "direction": {
#                     "type": "string",
#                     "enum": ["A", "D"],
#                     "description": "\"A\" for Arrival, \"D\" for Departure"
#                 },
#                 "traveldate": {
#                     "type": "string",
#                     "pattern": "^[0-9]{8}$",
#                     "description": "Date of travel in YYYYMMDD format"
#                 },
#                 "flightId": {
#                     "type": "string",
#                     "description": "Flight ID (e.g., XY123)"
#                 },
#             },
#             "required": ["airportid", "direction", "traveldate", "flightId"]
#         }
#     },
#     "required": ["message", "human_input" , "schedule_info"]
# }

cart_summary_schema = {
    "title": "cart_summary_schema",
    "description": "Schema for summarizing selected cart items and guiding user to next step",
    "type": "object",
    "properties": {
        "message": {
            "type": "string",
            "description": "AI response to the user summarizing current cart and asking if they want to add more"
        },
        "direction": {
            "type": "string",
            "enum": ["direction", "end"],
            "description": "'direction' if user wants to continue adding products, 'end' if they're done"
        },
        "human_input": {
            "type": "boolean",
            "description": "True if AI still needs clarification from user before proceeding. make it false if user have chosen to head to checkout or want to add another product"
        }
    },
    "required": ["message", "cart_summary", "direction", "human_input"]
}

contact_schema = {
    "title": "contact_info_collector",
    "description": "Schema for contact information",
    "type": "object",
    "properties": {
        "message": {
            "type": "string",
            "description": "AI response to human"
        },
        "human_input": {
            "type": "boolean",
            "description": "True if human input is needed"
        },
        "contact_info": {
            "type": "object",
            "description": "Contact information object",
            "properties": {
                "firstname": {
                    "type": "string",
                    "description": "First name of the user"
                },
                "lastname": {
                    "type": "string",
                    "description": "Last name of the user"
                },
                "email": {
                    "type": "string",
                    "format": "email",
                    "description": "Email address"
                },
                "phone": {
                    "type": "string",
                    "description": "Phone number with country code (e.g., +919999999999)"
                },
            },
            "required": ["firstname", "lastname", "email", "phone"]
        }
    },
    "required": ["message", "human_input" , "contact_info" ]
}

def generate_contact_schema(adult_count: int, child_count: int):
    passenger_details = {
        "type": "object",
        "description": "Passenger details",
        "properties": {
            "adults": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "enum": ["MR", "MRS", "Miss", "Master"],
                            "description": "Title of the adult"
                        },
                        "firstname": {
                            "type": "string",
                            "description": "First name"
                        },
                        "lastname": {
                            "type": "string",
                            "description": "Last name"
                        },
                        "email": {
                            "type": "string",
                            "format": "email",
                            "description": "Email address"
                        },
                        "dob": {
                            "type": ["string", "null"],
                            "description": "Date of birth in YYYY-MM-DD (optional for adults)",
                            "pattern": "^\d{4}-\d{2}-\d{2}$"
                        }
                    },
                    "required": ["title", "firstname", "lastname", "email"]
                },
                "minItems": adult_count,
                "maxItems": adult_count
            },
            "children": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "enum": ["MR", "MRS", "Miss", "Master"],
                            "description": "Title of the child"
                        },
                        "firstname": {
                            "type": "string",
                            "description": "First name"
                        },
                        "lastname": {
                            "type": "string",
                            "description": "Last name"
                        },
                        "dob": {
                            "type": "string",
                            "description": "Date of birth in YYYY-MM-DD (required)",
                            "pattern": "^\d{4}-\d{2}-\d{2}$"
                        }
                    },
                    "required": ["title", "firstname", "lastname", "dob"]
                },
                "minItems": child_count,
                "maxItems": child_count
            }
        },
        "required": ["adults", "children"]
    }

    contact_info_schema = {
        "title": "contact_info_collector",
        "description": "Schema for contact information",
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": "AI response to human"
            },
            "human_input": {
                "type": "boolean",
                "description": "True if human input is needed"
            },
            "contact_info": {
                "type": "object",
                "description": "Contact information object",
                "properties": {
                    "passengerDetails": passenger_details,
                    "contact": {
                        "type": "object",
                        "description": "Main contact person",
                        "properties": {
                            "title": {
                                "type": "string",
                                "enum": ["MR", "MRS", "Miss", "Master"],
                                "description": "Title of contact"
                            },
                            "firstname": {
                                "type": "string",
                                "description": "First name"
                            },
                            "lastname": {
                                "type": "string",
                                "description": "Last name"
                            },
                            "email": {
                                "type": "string",
                                "format": "email",
                                "description": "Email address"
                            },
                            "phone": {
                                "type": "string",
                                "description": "Phone number with country code (e.g., +919999999999)"
                            }
                        },
                        "required": ["title", "firstname", "lastname", "email", "phone"]
                    }
                },
                "required": ["passengerDetails", "contact"]
            }
        },
        "required": ["message", "human_input", "contact_info"]
    }

    return contact_info_schema

schema_map = {
    constants.DIRECTION : direction_schema ,
    constants.PRODUCT_TYPE:  product_type_schema ,
    constants.INFO_COLLECTOR : info_collector_schema , 
    constants.SCHEDULE_INFO : schedule_schema , 
    constants.FAILURE_HANDLER: failure_schema,
    constants.CONTACT_INFO: generate_contact_schema , 
    constants.CART: cart_summary_schema
}

