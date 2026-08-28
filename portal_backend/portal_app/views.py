from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    Appointment,
    AppointmentHistory,
    NotificationOutbox,
    Patient,
    Provider,
)
from .serializers import (
    AppointmentCancelSerializer,
    AppointmentConfirmSerializer,
    AppointmentHistorySerializer,
    AppointmentRequestSerializer,
    AppointmentRescheduleSerializer,
    AppointmentSerializer,
    NotificationOutboxSerializer,
    PatientSerializer,
    ProviderSerializer,
)
from .services import (
    AppointmentNotFound,
    AppointmentOverlapError,
    AppointmentPermissionError,
    AppointmentServiceError,
    AppointmentVersionConflict,
    InvalidAppointmentTransition,
    cancel_appointment,
    confirm_appointment,
    request_appointment,
    reschedule_appointment,
)


# ============================================================
# Common exception mapping
# ============================================================


def service_exception_response(exc):
    """
    Convert domain/service exceptions into HTTP responses.

    The service layer does not know anything about HTTP.

    This keeps:
        business logic != transport logic
    """

    if isinstance(exc, AppointmentVersionConflict):
        return Response(
            {
                "error": "appointment_version_conflict",
                "detail": str(exc),
            },
            status=status.HTTP_409_CONFLICT,
        )

    if isinstance(exc, AppointmentOverlapError):
        return Response(
            {
                "error": "appointment_overlap",
                "detail": str(exc),
            },
            status=status.HTTP_409_CONFLICT,
        )

    if isinstance(exc, AppointmentPermissionError):
        return Response(
            {
                "error": "permission_denied",
                "detail": str(exc),
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    if isinstance(exc, InvalidAppointmentTransition):
        return Response(
            {
                "error": "invalid_status_transition",
                "detail": str(exc),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if isinstance(exc, AppointmentNotFound):
        return Response(
            {
                "error": "appointment_not_found",
                "detail": str(exc),
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    if isinstance(exc, AppointmentServiceError):
        return Response(
            {
                "error": "appointment_error",
                "detail": str(exc),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    return None


# ============================================================
# Patient / Provider
# ============================================================


class PatientListAPIView(APIView):
    """
    GET /api/patients/

    Used by the frontend role switcher/demo environment.

    No authentication is implemented because the assignment
    explicitly says that real authentication is not required.
    """

    def get(self, request):
        patients = Patient.objects.all()

        serializer = PatientSerializer(
            patients,
            many=True,
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )


class ProviderListAPIView(APIView):
    """
    GET /api/providers/
    """

    def get(self, request):
        providers = Provider.objects.all()

        serializer = ProviderSerializer(
            providers,
            many=True,
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )


# ============================================================
# Appointment list / create
# ============================================================


class AppointmentListCreateAPIView(APIView):
    """
    GET  /api/appointments/
    POST /api/appointments/

    GET supports:

        ?patient_id=1
        ?provider_id=1

    This allows the frontend role switcher to show the
    appropriate appointments.
    """

    def get(self, request):
        """
        Appointment list.

        Query filtering is done before serialization so we don't
        unnecessarily load unrelated appointments.
        """

        queryset = Appointment.objects.select_related(
            "patient",
            "provider",
        )

        patient_id = request.query_params.get(
            "patient_id"
        )

        provider_id = request.query_params.get(
            "provider_id"
        )

        if patient_id is not None:
            try:
                patient_id = int(patient_id)
            except (TypeError, ValueError):
                return Response(
                    {
                        "error": "invalid_patient_id",
                        "detail": "patient_id must be an integer.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            queryset = queryset.filter(
                patient_id=patient_id
            )

        if provider_id is not None:
            try:
                provider_id = int(provider_id)
            except (TypeError, ValueError):
                return Response(
                    {
                        "error": "invalid_provider_id",
                        "detail": "provider_id must be an integer.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            queryset = queryset.filter(
                provider_id=provider_id
            )

        serializer = AppointmentSerializer(
            queryset,
            many=True,
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        """
        Patient requests an appointment.

        Lifecycle:

            request
              ↓
            serializer validation
              ↓
            object lookup already handled by serializer
              ↓
            service/business validation
              ↓
            database transaction
              ↓
            response serialization
        """

        serializer = AppointmentRequestSerializer(
            data=request.data
        )

        # ----------------------------------------------------
        # 1. Request validation
        # ----------------------------------------------------

        serializer.is_valid(
            raise_exception=True
        )

        data = serializer.validated_data

        # ----------------------------------------------------
        # 2. Business logic
        # ----------------------------------------------------

        try:
            appointment = request_appointment(
                patient=data["patient"],
                provider=data["provider"],
                scheduled_at=data["scheduled_at"],
                appointment_type=data["appointment_type"],
                reason=data["reason"],
                duration_minutes=data[
                    "duration_minutes"
                ],
            )

        except AppointmentServiceError as exc:
            return service_exception_response(exc)

        # ----------------------------------------------------
        # 3. Response serialization
        # ----------------------------------------------------

        response_serializer = AppointmentSerializer(
            appointment
        )

        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED,
        )


# ============================================================
# Appointment detail
# ============================================================


class AppointmentDetailAPIView(APIView):
    """
    GET /api/appointments/<id>/

    Returns the current appointment state.
    """

    def get(self, request, pk):
        appointment = get_object_or_404(
            Appointment.objects.select_related(
                "patient",
                "provider",
            ),
            pk=pk,
        )

        serializer = AppointmentSerializer(
            appointment
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )


# ============================================================
# Confirm
# ============================================================


class AppointmentConfirmAPIView(APIView):
    """
    POST /api/appointments/<id>/confirm/

    Provider action.
    """

    def post(self, request, pk):
        # ----------------------------------------------------
        # 1. Request validation
        # ----------------------------------------------------

        serializer = AppointmentConfirmSerializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        expected_version = serializer.validated_data[
            "expected_version"
        ]

        provider_id = request.data.get(
            "provider_id"
        )

        if provider_id is None:
            return Response(
                {
                    "error": "provider_id_required",
                    "detail": "provider_id is required.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            provider_id = int(provider_id)
        except (TypeError, ValueError):
            return Response(
                {
                    "error": "invalid_provider_id",
                    "detail": "provider_id must be an integer.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ----------------------------------------------------
        # 2. Actor/business validation
        # ----------------------------------------------------

        provider = get_object_or_404(
            Provider,
            pk=provider_id,
        )

        # ----------------------------------------------------
        # 3. Business logic + database protection
        # ----------------------------------------------------

        try:
            appointment = confirm_appointment(
                appointment_id=pk,
                provider=provider,
                expected_version=expected_version,
            )

        except AppointmentServiceError as exc:
            return service_exception_response(exc)

        # ----------------------------------------------------
        # 4. Response
        # ----------------------------------------------------

        response_serializer = AppointmentSerializer(
            appointment
        )

        return Response(
            response_serializer.data,
            status=status.HTTP_200_OK,
        )


# ============================================================
# Reschedule
# ============================================================


class AppointmentRescheduleAPIView(APIView):
    """
    POST /api/appointments/<id>/reschedule/

    Provider action.
    """

    def post(self, request, pk):
        # ----------------------------------------------------
        # 1. Request validation
        # ----------------------------------------------------

        serializer = AppointmentRescheduleSerializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        new_scheduled_at = serializer.validated_data[
            "new_scheduled_at"
        ]

        expected_version = serializer.validated_data[
            "expected_version"
        ]

        provider_id = request.data.get(
            "provider_id"
        )

        if provider_id is None:
            return Response(
                {
                    "error": "provider_id_required",
                    "detail": "provider_id is required.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            provider_id = int(provider_id)
        except (TypeError, ValueError):
            return Response(
                {
                    "error": "invalid_provider_id",
                    "detail": "provider_id must be an integer.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ----------------------------------------------------
        # 2. Actor/business validation
        # ----------------------------------------------------

        provider = get_object_or_404(
            Provider,
            pk=provider_id,
        )

        # ----------------------------------------------------
        # 3. Business logic
        # ----------------------------------------------------

        try:
            appointment = reschedule_appointment(
                appointment_id=pk,
                provider=provider,
                new_scheduled_at=new_scheduled_at,
                expected_version=expected_version,
            )

        except AppointmentServiceError as exc:
            return service_exception_response(exc)

        # ----------------------------------------------------
        # 4. Response
        # ----------------------------------------------------

        response_serializer = AppointmentSerializer(
            appointment
        )

        return Response(
            response_serializer.data,
            status=status.HTTP_200_OK,
        )


# ============================================================
# Cancel
# ============================================================


class AppointmentCancelAPIView(APIView):
    """
    POST /api/appointments/<id>/cancel/

    Patient action.
    """

    def post(self, request, pk):
        # ----------------------------------------------------
        # 1. Request validation
        # ----------------------------------------------------

        serializer = AppointmentCancelSerializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        expected_version = serializer.validated_data[
            "expected_version"
        ]

        patient_id = request.data.get(
            "patient_id"
        )

        if patient_id is None:
            return Response(
                {
                    "error": "patient_id_required",
                    "detail": "patient_id is required.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            patient_id = int(patient_id)
        except (TypeError, ValueError):
            return Response(
                {
                    "error": "invalid_patient_id",
                    "detail": "patient_id must be an integer.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ----------------------------------------------------
        # 2. Actor/business validation
        # ----------------------------------------------------

        patient = get_object_or_404(
            Patient,
            pk=patient_id,
        )

        # ----------------------------------------------------
        # 3. Business logic
        # ----------------------------------------------------

        try:
            appointment = cancel_appointment(
                appointment_id=pk,
                patient=patient,
                expected_version=expected_version,
            )

        except AppointmentServiceError as exc:
            return service_exception_response(exc)

        # ----------------------------------------------------
        # 4. Response
        # ----------------------------------------------------

        response_serializer = AppointmentSerializer(
            appointment
        )

        return Response(
            response_serializer.data,
            status=status.HTTP_200_OK,
        )


# ============================================================
# History
# ============================================================


class AppointmentHistoryAPIView(APIView):
    """
    GET /api/appointments/<id>/history/

    Problem 2:
    Provides the complete appointment audit trail.
    """

    def get(self, request, pk):
        # Verify appointment exists.
        get_object_or_404(
            Appointment,
            pk=pk,
        )

        history = AppointmentHistory.objects.filter(
            appointment_id=pk
        ).order_by(
            "created_at",
            "id",
        )

        serializer = AppointmentHistorySerializer(
            history,
            many=True,
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )


# ============================================================
# Notification outbox
# ============================================================


class NotificationOutboxAPIView(APIView):
    """
    GET /api/notifications/

    Development/demo endpoint for Problem 3.

    This allows us to demonstrate that confirmation creates
    a notification work item without coupling appointment
    confirmation to external notification delivery.
    """

    def get(self, request):
        notifications = NotificationOutbox.objects.all()

        serializer = NotificationOutboxSerializer(
            notifications,
            many=True,
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )