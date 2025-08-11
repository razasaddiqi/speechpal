from django.shortcuts import get_object_or_404
from django.db.models import Avg, Count, Q, Sum
from django.utils import timezone
from datetime import timedelta
from django.utils.dateparse import parse_duration
from datetime import timedelta
from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    UserProfile, CharacterCustomization, UnlockedCustomization,
    SpeechSession, Achievement, UserAchievement, SpeechExercise, ExerciseAttempt,
    OnboardingProfile, UserAvatar,
)
from .serializers import (
    UserProfileSerializer, CharacterCustomizationSerializer, UnlockedCustomizationSerializer,
    SpeechSessionSerializer, AchievementSerializer, UserAchievementSerializer,
    SpeechExerciseSerializer, ExerciseAttemptSerializer, CharacterCustomizationOptionsSerializer,
    ProgressSummarySerializer, OnboardingProfileSerializer, UserAvatarSerializer,
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
