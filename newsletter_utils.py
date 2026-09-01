import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import google.generativeai as genai
from datetime import datetime
import markdown
import base64

SUBSCRIBERS_FILE = "newsletter_subscribers.csv"

def load_subscribers():
    if not os.path.exists(SUBSCRIBERS_FILE):
        return []
    try:
        import pandas as pd
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
        import pandas as pd
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
        import pandas as pd
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

LOGO_CID = "logo_image"


def load_logo_bytes(base_width=75):
    """logo.png 를 base_width 픽셀로 줄여 바이트로 돌려준다. 없으면 None."""
    if not os.path.exists("logo.png"):
        return None
    try:
        import io

        from PIL import Image
        with open("logo.png", "rb") as f:
            raw_data = f.read()
        try:
            with Image.open(io.BytesIO(raw_data)) as img:
                w_percent = base_width / float(img.size[0])
                h_size = int(float(img.size[1]) * w_percent)
                img = img.resize((base_width, h_size), Image.Resampling.LANCZOS)
                byte_io = io.BytesIO()
                img.save(byte_io, 'PNG')
                return byte_io.getvalue()
        except Exception as resize_err:
            print(f"Resize failed, using original: {resize_err}")
            return raw_data
    except Exception as e:
        print(f"Error processing logo: {e}")
        return None


def wrap_html(body_markdown, has_logo):
    """마크다운 본문을 이메일용 HTML 문서로 감싼다."""
    html_content = markdown.markdown(body_markdown)
    logo_html = (
        f'<div style="text-align: center; margin-bottom: 20px;">'
        f'<img src="cid:{LOGO_CID}" alt="Elite Prep Logo" style="max-width: 75px;">'
        f'</div>'
    ) if has_logo else ""
    return f"""
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


def build_message(sender_email, recipient, subject, body_markdown, img_data):
    """수신자 한 명에게 보낼 MIME 메시지를 만든다 (로고는 인라인 첨부)."""
    from email.mime.image import MIMEImage

    msg = MIMEMultipart("related")
    msg["From"] = sender_email
    msg["To"] = recipient
    msg["Subject"] = subject

    alt = MIMEMultipart("alternative")
    msg.attach(alt)
    alt.attach(MIMEText(body_markdown, "plain"))
    alt.attach(MIMEText(wrap_html(body_markdown, bool(img_data)), "html"))

    if img_data:
        img = MIMEImage(img_data)
        img.add_header('Content-ID', f'<{LOGO_CID}>')
        img.add_header('Content-Disposition', 'inline', filename="logo.png")
        msg.attach(img)
    return msg


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

        # 로고는 한 번만 처리해서 모든 메일에 인라인 첨부한다
        img_data = load_logo_bytes()

        # LOOP THROUGH RECIPIENTS AND SEND INDIVIDUALLY
        sent_count = 0
        failed_recipients = []

        for recipient in recipients:
            try:
                msg = build_message(sender_email, recipient, subject,
                                    body_markdown, img_data)
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
