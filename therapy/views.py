import logging
import time
from django.shortcuts import get_object_or_404
from django.db.models import Avg, Count, Q, Sum
from django.utils import timezone
from datetime import timedelta
from django.utils.dateparse import parse_duration
from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from core.models import User
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .webhook_logger import WebhookLogger

logger = logging.getLogger(__name__)

from .models import (
    UserProfile, CharacterCustomization, UnlockedCustomization,
    SpeechSession, Achievement, UserAchievement, SpeechExercise, ExerciseAttempt,
    OnboardingProfile, UserAvatar, ConversationSession, UserMemory,
)
from .serializers import (
    UserProfileSerializer, CharacterCustomizationSerializer, UnlockedCustomizationSerializer,
    SpeechSessionSerializer, AchievementSerializer, UserAchievementSerializer,
    SpeechExerciseSerializer, ExerciseAttemptSerializer, CharacterCustomizationOptionsSerializer,
    ProgressSummarySerializer, OnboardingProfileSerializer, UserAvatarSerializer,
    ConversationContextSerializer, ConversationFeedbackSerializer,
)


class UserProfileView(generics.RetrieveUpdateAPIView):
    """Get or update user's therapy profile"""
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        profile, created = UserProfile.objects.get_or_create(user=self.request.user)
        return profile


class CharacterCustomizationView(generics.RetrieveUpdateAPIView):
    """Get or update user's character customization"""
    serializer_class = CharacterCustomizationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        customization, created = CharacterCustomization.objects.get_or_create(user=self.request.user)
        return customization


class CharacterCustomizationOptionsView(APIView):
    """Get available customization options with unlock status"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        profile = get_object_or_404(UserProfile, user=user)
        unlocked = UnlockedCustomization.objects.filter(user=user)
        
        # Get all unlocked customizations
        unlocked_dict = {}
        for unlock in unlocked:
            if unlock.customization_type not in unlocked_dict:
                unlocked_dict[unlock.customization_type] = set()
            unlocked_dict[unlock.customization_type].add(unlock.customization_value)
        
        def get_customization_options(choices, customization_type):
            options = []
            for value, display_name in choices:
                level_required = self._get_level_requirement(customization_type, value)
                is_unlocked = (
                    level_required <= profile.level or 
                    value in unlocked_dict.get(customization_type, set())
                )
                options.append({
                    'value': value,
                    'display_name': display_name,
                    'level_required': level_required,
                    'is_unlocked': is_unlocked
                })
            return options

        data = {
            'body_colors': get_customization_options(CharacterCustomization.BODY_COLOR_CHOICES, 'body_color'),
            'eye_colors': get_customization_options(CharacterCustomization.EYE_COLOR_CHOICES, 'eye_color'),
            'accessories': get_customization_options(CharacterCustomization.ACCESSORY_CHOICES, 'accessory'),
        }
        
        serializer = CharacterCustomizationOptionsSerializer(data)
        return Response(serializer.data)
    
    def _get_level_requirement(self, customization_type, value):
        """Define level requirements for different customizations"""
        level_requirements = {
            'body_color': {
                'brown': 1, 'golden': 1, 'black': 2, 'white': 3,
                'spotted': 5, 'blue': 10, 'purple': 15, 'rainbow': 20
            },
            'eye_color': {
                'brown': 1, 'blue': 2, 'green': 3, 'amber': 4,
                'purple': 12, 'rainbow': 18
            },
            'accessory': {
                'none': 1, 'collar': 2, 'hat': 4, 'bow_tie': 6,
                'glasses': 8, 'cape': 12, 'crown': 16, 'wings': 20
            }
        }
        return level_requirements.get(customization_type, {}).get(value, 1)


class SpeechSessionListCreateView(generics.ListCreateAPIView):
    """List user's speech sessions or create a new one"""
    serializer_class = SpeechSessionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return SpeechSession.objects.filter(user=self.request.user).order_by('-created_at')

    def perform_create(self, serializer):
        session = serializer.save(user=self.request.user)
        self._update_user_progress(session)
        self._check_achievements(session)

    def _update_user_progress(self, session):
        """Update user's progress based on the speech session"""
        profile = UserProfile.objects.get(user=session.user)
        
        # Add experience points
        profile.experience_points += session.experience_gained
        
        # Update total speaking time
        if profile.total_speaking_time:
            profile.total_speaking_time += session.duration
        else:
            profile.total_speaking_time = session.duration
        
        # Update improvement score (weighted average)
        recent_sessions = SpeechSession.objects.filter(
            user=session.user,
            created_at__gte=timezone.now() - timedelta(days=7)
        )
        avg_score = recent_sessions.aggregate(avg_score=Avg('overall_score'))['avg_score']
        if avg_score:
            profile.improvement_score = avg_score
        
        # Level up if enough XP
        required_xp = profile.level * 100
        if profile.experience_points >= required_xp:
            profile.level += 1
            self._unlock_level_rewards(profile)
        
        profile.save()

    def _unlock_level_rewards(self, profile):
        """Unlock rewards when user levels up"""
        # Auto-unlock customizations based on level
        customizations_to_unlock = []
        
        if profile.level == 2:
            customizations_to_unlock.extend([
                ('body_color', 'black'),
                ('eye_color', 'blue')
            ])
        elif profile.level == 5:
            customizations_to_unlock.append(('body_color', 'spotted'))
        elif profile.level == 10:
            customizations_to_unlock.append(('body_color', 'blue'))
        # Add more level rewards as needed
        
        for customization_type, value in customizations_to_unlock:
            UnlockedCustomization.objects.get_or_create(
                user=profile.user,
                customization_type=customization_type,
                customization_value=value,
                defaults={'level_required': profile.level}
            )

    def _check_achievements(self, session):
        """Check if user has earned any achievements"""
        user = session.user
        profile = UserProfile.objects.get(user=user)
        
        # Check for achievements user hasn't earned yet
        earned_achievements = UserAchievement.objects.filter(user=user).values_list('achievement_id', flat=True)
        available_achievements = Achievement.objects.exclude(id__in=earned_achievements)
        
        for achievement in available_achievements:
            if self._check_achievement_condition(achievement, user, profile, session):
                UserAchievement.objects.create(user=user, achievement=achievement)
                # Award experience points
                profile.experience_points += achievement.experience_reward
                profile.save()
                
                # Unlock customization reward if any
                if achievement.customization_reward:
                    reward = achievement.customization_reward
                    UnlockedCustomization.objects.get_or_create(
                        user=user,
                        customization_type=reward['type'],
                        customization_value=reward['value'],
                        defaults={'level_required': profile.level}
                    )

    def _check_achievement_condition(self, achievement, user, profile, session):
        """Check if achievement condition is met"""
        if achievement.achievement_type == 'speaking_time':
            total_seconds = profile.total_speaking_time.total_seconds()
            return total_seconds >= achievement.target_value
        
        elif achievement.achievement_type == 'words_spoken':
            total_words = SpeechSession.objects.filter(user=user).aggregate(
                total=Sum('words_spoken')
            )['total'] or 0
            return total_words >= achievement.target_value
        
        elif achievement.achievement_type == 'level_milestone':
            return profile.level >= achievement.target_value
        
        elif achievement.achievement_type == 'clarity_improvement':
            return session.clarity_score >= achievement.target_value
        
        elif achievement.achievement_type == 'fluency_improvement':
            return session.fluency_score >= achievement.target_value
        
        elif achievement.achievement_type == 'consistency':
            # Check if user has consistent scores over time
            recent_sessions = SpeechSession.objects.filter(
                user=user,
                created_at__gte=timezone.now() - timedelta(days=7)
            ).count()
            return recent_sessions >= achievement.target_value
        
        return False


