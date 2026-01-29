import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import google.generativeai as genai
import pandas as pd
from datetime import datetime
import markdown
import base64

SUBSCRIBERS_FILE = "newsletter_subscribers.csv"

def load_subscribers():
    if not os.path.exists(SUBSCRIBERS_FILE):
        return []
    try:
        df = pd.read_csv(SUBSCRIBERS_FILE)
        # Ensure all are strings and strip whitespace
        return [str(e).strip() for e in df['email'].tolist() if pd.notna(e)]
    except Exception:
        return []

def save_subscriber(email):
    return save_subscribers([email]) > 0

def save_subscribers(email_list):
    current_emails = load_subscribers()
    added_count = 0
    for email in email_list:
        email = str(email).strip()
        if email and email not in current_emails:
            current_emails.append(email)
            added_count += 1
            
    if added_count > 0:
        df = pd.DataFrame({'email': current_emails})
        df.to_csv(SUBSCRIBERS_FILE, index=False)
    return added_count

def remove_subscriber(email):
    return remove_subscribers([email])

def remove_subscribers(email_list):
    current_emails = load_subscribers()
    # Normalize removal list too
    targets = [str(e).strip() for e in email_list]
    
    # Filter out emails to be removed
    new_emails = [e for e in current_emails if e not in targets]
    
    if len(new_emails) != len(current_emails):
        df = pd.DataFrame({'email': new_emails})
        df.to_csv(SUBSCRIBERS_FILE, index=False)
        return True
    return False

def generate_monthly_plan(api_key, grade, month_name):
    if not api_key: return "API Key Missing"
    
    genai.configure(api_key=api_key)
    # Using 'gemini-3-flash-preview' as defined in app.py for the Chatbot
    model = genai.GenerativeModel('gemini-3-flash-preview') 
    
    prompt = f"""
    You are an expert US College Admissions Consultant (Elite Level).
    Target Audience: High School Students in {grade}.
    Current Month: {month_name}.
    
    Create a highly motivating, professional 'Monthly Action Plan' for this specific month.
    
    Structure:
    0. **Title**: # {month_name} Monthly Action Plan
    1. **Greeting**: Start with "Welcome, {grade} Students." followed by a motivating opening about where they are in the academic year (e.g., "pivotal milestone", "halfway mark").
    2. **Target Focus** (1 clear headline starting with "Target Focus:")
    3. **Checklist** (3-4 specific, actionable items. MUST use bulleted checkboxes format: "- [ ] Item text...")
    4. **Consultant's Tip** (Headline: "### Consultant's Tip", followed by bold advice)
    
    IMPORTANT: Do NOT use strikethrough (~~text~~) formatting. If something is important, use **Bold** instead.
    Output in English. Use Markdown formatting.
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error generating content: {e}"

def send_email(sender_email, sender_password, recipients, subject, body_markdown):
    # Force reload environment variables to get the latest password
    from dotenv import load_dotenv
    load_dotenv(override=True)
    
    # If arguments are passed as None/Empty by caller who might have old state, try fetching from env again
    if not sender_password or sender_password.startswith("!"):
        sender_password = os.getenv("SENDER_PASSWORD")
        
    if not recipients: return False, "No recipients"
    
    try:
        # Connect to Gmail SMTP once for the batch
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)

        # Convert Markdown to HTML for Email
        html_content = markdown.markdown(body_markdown)
        
        # Determine Logo HTML with CID/Resize Logic
        # We process the logo ONCE, then attach readability to each email
        logo_cid = "logo_image"
        has_logo = False
        img_data = None
        
        if os.path.exists("logo.png"):
            has_logo = True
            try:
                from PIL import Image
                import io
                with open("logo.png", "rb") as f:
                    raw_data = f.read()
                    try:
                         with Image.open(io.BytesIO(raw_data)) as img:
                            base_width = 75 # REDUCED TO 75px AS REQUESTED
                            w_percent = (base_width / float(img.size[0]))
                            h_size = int((float(img.size[1]) * float(w_percent)))
                            img = img.resize((base_width, h_size), Image.Resampling.LANCZOS)
                            
                            byte_io = io.BytesIO()
                            img.save(byte_io, 'PNG')
                            img_data = byte_io.getvalue()
                    except Exception as resize_err:
                        print(f"Resize failed, using original: {resize_err}")
                        img_data = raw_data
            except Exception as e:
                print(f"Error processing logo: {e}")
                has_logo = False

        # Logo HTML for body
        if has_logo:
             logo_html = f'<div style="text-align: center; margin-bottom: 20px;"><img src="cid:{logo_cid}" alt="Elite Prep Logo" style="max-width: 75px;"></div>'
        else:
             logo_html = ""

        # Construct Full HTML Body
        full_html_template = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                {logo_html}
                {html_content}
                <hr style="margin-top: 30px; border: 0; border-top: 1px solid #eee;">
            </div>
        </body>
        </html>
        """

        # LOOP THROUGH RECIPIENTS AND SEND INDIVIDUALLY
        sent_count = 0
        failed_recipients = []
        
        from email.mime.image import MIMEImage

        for recipient in recipients:
            try:
                msg = MIMEMultipart("related")
                msg["From"] = sender_email
                msg["To"] = recipient # Individual To
                msg["Subject"] = subject
                
                msg_alternative = MIMEMultipart("alternative")
                msg.attach(msg_alternative)
                
                msg_alternative.attach(MIMEText(body_markdown, "plain"))
                msg_alternative.attach(MIMEText(full_html_template, "html"))
                
                # Attach Logo if exists
                if has_logo and img_data:
                    img_attachment = MIMEImage(img_data)
                    img_attachment.add_header('Content-ID', f'<{logo_cid}>')
                    img_attachment.add_header('Content-Disposition', 'inline', filename="logo.png")
                    msg.attach(img_attachment)
                
                server.sendmail(sender_email, recipient, msg.as_string())
                sent_count += 1
            except Exception as e:
                print(f"Failed to send to {recipient}: {e}")
                failed_recipients.append(recipient)

        server.quit()
        
        if failed_recipients:
            return True, f"Sent individually to {sent_count} recipients. Failed: {', '.join(failed_recipients)}"
        return True, f"Emails sent individually to {sent_count} recipients."
        
    except Exception as e:
        return False, str(e)
