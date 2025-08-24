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
    
    @property
    def level_progress(self):
        """Calculate progress percentage to next level"""
        current_level_xp = self._calculate_xp_for_level(self.level)
        next_level_xp = self._calculate_xp_for_level(self.level + 1)
        level_range = next_level_xp - current_level_xp
        
        if level_range == 0:
            return 1.0
        
        progress_in_level = self.experience_points - current_level_xp
        return (progress_in_level / level_range).clamp(0.0, 1.0)
    
    def _calculate_xp_for_level(self, level):
        """Calculate XP required for a specific level"""
        if level == 1:
            return 0
        elif level <= 5:
            # Simple formula for levels 1-5
            return (level - 1) * 100
        else:
            # More complex formula for higher levels
            base_xp = 400  # XP for level 5
            additional_levels = level - 5
            return base_xp + (additional_levels * 150) + (additional_levels * (additional_levels - 1) * 25)


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


class ConversationSession(models.Model):
    """Track Eleven Labs conversation sessions with enhanced memory"""
    
    DIFFICULTY_LEVELS = [
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
    ]
    
    ENGAGEMENT_LEVELS = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="conversation_sessions")
    elevenlabs_conversation_id = models.CharField(max_length=255, unique=True)
    duration = models.DurationField(default=timedelta())
    user_messages_count = models.IntegerField(default=0)
    ai_responses_count = models.IntegerField(default=0)
    topics_covered = models.JSONField(default=list)
    difficulty_level = models.CharField(max_length=20, choices=DIFFICULTY_LEVELS, default='beginner')
    engagement_level = models.CharField(max_length=10, choices=ENGAGEMENT_LEVELS, default='medium')
    speech_clarity_notes = models.TextField(blank=True)
    improvements_noted = models.JSONField(default=list)
    areas_to_work_on = models.JSONField(default=list)
    experience_earned = models.IntegerField(default=0)
    session_rating = models.FloatField(default=0.0, validators=[MinValueValidator(0.0), MaxValueValidator(5.0)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - Conversation {self.elevenlabs_conversation_id[:8]}"

    @property
    def session_summary(self):
        """Generate a summary of this session for future reference"""
        return {
            'duration_minutes': int(self.duration.total_seconds() // 60),
            'engagement': self.engagement_level,
            'topics': self.topics_covered,
            'improvements': self.improvements_noted,
            'areas_to_improve': self.areas_to_work_on,
            'rating': self.session_rating,
        }


class UserMemory(models.Model):
    """Store personalized memory about user's progress and preferences"""
    
    MEMORY_TYPES = [
        ('preference', 'User Preference'),
        ('achievement', 'Achievement Milestone'),
        ('challenge', 'Ongoing Challenge'),
        ('interest', 'Personal Interest'),
        ('goal', 'Learning Goal'),
        ('feedback', 'Feedback Response'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memories")
    memory_type = models.CharField(max_length=20, choices=MEMORY_TYPES)
    key = models.CharField(max_length=100)  # e.g., "favorite_topic", "last_achievement"
    value = models.TextField()  # JSON or text value
    importance_score = models.FloatField(default=1.0, validators=[MinValueValidator(0.0), MaxValueValidator(10.0)])
    last_referenced = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ['user', 'key']
        indexes = [
            models.Index(fields=['user', 'memory_type']),
            models.Index(fields=['user', 'importance_score']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.key}: {self.value[:50]}"

    @classmethod
    def get_user_context(cls, user, limit=10):
        """Get most important and recent memories for user context"""
        return cls.objects.filter(
            user=user, 
            is_active=True
        ).order_by('-importance_score', '-last_referenced')[:limit]