class UserAchievementsView(generics.ListAPIView):
    """List user's earned achievements"""
    serializer_class = UserAchievementSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return UserAchievement.objects.filter(user=self.request.user).order_by('-earned_at')


class AvailableExercisesView(generics.ListAPIView):
    """List available exercises for user's level"""
    serializer_class = SpeechExerciseSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        profile = get_object_or_404(UserProfile, user=self.request.user)
        return SpeechExercise.objects.filter(
            level_required__lte=profile.level,
            is_active=True
        ).order_by('difficulty', 'level_required')


class ExerciseAttemptCreateView(generics.CreateAPIView):
    """Create a new exercise attempt"""
    serializer_class = ExerciseAttemptSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class ProgressSummaryView(APIView):
    """Get comprehensive progress summary"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        
        # Get or create profile
        profile, created = UserProfile.objects.get_or_create(user=user)
        # Ensure total_speaking_time is a timedelta (not a raw string from old defaults)
        if isinstance(profile.total_speaking_time, str):
            parsed_duration = parse_duration(profile.total_speaking_time)
            profile.total_speaking_time = parsed_duration if parsed_duration is not None else timedelta()
            # Persist the corrected value so future reads are safe
            try:
                profile.save(update_fields=["total_speaking_time"])
            except Exception:
                pass
        character, _ = CharacterCustomization.objects.get_or_create(user=user)
        
        # Get recent sessions (last 10)
        recent_sessions = SpeechSession.objects.filter(user=user).order_by('-created_at')[:10]
        
        # Get achievements
        achievements = UserAchievement.objects.filter(user=user).order_by('-earned_at')
        
        # Get available exercises
        available_exercises = SpeechExercise.objects.filter(
            level_required__lte=profile.level,
            is_active=True
        )[:5]
        
        # Get unlocked customizations
        unlocked_customizations = UnlockedCustomization.objects.filter(user=user)
        
        data = {
            'profile': UserProfileSerializer(profile).data,
            'character': CharacterCustomizationSerializer(character).data,
            'recent_sessions': SpeechSessionSerializer(recent_sessions, many=True).data,
            'achievements': UserAchievementSerializer(achievements, many=True).data,
            'available_exercises': SpeechExerciseSerializer(available_exercises, many=True).data,
            'unlocked_customizations': UnlockedCustomizationSerializer(unlocked_customizations, many=True).data,
            'onboarding_completed': profile.has_completed_onboarding,
            'has_active_avatar': profile.has_active_avatar,
        }
        
        # serializer = ProgressSummarySerializer(data)
        return Response(data)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def analyze_speech(request):
    """Analyze speech and provide feedback"""
    # This would integrate with speech analysis logic
    # For now, we'll return mock analysis
    
    text = request.data.get('text', '')
    duration = request.data.get('duration', 0)
    
    # Mock analysis - in real implementation, this would use AI/ML
    word_count = len(text.split()) if text else 0
    clarity_score = min(100, max(0, 70 + (word_count * 2)))  # Mock calculation
    fluency_score = min(100, max(0, 60 + (word_count * 3)))  # Mock calculation
    confidence_score = min(100, max(0, 65 + (word_count * 2.5)))  # Mock calculation
    
    # Generate feedback
    feedback = []
    areas_for_improvement = []
    strengths = []
    
    if clarity_score < 70:
        areas_for_improvement.append("Try to speak more clearly")
        feedback.append("Focus on pronouncing each word clearly. Take your time!")
    else:
        strengths.append("Great clarity in your speech!")
    
    if fluency_score < 70:
        areas_for_improvement.append("Work on speaking more smoothly")
        feedback.append("Try to speak without too many pauses. Keep practicing!")
    else:
        strengths.append("Excellent fluency!")
    
    if confidence_score < 70:
        areas_for_improvement.append("Build confidence by practicing more")
        feedback.append("You're doing great! Keep practicing to build confidence.")
    else:
        strengths.append("Very confident delivery!")
    
    # Calculate experience gained
    base_xp = 10
    bonus_xp = int((clarity_score + fluency_score + confidence_score) / 30)
    experience_gained = base_xp + bonus_xp
    
    return Response({
        'clarity_score': clarity_score,
        'fluency_score': fluency_score,
        'confidence_score': confidence_score,
        'overall_score': (clarity_score + fluency_score + confidence_score) / 3,
        'experience_gained': experience_gained,
        'feedback_text': ' '.join(feedback),
        'areas_for_improvement': areas_for_improvement,
        'strengths': strengths,
        'word_count': word_count
    }) 


class OnboardingProfileView(generics.RetrieveUpdateAPIView):
    """Create or update onboarding profile and mark onboarding complete"""
    serializer_class = OnboardingProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        profile, _ = OnboardingProfile.objects.get_or_create(user=self.request.user)
        return profile

    def perform_update(self, serializer):
        onboarding = serializer.save(user=self.request.user)
        # Mark user profile as onboarded and initialize character if not
        therapy_profile, _ = UserProfile.objects.get_or_create(user=self.request.user)
        if not therapy_profile.has_completed_onboarding:
            therapy_profile.has_completed_onboarding = True
            therapy_profile.save()

        character, _ = CharacterCustomization.objects.get_or_create(user=self.request.user)
        if not character.is_initialized:
            # keep values from request if provided via CharacterCustomizationView later
            character.is_initialized = True
            character.save()

        return onboarding


class InitializeAvatarView(APIView):
    """Initialize character customization with limited starter options"""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        body_color = request.data.get('body_color', 'brown')
        eye_color = request.data.get('eye_color', 'brown')
        accessory = request.data.get('accessory', 'none')

        # Restrict to limited starter options
        allowed_body = {'brown', 'golden', 'white'}
        allowed_eye = {'brown', 'blue', 'green'}
        allowed_acc = {'none', 'collar', 'hat'}

        if body_color not in allowed_body or eye_color not in allowed_eye or accessory not in allowed_acc:
            return Response({'detail': 'Invalid starter customization'}, status=status.HTTP_400_BAD_REQUEST)

        character, _ = CharacterCustomization.objects.get_or_create(user=request.user)
        character.body_color = body_color
        character.eye_color = eye_color
        character.accessory = accessory
        character.is_initialized = True
        character.save()

        return Response(CharacterCustomizationSerializer(character).data, status=status.HTTP_200_OK)


class UserAvatarView(generics.RetrieveUpdateAPIView):
    """Save and retrieve user's Fluttermoji avatar data"""
    serializer_class = UserAvatarSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        avatar, _ = UserAvatar.objects.get_or_create(user=self.request.user, defaults={
            'data': ''
        })
        return avatar

    def perform_update(self, serializer):
        avatar = serializer.save(user=self.request.user, provider='fluttermoji', is_active=True)
        # Mark profile as having active avatar
        profile, _ = UserProfile.objects.get_or_create(user=self.request.user)
        if not profile.has_active_avatar:
            profile.has_active_avatar = True
            profile.save()
        return avatar


