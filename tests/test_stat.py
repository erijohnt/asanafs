from pathlib import Path
import trio
import pytest
import asanafs
import pyfuse3


@pytest.fixture
async def asana_fuse(
    source: str = "/", mountpoint: str = "/home/eli/asana", debug: bool = True
):
    fuse_options = set(pyfuse3.default_options)
    fuse_options.add("fsname=asanafs")
    fuse_options.add("debug")
    try:
        operations = asanafs.AsanaFS(root=source)
        pyfuse3.init(operations, mountpoint, fuse_options)
        await pyfuse3.main()
    except (Exception, KeyboardInterrupt) as e:
        pyfuse3.close(unmount=True)
        raise e

    pyfuse3.close(unmount=True)


async def test_stat(asana_fuse, root_dir: Path | None = None):
    """Sorry this only works for eli :)"""
    if root_dir is None:
        root_dir = Path("/home/eli/asana")
    root_dir.stat
    (root_dir / "My workspace").stat
    (root_dir / "My workspace" / "burn").stat
    (root_dir / "My workspace" / "burn" / "Pack lists").stat
