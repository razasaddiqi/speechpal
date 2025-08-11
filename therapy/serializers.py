from rest_framework import serializers
from .models import (
    UserProfile, CharacterCustomization, UnlockedCustomization,
    SpeechSession, Achievement, UserAchievement, SpeechExercise, ExerciseAttempt,
    OnboardingProfile, UserAvatar,
)


class UserProfileSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source='user.username', read_only=True)
    xp_to_next_level = serializers.ReadOnlyField()
    
    class Meta:
        model = UserProfile
        fields = [
            'user', 'user_username', 'level', 'experience_points', 
            'xp_to_next_level', 'total_speaking_time', 'improvement_score',
            'has_completed_onboarding', 'has_active_avatar', 'created_at', 'updated_at'
        ]
        read_only_fields = ['user', 'created_at', 'updated_at']


class CharacterCustomizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = CharacterCustomization
        fields = [
            'user', 'body_color', 'eye_color', 'accessory', 'is_initialized',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['user', 'created_at', 'updated_at']


class UnlockedCustomizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = UnlockedCustomization
        fields = [
            'user', 'customization_type', 'customization_value',
            'level_required', 'unlocked_at'
        ]
        read_only_fields = ['user', 'unlocked_at']


class SpeechSessionSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = SpeechSession
        fields = [
            'id', 'user', 'user_username', 'duration', 'words_spoken',
            'clarity_score', 'fluency_score', 'confidence_score', 'overall_score',
            'experience_gained', 'created_at'
        ]
        read_only_fields = ['id', 'user', 'overall_score', 'created_at']


class AchievementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Achievement
        fields = [
            'id', 'name', 'description', 'achievement_type', 'target_value',
            'icon', 'experience_reward', 'customization_reward', 'created_at'
        ]


class UserAchievementSerializer(serializers.ModelSerializer):
    achievement_name = serializers.CharField(source='achievement.name', read_only=True)
    achievement_icon = serializers.CharField(source='achievement.icon', read_only=True)
    achievement_description = serializers.CharField(source='achievement.description', read_only=True)
    
    class Meta:
        model = UserAchievement
        fields = [
            'achievement', 'achievement_name', 'achievement_icon', 
            'achievement_description', 'earned_at'
        ]
        read_only_fields = ['earned_at']


class SpeechExerciseSerializer(serializers.ModelSerializer):
    class Meta:
        model = SpeechExercise
        fields = [
            'id', 'title', 'description', 'exercise_type', 'difficulty',
            'level_required', 'prompt_text', 'target_words', 'expected_duration',
            'experience_reward', 'is_active', 'created_at'
        ]


class ExerciseAttemptSerializer(serializers.ModelSerializer):
    exercise_title = serializers.CharField(source='exercise.title', read_only=True)
    user_username = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = ExerciseAttempt
        fields = [
            'id', 'user', 'user_username', 'exercise', 'exercise_title',
            'speech_session', 'completed', 'feedback_text',
            'areas_for_improvement', 'strengths', 'created_at'
        ]
        read_only_fields = ['id', 'user', 'created_at']


class CharacterCustomizationOptionsSerializer(serializers.Serializer):
    """Serializer to show available customization options with unlock status"""
    body_colors = serializers.ListField(child=serializers.DictField())
    eye_colors = serializers.ListField(child=serializers.DictField())
    accessories = serializers.ListField(child=serializers.DictField())


class ProgressSummarySerializer(serializers.Serializer):
    """Serializer for user progress summary"""
    profile = UserProfileSerializer()
    character = CharacterCustomizationSerializer()
    recent_sessions = SpeechSessionSerializer(many=True)
    achievements = UserAchievementSerializer(many=True)
    available_exercises = SpeechExerciseSerializer(many=True)
    unlocked_customizations = UnlockedCustomizationSerializer(many=True) 


class OnboardingProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = OnboardingProfile
        fields = [
            'user', 'age_range', 'primary_language', 'goals', 'interests',
            'daily_goal_minutes', 'voice_preference', 'created_at', 'updated_at'
        ]
        read_only_fields = ['user', 'created_at', 'updated_at']


class UserAvatarSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserAvatar
        fields = ['user', 'provider', 'data', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['user', 'provider', 'created_at', 'updated_at']