# New views for Eleven Labs integration with dynamic variables and memory

class ConversationContextView(APIView):
    """Get user context data for Eleven Labs dynamic variables"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        
        # Get user profile and onboarding data
        profile, _ = UserProfile.objects.get_or_create(user=user)
        try:
            onboarding = OnboardingProfile.objects.get(user=user)
        except OnboardingProfile.DoesNotExist:
            onboarding = None

        # Get recent achievements (last 3)
        recent_achievements = UserAchievement.objects.filter(
            user=user
        ).select_related('achievement').order_by('-earned_at')[:3]

        # Get recent conversation sessions for context
        recent_sessions = ConversationSession.objects.filter(
            user=user
        ).order_by('-created_at')[:5]

        # Get user memories for personalization
        user_memories = UserMemory.get_user_context(user, limit=8)

        # Calculate difficulty level based on user level
        if profile.level <= 3:
            difficulty_level = "beginner"
        elif profile.level <= 8:
            difficulty_level = "intermediate"  
        else:
            difficulty_level = "advanced"

        # Get suggested exercises based on level
        suggested_exercises = SpeechExercise.objects.filter(
            level_required__lte=profile.level,
            is_active=True
        ).values_list('title', flat=True)[:4]

        # Get last session performance
        last_session_score = 0.0
        if recent_sessions:
            last_session_score = recent_sessions[0].session_rating

        # Prepare context data
        context_data = {
            'user_name': user.first_name or user.username,
            'user_age': onboarding.age_range if onboarding else 'unknown',
            'user_level': profile.level,
            'experience_points': profile.experience_points,
            'improvement_score': profile.improvement_score,
            'interests': onboarding.interests if onboarding else [],
            'goals': onboarding.goals if onboarding else [],
            'recent_achievements': [ach.achievement.name for ach in recent_achievements],
            'difficulty_level': difficulty_level,
            'session_count': ConversationSession.objects.filter(user=user).count(),
            'last_session_score': last_session_score,
            'suggested_exercises': list(suggested_exercises),
        }

        # Add memory context
        memory_context = {}
        for memory in user_memories:
            memory_context[memory.key] = memory.value

        context_data['memory_context'] = memory_context

        serializer = ConversationContextSerializer(context_data)
        return Response(serializer.data)


class ConversationSessionCreateView(APIView):
    """Create or update a conversation session"""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        conversation_id = request.data.get('conversation_id')
        if not conversation_id:
            return Response({'error': 'conversation_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        user = request.user
        
        # Create or get conversation session
        session, created = ConversationSession.objects.get_or_create(
            elevenlabs_conversation_id=conversation_id,
            defaults={
                'user': user,
                'difficulty_level': self._get_user_difficulty_level(user)
            }
        )

        if created:
            return Response({
                'id': str(session.id),
                'conversation_id': session.elevenlabs_conversation_id,
                'created': True
            })
        else:
            return Response({
                'id': str(session.id),
                'conversation_id': session.elevenlabs_conversation_id,
                'created': False
            })

    def _get_user_difficulty_level(self, user):
        """Determine user's current difficulty level"""
        try:
            profile = UserProfile.objects.get(user=user)
            if profile.level <= 3:
                return 'beginner'
            elif profile.level <= 8:
                return 'intermediate'
            else:
                return 'advanced'
        except UserProfile.DoesNotExist:
            return 'beginner'


