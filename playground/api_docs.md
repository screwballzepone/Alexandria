# API Module Documentation

> Hypothetical module `api.py` — user management system.

---

## `create_user(name, email, age=None)`

Creates a new user in the system.

### Parameters

| Name    | Type          | Required | Description                          |
|---------|---------------|----------|--------------------------------------|
| `name`  | `str`         | Yes      | Full name of the user.               |
| `email` | `str`         | Yes      | Email address (must be unique).      |
| `age`   | `int` or None | No       | Age of the user in years. Defaults to `None`. |

### Returns

| Type  | Description                          |
|-------|--------------------------------------|
| `int` | The newly created user's ID.         |

---

## `delete_user(user_id, hard=False)`

Deletes a user by ID.

### Parameters

| Name      | Type   | Required | Description                                        |
|-----------|--------|----------|----------------------------------------------------|
| `user_id` | `int`  | Yes      | The ID of the user to delete.                      |
| `hard`    | `bool` | No       | If `True`, removes the user from DB entirely (not just soft-delete). Defaults to `False`. |

### Returns

| Type   | Description                          |
|--------|--------------------------------------|
| `bool` | `True` if the user was found and deleted, `False` otherwise. |

---

## `list_users(page=1, per_page=50)`

Lists users with pagination.

### Parameters

| Name       | Type  | Required | Description                                               |
|------------|-------|----------|-----------------------------------------------------------|
| `page`     | `int` | No       | The page number to retrieve (1-indexed). Defaults to `1`. |
| `per_page` | `int` | No       | Number of users per page. Defaults to `50`.               |

### Returns

| Type   | Description                                           |
|--------|-------------------------------------------------------|
| `list` | A list of user dicts for the requested page. Returns an empty list if the page is beyond the last result. |
