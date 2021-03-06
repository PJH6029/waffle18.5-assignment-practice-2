from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.db import IntegrityError
from rest_framework import status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from user.serializers import UserSerializer, ParticipantProfileSerializer


class UserViewSet(viewsets.GenericViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    # 이거 자체는 class의 tuple로. get_permissions를 override할 때 return을 super로
    permission_classes = (IsAuthenticated, )

    def get_permissions(self):
        if self.action in ('create', 'login'):
            return (AllowAny(), )
        return super(UserViewSet, self).get_permissions()

    # POST /api/v1/user/
    def create(self, request):
        print("DEBUG: UserViewSet.create()")
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = serializer.save()
        except IntegrityError:
            return Response({"error": "A user with that username already exists."}, status=status.HTTP_400_BAD_REQUEST)

        login(request, user)

        data = serializer.data
        data['token'] = user.auth_token.key
        return Response(data, status=status.HTTP_201_CREATED)

    # PUT /api/v1/user/login/
    @action(detail=False, methods=['PUT'])
    def login(self, request):
        print("DEBUG: UserViewSet.login()")
        username = request.data.get('username')
        password = request.data.get('password')

        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)

            data = self.get_serializer(user).data
            token, created = Token.objects.get_or_create(user=user)
            data['token'] = token.key
            return Response(data)

        return Response({"error": "Wrong username or wrong password"}, status=status.HTTP_403_FORBIDDEN)

    # POST /api/v1/user/logout/
    @action(detail=False, methods=['POST'])
    def logout(self, request):
        print("DEBUG: UserViewSet.logout()")
        logout(request)
        return Response()

    # GET /api/v1/user/me/
    def retrieve(self, request, pk=None):
        print("DEBUG: UserViewSet.retrieve()")
        # get_object()의 기본 filter는 pk=pk?? YES
        user = request.user if pk == 'me' else self.get_object()
        return Response(self.get_serializer(user).data)

    # PUT /api/v1/user/me/
    def update(self, request, pk=None):
        print("DEBUG: UserViewSet.update()")
        if pk != 'me':
            return Response({"error": "Can't update other Users information"}, status=status.HTTP_403_FORBIDDEN)

        user = request.user
        data = request.data.copy()
        data.pop('accepted', None)

        # partial=True때문에 일부만 받아와도 가능!
        serializer = self.get_serializer(user, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.update(user, serializer.validated_data)
        return Response(serializer.data)

    # POST /api/v1/user/participant/
    @action(detail=False, methods=['POST'])
    def participant(self, request):
        print("DEBUG: UserViewSet.participant()")
        user = request.user
        data = request.data.copy()

        if hasattr(user, 'participant'):
            return Response({"error": "You're already a participant"}, status=status.HTTP_400_BAD_REQUEST)

        # User은 이미 있고, 옆에 ParticipantProfile을 하나 더 만들어주는 과정
        data['user_id'] = user.id

        serializer = ParticipantProfileSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        # refresh
        user.refresh_from_db()
        return Response(self.get_serializer(user).data, status=status.HTTP_201_CREATED)

