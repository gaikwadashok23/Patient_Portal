from django.contrib import admin
from .models import Appointment, AppointmentHistory, NotificationOutbox, Patient, Provider


class AppointmentHistoryInline(admin.TabularInline):
    model = AppointmentHistory
    extra = 0
    can_delete = False
    readonly_fields = (
        "action",
        "actor_type",
        "actor_name",
        "old_status",
        "old_scheduled_at",
        "new_status",
        "new_scheduled_at",
        "created_at",
    )

    def has_add_permission(self, request, obj=None):
        return False


class NotificationOutboxInline(admin.TabularInline):
    model = NotificationOutbox
    extra = 0
    can_delete = False
    readonly_fields = (
        "channel",
        "recipient",
        "message",
        "status",
        "created_at",
        "processed_at",
    )

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ("id","name", "email", "phone", "created_at")
    search_fields = ("name", "email", "phone")
    list_filter = ("created_at",)
    readonly_fields = ("created_at",)


@admin.register(Provider)
class ProviderAdmin(admin.ModelAdmin):
    list_display = ("id","name", "specialty", "created_at")
    search_fields = ("name", "specialty")
    list_filter = ("specialty", "created_at")
    readonly_fields = ("created_at",)


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "patient",
        "provider",
        "scheduled_at",
        "duration_minutes",
        "appointment_type",
        "status",
        "version",
    )
    list_filter = ("status", "appointment_type", "scheduled_at", "provider")
    search_fields = (
        "patient__name",
        "patient__email",
        "provider__name",
        "reason",
    )
    readonly_fields = ("version", "created_at", "updated_at", "ends_at")
    inlines = [AppointmentHistoryInline, NotificationOutboxInline]

    fieldsets = (
        (
            "Core Information",
            {
                "fields": (
                    "patient",
                    "provider",
                    "appointment_type",
                    "status",
                    "reason",
                )
            },
        ),
        (
            "Schedule",
            {
                "fields": (
                    "scheduled_at",
                    "duration_minutes",
                    "ends_at",
                )
            },
        ),
        (
            "Metadata & Concurrency",
            {
                "fields": (
                    "version",
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )


@admin.register(AppointmentHistory)
class AppointmentHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "appointment",
        "action",
        "actor_type",
        "actor_name",
        "old_status",
        "new_status",
        "created_at",
    )
    list_filter = ("action", "actor_type", "created_at")
    search_fields = ("actor_name", "appointment__id", "appointment__patient__name")
    readonly_fields = [field.name for field in AppointmentHistory._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(NotificationOutbox)
class NotificationOutboxAdmin(admin.ModelAdmin):
    list_display = ("id", "appointment", "channel", "recipient", "status", "created_at", "processed_at")
    list_filter = ("status", "channel", "created_at")
    search_fields = ("recipient", "message", "appointment__id")
    readonly_fields = ("created_at",)