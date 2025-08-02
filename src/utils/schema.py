import src.utils.constants as constants

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
            "enum": ["ARRIVAL", "DEPARTURE" , "ARRIVALBUNDLE"],
            "description": "product type selected by user"
        } , 
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

schedule_schema = {
    "title": "schedule_info_collector",
    "description": "Schema for schedule",
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
        "schedule_info": {
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
            "required": ["airportid", "direction", "traveldate", "flightId"]
        }
    },
    "required": ["message", "human_input" , "schedule_info"]
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

schema_map = {
    constants.DIRECTION : direction_schema ,
    constants.PRODUCT_TYPE:  product_type_schema ,
    constants.INFO_COLLECTOR : info_collector_schema , 
    constants.SCHEDULE_INFO : schedule_schema , 
    constants.FAILURE_HANDLER: failure_schema,
    constants.CONTACT_INFO: contact_schema
}

