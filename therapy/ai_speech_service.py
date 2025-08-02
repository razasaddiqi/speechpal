import json
import asyncio
import aiohttp
import logging
from django.conf import settings
from asgiref.sync import sync_to_async
import math
import re

logger = logging.getLogger(__name__)

class AISpeechService:
    """AI-powered speech analysis service for Django backend"""
    
    def __init__(self):
        self.openai_key = settings.OPENAI_API_KEY
        self.elevenlabs_key = settings.ELEVENLABS_API_KEY
        self.voice_id = settings.ELEVENLABS_VOICE_ID
        self.use_mock = settings.USE_MOCK_AI
        
    async def analyze_speech_with_ai(self, spoken_text: str, user_age: int = 8) -> dict:
        """Analyze speech using OpenAI and return detailed feedback"""
        try:
            if self.use_mock:
                return await self._get_mock_analysis(spoken_text)
            
            prompt = f"""You are a pediatric speech therapist AI helping children (age {user_age}) improve their speech. 
            Analyze the given text for:
            1. Pronunciation clarity (0-100)
            2. Grammar correctness (0-100) 
            3. Vocabulary appropriateness (0-100)
            4. Specific words that need improvement
            5. Encouraging feedback

            Respond ONLY in this JSON format:
            {{
                "clarity_score": 85,
                "grammar_score": 90,
                "vocabulary_score": 95,
                "overall_score": 90,
                "difficult_words": ["pronunciation", "specific"],
                "improvement_suggestions": ["Try to pronounce 'pronunciation' as pro-nun-see-AY-shun"],
                "encouragement": "Great job! Your speech is getting clearer!",
                "pronunciation_tips": "Remember to slow down when saying difficult words.",
                "experience_gained": 15
            }}"""

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    'https://api.openai.com/v1/chat/completions',
                    headers={
                        'Authorization': f'Bearer {self.openai_key}',
                        'Content-Type': 'application/json',
                    },
                    json={
                        'model': 'gpt-4',
                        'messages': [
                            {'role': 'system', 'content': prompt},
                            {'role': 'user', 'content': f'Analyze this speech: "{spoken_text}"'}
                        ],
                        'max_tokens': 500,
                        'temperature': 0.3,
                    }
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        content = data['choices'][0]['message']['content']
                        return json.loads(content)
                    else:
                        logger.error(f'OpenAI API Error: {response.status}')
                        return await self._get_mock_analysis(spoken_text)
                        
        except Exception as e:
            logger.error(f'AI Analysis Error: {e}')
            return await self._get_mock_analysis(spoken_text)

    async def transcribe_audio_with_whisper(self, audio_bytes: bytes) -> str:
        """Transcribe audio using OpenAI Whisper API"""
        try:
            if self.use_mock:
                return "Hello, this is a test transcription."
            
            async with aiohttp.ClientSession() as session:
                # Create form data with audio file
                data = aiohttp.FormData()
                data.add_field('file', 
                             audio_bytes,
                             filename='audio.wav',
                             content_type='audio/wav')
                data.add_field('model', 'whisper-1')
                data.add_field('response_format', 'text')
                
                async with session.post(
                    'https://api.openai.com/v1/audio/transcriptions',
                    headers={
                        'Authorization': f'Bearer {self.openai_key}',
                    },
                    data=data
                ) as response:
                    if response.status == 200:
                        transcribed_text = await response.text()
                        logger.info(f'Whisper transcription successful: {transcribed_text[:100]}...')
                        return transcribed_text.strip()
                    else:
                        error_text = await response.text()
                        logger.error(f'Whisper API Error: {response.status} - {error_text}')
                        raise Exception(f'Whisper transcription failed: {response.status}')
                        
        except Exception as e:
            logger.error(f'Whisper transcription error: {e}')
            raise e

    async def generate_spoken_feedback_audio(self, feedback_text: str) -> bytes:
        """Generate audio feedback using ElevenLabs TTS"""
        try:
            if self.use_mock:
                return None  # Will use system TTS
                
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f'https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}',
                    headers={
                        'xi-api-key': self.elevenlabs_key,
                        'Content-Type': 'application/json',
                    },
                    json={
                        'text': feedback_text,
                        'model_id': 'eleven_monolingual_v1',
                        'voice_settings': {
                            'stability': 0.5,
                            'similarity_boost': 0.5,
                            'style': 0.2,  # More child-friendly
                            'use_speaker_boost': True
                        }
                    }
                ) as response:
                    if response.status == 200:
                        return await response.read()
                    else:
                        logger.error(f'ElevenLabs API Error: {response.status}')
                        return None
                        
        except Exception as e:
            logger.error(f'TTS Generation Error: {e}')
            return None

    async def _get_mock_analysis(self, spoken_text: str) -> dict:
        """Generate mock analysis for demo purposes"""
        words = spoken_text.lower().split()
        word_count = len(words)
        
        # Mock difficult words detection
        difficult_words = []
        common_difficult_words = [
            'pronunciation', 'specific', 'beautiful', 'comfortable', 
            'probably', 'definitely', 'especially', 'restaurant',
            'library', 'temperature', 'vegetables', 'chocolate'
        ]
        
        for word in words:
            clean_word = re.sub(r'[^\w]', '', word.lower())
            if clean_word in common_difficult_words:
                difficult_words.append(word)

        # Mock scoring based on word count and complexity
        clarity_score = min(100, 60 + (word_count * 3) + (10 if len(spoken_text) > 50 else 0))
        grammar_score = min(100, 70 + (word_count * 2) + (5 if '.' in spoken_text else 0))
        vocabulary_score = min(100, 75 + (word_count * 2) + (len([w for w in words if len(w) > 6]) * 3))
        overall_score = (clarity_score + grammar_score + vocabulary_score) / 3

        # Generate contextual feedback
        if overall_score >= 85:
            encouragement = "Excellent speech! You're speaking very clearly and confidently!"
            pronunciation_tips = "Keep up the fantastic work! Your pronunciation is getting better every day."
        elif overall_score >= 70:
            encouragement = "Great job! Your speech is improving nicely!"
            pronunciation_tips = "Try to speak a little slower and focus on each word."
        elif overall_score >= 55:
            encouragement = "Good effort! Keep practicing and you'll get even better!"
            pronunciation_tips = "Take your time with each word. Break difficult words into smaller parts."
        else:
            encouragement = "Nice try! Every time you practice, you're getting better!"
            pronunciation_tips = "Let's practice saying words slowly and clearly together."

        # Generate specific suggestions for difficult words
        improvement_suggestions = []
        pronunciation_guides = {
            'pronunciation': "Try 'pronunciation' as: pro-nun-see-AY-shun",
            'specific': "Say 'specific' as: spuh-SIF-ik",
            'beautiful': "Say 'beautiful' as: BYOO-tuh-ful",
            'comfortable': "Say 'comfortable' as: KUHM-fer-tuh-bul",
            'probably': "Say 'probably' as: PROB-uh-blee",
            'definitely': "Say 'definitely' as: DEF-uh-nit-lee",
            'especially': "Say 'especially' as: ih-SPESH-uh-lee",
            'restaurant': "Say 'restaurant' as: RES-tuh-ront",
            'library': "Say 'library' as: LI-brer-ee",
            'temperature': "Say 'temperature' as: TEM-per-uh-chur",
            'vegetables': "Say 'vegetables' as: VEJ-tuh-buls",
            'chocolate': "Say 'chocolate' as: CHOK-lit"
        }

        for word in difficult_words:
            clean_word = re.sub(r'[^\w]', '', word.lower())
            if clean_word in pronunciation_guides:
                improvement_suggestions.append(pronunciation_guides[clean_word])
            else:
                improvement_suggestions.append(f"Take your time with '{word}' - break it into smaller parts")

        if not improvement_suggestions:
            improvement_suggestions.append("Try to speak with confidence and take your time!")

        return {
            'clarity_score': float(clarity_score),
            'grammar_score': float(grammar_score),
            'vocabulary_score': float(vocabulary_score),
            'overall_score': float(overall_score),
            'difficult_words': difficult_words,
            'improvement_suggestions': improvement_suggestions,
            'encouragement': encouragement,
            'pronunciation_tips': pronunciation_tips,
            'experience_gained': max(5, int(overall_score / 10)),
        }

    def generate_comprehensive_feedback(self, analysis: dict) -> str:
        """Generate comprehensive spoken feedback text"""
        encouragement = analysis.get('encouragement', 'Great job!')
        pronunciation_tips = analysis.get('pronunciation_tips', '')
        improvements = analysis.get('improvement_suggestions', [])
        experience_gained = analysis.get('experience_gained', 0)
        overall_score = analysis.get('overall_score', 0)

        feedback_parts = []
        
        # Start with encouragement
        feedback_parts.append(encouragement)

        # Add score-based feedback
        if overall_score >= 85:
            feedback_parts.append(f"You scored {int(overall_score)} percent! That's amazing!")
        elif overall_score >= 70:
            feedback_parts.append(f"You scored {int(overall_score)} percent! You're doing really well!")
        else:
            feedback_parts.append(f"You scored {int(overall_score)} percent. Let's work together to make it even better!")

        # Add specific improvement suggestions (limit to 2)
        if improvements:
            feedback_parts.append("Here's a tip to help you improve:")
            feedback_parts.append(improvements[0])
            
            if len(improvements) > 1:
                feedback_parts.append(f"Also, {improvements[1].lower()}")

        # Add pronunciation tips
        if pronunciation_tips:
            feedback_parts.append(pronunciation_tips)

        # Add experience points encouragement
        feedback_parts.append(f"You earned {experience_gained} experience points! Keep practicing!")

        return ' '.join(feedback_parts) 