from rest_framework import serializers


class TestMessageSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    message = serializers.CharField(max_length=500)
