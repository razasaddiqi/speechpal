import time
import json
from django.utils import timezone
from .models import WebhookLog


class WebhookLogger:
    """Utility class for logging webhook calls"""
    
    @staticmethod
    def log_webhook_call(webhook_type, request_data, request, start_time=None):
        """
        Log a webhook call
        
        Args:
            webhook_type: Type of webhook ('award_xp' or 'conversation_end')
            request_data: The data received in the webhook
            request: Django request object
            start_time: Start time for calculating processing duration
        """
        try:
            # Extract user_id from request data
            user_id_from_request = request_data.get('user_id')
            
            # Get client information
            ip_address = WebhookLogger._get_client_ip(request)
            user_agent = request.META.get('HTTP_USER_AGENT', '')
            
            # Calculate processing time
            processing_time_ms = None
            if start_time:
                processing_time_ms = int((time.time() - start_time) * 1000)
            
            # Create webhook log entry
            webhook_log = WebhookLog.objects.create(
                webhook_type=webhook_type,
                user_id_from_request=user_id_from_request,
                status='pending',
                request_data=request_data,
                ip_address=ip_address,
                user_agent=user_agent,
                processing_time_ms=processing_time_ms
            )
            
            return webhook_log
            
        except Exception as e:
            # If logging fails, at least print the error
            print(f"Failed to log webhook call: {e}")
            return None
    
    @staticmethod
    def update_webhook_log(webhook_log, status, response_data=None, error_message=None):
        """
        Update a webhook log with results
        
        Args:
            webhook_log: WebhookLog instance
            status: 'success' or 'error'
            response_data: Response data to store
            error_message: Error message if any
        """
        try:
            webhook_log.status = status
            webhook_log.response_data = response_data
            webhook_log.error_message = error_message
            webhook_log.processed_at = timezone.now()
            webhook_log.save()
            
        except Exception as e:
            print(f"Failed to update webhook log: {e}")
    
    @staticmethod
    def _get_client_ip(request):
        """Extract client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    @staticmethod
    def get_webhook_stats():
        """Get statistics about webhook calls"""
        from django.db.models import Count, Avg
        
        stats = WebhookLog.objects.aggregate(
            total_calls=Count('id'),
            successful_calls=Count('id', filter={'status': 'success'}),
            error_calls=Count('id', filter={'status': 'error'}),
            avg_processing_time=Avg('processing_time_ms')
        )
        
        # Add recent activity
        recent_calls = WebhookLog.objects.filter(
            created_at__gte=timezone.now() - timezone.timedelta(hours=24)
        ).count()
        
        stats['recent_calls_24h'] = recent_calls
        
        return stats
    
    @staticmethod
    def get_recent_errors(limit=10):
        """Get recent webhook errors"""
        return WebhookLog.objects.filter(
            status='error'
        ).order_by('-created_at')[:limit]
    
    @staticmethod
    def get_webhook_summary():
        """Get a summary of webhook activity"""
        from django.db.models import Count
        from django.utils import timezone
        
        # Last 24 hours
        last_24h = timezone.now() - timezone.timedelta(hours=24)
        
        # Last 7 days
        last_7d = timezone.now() - timezone.timedelta(days=7)
        
        summary = {
            'last_24h': {
                'award_xp': WebhookLog.objects.filter(
                    webhook_type='award_xp',
                    created_at__gte=last_24h
                ).count(),
                'conversation_end': WebhookLog.objects.filter(
                    webhook_type='conversation_end',
                    created_at__gte=last_24h
                ).count(),
                'errors': WebhookLog.objects.filter(
                    status='error',
                    created_at__gte=last_24h
                ).count(),
            },
            'last_7d': {
                'award_xp': WebhookLog.objects.filter(
                    webhook_type='award_xp',
                    created_at__gte=last_7d
                ).count(),
                'conversation_end': WebhookLog.objects.filter(
                    webhook_type='conversation_end',
                    created_at__gte=last_7d
                ).count(),
                'errors': WebhookLog.objects.filter(
                    status='error',
                    created_at__gte=last_7d
                ).count(),
            }
        }
        
        return summary
