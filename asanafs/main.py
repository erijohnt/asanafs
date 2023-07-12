import errno
import io

import asana_utils as asana

import sys
import stat
import os
import fuse
import pathlib
import logging
from fuse import FuseOSError


logging.basicConfig(level=logging.DEBUG)


class AsanaFS(fuse.LoggingMixIn, fuse.Operations):
    def __init__(self, root):
        self.root = root
        self.open_files = {}

        token = os.getenv("ASANA_API_KEY")
        assert token, "Missing ASANA_API_KEY with personal access token"
        self.asana = asana.Asana(token)

    def readdir(self, path, fh):
        dirents = [".", ".."]
        path = pathlib.Path(path)
        breakpoint()
        if path == pathlib.Path("/"):
            # list workspaces
            dirents.extend(self.asana.workspaces.keys())
        elif len(path.parts) == 2:
            # list projects within a workspace
            _, workspace = path.parts
            dirents.extend(self.asana.projects_by_workspace[workspace].keys())
        elif len(path.parts) == 3:
            # list tasks within a project
            _, workspace, project = path.parts
            dirents.extend(list(self.asana.project_tasks(workspace, project).keys()))
        elif len(path.parts) == 4:
            # list task
            _, workspace, project, task = path.parts
            project_tasks = self.asana.project_tasks(workspace, project)
            dirents = [t for t in project_tasks if t == task]
        else:
            raise FuseOSError(errno.ENOENT)

        for r in dirents:
            yield r

    def getattr(self, path, fh=None):
        # https://linux.die.net/man/2/stat
        path = pathlib.Path(path)
        if len(path.parts) <= 3:
            # workspaces and projects are directories
            st_mode = 0o755 | stat.S_IFDIR
            st_size = 0
            st_mtime = 0
        else:
            # tasks are files
            st_mode = 0o755 | stat.S_IFREG
            _, workspace, project, task = path.parts
            task = self.asana.path_to_task(workspace, project, task)
            st_size = task.st_size
            st_mtime = task.st_mtime
        return dict(
            st_atime=0,
            st_ctime=0,
            st_gid=0,
            st_mode=st_mode,
            st_mtime=st_mtime,
            st_nlink=0,
            st_size=st_size,
            st_uid=0,
        )

    def read(self, path, length, offset, fh):
        print(f"params: {path=} {length=} {offset=}")
        path = pathlib.Path(path)
        _, workspace, project, task = path.parts
        task = self.asana.path_to_task(workspace, project, task).dump()
        task_io = io.BytesIO(initial_bytes=task.encode("utf-8"))
        task_io.seek(offset)
        return task_io.read(length)

    def flush(self, path, fh):
        pass

    def fsync(self, path, fdatasync, fh):
        pass

    def release(self, path, fh):
        pass

    def access(self, path, mode):
        pass


def main(mountpoint, root):
    fuse.FUSE(
        AsanaFS("/"), mountpoint, nothreads=False, foreground=True, allow_other=False
    )


if __name__ == "__main__":
    main(sys.argv[2], sys.argv[1])
