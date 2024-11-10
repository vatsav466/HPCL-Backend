import os
import sys
import enum
import typing
import pydantic
import pydantic_settings

EnvConfigFile = ".alg_env"
Db_Urls_Base = {
        "mongo": [
            "mongodb://localhost"
        ],
        "elastic": [
            "https://admin:password@localhost:9200"
        ],
        "postgres_async": [
            "postgresql+asyncpg://localhost:5432/hpcl_ceg?user=postgres&password=1234"
        ],
        "redis": [
            "redis://localhost:6379"
        ]
    }


class MultiTenancyMode(str, enum.Enum):
    SingleServerSingleDb = 'SingleServerSingleDb'
    SingleServerMultiDb = 'SingleServerMultiDb'
    MultiServerSingleDb = 'MultiServerSingleDb'
    MultiServerMultiDb = 'MultiServerMultiDb'


def configure_db_urls(db_urls):
    for key, value in Db_Urls_Base.items():
        if key not in db_urls:
            db_urls[key] = [pydantic.AnyUrl(url) for url in value]
    return db_urls


class Settings(pydantic_settings.BaseSettings):
    model_config = pydantic_settings.SettingsConfigDict(env_file=EnvConfigFile, extra='ignore')
    # Domain defaults
    app_name: str = "hpcl_ceg"
    cookie_name: str = "hpcl_ceg"
    default_index: str = "hpcl_ceg"
    multi_tenant_support: bool = True

    # Header based authentication Enabled or Not
    enable_header_auth: bool = False

    # Keycloak Auth Server
    keycloak_external_url: pydantic.AnyHttpUrl = 'https://localhost:8443'
    keycloak_auth_default: str = "auth"
    keycloak_internal_url: pydantic.AnyHttpUrl = 'https://localhost:8443'
    keycloak_admin: str = 'admin'
    keycloak_password: str = 'password'
    keycloak_db_password: str = 'admin'
    fernet_key: str = 'NjY5N2IwOWM5ZjE0MjMzN2M3YzA5Y2Y4ZDE4NTA2Mjk='
    default_realm: str = 'hpcl'
    roles_directories: typing.List[str] = []

    # For Logger
    log_base_dir: str = "/var/log/ceg_logs"
    log_max_size: int = 10000000
    log_max_count: int = 5

    # DB Multi-tenancy model
    db_multi_tenancy_model: MultiTenancyMode = MultiTenancyMode.SingleServerSingleDb
    login_count: int = 5
    base_path: str = ""
    mft_path: str = ""
    ui_path: str = ""
    download_path: str = ""
    kibana_dashboard_header: str = 'osd-xsrf'
    db_urls: typing.Dict[str, typing.List[pydantic.AnyUrl]] = Db_Urls_Base

    # Postgresql settings
    enable_echo: bool = True

    # Session configuration settings
    session_same_site: str = 'lax'
    session_secure: bool = True
    session_httponly: bool = True

    # For importing Urdhva framework packages
    import_paths: typing.Dict[str, str] = {}

    # No Auth Urls
    noauth_urls: typing.List[str] = []

    # Kafka
    kafka_enabled: bool = False
    kafka_bootstrap_servers: str = 'localhost:9092'

    # Superset
    superset_internal_url: str = 'http://localhost:8088'
    superset_external_url: str = 'http://localhost:8088'
    superset_user: str = "admin"
    superset_password: str = 'password'

    # camunda
    camunda_url: str = 'http://localhost:8080'
    camunda_default_config: typing.Dict[str, int] = {
        "maxTasks": 1,
        "lockDuration": 10000,
        "asyncResponseTimeout": 5000,
        "retries": 3,
        "retryTimeout": 5000,
        "sleepSeconds": 30
    }

    def db_url(self, db):
        if self.db_multi_tenancy_model == MultiTenancyMode.SingleServerSingleDb or \
                self.db_multi_tenancy_model == MultiTenancyMode.SingleServerMultiDb:
            return self.db_urls.get(db, [])[0]

    class ConfigDict:
        env_file = EnvConfigFile
        case_sensitive = False


settings = Settings()

# Loading provided paths
if len(settings.import_paths) > 0:
    for _, path in settings.import_paths.items():
        if os.path.exists(path) and os.path.isdir(path):
            sys.path.append(path)

configure_db_urls(settings.db_urls)
