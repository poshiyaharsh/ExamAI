from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import TestMessageSerializer


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
