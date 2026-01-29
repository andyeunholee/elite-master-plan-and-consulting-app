import os
import time
from datetime import datetime
from dotenv import load_dotenv
import newsletter_utils

# Load environment variables
load_dotenv()

def main():
    print("--- 📧 Automated Newsletter Sender Started ---")
    print(f"Time: {datetime.now()}")
    
    # 1. Configuration Check
    api_key = os.getenv("GOOGLE_API_KEY")
    sender_email = os.getenv("SENDER_EMAIL")
    sender_password = os.getenv("SENDER_PASSWORD")
    
    if not api_key:
        print("❌ Error: GOOGLE_API_KEY is missing.")
        return
    if not sender_email or not sender_password:
        print("❌ Error: Email credentials (SENDER_EMAIL, SENDER_PASSWORD) are missing.")
        return

    # 2. Load Subscribers
    subscribers = newsletter_utils.load_subscribers()
    if not subscribers:
        print("⚠️ No subscribers found. Exiting.")
        return
        
    print(f"✅ Found {len(subscribers)} subscribers: {subscribers}")
    
    # 3. Generate Content
    current_month = datetime.now().strftime("%B") # e.g., "January"
    print(f"📊 Generating content for: {current_month}")
    
    # Updated Header to match app.py
    full_markdown_body = f"# Elite Prep – {current_month} Academic Master Plan\n\n"
    
    grades = ["9th Grade", "10th Grade", "11th Grade", "12th Grade"]
    
    for grade in grades:
        print(f"   > Generating for {grade}...")
        try:
            content = newsletter_utils.generate_monthly_plan(api_key, grade, current_month)
            full_markdown_body += f"## 📌 {grade}\n{content}\n\n---\n\n"
            time.sleep(2) # Prevent rate limiting
        except Exception as e:
            print(f"   ❌ Error generating {grade}: {e}")
            full_markdown_body += f"## {grade}\n(Content generation failed)\n\n"

    # Append Footer Signature
    full_markdown_body += """
Sent by Elite Prep Master Plan & Academic Consulting

Andy Lee  | Branch Director <br>
Elite Prep Suwanee powered by Elite Open School <br>
1291 Old Peachtree Rd. NW #127, Suwanee, GA 30024 <br>
Tel & Text: 470.253.1004
"""

    # 4. Send Email
    print("📤 Sending email...")
    # Updated Subject Line
    subject = f"[{current_month}] Monthly Academic Master Plan"
    
    # newsletter_utils.send_email handles logo embedding internally now
    success, msg = newsletter_utils.send_email(
        sender_email, 
        sender_password, 
        subscribers, 
        subject, 
        full_markdown_body
    )
    
    if success:
        print(f"✅ Success: {msg}")
    else:
        print(f"❌ Failed: {msg}")

    print("--- Done ---")

if __name__ == "__main__":
    main()
