import pytest
from pydantic import ValidationError

from backend.shared.schemas import EventCreate, EventNotification, LocationUpdate


class TestLocationUpdate:
    def test_valid(self):
        obj = LocationUpdate(user_id="u-0001", latitude=25.0173, longitude=121.5397)
        assert obj.user_id == "u-0001"
        assert obj.latitude == 25.0173
        assert obj.longitude == 121.5397

    def test_invalid_latitude_above_90(self):
        with pytest.raises(ValidationError):
            LocationUpdate(user_id="u-0001", latitude=91, longitude=121.5397)

    def test_invalid_latitude_below_neg_90(self):
        with pytest.raises(ValidationError):
            LocationUpdate(user_id="u-0001", latitude=-91, longitude=121.5397)

    def test_invalid_longitude_above_180(self):
        with pytest.raises(ValidationError):
            LocationUpdate(user_id="u-0001", latitude=25.0, longitude=181)

    def test_invalid_longitude_below_neg_180(self):
        with pytest.raises(ValidationError):
            LocationUpdate(user_id="u-0001", latitude=25.0, longitude=-181)

    def test_missing_user_id(self):
        with pytest.raises(ValidationError):
            LocationUpdate(latitude=25.0, longitude=121.0)


class TestEventCreate:
    def test_valid(self):
        obj = EventCreate(
            title="Test event",
            message="Something happened",
            latitude=25.0173,
            longitude=121.5397,
        )
        assert obj.title == "Test event"
        assert obj.severity == "info"
        assert obj.radius_meters == 500

    def test_minimal_fields(self):
        """Only required fields; severity and radius default."""
        obj = EventCreate(
            title="Minimal",
            message="test",
            latitude=25.0,
            longitude=121.0,
        )
        assert obj.severity == "info"
        assert obj.radius_meters == 500

    def test_urgent_severity(self):
        obj = EventCreate(
            title="Urgent!",
            message="Emergency",
            latitude=25.0,
            longitude=121.0,
            severity="urgent",
        )
        assert obj.severity == "urgent"

    def test_custom_radius(self):
        obj = EventCreate(
            title="Custom radius",
            message="test",
            latitude=25.0,
            longitude=121.0,
            radius_meters=1000,
        )
        assert obj.radius_meters == 1000

    def test_invalid_radius_below_min(self):
        with pytest.raises(ValidationError):
            EventCreate(
                title="Too small",
                message="test",
                latitude=25.0,
                longitude=121.0,
                radius_meters=10,
            )

    def test_invalid_radius_above_max(self):
        with pytest.raises(ValidationError):
            EventCreate(
                title="Too large",
                message="test",
                latitude=25.0,
                longitude=121.0,
                radius_meters=5000,
            )

    def test_invalid_latitude(self):
        with pytest.raises(ValidationError):
            EventCreate(
                title="Bad lat",
                message="test",
                latitude=200,
                longitude=121.0,
            )


class TestEventNotification:
    def test_all_fields(self):
        obj = EventNotification(
            event_id="evt-001",
            title="Test",
            message="Hello",
            latitude=25.0,
            longitude=121.0,
            severity="info",
            distance_meters=150.0,
        )
        assert obj.distance_meters == 150.0

    def test_no_distance(self):
        obj = EventNotification(
            event_id="evt-002",
            title="Test",
            message="Hello",
            latitude=25.0,
            longitude=121.0,
            severity="urgent",
        )
        assert obj.distance_meters is None
