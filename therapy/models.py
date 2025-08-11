from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from datetime import timedelta
import uuid
import json


class UserProfile(models.Model):
    """Extended user profile for speech therapy tracking"""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="therapy_profile")
    level = models.IntegerField(default=1, validators=[MinValueValidator(1)])
    experience_points = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    total_speaking_time = models.DurationField(default=timedelta())
    improvement_score = models.FloatField(default=0.0, validators=[MinValueValidator(0.0), MaxValueValidator(100.0)])
    has_completed_onboarding = models.BooleanField(default=False)
    has_active_avatar = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - Level {self.level}"

    @property
    def xp_to_next_level(self):
        """Calculate XP needed for next level"""
        return (self.level * 100) - (self.experience_points % (self.level * 100))


class CharacterCustomization(models.Model):
    """Store user's character customization choices"""
    
    BODY_COLOR_CHOICES = [
        ('brown', 'Brown'),
        ('golden', 'Golden'),
        ('black', 'Black'),
        ('white', 'White'),
        ('spotted', 'Spotted'),
        ('blue', 'Blue Magic'),
        ('purple', 'Purple Magic'),
        ('rainbow', 'Rainbow Magic'),
    ]
    
    EYE_COLOR_CHOICES = [
        ('brown', 'Brown'),
        ('blue', 'Blue'),
        ('green', 'Green'),
        ('amber', 'Amber'),
        ('purple', 'Purple Magic'),
        ('rainbow', 'Rainbow Magic'),
    ]
    
    ACCESSORY_CHOICES = [
        ('none', 'None'),
        ('hat', 'Hat'),
        ('bow_tie', 'Bow Tie'),
        ('collar', 'Collar'),
        ('glasses', 'Glasses'),
        ('cape', 'Super Cape'),
        ('crown', 'Royal Crown'),
        ('wings', 'Magic Wings'),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="character_customization")
    body_color = models.CharField(max_length=20, choices=BODY_COLOR_CHOICES, default='brown')
    eye_color = models.CharField(max_length=20, choices=EYE_COLOR_CHOICES, default='brown')
    accessory = models.CharField(max_length=20, choices=ACCESSORY_CHOICES, default='none')
    is_initialized = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s Character"


class UnlockedCustomization(models.Model):
    """Track which customizations a user has unlocked"""
    
    CUSTOMIZATION_TYPE_CHOICES = [
        ('body_color', 'Body Color'),
        ('eye_color', 'Eye Color'),
        ('accessory', 'Accessory'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="unlocked_customizations")
    customization_type = models.CharField(max_length=20, choices=CUSTOMIZATION_TYPE_CHOICES)
    customization_value = models.CharField(max_length=20)
    level_required = models.IntegerField(validators=[MinValueValidator(1)])
    unlocked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'customization_type', 'customization_value']

    def __str__(self):
        return f"{self.user.username} - {self.customization_type}: {self.customization_value}"


