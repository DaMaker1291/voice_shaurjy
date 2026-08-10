"""JARVIS Artifacts — First-Class Output Objects.

Every output is an artifact with metadata:
- filename, type, creator, mission_id, checksum, verification_status
- Reproducible, traceable, verifiable
"""

import os, hashlib, time, json
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

ARTIFACTS_PATH = Path("/opt/jarvis/artifacts.json")


@dataclass
class Artifact:
    filename: str
    artifact_type: str  # pptx, docx, xlsx, py, html, png, mp4, etc.
    mission_id: str = ""
    creator: str = ""  # agent name
    source_files: list = field(default_factory=list)
    dependencies: list = field(default_factory=list)
    creation_time: float = 0
    verification_status: str = "pending"  # pending, verified, failed
    checksum: str = ""
    version: int = 1
    size_bytes: int = 0
    tags: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict) -> "Artifact":
        return Artifact(**{k: v for k, v in data.items() if k in Artifact.__dataclass_fields__})


class ArtifactRegistry:
    """Registry of all artifacts produced by JARVIS."""

    def __init__(self):
        self.artifacts: list[Artifact] = []
        self._load()

    def _load(self):
        if ARTIFACTS_PATH.exists():
            try:
                data = json.loads(ARTIFACTS_PATH.read_text())
                self.artifacts = [Artifact.from_dict(a) for a in data.get("artifacts", [])]
            except Exception:
                pass

    def save(self):
        ARTIFACTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        data = {"artifacts": [a.to_dict() for a in self.artifacts[-200:]]}
        ARTIFACTS_PATH.write_text(json.dumps(data, indent=2))

    def register(self, filename: str, artifact_type: str, mission_id: str = "",
                 creator: str = "", source_files: list = None,
                 tags: list = None) -> Artifact:
        """Register a new artifact."""
        filepath = Path(filename)
        checksum = ""
        size = 0
        if filepath.exists():
            size = filepath.stat().st_size
            try:
                h = hashlib.sha256()
                with open(filepath, 'rb') as f:
                    for chunk in iter(lambda: f.read(8192), b''):
                        h.update(chunk)
                checksum = h.hexdigest()[:16]
            except Exception:
                pass

        artifact = Artifact(
            filename=str(filepath.absolute()),
            artifact_type=artifact_type,
            mission_id=mission_id,
            creator=creator,
            source_files=source_files or [],
            creation_time=time.time(),
            checksum=checksum,
            size_bytes=size,
            tags=tags or [],
        )
        self.artifacts.append(artifact)
        self.save()
        return artifact

    def verify(self, filename: str) -> dict:
        """Verify an artifact matches its stored checksum."""
        filepath = Path(filename)
        if not filepath.exists():
            return {"exists": False, "verified": False}

        artifact = None
        for a in self.artifacts:
            if a.filename == str(filepath.absolute()):
                artifact = a
                break

        if not artifact:
            return {"exists": True, "verified": False, "reason": "not_registered"}

        if not artifact.checksum:
            return {"exists": True, "verified": False, "reason": "no_checksum"}

        h = hashlib.sha256()
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                h.update(chunk)
        current = h.hexdigest()[:16]

        match = current == artifact.checksum
        if match:
            artifact.verification_status = "verified"
        else:
            artifact.verification_status = "failed"
        self.save()

        return {"exists": True, "verified": match, "checksum_match": match}

    def get_by_mission(self, mission_id: str) -> list[Artifact]:
        """Get all artifacts from a mission."""
        return [a for a in self.artifacts if a.mission_id == mission_id]

    def get_by_type(self, artifact_type: str) -> list[Artifact]:
        """Get all artifacts of a type."""
        return [a for a in self.artifacts if a.artifact_type == artifact_type]

    def get_recent(self, limit: int = 10) -> list[Artifact]:
        """Get most recent artifacts."""
        return sorted(self.artifacts, key=lambda a: a.creation_time, reverse=True)[:limit]

    def search(self, query: str) -> list[Artifact]:
        """Search artifacts by filename, type, or tags."""
        q = query.lower()
        return [a for a in self.artifacts
                if q in a.filename.lower() or q in a.artifact_type.lower()
                or any(q in t.lower() for t in a.tags)]


_registry: Optional[ArtifactRegistry] = None

def get_artifact_registry() -> ArtifactRegistry:
    global _registry
    if _registry is None:
        _registry = ArtifactRegistry()
    return _registry
