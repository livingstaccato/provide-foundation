"""Comprehensive coverage tests for ConfigSchema class and schema validation."""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock
from attrs import define, field

from provide.foundation.config.base import BaseConfig
from provide.foundation.config.schema import (
    SchemaField,
    ConfigSchema,
    validate_schema,
    validate_port,
    validate_url,
    validate_email,
    validate_path,
    validate_version,
    validate_url_accessible,
)
from provide.foundation.errors import ConfigValidationError


class TestConfigSchemaComprehensive:
    """Comprehensive tests for ConfigSchema class."""

    def test_init_with_fields(self):
        """Test ConfigSchema initialization with fields."""
        field1 = SchemaField(name="field1", type=str)
        field2 = SchemaField(name="field2", type=int)

        schema = ConfigSchema([field1, field2])

        assert len(schema.fields) == 2
        assert "field1" in schema._field_map
        assert "field2" in schema._field_map
        assert schema._field_map["field1"] is field1
        assert schema._field_map["field2"] is field2

    def test_init_without_fields(self):
        """Test ConfigSchema initialization without fields."""
        schema = ConfigSchema()

        assert len(schema.fields) == 0
        assert len(schema._field_map) == 0

    def test_add_field(self):
        """Test adding field to schema."""
        schema = ConfigSchema()
        field_obj = SchemaField(name="new_field", type=str)

        schema.add_field(field_obj)

        assert len(schema.fields) == 1
        assert "new_field" in schema._field_map
        assert schema._field_map["new_field"] is field_obj

    @pytest.mark.asyncio
    async def test_validate_missing_required_field(self):
        """Test validation fails for missing required field."""
        required_field = SchemaField(name="required_field", required=True)
        schema = ConfigSchema([required_field])

        data = {}  # Missing required field

        with pytest.raises(ConfigValidationError, match="Required field missing"):
            await schema.validate(data)

    @pytest.mark.asyncio
    async def test_validate_all_required_fields_present(self):
        """Test validation passes when all required fields present."""
        required_field = SchemaField(name="required_field", required=True, type=str)
        optional_field = SchemaField(name="optional_field", required=False, type=int)
        schema = ConfigSchema([required_field, optional_field])

        data = {"required_field": "value"}  # Optional field missing but that's OK

        # Should not raise
        await schema.validate(data)

    @pytest.mark.asyncio
    async def test_validate_field_validation_error(self):
        """Test validation propagates field validation errors."""
        field_obj = SchemaField(name="test_field", type=int)
        schema = ConfigSchema([field_obj])

        data = {"test_field": "not_an_int"}

        with pytest.raises(ConfigValidationError, match="Expected type int"):
            await schema.validate(data)

    @pytest.mark.asyncio
    async def test_validate_unknown_fields_ignored(self):
        """Test validation ignores unknown fields."""
        field_obj = SchemaField(name="known_field", type=str)
        schema = ConfigSchema([field_obj])

        data = {"known_field": "value", "unknown_field": "ignored"}

        # Should not raise
        await schema.validate(data)

    def test_apply_defaults_no_defaults(self):
        """Test apply_defaults with no default values."""
        field_obj = SchemaField(name="test_field", type=str)
        schema = ConfigSchema([field_obj])

        data = {"test_field": "value"}
        result = schema.apply_defaults(data)

        assert result == data
        assert result is not data  # Should be a copy

    def test_apply_defaults_with_defaults(self):
        """Test apply_defaults applies missing default values."""
        field1 = SchemaField(name="field1", type=str, default="default1")
        field2 = SchemaField(name="field2", type=int, default=42)
        schema = ConfigSchema([field1, field2])

        data = {"field1": "custom_value"}  # field2 missing
        result = schema.apply_defaults(data)

        assert result == {"field1": "custom_value", "field2": 42}

    def test_apply_defaults_existing_values_preserved(self):
        """Test apply_defaults doesn't overwrite existing values."""
        field_obj = SchemaField(name="test_field", type=str, default="default_value")
        schema = ConfigSchema([field_obj])

        data = {"test_field": "existing_value"}
        result = schema.apply_defaults(data)

        assert result == {"test_field": "existing_value"}

    def test_apply_defaults_none_default_ignored(self):
        """Test apply_defaults ignores None default values."""
        field_obj = SchemaField(name="test_field", type=str, default=None)
        schema = ConfigSchema([field_obj])

        data = {}
        result = schema.apply_defaults(data)

        assert result == {}

    def test_filter_extra_fields(self):
        """Test filter_extra_fields removes unknown fields."""
        field1 = SchemaField(name="known_field1", type=str)
        field2 = SchemaField(name="known_field2", type=int)
        schema = ConfigSchema([field1, field2])

        data = {
            "known_field1": "value1",
            "known_field2": 42,
            "unknown_field": "should_be_removed",
            "another_unknown": "also_removed",
        }

        result = schema.filter_extra_fields(data)

        assert result == {"known_field1": "value1", "known_field2": 42}

    def test_filter_extra_fields_empty_schema(self):
        """Test filter_extra_fields with empty schema."""
        schema = ConfigSchema([])

        data = {"field1": "value1", "field2": "value2"}
        result = schema.filter_extra_fields(data)

        assert result == {}

    def test_from_config_class(self):
        """Test generating schema from config class."""

        @define
        class TestConfig(BaseConfig):
            name: str = field(default="test")
            count: int = field(default=0)
            enabled: bool = field(default=False)

        schema = ConfigSchema.from_config_class(TestConfig)

        # TestConfig has 3 fields + BaseConfig has internal fields like _source_map
        assert len(schema.fields) >= 3
        assert "name" in schema._field_map
        assert "count" in schema._field_map
        assert "enabled" in schema._field_map

        name_field = schema._field_map["name"]
        assert name_field.name == "name"
        assert name_field.type == str
        assert name_field.default == "test"

    def test_from_config_class_with_metadata(self):
        """Test generating schema with field metadata."""

        @define
        class TestConfig(BaseConfig):
            secret: str = field(
                default="", metadata={"description": "Secret value", "sensitive": True}
            )

        schema = ConfigSchema.from_config_class(TestConfig)

        secret_field = schema._field_map["secret"]
        assert secret_field.description == "Secret value"
        assert secret_field.sensitive is True

    def test_attr_to_schema_field_required_detection(self):
        """Test _attr_to_schema_field required field detection."""
        # Mock attribute with no default and no factory -> required
        attr = Mock()
        attr.name = "required_field"
        attr.default = None
        attr.factory = None
        attr.type = str
        attr.metadata = {}

        field_obj = ConfigSchema._attr_to_schema_field(attr)

        assert field_obj.required is True
        assert field_obj.name == "required_field"
        assert field_obj.type == str

    def test_attr_to_schema_field_optional_with_default(self):
        """Test _attr_to_schema_field optional field with default."""
        # Mock attribute with default -> not required
        attr = Mock()
        attr.name = "optional_field"
        attr.default = "default_value"
        attr.factory = None
        attr.type = str
        attr.metadata = {}

        field_obj = ConfigSchema._attr_to_schema_field(attr)

        assert field_obj.required is False
        assert field_obj.default == "default_value"

    def test_attr_to_schema_field_optional_with_factory(self):
        """Test _attr_to_schema_field optional field with factory."""
        # Mock attribute with factory -> not required
        attr = Mock()
        attr.name = "factory_field"
        attr.default = None
        attr.factory = lambda: []
        attr.type = list
        attr.metadata = {}

        field_obj = ConfigSchema._attr_to_schema_field(attr)

        assert field_obj.required is False

    def test_attr_to_schema_field_no_type_attribute(self):
        """Test _attr_to_schema_field with missing type attribute."""
        attr = Mock(spec=[])  # No type attribute
        attr.name = "no_type_field"
        attr.default = None
        attr.factory = None
        attr.metadata = {}

        field_obj = ConfigSchema._attr_to_schema_field(attr)

        assert field_obj.type is None


class TestValidateSchema:
    """Test the validate_schema function."""

    @pytest.mark.asyncio
    async def test_validate_schema_passes(self):
        """Test validate_schema with valid config."""

        @define
        class TestConfig(BaseConfig):
            name: str = field(default="test")

        config = TestConfig(name="valid_name")
        schema = ConfigSchema([SchemaField(name="name", type=str)])

        # Should not raise
        await validate_schema(config, schema)

    @pytest.mark.asyncio
    async def test_validate_schema_fails(self):
        """Test validate_schema with invalid config."""
        # Mock config that returns invalid data
        mock_config = Mock(spec=BaseConfig)
        mock_config.to_dict = Mock(return_value={"name": 123})  # Wrong type

        schema = ConfigSchema([SchemaField(name="name", type=str)])

        with pytest.raises(ConfigValidationError, match="Expected type str"):
            await validate_schema(mock_config, schema)