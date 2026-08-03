from __future__ import annotations

import pytest
from pydantic import ValidationError

from tests.conftest import load_module


schemas = load_module("backend_shared_schemas", "backend/shared/schemas.py")


def test_location_update_valid() -> None:
    payload = schemas.LocationUpdate(user_id="u-0001", latitude=25.0173, longitude=121.5397)

    assert payload.user_id == "u-0001"
    assert payload.latitude == 25.0173
    assert payload.longitude == 121.5397


def test_location_update_invalid_latitude() -> None:
    with pytest.raises(ValidationError):
        schemas.LocationUpdate(user_id="u-0001", latitude=91, longitude=121.5397)


def test_location_update_invalid_longitude() -> None:
    with pytest.raises(ValidationError):
        schemas.LocationUpdate(user_id="u-0001", latitude=25.0173, longitude=181)


def test_event_create_valid() -> None:
    payload = schemas.EventCreate(
        title="Library 3F has seats",
        message="About 10 seats near the windows.",
        latitude=25.0173,
        longitude=121.5397,
    )

    assert payload.severity == "info"
    assert payload.radius_meters == 500


def test_event_create_invalid_radius() -> None:
    with pytest.raises(ValidationError):
        schemas.EventCreate(
            title="Library 3F has seats",
            message="About 10 seats near the windows.",
            latitude=25.0173,
            longitude=121.5397,
            radius_meters=20,
        )


def test_event_notification_all_fields() -> None:
    payload = schemas.EventNotification(
        event_id="uuid",
        title="Urgent notice",
        message="Road blocked near library",
        latitude=25.0173,
        longitude=121.5397,
        severity="urgent",
        distance_meters=120.0,
    )

    assert payload.distance_meters == 120.0
    assert payload.severity == "urgent"


def test_event_notification_no_distance() -> None:
    payload = schemas.EventNotification(
        event_id="uuid",
        title="Urgent notice",
        message="Road blocked near library",
        latitude=25.0173,
        longitude=121.5397,
        severity="urgent",
    )

    assert payload.distance_meters is None
