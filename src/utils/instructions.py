import src.utils.constants as constants
from langchain_core.prompts import PromptTemplate

product_type_instruction = """
Ask the user if they want lounge access for arrival, departure, or both. Internally map the response to one of the following product IDs: ARRIVALONLY, DEPARTURE, ARRIVALBUNDLE. Do not show or mention product IDs to the user , if not provide tell user what they need to share.
"""

direction_instruction = "classify the user message based on their intent if it's for booking lounge or an general querry"

schedule_instruction = (
    "Collect schedule information including: airport ID (e.g., SIA or NMIA), direction (Arrival or Departure), travel date (YYYYMMDD)(if it's not in this formate then convert it your self), and flight ID. if not provide tell user what they need to share "
    "If this is a bundle, the passenger count will be shared across all items. "
    "Do not proceed until all the required schedule information is provided. If all details are already available, proceed without confirmation."
)


failure_instruction_prompt = PromptTemplate.from_template(
"""You're an AI assistant helping a user with a booking process.

The step **"{step}"** failed due to an error while calling an external service or API.

**Error Details**: {error}

Your task:
1. Briefly explain the issue to the user in a polite, non-technical way.
2. Offer two clear options:
   - Retry the same step
   - Exit the booking process

Keep the tone helpful and professional. Format the response as a short message the AI should send to the user."""
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

contact_instruction = "Collect contact information including first name, last name, email, phone number. if not provide tell user what they need to share"

cart_instruction= "show the current added product into from cart and then ask user if they want to add more product or want to procced for payment"

inst_map = {
constants.DIRECTION: direction_instruction,
constants.PRODUCT_TYPE: product_type_instruction ,
constants.SCHEDULE_INFO: schedule_instruction ,
constants.CONTACT_INFO:contact_instruction , 
constants.CART: cart_summary_instruction_prompt
}