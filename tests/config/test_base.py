"""Tests for base configuration classes."""
from __future__ import annotations

import pytest
from attrs import define

from provide.foundation.config.base import (
    BaseConfig,
    ConfigError,
    ConfigValidationError,
    field,
)
from provide.foundation.config.types import ConfigSource


@define
class SampleConfig(BaseConfig):
    """Sample configuration for testing."""
    
    name: str = field(default="test")
    port: int = field(default=8080)
    debug: bool = field(default=False)
    tags: list[str] = field(factory=list)
    metadata: dict[str, str] = field(factory=dict)
    secret: str = field(default="", sensitive=True)

    def __attrs_post_init__(self):
        super().__attrs_post_init__()


class TestBaseConfig:
    """Test BaseConfig functionality."""
    
    def test_create_config(self):
        """Test creating a configuration instance."""
        config = SampleConfig()
        assert config.name == "test"
        assert config.port == 8080
        assert config.debug is False
        assert config.tags == []
        assert config.metadata == {}
    
    def test_create_config_with_values(self):
        """Test creating configuration with custom values."""
        config = SampleConfig(
            name="production",
            port=9000,
            debug=True,
            tags=["api", "v2"],
            metadata={"version": "1.0"}
        )
        assert config.name == "production"
        assert config.port == 9000
        assert config.debug is True
        assert config.tags == ["api", "v2"]
        assert config.metadata == {"version": "1.0"}
    
    def test_to_dict(self):
        """Test converting configuration to dictionary."""
        config = SampleConfig(name="test", port=8080)
        result = config.to_dict()
        
        assert result["name"] == "test"
        assert result["port"] == 8080
        assert result["debug"] is False
        assert "secret" not in result  # Sensitive field excluded by default
    
    def test_to_dict_with_sensitive(self):
        """Test converting configuration with sensitive fields."""
        config = SampleConfig(secret="password123")
        
        # Without sensitive
        result = config.to_dict(include_sensitive=False)
        assert "secret" not in result
        
        # With sensitive
        result = config.to_dict(include_sensitive=True)
        assert result["secret"] == "password123"
    
    def test_from_dict(self):
        """Test creating configuration from dictionary."""
        data = {
            "name": "from_dict",
            "port": 3000,
            "debug": True,
            "tags": ["test"],
            "extra_field": "ignored"  # Should be ignored
        }
        
        config = SampleConfig.from_dict(data)
        assert config.name == "from_dict"
        assert config.port == 3000
        assert config.debug is True
        assert config.tags == ["test"]
        assert not hasattr(config, "extra_field")
    
    def test_update(self):
        """Test updating configuration."""
        config = SampleConfig(name="original")
        
        config.update({"name": "updated", "port": 5000})
        assert config.name == "updated"
        assert config.port == 5000
    
    def test_update_with_source_precedence(self):
        """Test update respects source precedence."""
        config = SampleConfig()
        
        # Set initial value with FILE source
        config.update({"name": "from_file"}, ConfigSource.FILE)
        assert config.name == "from_file"
        
        # Try to update with lower precedence (should be ignored)
        config.update({"name": "from_default"}, ConfigSource.DEFAULT)
        assert config.name == "from_file"
        
        # Update with higher precedence (should work)
        config.update({"name": "from_runtime"}, ConfigSource.RUNTIME)
        assert config.name == "from_runtime"
    
    def test_get_source(self):
        """Test getting configuration source."""
        config = SampleConfig()
        
        # Default source
        assert config.get_source("name") is None
        
        # After update
        config.update({"name": "updated"}, ConfigSource.ENV)
        assert config.get_source("name") == ConfigSource.ENV
    
    def test_reset_to_defaults(self):
        """Test resetting to default values."""
        config = SampleConfig(name="modified", port=9999)
        config.reset_to_defaults()
        
        assert config.name == "test"
        assert config.port == 8080
        assert config._source_map == {}
    
    def test_clone(self):
        """Test cloning configuration."""
        config = SampleConfig(name="original", tags=["a", "b"])
        clone = config.clone()
        
        # Verify clone has same values
        assert clone.name == "original"
        assert clone.tags == ["a", "b"]
        
        # Verify they're independent
        clone.name = "cloned"
        clone.tags.append("c")
        
        assert config.name == "original"
        assert config.tags == ["a", "b"]
    
    def test_diff(self):
        """Test comparing configurations."""
        config1 = SampleConfig(name="config1", port=8080)
        config2 = SampleConfig(name="config2", port=8080, debug=True)
        
        diff = config1.diff(config2)
        
        assert "name" in diff
        assert diff["name"] == ("config1", "config2")
        assert "debug" in diff
        assert diff["debug"] == (False, True)
        assert "port" not in diff  # Same value
    
    def test_diff_type_error(self):
        """Test diff with incompatible types."""
        config = SampleConfig()
        other = BaseConfig()
        
        with pytest.raises(TypeError):
            config.diff(other)
    
    def test_repr_hides_sensitive(self):
        """Test string representation hides sensitive fields."""
        config = SampleConfig(name="test", secret="password123")
        repr_str = repr(config)
        
        assert "name='test'" in repr_str
        assert "secret='***SENSITIVE***'" in repr_str
        assert "password123" not in repr_str


class TestConfigField:
    """Test enhanced field functionality."""
    
    def test_field_with_description(self):
        """Test field with description metadata."""
        @define
        class ConfigWithDescription(BaseConfig):
            value: str = field(description="A test value")
        
        # Access metadata through attrs
        from attrs import fields
        field_obj = fields(ConfigWithDescription)[0]
        assert field_obj.metadata["description"] == "A test value"
    
    def test_field_with_env_metadata(self):
        """Test field with environment variable metadata."""
        @define
        class ConfigWithEnv(BaseConfig):
            value: str = field(env_var="MY_VALUE", env_prefix="APP")
        
        from attrs import fields
        field_obj = fields(ConfigWithEnv)[0]
        assert field_obj.metadata["env_var"] == "MY_VALUE"
        assert field_obj.metadata["env_prefix"] == "APP"


class TestConfigValidationError:
    """Test ConfigValidationError."""
    
    def test_validation_error(self):
        """Test creating validation error."""
        error = ConfigValidationError("test_field", 123, "Invalid value")
        
        assert error.field_name == "test_field"
        assert error.value == 123
        assert "test_field" in str(error)
        assert "Invalid value" in str(error)