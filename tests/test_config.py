from datetime import UTC, datetime

import pytest
import yaml
from pydantic import ValidationError

from config import ClinicConfig, build_system_prompt, load_config


def test_sample_configuration_and_prompt():
    config = load_config()
    assert config.name == "Willow Dental & Medical"
    assert config.hours["saturday"] is None
    assert {service.id for service in config.services} == {
        "cleaning",
        "dental_exam",
        "general_consultation",
    }
    prompt = build_system_prompt(config, datetime(2026, 1, 5, 14, tzinfo=UTC))
    assert "2026-01-05 09:00 EST" in prompt
    assert "AI receptionist" in prompt
    assert "Never give medical advice" in prompt
    assert "pending staff" in prompt
    assert all(number in prompt for number in ["911", "000", "999"])
    assert config.address in prompt


@pytest.mark.parametrize(
    "change",
    [
        {"timezone": "Not/A_Timezone"},
        {"currency": "usd"},
        {"emergency_numbers": ["911"]},
        {"name": " "},
        {"hours": {"monday": None}},
        {"unexpected_option": True},
    ],
)
def test_invalid_config_is_rejected(change):
    data = load_config().model_dump()
    data.update(change)
    with pytest.raises(ValidationError):
        ClinicConfig.model_validate(data)


@pytest.mark.parametrize(
    "hours",
    [
        {"open": "9:00", "close": "17:00"},
        {"open": "17:00", "close": "09:00"},
        {"open": "25:00", "close": "26:00"},
    ],
)
def test_invalid_opening_hours(hours):
    data = load_config().model_dump()
    data["hours"]["monday"] = hours
    with pytest.raises(ValidationError):
        ClinicConfig.model_validate(data)


def test_duplicate_services_rejected():
    data = load_config().model_dump()
    data["services"].append(data["services"][0].copy())
    with pytest.raises(ValidationError, match="unique"):
        ClinicConfig.model_validate(data)


def test_yaml_can_be_customized(tmp_path):
    data = load_config().model_dump()
    data["name"] = "Demo Clinic"
    path = tmp_path / "clinic.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    assert load_config(path).name == "Demo Clinic"


def test_yaml_must_be_a_mapping(tmp_path):
    path = tmp_path / "clinic.yaml"
    path.write_text("- invalid\n", encoding="utf-8")
    with pytest.raises(ValueError, match="mapping"):
        load_config(path)


def test_prompt_requires_aware_clock():
    with pytest.raises(ValueError, match="timezone-aware"):
        build_system_prompt(load_config(), datetime(2026, 1, 5))
