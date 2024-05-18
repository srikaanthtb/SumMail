import os
import email
from plistlib import UID  # This import is unused and can be removed
import openai
import imaplib
import requests
import html2text
import smtplib, ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from email.header import decode_header

def fetch_emails_from_sender():
    try:
        # Load environment variables from .env file
        load_dotenv()

        # Email account credentials
        IMAP_SERVER = os.getenv('IMAP_SERVER')
        IMAP_USERNAME = os.getenv('IMAP_USERNAME')
        IMAP_PASSWORD = os.getenv('IMAP_PASSWORD')

        # Sender
        SENDER_EMAIL = os.getenv('SENDER_EMAIL')

        # Connect to the IMAP server
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, 993)
        mail.login(IMAP_USERNAME, IMAP_PASSWORD)

        mail.select("inbox")
        status, response = mail.search(None, "UNSEEN FROM", SENDER_EMAIL)
        
        email_ids = response[0].split()

        emails = []
        for email_id in email_ids:
            # Fetch the email
            status, response = mail.fetch(email_id, "(RFC822)")
            raw_email = response[0][1]

            # Parse the email content using the email module
            email_message = email.message_from_bytes(raw_email)

            # Extract the subject and decode it
            subject = decode_header(email_message["Subject"])[0][0]
            if isinstance(subject, bytes):
                # If it's bytes, decode to string
                subject = subject.decode()

            # Extract the text content of the email
            body = ""

            for part in email_message.walk():
                content_type = part.get_content_type()
                if content_type == "text/plain":
                    charset = part.get_content_charset()
                    body += str(part.get_payload(decode=True), str(charset), "ignore")

            # Convert only to Text and remove html
            body = html2text.html2text(body)

            # Split the email body into chunks of 2037 tokens (max 2048)
            chunk_size = 2037
            chunks = [body[i:i+chunk_size] for i in range(0, len(body), chunk_size)]

            emails.append((subject, chunks))

        return emails
    except Exception as e:
        print(f"An error occurred: {e}")
        return []
    
def summarize_chunks(chunks):
    try:
        # Set up the OpenAI API client
        openai.api_key = os.getenv('OPENAI_API_KEY')

        # Set up the API endpoint
        openai_url = "https://api.openai.com/v1/chat/completions"

        # Set up the request headers
        headers = {
            "Authorization": f"Bearer {openai.api_key}",
            "Content-Type": "application/json",
        }

        # Summarize each chunk using OpenAI's gpt-4 model
        summaries = []
        for chunk in chunks:
            messages = [
                {"role": "system", "content": "Your job is to summarize the content of email newsletters. Highlight the main points, important updates, and key takeaways."},
                {"role": "user", "content": f"Summarize the content of this email into bullet points: {chunk}"}
            ]
            data = {
                "model": "gpt-4o",
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 1000
            }

            # Make the HTTP request
            response = requests.post(openai_url, headers=headers, json=data)

            # Extract the summary from the response
            summary = response.json()['choices'][0]['message']['content'].strip()
            summaries.append(summary)

        # Join the bullet points into a single string
        bullet_list = "\n- ".join(summaries)

        return bullet_list
    except Exception as e:
        print(f"An error occurred: {e}")

def main():
    emails = fetch_emails_from_sender()
    if not emails:
        print("No emails found from the specified sender.")
        return
    for subject, chunks in emails:
        bullet_list = summarize_chunks(chunks)

        if not bullet_list:
            print(f"Failed to summarize email with subject: {subject}")
            continue

        # Print the subject and bullet list
        print("Subject: " + subject)
        print("Summary: \n- " + bullet_list)
        print()

        SMTP_SERVER = os.getenv('SMTP_SERVER')
        PORT = 465
        EMAIL = os.getenv('IMAP_USERNAME')
        EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')

        # Create email message
        message = MIMEMultipart()
        message["From"] = EMAIL
        message["To"] = EMAIL
        message["Subject"] = f"Summary of: {subject}"
        message.attach(MIMEText(f"Summary of email:\n- {bullet_list}", "plain"))

        # Send email using SMTP
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_SERVER, PORT, context=context) as server:
            server.login(EMAIL, EMAIL_PASSWORD)
            server.sendmail(EMAIL, EMAIL, message.as_string())

if __name__ == "__main__":
    main()
