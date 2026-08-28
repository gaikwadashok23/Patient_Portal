import { useEffect, useState } from "react";

import {
    getAppointment,
    getAppointmentHistory,
    confirmAppointment,
    rescheduleAppointment,
} from "../api/api";


/* ============================================================
   DATE FORMATTER
============================================================ */

function formatDateTime(value) {
    if (!value) {
        return "—";
    }

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
        return "—";
    }

    return date.toLocaleString("en-IN", {
        weekday: "long",
        day: "2-digit",
        month: "long",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
    });
}


/* ============================================================
   DATETIME LOCAL FORMATTER
============================================================ */

function toDateTimeLocal(value) {
    if (!value) {
        return "";
    }

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
        return "";
    }

    const offset =
        date.getTimezoneOffset() * 60000;

    return new Date(
        date.getTime() - offset
    )
        .toISOString()
        .slice(0, 16);
}


/* ============================================================
   HISTORY ACTION FORMATTER
============================================================ */

function formatAction(action) {
    if (!action) {
        return "";
    }

    return action
        .replaceAll("_", " ")
        .replace(/\b\w/g, (letter) =>
            letter.toUpperCase()
        );
}


/* ============================================================
   COMPONENT
============================================================ */

export default function ProviderAppointmentDetail({
    appointmentId,
    onBack,
    onUpdated,
}) {

    const [appointment, setAppointment] =
        useState(null);

    const [history, setHistory] =
        useState([]);

    const [newDateTime, setNewDateTime] =
        useState("");

    const [loading, setLoading] =
        useState(true);

    const [saving, setSaving] =
        useState(false);

    const [error, setError] =
        useState("");

    const [success, setSuccess] =
        useState("");


    /* ========================================================
       LOAD APPOINTMENT + HISTORY
    ======================================================== */

    async function loadData({
        showLoading = true,
        clearMessages = true,
    } = {}) {

        if (!appointmentId) {
            setError(
                "Appointment ID is missing."
            );

            setLoading(false);

            return;
        }

        try {

            if (showLoading) {
                setLoading(true);
            }

            if (clearMessages) {
                setError("");
            }

            const [
                appointmentData,
                historyData,
            ] = await Promise.all([
                getAppointment(
                    appointmentId
                ),

                getAppointmentHistory(
                    appointmentId
                ),
            ]);


            setAppointment(
                appointmentData
            );


            setHistory(
                Array.isArray(historyData)
                    ? historyData
                    : historyData?.results || []
            );


            /*
             * Keep the datetime input synchronized
             * with the latest backend value.
             */

            setNewDateTime(
                toDateTimeLocal(
                    appointmentData.scheduled_at
                )
            );

        } catch (error) {

            console.error(
                "LOAD PROVIDER APPOINTMENT ERROR:",
                error
            );

            setError(
                error.message ||
                "Unable to load appointment."
            );

        } finally {

            if (showLoading) {
                setLoading(false);
            }
        }
    }


    /* ========================================================
       INITIAL LOAD
    ======================================================== */

    useEffect(() => {

        loadData();

    }, [appointmentId]);


    /* ========================================================
       PROVIDER CONFIRM
    ======================================================== */

    async function handleConfirm() {

        if (!appointment) {
            return;
        }


        if (
            appointment.status !==
            "pending"
        ) {

            setError(
                "Only pending appointments can be confirmed."
            );

            return;
        }


        if (!appointment.provider) {

            setError(
                "Provider information is missing. Please refresh the appointment."
            );

            return;
        }


        if (
            appointment.version === undefined ||
            appointment.version === null
        ) {

            setError(
                "Appointment version is missing. Please refresh the appointment."
            );

            return;
        }


        try {

            setSaving(true);
            setError("");
            setSuccess("");


            /*
             * Pass the REAL appointment object.
             *
             * api.js extracts:
             *
             * appointment.id
             * appointment.provider
             * appointment.version
             */

            const updated =
                await confirmAppointment(
                    appointment
                );


            setAppointment(updated);


            setSuccess(
                "Appointment confirmed successfully."
            );


            await loadData({
                showLoading: false,
                clearMessages: false,
            });


            if (onUpdated) {
                onUpdated();
            }

        } catch (error) {

            console.error(
                "CONFIRM APPOINTMENT ERROR:",
                error
            );


            /* =================================================
               PROBLEM 1 - VERSION CONFLICT
            ================================================= */

            if (
                error.status === 409 ||
                error.data?.error ===
                    "appointment_version_conflict"
            ) {

                setSuccess("");

                setError(
                    "Appointment updated. Another user changed this appointment while you were viewing it. Your confirmation was not applied. The latest appointment details have been loaded."
                );


                await loadData({
                    showLoading: false,
                    clearMessages: false,
                });

                return;
            }


            /* =================================================
               PROBLEM 4 - OVERLAPPING APPOINTMENT
            ================================================= */

            if (
                error.data?.error ===
                "appointment_overlap"
            ) {

                setSuccess("");

                setError(
                    error.data?.detail ||
                    "The provider already has a confirmed appointment during this time. Please choose another time."
                );

                return;
            }


            /* =================================================
               GENERIC ERROR
            ================================================= */

            setError(
                error.data?.detail ||
                error.message ||
                "Unable to confirm appointment."
            );

        } finally {

            setSaving(false);
        }
    }


    /* ========================================================
       PROVIDER RESCHEDULE
    ======================================================== */

    async function handleReschedule(event) {

        event.preventDefault();


        if (!appointment) {
            return;
        }


        /* ----------------------------------------------------
           STATUS
        ---------------------------------------------------- */

        if (
            appointment.status ===
            "cancelled"
        ) {

            setError(
                "Cancelled appointments cannot be rescheduled."
            );

            return;
        }


        /* ----------------------------------------------------
           PROVIDER ID
        ---------------------------------------------------- */

        if (!appointment.provider) {

            setError(
                "Provider information is missing. Please refresh the appointment."
            );

            return;
        }


        /* ----------------------------------------------------
           NEW DATE
        ---------------------------------------------------- */

        if (!newDateTime) {

            setError(
                "Please select a new date and time."
            );

            return;
        }


        /* ----------------------------------------------------
           VERSION
        ---------------------------------------------------- */

        if (
            appointment.version === undefined ||
            appointment.version === null
        ) {

            setError(
                "Appointment version is missing. Please refresh the appointment."
            );

            return;
        }


        const selectedDate =
            new Date(newDateTime);


        if (
            Number.isNaN(
                selectedDate.getTime()
            )
        ) {

            setError(
                "Invalid appointment date/time."
            );

            return;
        }


        /* ----------------------------------------------------
           FUTURE DATE VALIDATION
        ---------------------------------------------------- */

        if (
            selectedDate <=
            new Date()
        ) {

            setError(
                "Appointment date/time must be in the future."
            );

            return;
        }


        try {

            setSaving(true);
            setError("");
            setSuccess("");


            const isoDate =
                selectedDate.toISOString();


            /*
             * IMPORTANT
             *
             * Pass the COMPLETE REAL appointment object.
             *
             * api.js extracts:
             *
             * appointment.id
             * appointment.provider
             * appointment.version
             *
             * and sends:
             *
             * {
             *     provider_id: appointment.provider,
             *     new_scheduled_at: isoDate,
             *     expected_version: appointment.version
             * }
             */

            const updated =
                await rescheduleAppointment(
                    appointment,
                    isoDate
                );


            setAppointment(updated);


            setNewDateTime(
                toDateTimeLocal(
                    updated.scheduled_at
                )
            );


            setSuccess(
                "Appointment rescheduled successfully."
            );


            await loadData({
                showLoading: false,
                clearMessages: false,
            });


            if (onUpdated) {
                onUpdated();
            }

        } catch (error) {

            console.error(
                "RESCHEDULE APPOINTMENT ERROR:",
                error
            );


            /* =================================================
               PROBLEM 4
               
               Provider cannot have two overlapping confirmed
               appointments.
               
               Backend is the final authority.
            ================================================= */

            if (
                error.data?.error ===
                "appointment_overlap"
            ) {

                setSuccess("");


                setError(
                    error.data?.detail ||
                    "The provider already has a confirmed appointment during this time. Please choose another time."
                );


                /*
                 * Do NOT change the appointment locally.
                 *
                 * The backend rejected the update.
                 *
                 * The existing appointment remains unchanged.
                 */

                return;
            }


            /* =================================================
               PROBLEM 1
               
               Stale appointment version.
            ================================================= */

            if (
                error.status === 409 ||
                error.data?.error ===
                    "appointment_version_conflict"
            ) {

                setSuccess("");


                setError(
                    "Appointment updated. Another user changed this appointment while you were viewing it. Your reschedule was not applied. The latest appointment details have been loaded."
                );


                await loadData({
                    showLoading: false,
                    clearMessages: false,
                });


                return;
            }


            /* =================================================
               OTHER BACKEND VALIDATION ERROR
            ================================================= */

            setError(
                error.data?.detail ||
                error.message ||
                "Unable to reschedule appointment."
            );

        } finally {

            setSaving(false);
        }
    }


    /* ========================================================
       LOADING STATE
    ======================================================== */

    if (loading) {

        return (
            <div className="detail-page">

                <button
                    className="back-button"
                    onClick={onBack}
                >
                    ← Back to appointments
                </button>


                <div className="detail-loading">
                    Loading appointment...
                </div>

            </div>
        );
    }


    /* ========================================================
       NOT FOUND
    ======================================================== */

    if (!appointment) {

        return (
            <div className="detail-page">

                <button
                    className="back-button"
                    onClick={onBack}
                >
                    ← Back
                </button>


                <div
                    className="detail-error"
                    role="alert"
                >
                    {
                        error ||
                        "Appointment not found."
                    }
                </div>

            </div>
        );
    }


    /* ========================================================
       UI
    ======================================================== */

    return (
        <div className="detail-page">


            {/* ==================================================
                HEADER
            ================================================== */}

            <div className="detail-header">

                <button
                    className="back-button"
                    onClick={onBack}
                    disabled={saving}
                >
                    ← Back to appointments
                </button>


                <span
                    className={`status-badge status-${appointment.status}`}
                >
                    {
                        appointment.status_display ||
                        appointment.status
                    }
                </span>

            </div>


            {/* ==================================================
                ERROR
            ================================================== */}

            {error && (

                <div
                    className="error-banner"
                    role="alert"
                >

                    <strong>
                        Action could not be completed
                    </strong>

                    <p>
                        {error}
                    </p>

                </div>

            )}


            {/* ==================================================
                SUCCESS
            ================================================== */}

            {success && (

                <div
                    className="success-banner"
                    role="status"
                >
                    {success}
                </div>

            )}


            {/* ==================================================
                APPOINTMENT CARD
            ================================================== */}

            <div className="detail-card">


                {/* ------------------------------------------------
                    HEADER
                ------------------------------------------------ */}

                <div className="detail-card-header">

                    <div>

                        <span className="eyebrow">
                            PROVIDER APPOINTMENT
                        </span>


                        <h2>
                            {
                                appointment.appointment_type_display ||
                                appointment.appointment_type ||
                                "Appointment"
                            }
                        </h2>

                    </div>


                    <div className="appointment-id">
                        #{appointment.id}
                    </div>

                </div>


                {/* ------------------------------------------------
                    DETAILS
                ------------------------------------------------ */}

                <div className="detail-grid">


                    {/* PATIENT */}

                    <div className="detail-item">

                        <span>
                            Patient
                        </span>

                        <strong>
                            {
                                appointment.patient_name ||
                                "—"
                            }
                        </strong>

                    </div>


                    {/* PATIENT EMAIL */}

                    <div className="detail-item">

                        <span>
                            Patient email
                        </span>

                        <strong>
                            {
                                appointment.patient_email ||
                                "—"
                            }
                        </strong>

                    </div>


                    {/* DATE */}

                    <div className="detail-item">

                        <span>
                            Current date & time
                        </span>

                        <strong>
                            {formatDateTime(
                                appointment.scheduled_at
                            )}
                        </strong>

                    </div>


                    {/* DURATION */}

                    <div className="detail-item">

                        <span>
                            Duration
                        </span>

                        <strong>
                            {
                                appointment.duration_minutes ??
                                "—"
                            }{" "}
                            minutes
                        </strong>

                    </div>

                </div>


                {/* ------------------------------------------------
                    REASON
                ------------------------------------------------ */}

                <div className="reason-section">

                    <span>
                        Reason for visit
                    </span>

                    <p>
                        {
                            appointment.reason ||
                            "No reason provided."
                        }
                    </p>

                </div>


                {/* =================================================
                    PROVIDER ACTIONS
                ================================================= */}

                {appointment.status !==
                    "cancelled" && (

                    <div className="provider-actions">


                        {/* -----------------------------------------
                            CONFIRM
                        ----------------------------------------- */}

                        {appointment.status ===
                            "pending" && (

                            <button
                                className="primary-button"
                                disabled={saving}
                                onClick={
                                    handleConfirm
                                }
                            >

                                {saving
                                    ? "Processing..."
                                    : "Confirm appointment"}

                            </button>
                        )}


                        {/* -----------------------------------------
                            RESCHEDULE
                            
                            Both pending and confirmed appointments
                            can be rescheduled.
                        ----------------------------------------- */}

                        <form
                            className="reschedule-form"
                            onSubmit={
                                handleReschedule
                            }
                        >

                            <label>
                                Change date & time
                            </label>


                            <div className="reschedule-row">

                                <input
                                    type="datetime-local"
                                    value={
                                        newDateTime
                                    }
                                    onChange={(event) =>
                                        setNewDateTime(
                                            event.target.value
                                        )
                                    }
                                    disabled={saving}
                                />


                                <button
                                    type="submit"
                                    className="secondary-button"
                                    disabled={saving}
                                >

                                    {saving
                                        ? "Processing..."
                                        : "Reschedule"}

                                </button>

                            </div>

                        </form>

                    </div>
                )}


                {/* =================================================
                    CONFIRMED NOTICE
                ================================================= */}

                {appointment.status ===
                    "confirmed" && (

                    <div className="confirmed-provider-notice">

                        <strong>
                            Appointment confirmed
                        </strong>

                        <p>
                            The appointment is confirmed.
                            The provider can still reschedule
                            it if required.
                        </p>

                    </div>
                )}


                {/* =================================================
                    CANCELLED
                ================================================= */}

                {appointment.status ===
                    "cancelled" && (

                    <div className="cancelled-notice">

                        This appointment has been
                        cancelled.

                    </div>
                )}

            </div>


            {/* ====================================================
                AUDIT HISTORY
            ==================================================== */}

            <div className="history-card">


                <div className="history-header">

                    <span className="eyebrow">
                        AUDIT TRAIL
                    </span>

                    <h2>
                        Appointment history
                    </h2>

                </div>


                {history.length === 0 ? (

                    <p className="history-empty">
                        No history available.
                    </p>

                ) : (

                    <div className="history-list">

                        {history.map((item) => (

                            <div
                                className="history-item"
                                key={item.id}
                            >

                                <div
                                    className="history-dot"
                                />


                                <div
                                    className="history-content"
                                >


                                    {/* HISTORY TITLE */}

                                    <div
                                        className="history-title"
                                    >

                                        <strong>
                                            {formatAction(
                                                item.action
                                            )}
                                        </strong>


                                        <span>
                                            {
                                                item.actor_name ||
                                                "System"
                                            }
                                        </span>

                                    </div>


                                    {/* HISTORY TIME */}

                                    <div
                                        className="history-time"
                                    >
                                        {formatDateTime(
                                            item.created_at
                                        )}
                                    </div>


                                    {/* HISTORY CHANGE */}

                                    <div
                                        className="history-change"
                                    >


                                        {/* STATUS */}

                                        {item.old_status &&
                                            item.new_status &&
                                            item.old_status !==
                                                item.new_status && (

                                            <span>

                                                Status:{" "}

                                                {
                                                    item.old_status
                                                }

                                                {" → "}

                                                {
                                                    item.new_status
                                                }

                                            </span>
                                        )}


                                        {/* TIME */}

                                        {item.old_scheduled_at &&
                                            item.new_scheduled_at &&
                                            item.old_scheduled_at !==
                                                item.new_scheduled_at && (

                                            <span>

                                                Time:{" "}

                                                {formatDateTime(
                                                    item.old_scheduled_at
                                                )}

                                                {" → "}

                                                {formatDateTime(
                                                    item.new_scheduled_at
                                                )}

                                            </span>
                                        )}

                                    </div>

                                </div>

                            </div>
                        ))}

                    </div>
                )}

            </div>

        </div>
    );
}
