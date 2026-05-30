import { useState, type FormEvent } from 'react';
import { createEvent } from '../services/eventApi';
import type { EventCreateResponse } from '../types/api';

interface EventFormProps {
  latitude: number | null;
  longitude: number | null;
  onEventCreated?: (response: EventCreateResponse) => void;
}

export default function EventForm({ latitude, longitude, onEventCreated }: EventFormProps) {
  const [title, setTitle] = useState('');
  const [message, setMessage] = useState('');
  const [severity, setSeverity] = useState<'info' | 'urgent'>('info');
  const [radius, setRadius] = useState(500);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState(true);

  const canSubmit =
    title.trim().length > 0 &&
    message.trim().length > 0 &&
    latitude != null &&
    longitude != null &&
    !submitting;

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;

    setSubmitting(true);
    setError(null);
    setSuccess(null);

    try {
      const result = await createEvent({
        title: title.trim(),
        message: message.trim(),
        latitude: latitude!,
        longitude: longitude!,
        severity,
        radius_meters: radius,
      });
      setSuccess(
        `Event posted! Delivered to ${result.delivered_count} nearby user(s).`,
      );
      setTitle('');
      setMessage('');
      setSeverity('info');
      setRadius(500);
      onEventCreated?.(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create event.');
    } finally {
      setSubmitting(false);
    }
  }

  const isDisabled = latitude == null || longitude == null;

  return (
    <div className={`event-form ${collapsed ? 'collapsed' : ''}`}>
      <button
        className="event-form-toggle"
        onClick={() => setCollapsed(!collapsed)}
        aria-label={collapsed ? 'Open event form' : 'Close event form'}
      >
        {collapsed ? '📢 Post Event' : '✕ Close'}
      </button>

      {!collapsed && (
        <form onSubmit={handleSubmit} className="event-form-body">
          {isDisabled && (
            <div className="event-form-warning">
              Waiting for your location...
            </div>
          )}

          <label>
            Title
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Library 3F has seats"
              maxLength={100}
              disabled={submitting}
            />
          </label>

          <label>
            Message
            <textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="Describe what's happening..."
              rows={3}
              maxLength={500}
              disabled={submitting}
            />
          </label>

          <div className="event-form-row">
            <label>
              Severity
              <select
                value={severity}
                onChange={(e) => setSeverity(e.target.value as 'info' | 'urgent')}
                disabled={submitting}
              >
                <option value="info">Info</option>
                <option value="urgent">Urgent</option>
              </select>
            </label>

            <label>
              Radius (m)
              <input
                type="number"
                value={radius}
                onChange={(e) => setRadius(Number(e.target.value))}
                min={50}
                max={3000}
                step={50}
                disabled={submitting}
              />
            </label>
          </div>

          {error && <div className="event-form-error">{error}</div>}
          {success && <div className="event-form-success">{success}</div>}

          <button
            type="submit"
            className="event-form-submit"
            disabled={!canSubmit}
          >
            {submitting ? 'Posting...' : 'Post Event'}
          </button>
        </form>
      )}
    </div>
  );
}
