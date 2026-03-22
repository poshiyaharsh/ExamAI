from rest_framework import serializers


class TestMessageSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    message = serializers.CharField(max_length=500)


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate_current_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('Current password is incorrect.')
        return value

    def validate_new_password(self, value):
        has_letter = any(char.isalpha() for char in value)
        has_number = any(char.isdigit() for char in value)
        if not (has_letter and has_number):
            raise serializers.ValidationError('New password must include at least one letter and one number.')
        return value
