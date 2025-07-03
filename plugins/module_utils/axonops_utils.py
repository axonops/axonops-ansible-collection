from ansible.module_utils.basic import env_fallback


def make_module_args(module_args: dict) -> dict:
    return {**base_module_args(), **module_args}


def base_module_args() -> dict:
    return {
        "base_url": {"type": 'str', "required": False, "fallback": (env_fallback, ['AXONOPS_URL'])},
        "org": {"type": 'str', "required": True, "fallback": (env_fallback, ['AXONOPS_ORG'])},
        "cluster": {"type": 'str', "required": False, "fallback": (env_fallback, ['AXONOPS_CLUSTER'])},
        "auth_token": {"type": 'str', "required": False, "fallback": (env_fallback, ['AXONOPS_TOKEN'])},
        "username": {"type": 'str', "required": False, "fallback": (env_fallback, ['AXONOPS_USERNAME'])},
        "password": {"type": 'str', "required": False, "fallback": (env_fallback, ['AXONOPS_PASSWORD'])},
        "cluster_type": {"type": 'str', "required": False, "fallback": (env_fallback, ['AXONOPS_CLUSTER_TYPE']),
                         'default': 'cassandra'},
        "api_token": {"type": 'str', "required": False, "fallback": (env_fallback, ['AXONOPS_API_TOKEN'])},
        "override_saas": {"type": 'bool', "required": False, "fallback": (env_fallback, ['AXONOPS_OVERRIDE_SAAS']),
                          'default': False},

    }


def dicts_are_different(a: dict, b: dict) -> bool:
    """
    Check if the dictionaries a and b are different
    """
    # check the keys
    if set(a.keys()) != set(b.keys()):
        return True  # If keys are different, dictionaries are different

    # check the content of the keys
    for key_a, value_a in a.items():
        value_b = b.get(key_a)
        if value_a != value_b:
            return True  # If any value is different, dictionaries are different

    return False  # Dictionaries are identical


def find_by_field(dicts, field, value):
    """
    Find items in a list of dicts by searching a particular field for a value.
    - Returns None if no matching items are found.
    - Returns a single item if only one match is found.
    - Returns a list of items if multiple matches are found.
    """
    matches = [d for d in dicts or [] if d.get(field) == value]

    if not matches:
        return None
    elif len(matches) == 1:
        return matches[0]
    else:
        return matches


def string_to_bool(value):
    return value is not None and value.lower() in ('true', 't', '1', 'yes', 'y')


def bool_to_string(value):
    return 'true' if value else 'false'


def string_or_none(value):
    if value is None or value.lower() in ('none', 'null'):
        return None
    return value


def normalize_numbers(d):
    """
    Recursively normalizes numbers and lists in a dictionary:
    - Converts all integers and floats to floats to ensure consistent comparison.
    - Sorts lists for consistent comparison, unless they contain dictionaries.
    """
    if isinstance(d, dict):
        return {k: normalize_numbers(v) for k, v in d.items()}
    elif isinstance(d, list):
        # Only sort the list if it contains non-dictionary elements
        if all(isinstance(i, (int, float, str)) for i in d):
            return sorted(normalize_numbers(i) for i in d)
        else:
            return [normalize_numbers(i) for i in d]  # Do not sort if dictionaries are present
    elif isinstance(d, (int, float)):
        return float(d)  # Convert all numbers to floats
    elif isinstance(d, str):
        return d.strip()  # Handle strings by stripping whitespace
    return d


# Function to get the ID by name
def get_integration_id_by_name(data, target_name):
    definitions = data.get("Definitions", [])

    for definition in definitions:
        params = definition.get("Params", {})
        name = params.get("name")
        if name == target_name:
            return definition.get("ID")

    return None


def get_value_by_name(checked_filters, filter_name):
    """
    search in a Value / Name dictionary
    """
    if checked_filters:
        for checked_filter in checked_filters:
            if checked_filter['Name'] == filter_name:
                return checked_filter['Value']
    return None
