"""Tests for Foundation serialization utilities."""

import json
from unittest.mock import patch

import pytest

from provide.foundation.errors import ValidationError
from provide.foundation.serialization import provide_dumps, provide_loads


class TestProvideDumps:
    """Test provide_dumps function."""

    def test_provide_dumps_basic_dict(self):
        """Test provide_dumps with basic dictionary."""
        data = {"key": "value", "number": 42}
        result = provide_dumps(data)
        assert isinstance(result, str)
        # Parse back to verify structure
        parsed = json.loads(result)
        assert parsed == data

    def test_provide_dumps_basic_list(self):
        """Test provide_dumps with basic list."""
        data = [1, 2, "three", None, True]
        result = provide_dumps(data)
        assert isinstance(result, str)
        parsed = json.loads(result)
        assert parsed == data

    def test_provide_dumps_nested_structure(self):
        """Test provide_dumps with nested data structures."""
        data = {
            "users": [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}],
            "metadata": {"version": "1.0", "created": None},
        }
        result = provide_dumps(data)
        parsed = json.loads(result)
        assert parsed == data

    def test_provide_dumps_with_indent(self):
        """Test provide_dumps with indentation."""
        data = {"a": 1, "b": {"c": 2}}
        result = provide_dumps(data, indent=2)

        # Check that result is properly formatted
        lines = result.split("\n")
        assert len(lines) > 1  # Multi-line output
        assert "  " in result  # Contains indentation

    def test_provide_dumps_with_sort_keys(self):
        """Test provide_dumps with sorted keys."""
        data = {"zebra": 1, "apple": 2, "banana": 3}
        result = provide_dumps(data, sort_keys=True)

        # Keys should be in alphabetical order
        expected = '{"apple": 2, "banana": 3, "zebra": 1}'
        assert result == expected

    def test_provide_dumps_with_ensure_ascii_false(self):
        """Test provide_dumps with ensure_ascii=False."""
        data = {"message": "こんにちは", "emoji": "🎉"}
        result = provide_dumps(data, ensure_ascii=False)

        # Non-ASCII characters should be preserved
        assert "こんにちは" in result
        assert "🎉" in result

    def test_provide_dumps_with_ensure_ascii_true(self):
        """Test provide_dumps with ensure_ascii=True."""
        data = {"message": "こんにちは"}
        result = provide_dumps(data, ensure_ascii=True)

        # Non-ASCII characters should be escaped
        assert "こんにちは" not in result
        assert "\\u" in result  # Unicode escape sequences

    def test_provide_dumps_primitive_types(self):
        """Test provide_dumps with primitive types."""
        test_cases = [
            (None, "null"),
            (True, "true"),
            (False, "false"),
            (42, "42"),
            (3.14, "3.14"),
            ("hello", '"hello"'),
        ]

        for value, expected in test_cases:
            result = provide_dumps(value)
            assert result == expected

    def test_provide_dumps_empty_structures(self):
        """Test provide_dumps with empty structures."""
        assert provide_dumps({}) == "{}"
        assert provide_dumps([]) == "[]"
        assert provide_dumps("") == '""'

    def test_provide_dumps_non_serializable_raises_error(self):
        """Test provide_dumps raises ValidationError for non-serializable objects."""

        class NonSerializable:
            pass

        with pytest.raises(ValidationError, match="Cannot serialize object to JSON"):
            provide_dumps(NonSerializable())

    def test_provide_dumps_circular_reference_raises_error(self):
        """Test provide_dumps raises ValidationError for circular references."""
        data = {}
        data["self"] = data

        with pytest.raises(ValidationError, match="Cannot serialize object to JSON"):
            provide_dumps(data)

    @patch("provide.foundation.serialization.core.json")
    def test_provide_dumps_uses_json_module(self, mock_json):
        """Test provide_dumps calls json.dumps()."""
        mock_json.dumps.return_value = '{"test": "value"}'

        data = {"test": "value"}
        result = provide_dumps(data, indent=2, sort_keys=True)

        assert result == '{"test": "value"}'
        mock_json.dumps.assert_called_once_with(
            data, ensure_ascii=False, indent=2, sort_keys=True
        )

    def test_provide_dumps_complex_numbers_raises_error(self):
        """Test provide_dumps raises error for complex numbers."""
        with pytest.raises(ValidationError):
            provide_dumps(3 + 4j)

    def test_provide_dumps_set_raises_error(self):
        """Test provide_dumps raises error for sets."""
        with pytest.raises(ValidationError):
            provide_dumps({1, 2, 3})