class ConversationFeedbackView(APIView):
    """Receive feedback from conversation and update user progress"""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ConversationFeedbackSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        user = request.user
        conversation_id = data['conversation_id']

        try:
            session = ConversationSession.objects.get(
                elevenlabs_conversation_id=conversation_id,
                user=user
            )
        except ConversationSession.DoesNotExist:
            return Response({'error': 'Conversation session not found'}, status=status.HTTP_404_NOT_FOUND)

        # Update session with feedback data
        session.duration = timedelta(seconds=data['duration_seconds'])
        session.user_messages_count = data['user_messages_count']
        session.topics_covered = data['topics_covered']
        session.engagement_level = data['engagement_level']
        session.speech_clarity_notes = data.get('speech_clarity_feedback', '')
        session.improvements_noted = data['speech_improvements_noted']
        session.areas_to_work_on = data['areas_to_work_on']

        # Calculate experience earned based on engagement and duration
        base_xp = 15  # Base XP for completing a conversation
        duration_bonus = min(data['duration_seconds'] // 60 * 2, 30)  # 2 XP per minute, max 30
        engagement_multiplier = {'low': 1.0, 'medium': 1.2, 'high': 1.5}[data['engagement_level']]
        
        session.experience_earned = int((base_xp + duration_bonus) * engagement_multiplier)
        session.session_rating = self._calculate_session_rating(data)
        session.save()

        # Update user profile
        self._update_user_progress(user, session)

        # Store important memories from this session
        self._update_user_memories(user, data)

        return Response({
            'success': True,
            'experience_earned': session.experience_earned,
            'session_rating': session.session_rating,
            'level_up': self._check_level_up(user)
        })

    def _calculate_session_rating(self, data):
        """Calculate session rating based on feedback data"""
        base_rating = 3.0
        
        # Adjust based on engagement
        engagement_bonus = {'low': -0.5, 'medium': 0.0, 'high': 0.8}[data['engagement_level']]
        
        # Adjust based on duration (longer conversations are generally better)
        duration_minutes = data['duration_seconds'] // 60
        duration_bonus = min(duration_minutes * 0.1, 1.0)
        
        # Adjust based on improvements noted
        improvement_bonus = len(data['speech_improvements_noted']) * 0.2
        
        rating = base_rating + engagement_bonus + duration_bonus + improvement_bonus
        return min(max(rating, 1.0), 5.0)  # Clamp between 1.0 and 5.0

    def _update_user_progress(self, user, session):
        """Update user profile based on conversation session"""
        profile, _ = UserProfile.objects.get_or_create(user=user)
        
        # Add experience points
        old_level = profile.level
        profile.experience_points += session.experience_earned
        
        # Update total speaking time
        if profile.total_speaking_time:
            profile.total_speaking_time += session.duration
        else:
            profile.total_speaking_time = session.duration

        # Update improvement score based on recent sessions
        recent_sessions = ConversationSession.objects.filter(
            user=user,
            created_at__gte=timezone.now() - timedelta(days=7)
        )
        avg_rating = recent_sessions.aggregate(avg_rating=Avg('session_rating'))['avg_rating']
        if avg_rating:
            # Convert 1-5 rating to 0-100 score
            profile.improvement_score = (avg_rating - 1) * 25

        # Level up check
        required_xp = profile.level * 100
        while profile.experience_points >= required_xp:
            profile.level += 1
            required_xp = profile.level * 100
            
        profile.save()

        # If leveled up, unlock rewards
        if profile.level > old_level:
            self._unlock_level_rewards(profile)

    def _unlock_level_rewards(self, profile):
        """Unlock rewards when user levels up"""
        # Auto-unlock customizations based on level
        customizations_to_unlock = []
        
        level_rewards = {
            2: [('body_color', 'black'), ('eye_color', 'blue')],
            3: [('eye_color', 'green'), ('accessory', 'collar')],
            4: [('accessory', 'hat')],
            5: [('body_color', 'spotted')],
            6: [('accessory', 'bow_tie')],
            8: [('accessory', 'glasses')],
            10: [('body_color', 'blue')],
            12: [('eye_color', 'purple'), ('accessory', 'cape')],
            15: [('body_color', 'purple')],
            16: [('accessory', 'crown')],
            18: [('eye_color', 'rainbow')],
            20: [('body_color', 'rainbow'), ('accessory', 'wings')],
        }
        
        if profile.level in level_rewards:
            for customization_type, value in level_rewards[profile.level]:
                UnlockedCustomization.objects.get_or_create(
                    user=profile.user,
                    customization_type=customization_type,
                    customization_value=value,
                    defaults={'level_required': profile.level}
                )

    def _update_user_memories(self, user, data):
        """Update user memories based on conversation data"""
        # Store topics covered as interests if they showed high engagement
        if data['engagement_level'] == 'high' and data['topics_covered']:
            for topic in data['topics_covered']:
                memory, created = UserMemory.objects.get_or_create(
                    user=user,
                    key=f"enjoys_topic_{topic.lower().replace(' ', '_')}",
                    defaults={
                        'memory_type': 'interest',
                        'value': f"Shows high engagement when discussing {topic}",
                        'importance_score': 7.0
                    }
                )
                if not created:
                    memory.importance_score = min(memory.importance_score + 0.5, 10.0)
                    memory.save()

        # Store areas to work on as challenges
        for area in data['areas_to_work_on']:
            memory, created = UserMemory.objects.get_or_create(
                user=user,
                key=f"challenge_{area.lower().replace(' ', '_')}",
                defaults={
                    'memory_type': 'challenge',
                    'value': f"Needs to work on: {area}",
                    'importance_score': 8.0
                }
            )

        # Store recent improvements as achievements
        for improvement in data['speech_improvements_noted']:
            memory, created = UserMemory.objects.get_or_create(
                user=user,
                key=f"improvement_{improvement.lower().replace(' ', '_')}",
                defaults={
                    'memory_type': 'achievement',
                    'value': f"Recent improvement: {improvement}",
                    'importance_score': 6.0
                }
            )

    def _check_level_up(self, user):
        """Check if user leveled up in this session"""
        profile = UserProfile.objects.get(user=user)
        previous_sessions = ConversationSession.objects.filter(
            user=user
        ).order_by('-created_at')[1:2]  # Get second most recent session
        
        if previous_sessions:
            prev_session = previous_sessions[0]
            # Check if we have user profile data from before this session
            # For simplicity, we'll just return False for now
            # In a real implementation, you'd track this more precisely
            return False
        
        return profile.level > 1  # If this is their first session and they're above level 1


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_user_dynamic_variables(request):
    """Get simplified dynamic variables for Eleven Labs agent initialization"""
    user = request.user
    
    try:
        profile = UserProfile.objects.get(user=user)
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=user)
    
    try:
        onboarding = OnboardingProfile.objects.get(user=user)
    except OnboardingProfile.DoesNotExist:
        onboarding = None

    # Get recent achievements for motivation
    recent_achievements = UserAchievement.objects.filter(
        user=user
    ).select_related('achievement').order_by('-earned_at')[:2]

    # Get user memories for personalization
    memories = UserMemory.objects.filter(
        user=user,
        is_active=True
    ).order_by('-importance_score')[:5]

    # Prepare simplified variables for agent
    variables = {
        'user_name': user.first_name or 'friend',
        'user_age_range': onboarding.age_range if onboarding else '7-9',
        'user_level': str(profile.level),
        'user_xp': str(profile.experience_points),
        'user_id': str(user.id),
        'recent_achievement': recent_achievements[0].achievement.name if recent_achievements else 'Getting Started',
        'user_interests': ', '.join(onboarding.interests[:3]) if onboarding and onboarding.interests else 'learning',
        'difficulty_preference': 'beginner' if profile.level <= 3 else 'intermediate' if profile.level <= 8 else 'advanced',
        'last_conversation_rating': '4.0',  # This would be calculated from recent sessions
        'user_goal': ', '.join(onboarding.goals[:2]) if onboarding and onboarding.goals else 'improving speech',
    }

    # Add memory context
    for memory in memories:
        if 'enjoys_topic' in memory.key:
            variables['favorite_topic'] = memory.value.split('discussing ')[-1] if 'discussing ' in memory.value else 'animals'
        elif 'challenge' in memory.key:
            variables['current_challenge'] = memory.value.replace('Needs to work on: ', '') if 'Needs to work on:' in memory.value else 'pronunciation'

    # Set defaults if not found in memories
    if 'favorite_topic' not in variables:
        variables['favorite_topic'] = onboarding.interests[0] if onboarding and onboarding.interests else 'animals'
    if 'current_challenge' not in variables:
        variables['current_challenge'] = 'pronunciation practice'

    return Response(variables)


