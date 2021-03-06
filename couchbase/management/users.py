from abc import abstractmethod

from couchbase.management.admin import Admin
from couchbase.options import timedelta, forward_args
from couchbase.management.generic import GenericManager
from couchbase_core import mk_formstr, JSONMapping, Mapped
from couchbase.auth import AuthDomain
from couchbase_core._pyport import ulp, with_metaclass, Protocol
from couchbase_core import ABCMeta
from typing import *
from couchbase.options import OptionBlockTimeOut
from couchbase.exceptions import HTTPException, ErrorMapper, NotSupportedWrapper


class GroupNotFoundException(HTTPException):
    """ The RBAC Group was not found"""


class UserNotFoundException(HTTPException):
    """ The RBAC User was not found"""


class UserErrorHandler(ErrorMapper):
    @staticmethod
    def mapping():
        # type (...)->Mapping[str, CBErrorType]
        return {HTTPException: {'Unknown group': GroupNotFoundException,
                            'Unknown user': UserNotFoundException}}


@UserErrorHandler.wrap
class UserManager(GenericManager):
    def __init__(self,  # type: UserManager
                 admin):
        """User Manager
        Programmatic access to the user management REST API:
        https://docs.couchbase.com/server/current/rest-api/rbac.html

        Unless otherwise indicated, all objects SHOULD be immutable.
        :param parent_cluster: """
        super(UserManager, self).__init__(admin)

    def get_user(self,  # type: UserManager
                 username,  # type: str
                 domain_name=AuthDomain.Local,  # type: str
                 timeout=None  # timedelta
                 ):
        pass

    #@mgmt_exc_wrap
    def get_user(self,  # type: UserManager
                 username,  # type: str
                 domain_name=AuthDomain.Local,  # type: AuthDomain
                 *options,  # type: GetUserOptions
                 **kwargs
                 ):
        # type: (...) -> UserAndMetadata
        """
        Gets a user.

        :param str username: ID of the user.
        :param AuthDomain domain_name: name of the user domain. Defaults to local.
        :param timedelta timeout: the time allowed for the operation to be terminated. This is controlled by the client.

        :returns: An instance of UserAndMetadata.

        :raises: UserNotFoundException
        :raises: InvalidArgumentsException
        Any exceptions raised by the underlying platform
        """

        # Implementation Notes
        # When parsing the "get" and "getAll" responses,
        # take care to distinguish between roles assigned directly to the user (role origin with type="user") and
        # roles inherited from groups (role origin with type="group" and name=<group name>).
        # If the server response does not include an "origins" field for a role,
        # then it was generated by a server version prior to 6.5 and the SDK MUST treat the role as if it had a
        # single origin of type="user".
        return RawUserAndMetadata(self._admin_bucket.user_get(domain_name, username,
                                                              **forward_args(kwargs, *options)))

    @overload
    def get_all_users(self,  # type: UserManager
                      domain_name,  # type: str
                      timeout=None  # type: timedelta
                      ):
        pass

    def get_all_users(self,  # type: UserManager
                      domain_name,  # type: str
                      *options,  # type: GetAllUsersOptions
                      **kwargs
                      ):
        # type: (...) -> Iterable[UserAndMetadata]
        """

        :param domain_name: name of the user domain. Defaults to local.
        :param options:
        :param timedelta timeout: the time allowed for the operation to be terminated. This is controlled by the client.

        :return: An iterable collection of UserAndMetadata.

        """
        return list(map(RawUserAndMetadata,
                        self._admin_bucket.users_get(domain=domain_name,
                                                     **forward_args(kwargs, *options)).value))

    @overload
    def upsert_user(self,  # type: UserManager
                    user,  # type: User
                    domain=AuthDomain.Local,  # type: AuthDomain
                    timeout=None  # type: timedelta
                    ):
        pass

    def upsert_user(self,  # type: UserManager
                    user,  # type: User
                    domain=AuthDomain.Local,  # type: AuthDomain
                    *options,  # type: UpsertUserOptions
                    **kwargs
                    ):
        """
        Creates or updates a user.

        :param User user: the new version of the user.
        :param AuthDomain domain: name of the user domain (local | external). Defaults to local.
        :param timedelta timeout: the time allowed for the operation to be terminated. This is controlled by the client.

        :raises: InvalidArgumentsException
        """

        # Implementation Notes
        #
        # When building the PUT request to send to the REST endpoint, implementations MUST omit the "password" property
        # if it is not present in the given User domain object (so that the password is only changed if the calling code
        # provided a new password).
        #
        # For backwards compatibility with Couchbase Server 6.0 and earlier,
        # the "groups" parameter MUST be omitted if the group list is empty. Couchbase Server 6.5 treats the absent parameter the same as an explicit parameter with no value (removes any existing group associations, which is what we want in this case).

        final_opts = {k: v for k, v in user.as_dict.items() if k in {'password', 'roles', 'name', 'timeout'}}
        self._admin_bucket.user_upsert(domain, user.username, **final_opts)

    @overload
    def drop_user(self,  # type: UserManager
                  user_name,  # type: str
                  domain=AuthDomain.Local,  # type: AuthDomain
                  timeout=None  # type: timedelta
                  ):
        pass

    def drop_user(self,  # type: UserManager
                  user_name,  # type: str
                  domain=AuthDomain.Local,  # type: AuthDomain
                  *options,  # type: DropUserOptions
                  **kwargs
                  ):
        """
        Removes a user.

        :param str user_name: ID of the user.
        :param AuthDomain domain: name of the user domain. Defaults to local.
        :param timedelta timeout: the time allowed for the operation to be terminated. This is controlled by the client.
        :return:

        :raises: UserNotFoundException
        :raises: InvalidArgumentsException
        """
        final_args = forward_args(kwargs, *options)
        self._admin_bucket.user_remove(domain, user_name, **final_args)

    @overload
    def get_roles(self,  # type: UserManager
                  timeout=None,  # type: timedelta
                  *options):
        pass

    def get_roles(self,  # type: UserManager
                  *options,  # type: GetRolesOptions
                  **kwargs
                  ):
        # type: (...) -> Iterable[RoleAndDescription]
        """
        Returns the roles supported by the server.

        :param options: misc options
        :param timedelta timeout: the time allowed for the operation to be terminated. This is controlled by the client.
        :return: An iterable collection of RoleAndDescription.
        """
        return list(map(lambda x: RoleAndDescription.of(**x), self._admin_bucket.http_request("/settings/rbac/roles/",
                                                                                **forward_args(kwargs, *options)).value))

    @overload
    def get_group(self,  # type: UserManager
                  group_name,  # type: str
                  timeout=None  # type: timedelta
                  ):
        pass

    def get_group(self,  # type: UserManager
                  group_name,  # type: str
                  *options,  # type: GetGroupOptions
                  **kwargs
                  ):
        # type: (...) -> Group
        """
        Get info about the named group.

        :param str group_name: name of the group to get.
        :param timedelta timeout: the time allowed for the operation to be terminated. This is controlled by the client.
        :return: An instance of Group.
        :raises: GroupNotFoundException
        :raises: InvalidArgumentsException
        """
        return Group.from_json(self._admin_bucket.http_request("/settings/rbac/groups/{}".format(group_name),
                                                               **forward_args(kwargs, *options)).value)


    @overload
    def get_all_groups(self,  # type: UserManager
                       timeout=None,  # type: timedelta
                       *options  # type: GetAllGroupsOptions
                       ):
        pass

    @NotSupportedWrapper.a_404_means_not_supported
    def get_all_groups(self,  # type: UserManager
                       *options,  # type: GetAllGroupsOptions
                       **kwargs
                       ):
        # type: (...) -> Iterable[Group]
        """
        Get all groups.

        :param timedelta timeout: the time allowed for the operation to be terminated. This is controlled by the client.
        :returns: An iterable collection of Group.
        """
        groups = self._admin_bucket.http_request("/settings/rbac/groups/",
                                                 **forward_args(kwargs, *options))
        return list(
            map(Group.from_json, groups.value))

    @overload
    def upsert_group(self,  # type: UserManager
                     group,  # type: Group
                     timeout=None  # type: timedelta
                     ):
        pass

    def upsert_group(self,  # type: UserManager
                     group,  # type: Group
                     *options,  # type: UpsertGroupOptions
                     **kwargs
                     ):
        """
        Add or replace a group.

        :warning: Does not appear to work correctly yet - tracked here: https://issues.couchbase.com/browse/PYCBC-667

        :param Group group: the new version of the group.
        :param timedelta timeout: the time allowed for the operation to be terminated. This is controlled by the client.
        :raises: InvalidArgumentsException
        """
        # This endpoint accepts application/x-www-form-urlencoded and requires the data be sent as form data.
        # The name/id should not be included in the form data.
        # Roles should be a comma separated list of strings.
        # If, only if, the role contains a bucket name then the rolename should be suffixed
        # with[<bucket_name>] e.g. bucket_full_access[default],security_admin.

        group_dict = group.as_dict()
        form_data = mk_formstr(group_dict)
        self._admin_bucket.http_request(path="/settings/rbac/groups/{}".format(group.name),
                                        method='PUT',
                                        content=form_data,
                                        content_type='application/x-www-form-urlencoded',
                                        **forward_args(kwargs, *options))

    @overload
    def drop_group(self,  # type: UserManager
                   group_name,  # type: str
                   timeout=None  # type: timedelta
                   ):
        pass

    def drop_group(self,  # type: UserManager
                   group_name,  # type: str
                   *options,  # type: DropGroupOptions
                   **kwargs
                   ):
        """
        Removes a group.

        :param str group_name: name of the group.
        :param timedelta timeout: the time allowed for the operation to be terminated. This is controlled by the client.

        :raises: GroupNotFoundException
        :raises: InvalidArgumentsException
        """
        self._admin_bucket.http_request("/settings/rbac/groups/{}".format(group_name), method='DELETE',
                                        **forward_args(kwargs, *options))


