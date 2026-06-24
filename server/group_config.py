"""Group definition loader + model resolution. Pure; no FastAPI/Ollama import."""
import yaml


class GroupConfig:
    def __init__(self, name, shared_model, director_model, roster):
        self.name = name
        self.shared_model = shared_model
        self.director_model = director_model or shared_model
        self._roster = roster  # list of {"id": str, "model": str|None}

    @classmethod
    def load(cls, path):
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        roster = [{"id": m["id"], "model": m.get("model")} for m in data.get("roster", [])]
        return cls(
            name=data.get("name", "group"),
            shared_model=data.get("shared_model"),
            director_model=data.get("director_model"),
            roster=roster,
        )

    @property
    def member_ids(self):
        return [m["id"] for m in self._roster]

    def model_for(self, member_id):
        for m in self._roster:
            if m["id"] == member_id:
                return m["model"] or self.shared_model
        return self.shared_model

    def distinct_models(self):
        return sorted({self.model_for(mid) for mid in self.member_ids})
