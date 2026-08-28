from django.db import migrations


FORWARD_SQL = """
CREATE TRIGGER prevent_overlapping_confirmed_appointments_insert
BEFORE INSERT ON portal_app_appointment
WHEN NEW.status = 'confirmed'
BEGIN
    SELECT RAISE(
        ABORT,
        'Provider already has an overlapping confirmed appointment'
    )
    WHERE EXISTS (
        SELECT 1
        FROM portal_app_appointment AS existing
        WHERE existing.provider_id = NEW.provider_id
          AND existing.status = 'confirmed'
          AND datetime(existing.scheduled_at)
              < datetime(
                  NEW.scheduled_at,
                  '+' || NEW.duration_minutes || ' minutes'
              )
          AND datetime(NEW.scheduled_at)
              < datetime(
                  existing.scheduled_at,
                  '+' || existing.duration_minutes || ' minutes'
              )
    );
END;


CREATE TRIGGER prevent_overlapping_confirmed_appointments_update
BEFORE UPDATE OF
    provider_id,
    scheduled_at,
    duration_minutes,
    status
ON portal_app_appointment
WHEN NEW.status = 'confirmed'
BEGIN
    SELECT RAISE(
        ABORT,
        'Provider already has an overlapping confirmed appointment'
    )
    WHERE EXISTS (
        SELECT 1
        FROM portal_app_appointment AS existing
        WHERE existing.id != NEW.id
          AND existing.provider_id = NEW.provider_id
          AND existing.status = 'confirmed'
          AND datetime(existing.scheduled_at)
              < datetime(
                  NEW.scheduled_at,
                  '+' || NEW.duration_minutes || ' minutes'
              )
          AND datetime(NEW.scheduled_at)
              < datetime(
                  existing.scheduled_at,
                  '+' || existing.duration_minutes || ' minutes'
              )
    );
END;
"""


REVERSE_SQL = """
DROP TRIGGER IF EXISTS
prevent_overlapping_confirmed_appointments_insert;

DROP TRIGGER IF EXISTS
prevent_overlapping_confirmed_appointments_update;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("portal_app", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(
            sql=FORWARD_SQL,
            reverse_sql=REVERSE_SQL,
        ),
    ]