RawRole = NamedTuple('RawRole', [('name', str), ('bucket', str)])


class Role(with_metaclass(ABCMeta, Mapped)):
    """A role identifies a specific permission. CAVEAT,  # type: The properties of a role are likely to change with the introduction of collection-level permissions. Until then
    here's what the accessor methods look like:
    """
    factory = RawRole

    @staticmethod
    def defaults():
        return {'bucket': None}

    @staticmethod
    def mappings():
        return {'role': 'name'}

    @property
    @abstractmethod
    def name(self):
        pass

    @property
    @abstractmethod
    def bucket(self):
        pass

    def __iter__(self):
        return iter([self.name, self.bucket])

    def __str__(self):
        return Admin._role_to_str(self)

    @classmethod
    def decode(cls, param):
        if isinstance(param, str):
            param = Admin._str_to_role(param)
        if isinstance(param, dict):
            args = list(map(param.get, ('role', 'bucket')))
        else:
            args = param
        return cls.factory(*args)


RawRoleAndDescription = NamedTuple('RawRoleAndDescription',
                                   [('role', Role),
                                    ('display_name', str),
                                    ('description', str),
                                    ('ce', Any),
                                    ('bucket_name', str)])


class RoleAndDescription(with_metaclass(ABCMeta, Mapped)):
    """ Associates a role with its name and description.
    This is additional information only present in the "list available roles" response."""

    factory = RawRoleAndDescription

    @staticmethod
    def defaults():
        return {'ce': True, 'bucket_name':None}

    @staticmethod
    def mappings():
        return {'desc':'description', 'name': 'display_name'}

    @property
    @abstractmethod
    def role(self):
        # type: (...) -> Role
        return None

    @property
    @abstractmethod
    def ce(self):
        # type: (...) -> Role
        return None

    @property
    @abstractmethod
    def display_name(self):
        # type: (...) -> str
        return None

    @property
    @abstractmethod
    def description(self):
        # type: (...) -> str
        pass

    @classmethod
    def of(cls, *args, **kwargs):
        return Mapped._of(cls, *args, **kwargs)


