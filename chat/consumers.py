import json
import os
from openai import OpenAI, AsyncOpenAI

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
aclient = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])

from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import AnonymousUser
from rest_framework.authtoken.models import Token
from .models import ChatSession, ChatMessage
from asgiref.sync import sync_to_async

# 1) Define the function schema
IMAGE_FUNCTION = {
    "name": "generate_image",
    "description": "Generate an image with DALL-E",
    "parameters": {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "The prompt to generate an image for"
            },
            "n": {
                "type": "integer",
                "description": "Number of images to generate",
                "default": 1
            },
            "size": {
                "type": "string",
                "description": "Size of the generated image",
                "enum": ["256x256", "512x512", "1024x1024"],
                "default": "512x512"
            }
        },
        "required": ["prompt"]
    }
}

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.session_id = self.scope['url_route']['kwargs']['session_id']
        # Try to obtain the DRF token from either query parameters or headers
        query_string = self.scope["query_string"].decode()
        token_key = None
        if "token=" in query_string:
            token_key = query_string.split("token=")[-1].split("&")[0]
        if not token_key:
            for header_name, header_value in self.scope.get("headers", []):
                if header_name.decode().lower() == "authorization":
                    auth_header = header_value.decode()
                    if auth_header.lower().startswith("token "):
                        token_key = auth_header.split(" ", 1)[1]
                    else:
                        token_key = auth_header
                    break
        self.user = None
        token = await self.get_user_from_token(token_key)
        if token:
            self.user = token.user
        else:
            await self.close()
            return
        await self.accept()
        self.session, _ = await self.create_session(self.session_id, self.user)

    @sync_to_async
    def create_session(self, session_id, user):
        return ChatSession.objects.get_or_create(id=session_id, defaults={'user': user})

    @sync_to_async
    def get_user_from_token(self, token):
        try:
            return Token.objects.select_related('user').get(key=token)
        except Token.DoesNotExist:
            return None

    @sync_to_async
    def create_chat_message(self, session, content, role):
        ChatMessage.objects.create(session=session, role=role, content=content)

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return
        data = json.loads(text_data)
        user_text = data.get('message', '')
        await self.create_chat_message(self.session, user_text, 'user')
        await self.stream_openai_response(user_text)

    async def stream_openai_response(self, user_text):
        # 2) Ask the model, allowing it to “call” our generate_image function
        response_stream = await aclient.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": user_text}],
            stream=True,
            functions=[IMAGE_FUNCTION],
            function_call="auto"
        )

        assistant_content = ""
        function_call = None
        function_args = ""

        # 3) Stream tokens & capture any function_call
        async for chunk in response_stream:
            delta = chunk.choices[0].delta

            # a) Content tokens
            if delta.content:
                assistant_content += delta.content
                await self.send(json.dumps({
                    "eos": False,
                    "content": delta.content
                }))

            # b) Function call name
            if delta.function_call:
                if delta.function_call.name:
                    function_call = delta.function_call.name
                if delta.function_call.arguments:
                    function_args += delta.function_call.arguments

        # 4) If the model requested image gen, execute and stream that
        if function_call == "generate_image":
            args = json.loads(function_args)
            img_response = client.images.generate(
                prompt=args["prompt"],
                n=args.get("n", 1),
                size=args.get("size", "512x512")
            )
            image_url = img_response.data[0].url

            markdown_img = f"![{args['prompt']}]({image_url})"
            assistant_content += "\n\n" + markdown_img
            await self.send(json.dumps({
                "eos": False,
                "content": markdown_img
            }))

        # 5) Finally signal end-of-stream
        await self.send(json.dumps({"eos": True}))
        await self.create_chat_message(self.session, assistant_content, 'assistant')