class TestProvideLoads:
    """Test provide_loads function."""

    def test_provide_loads_basic_dict(self):
        """Test provide_loads with basic dictionary JSON."""
        json_str = '{"key": "value", "number": 42}'
        result = provide_loads(json_str)
        expected = {"key": "value", "number": 42}
        assert result == expected

    def test_provide_loads_basic_list(self):
        """Test provide_loads with basic list JSON."""
        json_str = '[1, 2, "three", null, true, false]'
        result = provide_loads(json_str)
        expected = [1, 2, "three", None, True, False]
        assert result == expected

    def test_provide_loads_nested_structure(self):
        """Test provide_loads with nested JSON structure."""
        json_str = """
        {
            "users": [
                {"name": "Alice", "age": 30},
                {"name": "Bob", "age": 25}
            ],
            "metadata": {
                "version": "1.0",
                "created": null
            }
        }
        """
        result = provide_loads(json_str)
        expected = {
            "users": [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}],
            "metadata": {"version": "1.0", "created": None},
        }
        assert result == expected

    def test_provide_loads_primitive_types(self):
        """Test provide_loads with primitive JSON types."""
        test_cases = [
            ("null", None),
            ("true", True),
            ("false", False),
            ("42", 42),
            ("3.14", 3.14),
            ('"hello"', "hello"),
        ]

        for json_str, expected in test_cases:
            result = provide_loads(json_str)
            assert result == expected

    def test_provide_loads_empty_structures(self):
        """Test provide_loads with empty JSON structures."""
        assert provide_loads("{}") == {}
        assert provide_loads("[]") == []
        assert provide_loads('""') == ""

    def test_provide_loads_unicode_characters(self):
        """Test provide_loads with Unicode characters."""
        json_str = '{"message": "こんにちは", "emoji": "🎉"}'
        result = provide_loads(json_str)
        expected = {"message": "こんにちは", "emoji": "🎉"}
        assert result == expected

    def test_provide_loads_escaped_unicode(self):
        """Test provide_loads with escaped Unicode characters."""
        json_str = r'{"message": "\u3053\u3093\u306b\u3061\u306f"}'
        result = provide_loads(json_str)
        expected = {"message": "こんにちは"}
        assert result == expected

    def test_provide_loads_invalid_json_raises_error(self):
        """Test provide_loads raises ValidationError for invalid JSON."""
        invalid_json_cases = [
            '{"key": value}',  # Unquoted value
            '{"key": "value",}',  # Trailing comma
            '{key: "value"}',  # Unquoted key
            '{"incomplete": "object"',  # Missing closing brace
            "[1, 2, 3,]",  # Trailing comma in array
            "undefined",  # Invalid literal
            '{"duplicate": 1, "duplicate": 2}',  # Duplicate keys (valid JSON but worth testing)
        ]

        for invalid_json in invalid_json_cases[:-1]:  # Skip duplicate keys test
            with pytest.raises(ValidationError, match="Invalid JSON string"):
                provide_loads(invalid_json)

    def test_provide_loads_empty_string_raises_error(self):
        """Test provide_loads raises ValidationError for empty string."""
        with pytest.raises(ValidationError, match="Invalid JSON string"):
            provide_loads("")

    def test_provide_loads_non_string_raises_error(self):
        """Test provide_loads raises ValidationError for non-string input."""
        non_string_inputs = [None, 123, [], {}, True]

        for invalid_input in non_string_inputs:
            with pytest.raises(ValidationError, match="Input must be a string"):
                provide_loads(invalid_input)

    def test_provide_loads_whitespace_only_raises_error(self):
        """Test provide_loads raises ValidationError for whitespace-only string."""
        with pytest.raises(ValidationError, match="Invalid JSON string"):
            provide_loads("   ")

    @patch("provide.foundation.serialization.core.json")
    def test_provide_loads_uses_json_module(self, mock_json):
        """Test provide_loads calls json.loads()."""
        mock_json.loads.return_value = {"test": "value"}

        json_str = '{"test": "value"}'
        result = provide_loads(json_str)

        assert result == {"test": "value"}
        mock_json.loads.assert_called_once_with(json_str)

    def test_provide_loads_large_numbers(self):
        """Test provide_loads with large numbers."""
        json_str = (
            '{"small": 1, "large": 9007199254740991, "float": 1.7976931348623157e+308}'
        )
        result = provide_loads(json_str)
        assert result["small"] == 1
        assert result["large"] == 9007199254740991
        assert result["float"] == 1.7976931348623157e308

    def test_provide_loads_special_float_values(self):
        """Test provide_loads handles special float values in JSON."""
        # Python's json.loads actually accepts these values
        test_cases = [
            ("Infinity", float("inf")),
            ("-Infinity", float("-inf")),
            ("NaN", float("nan")),
        ]

        for json_str, expected in test_cases:
            result = provide_loads(json_str)
            if expected != expected:  # Check for NaN
                assert result != result  # NaN != NaN
            else:
                assert result == expected


