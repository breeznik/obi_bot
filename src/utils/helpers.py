from src.utils.states import State
import re
import src.utils.constants as constants
import json

lounge_lables = {
    "SIA":{"value":"SIA" , "label":"Club Mobay / Sangster Intl" }, 
    "NMIA":{"value":"NMIA" , "label":"Kingston" }
}
title_lables = {
    "MR":{"value":"MR" , "label":"Mr"},
    "MRS":{"value":"MRS" , "label":"Mrs"}, 
}
def get_prefix(value: str) -> str:
    match = re.match(r"^[A-Z]+", value)
    return match.group() if match else ""

def get_time_lowercase(timestamp: str) -> str:
    match = re.search(r"\b(\d{1,2}):(\d{2})\s*(AM|PM)\b", timestamp, re.IGNORECASE)
    if match:
        hour = str(int(match.group(1)))  # remove leading zero
        minute = match.group(2)
        am_pm = match.group(3).upper()
        return f"{hour}:{minute} {am_pm}"
    return ""

def extract_flight_date(target_date: str) -> str:
    match = re.match(r"(\d{4})-(\d{2})-(\d{2})", target_date)
    if match:
        year = match.group(1)
        month = match.group(2)
        day = match.group(3)
        return f"{month}/{day}/{year}"
    return ""

def cart_formulator(cartData:dict):
     cart_items = []
     cart = {"cartData":[] , "cartItemId":""}
     for item_key, cart_item in cartData.items():
         schedule = cart_item["intermidiate"]["schedule"]
         reservation = cart_item["intermidiate"]["reservation"]
         schedule_info = cart_item["intermidiate"]["schedule_info"]
         contact_info = cart_item["intermidiate"]["contact_info"]
         isBundle = cart_item["summary"]["product"] == constants.BUNDLE
         
         if isBundle:
            # Extract flight date in YY/MM/DD format from targetDate
       
            bundleItem = {
                "key":item_key,
                "value": {
                    "sessionId":cart_item["intermidiate"]["sessionId"],
                    "bookingDetail":{
                        0:{
                            "lounge":lounge_lables[schedule["arrival"]["airportId"]],
                            "airlineName":{"value":get_prefix(schedule["arrival"]["flightId"]) , "label":schedule["arrival"]["airline"]},
                            "airlineId":get_prefix(schedule["arrival"]["flightId"]),
                            "flightNumber":{"value":schedule["arrival"]["flightNumber"] , "label":schedule["arrival"]["flightNumber"]},
                            "flightTime_hour":get_time_lowercase(schedule["arrival"]["targetDate"]),
                            "flightDate": extract_flight_date(schedule["arrival"]["targetDate"]),
                        }, 
                        1:{
                            "lounge":lounge_lables[schedule["departure"]["airportId"]],
                            "airlineName":{"value":get_prefix(schedule["departure"]["flightId"]) , "label":schedule["departure"]["airline"]},
                            "airlineId":get_prefix(schedule["departure"]["flightId"]),
                            "flightNumber":{"value":schedule["departure"]["flightNumber"] , "label":schedule["departure"]["flightNumber"]},
                            "flightTime_hour":get_time_lowercase(schedule["departure"]["targetDate"]),
                            "flightDate": extract_flight_date(schedule["departure"]["targetDate"])
                        }
                    },
                    "currentCartItem": reservation,
                    "adultCount":schedule_info["pessanger_count"].get("adult" , 0),
                    "childCount":schedule_info["pessanger_count"].get("children" , 0),
                    "infantCount":schedule_info["pessanger_count"].get("infant" , 0),
                    "data":{
                        "passengerInfo":{
                            "adults":contact_info["passengerDetails"].get("adults", []),
                            "childs":contact_info["passengerDetails"].get("children", []),
                            "infant":contact_info["passengerDetails"].get("infant", []),
                        "primaryContactDetails":{
                            "title":title_lables[contact_info["contact"]["title"]],
                            "firstName":contact_info["contact"]["firstName"],
                            "lastName":contact_info["contact"]["lastName"],
                            "email":contact_info["contact"]["email"],
                            "confirmEmail":contact_info["contact"]["email"],
                            "phone":contact_info["contact"]["phone"],
                        },
                        "secondaryContactDetails":{
                            "heading":"",
                            "title":{"value":"","label":""},
                            "firstName":"",
                            "lastName":"",
                            "email":"",
                            "confirmEmail":"",
                            "phone":"",
                        },
                        "greetingDetail":{
                            0:{"name":"" , "occasion":{"value":"" , "label":""},"occasionDetail":"" },
                        },
                        },
                        "productid":cart_item["summary"]["product"],
                        "cartItemId":item_key,
                    }
                }
            }
            cart_items.append(bundleItem)
            cart["cartItemId"] = item_key
         else:
            single_item  = {
                "key":item_key,
                "value": {
                    "sessionId":cart_item["intermidiate"]["sessionId"],
                    "bookingDetail":{
                        "lounge":lounge_lables[schedule["airportId"]],
                        "airlineName":{"value":get_prefix(schedule["flightId"]) , "label":schedule["airline"]},
                        "airlineId":get_prefix(schedule["flightId"]),
                        "flightNumber":{"value":schedule["flightNumber"] , "label":schedule["flightNumber"]},
                        "flightTime_hour":get_time_lowercase(schedule["targetDate"]),
                        "flightDate": extract_flight_date(schedule["targetDate"]),
                    },
                    "currentCartItem": reservation,
                    "adultCount":schedule_info["pessanger_count"].get("adult" , 0),
                    "childCount":schedule_info["pessanger_count"].get("children" , 0),
                    "infantCount":schedule_info["pessanger_count"].get("infant" , 0),
                    "data":{
                        "passengerInfo":{
                            "adults":contact_info["passengerDetails"].get("adults", []),
                            "childs":contact_info["passengerDetails"].get("children", []),
                            "infant":contact_info["passengerDetails"].get("infant", []) , 
                            
                        "primaryContactDetails":{
                            "title":title_lables[contact_info["contact"]["title"]],
                            "firstName":contact_info["contact"]["firstName"],
                            "lastName":contact_info["contact"]["lastName"],
                            "email":contact_info["contact"]["email"],
                            "confirmEmail":contact_info["contact"]["email"],
                            "phone":contact_info["contact"]["phone"],
                        },
                        "secondaryContactDetails":{
                            "heading":"",
                            "title":{"value":"","label":""},
                            "firstName":"",
                            "lastName":"",
                            "email":"",
                            "confirmEmail":"",
                            "phone":"",
                        },
                        "greetingDetail":{
                            0:{"name":"" , "occasion":{"value":"" , "label":""},"occasionDetail":"" },
                        },
                        },
                        
                        "productid":cart_item["summary"]["product"],
                        "cartItemId":item_key,
                    }
                }
            }
            cart_items.append(single_item)
            cart["cartItemId"] = item_key
            
    
     cart["cartData"] = cart_items
     
     return cart