# ElevenLabs Webhook Endpoints
@api_view(['POST'])
@permission_classes([])  # No authentication required for webhooks
def elevenlabs_award_xp_webhook(request):
    """Webhook endpoint for ElevenLabs to award XP based on speech performance"""
    start_time = time.time()
    webhook_log = None
    
    try:
        data = request.data
        logger.info(f"Received ElevenLabs award_xp webhook: {data}")
        
        # Log the webhook call
        webhook_log = WebhookLogger.log_webhook_call('award_xp', data, request, start_time)
        
        # Extract data from ElevenLabs webhook
        user_id = data.get('user_id')
        phoneme = data.get('phoneme')  # Target sound (r, s, l)
        difficulty = data.get('difficulty', 'easy')  # easy, medium, hard
        score = data.get('score', 0)  # 0-100 accuracy score
        session_id = data.get('session_id')
        
        if not user_id:
            error_msg = 'user_id is required'
            if webhook_log:
                WebhookLogger.update_webhook_log(webhook_log, 'error', error_message=error_msg)
            return Response({'error': error_msg}, status=status.HTTP_400_BAD_REQUEST)
        
        # Get user profile
        try:
            user = User.objects.get(id=user_id)
            profile = UserProfile.objects.get(user=user)
        except (User.DoesNotExist, UserProfile.DoesNotExist):
            error_msg = f'User not found with ID: {user_id}'
            if webhook_log:
                WebhookLogger.update_webhook_log(webhook_log, 'error', error_message=error_msg)
            return Response({'error': error_msg}, status=status.HTTP_404_NOT_FOUND)
        
        # Calculate XP based on performance
        base_xp = _calculate_base_xp(difficulty, score)
        bonus_xp = _calculate_bonus_xp(phoneme, score)
        total_xp = base_xp + bonus_xp
        
        # Update user profile
        old_level = profile.level
        profile.experience_points += total_xp
        
        # Check for level up
        new_level = _calculate_level_from_xp(profile.experience_points)
        level_up = new_level > old_level
        
        if level_up:
            profile.level = new_level
            # Unlock new customizations based on level
            _unlock_customizations_for_level(user, new_level)
        
        profile.save()
        
        # Create speech session record
        if session_id:
            SpeechSession.objects.create(
                user=user,
                session_id=session_id,
                duration=timedelta(seconds=30),  # Default duration
                words_spoken=1,  # Single word attempt
                clarity_score=score,
                fluency_score=score,
                confidence_score=score,
                experience_gained=total_xp
            )
        
        # Prepare response for ElevenLabs dynamic variables
        response_data = {
            'user_xp': profile.experience_points,
            'user_level': profile.level,
            'xp_earned': total_xp,
            'level_up': level_up,
            'old_level': old_level,
            'new_level': new_level,
            'message': f"Great job! You earned {total_xp} XP for practicing the '{phoneme}' sound!"
        }
        
        # Send real-time update via WebSocket
        _send_xp_update_to_websocket(user_id, response_data)
        
        # Update webhook log with success
        if webhook_log:
            WebhookLogger.update_webhook_log(webhook_log, 'success', response_data)
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        error_msg = f"Error in award_xp webhook: {e}"
        logger.error(error_msg)
        if webhook_log:
            WebhookLogger.update_webhook_log(webhook_log, 'error', error_message=error_msg)
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([])
def elevenlabs_conversation_end_webhook(request):
    """Webhook endpoint for ElevenLabs conversation end analysis"""
    start_time = time.time()
    webhook_log = None
    
    try:
        data = request.data
        logger.info(f"Received ElevenLabs conversation end webhook: {data}")
        
        # Log the webhook call
        webhook_log = WebhookLogger.log_webhook_call('conversation_end', data, request, start_time)
        
        # Extract conversation data
        user_id = data.get('user_id')
        session_id = data.get('session_id')
        transcript = data.get('transcript', '')
        analysis_results = data.get('analysis', {})
        dynamic_variables = data.get('dynamic_variables', {})
        
        if not user_id:
            error_msg = 'user_id is required'
            if webhook_log:
                WebhookLogger.update_webhook_log(webhook_log, 'error', error_message=error_msg)
            return Response({'error': error_msg}, status=status.HTTP_400_BAD_REQUEST)
        
        # Get user profile
        try:
            user = User.objects.get(id=user_id)
            profile = UserProfile.objects.get(user=user)
        except (User.DoesNotExist, UserProfile.DoesNotExist):
            error_msg = f'User not found with ID: {user_id}'
            if webhook_log:
                WebhookLogger.update_webhook_log(webhook_log, 'error', error_message=error_msg)
            return Response({'error': error_msg}, status=status.HTTP_404_NOT_FOUND)
        
        # Calculate XP based on analysis results
        total_xp = _calculate_conversation_xp(analysis_results, dynamic_variables)
        
        # Update user profile
        old_level = profile.level
        profile.experience_points += total_xp
        new_level = _calculate_level_from_xp(profile.experience_points)
        level_up = new_level > old_level
        
        if level_up:
            profile.level = new_level
            _unlock_customizations_for_level(user, new_level)
        
        profile.save()
        
        # Create conversation session record
        if session_id:
            ConversationSession.objects.create(
                user=user,
                session_id=session_id,
                transcript=transcript,
                analysis_results=analysis_results,
                experience_gained=total_xp,
                duration=timedelta(minutes=5)  # Default duration
            )
        
        response_data = {
            'user_xp': profile.experience_points,
            'user_level': profile.level,
            'xp_earned': total_xp,
            'level_up': level_up,
            'conversation_summary': _generate_conversation_summary(analysis_results)
        }
        
        # Send real-time update via WebSocket
        _send_xp_update_to_websocket(user_id, response_data)
        
        # Update webhook log with success
        if webhook_log:
            WebhookLogger.update_webhook_log(webhook_log, 'success', response_data)
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        error_msg = f"Error in conversation end webhook: {e}"
        logger.error(error_msg)
        if webhook_log:
            WebhookLogger.update_webhook_log(webhook_log, 'error', error_message=error_msg)
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Helper functions for XP calculation
def _calculate_base_xp(difficulty, score):
    """Calculate base XP based on difficulty and score"""
    difficulty_multipliers = {
        'easy': 5,
        'medium': 10,
        'hard': 15
    }
    
    base_xp = difficulty_multipliers.get(difficulty, 5)
    score_multiplier = score / 100.0
    return int(base_xp * score_multiplier)


