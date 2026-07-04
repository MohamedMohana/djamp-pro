from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

# Default managed service ports (MAMP-style, avoids clobbering system services).
MANAGED_POSTGRES_PORT = 54329
MANAGED_MYSQL_PORT = 33069
MANAGED_REDIS_PORT = 6389


class DatabaseConfig(BaseModel):
    type: Literal["postgres", "mysql", "none"] = "none"
    port: int = MANAGED_POSTGRES_PORT
    name: str = ""
    username: str = ""
    password: str = ""


class CacheConfig(BaseModel):
    type: Literal["redis", "none"] = "none"
    port: int = MANAGED_REDIS_PORT


class Project(BaseModel):
    id: str
    name: str
    path: str
    settingsModule: str
    domain: str
    aliases: List[str] = Field(default_factory=list)
    port: int = 8000
    pythonVersion: str = "3.11"
    venvPath: str = ""
    debug: bool = True
    allowedHosts: List[str] = Field(default_factory=list)
    httpsEnabled: bool = True
    certificatePath: str = ""
    staticPath: str = "static"
    mediaPath: str = "media"
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    status: Literal["stopped", "starting", "running", "stopping", "error"] = "stopped"
    environmentVars: Dict[str, str] = Field(default_factory=dict)
    createdAt: str
    runtimeMode: Literal["uv", "conda", "system", "custom"] = "uv"
    condaEnv: str = ""
    customInterpreter: str = ""
    domainMode: Literal["local_only", "public_override"] = "local_only"


class AppSettings(BaseModel):
    caInstalled: bool = False
    defaultPython: str = "3.11"
    autoStartProjects: List[str] = Field(default_factory=list)
    proxyPort: int = 8443
    proxyHttpPort: int = 8080
    anyDomainOverrideEnabled: bool = False
    standardPortsEnabled: bool = True
    restoreOnQuit: bool = True


class Registry(BaseModel):
    projects: List[Project] = Field(default_factory=list)
    settings: AppSettings = Field(default_factory=AppSettings)


class CommandResult(BaseModel):
    success: bool
    output: str = ""
    error: str = ""


class DetectionResult(BaseModel):
    found: bool
    managePyPath: Optional[str] = None
    settingsModules: List[str] = Field(default_factory=list)


class CertificateInfo(BaseModel):
    domain: str
    certificatePath: str = ""
    keyPath: str = ""
    expiresAt: str = ""
    isValid: bool = False


class ProxyStatus(BaseModel):
    proxyHttpPort: int
    proxyPort: int
    standardPortsEnabled: bool
    standardHttpActive: bool
    standardHttpsActive: bool


class UpdateSettingsPayload(BaseModel):
    settings: Dict[str, Any]


class UpdateProjectPayload(BaseModel):
    id: str
    updates: Dict[str, Any]


class AddProjectPayload(BaseModel):
    project: Dict[str, Any]


class DomainPayload(BaseModel):
    domain: str


class CreateVenvPayload(BaseModel):
    path: str
    pythonVersion: str = "3.11"


class InstallDependenciesPayload(BaseModel):
    projectId: str


class ShellPayload(BaseModel):
    project_id: str


class CreateSuperuserPayload(BaseModel):
    username: str
    email: str
