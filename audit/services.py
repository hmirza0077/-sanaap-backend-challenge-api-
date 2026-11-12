from audit.models import AuditLog


class AuditLogService:
    @staticmethod
    def log_action(user, action, document):
        """Save one line of history: who did what to which document."""
        AuditLog.objects.create(
            user=user,
            action=action,
            document_id=document.id,
            document_title=document.title,
        )
