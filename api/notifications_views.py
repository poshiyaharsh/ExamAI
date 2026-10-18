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
