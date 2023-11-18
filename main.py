import os
import email
import openai
import imaplib
import requests
import html2text
from dotenv import load_dotenv
from email.header import decode_header


def fetch_emails_from_sender():
    try:
        # load environment variables from .env file
        load_dotenv()

        # Email account credentials
        IMAP_SERVER = os.getenv('IMAP_SERVER')
        IMAP_USERNAME = os.getenv('IMAP_USERNAME')
        IMAP_PASSWORD = os.getenv('IMAP_PASSWORD')

        # Sender
        SENDER_EMAIL = os.getenv('SENDER_EMAIL')

        # connect to the IMAP server
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, 993)
        mail.login(IMAP_USERNAME, IMAP_PASSWORD)

        mail.select("inbox")
        status, response = mail.search(None, "FROM", SENDER_EMAIL)
        email_ids = response[0].split()

        emails = []

        for email_id in email_ids:
            # fetch the email
            status, response = mail.fetch(email_id, "(RFC822)")
            raw_email = response[0][1]

            # parse the email content using the email module
            email_message = email.message_from_bytes(raw_email)

            # extract the subject and decode it
            subject = decode_header(email_message["Subject"])[0][0]
            if isinstance(subject, bytes):
                # if it's bytes, decode to string
                subject = subject.decode()

            # extract the text content of the email
            body = ""

            for part in email_message.walk():
                content_type = part.get_content_type()
                if content_type == "text/plain":
                    charset = part.get_content_charset()
                    body += str(part.get_payload(decode=True), str(charset), "ignore")

            # Convert only to Text and remove html
            body = html2text.html2text(body)

            # split the email body into chunks of 2037 tokens (max 2048)
            chunk_size = 2037
            chunks = [body[i:i+chunk_size] for i in range(0, len(body), chunk_size)]

            emails.append((subject, chunks))

        return emails
    except Exception as e:
        print(f"An error occurred: {e}")
        return []
    
def summarize_chunks(chunks):
    try:
        # set up the OpenAI API client
        openai.api_key = os.getenv('OPENAI_API_KEY')

        # set up the API endpoint
        openai_url = "https://api.openai.com/v1/completions"

        # set up the request headers
        headers = {
            "Authorization": f"Bearer {openai.api_key}",
            "Content-Type": "application/json",
        }

        # summarize each chunk using OpenAI's text-davinci-003 model
        summaries = []
        for chunk in chunks:
            prompt = f"Summarize the content of this string using bulletpoints: {chunk}"
            data = {
                "model": "text-davinci-003",
                "prompt": prompt,
                "temperature": 1,
                "max_tokens": 1000
            }

            # make the HTTP request
            response = requests.post(openai_url, headers=headers, json=data)

            # extract the summary from the response
            # print(response.json())
            summary = response.json()["choices"][0]["text"].strip()
            summaries.append(summary)

        # join the bullet points into a single string
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

        # print the subject and bullet list
        print("Subject: " + subject)
        print("Summary: \n- " + bullet_list)
        print()

if __name__ == "__main__":
    main()
