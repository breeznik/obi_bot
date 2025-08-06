import src.utils.constants as constants
from langchain_core.prompts import PromptTemplate

# Enhanced product type instruction with examples
product_type_instruction = """
Ask the user what type of lounge access they need. Present the options clearly:

"I can help you with lounge access for your trip. Which would you prefer:
1. **Arrival lounge** - Access when you land at your destination
2. **Departure lounge** - Access before your flight departs  
3. **Both arrival and departure** - Complete lounge access for your journey

Which option works best for you?"

Internally map responses to: ARRIVALONLY, DEPARTURE, ARRIVALBUNDLE. Never show these IDs to users.
"""

# Enhanced direction instruction  
direction_instruction = """
Analyze the user's message to determine their intent:
- **booking**: User wants to book lounge access, make reservations, or purchase services
- **inquiry**: User has questions, needs information, or wants to check existing bookings
- **support**: User needs help, has complaints, or technical issues

Look for keywords like: book, reserve, buy, purchase (booking) vs. question, info, help, check, status (inquiry).
"""

# Enhanced schedule instruction with validation
schedule_instruction = """
Collect complete flight and travel information. Required fields:

**Airport Code**: 3-letter IATA code (e.g., SIA, NMIA, JFK)
**Direction**: 
  - "Arrival" (A) - when landing at this airport
  - "Departure" (D) - when leaving from this airport
**Travel Date**: Must be YYYYMMDD format (e.g., 20250815 for August 15, 2025)
**Flight Number**: Complete flight ID including airline code (e.g., AF2859, BA123)

For bundle bookings, passenger count applies to all items.

Validation rules:
- Date must be today or future
- Airport code must be valid 3-letter code
- Flight number must include airline prefix
- All fields are mandatory

If any information is missing or invalid, clearly explain what's needed.
"""


failure_instruction_prompt = PromptTemplate.from_template(
"""You're an AI assistant helping a user with a booking process.

The step **"{step}"** encountered an issue while processing your request.

**Issue**: {error}

I apologize for the inconvenience. Here are your options:
1. **Try Again** - I can retry this step for you
2. **Exit Booking** - End the current booking process
3. **Get Help** - Speak with a customer service representative

Please let me know how you'd like to proceed. I'm here to help make this as smooth as possible for you."""
)

# Add validation instruction
validation_instruction_prompt = PromptTemplate.from_template(
"""You are validating user input for the {field_type} step.

User provided: {user_input}
Required format: {required_format}
Validation rules: {validation_rules}

Task:
1. Check if the input meets all requirements
2. If valid, extract and format the information correctly
3. If invalid, politely explain what's needed and ask for correction

Response format: {{"valid": true/false, "data": extracted_data, "message": "feedback_to_user"}}"""
)

cart_summary_instruction_prompt = PromptTemplate.from_template(
    """You are a helpful AI assistant guiding a user through a booking process.

Here is the current cart summary:
{cart}

Your task:
1. Summarize the booking details in simple, clear language. Include:
   - Product type
   - Number of passengers
   - Total amount (if available)
2. Ask the user whether they would like to book another product or proceed to checkout.

Respond in a helpful, polite tone.


"""
)

# Enhanced contact instruction with validation
contact_instruction = """
Collect complete contact information for the booking:

**Required Information:**
- **First Name**: Legal first name as on travel documents
- **Last Name**: Legal last name as on travel documents  
- **Email**: Valid email address for booking confirmation
- **Phone Number**: Include country code (e.g., +1-555-123-4567)

**Validation:**
- Names: No special characters, 2-50 characters each
- Email: Must contain @ and valid domain
- Phone: 10-15 digits with optional country code

Present this in a friendly way: "I'll need some contact details to complete your booking. Could you please provide your full name, email address, and phone number?"
"""

# Enhanced cart instruction
cart_instruction = """
Present the cart summary in a clear, organized format:

**Your Booking Summary:**
- List each product with details (type, date, flight, passengers)
- Show individual and total pricing if available
- Highlight any special offers or discounts

**Next Steps:**
"Your current selection is ready! Would you like to:
1. **Add another product** to your booking
2. **Proceed to checkout** to complete your purchase
3. **Modify** any existing selections

What would you prefer to do next?"

Keep the tone positive and make it easy for users to understand their options.
"""

# Instruction mapping with enhanced error handling
inst_map = {
    constants.DIRECTION: direction_instruction,
    constants.PRODUCT_TYPE: product_type_instruction,
    constants.SCHEDULE_INFO: schedule_instruction,
    constants.CONTACT_INFO: contact_instruction,
    constants.CART: cart_summary_instruction_prompt,
    constants.FAILURE_HANDLER: failure_instruction_prompt
}

# Validation mapping for each step
validation_map = {
    constants.SCHEDULE_INFO: validation_instruction_prompt,
    constants.CONTACT_INFO: validation_instruction_prompt,
    constants.PRODUCT_TYPE: validation_instruction_prompt
}