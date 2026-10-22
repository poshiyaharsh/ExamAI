from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Notification


class NotificationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Notification.objects.filter(user=request.user).order_by('-created_at')[:50]
        unread_count = Notification.objects.filter(user=request.user, is_read=False).count()
        results = [
            {
                'id': n.id,
                'title': n.title,
                'message': n.message,
                'type': n.type,
                'link': n.link,
                'is_read': n.is_read,
                'created_at': n.created_at.isoformat(),
            }
            for n in qs
        ]
        return Response({
            'unread_count': unread_count,
            'notifications': results,
        })


class NotificationMarkReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, notification_id):
        updated = Notification.objects.filter(id=notification_id, user=request.user).update(is_read=True)
        if not updated:
            return Response({'detail': 'Notification not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response({'detail': 'Marked as read.'}, status=status.HTTP_200_OK)


class NotificationMarkAllReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return Response({'detail': 'All notifications marked as read.'}, status=status.HTTP_200_OK)


class NotificationPopupListView(APIView):
    """
    Returns pending pop-ups targeted to the authenticated user.
    Records popup_shown_at upon initial retrieval.
    Suppressed automatically during active exam attempts on the frontend.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        now = timezone.now()
        qs = Notification.objects.filter(
            user=request.user,
            is_popup=True,
            popup_dismissed_at__isnull=True,
        ).order_by('created_at')[:10]

        # Record shown timestamp for first display
        unshown_ids = [n.id for n in qs if not n.popup_shown_at]
        if unshown_ids:
            Notification.objects.filter(id__in=unshown_ids).update(popup_shown_at=now)

        results = [
            {
                'id': n.id,
                'title': n.title,
                'message': n.message,
                'type': n.type,
                'link': n.link,
                'created_at': n.created_at.isoformat(),
                'popup_shown_at': (n.popup_shown_at or now).isoformat(),
            }
            for n in qs
        ]
        return Response({
            'count': len(results),
            'popups': results,
        }, status=status.HTTP_200_OK)


class NotificationDismissPopupView(APIView):
    """
    Dismisses a single pop-up notification for the user.
    Also marks the notification as read.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, notification_id):
        now = timezone.now()
        updated = Notification.objects.filter(
            id=notification_id,
            user=request.user,
        ).update(
            popup_dismissed_at=now,
            is_read=True,
        )
        if not updated:
            return Response({'detail': 'Notification not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response({'detail': 'Popup dismissed successfully.'}, status=status.HTTP_200_OK)


class NotificationDismissAllPopupsView(APIView):
    """
    Dismisses all pending pop-up notifications for the user at once.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        now = timezone.now()
        count = Notification.objects.filter(
            user=request.user,
            is_popup=True,
            popup_dismissed_at__isnull=True,
        ).update(
            popup_dismissed_at=now,
            is_read=True,
        )
        return Response({'detail': f'Dismissed {count} popups.'}, status=status.HTTP_200_OK)

