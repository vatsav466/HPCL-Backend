import urdhva_base
import json
import hpcl_ceg_model


class AuthenticationManager:
    """
    A class to manage user authentication, roles, and permissions.
    """

    @classmethod
    async def login(cls, username, password):
        """
        Authenticates a user based on their username and password.

        Args:
            username (str): The username of the user.
            password (str): The password of the user.

        Returns:
            bool: True if authentication is successful, False otherwise.
        """
        data = hpcl_ceg_model.Users.get_aggr_data(f"select * from users where "
                                                  f"lower(username)='{username.lower()}'", skip_total=True)
        # If provided password not equals to db password, skip authentication
        if not data["data"] or urdhva_base.types.Secret(data["data"]["password"]).get_secret() != password:
            return False, "Invalid user or wrong password"
        return True, "Success"

    @classmethod
    async def create_user(cls, username, password, role, first_name, last_name, employee_id, status=True):
        """
        Creates a new user with the specified username, password, and status.

        Args:
            username (str): The username for the new user.
            password (str): The password for the new user.
            role (list): Role attached for user
            first_name (str): First name of the user
            last_name (str): Last name of the user
            employee_id (str): Employee ID of the user
            status (bool): The active status of the user (default is True).

        Returns:
            None
        """
        data = hpcl_ceg_model.Users.get_aggr_data(f"select username from users where "
                                                  f"lower(username)='{username.lower()}'", skip_total=True)
        if data["data"]:
            for user in data["data"]:
                if user["username"].lower() == username.lower():
                    return False, "user exists"
        await hpcl_ceg_model.Users(**{"username": username.lower(), "password": password, "role": role,
                                      "first_name": first_name, "last_name": last_name, "employee_id": employee_id,
                                      "status": True}).create()
        return True, "User created successfully"

    @classmethod
    async def update_user_role(cls, username, role):
        """
        Updates the role assigned to a specific user.

        Args:
            username (str): The username of the user whose role is being updated.
            role (str): The new role to assign to the user.

        Returns:
            None
        """
        ...

    @classmethod
    async def update_user_status(cls, username, status):
        """
        Updates the active status of a user.

        Args:
            username (str): The username of the user.
            status (bool): The new status (True for active, False for inactive).

        Returns:
            None
        """
        ...

    @classmethod
    async def fetch_users(cls, search_string, limit, skip):
        """
        Fetches a list of users based on a search query, with pagination support.

        Args:
            search_string (str): A string to filter users by (e.g., username or other criteria).
            limit (int): The maximum number of users to fetch in this query.
            skip (int): The number of users to skip (used for pagination).

        Returns:
            list: A list of user objects or dictionaries matching the search criteria.
        """
        ...

    @classmethod
    async def create_role(cls, name, allowed_pages, status=True):
        """
        Creates a new role with the specified permissions and status.

        Args:
            name (str): The name of the role.
            allowed_pages (list): A list of pages or actions the role has access to.
            status (bool): The active status of the role (default is True).

        Returns:
            None
        """
        ...

    @classmethod
    async def update_role_status(cls, name, status):
        """
        Updates the active status of a role.

        Args:
            name (str): The name of the role.
            status (bool): The new status (True for active, False for inactive).

        Returns:
            None
        """
        ...

    @classmethod
    async def get_all_role_pages(cls):
        """
        Retrieves all roles and their associated allowed pages.

        Returns:
            dict: A dictionary mapping roles to their allowed pages.
        """
        ...
