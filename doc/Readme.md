# Using get_tokens.py
This python script will let you use it to log in to your Hilo account.

From there, you will be asked to copy the full HA redirect(callback) URL and go back to your python script and press enter.

Negotiation will take place and you will receive three distinct tokens:
- Your access token
- Your devicehub token
- Your challengehub token

Take care not to share your tokens as they are not encrypted and contain personally identifiable information.

1. Run get_tokens.py, you will be provided with a link. Either click it or copy it in your favourite browser.
<img width="1393" height="186" alt="image" src="https://github.com/user-attachments/assets/0b9559b1-1d9a-41ae-b4bf-185a5a5c588b" />

2. Login using your Hilo Credentials
   
   <img width="631" height="569" alt="image" src="https://github.com/user-attachments/assets/ad7c79a7-2402-44e8-9a0b-962406b89527" />

3. Once you get to this page, select the URL and copy it to clipboard
<img width="694" height="274" alt="image" src="https://github.com/user-attachments/assets/85989069-31a3-418d-b305-1f2378432d84" />
<img width="567" height="46" alt="image" src="https://github.com/user-attachments/assets/1d979626-6d93-46cb-aae0-50ef061a0d61" />

4. Go back to get_tokens.py and press enter, you'll get all 3 tokens:

<img width="1208" height="805" alt="image" src="https://github.com/user-attachments/assets/10258890-e935-4b16-8d16-12bdd340c001" />
   

# Using Postman to send payloads to devicehub or challengehub
## Prerequisite: you need to have your tokens on hand, they are relatively short lived so once you have them, get to connecting!


