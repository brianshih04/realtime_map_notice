import type { MapEvent } from './MapView';

interface EventListProps {
  events: MapEvent[];
  onSelectEvent?: (evt: MapEvent) => void;
}

export default function EventList({ events, onSelectEvent }: EventListProps) {
  if (events.length === 0) {
    return (
      <div className="event-list empty">
        <p className="event-list-empty-text">No nearby events</p>
      </div>
    );
  }

  return (
    <div className="event-list">
      <h3 className="event-list-title">Nearby Events ({events.length})</h3>
      <ul className="event-list-items">
        {events.map((evt) => (
          <li
            key={evt.event_id}
            className={`event-list-item severity-${evt.severity}`}
            onClick={() => onSelectEvent?.(evt)}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') onSelectEvent?.(evt);
            }}
          >
            <div className="event-list-item-header">
              <span className={`severity-badge ${evt.severity}`}>
                {evt.severity === 'urgent' ? '🔴' : '🟡'}
              </span>
              <strong>{evt.title}</strong>
            </div>
            {evt.distance_meters != null && (
              <span className="event-list-distance">
                {Math.round(evt.distance_meters)}m away
              </span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
