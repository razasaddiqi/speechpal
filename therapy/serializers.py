from rest_framework import serializers
from django.contrib.auth.models import User

from .models import (
    UserProfile, CharacterCustomization, UnlockedCustomization, SpeechSession, 
    Achievement, UserAchievement, SpeechExercise, ExerciseAttempt,
    OnboardingProfile, UserAvatar
)


class UserProfileSerializer(serializers.ModelSerializer):
    xp_to_next_level = serializers.ReadOnlyField()
    
    class Meta:
        model = UserProfile
        fields = ['level', 'experience_points', 'total_speaking_time', 'improvement_score', 
                 'has_completed_onboarding', 'has_active_avatar', 'xp_to_next_level']
        read_only_fields = ['level', 'experience_points', 'total_speaking_time', 'improvement_score']


class CharacterCustomizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = CharacterCustomization
        fields = ['body_color', 'eye_color', 'accessory', 'is_initialized']


class UnlockedCustomizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = UnlockedCustomization
        fields = ['customization_type', 'customization_value', 'level_required', 'unlocked_at']


class SpeechSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = SpeechSession
        fields = ['id', 'session_id', 'duration', 'words_spoken', 'clarity_score', 
                 'fluency_score', 'confidence_score', 'overall_score', 'experience_gained', 
                 'created_at']
        read_only_fields = ['id', 'overall_score', 'created_at']


class AchievementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Achievement
        fields = ['id', 'name', 'description', 'achievement_type', 'target_value', 
                 'icon', 'experience_reward', 'customization_reward']


class UserAchievementSerializer(serializers.ModelSerializer):
    achievement = AchievementSerializer(read_only=True)
    
    class Meta:
        model = UserAchievement
        fields = ['achievement', 'earned_at']


class SpeechExerciseSerializer(serializers.ModelSerializer):
    class Meta:
        model = SpeechExercise
        fields = ['id', 'title', 'description', 'exercise_type', 'difficulty', 
                 'level_required', 'prompt_text', 'target_words', 'expected_duration', 
                 'experience_reward']


class ExerciseAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExerciseAttempt
        fields = ['id', 'exercise', 'speech_session', 'completed', 'feedback_text', 
                 'areas_for_improvement', 'strengths', 'created_at']
        read_only_fields = ['id', 'created_at']


class CharacterCustomizationOptionsSerializer(serializers.Serializer):
    body_colors = serializers.ListField(child=serializers.DictField())
    eye_colors = serializers.ListField(child=serializers.DictField())
    accessories = serializers.ListField(child=serializers.DictField())


class ProgressSummarySerializer(serializers.Serializer):
    profile = UserProfileSerializer()
    character = CharacterCustomizationSerializer()
    recent_sessions = SpeechSessionSerializer(many=True)
    achievements = UserAchievementSerializer(many=True)
    available_exercises = SpeechExerciseSerializer(many=True)
    unlocked_customizations = UnlockedCustomizationSerializer(many=True)
    onboarding_completed = serializers.BooleanField()
    has_active_avatar = serializers.BooleanField()


class OnboardingProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = OnboardingProfile
        fields = ['age_range', 'primary_language', 'goals', 'interests', 
                 'daily_goal_minutes', 'voice_preference', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']


class UserAvatarSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserAvatar
        fields = ['provider', 'data', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']


# New serializers for Eleven Labs integration
class ConversationContextSerializer(serializers.Serializer):
    """Serializer for user context data to be passed to Eleven Labs as dynamic variables"""
    user_name = serializers.CharField()
    user_age = serializers.CharField()
    user_level = serializers.IntegerField()
    experience_points = serializers.IntegerField()
    improvement_score = serializers.FloatField()
    interests = serializers.ListField(child=serializers.CharField(), default=list)
    goals = serializers.ListField(child=serializers.CharField(), default=list)
    recent_achievements = serializers.ListField(child=serializers.CharField(), default=list)
    difficulty_level = serializers.CharField()
    session_count = serializers.IntegerField()
    last_session_score = serializers.FloatField(default=0.0)
    suggested_exercises = serializers.ListField(child=serializers.CharField(), default=list)


class ConversationSessionSerializer(serializers.ModelSerializer):
    """Track Eleven Labs conversation sessions"""
    class Meta:
        model = SpeechSession
        fields = ['id', 'session_id', 'duration', 'words_spoken', 'clarity_score',
                 'fluency_score', 'confidence_score', 'overall_score', 'experience_gained']
        read_only_fields = ['id', 'overall_score']


class ConversationFeedbackSerializer(serializers.Serializer):
    """Feedback data from Eleven Labs conversation to update user progress"""
    conversation_id = serializers.CharField()
    duration_seconds = serializers.IntegerField()
    user_messages_count = serializers.IntegerField()
    speech_clarity_feedback = serializers.CharField(required=False, allow_blank=True)
    topics_covered = serializers.ListField(child=serializers.CharField(), default=list)
    engagement_level = serializers.ChoiceField(choices=['low', 'medium', 'high'], default='medium')
    speech_improvements_noted = serializers.ListField(child=serializers.CharField(), default=list)
    areas_to_work_on = serializers.ListField(child=serializers.CharField(), default=list)