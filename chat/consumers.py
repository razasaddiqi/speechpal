import json
import openai
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import AnonymousUser
from rest_framework.authtoken.models import Token
from .models import ChatSession, ChatMessage


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.session_id = self.scope['url_route']['kwargs']['session_id']
        token_key = self.scope['query_string'].decode().split('token=')[-1]
        self.user = None
        try:
            token = Token.objects.get(key=token_key)
            self.user = token.user
        except Token.DoesNotExist:
            await self.close()
            return
        await self.accept()
        self.session, _ = ChatSession.objects.get_or_create(id=self.session_id, defaults={'user': self.user})

    async def receive(self, text_data=None, bytes_data=None):
        if text_data is None:
            return
        data = json.loads(text_data)
        content = data.get('message', '')
        ChatMessage.objects.create(session=self.session, role='user', content=content)
        await self.stream_openai_response(content)

    async def stream_openai_response(self, content):
        openai.api_key = openai.api_key or self.scope.get('settings', {}).get('OPENAI_API_KEY')
        response = await openai.ChatCompletion.acreate(
            model='gpt-3.5-turbo',
            messages=[{'role': 'user', 'content': content}],
            stream=True,
        )
        assistant_content = ''
        async for chunk in response:
            delta = chunk['choices'][0]['delta']
            if 'content' in delta:
                assistant_content += delta['content']
                await self.send(json.dumps({'eos': False, 'content': delta['content']}))
        # handle dalle command
        if content.startswith('/image '):
            prompt = content[7:]
            img = openai.Image.create(prompt=prompt, n=1, size='512x512')
            url = img['data'][0]['url']
            assistant_content += f"![]({url})"
            await self.send(json.dumps({'eos': False, 'content': f"![]({url})"}))
        await self.send(json.dumps({'eos': True}))
        ChatMessage.objects.create(session=self.session, role='assistant', content=assistant_content)
