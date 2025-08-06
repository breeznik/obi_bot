"""
Centralized validation service for all user inputs
"""
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime
import re
from src.utils import constants


class ValidationService:
    """Handles all input validation with consistent error messaging"""
    
    @staticmethod
    def validate_product_type(product_type: str) -> Tuple[bool, Optional[str]]:
        """Validate product type selection"""
        valid_types = [constants.ARRIVAL, constants.DEPARTURE, constants.BUNDLE]
        if product_type not in valid_types:
            return False, f"Invalid product type. Must be one of: {', '.join(valid_types)}"
        return True, None
    
    @staticmethod
    def validate_schedule_info(schedule_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate schedule information"""
        errors = []
        
        # Validate airport ID
        airport_id = schedule_data.get("airportid", "")
        if not airport_id or len(airport_id) != 3:
            errors.append("Airport ID must be a 3-letter code (e.g., SIA, NMIA)")
        
        # Validate direction
        direction = schedule_data.get("direction", "")
        if direction not in ["A", "D"]:
            errors.append("Direction must be 'A' for Arrival or 'D' for Departure")
        
        # Validate date format
        travel_date = schedule_data.get("traveldate", "")
        if not re.match(r'^\d{8}$', travel_date):
            errors.append("Travel date must be in YYYYMMDD format (e.g., 20250815)")
        else:
            # Validate date is not in the past
            try:
                date_obj = datetime.strptime(travel_date, "%Y%m%d")
                if date_obj.date() < datetime.now().date():
                    errors.append("Travel date cannot be in the past")
            except ValueError:
                errors.append("Invalid travel date format")
        
        # Validate flight ID
        flight_id = schedule_data.get("flightId", "")
        if not flight_id or len(flight_id) < 3:
            errors.append("Flight ID must include airline code (e.g., AF2859, BA123)")
        
        # Validate passenger count
        passengers = schedule_data.get("passengers") or schedule_data.get("pessanger_count", {})
        if isinstance(passengers, dict):
            adult_count = passengers.get("adult", 0)
            child_count = passengers.get("children", 0)
            if adult_count < 1:
                errors.append("At least one adult passenger is required")
            if adult_count > 10 or child_count > 10:
                errors.append("Maximum 10 passengers per booking")
        
        return len(errors) == 0, errors
    
    @staticmethod
    def validate_contact_info(contact_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate contact information"""
        errors = []
        
        # Validate required fields
        required_fields = ["firstname", "lastname", "email", "phone"]
        for field in required_fields:
            if not contact_data.get(field, "").strip():
                errors.append(f"{field.replace('_', ' ').title()} is required")
        
        # Validate email format
        email = contact_data.get("email", "")
        if email and not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email):
            errors.append("Please provide a valid email address")
        
        # Validate phone format
        phone = contact_data.get("phone", "")
        if phone and not re.match(r'^[\+]?[1-9][\d]{3,14}$', phone):
            errors.append("Please provide a valid phone number with country code")
        
        # Validate name length
        firstname = contact_data.get("firstname", "")
        lastname = contact_data.get("lastname", "")
        if firstname and (len(firstname) < 2 or len(firstname) > 50):
            errors.append("First name must be 2-50 characters")
        if lastname and (len(lastname) < 2 or len(lastname) > 50):
            errors.append("Last name must be 2-50 characters")
        
        return len(errors) == 0, errors
    
    @staticmethod
    def validate_bundle_schedule(schedule_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate bundle schedule (arrival + departure)"""
        errors = []
        
        arrival = schedule_data.get("arrival", {})
        departure = schedule_data.get("departure", {})
        
        if not arrival:
            errors.append("Arrival schedule information is required for bundle")
        else:
            valid, arr_errors = ValidationService.validate_schedule_info(arrival)
            if not valid:
                errors.extend([f"Arrival: {err}" for err in arr_errors])
        
        if not departure:
            errors.append("Departure schedule information is required for bundle")
        else:
            valid, dep_errors = ValidationService.validate_schedule_info(departure)
            if not valid:
                errors.extend([f"Departure: {err}" for err in dep_errors])
        
        return len(errors) == 0, errors
