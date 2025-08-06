"""
Centralized API service for external MCP calls
"""
import json
from typing import Dict, Any, Optional, Tuple
from src.services.mcp_client import get_mcpInstance, McpClient
from src.utils import constants


class ApiService:
    """Handles all external API calls with consistent error handling"""
    
    @staticmethod
    async def call_schedule_api(schedule_data: Dict[str, Any], session_id: str) -> Tuple[bool, Any, Optional[str]]:
        """Call schedule API with error handling"""
        try:
            mcp_client = await get_mcpInstance()
            
            payload = {
                "airportid": schedule_data.get("airportid"),
                "direction": schedule_data.get("direction"),
                "traveldate": schedule_data.get("traveldate"),
                "flightId": schedule_data.get("flightId"),
                "sessionid": session_id
            }
            
            result = await mcp_client.invoke_tool("schedule", payload)
            
            # Parse if string
            if isinstance(result, str):
                result = json.loads(result)
            
            # Validate result has schedule ID
            if isinstance(result, dict) and result.get("scheduleId"):
                return True, result, None
            else:
                return False, result, "No schedule ID returned from API"
                
        except Exception as e:
            return False, None, f"Schedule API error: {str(e)}"
    
    @staticmethod
    async def call_bundle_schedule_api(arrival_data: Dict[str, Any], departure_data: Dict[str, Any], session_id: str) -> Tuple[bool, Dict[str, Any], Optional[str]]:
        """Call schedule API for bundle (arrival + departure)"""
        try:
            # Call both APIs
            arrival_success, arrival_result, arrival_error = await ApiService.call_schedule_api(arrival_data, session_id)
            departure_success, departure_result, departure_error = await ApiService.call_schedule_api(departure_data, session_id)
            
            if arrival_success and departure_success:
                return True, {
                    "arrival": arrival_result,
                    "departure": departure_result
                }, None
            else:
                errors = []
                if not arrival_success:
                    errors.append(f"Arrival: {arrival_error}")
                if not departure_success:
                    errors.append(f"Departure: {departure_error}")
                
                return False, {
                    "arrival": arrival_result,
                    "departure": departure_result
                }, "; ".join(errors)
                
        except Exception as e:
            return False, {}, f"Bundle schedule API error: {str(e)}"
    
    @staticmethod
    async def call_reservation_api(reservation_data: Dict[str, Any]) -> Tuple[bool, Any, Optional[str]]:
        """Call reservation API with error handling"""
        try:
            mcp_client = await get_mcpInstance()
            
            result = await mcp_client.invoke_tool("reservation", reservation_data)
            
            # Parse if string
            if isinstance(result, str):
                result = json.loads(result)
            
            # Validate result has cart item ID
            if isinstance(result, dict) and result.get("cartitemid"):
                return True, result, None
            else:
                return False, result, "No cart item ID returned from reservation API"
                
        except Exception as e:
            return False, None, f"Reservation API error: {str(e)}"
    
    @staticmethod
    async def call_contact_api(contact_data: Dict[str, Any]) -> Tuple[bool, Any, Optional[str]]:
        """Call contact API with error handling"""
        try:
            mcp_client = await get_mcpInstance()
            
            result = await mcp_client.invoke_tool("contact", contact_data)
            
            # Parse if string
            if isinstance(result, str):
                result = json.loads(result)
            
            return True, result, None
                
        except Exception as e:
            return False, None, f"Contact API error: {str(e)}"
    
    @staticmethod
    def build_reservation_payload(product_type: str, schedule_info: Dict[str, Any], schedule_result: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        """Build reservation API payload"""
        # Get passenger counts
        passengers = schedule_info.get("passengers") or schedule_info.get("pessanger_count", {})
        adult_tickets = passengers.get("adult", 1) if isinstance(passengers, dict) else 1
        child_tickets = passengers.get("children", 0) if isinstance(passengers, dict) else 0
        
        if product_type == constants.BUNDLE:
            return {
                "adulttickets": adult_tickets,
                "childtickets": child_tickets,
                "scheduleData": {
                    "A": {"scheduleId": schedule_result.get("arrival", {}).get("scheduleId", 0)},
                    "D": {"scheduleId": schedule_result.get("departure", {}).get("scheduleId", 0)}
                },
                "productid": product_type,
                "sessionid": session_id
            }
        else:
            schedule_id = schedule_result.get("scheduleId", 0)
            return {
                "adulttickets": adult_tickets,
                "childtickets": child_tickets,
                "scheduleData": {
                    "A": {"scheduleId": schedule_id if product_type == constants.ARRIVAL else 0},
                    "D": {"scheduleId": schedule_id if product_type == constants.DEPARTURE else 0}
                },
                "productid": product_type,
                "sessionid": session_id
            }
    
    @staticmethod
    def build_contact_payload(contact_info: Dict[str, Any], reservation_result: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        """Build contact API payload"""
        # Handle different contact info structures
        if "passengerDetails" in contact_info:
            # Old structure
            first_adult = contact_info["passengerDetails"]["adults"][0]
            return {
                "cartitemid": reservation_result.get("cartitemid"),
                "email": first_adult.get("email"),
                "firstname": first_adult.get("firstname"),
                "lastname": first_adult.get("lastname"),
                "phone": contact_info.get("contact", {}).get("phone"),
                "title": first_adult.get("title", "Mr"),
                "sessionid": session_id
            }
        else:
            # New simplified structure
            return {
                "cartitemid": reservation_result.get("cartitemid"),
                "email": contact_info.get("email"),
                "firstname": contact_info.get("firstname"),
                "lastname": contact_info.get("lastname"),
                "phone": contact_info.get("phone"),
                "title": "Mr",
                "sessionid": session_id
            }