def _calculate_bonus_xp(phoneme, score):
    """Calculate bonus XP for specific phonemes"""
    if score >= 80:
        return 10  # Bonus for high accuracy
    elif score >= 60:
        return 5   # Small bonus for moderate accuracy
    return 0


def _calculate_conversation_xp(analysis_results, dynamic_variables):
    """Calculate XP for entire conversation"""
    base_xp = 20  # Base XP for completing conversation
    
    # Add XP based on analysis results
    if analysis_results:
        accuracy = analysis_results.get('overall_accuracy', 0)
        words_spoken = analysis_results.get('words_spoken', 0)
        duration = analysis_results.get('duration_minutes', 1)
        
        # XP based on accuracy
        accuracy_xp = int(accuracy * 0.5)
        
        # XP based on engagement (words spoken)
        engagement_xp = min(words_spoken * 2, 50)
        
        # XP based on duration
        duration_xp = min(duration * 5, 30)
        
        return base_xp + accuracy_xp + engagement_xp + duration_xp
    
    return base_xp


def _calculate_level_from_xp(xp):
    """Calculate level based on total XP"""
    if xp < 100:
        return 1
    elif xp < 250:
        return 2
    elif xp < 450:
        return 3
    elif xp < 700:
        return 4
    elif xp < 1000:
        return 5
    else:
        # For higher levels, use a more complex formula
        level = 5
        remaining_xp = xp - 1000
        while remaining_xp >= (level * 150):
            remaining_xp -= (level * 150)
            level += 1
        return level


