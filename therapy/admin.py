from django.contrib import admin
from .models import (
    UserProfile, CharacterCustomization, UnlockedCustomization,
    SpeechSession, Achievement, UserAchievement, SpeechExercise, ExerciseAttempt,
    WebhookLog
)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'level', 'experience_points', 'improvement_score', 'created_at']
    list_filter = ['level', 'created_at']
    search_fields = ['user__username', 'user__email']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(CharacterCustomization)
class CharacterCustomizationAdmin(admin.ModelAdmin):
    list_display = ['user', 'body_color', 'eye_color', 'accessory', 'updated_at']
    list_filter = ['body_color', 'eye_color', 'accessory']
    search_fields = ['user__username']


@admin.register(UnlockedCustomization)
class UnlockedCustomizationAdmin(admin.ModelAdmin):
    list_display = ['user', 'customization_type', 'customization_value', 'level_required', 'unlocked_at']
    list_filter = ['customization_type', 'level_required']
    search_fields = ['user__username']


@admin.register(SpeechSession)
class SpeechSessionAdmin(admin.ModelAdmin):
    list_display = ['user', 'duration', 'words_spoken', 'overall_score', 'experience_gained', 'created_at']
    list_filter = ['created_at', 'overall_score']
    search_fields = ['user__username']
    readonly_fields = ['id', 'overall_score', 'created_at']


@admin.register(Achievement)
class AchievementAdmin(admin.ModelAdmin):
    list_display = ['name', 'achievement_type', 'target_value', 'experience_reward', 'created_at']
    list_filter = ['achievement_type', 'created_at']
    search_fields = ['name', 'description']


@admin.register(UserAchievement)
class UserAchievementAdmin(admin.ModelAdmin):
    list_display = ['user', 'achievement', 'earned_at']
    list_filter = ['achievement', 'earned_at']
    search_fields = ['user__username', 'achievement__name']


@admin.register(SpeechExercise)
class SpeechExerciseAdmin(admin.ModelAdmin):
    list_display = ['title', 'exercise_type', 'difficulty', 'level_required', 'experience_reward', 'is_active']
    list_filter = ['exercise_type', 'difficulty', 'level_required', 'is_active']
    search_fields = ['title', 'description']


@admin.register(ExerciseAttempt)
class ExerciseAttemptAdmin(admin.ModelAdmin):
    list_display = ['user', 'exercise', 'completed', 'created_at']
    list_filter = ['completed', 'exercise__exercise_type', 'created_at']
    search_fields = ['user__username', 'exercise__title']
    readonly_fields = ['id', 'created_at']


@admin.register(WebhookLog)
class WebhookLogAdmin(admin.ModelAdmin):
    list_display = ['webhook_type', 'user_id_from_request', 'status', 'processing_duration', 'created_at']
    list_filter = ['webhook_type', 'status', 'created_at']
    search_fields = ['user_id_from_request', 'error_message']
    readonly_fields = ['created_at', 'processed_at', 'processing_duration']
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('webhook_type', 'user', 'user_id_from_request', 'status')
        }),
        ('Request Details', {
            'fields': ('request_data', 'ip_address', 'user_agent')
        }),
        ('Response Details', {
            'fields': ('response_data', 'error_message', 'processing_time_ms')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'processed_at')
        }),
    )
    
    def has_add_permission(self, request):
        return False  # Webhook logs should only be created by the system
    
    def has_change_permission(self, request, obj=None):
        return False  # Webhook logs should not be edited manually 