class Origin(object):
    def __init__(self):
        """Indicates why the user has a specific role.
        If the type is "user" it means the role is assigned directly to the user. If the type is "group" it means the role is inherited from the group identified by the "name" field."""

    @property
    def type(self):
        # type: (...) -> str
        pass

    @property
    def name(self):
        # type: (...) -> str
        return None


class RoleAndOrigins(object):
    def __init__(self):
        """Associates a role with its origins.
        This is how roles are returned by the "get user" and "get all users" responses."""

    @property
    def role(self):
        # type: (...) -> Role
        pass

    @property
    def origins(self):
        # type: (...) -> List[Origin]
        pass


class User(object):
    @overload
    def __init__(self, username=None, display_name=None, password=None, groups=None, roles=None):
        pass

    def __init__(self, **raw_data):
        self._raw_data = raw_data

    @property
    def username(self):
        # type: (...) -> str
        return self._raw_data.get('username')

    @property
    def display_name(self):
        # type: (...) -> str
        return self._raw_data.get('username')

    @property
    def groups(self):
        # type: (...) -> Set[str]
        """names of the groups"""
        return set(self._raw_data.get('groups', []))

    @property
    def roles(self):
        # type: (...) -> Set[Role]
        """only roles assigned directly to the user (not inherited from groups)"""
        return self._raw_data.get('roles')

    @property
    def password(self):
        # type: (...) -> None
        """ From the user's perspective the password property is "write-only".
        The accessor SHOULD be hidden from the user and be visible only to the manager implementation."""
        return self._raw_data.get('password')

    @password.setter
    def password(self, value):
        self._raw_data['password'] = value

    @property
    def as_dict(self):
        return self._raw_data


