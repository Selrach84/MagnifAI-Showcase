"""Template validator — schema and connector validation."""


class TemplateValidator:
    @staticmethod
    def validate_schema(config: dict, schema: dict) -> list[str]:
        errors: list[str] = []
        properties = schema.get("properties", {})
        for key, prop_schema in properties.items():
            if prop_schema.get("required", False) and key not in config:
                errors.append(f"Missing required field: {key}")
            if key in config:
                expected_type = prop_schema.get("type")
                value = config[key]
                if expected_type == "string" and not isinstance(value, str):
                    errors.append(f"Field '{key}' must be a string")
                elif expected_type == "number" and not isinstance(value, (int, float)):
                    errors.append(f"Field '{key}' must be a number")
                elif expected_type == "boolean" and not isinstance(value, bool):
                    errors.append(f"Field '{key}' must be a boolean")
        return errors

    @staticmethod
    def validate_connectors(
        required: list[str], available: list[str]
    ) -> list[str]:
        errors: list[str] = []
        for connector in required:
            if connector not in available:
                errors.append(f"Missing connector: {connector}")
        return errors