class SpeechSession(models.Model):
    """Track individual speech therapy sessions"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="speech_sessions")
    session_id = models.CharField(max_length=64, null=True, blank=True, db_index=True)  # For deduplication
    duration = models.DurationField()
    words_spoken = models.IntegerField(validators=[MinValueValidator(0)])
    clarity_score = models.FloatField(validators=[MinValueValidator(0.0), MaxValueValidator(100.0)])
    fluency_score = models.FloatField(validators=[MinValueValidator(0.0), MaxValueValidator(100.0)])
    confidence_score = models.FloatField(validators=[MinValueValidator(0.0), MaxValueValidator(100.0)])
    overall_score = models.FloatField(validators=[MinValueValidator(0.0), MaxValueValidator(100.0)])
    experience_gained = models.IntegerField(validators=[MinValueValidator(0)])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'session_id']  # Prevent duplicate sessions
        
    def save(self, *args, **kwargs):
        # Calculate overall score as average of individual scores
        self.overall_score = (self.clarity_score + self.fluency_score + self.confidence_score) / 3
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username} - Session {self.id}"


class Achievement(models.Model):
    """Define available achievements"""
    
    ACHIEVEMENT_TYPE_CHOICES = [
        ('speaking_time', 'Speaking Time'),
        ('words_spoken', 'Words Spoken'),
        ('clarity_improvement', 'Clarity Improvement'),
        ('fluency_improvement', 'Fluency Improvement'),
        ('consistency', 'Consistency'),
        ('level_milestone', 'Level Milestone'),
    ]

    name = models.CharField(max_length=100)
    description = models.TextField()
    achievement_type = models.CharField(max_length=30, choices=ACHIEVEMENT_TYPE_CHOICES)
    target_value = models.FloatField()
    icon = models.CharField(max_length=50, default='🏆')
    experience_reward = models.IntegerField(validators=[MinValueValidator(0)])
    customization_reward = models.JSONField(null=True, blank=True)  # {'type': 'body_color', 'value': 'blue'}
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class UserAchievement(models.Model):
    """Track which achievements users have earned"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="user_achievements")
    achievement = models.ForeignKey(Achievement, on_delete=models.CASCADE)
    earned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'achievement']

    def __str__(self):
        return f"{self.user.username} - {self.achievement.name}"


class SpeechExercise(models.Model):
    """Define speech therapy exercises"""
    
    DIFFICULTY_CHOICES = [
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard'),
    ]
    
    EXERCISE_TYPE_CHOICES = [
        ('pronunciation', 'Pronunciation'),
        ('fluency', 'Fluency'),
        ('vocabulary', 'Vocabulary'),
        ('storytelling', 'Storytelling'),
        ('conversation', 'Conversation'),
    ]

    title = models.CharField(max_length=100)
    description = models.TextField()
    exercise_type = models.CharField(max_length=20, choices=EXERCISE_TYPE_CHOICES)
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES)
    level_required = models.IntegerField(validators=[MinValueValidator(1)])
    prompt_text = models.TextField()
    target_words = models.JSONField(default=list)  # List of words to focus on
    expected_duration = models.DurationField()
    experience_reward = models.IntegerField(validators=[MinValueValidator(0)])
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} - {self.difficulty}"


class OnboardingProfile(models.Model):
    """One-time onboarding responses for tailoring therapy experience"""

    AGE_RANGE_CHOICES = [
        ('3-4', '3-4 years'),
        ('5-6', '5-6 years'),
        ('7-9', '7-9 years'),
        ('10+', '10+ years'),
    ]

    VOICE_PREFERENCE_CHOICES = [
        ('kid', 'Kid voice'),
        ('soft', 'Soft & friendly'),
        ('neutral', 'Neutral'),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="onboarding_profile")
    age_range = models.CharField(max_length=10, choices=AGE_RANGE_CHOICES)
    primary_language = models.CharField(max_length=50, default='English')
    goals = models.JSONField(default=list)          # ["pronunciation", "fluency", ...]
    interests = models.JSONField(default=list)      # ["animals", "superheroes", ...]
    daily_goal_minutes = models.IntegerField(default=10, validators=[MinValueValidator(5), MaxValueValidator(60)])
    voice_preference = models.CharField(max_length=10, choices=VOICE_PREFERENCE_CHOICES, default='kid')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Onboarding for {self.user.username}"

class ExerciseAttempt(models.Model):
    """Track user attempts at exercises"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="exercise_attempts")
    exercise = models.ForeignKey(SpeechExercise, on_delete=models.CASCADE, related_name="attempts")
    speech_session = models.OneToOneField(SpeechSession, on_delete=models.CASCADE, related_name="exercise_attempt")
    completed = models.BooleanField(default=False)
    feedback_text = models.TextField(blank=True)
    areas_for_improvement = models.JSONField(default=list)
    strengths = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.exercise.title}" 


class UserAvatar(models.Model):
    """Stores user's Fluttermoji avatar data and state"""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="avatar")
    provider = models.CharField(max_length=50, default='fluttermoji')
    data = models.TextField()  # encoded attribute string from fluttermoji
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} avatar ({self.provider})"