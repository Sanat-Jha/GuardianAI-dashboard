import json
import os
from openai import OpenAI
from toon import encode  # Importing the TOON encoder

# Initialize OpenAI client (ensure OPENAI_API_KEY is set in your environment)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def query_gpt_with_toon_context(context_json, user_prompt):
    """
    Converts a context JSON object to TOON format and queries OpenAI GPT.
    
    Args:
        context_json (dict): The data dictionary containing device usage stats.
        user_prompt (str): The specific question or request (e.g., "summarise this").
        
    Returns:
        str: The response from GPT.
    """
    
    # 1. Convert the JSON context to TOON format
    # TOON is optimized for LLMs, using fewer tokens than JSON for structured data
    try:
        toon_feed = encode(context_json)
    except Exception as e:
        return f"Error converting to TOON format: {e}"

    # 2. Define the refined Setup Prompt (System Message)
    # I corrected 'dept' to 'depth' and added persona details for better output.
    setup_prompt = (
        "You are an expert data analyst specializing in digital well-being and child development. "
        "Using the provided Child mobile device usage and consumption data (formatted in TOON), "
        "perform a complete depth analysis to identify usage patterns, screen time risks, and content preferences. "
        "Use these insights to provide a comprehensive answer to the user's specific request below."
    )

    # 3. Construct the Message Payload
    # We combine the TOON data and the user's specific prompt into the user message
    full_user_message = f"DATA (TOON Format):\n{toon_feed}\n\nREQUEST:\n{user_prompt}"

    try:
        response = client.chat.completions.create(
            model="gpt-4o",  # Use a capable model for data analysis
            messages=[
                {"role": "system", "content": setup_prompt},
                {"role": "user", "content": full_user_message}
            ],
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"API Call Failed: {e}"

# --- Example Usage ---
if __name__ == "__main__":
    # Sample Context JSON: Child device usage data
    child_data = {
        "user_id": "child_01",
        "period": "2025-11-18 to 2025-11-24",
        "total_screen_time_hours": 28.5,
        "apps": [
            {"name": "YouTube Kids", "category": "Video", "hours": 12.0, "flagged_content": 0},
            {"name": "Roblox", "category": "Game", "hours": 8.5, "in_app_purchases": 4},
            {"name": "TikTok", "category": "Social", "hours": 5.0, "flagged_content": 1},
            {"name": "Duolingo", "category": "Education", "hours": 3.0, "streak": 15}
        ],
        "daily_average_hours": 4.07,
        "parental_limits_exceeded": True
    }

    # Sample User Prompt
    request = "Summarise the risky behavior and suggest 3 actionable limits."

    # Run the function
    result = query_gpt_with_toon_context(child_data, request)
    
    print("--- GPT Response ---")
    print(result)
