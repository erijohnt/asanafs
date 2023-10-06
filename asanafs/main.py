import errno
import io

import asana_utils as asana
import trio

import sys
import stat
import os
import pathlib
import pyfuse3
import logging


logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)


class AsanaFS(pyfuse3.Operations):
    def __init__(self, root):
        super(AsanaFS, self).__init__()
        self.root = root
        self.open_files = {}

        token = os.getenv("ASANA_API_KEY")
        assert token, "Missing ASANA_API_KEY with personal access token"
        self.asana = asana.Asana(token)

    async def readdir(self, path, fh):
        dirents = [".", ".."]
        path = pathlib.Path(path)
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
            raise pyfuse3.FUSEError(errno.ENOENT)

        for r in dirents:
            yield r

    async def getattr(self, inode, ctx=None):
        # https://linux.die.net/man/2/stat
        print(f"noooooosdfaslkdfasdfa {inode=}")
        return pyfuse3.EntryAttributes()
        if inode == 1:
            # workspaces and projects are directories
            st_mode = 0o755 | stat.S_IFDIR
            st_size = 0
            st_mtime = 0
        else:
            # tasks are files
            st_mode = 0o755 | stat.S_IFREG
            _, workspace, project, task = inode.parts
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

    async def statfs(self, ctx):
        return pyfuse3.StatvfsData()

    async def read(self, path, length, offset, fh):
        path = pathlib.Path(path)
        _, workspace, project, task = path.parts
        task = self.asana.path_to_task(workspace, project, task).dump()
        task_io = io.BytesIO(initial_bytes=task.encode("utf-8"))
        task_io.seek(offset)
        return task_io.read(length)

    async def flush(self, path, fh):
        pass

    async def fsync(self, path, fdatasync, fh):
        pass

    async def release(self, path, fh):
        pass

    async def access(self, path, mode):
        pass


def main(source: str, mountpoint: str, debug: bool = True):
    operations = AsanaFS(source)

    log.debug("Mounting...")
    fuse_options = set(pyfuse3.default_options)
    fuse_options.add("fsname=asanafs")
    if debug:
        fuse_options.add("debug")
    try:
        pyfuse3.init(operations, mountpoint, fuse_options)
        log.debug("Entering main loop..")
        trio.run(pyfuse3.main)
    except Exception as e:
        pyfuse3.close(unmount=True)
        raise e

    log.debug("Unmounting..")
    pyfuse3.close()


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
