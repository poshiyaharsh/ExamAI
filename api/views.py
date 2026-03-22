from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import ChangePasswordSerializer, TestMessageSerializer


class TestAPIView(APIView):
    def get(self, request):
        return Response(
            {
                'status': 'success',
                'message': 'Django API is connected successfully.',
                'data': {
                    'course': 'Mini Project Integration',
                    'backend': 'Django REST Framework',
                },
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        serializer = TestMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated_data = serializer.validated_data

        return Response(
            {
                'status': 'success',
                'message': f"Hello {validated_data['name']}, your message was received.",
                'submitted': validated_data,
            },
            status=status.HTTP_201_CREATED,
        )


class ChangePasswordAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        request.user.set_password(serializer.validated_data['new_password'])
        request.user.save(update_fields=['password'])

        return Response(
            {
                'status': 'success',
                'message': 'Password updated successfully.',
            },
            status=status.HTTP_200_OK,
        )