def _unlock_customizations_for_level(user, level):
    """Unlock new customizations based on level"""
    # Define level requirements for customizations
    level_requirements = {
        'body_color': {
            'brown': 1, 'golden': 1, 'black': 2, 'white': 3,
            'spotted': 5, 'blue': 10, 'purple': 15, 'rainbow': 20
        },
        'eye_color': {
            'brown': 1, 'blue': 2, 'green': 3, 'amber': 4,
            'purple': 12, 'rainbow': 18
        },
        'accessory': {
            'none': 1, 'collar': 2, 'hat': 4, 'bow_tie': 6,
            'glasses': 8, 'cape': 12, 'crown': 16, 'wings': 20
        }
    }
    
    for customization_type, requirements in level_requirements.items():
        for value, required_level in requirements.items():
            if level >= required_level:
                UnlockedCustomization.objects.get_or_create(
                    user=user,
                    customization_type=customization_type,
                    customization_value=value,
                    level_required=required_level
                )


def _generate_conversation_summary(analysis_results):
    """Generate a summary of the conversation for the agent"""
    if not analysis_results:
        return "Great conversation! Keep practicing to improve your speech skills."
    
    summary_parts = []
    
    if 'overall_accuracy' in analysis_results:
        accuracy = analysis_results['overall_accuracy']
        if accuracy >= 0.8:
            summary_parts.append("Excellent pronunciation accuracy!")
        elif accuracy >= 0.6:
            summary_parts.append("Good pronunciation, keep practicing!")
        else:
            summary_parts.append("Keep working on your pronunciation!")
    
    if 'words_spoken' in analysis_results:
        words = analysis_results['words_spoken']
        if words >= 20:
            summary_parts.append("Great engagement with lots of words spoken!")
        elif words >= 10:
            summary_parts.append("Good participation in the conversation!")
    
    return " ".join(summary_parts) if summary_parts else "Great conversation! Keep practicing!"


def _send_xp_update_to_websocket(user_id, data):
    """Send XP update to connected WebSocket clients"""
    try:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"user_{user_id}",
            {
                'type': 'xp_update',
                'data': data
            }
        )
    except Exception as e:
        logger.error(f"Error sending XP update to WebSocket: {e}")


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def webhook_status(request):
    """Get webhook status and statistics for monitoring"""
    try:
        stats = WebhookLogger.get_webhook_stats()
        summary = WebhookLogger.get_webhook_summary()
        recent_errors = WebhookLogger.get_recent_errors(5)
        
        # Format recent errors for display
        error_list = []
        for error in recent_errors:
            error_list.append({
                'id': error.id,
                'webhook_type': error.webhook_type,
                'user_id': error.user_id_from_request,
                'error_message': error.error_message,
                'created_at': error.created_at.isoformat(),
                'request_data': error.request_data
            })
        
        response_data = {
            'stats': stats,
            'summary': summary,
            'recent_errors': error_list,
            'status': 'healthy' if stats['error_calls'] == 0 else 'has_errors'
        }
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error getting webhook status: {e}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



