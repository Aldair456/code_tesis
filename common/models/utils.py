def uuid_string_properties(*field_names):
    def decorator(cls):
        for field_name in field_names:
            def make_property(fname):
                def getter(self):
                    value = getattr(self, fname)
                    return str(value) if value is not None else None
                return property(getter)
            setattr(cls, f"{field_name}_str", make_property(field_name))
        return cls
    return decorator