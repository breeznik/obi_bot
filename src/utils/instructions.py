import src.utils.constants as constants
from langchain_core.prompts import PromptTemplate

product_type_instruction = """
Ask the user if they want lounge access for arrival, departure, or both. Internally map the response to one of the following product IDs: ARRIVALONLY, DEPARTURE, ARRIVALBUNDLE. Do not show or mention product IDs to the user.
"""

direction_instruction = "classify the user message based on their intent if it's for booking lounge or an general querry"

schedule_instruction = "Collect schedule information including airport ID (e.g., SIA or NMIA), direction (Arrival or Departure), travel date (YYYYMMDD), flight ID."


failure_instruction = "handle the failure while processing the provided"

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

contact_instruction = "Collect contact information including first name, last name, email, phone number."


inst_map = {
constants.DIRECTION: direction_instruction,
constants.PRODUCT_TYPE: product_type_instruction ,
constants.SCHEDULE_INFO: schedule_instruction ,
constants.CONTACT_INFO:contact_instruction
}