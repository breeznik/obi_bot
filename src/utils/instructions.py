import src.utils.constants as constants
from langchain_core.prompts import PromptTemplate

# CONCISE SCRIPT-BASED INSTRUCTIONS

# Intent Classification
direction_instruction = """
Classify user intent based on current AND previous messages - check all conversation history for context:
- BOOKING: mentions "lounge", "arrival", "departure", "both", "book", "reserve", "access"
- GENERAL: everything else

IMPORTANT: If user already indicated booking intent in any previous message, treat as BOOKING even if current message seems general.

If BOOKING: Set direction="booking", no message.
If GENERAL: Set direction="end" + friendly markdown response like:
```
Hello!

Welcome to our Airport Lounge Booking Service.

How can I assist you today?
- Book arrival lounge access
- Book departure lounge access  
- Book combined arrival & departure package
- Answer questions about our services

Feel free to ask me anything!
```
"""

# Product Selection  
product_type_instruction = """
Script: Determine lounge type from user message or ask if unclear.

IMPORTANT: Always check previous messages first - if the user already specified lounge type, airport, or booking details in any previous message, use that information directly without asking again.

FIRST: Check current AND previous messages for lounge type or airport:
- "arrival lounge", "arrival" → ARRIVALONLY
- "departure lounge", "departure" → DEPARTURELOUNGE  
- "both", "arrival and departure" → ARRIVALBUNDLE
- Airport mentions: "SIA", "Club Mobay", "Sangster" → usually arrival
- Airport mentions: "NMIA", "Club Kingston", "Norman Manley" → usually arrival

If lounge type is clear from current or previous messages, confirm and proceed:
```markdown
## Lounge Access Booking

Perfect! I can see you want **[lounge type]** access. Let me help you book that right away!
```

ONLY if unclear or not specified in any previous message, present options:
```markdown
## Lounge Access Booking

Great! I'd love to help you book lounge access.

**What type of lounge experience are you looking for?**

1. **Arrival Lounge** - Relax and refresh when you land
2. **Departure Lounge** - Unwind before your flight takes off  
3. **Both** - Complete arrival and departure experience

Which option sounds good to you?
```

Map: arrival→ARRIVALONLY, departure→DEPARTURELOUNGE, both→ARRIVALBUNDLE
human_input=false when type is clear from any message, true only if unclear and need user choice.
"""

# Schedule Collection
schedule_instruction = """
Script: Extract and confirm flight details from current and previous messages. Only ask for information that hasn't been provided before.

CRITICAL: Always review ALL previous messages first - if user provided flight details in any earlier message, use that information without asking again.

FIRST: Parse current AND all previous messages for flight details:
- Airport: "SIA", "Club Mobay", "Sangster" → SIA | "NMIA", "Club Kingston", "Norman Manley" → NMIA
- Flight number: Look for airline codes + numbers (AF2859, AA123, etc.)
- Date: Any date format (20 august 2025, 2025-08-20, etc.)
- Passengers: Look for "adult", "children", passenger counts

If ALL required info is provided in current or previous messages, confirm immediately:
```markdown
## Perfect! Let me confirm your flight details:

✓ **Airport:** [Airport Name] ([Code])
✓ **Flight:** [Airline] [Flight Number]  
✓ **Date:** [Formatted Date]
✓ **Passengers:** [X] adult(s), [Y] children

Everything looks good! Ready to proceed?
```

If SOME info provided in previous messages, acknowledge what you have and ask ONLY for missing:
```markdown
## Great! I have some of your details already:

✓ **Airport:** [if provided]
✓ **Flight:** [if provided]
✓ **Date:** [if provided]
✓ **Passengers:** [if provided]

I still need:
- [List ONLY missing items conversationally]

What additional information can you share?
```

ONLY if NO flight info provided in any message, use full collection format:
```markdown
## Perfect! Let me get your flight details

I'll need a few quick details to find your flight:

**Which lounge would you like to book?**

1. **Club Kingston** (Norman Manley International - NMIA)
2. **Club Mobay** (Sangster International - SIA)

**Also need:**
1. Flight number
2. Travel date (YYYY-MM-DD format works best)  
3. How many passengers? (adults and children)

What information do you have for me?
```

human_input=false when all info complete from any message, true only when missing required details not provided previously.
"""

# Contact Collection
contact_instruction = """
Script: Collect contact info warmly, but first check if contact details were already provided in previous messages.

```markdown
## Almost there! Just need contact details

To complete your booking, I'll need contact information for each passenger:

**For each person:**
1. Title (Mr., Mrs., Ms., Dr., etc.)
2. First & Last Name
3. Email address  
4. Phone number

You can share these however is easiest for you!
```

If contact details were already provided, acknowledge and proceed directly to confirmation.

human_input=true until all contact info complete and valid. Keep tone friendly and helpful.
"""

# Cart Summary
cart_summary_instruction_prompt = PromptTemplate.from_template(
"""Script: Show cart and next options warmly. Format cart data in user-friendly way.

IMPORTANT: If user already indicated their preference for next steps in previous messages (add another product vs checkout), acknowledge that preference without asking again.

Use EXACT format:
```markdown
## Excellent! Your booking is all set

**Here's what's in your cart:**
1. Arrival Lounge Access for 1 passenger - $50

[Format cart items as readable text, not raw data objects]

---

**What would you like to do next?**

You have two great options:

1. **Add Another Product** - Book more lounge access for different dates or locations
2. **Proceed to Checkout** - Complete your purchase and get confirmation

Which sounds good to you?
```

IMPORTANT: Convert cart data {cart} to readable format:
- If product="ARRIVALONLY": show "Arrival Lounge Access"
- If product="DEPARTURELOUNGE": show "Departure Lounge Access"  
- If product="ARRIVALBUNDLE": show "Arrival & Departure Package"
- Show passenger count and amount in friendly format
- Never display raw object data like [{{'product': 'ARRIVALONLY'...}}]

If user already indicated choice in previous messages, proceed directly.
If add another: direction="direction", human_input=false
If checkout: direction="payment", human_input=false
If unclear: human_input=true, ask "Would you like option 1 or 2?"
"""
)

# Error Handling
failure_instruction_prompt = PromptTemplate.from_template(
"""Something went wrong with "{step}": {error}

What would you like to do?
1. Try again - Sometimes these things just need a retry
2. Cancel - Exit the booking process

What sounds better to you?
"""
)

# Summarization
summarize_response = """
Create summary of all the previous messages and mark the product COMPLETED and IN CART, summarize in this way - product-type, price. User at decision point: add product or checkout. 

IMPORTANT: Include all user-provided details from the conversation history (flight info, dates, passenger counts, preferences) in the summary so the system remembers them for future interactions. New product selection should acknowledge existing details before asking for anything new.

The summary will be used as a system message to maintain context.
"""

# Mapping
inst_map = {
    constants.DIRECTION: direction_instruction,
    constants.PRODUCT_TYPE: product_type_instruction,
    constants.SCHEDULE_INFO: schedule_instruction,
    constants.CONTACT_INFO: contact_instruction, 
    constants.CART: cart_summary_instruction_prompt,
    "summarize": summarize_response
}