class UserAndMetadata(object):
    """Models the "get user" / "get all users" response.
    Associates the mutable properties of a user with derived properties such as the effective roles inherited from groups."""

    @property
    def domain(self):
        # type: (...) -> AuthDomain
        """ AuthDomain is an enumeration with values "local" and "external".
        It MAY alternatively be represented as String."""

    @property
    def user(self):
        # type: (...) -> User
        """- returns a new mutable User object each time this method is called.
        Modifying the fields of the returned User MUST have no effect on the UserAndMetadata object it came from."""

    @property
    def effective_roles(self):
        # type: (...) -> Set[Role]
        """all roles, regardless of origin."""

    @property
    def effective_roles_and_origins(self):
        # type: (...) -> List[RoleAndOrigins]
        """same as effectiveRoles, but with origin information included."""
        pass

    @property
    def password_changed(self):
        # type: (...) -> Optional[float]
        pass

    @property
    def external_groups(self):
        # type: (...) -> Set[str]
        pass


class RawUserAndMetadata(UserAndMetadata):
    def __init__(self, raw_data):
        self._raw_data = raw_data

    @property
    def domain(self):
        # type: (...) -> AuthDomain
        """ AuthDomain is an enumeration with values "local" and "external".
        It MAY alternatively be represented as String."""
        return self._raw_data.get('domain')

    @property
    def user(self):
        # type: (...) -> User
        """- returns a new mutable User object each time this method is called.
        Modifying the fields of the returned User MUST have no effect on the UserAndMetadata object it came from."""
        return User(**self._raw_data.get('user'))

    @property
    def effective_roles(self):
        # type: (...) -> Set[Role]
        """all roles, regardless of origin."""
        return set(map(Role, self._raw_data.get('effective_roles')))

    @property
    def effective_roles_and_origins(self):
        # type: (...) -> List[RoleAndOrigins]
        """same as effectiveRoles, but with origin information included."""
        return list(map(RoleAndOrigins, self._raw_data.get('effective_roles_and_origins')))

    @property
    def password_changed(self):
        # type: (...) -> Optional[float]
        return self._raw_data.get('password_changed')

    @property
    def external_groups(self):
        # type: (...) -> Set[str]
        return set(self._raw_data.get('external_groups'))


class Group(JSONMapping):
    @staticmethod
    def defaults():
      return {'description': '', 'ldap_group_ref': ''}

    @overload
    def __init__(self, name, description=None, roles=None, ldap_group_reference=None):
        pass

    def __init__(self, name, **kwargs):
        self._name = name
        super(Group,self).__init__(kwargs)

    @property
    def name(self):
        return self._name

    ldap_group_reference=JSONMapping._genprop('ldap_group_ref')
    @property
    def roles(self):
        return set(map(Role.decode, self._raw_json['roles']))

    @roles.setter
    def roles(self, value):
        self._raw_json['roles']=list(map(Admin._role_to_str, value))

    @staticmethod
    def from_json(kwargs):
        name = kwargs.pop('id')
        return Group(name, **kwargs)

    def as_dict(self):
        result = {k: v for k, v in self._raw_json.items() if v}
        if 'roles' in result:
          result['roles'] = ','.join(map(ulp.quote, result['roles']))
        else:
          result['roles'] = []
        return result

    def __eq__(self, other):
        return self.name == other.name and self._raw_json == other._raw_json

    def __repr__(self):
        return '{}:{}'.format(self.name, repr(self._raw_json))


class GetUserOptions(OptionBlockTimeOut):
    pass


class UpsertUserOptions(OptionBlockTimeOut):
    pass


class GetRolesOptions(OptionBlockTimeOut):
    pass


class GetGroupOptions(OptionBlockTimeOut):
    pass


class GetAllGroupsOptions(OptionBlockTimeOut):
    pass


class DropGroupOptions(OptionBlockTimeOut):
    pass


class DropUserOptions(OptionBlockTimeOut):
    pass


class GetAllUsersOptions(OptionBlockTimeOut):
    pass


class UpsertGroupOptions(OptionBlockTimeOut):
    pass
