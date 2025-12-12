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

### DeviceHub

1. Open up a new websocket connection and paste the DeviceHub URL
2. In Headers, add "Authorization".
3. In the Authorization field, type in "Bearer" then a space, and paste your DeviceHub token.
   <img width="856" height="479" alt="image" src="https://github.com/user-attachments/assets/6ff6540d-066b-4ea2-a640-5bcaada9ea09" />
4. Go to the "Messages" tab and type in. Notice the control character at the end chr(30). It is required.

```
{
    "protocol": "json",
    "version": 1
}
```
5. You can then invoke "SubscribeToLocation" to get your device informations.
```
{
    "arguments": [
        69420
    ],
    "invocationId": "0",
    "target": "SubscribeToLocation",
    "type": 1
}
```
6. You should received the DeviceListInitialValuesReceived message back.

### ChallengeHub

1. Open up a new websocket connection and paste the DeviceHub URL
2. In Headers, add "Authorization".
3. In the Authorization field, type in "Bearer" then a space, and paste your DeviceHub token.
   <img width="856" height="479" alt="image" src="https://github.com/user-attachments/assets/6ff6540d-066b-4ea2-a640-5bcaada9ea09" />
4. Go to the "Messages" tab and type in. Notice the control character at the end chr(30). It is required.

```
{
    "protocol": "json",
    "version": 1
}
```
5. You can send various messages to the ChallengeHub to request different information. For the 2025-2026 season with the addition of Flex D, the messages were split between Winter Credit (Crédit Hivernal) and Flex D. Winter Credit messages will contain CH in their target, and Flex D event will contain Flex in their target. Each of rates has its own event id, for example, event 337 was for Winter Credits, and event 338 was for Flex D, both occured at the same time. You will have access to one, or the other, depending on your rate.


### Examples of various invokesto the ChallengeHub

#### SubscribeToEventCH or SubscribeToEventFlex

This invoke is used:
```
{
    "arguments": [
        {
            "locationHiloId": "urn:YOUR-URN",
            "eventId": ID(numberic)
        }
    ],
    "invocationId": "1",
    "target": "SubscribeToEventCH",
    "type": 1
}
```

And should return
```
EventCHDetailsInitialValuesReceived
````
Or 
```
EventFlexDetailsInitialValuesReceived
```



