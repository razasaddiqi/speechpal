import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from .models import UserProfile, SpeechSession, UnlockedCustomization
from .ai_speech_service import AISpeechService
from .serializers import SpeechExerciseSerializer, UserProfileSerializer
import base64
import time
import hashlib

logger = logging.getLogger(__name__)

class SpeechAnalysisConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time speech analysis"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ai_service = AISpeechService()
        self.user = None
        self.user_profile = None
        self.processed_requests = set()  # Track processed requests to prevent duplicates

    async def connect(self):
        """Accept WebSocket connection"""
        # Get authorization header from scope
        headers = dict(self.scope.get('headers', []))
        auth_header = headers.get(b'authorization', b'').decode()
        
        if not auth_header.startswith('Token '):
            await self.close()
            return
            
        # Extract token and authenticate user
        token = auth_header.split(' ')[1]
        from rest_framework.authtoken.models import Token
        from channels.db import database_sync_to_async
        
        @database_sync_to_async
        def get_user_from_token(token_key):
            try:
                token_obj = Token.objects.get(key=token_key)
                return token_obj.user
            except Token.DoesNotExist:
                return None
                
        self.user = await get_user_from_token(token)
        if not self.user:
            await self.close() 
            return
            
        await self.accept()
        
        # Load user profile
        self.user_profile = await self.get_user_profile()
        
        # Send initial connection confirmation
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'message': 'Speech analysis service connected',
            'user_level': self.user_profile.level if self.user_profile else 1
        }))

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        logger.info(f"Speech analysis WebSocket disconnected: {close_code}")

    async def receive(self, text_data):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'analyze_speech':
                await self.handle_speech_analysis(data)
            elif message_type == 'get_pronunciation_help':
                await self.handle_pronunciation_help(data)
            elif message_type == 'ping':
                await self.send(text_data=json.dumps({'type': 'pong'}))
            else:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': f'Unknown message type: {message_type}'
                }))
                
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON format'
            }))
        except Exception as e:
            logger.error(f"Error handling WebSocket message: {e}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Internal server error'
            }))

    def _generate_request_id(self, text, timestamp):
        """Generate unique request ID to prevent duplicate processing"""
        content = f"{self.user.id}_{text}_{timestamp}"
        return hashlib.md5(content.encode()).hexdigest()

    async def handle_speech_analysis(self, data):
        """Handle speech analysis request with deduplication"""
        try:
            spoken_text = data.get('text', '').strip()
            duration_seconds = data.get('duration', 0)
            timestamp = data.get('timestamp', int(time.time() * 1000))
            
            if not spoken_text:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'No text provided for analysis'
                }))
                return

            # Generate request ID for deduplication
            request_id = self._generate_request_id(spoken_text, timestamp)
            
            # Check if this request was already processed
            if request_id in self.processed_requests:
                logger.warning(f"Duplicate request detected and ignored: {request_id}")
                return
            
            # Mark request as being processed
            self.processed_requests.add(request_id)

            # Send processing status
            await self.send(text_data=json.dumps({
                'type': 'analysis_started',
                'message': 'Analyzing your speech...'
            }))

            # Get AI analysis
            user_age = await self.get_user_age()
            analysis = await self.ai_service.analyze_speech_with_ai(spoken_text, user_age)
            
            # Generate comprehensive feedback text
            feedback_text = self.ai_service.generate_comprehensive_feedback(analysis)
            
            # Generate audio feedback (optional)
            audio_data = None
            try:
                audio_bytes = await self.ai_service.generate_spoken_feedback_audio(feedback_text)
                if audio_bytes:
                    audio_data = base64.b64encode(audio_bytes).decode('utf-8')
            except Exception as e:
                logger.warning(f"Audio generation failed: {e}")

            # Save speech session and update user progress (atomic operation)
            session_result = await self.save_speech_session_atomic(analysis, spoken_text, duration_seconds, request_id)
            
            if not session_result:
                # Session already exists, this is a duplicate
                logger.warning(f"Duplicate session detected for request: {request_id}")
                return

            old_level = session_result.get('old_level', 1)
            new_level = session_result.get('new_level', 1)
            level_up = new_level > old_level
            
            # Get unlocked items if level up occurred
            unlocked_items = []
            if level_up:
                unlocked_items = await self.get_newly_unlocked_items(new_level)

            # Send single comprehensive response with all data
            response = {
                'type': 'analysis_complete',
                'request_id': request_id,  # Include request ID for client-side deduplication
                'analysis': {
                    'clarity_score': analysis['clarity_score'],
                    'grammar_score': analysis['grammar_score'],
                    'vocabulary_score': analysis['vocabulary_score'],
                    'overall_score': analysis['overall_score'],
                    'difficult_words': analysis['difficult_words'],
                    'improvement_suggestions': analysis['improvement_suggestions'],
                    'encouragement': analysis['encouragement'],
                    'pronunciation_tips': analysis['pronunciation_tips'],
                    'experience_gained': analysis['experience_gained'],
                    'strengths': self.generate_strengths(analysis),
                    'areas_for_improvement': analysis['improvement_suggestions'],
                    'feedback_text': feedback_text,
                    'word_count': len(spoken_text.split())
                },
                'user_progress': {
                    'level': new_level,
                    'experience': session_result.get('total_experience', 0),
                    'level_up': level_up,
                    'unlocked_items': unlocked_items,
                    'achievements': []  # For future use
                },
                'audio_feedback': audio_data,
                'session_id': session_result.get('session_id'),
                'duration': duration_seconds
            }
            
            # Send the single comprehensive response
            await self.send(text_data=json.dumps(response))
            
            logger.info(f"Speech analysis completed successfully for request: {request_id}, Level: {old_level}->{new_level}, XP: {analysis['experience_gained']}")

        except Exception as e:
            logger.error(f"Speech analysis error: {e}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Failed to analyze speech. Please try again.'
            }))

    async def handle_pronunciation_help(self, data):
        """Handle pronunciation help request"""
        try:
            word = data.get('word', '').strip().lower()
            
            pronunciation_guides = {
                'pronunciation': 'pro-nun-see-AY-shun',
                'specific': 'spuh-SIF-ik',
                'beautiful': 'BYOO-tuh-ful',
                'comfortable': 'KUHM-fer-tuh-bul',
                'probably': 'PROB-uh-blee',
                'definitely': 'DEF-uh-nit-lee',
                'especially': 'ih-SPESH-uh-lee',
                'restaurant': 'RES-tuh-ront',
                'library': 'LI-brer-ee',
                'temperature': 'TEM-per-uh-chur',
                'vegetables': 'VEJ-tuh-buls',
                'chocolate': 'CHOK-lit'
            }
            
            phonetic = pronunciation_guides.get(word, word.replace('', '-'))
            guide_text = f"Let's practice the word {word}. It sounds like {phonetic}. Now you try!"
            
            # Generate audio for pronunciation guide
            audio_data = None
            try:
                audio_bytes = await self.ai_service.generate_spoken_feedback_audio(guide_text)
                if audio_bytes:
                    audio_data = base64.b64encode(audio_bytes).decode('utf-8')
            except Exception as e:
                logger.warning(f"Pronunciation audio generation failed: {e}")
            
            await self.send(text_data=json.dumps({
                'type': 'pronunciation_help',
                'word': word,
                'phonetic': phonetic,
                'guide_text': guide_text,
                'audio_data': audio_data
            }))
            
        except Exception as e:
            logger.error(f"Pronunciation help error: {e}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Failed to get pronunciation help'
            }))

    @database_sync_to_async
    def get_user_profile(self):
        """Get or create user profile"""
        try:
            profile, created = UserProfile.objects.get_or_create(
                user=self.user,
                defaults={
                    'level': 1,
                    'experience_points': 0
                }
            )
            return profile
        except Exception as e:
            logger.error(f"Error getting user profile: {e}")
            return None

    @database_sync_to_async
    def get_user_age(self):
        """Get user age from profile, default to 8"""
        try:
            if self.user_profile and hasattr(self.user_profile, 'age'):
                return self.user_profile.age
            return 8  # Default age for children
        except:
            return 8

    @database_sync_to_async
    def save_speech_session_atomic(self, analysis, spoken_text, duration_seconds, request_id):
        """Save speech session and update user progress atomically with duplicate prevention"""
        from django.db import transaction
        from datetime import timedelta
        
        try:
            with transaction.atomic():
                # Check if session with this request_id already exists
                existing_session = SpeechSession.objects.filter(
                    user=self.user,
                    session_id=request_id
                ).first()
                
                if existing_session:
                    logger.warning(f"Session already exists for request_id: {request_id}")
                    return None  # Duplicate session
                
                # Get current user profile with lock to prevent race conditions
                profile = UserProfile.objects.select_for_update().get(user=self.user)
                old_level = profile.level
                old_experience = profile.experience_points
                
                # Create speech session with request_id
                session = SpeechSession.objects.create(
                    user=self.user,
                    session_id=request_id,  # Add this field to model if not exists
                    words_spoken=len(spoken_text.split()),
                    duration=timedelta(seconds=duration_seconds),
                    clarity_score=analysis['clarity_score'],
                    fluency_score=analysis['grammar_score'],
                    confidence_score=analysis['vocabulary_score'],
                    overall_score=analysis['overall_score'],
                    experience_gained=analysis['experience_gained']
                )
                
                # Update user profile atomically
                profile.experience_points += analysis['experience_gained']
                
                # Calculate new level (every 100 XP = 1 level)
                new_level = (profile.experience_points // 100) + 1
                profile.level = new_level
                profile.save()
                
                # Update the instance variable
                self.user_profile = profile
                
                logger.info(f"Session saved: ID={session.id}, User={self.user.username}, XP: {old_experience} -> {profile.experience_points} (+{analysis['experience_gained']}), Level: {old_level} -> {new_level}")
                
                return {
                    'session_id': str(session.id),
                    'old_level': old_level,
                    'new_level': new_level,
                    'total_experience': profile.experience_points,
                    'experience_gained': analysis['experience_gained']
                }
                
        except Exception as e:
            logger.error(f"Error saving speech session atomically: {e}")
            return None

    @database_sync_to_async
    def get_newly_unlocked_items(self, new_level):
        """Get items unlocked at the new level"""
        try:
            # Define level-based unlocks
            level_unlocks = {
                2: [{'type': 'body_color', 'name': 'golden'}],
                3: [{'type': 'eye_color', 'name': 'blue'}],
                4: [{'type': 'accessory', 'name': 'hat'}],
                5: [{'type': 'body_color', 'name': 'white'}],
                6: [{'type': 'eye_color', 'name': 'green'}],
                7: [{'type': 'accessory', 'name': 'bow_tie'}],
                8: [{'type': 'body_color', 'name': 'spotted'}],
                9: [{'type': 'eye_color', 'name': 'amber'}],
                10: [{'type': 'accessory', 'name': 'crown'}]
            }
            
            unlocked_items = level_unlocks.get(new_level, [])
            
            # Create unlock records
            for item in unlocked_items:
                UnlockedCustomization.objects.get_or_create(
                    user=self.user,
                    customization_type=item['type'],
                    customization_value=item['name']
                )
            
            return unlocked_items
            
        except Exception as e:
            logger.error(f"Error getting unlocked items: {e}")
            return []

    def generate_strengths(self, analysis):
        """Generate strengths list from analysis"""
        strengths = []
        clarity_score = analysis.get('clarity_score', 0)
        grammar_score = analysis.get('grammar_score', 0)
        vocabulary_score = analysis.get('vocabulary_score', 0)
        
        if clarity_score >= 80:
            strengths.append("Excellent clarity in speech!")
        if grammar_score >= 80:
            strengths.append("Great grammar usage!")
        if vocabulary_score >= 80:
            strengths.append("Wonderful vocabulary!")
        if clarity_score >= 70:
            strengths.append("Good pronunciation!")
        if grammar_score >= 70:
            strengths.append("Nice sentence structure!")
        
        if not strengths:
            strengths.append("Keep practicing - you're improving!")
        
        return strengths 