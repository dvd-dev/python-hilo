# Using get_tokens.py
This python script will let you use it to log in to your Hilo account.

From there, you will be asked to copy the full HA redirect(callback) URL and go back to your python script and press enter.

Negotiation will take place and you will receive three distinct tokens:
- Your access token
- Your devicehub token
- Your challengehub token

Take care not to share your tokens as they are not encrypted and contain personally identifiable information.

# Using Postman to send payloads to devicehub or challengehub
## Prerequisite: you need to have your tokens on hand, they are relatively short lived so once you have them, get to connecting!
