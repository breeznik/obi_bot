import src.utils.constants as constants
from langchain_core.prompts import PromptTemplate

product_type_instruction = """
Ask the user if they want lounge access for **arrival**, **departure**, or **both**. Internally map the response to one of the following product IDs: ARRIVALONLY, DEPARTURE, ARRIVALBUNDLE. 

from previouse messsages if user have shared their direction then don't ask again.

**Important**: Do not show or mention product IDs to the user.

if the user have provided what direction they are looking for then don't ask again.
"""

direction_instruction = "Classify the user message based on their intent.  If it's for booking lounge access or mentioned [arrival ,departure , bundle] then classify as booking if not then a general query, format your response clearly."

schedule_instruction = "Collect schedule information including airport ID (e.g., SIA or NMIA), direction (Arrival or Departure), travel date (YYYYMMDD), flight ID. present the information in a clear and structured format using markdown."


failure_instruction_prompt = PromptTemplate.from_template(
"""You're an AI assistant helping a user with a booking process.

The step **"{step}"** failed due to an error while calling an external service or API.

## ⚠️ Error Details
{error}

## Your Options:
1. **🔄 Retry** - Try the same step again
2. **❌ Exit** - Cancel the booking process

Please let me know how you'd like to proceed. I'm here to help!

*Keep the tone helpful and professional. Format the response using proper markdown with headers, bullet points, and emphasis.*"""
)

cart_summary_instruction_prompt = PromptTemplate.from_template(
    """You are a helpful AI assistant guiding a user through a booking process.
## 🛒 Your Cart Summary

{cart}

### 📋 Booking Details:
Please review your selection:
- **Product Type:** [Product details]
- **Number of Passengers:** [Count]
- **Total Amount:** [Amount if available]

### What's Next?
Would you like to:
1. **➕ Add Another Product** - Book additional services
2. **💳 Proceed to Checkout** - Complete your booking

Please let me know your preference!

*Always format responses using proper markdown with headers, bullet points, emojis, and emphasis for better readability. if the users shares intent to add another product then direct them to "direction" and make the human_input false*

"""
)

contact_instruction = """
##  Contact Information Required

ask user for their contact details to proceed with the booking.
and share what you need from them.

**Required Information:**
- **First Name**
- **Last Name** 
- **Email Address**
- **Phone Number**

If any information is missing, please use a bulleted list to show what's needed and format your response with proper markdown.
"""

cart_instruction = """
## 🛒 Current Cart Status

Show the current products added to the cart using markdown formatting:

### Your Items:
[Display cart contents here]

### Next Steps:
Would you like to:
- **Add more products** to your cart
- **Proceed to payment** and complete your booking

Please format your response with proper headings, bullet points, and emphasis.
"""

inst_map = {
constants.DIRECTION: direction_instruction,
constants.PRODUCT_TYPE: product_type_instruction ,
constants.SCHEDULE_INFO: schedule_instruction ,
constants.CONTACT_INFO:contact_instruction , 
constants.CART: cart_summary_instruction_prompt
}