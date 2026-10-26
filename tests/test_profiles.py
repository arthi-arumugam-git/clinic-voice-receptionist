"""Tests for clinic profile loading and UAE/Dubai configuration."""

from datetime import UTC, datetime

import pytest

from config import build_system_prompt, load_config


class TestDubaiProfile:
    @pytest.fixture
    def dubai_config(self):
        return load_config(profile="dubai")

    def test_dubai_timezone(self, dubai_config):
        assert dubai_config.timezone == "Asia/Dubai"

    def test_dubai_currency(self, dubai_config):
        assert dubai_config.currency == "AED"

    def test_dubai_emergency_numbers(self, dubai_config):
        assert "999" in dubai_config.emergency_numbers
        assert "998" in dubai_config.emergency_numbers
        assert "997" in dubai_config.emergency_numbers
        assert "911" in dubai_config.emergency_numbers
        assert "000" in dubai_config.emergency_numbers

    def test_dubai_clinic_name(self, dubai_config):
        assert "Al Noor" in dubai_config.name

    def test_dubai_services_in_aed(self, dubai_config):
        prices = [s.price for s in dubai_config.services]
        assert all(p > 100 for p in prices)

    def test_dubai_hours_include_friday_afternoon(self, dubai_config):
        friday_hours = dubai_config.hours["friday"]
        assert friday_hours is not None
        assert friday_hours.open == "14:00"

    def test_dubai_system_prompt(self, dubai_config):
        prompt = build_system_prompt(
            dubai_config,
            datetime(2027, 1, 4, 12, tzinfo=UTC),
        )
        assert "Asia/Dubai" in prompt
        assert "AED" in prompt
        assert "999" in prompt or "998" in prompt


class TestProfileLoading:
    def test_load_default_config(self):
        config = load_config()
        assert config.name == "Willow Dental & Medical"
        assert config.timezone == "America/New_York"
        assert config.currency == "USD"

    def test_load_profile_by_name(self):
        config = load_config(profile="dubai")
        assert config.timezone == "Asia/Dubai"

    def test_load_profile_via_env(self, monkeypatch):
        monkeypatch.setenv("CLINIC_PROFILE", "dubai")
        config = load_config()
        assert config.timezone == "Asia/Dubai"

    def test_explicit_path_overrides_profile(self, monkeypatch):
        monkeypatch.setenv("CLINIC_PROFILE", "dubai")
        config = load_config(path="clinic_config.yaml")
        assert config.timezone == "America/New_York"

    def test_env_path_overrides_profile(self, monkeypatch):
        monkeypatch.setenv("CLINIC_CONFIG_PATH", "clinic_config.yaml")
        monkeypatch.setenv("CLINIC_PROFILE", "dubai")
        config = load_config()
        assert config.timezone == "America/New_York"

    def test_nonexistent_profile_raises(self):
        with pytest.raises(FileNotFoundError):
            load_config(profile="nonexistent")


class TestCalendarEnabledPrompt:
    def test_prompt_without_calendar(self):
        config = load_config()
        prompt = build_system_prompt(config, calendar_enabled=False)
        assert "pending staff" in prompt.lower() or "pending confirmation" in prompt.lower()
        assert "local database" in prompt.lower()

    def test_prompt_with_calendar(self):
        config = load_config()
        prompt = build_system_prompt(config, calendar_enabled=True)
        assert "confirmed" in prompt.lower()
        assert "clinic calendar" in prompt.lower()


class TestEmergencyNumbersInPrompt:
    def test_us_emergency_numbers_in_default_prompt(self):
        config = load_config()
        prompt = build_system_prompt(config)
        assert "911" in prompt

    def test_uae_emergency_numbers_in_dubai_prompt(self):
        config = load_config(profile="dubai")
        prompt = build_system_prompt(config)
        assert "999" in prompt or "998" in prompt
