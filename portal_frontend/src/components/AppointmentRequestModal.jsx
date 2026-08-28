import { useEffect, useState } from "react";

import {
    createAppointment,
    getProviders,
} from "../api/api";


function AppointmentRequestModal({
    patient,
    onClose,
    onSuccess,
}) {
    const [providers, setProviders] = useState([]);

    const [form, setForm] = useState({
        provider_id: "",
        scheduled_at: "",
        duration_minutes: 60,
        appointment_type: "consultation",
        reason: "",
    });

    const [loading, setLoading] = useState(false);
    const [loadingProviders, setLoadingProviders] =
        useState(true);

    const [error, setError] = useState("");
    const [fieldErrors, setFieldErrors] = useState({});


    useEffect(() => {
        async function loadProviders() {
            try {
                const data = await getProviders();

                setProviders(
                    Array.isArray(data)
                        ? data
                        : data.results || []
                );
            } catch (err) {
                console.error(err);

                setError(
                    "Unable to load healthcare providers."
                );
            } finally {
                setLoadingProviders(false);
            }
        }

        loadProviders();
    }, []);


    function handleChange(event) {
        const {
            name,
            value,
        } = event.target;

        setForm((previous) => ({
            ...previous,
            [name]: value,
        }));

        setFieldErrors((previous) => ({
            ...previous,
            [name]: undefined,
        }));

        setError("");
    }


    function validate() {
        const errors = {};

        if (!form.provider_id) {
            errors.provider_id =
                "Please select a provider.";
        }

        if (!form.scheduled_at) {
            errors.scheduled_at =
                "Please select a date and time.";
        } else {
            const selectedDate =
                new Date(form.scheduled_at);

            if (
                Number.isNaN(
                    selectedDate.getTime()
                )
            ) {
                errors.scheduled_at =
                    "Please enter a valid date and time.";
            } else if (
                selectedDate <= new Date()
            ) {
                errors.scheduled_at =
                    "Appointment must be in the future.";
            }
        }

        if (
            !form.reason.trim()
        ) {
            errors.reason =
                "Please provide a reason for the visit.";
        }

        return errors;
    }


    async function handleSubmit(event) {
        event.preventDefault();

        const errors = validate();

        if (
            Object.keys(errors).length > 0
        ) {
            setFieldErrors(errors);
            return;
        }


        try {
            setLoading(true);
            setError("");
            setFieldErrors({});


            /*
             * Convert the HTML datetime-local value
             * into an ISO datetime understood by DRF.
             */
            const scheduledAt =
                new Date(
                    form.scheduled_at
                ).toISOString();


            const payload = {
                patient_id: patient.id,

                provider_id:
                    Number(form.provider_id),

                scheduled_at:
                    scheduledAt,

                duration_minutes:
                    Number(
                        form.duration_minutes
                    ),

                appointment_type:
                    form.appointment_type,

                reason:
                    form.reason.trim(),
            };


            await createAppointment(payload);


            onSuccess();

        } catch (err) {
            console.error(err);

            /*
             * DRF normally returns:
             *
             * {
             *   "scheduled_at": ["..."],
             *   "provider": ["..."]
             * }
             *
             * We surface those validation errors
             * directly to the user.
             */

            if (
                err.data &&
                typeof err.data === "object"
            ) {
                setFieldErrors(err.data);
            }

            setError(
                "We couldn't submit the appointment request. Please review the information and try again."
            );

        } finally {
            setLoading(false);
        }
    }


    return (
        <div
            className="modal-backdrop"
            onMouseDown={(event) => {
                if (
                    event.target ===
                    event.currentTarget
                ) {
                    onClose();
                }
            }}
        >

            <div className="appointment-modal">

                {/* HEADER */}

                <div className="modal-header">

                    <div>

                        <span className="eyebrow">
                            APPOINTMENT REQUEST
                        </span>

                        <h2>
                            Request an appointment
                        </h2>

                        <p>
                            Tell us when you'd prefer
                            to see your provider.
                        </p>

                    </div>


                    <button
                        className="modal-close"
                        onClick={onClose}
                        type="button"
                        aria-label="Close"
                    >
                        ×
                    </button>

                </div>


                {/* ERROR */}

                {error && (
                    <div className="form-error-banner">
                        {error}
                    </div>
                )}


                {/* FORM */}

                <form
                    className="appointment-form"
                    onSubmit={handleSubmit}
                >

                    {/* PROVIDER */}

                    <div className="form-group">

                        <label htmlFor="provider_id">
                            Healthcare provider
                        </label>

                        <select
                            id="provider_id"
                            name="provider_id"
                            value={
                                form.provider_id
                            }
                            onChange={
                                handleChange
                            }
                            disabled={
                                loadingProviders ||
                                loading
                            }
                        >

                            <option value="">
                                {loadingProviders
                                    ? "Loading providers..."
                                    : "Select a provider"}
                            </option>

                            {providers.map(
                                (provider) => (
                                    <option
                                        key={
                                            provider.id
                                        }
                                        value={
                                            provider.id
                                        }
                                    >
                                        {
                                            provider.name
                                        }

                                        {provider.specialty
                                            ? ` — ${provider.specialty}`
                                            : ""}
                                    </option>
                                )
                            )}

                        </select>


                        {fieldErrors.provider_id && (
                            <span className="field-error">
                                {
                                    fieldErrors
                                        .provider_id[0]
                                }
                            </span>
                        )}

                    </div>


                    {/* DATE */}

                    <div className="form-row">

                        <div className="form-group">

                            <label htmlFor="scheduled_at">
                                Preferred date & time
                            </label>

                            <input
                                id="scheduled_at"
                                name="scheduled_at"
                                type="datetime-local"
                                value={
                                    form.scheduled_at
                                }
                                onChange={
                                    handleChange
                                }
                                disabled={
                                    loading
                                }
                            />


                            {fieldErrors.scheduled_at && (
                                <span className="field-error">
                                    {
                                        fieldErrors
                                            .scheduled_at[0]
                                    }
                                </span>
                            )}

                        </div>


                        {/* DURATION */}

                        <div className="form-group">

                            <label htmlFor="duration_minutes">
                                Duration
                            </label>

                            <select
                                id="duration_minutes"
                                name="duration_minutes"
                                value={
                                    form.duration_minutes
                                }
                                onChange={
                                    handleChange
                                }
                                disabled={
                                    loading
                                }
                            >

                                <option value="30">
                                    30 minutes
                                </option>

                                <option value="45">
                                    45 minutes
                                </option>

                                <option value="60">
                                    60 minutes
                                </option>

                                <option value="90">
                                    90 minutes
                                </option>

                            </select>

                        </div>

                    </div>


                    {/* TYPE */}

                    <div className="form-group">

                        <label htmlFor="appointment_type">
                            Appointment type
                        </label>

                        <select
                            id="appointment_type"
                            name="appointment_type"
                            value={
                                form.appointment_type
                            }
                            onChange={
                                handleChange
                            }
                            disabled={
                                loading
                            }
                        >

                            <option value="consultation">
                                Consultation
                            </option>

                            <option value="follow_up">
                                Follow-up
                            </option>

                            <option value="therapy">
                                Therapy
                            </option>

                            <option value="other">
                                Other
                            </option>

                        </select>

                    </div>


                    {/* REASON */}

                    <div className="form-group">

                        <label htmlFor="reason">
                            Reason for visit
                        </label>

                        <textarea
                            id="reason"
                            name="reason"
                            rows="4"
                            placeholder="Briefly describe what you would like to discuss..."
                            value={
                                form.reason
                            }
                            onChange={
                                handleChange
                            }
                            disabled={
                                loading
                            }
                        />


                        {fieldErrors.reason && (
                            <span className="field-error">
                                {
                                    fieldErrors
                                        .reason[0]
                                }
                            </span>
                        )}

                    </div>


                    {/* INFORMATION */}

                    <div className="request-info">

                        <span className="info-icon">
                            i
                        </span>

                        <p>
                            This request will be sent
                            to your provider for
                            confirmation. Your appointment
                            will remain <strong>pending</strong>
                            until confirmed.

                        </p>

                    </div>


                    {/* ACTIONS */}

                    <div className="modal-actions">

                        <button
                            type="button"
                            className="secondary-button"
                            onClick={onClose}
                            disabled={loading}
                        >
                            Cancel
                        </button>


                        <button
                            type="submit"
                            className="primary-button"
                            disabled={
                                loading ||
                                loadingProviders
                            }
                        >

                            {loading
                                ? "Submitting..."
                                : "Submit request"}

                        </button>

                    </div>

                </form>

            </div>

        </div>
    );
}


export default AppointmentRequestModal;