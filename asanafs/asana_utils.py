import io
from yaml.representer import SafeRepresenter
import asana
import os
import yaml
from functools import cache, cached_property
import dateutil.parser

import logging

logger = logging.getLogger(__name__)


def user_repr(user: dict):
    return f"{user['name']} <{user['email']}>"


class Asana:
    def __init__(self, token: str | None = None, eager_cache: bool = True):
        """Slim wrapper around the asana sdk to cache certain resources and
        provide helper functions

        :param token: asana personal access token
        :param eager_cache: if True, populate the caches as part of init
        """
        if token is None:
            token = os.getenv("ASANA_API_KEY")
        self.client = asana.Client.access_token(token)

        if eager_cache:
            logger.debug("Eagerly populating cache...")
            self.workspaces
            self.projects_by_workspace
            for wn in self.workspaces.keys():
                for pn in self.projects_by_workspace[wn].keys():
                    self.project_tasks(workspace=wn, project=pn)
        logger.info("Finished init")

    @cached_property
    @cache
    def workspaces(self):
        return {w["name"]: w for w in self.client.workspaces.get_workspaces()}

    @cached_property
    def projects_by_workspace(self):
        projects = {}
        for name, w in self.workspaces.items():
            w_projs = {
                p["name"]: p
                for p in list(self.client.projects.get_projects(workspace=w["gid"]))
            }
            projects[name] = w_projs
            projects[w["gid"]] = w_projs
        logger.debug(projects)
        return projects

    @cache
    def project_tasks(self: str, workspace: str, project: str):
        r = {
            t["name"]: t
            for t in self.client.tasks.find_by_project(
                self.projects_by_workspace[workspace][project]["gid"]
            )
        }
        logger.debug(r)
        return r

    @cache
    def get_user(self, user_gid: str, params=None, **options) -> dict:
        return self.client.users.get_user(
            user_gid=user_gid, params=params, options=options
        )

    @cache
    def path_to_task_gid(self, workspace: str, project: str, task: str):
        task_gid = [
            t
            for _, t in self.project_tasks(workspace, project).items()
            if t["name"] == task
        ][0]["gid"]
        return task_gid

    @cache
    def path_to_task(self, workspace: str, project: str, task: str):
        task_gid = self.path_to_task_gid(workspace, project, task)
        task = self.client.tasks.get_task(task_gid=task_gid)
        return AsanaTask(task=task, asana=self)


class AsanaTask:
    _raw: dict
    asana: Asana
    line_width: int = 80

    name: str
    done: bool
    link: str
    notes: str
    assignee: str | None
    followers: list[str]
    due_on: str
    created: str
    updated: str

    def __init__(
        self,
        task: dict,
        asana: Asana = None,
    ):
        if asana is None:
            self.asana = Asana()
        self._raw = task
        self.asana = asana
        self.name = self._raw["name"]
        self.done = self._raw["completed"]
        self.link = self._raw["permalink_url"]
        self.notes = self._raw["notes"]
        self.due_on = self._raw["due_on"]
        self.created = self._raw["created_at"]
        self.updated = self._raw["modified_at"]

    @cached_property
    def followers(self) -> list[str]:
        return [
            user_repr(self.asana.get_user(f["gid"])) for f in self._raw["followers"]
        ]

    @cached_property
    def assignee(self) -> str | None:
        assignee = None
        try:
            gid = self._raw["assignee"]["gid"]
            assignee = user_repr(self.asana.get_user(gid))
        except (KeyError, TypeError):
            pass
        return assignee

    @property
    def st_mtime(self):
        return dateutil.parser.parse(self.updated).timestamp()

    @property
    def st_size(self):
        return len(self.dump().encode("utf-8"))

    @property
    def _asdict_for_dump(self) -> dict:
        """Representation dict to pass to yaml.dump, which may include special
        types for controlling yaml styling

        TODO: imo it would be cool if the created/updated fields included
        comments with human-friendly relative time
        """
        r = dict(
            name=self.name,
            done=self.done,
            link=self.link,
            notes=self.notes,
            metadata=dict(
                assignee=self.assignee,
                followers=self.followers,
                due_on=self.due_on,
                created=self.created,
                updated=self.updated,
            ),
        )

        if len(self.notes) >= self.line_width:
            r["notes"] = folded_str(self.notes)

        return r

    def dump(self, stream: io.BytesIO | None = None) -> str:
        """Dump task to pretty yaml output

        :param stream: if set, also dump contents to the stream. defaults to None
        :return: yaml-serialized representation of the task
        """
        return yaml.safe_dump(
            data=self._asdict_for_dump,
            stream=stream,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
            width=self.line_width,
        )


#################################################################################
# yaml representation funtimes
# https://stackoverflow.com/questions/6432605/any-yaml-libraries-in-python-that-support-dumping-of-long-strings-as-block-liter
#################################################################################


def change_yaml_style(style, representer):
    def new_representer(dumper, data):
        scalar = representer(dumper, data)
        scalar.style = style
        return scalar

    return new_representer


# represent_str does handle some corner cases, so use that
# instead of calling represent_scalar directly
represent_folded_str = change_yaml_style(">", SafeRepresenter.represent_str)
represent_literal_str = change_yaml_style("|", SafeRepresenter.represent_str)


class folded_str(str):
    pass


class literal_str(str):
    pass


yaml.add_representer(folded_str, represent_folded_str, Dumper=yaml.SafeDumper)
yaml.add_representer(literal_str, represent_literal_str, Dumper=yaml.SafeDumper)