class TestSerializationRoundTrip:
    """Test round-trip serialization/deserialization."""

    def test_roundtrip_basic_data(self):
        """Test round-trip with basic data types."""
        test_data = {
            "string": "hello",
            "number": 42,
            "float": 3.14,
            "boolean": True,
            "null": None,
            "list": [1, 2, 3],
            "nested": {"key": "value"},
        }

        serialized = provide_dumps(test_data)
        deserialized = provide_loads(serialized)

        assert deserialized == test_data

    def test_roundtrip_with_formatting(self):
        """Test round-trip preserves data with formatting options."""
        test_data = {"z": 1, "a": 2, "m": 3}

        # Serialize with formatting
        serialized = provide_dumps(test_data, indent=2, sort_keys=True)

        # Deserialize should still give original data
        deserialized = provide_loads(serialized)
        assert deserialized == test_data

    def test_roundtrip_unicode_data(self):
        """Test round-trip with Unicode data."""
        test_data = {
            "japanese": "こんにちは",
            "emoji": "🎉🚀💖",
            "symbols": "∑∆∞",
            "mixed": "Hello 世界 🌍",
        }

        serialized = provide_dumps(test_data)
        deserialized = provide_loads(serialized)

        assert deserialized == test_data

    def test_roundtrip_edge_cases(self):
        """Test round-trip with edge case data."""
        test_cases = [
            {},  # Empty dict
            [],  # Empty list
            "",  # Empty string
            0,  # Zero
            False,  # False boolean
            None,  # Null value
        ]

        for test_data in test_cases:
            serialized = provide_dumps(test_data)
            deserialized = provide_loads(serialized)
            assert deserialized == test_data


class TestSerializationIntegration:
    """Integration tests for serialization utilities."""

    def test_serialization_with_foundation_objects(self):
        """Test serialization works with Foundation-compatible objects."""
        # Test data that might come from Foundation usage
        log_data = {
            "timestamp": "2023-01-01T12:00:00Z",
            "level": "info",
            "message": "Test message",
            "context": {
                "user_id": 12345,
                "session_id": "abc-def-123",
                "metadata": None,
            },
            "tags": ["test", "foundation"],
        }

        serialized = provide_dumps(log_data, sort_keys=True, indent=2)
        deserialized = provide_loads(serialized)

        assert deserialized == log_data
        # Verify it's properly formatted
        assert "\n" in serialized
        assert '"context"' in serialized

    def test_serialization_performance_basic(self):
        """Test basic performance characteristics."""
        # Create reasonably sized test data
        test_data = {
            f"key_{i}": {
                "value": f"value_{i}",
                "number": i,
                "nested": [i, i * 2, i * 3],
            }
            for i in range(100)
        }

        # Should complete without timeout
        serialized = provide_dumps(test_data)
        deserialized = provide_loads(serialized)

        assert deserialized == test_data
        assert isinstance(serialized, str)
        assert len(serialized) > 1000  # Sanity check

    def test_error_message_quality(self):
        """Test that error messages are helpful."""
        # Test non-serializable object
        try:
            provide_dumps(object())
        except ValidationError as e:
            assert "Cannot serialize object to JSON" in str(e)
            assert "object" in str(e).lower()

        # Test invalid JSON
        try:
            provide_loads('{"invalid": json}')
        except ValidationError as e:
            assert "Invalid JSON string" in str(e)

        # Test non-string input
        try:
            provide_loads(123)
        except ValidationError as e:
            assert "Input must be a string" in str(e)

    def test_serialization_preserves_types(self):
        """Test that serialization preserves expected Python types."""
        original_data = {
            "int": 42,
            "float": 3.14,
            "bool_true": True,
            "bool_false": False,
            "none": None,
            "string": "test",
            "list": [1, 2, 3],
            "dict": {"nested": "value"},
        }

        serialized = provide_dumps(original_data)
        result = provide_loads(serialized)

        # Check types are preserved
        assert isinstance(result["int"], int)
        assert isinstance(result["float"], float)
        assert isinstance(result["bool_true"], bool)
        assert isinstance(result["bool_false"], bool)
        assert result["none"] is None
        assert isinstance(result["string"], str)
        assert isinstance(result["list"], list)
        assert isinstance(result["dict"], dict)
